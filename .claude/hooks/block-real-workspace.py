#!/usr/bin/env python3
"""Claude Code の PreToolUse hook: Claude が本物の作業フォルダに届く道を止める（#221・案A'）。

day-9（2026-09-26）に、担当（サブエージェント）が本物の作業フォルダを触る事故が2件あった。
**言葉の決まりは破られた**ので、道具で止める。守りは2段:

  1. **起動の守りは build.py の中**（`build.episodes_root()`）。Claude Code が打つコマンドには環境変数
     CLAUDECODE が付き、`bash -c`・`nohup`・子のプロセスにも引き継がれる。それがあって一時フォルダ
     （OKURADI_EPISODES_DIR）が無ければ、build.py・GUI のサーバー・app.py は本物を使わずに止まる。
     **コマンドの文字列を読んで起動を見分けるのはやめた**（書き方ですり抜けられ、引用符の中の文章まで
     止めていた。#228 のレビュー）
  2. **この hook** が見るのは2つだけ:
     - `OKURADI_REAL`（本物を使う合言葉）という語。これを付けると 1 の守りを越えられるので、
       Claude の打つコマンドに出てきたら止める。**ユーザーの `!` には hook が効かない**ので、
       ユーザーは `! OKURADI_REAL=1 ...` で本物を動かせる（2026-09-26 に確かめた）
     - 起動の守りが見る印（CLAUDECODE）を外すこと（env -u・unset・env -i）
     - 本物のサーバー（8000番）への書き込み。サーバーは誰が書いたかを見分けられないので、ここだけは
       文字列で止める。**完全ではない**（ヘッドレスの Chrome でボタンを押す、などは止められない）

**止めるのは、うっかりと軽い回避まで。わざと隠す形（語を分けて組み立てる、など）は越えられる。**
文字列を読む守りの限界として、2026-09-26 にユーザーが受け入れた（#228 のレビュー・案A）。

分からないとき（入力が読めない）は止める側に倒す（止める系の道具の決まり）。
"""

import json
import re
import sys

WORD = "OKURADI_" + "REAL"
REAL_PORT = "8000"

MESSAGE_WORD = f"""{WORD} は、ユーザーが本物の回で動かすための合言葉です。Claude は使いません（#221）。

試すときは、一時フォルダに向けてください（docs/testing.md）:
  TMP=$(mktemp -d); cp -r ep01 assets "$TMP/"
  OKURADI_EPISODES_DIR="$TMP" .venv/bin/python build.py ep01 --from clean --to clean

本物で動かす必要があるときは、ユーザーに「! {WORD}=1 <コマンド>」で打ってもらってください。
"""

MESSAGE_WRITE = f"""本物のサーバー（{REAL_PORT}番）に書き込もうとしたので、止めました（#221）。

{REAL_PORT}番はユーザーが立てた本物の GUI です。書き込むと、本物の回や settings.yml が変わります。
試すときは、一時フォルダに向けたサーバーを別の番号で立ててください（docs/testing.md）。
読むだけ（GET）は止めていません。
"""

MARK = "CLAUDE" + "CODE"

MESSAGE_MARK = f"""{MARK}（Claude から起動されたことを示す環境変数）を外そうとしたので、止めました（#221）。

build.py は {MARK} を見て、一時フォルダ無しでは本物の回を使わずに止まります。外すと、その守りを越えます。
試すときは、一時フォルダに向けてください（docs/testing.md）。
"""

# 8000番の書き方の違いも当てる: 先頭のゼロ（:08000）、ループバックの別表記（127.1・10進の数）、
# ホストと番号を別の変数に入れる（PORT=8000）。どれも curl が本当に 8000 番へ繋ぐことを確かめてある（#228 のレビュー）
REAL_URL = re.compile(rf"[^\s/'\"]+:0*{REAL_PORT}(\D|$)|(^|[\s;&|(])\w+=['\"]?0*{REAL_PORT}(\D|$)")
# 書き込む道具と、書き込む指定。**まとめて書いた短い指定**（-sXPUT・-sd）も当てる。
# 大文字小文字は区別する（区別しないと、読むだけの -f・-D まで止める）
WRITERS = re.compile(r"(^|[\s;&|('\"`$])(curl|wget|http|httpie)(\s|$)")
WRITE_FLAGS = re.compile(
    r"(^|\s)-[A-Za-z]*X\s*['\"]?(PUT|POST|DELETE|PATCH)"      # -X PUT / -sXPUT
    r"|(^|\s)-[A-Za-z]*[dFT](\s|['\"@{]|$)"                    # -d / -sd / -F / -T
    r"|--(data|form|json|upload-file|request\s*=?\s*['\"]?(PUT|POST|DELETE|PATCH))"
    r"|--method\s*=?\s*['\"]?(PUT|POST|DELETE|PATCH)|--post-(data|file)"   # wget
    r"|(^|\s)(PUT|POST|DELETE|PATCH)(\s)"                       # httpie
)
# Python などから直接書く（urllib・requests）
SCRIPT_WRITE = re.compile(r"method\s*=\s*['\"](PUT|POST|DELETE|PATCH)|requests\.(put|post|delete|patch)\(")


def block(message):
    print(message, file=sys.stderr)
    sys.exit(2)


def strip_heredocs(text):
    """ヒアドキュメント（<<'EOF' … EOF）の中身は、Bash が実行しない文字列なので読み飛ばす。

    **ただし `python - <<EOF` のように、中身を実行する道具に渡すときは読み飛ばさない**
    （Python から 8000 番に書く、を見落とさないため）。区切り語が最後まで来なかったら、
    隠した行を戻す（安全側に倒す）。
    """
    out, held, delim, keep = [], [], None, False
    for line in text.splitlines():
        if delim is not None:
            if line.replace("\t", "") == delim:
                if keep:
                    out.extend(held)
                delim, held = None, []
            else:
                held.append(line)
            continue
        probe = line.replace("<<<", "   ")
        m = re.search(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?", probe)
        if m:
            delim, held = m.group(1), []
            keep = bool(re.search(r"(^|[\s;&|(])(\S*/)?(python[0-9.]*|node|bash|sh)(\s|$)", probe[:m.start()]))
        out.append(line)
    if delim is not None:
        out.extend(held)
    return "\n".join(out)


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        block("hook の入力を読めなかったため、止めました。")
    command = ((data or {}).get("tool_input") or {}).get("command") or ""
    if not command:
        return
    text = strip_heredocs(command.replace("\r", ""))

    # 合言葉は、どこに書いてあっても止める（引用符の中・bash -c の中・変数に入れても、語が続けて書いてあれば当たる）。
    # **語を分けて組み立てれば越えられる**（A="OKURADI_"; B="REAL"）。ここで止めるのは、うっかりと軽い回避まで。
    # わざと隠すものまでは止めない（2026-09-26・ユーザーの判断・案A）
    if WORD in text:
        block(MESSAGE_WORD)

    # 起動の守り（build.episodes_root）が見る印を外す: env -u / unset / env -i（環境を丸ごと空にする）
    if MARK in text or re.search(r"(^|[\s;&|(])env\s+(-\S+\s+)*(-i|--ignore-environment)(\s|$)", text):
        block(MESSAGE_MARK)

    # 8000番への書き込み。URL を変数に入れても、同じコマンドのどこかに :8000 があれば見る
    if REAL_URL.search(text):
        if (WRITERS.search(text) and WRITE_FLAGS.search(text)) or SCRIPT_WRITE.search(text):
            block(MESSAGE_WRITE)


if __name__ == "__main__":
    main()
