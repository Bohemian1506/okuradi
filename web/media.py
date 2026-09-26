"""文字起こしを読むことと、音声を画面に配ること。"""

import json
import shutil
import subprocess
import wave
from pathlib import Path
from urllib.parse import quote


import build

from web import episodes, timeline

# 試聴のとき、区間の前後にこれだけ余白を付ける（響きの尾まで聴けるように）
PREVIEW_PAD = 0.4


def read_scan(name):
    """下見の文字起こし（`02_text/scan.json`）。

    時刻は、下見をかけた音そのもの（`source`）を基準にしている。
    再生もその音に合わせるので、行を押した位置と音がずれない。
    """
    ep_dir = episodes.resolve(name)
    path = ep_dir / "02_text" / "scan.json"
    if not path.exists():
        return {"state": "未実行", "segments": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise episodes.EpisodeError(
            f"scan.json が読めません: {str(exc).splitlines()[0]}"
        ) from exc

    segments = [
        {"start": row.get("start", 0), "end": row.get("end", 0),
         "text": (row.get("text") or "").strip()}
        for row in data.get("segments") or []
    ]
    return {
        "state": "表示",
        "segments": segments,
        "duration": data.get("duration"),
        "source": data.get("source") or "",
    }


def audio_path(name, kind):
    """画面に配る音のパス。

    scan    … 下見をかけた音そのもの（scan.json の source）。行の時刻と合う
    trimmed … 前後のトリムまで済ませたもの。波形とエコー区間の時刻の基準
    clean   … 整音後
    mix     … BGM・SE を重ねた後（#85）。動画化はこの音を使う
    """
    ep_dir = episodes.resolve(name)
    if kind == "clean":
        found = ep_dir / "01_clean" / "clean.wav"
        if not found.exists():
            raise episodes.EpisodeError("整音後の音声がありません")
        return found

    if kind == "mix":
        found = ep_dir / "01_mix" / "mix.wav"
        if not found.exists():
            raise episodes.EpisodeError("まだミックスを実行していません")
        return found

    if kind == "trimmed":
        found = trimmed_path(name)
        if not found.exists():
            raise episodes.EpisodeError("先に整音を1度実行してください")
        return found

    if kind != "scan":
        raise episodes.EpisodeError(f"知らない種類です: {kind}")

    path = ep_dir / "02_text" / "scan.json"
    if path.exists():
        try:
            source = json.loads(path.read_text(encoding="utf-8")).get("source")
        except (json.JSONDecodeError, OSError):
            source = None
        if source:
            # source は 00_raw のファイル名。名前だけを使い、外は指せないようにする
            found = ep_dir / "00_raw" / Path(source).name
            if found.exists():
                return found

    # 下見の前でも音源が聴けるように、いちばん近いものを返す
    raw = ep_dir / "00_raw"
    if raw.is_dir():
        wavs = sorted(raw.glob("*.wav")) + sorted(raw.glob("*.m4a"))
        if wavs:
            return wavs[0]
        videos = [f for f in sorted(raw.iterdir())
                  if f.suffix.lower() in build.VIDEO_EXTS]
        if videos:
            return videos[0]
    raise episodes.EpisodeError("音源がありません")


# ---------------------------------------------------------------- 波形

def trimmed_path(name):
    """波形とエコー区間の基準になる音。前後のトリムまで済ませたもの。"""
    return episodes.resolve(name) / "01_clean" / "trimmed.wav"


def waveform(name):
    """波形に使う音の在りか。形（peaks）はブラウザが wav を読んで描く（#36）。

    エコー区間の時刻と合うよう、音は trimmed.wav を使う。
    """
    path = trimmed_path(name)
    if not path.exists():
        return {"state": "未実行",
                "reason": "先に整音を1度実行すると、波形が出ます"}
    try:
        with wave.open(str(path)) as opened:
            duration = opened.getnframes() / opened.getframerate()
    except (wave.Error, OSError, ZeroDivisionError) as exc:
        raise episodes.EpisodeError(f"trimmed.wav が読めません: {exc}") from exc

    if not duration:
        return {"state": "未実行", "reason": "音が入っていません"}
    return {
        "state": "表示",
        "duration": duration,
        "url": f"/api/episodes/{name}/audio/trimmed",
        # 作り直したら読み直させる（ブラウザが古い音を使い回さないように）
        "at": int(path.stat().st_mtime),
    }


# ---------------------------------------------------------------- タイムライン（見るだけ・#85 の2段目）

def _resolve_raw_source(raw_dir, source):
    """`timeline.yml` の `source` を、`00_raw` の中の実在するファイルにだけ解決する。

    `Path().name` で基底名だけに削り、`00_raw` の外を指せないようにする
    （`web/timeline.py` の `_timeline_sources` / `build.join_sources` と同じ置き場所）。
    **ファイルかどうかまで見る。** `..` は基底名にすると空文字になり、素通しすると
    `00_raw` 自身（フォルダ）を指してしまう。`exists()` だけだとフォルダを
    「見つかった」として通してしまい、後段の `ffprobe` がフォルダを渡されて
    分かりにくい失敗をする（`timeline_source_path` と `_clip_duration` の
    どちらも通る道なので、ここ1か所にまとめる）。
    見つからなければ None（呼び出し側が理由の文言を書く）。
    """
    safe_name = Path(source).name
    found = raw_dir / safe_name if safe_name else None
    if not found or not found.is_file():
        return None
    return found


def timeline_source_path(name, filename):
    """タイムラインのクリップが指す音源を配る。"""
    ep_dir = episodes.resolve(name)
    found = _resolve_raw_source(ep_dir / "00_raw", filename)
    if not found:
        raise episodes.EpisodeError(f"音源がありません: {Path(filename).name or filename}")
    return found


def _clip_duration(raw_dir, clip):
    """生音の長さ。読めなければ (None, 理由) を返す（止めずに、そのクリップにだけ付ける）。"""
    found = _resolve_raw_source(raw_dir, clip["source"])
    if not found:
        name = Path(clip["source"]).name or clip["source"]
        return None, f"音源がありません: {name}"
    try:
        return build.audio_duration(found), None
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return None, f"長さが読めません: {str(exc).splitlines()[0][:80]}"


def timeline_view(name):
    """`timeline.yml` の並びを、見るだけの形にする（部品はまだ無いので #85 の2段目で決める）。

    **編集点（カット）はまだ工程に繋がっていない**（`web/timeline.py` の docstring・#144）。
    そのため、いまは生音の長さをそのまま出来上がりの長さとして扱う。**これは仮置き**。
    カットを工程に当てるようになったら（#85 の6段目）、ここも出来上がりの長さに直す必要がある。

    `web/timeline.py` の `positions()` は長さが読めないと `EpisodeError` で止まる
    （保存前の検証で使う分にはそれでよい）。ここは見るだけの画面なので、
    音源が無い・長さが読めないクリップがあっても止めずに、そのクリップに理由を付けて返す。
    """
    ep_dir = episodes.resolve(name)
    data = timeline.read(ep_dir)
    if not data:
        return {"timeline": None}

    raw_dir = ep_dir / "00_raw"

    def source_url(clip):
        return f"/api/episodes/{name}/timeline-source/{quote(Path(clip['source']).name)}"

    main_out = []
    positions = {}
    at = 0.0
    broken = False   # 前のクリップの長さが分からないと、後ろの位置はもう出せない
    for clip in data["lanes"]["main"]:
        length, error = _clip_duration(raw_dir, clip)
        entry = {
            "id": clip["id"], "source": Path(clip["source"]).name,
            "url": source_url(clip), "gap": clip["gap"],
            "duration": round(length, 3) if length is not None else None,
            "start": None, "error": None,
        }
        if error:
            entry["error"] = error
            broken = True
        elif broken:
            entry["error"] = "前のクリップの長さが分からないため、位置を計算できません"
        else:
            at = round(at + clip["gap"], 3)
            entry["start"] = at
            positions[clip["id"]] = at
            at = round(at + length, 3)
        main_out.append(entry)

    def side_lane(lane):
        out = []
        for clip in data["lanes"][lane]:
            length, error = _clip_duration(raw_dir, clip)
            entry = {
                "id": clip["id"], "source": Path(clip["source"]).name,
                "url": source_url(clip), "anchor": clip["anchor"], "at": clip["at"],
                "duration": round(length, 3) if length is not None else None,
                "start": None, "error": None,
            }
            if error:
                entry["error"] = error
            elif clip["anchor"] not in positions:
                entry["error"] = f"錨（{clip['anchor']}）の位置が分からないため計算できません"
            else:
                entry["start"] = round(positions[clip["anchor"]] + clip["at"], 3)
            out.append(entry)
        return out

    return {
        "timeline": {
            "lanes": {
                "main": main_out,
                "bgm": side_lane("bgm"),
                "se": side_lane("se"),
            },
        },
    }


# ---------------------------------------------------------------- エコーの試聴

def echo_preview(name, start, end, preset):
    """選んだ区間だけを、エコーをかけて短く書き出す。

    前後に余白を付け、そこにはエコーをかけない。本番と同じ聞こえ方にする。
    """
    src = trimmed_path(name)
    if not src.exists():
        raise episodes.EpisodeError("先に整音を1度実行してください")

    total = build.audio_duration(src)
    start = max(0.0, min(float(start), total))
    end = max(0.0, min(float(end), total))
    if end - start < 0.05:
        raise episodes.EpisodeError("区間が短すぎます")

    at = max(0.0, start - PREVIEW_PAD)
    length = min(end + PREVIEW_PAD, total) - at
    dst = src.parent / "preview.wav"

    filters = build.ECHO_PRESETS.get(preset)
    cmd = ["ffmpeg", "-y", "-ss", str(at), "-t", str(length), "-i", str(src)]
    if filters:
        # 切り出しの中での区間の位置に置き直す
        graph = build.echo_graph([(start - at, end - at, preset)], length)
        cmd += ["-filter_complex", graph + ";[echoed]anull[out]", "-map", "[out]"]
    cmd += ["-ar", "48000", "-ac", "1", str(dst)]
    build.run(cmd)
    return dst


# ---------------------------------------------------------------- 整音の結果

def clean_result(name):
    """整音の結果（部品15 整音結果パネル）。"""
    ep_dir = episodes.resolve(name)
    clean = ep_dir / "01_clean" / "clean.wav"
    if not clean.exists():
        return {"state": "未実行"}

    detail = {}
    info = ep_dir / "01_clean" / "clean.json"
    if info.exists():
        try:
            detail = json.loads(info.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            detail = {}

    mark = ep_dir / "01_clean" / "confirmed"
    # やり直したら「確認済み」は外れる（印より clean.wav が新しければ未確認）
    confirmed = mark.exists() and mark.stat().st_mtime >= clean.stat().st_mtime

    stale = _why_stale(ep_dir, clean, detail)
    made = detail.get("echoes")
    bands, bands_error = _clean_bands(detail)
    return {
        "bands": bands,
        "bands_error": bands_error,
        "state": "古い" if stale else "完了",
        "stale_reason": stale,
        "confirmed": confirmed and not stale,
        "duration": detail.get("duration"),
        "removed": detail.get("removed"),
        "target_lufs": detail.get("target_lufs"),
        "echoes": len(made) if isinstance(made, list) else 0,
        # 作り直したら波形を読み直させる（ブラウザが古い音を使い回さないように）
        "at": int(clean.stat().st_mtime),
    }


def _clean_bands(detail):
    """エコーをかけた区間が、clean.wav のどこに来るか（部品15 の波形の帯）。

    clean.json に残っているのは trimmed.wav の時刻。clean.wav は
    エコーの尾で伸び、継ぎ目で縮むので、そのまま重ねると後ろほどずれる。

    返すのは (帯, 出せなかった理由)。エコーをかけたのに出せないときは、
    黙って空にしない（空だと「エコー無し」と見分けが付かない）。
    """
    made = detail.get("echoes")
    if not isinstance(made, list) or not made:
        return [], None                # かけていないので、帯が無いのが正しい

    cannot = ("エコーをかけた所を波形に出せません"
              "（整音をやり直すと出ます）")
    total = detail.get("trimmed_duration")
    if not total:
        return [], cannot              # 古い clean.json には記録が無い
    try:
        regions = [(float(r["start"]), float(r["end"]), r.get("preset"))
                   for r in made]
        return build.echo_positions(regions, float(total)), None
    except (TypeError, ValueError, KeyError, AttributeError):
        return [], cannot              # 記録が壊れている


def _same_echoes(made, now):
    """作ったときのエコー設定と、いまの設定が同じか。"""
    def key(rows):
        return [(round(float(r.get("start", 0)), 2), round(float(r.get("end", 0)), 2),
                 r.get("preset") or "none")
                for r in rows if (r.get("preset") or "none") != "none"]
    try:
        return key(made or []) == key(now or [])
    except (TypeError, AttributeError, ValueError):
        return False          # 形が壊れていたら、作り直したほうが安全


def _why_stale(ep_dir, clean, detail):
    """作り直しが要るなら、その理由を返す。要らなければ None。

    docs/components.md 部品15 の「古い（音源やエコーを変えた）」。
    """
    source = sources_newest(ep_dir)
    if source is not None and source > clean.stat().st_mtime:
        return "音源を差し替えました"

    if not detail:
        return None           # 作ったときの記録が無い。判断できないので何も言わない

    try:
        now = episodes.read_config(ep_dir).get("echoes") or []
    except episodes.EpisodeError:
        return None
    # clean.json には「実際にかけた区間」だけが入る。config.yml には飛ばされた
    # 区間も残るので、比べる前に同じ整え方を通す
    total = detail.get("trimmed_duration") or detail.get("duration") or 0
    try:
        applied = build.normalize_echoes(now, total, report=False)
    except (TypeError, ValueError, AttributeError):
        return None
    wanted = [{"start": s, "end": e, "preset": p} for s, e, p in applied]
    if not _same_echoes(detail.get("echoes"), wanted):
        return "エコー区間を変えました"
    return None


def sources_newest(ep_dir):
    """00_raw の中でいちばん新しい更新日時。音源が無ければ None。"""
    raw = ep_dir / "00_raw"
    if not raw.is_dir():
        return None
    times = [f.stat().st_mtime for f in raw.iterdir() if f.is_file()]
    return max(times) if times else None


def confirm_clean(name):
    ep_dir = episodes.resolve(name)
    if not (ep_dir / "01_clean" / "clean.wav").exists():
        raise episodes.EpisodeError("まだ整音していません")
    (ep_dir / "01_clean" / "confirmed").write_text("", encoding="utf-8")
    return clean_result(name)


# ---------------------------------------------------------------- ミックスの結果

def mix_result(name):
    """ミックス（BGM・SE を重ねる）の結果。見た目は最低限（#85 の4段目）。

    「古い」かどうかは `episodes.step_states` がすでに持っている
    （画面は `stepOf("mix")` を見る）。ここでは事実（長さ・本数）だけを返す。
    """
    ep_dir = episodes.resolve(name)
    mix = ep_dir / "01_mix" / "mix.wav"
    if not mix.exists():
        return {"state": "未実行"}

    detail = {}
    info = ep_dir / "01_mix" / "mix.json"
    if info.exists():
        try:
            detail = json.loads(info.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            detail = {}
    return {
        "state": "表示",
        "duration": detail.get("duration"),
        "bgm": detail.get("bgm", 0),
        "se": detail.get("se", 0),
        "at": int(mix.stat().st_mtime),   # 作り直したら波形/音を読み直させる
    }


# ---------------------------------------------------------------- 確定版の文字起こし

def transcript_path(ep_dir):
    return ep_dir / "02_text" / "transcript.json"


def read_transcript(name):
    """確定版の文字起こし。時刻は clean.wav が基準。

    `original`（元の文字）は #7 から入れている。古いファイルには無いので、
    そのときは今の文字で代用する（＝直していない扱い）。
    """
    ep_dir = episodes.resolve(name)
    path = transcript_path(ep_dir)
    if not path.exists():
        return {"state": "未実行", "segments": [], "changed": 0}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise episodes.EpisodeError(
            f"transcript.json が読めません: {str(exc).splitlines()[0]}"
        ) from exc

    rows = []
    for row in data.get("segments") or []:
        text = (row.get("text") or "").strip()
        original = row.get("original")
        original = text if original is None else original.strip()
        rows.append({"start": row.get("start", 0), "end": row.get("end", 0),
                     "text": text, "original": original,
                     "changed": text != original})
    return {
        "state": "表示",
        "segments": rows,
        "changed": sum(1 for r in rows if r["changed"]),
        "duration": rows[-1]["end"] if rows else 0,
    }


def save_transcript(name, texts):
    """直した文字を書き戻す。行の数と時刻は変えない。"""
    ep_dir = episodes.resolve(name)
    path = transcript_path(ep_dir)
    if not path.exists():
        raise episodes.EpisodeError("まだ文字起こしをしていません")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise episodes.EpisodeError(
            f"transcript.json が読めません: {str(exc).splitlines()[0]}"
        ) from exc

    rows = data.get("segments") or []
    if len(texts) != len(rows):
        raise episodes.EpisodeError(
            f"行の数が合いません（画面 {len(texts)}行 / ファイル {len(rows)}行）。"
            "画面を開き直してください"
        )
    for row, text in zip(rows, texts):
        if "original" not in row:
            row["original"] = row.get("text", "")   # 古いファイルにも元の文字を足す
        row["text"] = (text or "").strip()

    # full_text も作り直す。メタデータの工程はこちらを読まないが、ずれたままにしない
    data["full_text"] = "".join(r.get("text", "") for r in rows)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return read_transcript(name)


# ---------------------------------------------------------------- メタデータ

# Claude がテーマと中身が合わないと判断したときに返す印。
# これが残ったまま動画化まで進んだことがあるので、見つけて止める（Issue #7）。
PENDING = "（保留中）"

TITLE_LIMIT = 60          # YouTube は60文字を超えると途中で切れて表示される


def meta_path(ep_dir):
    return ep_dir / "03_meta" / "meta.json"


def read_meta(name):
    """タイトル・概要欄・章・タグ。"""
    ep_dir = episodes.resolve(name)
    path = meta_path(ep_dir)
    if not path.exists():
        return {"state": "未実行", "title": "", "description": "",
                "chapters": [], "tags": [], "issues": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise episodes.EpisodeError(
            f"meta.json が読めません: {str(exc).splitlines()[0]}"
        ) from exc
    return meta_view(data, segments_of(name))


def segments_of(name):
    """その回のコーナーの並び。読めなければ空（保留チェックは数を見ない）。"""
    try:
        return episodes.read_config(episodes.resolve(name)).get("segments") or []
    except episodes.EpisodeError:
        return []


def meta_view(data, segments=None):
    chapters = []
    for row in data.get("chapters") or []:
        if not isinstance(row, dict):
            continue
        chapters.append({"seconds": row.get("seconds", 0),
                         "label": (row.get("label") or "").strip()})
    chapters.sort(key=lambda c: c["seconds"])
    view = {
        "state": "表示",
        "title": (data.get("title") or "").strip(),
        "description": (data.get("description") or "").rstrip(),
        "chapters": chapters,
        "tags": [t for t in (data.get("tags") or []) if isinstance(t, str)],
    }
    view["issues"] = pending_issues(view, segments)
    return view


def pending_issues(meta, segments=None):
    """動画化に進む前に直してほしいこと（部品17 保留チェック）。

    **章の数はコーナーの数と同じでなければならない**（#106 で案A を選んだ理由・1対1）。
    数を見ないと、案 B・C（Claude に数を任せる）と同じ動きになる。
    `segments` を渡さなければ、数は見ない（今までどおり）。
    """
    issues = []
    title = meta.get("title") or ""
    description = meta.get("description") or ""
    if not title.strip():
        issues.append("タイトルが空です")
    elif PENDING in title:
        issues.append(f"タイトルが{PENDING}のままです")
    if not description.strip():
        issues.append("概要欄が空です")
    elif PENDING in description:
        issues.append(f"概要欄が{PENDING}のままです")
    chapters = meta.get("chapters") or []
    if not chapters:
        issues.append("章がありません。1つ以上必要です")
    else:
        for chapter in chapters:
            if not (chapter.get("label") or "").strip():
                issues.append(f"{build.hhmmss(chapter.get('seconds', 0))} の章に見出しがありません")
                break
        # **コーナーと1対1**（#106 で決めた）。数が合わないのは、作り直しが要る印
        want = len(segments or [])
        if want and len(chapters) != want:
            issues.append(
                f"章が{len(chapters)}件ですが、コーナーは{want}件です。"
                "コーナーと1対1になるよう、メタデータを作り直すか章を直してください")
    return issues


def save_meta(name, title, description, chapters, tags):
    ep_dir = episodes.resolve(name)
    path = meta_path(ep_dir)
    if not path.exists():
        raise episodes.EpisodeError("まだメタデータを作っていません")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise episodes.EpisodeError(
            f"meta.json が読めません: {str(exc).splitlines()[0]}"
        ) from exc

    data["title"] = (title or "").strip()
    data["description"] = (description or "").rstrip()
    data["chapters"] = sorted(
        [{"seconds": round(float(c.get("seconds", 0)), 2),
          "label": (c.get("label") or "").strip()} for c in chapters or []],
        key=lambda c: c["seconds"],
    )
    # 同じタグは1つにまとめる（並びは保つ）
    data["tags"] = list(dict.fromkeys(
        t.strip() for t in (tags or []) if isinstance(t, str) and t.strip()
    ))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta_view(data)


def copy_texts(name, draft=None):
    """YouTube に貼るためのひとそろい。章は概要欄の末尾に付ける。

    draft を渡すと、保存前の直しから作る。画面が「押せる」と判断した中身と、
    実際にコピーされる中身をそろえるため（#47 のレビュー）。
    """
    if draft is None:
        meta = read_meta(name)
        if meta["state"] != "表示":
            raise episodes.EpisodeError("まだメタデータを作っていません")
    else:
        meta = meta_view(draft, segments_of(name))
    description = build.youtube_description(meta)
    return {
        "issues": meta["issues"],
        "title": meta["title"],
        "description": description,
        # 画面が「クレジットが入っているか」を見るのに使う（#137）。
        # 規約の義務なので、落ちていたら気づけるようにする
        "credits": build.credits_in(description),
        "tags": ", ".join(meta["tags"]),
    }


# ---------------------------------------------------------------- 動画

def video_path(ep_dir):
    cfg = episodes.read_config(ep_dir)
    return ep_dir / "04_video" / f"ep{episodes.episode_number(cfg, ep_dir):02d}.mp4"


def duration_of(path):
    """長さ（秒）。読めなければ None。"""
    try:
        return build.audio_duration(path)
    except (ValueError, OSError, subprocess.SubprocessError):
        return None


def video_size(path):
    """幅と高さ。読めなければ空。"""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "csv=p=0:s=x", str(path)],
            capture_output=True, text=True, timeout=20,
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def human_size(count):
    for unit in ["B", "KB", "MB", "GB"]:
        if count < 1024 or unit == "GB":
            return f"{count:.0f} {unit}" if unit == "B" else f"{count:.1f} {unit}"
        count /= 1024
    return f"{count:.1f} GB"


def poster_path(ep_dir):
    """動画の1コマ目。再生前に出す絵（部品19）。"""
    return ep_dir / "04_video" / "poster.jpg"


def make_poster(ep_dir):
    """動画の1コマ目を切り出す。作り直しが要るときだけ動かす。

    返すのは (パス, 作れなかった理由)。作れなくても動画は見られるので、
    工程は止めない。ただし黙って隠さず、理由を画面に返す。
    """
    video = video_path(ep_dir)
    if not video.exists():
        return None, None
    dst = poster_path(ep_dir)
    if dst.exists() and dst.stat().st_mtime >= video.stat().st_mtime:
        return dst, None
    try:
        build.run(["ffmpeg", "-y", "-ss", "0", "-i", str(video),
                   "-frames:v", "1", "-q:v", "3", str(dst)])
    except FileNotFoundError:
        return None, "ffmpeg が見つからないので、再生前の絵を作れません"
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        # ここで投げると、絵が作れないだけで動画パネルごと消えてしまう
        return None, f"再生前の絵を作れません: {exc}"
    if not dst.exists():
        return None, "再生前の絵を作れませんでした（ffmpeg が何も出しませんでした）"
    return dst, None


def video_view(name):
    ep_dir = episodes.resolve(name)
    path = video_path(ep_dir)
    if not path.exists():
        return {"state": "未実行"}
    seconds = duration_of(path)
    # ミックスをやり直したら動画も作り直し（step_video は mix.wav から作る。#85）
    mix = ep_dir / "01_mix" / "mix.wav"
    stale = None
    if mix.exists() and mix.stat().st_mtime > path.stat().st_mtime:
        stale = "ミックスをやり直しました"
    poster, poster_error = make_poster(ep_dir)
    return {
        "state": "古い" if stale else "完了",
        "stale_reason": stale,
        "poster": (f"/api/episodes/{name}/video/poster?t={int(poster.stat().st_mtime)}"
                   if poster else None),
        "poster_error": poster_error,
        "seconds": seconds,
        "name": f"{ep_dir.name}/04_video/{path.name}",
        "duration": build.hhmmss(seconds) if seconds is not None else "",
        "size": human_size(path.stat().st_size),
        "resolution": video_size(path),
        "at": int(path.stat().st_mtime),   # 作り直したら新しい動画を読ませる
    }


def open_folder(name):
    """動画のあるフォルダを Windows のエクスプローラーで開く。

    WSL から Windows 側を開くので、explorer.exe と wslpath に頼る。
    どちらかが無ければ、そう言って断る（静かに失敗させない）。
    """
    ep_dir = episodes.resolve(name)
    folder = ep_dir / "04_video"
    if not folder.is_dir():
        raise episodes.EpisodeError("動画の置き場がまだありません")
    if not shutil.which("explorer.exe") or not shutil.which("wslpath"):
        raise episodes.EpisodeError(
            f"この環境では開けません。場所: {folder}"
        )
    try:
        win = subprocess.run(["wslpath", "-w", str(folder)],
                             capture_output=True, text=True, timeout=10)
        where = win.stdout.strip()
        if win.returncode != 0 or not where:
            # 空のまま渡すと、explorer は黙って既定のフォルダを開いてしまう
            raise episodes.EpisodeError(
                f"フォルダの場所が分かりませんでした: {win.stderr.strip() or folder}")
        # explorer.exe は成功しても 1 を返すことがあるので、返り値は見ない
        subprocess.Popen(["explorer.exe", where])
    except (OSError, subprocess.SubprocessError) as exc:
        raise episodes.EpisodeError(f"フォルダを開けませんでした: {exc}") from exc
    return {"opened": str(folder)}


# ---------------------------------------------------------------- くわしいログ

# 画面に出す分だけ。これより古い行は落とす（ffmpeg は長い行を大量に出す）
LOG_TAIL = 400


def detail_log(name, step):
    """工程ごとの、外部コマンドの出力をぜんぶ残したログ。"""
    if step not in runnable_steps():
        raise episodes.EpisodeError(f"知らない工程です: {step}")
    path = episodes.resolve(name) / "00_logs" / f"{step}.log"
    if not path.exists():
        return {"state": "なし", "lines": []}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        raise episodes.EpisodeError(f"ログが読めません: {exc}") from exc
    return {
        "state": "表示",
        "lines": lines[-LOG_TAIL:],
        "dropped": max(0, len(lines) - LOG_TAIL),
    }


def runnable_steps():
    # 読み込みの輪を避けるため、ここで取り込む
    from web import runner
    return runner.RUNNABLE
