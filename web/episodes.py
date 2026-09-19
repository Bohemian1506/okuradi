"""回の一覧・作成と、工程の状態。

build.py の関数をそのまま使う皮。処理の実体は build.py 側にある。
"""

import copy
import shutil
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
    # build.py の step_video は clean.wav と config.yml の images しか読まない。
    # meta.json は使わないので、タイトルを直しても動画は作り直しにならない。
    "video": ["clean"],
}

# build.py の cut 工程は GUI では使わない（docs/components.md）。
# コマンドで cut をやり直しても、GUI の整音は「完了」のままになる。

AUDIO_EXTS = [".wav", ".m4a"]


class EpisodeError(Exception):
    """画面にそのまま出す前提のエラー。"""


# ---------------------------------------------------------------- 読み書き

def config_path(ep_dir):
    return ep_dir / "config.yml"


def read_config(ep_dir):
    try:
        return yaml.safe_load(config_path(ep_dir).read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
        # YAML のエラーは何行にもなるので、画面に出す分は1行に切り詰める
        reason = str(exc).splitlines()[0][:80]
        raise EpisodeError(f"{ep_dir.name}/config.yml が読めません: {reason}") from exc


def episode_dirs(root=ROOT):
    return sorted(d for d in root.iterdir()
                  if d.is_dir() and config_path(d).exists())


def dir_number(ep_dir):
    """ディレクトリ名から回の番号を取る（ep03 → 3）。config.yml が読めなくても使える。"""
    digits = "".join(c for c in ep_dir.name if c.isdigit())
    return int(digits) if digits else 0


def resolve(name, root=ROOT):
    """回の名前を、root の直下に実在する回だけに限る。

    `..` のような名前で回の外を読み書きされないようにする。
    """
    for ep_dir in episode_dirs(root):
        if ep_dir.name == name:
            return ep_dir
    raise EpisodeError(f"{name} がありません")


def number_of(ep_dir):
    """回の番号。config.yml が読めなければディレクトリ名から取る。"""
    try:
        return episode_number(read_config(ep_dir), ep_dir)
    except EpisodeError:
        return dir_number(ep_dir)


def episode_number(cfg, ep_dir):
    """config.yml の episode。無ければディレクトリ名（ep03 → 3）から拾う。"""
    n = cfg.get("episode")
    return n if isinstance(n, int) else dir_number(ep_dir)


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


def broken_summary(ep_dir, message):
    """config.yml が読めない回。一覧から消さずに、読めないことを出す。"""
    return {
        "name": ep_dir.name,
        "episode": dir_number(ep_dir),
        "theme": "（設定が読めません）",
        "steps": [],
        "done": 0,
        "total": len(STEPS),
        "error": message,
    }


def list_episodes(root=ROOT):
    """1つの回が壊れていても、他の回は出す。"""
    rows = []
    for ep_dir in episode_dirs(root):
        try:
            rows.append(summary(ep_dir, read_config(ep_dir)))
        except EpisodeError as exc:
            rows.append(broken_summary(ep_dir, str(exc)))
    return rows


def rule_view(key, rule):
    """コーナー1つ分を、画面に出す形にする。"""
    rule = rule or {}
    # title_hint は「「今更聞けない○○」の形。○○は…」のように2文で書かれている。
    # テーマ欄のヒントには、型を示す最初の文だけを使う。
    hint = (rule.get("title_hint") or "").split("。")[0]
    return {"label": rule.get("label") or key, "hint": hint}


def rules_of(ep_dir):
    """その回の config.yml の series_rules を、画面に出す形にして返す。"""
    rules = read_config(ep_dir).get("series_rules") or {}
    return {key: rule_view(key, rule) for key, rule in rules.items()}


def series_rules(root=ROOT):
    """画面に出すコーナーの選択肢。新しい回から順に見て、最初に見つかったものを使う。"""
    for ep_dir in sorted(episode_dirs(root), key=dir_number, reverse=True):
        try:
            rules = rules_of(ep_dir)
        except EpisodeError:
            continue
        if rules:
            return rules
    return {}


def detail(name, root=ROOT):
    ep_dir = resolve(name, root)
    cfg = read_config(ep_dir)
    data = summary(ep_dir, cfg)
    # segments は、表情差分や BGM など将来のキーも含めてそのまま渡す。
    # 画面はこれを持ち回り、保存のときに返してくるので、知らないキーが消えない。
    data["segments"] = copy.deepcopy(cfg.get("segments") or [])
    return data


def next_number(root=ROOT):
    dirs = episode_dirs(root)
    if not dirs:
        return 1
    return max(number_of(d) for d in dirs) + 1


# ---------------------------------------------------------------- 作成・保存

def template_config(number, root=ROOT):
    """ひな型にする config.yml。直前の回（その番号より小さい中でいちばん大きい回）から写す。"""
    dirs = episode_dirs(root)
    if not dirs:
        raise EpisodeError(
            "ひな型にする回がありません。最初の回は手で作ってください（ep01 のように）"
        )
    numbered = sorted((number_of(d), d.name, d) for d in dirs)
    before = [d for n, _, d in numbered if n < number]
    source = before[-1] if before else numbered[0][2]
    return read_config(source)


def validate_segments(segments, known):
    """コーナーの並びを確かめる。known はその回の series_rules。

    知らないキー（将来の表情差分・BGM など）は、そのまま残す。
    """
    if not segments:
        raise EpisodeError("コーナーを1つ以上入れてください")
    cleaned = []
    for segment in segments:
        if not isinstance(segment, dict):
            raise EpisodeError("コーナーの形が違います")
        series = (segment.get("series") or "").strip()
        theme = (segment.get("theme") or "").strip()
        if not series:
            raise EpisodeError("コーナーを選んでください")
        if known and series not in known:
            raise EpisodeError(f"知らないコーナーです: {series}")
        if not theme:
            raise EpisodeError("テーマを入れてください")
        row = dict(segment)
        row["series"] = series
        row["theme"] = theme
        cleaned.append(row)
    return cleaned


def create_episode(number, segments, root=ROOT):
    if not isinstance(number, int) or number < 1:
        raise EpisodeError("回の番号は1以上の数字にしてください")
    name = f"ep{number:02d}"
    ep_dir = root / name
    if ep_dir.exists():
        raise EpisodeError(f"同じ番号の回がすでにあります（{name}）")

    # ひな型を先に読む。コーナーの検証も、ひな型にする回の series_rules で行う。
    cfg = copy.deepcopy(template_config(number, root))
    known = {key: rule_view(key, rule)
             for key, rule in (cfg.get("series_rules") or {}).items()}
    cfg["episode"] = number
    cfg["recorded_on"] = None
    cfg["segments"] = validate_segments(segments, known)
    cfg["cuts"] = []

    ep_dir.mkdir(parents=True)
    try:
        build.save_config({"dir": ep_dir}, cfg)
        build.load_episode(root, name)  # 中間ファイルの置き場を作る
    except Exception:
        # 途中で失敗したら、中途半端なフォルダを残さない（同じ番号で作り直せなくなるため）
        shutil.rmtree(ep_dir, ignore_errors=True)
        raise
    return detail(name, root)


def save_segments(name, segments, root=ROOT):
    ep_dir = resolve(name, root)
    cfg = read_config(ep_dir)
    # 検証は、その回自身の series_rules で行う（新しい回で足したコーナーに引きずられない）
    cfg["segments"] = validate_segments(segments, rules_of(ep_dir))
    build.save_config({"dir": ep_dir}, cfg)
    return detail(name, root)
