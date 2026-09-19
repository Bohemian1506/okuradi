"""回の一覧・作成と、工程の状態。

build.py の関数をそのまま使う皮。処理の実体は build.py 側にある。
"""

import copy
from pathlib import Path

import yaml

import build

ROOT = Path(build.__file__).parent.resolve()

# GUI で見せる6工程。build.py の cut と upload は GUI では使わない（docs/components.md）
STEPS = [
    {"key": "source", "label": "音源"},
    {"key": "scan", "label": "下見"},
    {"key": "clean", "label": "整音"},
    {"key": "transcribe", "label": "文字起こし"},
    {"key": "meta", "label": "メタデータ"},
    {"key": "video", "label": "動画"},
]

# 工程が何から作られるか。作り直しが要る（＝「古い」）の判定に使う。
DEPS = {
    "source": [],
    "scan": ["source"],
    "clean": ["source"],
    "transcribe": ["clean"],
    "meta": ["transcribe"],
    "video": ["clean", "meta"],
}

AUDIO_EXTS = [".wav", ".m4a"]


class EpisodeError(Exception):
    """画面にそのまま出す前提のエラー。"""


# ---------------------------------------------------------------- 読み書き

def config_path(ep_dir):
    return ep_dir / "config.yml"


def read_config(ep_dir):
    return yaml.safe_load(config_path(ep_dir).read_text(encoding="utf-8")) or {}


def episode_dirs(root=ROOT):
    return sorted(d for d in root.iterdir()
                  if d.is_dir() and config_path(d).exists())


def episode_number(cfg, ep_dir):
    """config.yml の episode。無ければディレクトリ名（ep03 → 3）から拾う。"""
    n = cfg.get("episode")
    if isinstance(n, int):
        return n
    digits = "".join(c for c in ep_dir.name if c.isdigit())
    return int(digits) if digits else 0


# ---------------------------------------------------------------- 工程の状態

def artifact(ep_dir, key, cfg):
    """その工程の成果物のパスを返す。無ければ None。

    音源だけは名前が決まっていないので、00_raw の中でいちばん新しいものを見る。
    find_raw() は録画から音声を取り出す（ffmpeg を走らせる）ので、一覧の表示には使わない。
    """
    if key == "source":
        raw = ep_dir / "00_raw"
        if not raw.is_dir():
            return None
        files = [f for f in raw.iterdir() if f.is_file()
                 and f.suffix.lower() in build.VIDEO_EXTS + AUDIO_EXTS]
        return max(files, key=lambda f: f.stat().st_mtime) if files else None

    paths = {
        "scan": ep_dir / "02_text" / "scan.json",
        "clean": ep_dir / "01_clean" / "clean.wav",
        "transcribe": ep_dir / "02_text" / "transcript.json",
        "meta": ep_dir / "03_meta" / "meta.json",
        "video": ep_dir / "04_video" / f"ep{episode_number(cfg, ep_dir):02d}.mp4",
    }
    path = paths[key]
    return path if path.exists() else None


def step_states(ep_dir, cfg):
    """6工程の状態を返す。

    未実行 / 実行できる / 完了 / 古い の4つ。
    処理中・エラー・中止は工程を実行したときに決まるので、ここでは出ない（#8）。
    """
    mtimes = {}
    for step in STEPS:
        found = artifact(ep_dir, step["key"], cfg)
        mtimes[step["key"]] = found.stat().st_mtime if found else None

    states = []
    for step in STEPS:
        key = step["key"]
        mine = mtimes[key]
        deps = DEPS[key]
        if mine is None:
            ready = bool(deps) and all(mtimes[d] is not None for d in deps)
            state = "実行できる" if ready else "未実行"
        else:
            stale = any(mtimes[d] is not None and mtimes[d] > mine for d in deps)
            state = "古い" if stale else "完了"
        states.append({"key": key, "label": step["label"], "state": state})
    return states


# ---------------------------------------------------------------- 一覧

