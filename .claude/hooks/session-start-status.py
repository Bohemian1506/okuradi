#!/usr/bin/env python3
"""Claude Code の SessionStart hook: 始まるときに、いまの事実を出す。

役割: 申し送り（docs/handoff.md）を読む前に、GitHub と手元の実物を見せる。

day-4 に、番組側（r-hoso）が立てた Issue を3時間40分見落とし、
コメントで来た返事を3回「まだ来ていない」と書いた。どちらも見に行かなかっただけ。
申し送りは Claude が書くものなので、間違っていても気づけない。ここでは実物を出す。

**うるさくしない。** 全部並べると埋もれるので、気づきたいものだけに絞る。
- ラベルの無い Issue（番組側が立てたものはラベルが無い）と v1 は名前を出す
- そのほかは件数だけ
- 最近動いたものは上位5件。時刻は手元の時刻に直す（UTC のままだと9時間ずれる）

失敗しても静かに終わる。ネットが切れていてもセッションは始まる。
**gh が1回でも固まったら、残りの gh 呼び出しはやめる**（待ち時間を積み上げない）。
"""

import datetime
import json
import subprocess
import sys

TIMEOUT = 5          # 1回あたり。セッションの開始を待たせない
_gh_alive = True     # gh が固まったら、以降の gh 呼び出しはやめる


def run(args):
    """外のコマンドを呼ぶ。失敗したら None（セッションは止めない）。"""
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout if p.returncode == 0 else None


def gh_json(args):
    global _gh_alive
    if not _gh_alive:
        return None
    try:
        p = subprocess.run(["gh"] + args, capture_output=True, text=True,
                           timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        _gh_alive = False     # 1回固まったら、残りも固まる。待たない
        return None
    except OSError:
        _gh_alive = False     # gh が入っていない
        return None
    out = p.stdout if p.returncode == 0 else None
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def issues_section(lines):
    rows = gh_json(["issue", "list", "--limit", "50",
                    "--json", "number,title,labels"])
    if rows is None:
        return
    lines.append(f"開いている Issue: {len(rows)}件")

    tally = {}
    for r in rows:
        for name in [x["name"] for x in r["labels"]] or ["ラベル無し"]:
            tally[name] = tally.get(name, 0) + 1
    if tally:
        order = sorted(tally.items(), key=lambda kv: -kv[1])
        lines.append("  内訳: " + " / ".join(f"{k} {v}" for k, v in order))

    # 名前まで出すのは「いま効くもの」だけ。番組側からのものは、見落とすと半日止まる（day-4）
    for r in rows:
        names = [x["name"] for x in r["labels"]]
        if not names or "v1" in names or "番組側から" in names:
            tag = ",".join(names) or "ラベル無し"
            lines.append(f"  #{r['number']} [{tag}] {r['title']}")
    if any(not r["labels"] for r in rows):
        lines.append("  ※ ラベル無しは付け忘れ（#182）。番組側が立てたものなら `番組側から`、"
                     "こちらのものなら中身を読んで v1 / enhancement / 道具 に振り分ける")


def recent_section(lines):
    since = (datetime.datetime.now(datetime.timezone.utc)
             - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
    rows = gh_json(["issue", "list", "--state", "all",
                    "--search", f"updated:>={since}", "--limit", "30",
                    "--json", "number,title,updatedAt,state"])
    if not rows:
        return
    rows.sort(key=lambda r: r["updatedAt"], reverse=True)
    lines.append("")
    lines.append("最近動いた Issue（上位5件・手元の時刻）:")
    for r in rows[:5]:
        t = datetime.datetime.fromisoformat(
            r["updatedAt"].replace("Z", "+00:00")).astimezone()
        mark = "閉" if r["state"] == "CLOSED" else "開"
        lines.append(f"  {t:%m/%d %H:%M} [{mark}] #{r['number']} {r['title']}")


def prs_section(lines):
    rows = gh_json(["pr", "list", "--json", "number,title"])
    if not rows:
        return
    lines.append("")
    lines.append("開いている PR:")
    for r in rows:
        lines.append(f"  #{r['number']} {r['title']}")


def local_section(lines):
    branch = run(["git", "branch", "--show-current"])
    if branch is None:
        return
    lines.append("")
    lines.append(f"ブランチ: {branch.strip() or '（切り離された状態）'}")
    dirty = run(["git", "status", "--short"])
    if dirty and dirty.strip():
        lines.append("**コミットしていない変更がある。"
                     "ユーザーの作業かもしれないので、捨てる前に中身を見る:**")
        for line in dirty.rstrip("\n").split("\n"):
            lines.append(f"  {line}")


def main():
    lines = []
    for section in (issues_section, recent_section, prs_section, local_section):
        try:
            section(lines)
        except Exception:
            pass          # 1つ失敗しても、残りは出す
    text = "\n".join(lines).strip()
    if not text:
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext":
            "いまの状態（SessionStart hook が GitHub と手元から取った事実）:\n\n" + text,
    }}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)       # 何があってもセッションは始める
