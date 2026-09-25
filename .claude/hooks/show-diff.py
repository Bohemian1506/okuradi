#!/usr/bin/env python3
"""Claude Code の PostToolUse hook（Edit / Write）: 直した所の差分を、ペイン用のファイルに書く。

役割: 作業の画面（#183）の「変更」のペインに、**直前に直した所だけ**を映す。
ファイル全体は出さない。

**ここではペインに触らない。** `.claude/state/変更.txt` に書くだけで、映すのは
ペインの中で回っている `.claude/scripts/変更を映す.sh`。
Herdr の外でも、ペインが無くても、書くだけなので困らない。

差分は、Claude Code が渡す `tool_response.structuredPatch` から作る。
無ければ `tool_input` の old_string / new_string から作る（中身の形が変わっても止まらない）。

**何があってもツールの実行は止めない**（終了コードは必ず 0）。
"""

import difflib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
OUT = ROOT / ".claude" / "state" / "変更.txt"

RED, GREEN, CYAN, DIM, RESET = "\033[31m", "\033[32m", "\033[36m", "\033[2m", "\033[0m"


def color(line):
    if line.startswith("@@"):
        return CYAN + line + RESET
    if line.startswith("+"):
        return GREEN + line + RESET
    if line.startswith("-"):
        return RED + line + RESET
    return line


def from_patch(patch):
    """structuredPatch（塊の並び）を、unified diff の行にする。"""
    lines = []
    for h in patch:
        lines.append(f"@@ -{h['oldStart']},{h['oldLines']} +{h['newStart']},{h['newLines']} @@")
        lines.extend(h["lines"])
    return lines


def from_strings(old, new):
    return [l.rstrip("\n") for l in difflib.unified_diff(
        old.splitlines(), new.splitlines(), lineterm="", n=3)][2:]   # 先頭2行（---/+++）は捨てる


def diff_lines(data):
    resp = data.get("tool_response")
    if isinstance(resp, dict) and resp.get("structuredPatch"):
        return from_patch(resp["structuredPatch"])
    inp = data.get("tool_input") or {}
    tool = data.get("tool_name")
    if tool == "Edit":
        return from_strings(inp.get("old_string", ""), inp.get("new_string", ""))
    if tool == "MultiEdit":
        lines = []
        for e in inp.get("edits") or []:
            lines += from_strings(e.get("old_string", ""), e.get("new_string", ""))
        return lines
    if tool == "Write":
        n = len((inp.get("content") or "").splitlines())
        return [f"{DIM}（書き直し・新しいファイル。{n}行。全体は出さない）{RESET}"]
    return []


def main():
    data = json.loads(sys.stdin.read())
    if data.get("tool_name") not in ("Edit", "Write", "MultiEdit"):
        return
    path = (data.get("tool_input") or {}).get("file_path") or "?"
    try:
        path = str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        pass                 # リポジトリの外（memory など）はそのまま出す
    head = f"{CYAN}{path}{RESET}  {DIM}{data['tool_name']}  {time.strftime('%H:%M:%S')}{RESET}"
    body = [color(l) for l in diff_lines(data)]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text("\n".join([head, *body]) + "\n", encoding="utf-8")
    tmp.replace(OUT)         # 映す側が書きかけを読まないよう、入れ替えで書く


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
