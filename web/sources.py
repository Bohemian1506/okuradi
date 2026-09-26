"""音源の追加と、アプリ全体の設定。

収録ファイルは `00_raw/` に **コピー** する。今の `build.py` の作り
（`find_raw` が `00_raw` を見る）のままで済み、あとで元を消しても番組を作り直せる。
OBS の録画から音声を取り出すのは、工程を動かすときに `find_raw` がやる。
"""

import os
import shutil
import time
from datetime import datetime
from pathlib import Path

import yaml

import build

from web import episodes, timeline

# アプリ全体の設定の置き場所。既定はコードの場所（CODE_ROOT）の settings.yml。
# 環境変数 `OKURADI_SETTINGS` があれば、そこに変わる（担当が一時フォルダへ試す
# ため。#221）。「回を置く場所」（OKURADI_EPISODES_DIR）とは別に切り替えられる。
_settings_override = os.environ.get("OKURADI_SETTINGS")
SETTINGS = Path(_settings_override).expanduser().resolve() if _settings_override \
    else episodes.CODE_ROOT / "settings.yml"
# 回を置く場所（build.episodes_root）と同じく、**置き場所のフォルダが無いときは起動の時点で止める。**
# 黙って進むと、設定を保存した瞬間に素の FileNotFoundError で落ちる（#221 のレビュー前に気づいた）
if _settings_override and not SETTINGS.parent.is_dir():
    raise RuntimeError(
        f"OKURADI_SETTINGS の置き場所のフォルダがありません: {SETTINGS.parent}"
        "（先にフォルダを作るか、環境変数を外してください）")

# 受け付ける収録ファイル（見本の「wav / m4a / mkv / mp4 / mov / flv」）
AUDIO_EXTS = [".wav", ".m4a"]
ACCEPTED = AUDIO_EXTS + build.VIDEO_EXTS
ACCEPTED_TEXT = " / ".join(e.lstrip(".") for e in ACCEPTED)

# OBS のフォルダは録画が何本もたまるので、新しいほうから何本かだけ見せる
OBS_LIMIT = 12


# ---------------------------------------------------------------- 設定

def read_settings():
    """アプリ全体の設定。回ごとの config.yml とは別に持つ。"""
    if not SETTINGS.exists():
        return {}
    try:
        return yaml.safe_load(SETTINGS.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError) as exc:
        raise episodes.EpisodeError(f"settings.yml が読めません: {str(exc).splitlines()[0]}")


