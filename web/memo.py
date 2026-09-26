"""相談チャットの会話から、改善メモを作って GitHub の Issue に登録する。

下書きは Claude に作らせ、**画面で確認・編集してから**登録する
（外に出すものなので、黙って送らない）。
"""

import json
import shutil
import subprocess

import build

from web import chat, episodes

LABEL = "改善メモ"

SUMMARY = """\
次は、ラジオ番組「置くラジ」を作っている本人と、相談相手の会話です。
この会話から「次の収録で直すこと」を1つ、改善メモとしてまとめてください。

# 会話
{conversation}

# 出力の条件
- title: 何を直すかが分かる短い一文。30文字以内。日本語
- body: なぜそうするかと、次にやることの箇条書き。5行以内。日本語
- 会話に出ていないことは書かない
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "body": {"type": "string"},
    },
    "required": ["title", "body"],
}


def draft(name):
    """会話を要約して、Issue の下書きを作る。"""
    talk = chat.read_chat(name)
    if not talk["messages"]:
        raise episodes.EpisodeError("まだ会話がありません。先に相談してください")

    conversation = "\n\n".join(f"{m['who']}: {m['text']}" for m in talk["messages"])
    try:
        result = build.call_claude(
            SUMMARY.format(conversation=conversation), schema=SCHEMA)
    except RuntimeError as exc:
        raise episodes.EpisodeError(f"下書きを作れませんでした: {exc}") from exc

    got = result.get("structured_output") or {}
    return {
        "title": (got.get("title") or "").strip(),
        "body": (got.get("body") or "").strip(),
        "label": LABEL,
    }


def has_label():
    """ラベルがあるか。無いまま登録すると gh が失敗する。"""
    # --limit の既定は30件。ラベルが増えたときに取りこぼさないようにする。
    # cwd も create() とそろえる（別のリポジトリを見てしまわないように）。
    # gh はリポジトリの中で打つ必要があるので、コードの場所（CODE_ROOT）を使う。
    # 「回を置く場所」（episodes.ROOT）とは別（#221）
    out = subprocess.run(
        ["gh", "label", "list", "--json", "name", "--limit", "200"],
        capture_output=True, text=True, timeout=30, cwd=str(episodes.CODE_ROOT))
    if out.returncode != 0:
        return False
    try:
        return any(row.get("name") == LABEL for row in json.loads(out.stdout))
    except json.JSONDecodeError:
        return False


def create(name, title, body):
    """Issue に登録する。画面で確認したあとにだけ呼ぶ。"""
    title = (title or "").strip()
    body = (body or "").rstrip()
    if not title:
        raise episodes.EpisodeError("タイトルを入れてください")
    if not shutil.which("gh"):
        raise episodes.EpisodeError(
            "gh コマンドがありません。GitHub CLI を入れてください")
    if not has_label():
        raise episodes.EpisodeError(
            f"ラベル「{LABEL}」がありません。"
            f"`gh label create {LABEL}` で作ってから、もう一度お試しください")

    ep_dir = episodes.resolve(name)
    full = f"{body}\n\n---\n{ep_dir.name} の相談から。"
    try:
        out = subprocess.run(
            ["gh", "issue", "create", "--title", title, "--body", full,
             "--label", LABEL],
            capture_output=True, text=True, timeout=60, cwd=str(episodes.CODE_ROOT),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise episodes.EpisodeError(f"登録できませんでした: {exc}") from exc
    if out.returncode != 0:
        raise episodes.EpisodeError(
            f"登録できませんでした: {(out.stderr or out.stdout).strip()}")

    url = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    return {"url": url}
