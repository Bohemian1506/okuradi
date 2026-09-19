"""文字起こしを読むことと、音声を画面に配ること。"""

import json
from pathlib import Path

import build

from web import episodes


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