def save_settings(values):
    current = read_settings()
    current.update(values)
    SETTINGS.write_text(
        yaml.safe_dump(current, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return current


# ---------------------------------------------------------------- OBS のフォルダ

def duration_of(path):
    """長さ（秒）。読めなければ None。"""
    try:
        return build.audio_duration(path)
    except (ValueError, OSError):
        return None


def obs_view():
    """OBS のフォルダの様子。画面の「OBSのフォルダから選ぶ」に出す。"""
    folder = (read_settings().get("obs_dir") or "").strip()
    if not folder:
        return {"dir": "", "state": "未設定", "recordings": []}
    path = Path(folder)
    if not path.is_dir():
        return {"dir": folder, "state": "見つかりません", "recordings": []}

    files = [f for f in path.iterdir()
             if f.is_file() and f.suffix.lower() in ACCEPTED]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    rows = []
    for found in files[:OBS_LIMIT]:
        seconds = duration_of(found)
        rows.append({
            "name": found.name,
            "duration": build.hhmmss(seconds) if seconds else "",
            "recorded_at": datetime.fromtimestamp(found.stat().st_mtime).strftime("%m/%d %H:%M"),
        })
    return {"dir": folder, "state": "ok", "recordings": rows}


# ---------------------------------------------------------------- 収録ファイル

def raw_files(ep_dir):
    raw = ep_dir / "00_raw"
    if not raw.is_dir():
        return []
    return [f for f in sorted(raw.iterdir())
            if f.is_file() and f.suffix.lower() in ACCEPTED]


def source_view(name):
    """いま入っている収録ファイル（部品10 収録ファイルカード）。"""
    ep_dir = episodes.resolve(name)
    files = raw_files(ep_dir)
    if not files:
        return {"state": "空"}

    # find_raw と同じ選び方にそろえる。録画があればそれが元
    videos = [f for f in files if f.suffix.lower() in build.VIDEO_EXTS]
    found = videos[0] if videos else files[0]
    seconds = duration_of(found)
    kind = "OBSの録画" if found.suffix.lower() in build.VIDEO_EXTS else found.suffix.lstrip(".")
    return {
        "state": "使える",
        "name": found.name,
        "duration": build.hhmmss(seconds) if seconds else "長さが読めません",
        "kind": kind,
        "recorded_at": datetime.fromtimestamp(found.stat().st_mtime).strftime("%Y/%m/%d %H:%M"),
        "from_video": found.suffix.lower() in build.VIDEO_EXTS,
    }


def _check_name(filename):
    suffix = Path(filename).suffix.lower()
    if suffix not in ACCEPTED:
        raise episodes.EpisodeError(
            f"この形式には対応していません: {Path(filename).name}"
            f"（{ACCEPTED_TEXT} を置いてください）"
        )
    return suffix


def _clear_raw(ep_dir):
    """いまの音源を片付ける。録画から取り出した wav も一緒に消す。

    収録ファイルが2本あると `find_raw` がどちらを使うか分かりにくくなるので、
    1本だけ置く形にする（README の「収録ファイルを1本置いて」と同じ）。
    """
    raw = ep_dir / "00_raw"
    if not raw.is_dir():
        return
    for found in raw.iterdir():
        if found.is_file():
            found.unlink()


def is_framed(ep_dir):
    """枠の形にする回か。画面とサーバーで、この関数1つに条件をそろえる（#216 のレビュー）。

    - `timeline.yml` がある回は、もう枠の形で書かれているので、そのまま枠として扱う
      （コーナーを1つに減らしても、当たらないクリップの守りが効くように）。
    - 無い回は、コーナーが2つ以上あるときだけ枠にする。1つ（または0）の回は、
      いまの1本の入口のまま（`ep01` のような、`timeline.yml` を持たず `00_raw` に
      直接置く古い回と衝突しないため）。
    """
    if timeline.path(ep_dir).exists():
        return True
    try:
        return len(_frame_ids_of(ep_dir)) >= 2
    except episodes.EpisodeError:
        # config.yml が読めない・無いときは、枠かどうか判断できない。
        # 読めないことは他の画面でも分かるので、ここでは静かに「枠ではない」扱いにする
        return False


def _refuse_if_framed(ep_dir):
    """枠の回では、いまの「1本だけ」の入口を使わせない（#216 のレビュー）。

    これを通すと `_clear_raw` が 00_raw を全部消してしまい、`timeline.yml` は
    消えたファイルを指したまま残る。画面は枠の回でこの入口を出さないが、
    サーバー側でも断る（画面とサーバーがずれても壊れないように）。
    """
    if is_framed(ep_dir):
        raise episodes.EpisodeError(
            "この回はコーナーの枠で音源を入れます。上の枠から入れてください"
        )


def add_from_upload(name, filename, stream):
    """ドロップされた（選ばれた）ファイルを取り込む。"""
    ep_dir = episodes.resolve(name)
    _refuse_if_framed(ep_dir)
    _check_name(filename)
    _clear_raw(ep_dir)
    dst = ep_dir / "00_raw" / Path(filename).name
    with dst.open("wb") as out:
        shutil.copyfileobj(stream, out)
    return source_view(name)


def add_from_obs(name, filename):
    """OBS のフォルダの録画を取り込む。"""
    ep_dir = episodes.resolve(name)
    _refuse_if_framed(ep_dir)
    view = obs_view()
    if view["state"] != "ok":
        raise episodes.EpisodeError("OBS のフォルダが使えません")
    src = Path(view["dir"]) / Path(filename).name   # フォルダの外は指せない
    if not src.is_file() or src.suffix.lower() not in ACCEPTED:
        raise episodes.EpisodeError(f"{filename} が見つかりません")

    _clear_raw(ep_dir)
    dst = ep_dir / "00_raw" / src.name
    shutil.copy2(src, dst)
    return source_view(name)


# ---------------------------------------------------------------- コーナーの枠（#85 の3段目）
#
# 決めたこと（案B・2026-09-26・ユーザーの判断）は Issue #85 のコメント。
# 回の config.yml の segments（コーナーの並び）から枠を先に並べ、各枠に音源を入れる。
# 本編の並びはコーナーの順にする。
#
# **いまの1本だけの入口（source_view / add_from_upload / add_from_obs）は、
# コマンドや segments が空の回のためにそのまま残す**（CLAUDE.md）。


def frame_ids(segments):
    """コーナーの並びから、枠の id を作る。

    同じ series が2回以上あれば、2つめから `series-2` のように番号を足す
    （仮置き。並べ方は Issue #85 の案B）。
    """
    ids = []
    counts = {}
    for segment in segments or []:
        series = str((segment or {}).get("series") or "").strip()
        counts[series] = counts.get(series, 0) + 1
        n = counts[series]
        ids.append(series if n == 1 else f"{series}-{n}")
    return ids


def _frame_ids_of(ep_dir):
    cfg = episodes.read_config(ep_dir)
    return frame_ids(cfg.get("segments") or [])


def _validate_frame_id(ep_dir, frame_id):
    if frame_id not in _frame_ids_of(ep_dir):
        raise episodes.EpisodeError(f"その枠がありません: {frame_id}")


def _resolve_frame_source(raw_dir, source):
    """`timeline.yml` の source を、00_raw の中の実在するファイルにだけ解決する。

    `web/media.py` の `_resolve_raw_source` と同じ考え方（外は指せない）。
    **仮のファイル（`.` で始まる名前）は解決しない**（`_place_raw` の一時ファイルを
    誤って枠の音源として拾わないため。#216 のレビュー）。
    """
    safe_name = Path(source or "").name
    if not safe_name or safe_name.startswith("."):
        return None
    found = raw_dir / safe_name
    if not found.is_file():
        return None
    return found


def _frame_source_info(raw_dir, clip):
    """枠に入っている音源の様子（部品10 収録ファイルカードと同じ形）。

    `edits`（カットの件数）も付ける。差し替える前に「これも消えます」と言うため（#216 のレビュー）。
    """
    edits = len(clip.get("edits") or [])
    found = _resolve_frame_source(raw_dir, clip.get("source"))
    if not found:
        name = Path(clip.get("source") or "").name or clip.get("source")
        return {"state": "エラー", "error": f"音源がありません: {name}", "edits": edits}
    seconds = duration_of(found)
    kind = "OBSの録画" if found.suffix.lower() in build.VIDEO_EXTS else found.suffix.lstrip(".")
    return {
        "state": "使える",
        "name": found.name,
        "duration": build.hhmmss(seconds) if seconds else "長さが読めません",
        "kind": kind,
        "recorded_at": datetime.fromtimestamp(found.stat().st_mtime).strftime("%Y/%m/%d %H:%M"),
        "from_video": found.suffix.lower() in build.VIDEO_EXTS,
        "edits": edits,
    }


def _base_timeline(ep_dir):
    data = timeline.read(ep_dir)
    if data:
        return data
    return {"version": timeline.VERSION, "lanes": {"main": [], "bgm": [], "se": []}}


def _orphan_clips(ep_dir):
    """segments に無い id の、本編のクリップ（コーナーを消した・並べ替えたときに残る）。"""
    ids = _frame_ids_of(ep_dir)
    main = _base_timeline(ep_dir)["lanes"]["main"]
    return [clip for clip in main if clip["id"] not in ids]


def _check_no_orphans(ep_dir):
    """どのコーナーにも当たらないクリップがある間は、枠の出し入れを止める（案A・2026-09-26）。

    黙って `timeline.yml` から落とすと、そのクリップの edits（カット）まで消えてしまうため。
    """
    orphans = _orphan_clips(ep_dir)
    if orphans:
        names = "・".join(c["id"] for c in orphans)
        raise episodes.EpisodeError(
            f"どのコーナーにも当たらないクリップがあります（{names}）。"
            "そのクリップを外すか、コーナーを戻してください"
        )


def frames_view(name):
    """コーナーの枠の一覧（画面2「音源を入れる」欄）。

    枠は config.yml の segments の順。各枠に、timeline.yml の本編に同じ id の
    クリップがあれば、その音源の様子を付ける。

    segments に無い id のクリップが timeline.yml にあっても黙って消さず、
    「どのコーナーにも当たらないクリップ」として別に返す（コーナーを消した・
    並べ替えたときに起こる）。ある間は、枠の出し入れを止める（`_check_no_orphans`）。
    """
    ep_dir = episodes.resolve(name)
    cfg = episodes.read_config(ep_dir)
    segments = cfg.get("segments") or []
    ids = frame_ids(segments)
    raw_dir = ep_dir / "00_raw"

    main = _base_timeline(ep_dir)["lanes"]["main"]
    by_id = {clip["id"]: clip for clip in main}

    frames = []
    for segment, frame_id in zip(segments, ids):
        frame = {"id": frame_id, "label": episodes.segment_label(cfg, segment) or frame_id}
        clip = by_id.get(frame_id)
        if clip:
            frame.update(_frame_source_info(raw_dir, clip))
        else:
            frame["state"] = "空"
        frames.append(frame)

    orphans = []
    for clip in main:
        if clip["id"] not in ids:
            orphan = {"id": clip["id"]}
            orphan.update(_frame_source_info(raw_dir, clip))
            orphans.append(orphan)

    # 画面はこの値だけを見て、枠の形にするかを決める（`is_framed` と1つにそろえる。#216 のレビュー）
    return {"frames": frames, "orphans": orphans, "framed": is_framed(ep_dir)}


def _clear_stem(ep_dir, stem, keep=None):
    """その名前（拡張子より前）の音源を消す。録画から取り出した `<stem>.trackN.wav` も一緒に消す。

    **音源として受け付ける拡張子（`ACCEPTED`）だけを見る。** 拡張子を見ずに消すと、
    たまたま同じ名前の関係ないファイル（`op.txt` など）まで消してしまうため（#216 のレビュー）。
    **仮のファイル（`.` で始まる名前）は対象にしない。** `_place_raw` の一時ファイルを
    誤って拾わないようにする（#216 のレビュー）。
    `keep` を渡すと、そのファイルだけは消さない（置き換えた直後の新しいファイル自身など）。
    """
    raw = ep_dir / "00_raw"
    if not raw.is_dir():
        return
    for found in list(raw.iterdir()):
        if (not found.is_file() or found.name.startswith(".")
                or found.suffix.lower() not in ACCEPTED):
            continue
        if keep is not None and found == keep:
            continue
        found_stem = found.stem
        if found_stem == stem:
            found.unlink()
            continue
        base, sep, tail = found_stem.rpartition(".")
        if sep and base == stem and tail.startswith("track") and found.suffix.lower() == ".wav":
            found.unlink()


def _clear_frame(ep_dir, frame_id, keep=None):
    """その枠に前からある音源だけを消す（他の枠のファイルは残す）。

    枠のファイル名は `<枠のid><拡張子>` に固定している（仮置き）ので、そこから見つける。
    """
    _clear_stem(ep_dir, frame_id, keep=keep)


def _planned_main(ep_dir, frame_id, filename):
    """`timeline.yml` の本編を、いま入っている枠だけ・コーナーの順で書き直した形にして返す。

    **ファイルにはまだ触らない。検証だけする**（2026-09-26・ユーザーの判断）。
    先にファイルを差し替えてしまうと、検証で断られたときに「ファイルは新しいのに
    timeline.yml は古いまま」というずれ方をするため（BGM の錨が外れる枠を消したときなど）。

    filename: 新しく置くファイル名（00_raw の中の名前）。外すときは None。
    **差し替えたら（前からその枠にクリップがあったら）edits（カット）は空にする**
    （案A・2026-09-26・ユーザーの判断。前の録音のカットは、新しい録音には合わないため）。
    gap は残す（並びの間の秒数は音源と関係ないため）。bgm / se の行はそのまま残す。
    """
    ids = _frame_ids_of(ep_dir)
    data = _base_timeline(ep_dir)
    by_id = {clip["id"]: dict(clip) for clip in data["lanes"]["main"]}

    if filename is None:
        by_id.pop(frame_id, None)
    else:
        made = by_id.get(frame_id, {"id": frame_id})
        made["id"] = frame_id
        made["source"] = filename
        made["edits"] = []
        by_id[frame_id] = made

    new_main = [by_id[fid] for fid in ids if fid in by_id]
    new_data = {
        "version": timeline.VERSION,
        "lanes": {
            "main": new_main,
            "bgm": data["lanes"].get("bgm", []),
            "se": data["lanes"].get("se", []),
        },
    }
    return timeline.validate(new_data)


def _place_raw(ep_dir, frame_id, dst_name, write):
    """枠のファイルを、前のファイルを消す前に書き終えてから確定名にする（#216 のレビュー）。

    先に前のファイルを消してから書き込むと、書き込みが途中で切れたときに
    **前の音源が空ファイルで残ってしまう**（差し替えなのに音が消える）。
    一時名に書き終えてから確定名に rename し、拡張子が変わった前のファイルや
    `trackN.wav` の片付けは、そのあとにする。

    - `rename`（`Path.replace`）は同じ名前を上書きできるので、**同じ名前に置き換える
      ときは前を先に消す必要が無い**。rename が失敗したら、前のファイルは触らないまま
      一時ファイルだけ片付けて `EpisodeError` にする（拡張子が変わる差し替えでも、
      前のファイルは rename が成功するまで残っている）。
    - 前回の書き込みが残した仮のファイル（`.tmp-<枠のid>-*`）は、
      始める前に片付ける。残ったままだと `find_raw` が「音源が2本あります」と
      誤って断ってしまう（#216 のレビュー）。

    write(tmp_path) が実際の書き込み（コピー）をする。途中で失敗したら、
    一時ファイルを消し、前のファイルはそのまま残して `EpisodeError` にする。
    """
    raw = ep_dir / "00_raw"
    raw.mkdir(parents=True, exist_ok=True)
    for stale in raw.glob(f".tmp-{frame_id}-*"):
        stale.unlink(missing_ok=True)

    tmp = raw / f".tmp-{frame_id}-{dst_name}"
    try:
        write(tmp)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        if isinstance(exc, episodes.EpisodeError):
            raise
        raise episodes.EpisodeError(f"音源を置けませんでした: {exc}") from exc

    dst = raw / dst_name
    try:
        tmp.replace(dst)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise episodes.EpisodeError(f"音源を置けませんでした: {exc}") from exc

    # 拡張子が変わった前のファイルや track の wav は、置き換えたあとに片付ける。
    # 新しく置いたファイル自身（dst）は消さない
    try:
        _clear_frame(ep_dir, frame_id, keep=dst)
    except OSError as exc:
        raise episodes.EpisodeError(
            f"音源は置き換わりましたが、前のファイルを片付けられませんでした: {exc}"
        ) from exc


def _write_stream(tmp, stream):
    with tmp.open("wb") as out:
        shutil.copyfileobj(stream, out)


def add_frame_from_upload(name, frame_id, filename, stream):
    """枠にドロップ（選んだ）ファイルを入れる。"""
    ep_dir = episodes.resolve(name)
    _validate_frame_id(ep_dir, frame_id)
    _check_no_orphans(ep_dir)
    suffix = _check_name(filename)
    dst_name = f"{frame_id}{suffix}"
    planned = _planned_main(ep_dir, frame_id, dst_name)   # ファイルに触る前に検証する

    _place_raw(ep_dir, frame_id, dst_name, lambda tmp: _write_stream(tmp, stream))
    timeline.save(ep_dir, planned)
    return frames_view(name)


def add_frame_from_obs(name, frame_id, filename):
    """枠に OBS のフォルダの録画を入れる。"""
    ep_dir = episodes.resolve(name)
    _validate_frame_id(ep_dir, frame_id)
    _check_no_orphans(ep_dir)
    view = obs_view()
    if view["state"] != "ok":
        raise episodes.EpisodeError("OBS のフォルダが使えません")
    src = Path(view["dir"]) / Path(filename).name   # フォルダの外は指せない
    if not src.is_file() or src.suffix.lower() not in ACCEPTED:
        raise episodes.EpisodeError(f"{filename} が見つかりません")

    dst_name = f"{frame_id}{src.suffix.lower()}"
    planned = _planned_main(ep_dir, frame_id, dst_name)   # ファイルに触る前に検証する

    _place_raw(ep_dir, frame_id, dst_name, lambda tmp: shutil.copy2(src, tmp))
    timeline.save(ep_dir, planned)
    return frames_view(name)


def remove_frame(name, frame_id):
    """枠から音源を外す。ファイルも消す。"""
    ep_dir = episodes.resolve(name)
    _validate_frame_id(ep_dir, frame_id)
    _check_no_orphans(ep_dir)
    planned = _planned_main(ep_dir, frame_id, None)   # ファイルに触る前に検証する

    _clear_frame(ep_dir, frame_id)
    timeline.save(ep_dir, planned)
    return frames_view(name)


def remove_orphan(name, orphan_id):
    """どのコーナーにも当たらないクリップを外す。ファイルも消す（消す前に画面で確かめる）。"""
    ep_dir = episodes.resolve(name)
    orphans = {clip["id"]: clip for clip in _orphan_clips(ep_dir)}
    if orphan_id not in orphans:
        raise episodes.EpisodeError(f"その、どのコーナーにも当たらないクリップがありません: {orphan_id}")
    clip = orphans[orphan_id]

    data = _base_timeline(ep_dir)
    new_main = [c for c in data["lanes"]["main"] if c["id"] != orphan_id]
    new_data = {
        "version": timeline.VERSION,
        "lanes": {
            "main": new_main,
            "bgm": data["lanes"].get("bgm", []),
            "se": data["lanes"].get("se", []),
        },
    }
    planned = timeline.validate(new_data)   # ファイルに触る前に検証する

    _clear_stem(ep_dir, Path(clip["source"]).stem)
    timeline.save(ep_dir, planned)
    return frames_view(name)
