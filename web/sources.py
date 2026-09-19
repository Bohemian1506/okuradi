"""音源の追加と、アプリ全体の設定。

収録ファイルは `00_raw/` に **コピー** する。今の `build.py` の作り
（`find_raw` が `00_raw` を見る）のままで済み、あとで元を消しても番組を作り直せる。
OBS の録画から音声を取り出すのは、工程を動かすときに `find_raw` がやる。
"""

import shutil
import time
from datetime import datetime
from pathlib import Path

import yaml

import build

from web import episodes

ROOT = episodes.ROOT
SETTINGS = ROOT / "settings.yml"

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


def add_from_upload(name, filename, stream):
    """ドロップされた（選ばれた）ファイルを取り込む。"""
    ep_dir = episodes.resolve(name)
    _check_name(filename)
    _clear_raw(ep_dir)
    dst = ep_dir / "00_raw" / Path(filename).name
    with dst.open("wb") as out:
        shutil.copyfileobj(stream, out)
    return source_view(name)


def add_from_obs(name, filename):
    """OBS のフォルダの録画を取り込む。"""
    ep_dir = episodes.resolve(name)
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
