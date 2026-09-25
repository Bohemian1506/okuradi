#!/usr/bin/env python3
"""Claude Code の SessionStart hook: 起動したとき、`/始め` の手順を渡す。

役割: 打ち忘れても始まるようにする。

`/始め` は打たないと効かない。day-4 に、番組側（r-hoso）が立てた Issue を3時間40分
見落とし、コメントで来た返事を3回「まだ来ていない」と書いた。どちらも見に行かなかっただけ。
隣の `session-start-status.py` は**事実を出すだけ**で、突き合わせは人が打ったときにしか起きない。

**起動のときだけ出す。** SessionStart は続きから（resume）・要約（compact）・
クリア（clear）でも走る。絞らないと、作業の真っ最中に「申し送りを読み直します」が始まる。
`source` の実測値は `startup` と `resume`（2026-09-24・#180）。

**ただし、印があれば続きから（resume）でも出す**（#183）。`/作業終了` が
`.claude/state/作業終了` を置く。`start.sh -c` で続きから開いた朝は `source` が `resume` になり、
起動だけ見ていると突き合わせが一度も走らないため。**出したら印を消す**（出しっぱなしにしない）。
要約・クリアでは、印があっても出さない（作業の途中で起きるもの）。

**知らない値が来たら出さない側に倒す。** 出しすぎると、作業の邪魔になる方に倒れるため。

**手順はここに写さない。** 正本は `.claude/commands/始め.md` ひとつ。
写すと2か所になって、片方が古くなる。

隣の状態出しとは、失敗したときの向きが逆。あちらは「gh が死んだら黙る」。
こちらは**外を呼ばないので、黙る理由がない**。だから別のファイルにしてある。
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
MARK = ROOT / ".claude" / "state" / "作業終了"

OPENING = {
    "startup": "このセッションは「起動」です（SessionStart hook）。",
    "resume": "このセッションは、`/作業終了` で終えたあとの「続きから」です（SessionStart hook）。",
}

MESSAGE = """

**最初に `/始め` をやってください。** 手順は `.claude/commands/始め.md` にあります。
読んで、そのとおりに進めてください（ここには写していません。正本はあちらです）。

ただし、**ユーザーが最初のメッセージで別の用事を言っているときは、そちらを優先します。**
そのときは、申し送りと実物の食い違いだけを1〜2行で伝えてから、用事に入ってください。"""


def main():
    raw = sys.stdin.read()
    source = json.loads(raw).get("source")
    marked = MARK.exists()
    if not (source == "startup" or (source == "resume" and marked)):
        return           # 印の無い続きから・要約・クリア、そして知らない値では出さない
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": OPENING[source] + MESSAGE,
    }}, ensure_ascii=False))
    if marked:
        try:
            MARK.unlink(missing_ok=True)   # 促しを出してから消す。消せなくても促しは届いている
        except OSError:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass              # 何があってもセッションは始める
    sys.exit(0)