def segment_label(cfg, segment):
    """「今更聞けない OSI参照モデルの7層」の形にする。"""
    rules = cfg.get("series_rules") or {}
    label = (rules.get(segment.get("series")) or {}).get("label") or segment.get("series") or ""
    theme = segment.get("theme") or ""
    return " ".join(x for x in [label, theme] if x)


def summary(ep_dir, cfg):
    states = step_states(ep_dir, cfg)
    segments = cfg.get("segments") or []
    return {
        "name": ep_dir.name,
        "episode": episode_number(cfg, ep_dir),
        "theme": "／".join(segment_label(cfg, s) for s in segments) or "（テーマ未設定）",
        "steps": states,
        "done": sum(1 for s in states if s["state"] == "完了"),
        "total": len(states),
    }


def list_episodes(root=ROOT):
    return [summary(d, read_config(d)) for d in episode_dirs(root)]


def series_rules(root=ROOT):
    """コーナーの一覧。いちばん新しい回の config.yml から取る。"""
    dirs = episode_dirs(root)
    if not dirs:
        return {}
    latest = max(dirs, key=lambda d: episode_number(read_config(d), d))
    rules = read_config(latest).get("series_rules") or {}
    return {key: (rule or {}).get("label") or key for key, rule in rules.items()}


def detail(name, root=ROOT):
    ep_dir = root / name
    if not config_path(ep_dir).exists():
        raise EpisodeError(f"{name} がありません")
    cfg = read_config(ep_dir)
    data = summary(ep_dir, cfg)
    data["segments"] = [{"series": s.get("series"), "theme": s.get("theme") or ""}
                        for s in (cfg.get("segments") or [])]
    return data


def next_number(root=ROOT):
    dirs = episode_dirs(root)
    if not dirs:
        return 1
    return max(episode_number(read_config(d), d) for d in dirs) + 1


# ---------------------------------------------------------------- 作成・保存

def template_config(number, root=ROOT):
    """ひな型にする config.yml。直前の回（その番号より小さい中でいちばん大きい回）から写す。"""
    dirs = episode_dirs(root)
    if not dirs:
        raise EpisodeError(
            "ひな型にする回がありません。最初の回は手で作ってください（ep01 のように）"
        )
    numbered = [(episode_number(read_config(d), d), d) for d in dirs]
    before = [d for n, d in numbered if n < number]
    source = before[-1] if before else min(numbered)[1]
    return read_config(source)


def validate_segments(segments, root=ROOT):
    if not segments:
        raise EpisodeError("コーナーを1つ以上入れてください")
    known = series_rules(root)
    cleaned = []
    for segment in segments:
        series = (segment.get("series") or "").strip()
        theme = (segment.get("theme") or "").strip()
        if not series:
            raise EpisodeError("コーナーを選んでください")
        if known and series not in known:
            raise EpisodeError(f"知らないコーナーです: {series}")
        if not theme:
            raise EpisodeError("テーマを入れてください")
        cleaned.append({"series": series, "theme": theme})
    return cleaned


def create_episode(number, segments, root=ROOT):
    if not isinstance(number, int) or number < 1:
        raise EpisodeError("回の番号は1以上の数字にしてください")
    name = f"ep{number:02d}"
    ep_dir = root / name
    if ep_dir.exists():
        raise EpisodeError(f"同じ番号の回がすでにあります（{name}）")

    cleaned = validate_segments(segments, root)
    cfg = copy.deepcopy(template_config(number, root))
    cfg["episode"] = number
    cfg["recorded_on"] = None
    cfg["segments"] = cleaned
    cfg["cuts"] = []

    ep_dir.mkdir(parents=True)
    build.save_config({"dir": ep_dir}, cfg)
    build.load_episode(root, name)  # 中間ファイルの置き場を作る
    return detail(name, root)


def save_segments(name, segments, root=ROOT):
    ep_dir = root / name
    if not config_path(ep_dir).exists():
        raise EpisodeError(f"{name} がありません")
    cfg = read_config(ep_dir)
    cfg["segments"] = validate_segments(segments, root)
    build.save_config({"dir": ep_dir}, cfg)
    return detail(name, root)
