"""この回について Claude に相談するチャット。

`build.call_claude` をそのまま使う（サブスクの枠で動く `claude -p`）。
会話は `--resume` で続ける。1回目に文字起こしを渡し、2回目からは
セッションが覚えているので送り直さない。
"""

import json

import build

from web import episodes

# 会話の記録。回ごとに 00_logs/chat.json へ残す（画面を開き直しても消えない）
CHAT_FILE = "chat.json"

SYSTEM = """\
あなたはラジオ番組「置くラジ」の相談相手です。収録した本人からの質問に答えます。

# 答え方
- 日本語で、短く。専門用語は避ける
- 文字起こしの中を指すときは 02:14 のように時刻を書く
- 文字起こしに無いことは推測せず、分からないと言う
"""

FIRST = """\
これから、この回について相談します。まず材料を渡します。

# 番組について
{concept}

# この回のコーナー
{segments}

# 文字起こし（{kind}）
{transcript}

---
最初の質問です。

{question}
"""


def chat_path(ep_dir):
    return ep_dir / "00_logs" / CHAT_FILE


def read_chat(name):
    """いまの会話。画面を開き直しても続きから見える。"""
    ep_dir = episodes.resolve(name)
    path = chat_path(ep_dir)
    reading, _ = pick_transcript(ep_dir)
    if not path.exists():
        return {"reading": reading, "messages": [], "session": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"reading": reading, "messages": [], "session": None}
    return {
        "reading": reading,
        "messages": data.get("messages") or [],
        "session": data.get("session"),
    }


def save_chat(ep_dir, data):
    path = chat_path(ep_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def pick_transcript(ep_dir):
    """どの文字起こしを読ませるか。確定版があればそちら、無ければ下見。"""
    final = ep_dir / "02_text" / "transcript.json"
    scan = ep_dir / "02_text" / "scan.json"
    for label, path in [("確定版", final), ("下見", scan)]:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            rows = data.get("segments") or []
            if rows:
                return label, rows
    return "文字起こしなし", []


def segment_lines(cfg):
    rules = cfg.get("series_rules") or {}
    lines = []
    for segment in cfg.get("segments") or []:
        rule = rules.get(segment.get("series")) or {}
        lines.append(f"- 枠: {rule.get('label', segment.get('series'))}"
                     f" / テーマ: {segment.get('theme')}")
    return "\n".join(lines) or "（未設定）"


def ask(name, question):
    """質問を送って、答えを返す。"""
    question = (question or "").strip()
    if not question:
        raise episodes.EpisodeError("聞きたいことを書いてください")

    ep_dir = episodes.resolve(name)
    chat = read_chat(name)
    session = chat["session"]

    try:
        if session:
            # 2回目から。セッションが材料を覚えている
            result = build.call_claude(question, system=SYSTEM, resume=session)
        else:
            cfg = episodes.read_config(ep_dir)
            kind, rows = pick_transcript(ep_dir)
            body = "\n".join(f"[{build.hhmmss(r.get('start', 0))}] {r.get('text', '')}"
                             for r in rows) or "（まだ文字起こしがありません）"
            prompt = FIRST.format(
                concept=(cfg.get("concept") or "").strip() or "（未設定）",
                segments=segment_lines(cfg),
                kind=kind, transcript=body, question=question,
            )
            result = build.call_claude(prompt, system=SYSTEM, persist=True)
    except RuntimeError as exc:
        # claude が見つからない・失敗した。静かに失敗させない
        raise episodes.EpisodeError(f"Claude に聞けませんでした: {exc}") from exc

    answer = (result.get("result") or "").strip()
    messages = chat["messages"] + [
        {"who": "あなた", "text": question},
        {"who": "Claude", "text": answer},
    ]
    save_chat(ep_dir, {"session": result.get("session_id") or session,
                       "messages": messages})
    return read_chat(name)


def reset(name):
    """会話を最初からにする。次の質問で材料を渡し直す。"""
    ep_dir = episodes.resolve(name)
    path = chat_path(ep_dir)
    if path.exists():
        path.unlink()
    return read_chat(name)
