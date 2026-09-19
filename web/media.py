"""文字起こしを読むことと、音声を画面に配ること。"""

import json
import wave
from pathlib import Path

import numpy as np

import build

from web import episodes

# 波形に出す棒の数。見本は細い棒を並べただけなので、これくらいで足りる
WAVE_POINTS = 400

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

    scan  … 下見をかけた音そのもの（scan.json の source）。行の時刻と合う
    clean … 整音後
    """
    ep_dir = episodes.resolve(name)
    if kind == "clean":
        found = ep_dir / "01_clean" / "clean.wav"
        if not found.exists():
            raise episodes.EpisodeError("整音後の音声がありません")
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


def waveform(name, points=WAVE_POINTS):
    """波形の外形。エコー区間の時刻と合うよう、trimmed.wav から作る。"""
    path = trimmed_path(name)
    if not path.exists():
        return {"state": "未実行",
                "reason": "先に整音を1度実行すると、波形が出ます"}
    try:
        with wave.open(str(path)) as opened:
            rate = opened.getframerate()
            frames = opened.getnframes()
            raw = opened.readframes(frames)
    except (wave.Error, OSError) as exc:
        raise episodes.EpisodeError(f"trimmed.wav が読めません: {exc}") from exc

    data = np.frombuffer(raw, dtype=np.int16)
    if not len(data):
        return {"state": "未実行", "reason": "音が入っていません"}

    chunk = max(1, len(data) // points)
    usable = len(data) // chunk * chunk
    peaks = np.abs(data[:usable].reshape(-1, chunk).astype(np.int32)).max(axis=1) / 32768.0
    return {
        "state": "表示",
        "duration": frames / rate,
        "peaks": [round(float(v), 3) for v in peaks],
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
    return {
        "state": "古い" if stale else "完了",
        "stale_reason": stale,
        "confirmed": confirmed and not stale,
        "duration": detail.get("duration"),
        "removed": detail.get("removed"),
        "target_lufs": detail.get("target_lufs"),
        "echoes": len(made) if isinstance(made, list) else 0,
    }


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
