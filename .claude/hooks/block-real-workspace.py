#!/usr/bin/env python3
"""Claude Code の PreToolUse hook: Claude が本物の作業フォルダで試すのを止める（#221）。

day-9（2026-09-26）に、担当（サブエージェント）が本物の作業フォルダを触る事故が2件あった。
  1. 試験のために `PUT /api/settings` で `settings.yml` を作って残し、別の担当が中身を見ずに消した
  2. 「`ep01` は読むだけ」と伝えていたのに、`ep01` で mix と動画化を動かした
**言葉の決まりは破られた**ので、道具で止める。止めるのは次の2つ:

  - 環境変数 `OKURADI_EPISODES_DIR` を付けずに、`build.py`・GUI のサーバー（uvicorn web.main）・
    古い GUI（streamlit run app.py）を起動すること。付けていれば一時フォルダに向く（docs/testing.md）
  - 本物のサーバー（8000番）への書き込み（curl の -X PUT/POST/DELETE/PATCH、-d、-F、-T など）

**Claude が打つコマンドだけに効く。** ユーザーが自分の端末で打つコマンドには効かないので、
番組づくりは今までどおり。担当か lead かも見分けない（lead が実際の音で通すときも一時フォルダでよい）。

分からないとき（入力が読めない）は止める側に倒す（止める系の道具の決まり・申し送り「気をつけること」）。
"""

import json
import os
import re
import sys

ENV = "OKURADI_EPISODES_DIR"
REAL_PORT = "8000"

MESSAGE_RUN = f"""本物の作業フォルダで {{what}} を動かそうとしたので、止めました（#221）。

リポジトリ直下の ep*/ と settings.yml は本物（ユーザーの回・ユーザーの設定）です。
試すときは、一時フォルダに向けてから起動してください。やり方は docs/testing.md:

  TMP=$(mktemp -d); cp -r ep01 assets "$TMP/"
  {ENV}="$TMP" .venv/bin/python build.py ep01 --from clean --to clean

本物で動かす必要があるときは、ユーザーに「! <コマンド>」で打ってもらってください。
"""

MESSAGE_CURL = f"""本物のサーバー（{REAL_PORT}番）に書き込もうとしたので、止めました（#221）。

{REAL_PORT}番はユーザーが立てた本物の GUI です。書き込むと、本物の回や settings.yml が変わります。
試すときは、一時フォルダに向けたサーバーを別の番号で立ててください（docs/testing.md）。
読むだけ（GET）は止めていません。
"""

# 起動を見分ける形。引用符の中の文字列（コミットの説明など）には当てない（区切ったあとの先頭で見る）
RUNS = [
    (re.compile(r"^(\S*/)?python[0-9.]*\s+(-\S+\s+)*\S*build\.py(\s|$)"), "build.py"),
    (re.compile(r"^(\S*/)?python[0-9.]*\s+(-\S+\s+)*-m\s+uvicorn\s+\S*web\.main"), "GUI のサーバー（uvicorn）"),
    (re.compile(r"^(\S*/)?uvicorn\s+\S*web\.main"), "GUI のサーバー（uvicorn）"),
    (re.compile(r"^(\S*/)?streamlit\s+run\s+\S*app\.py"), "古い GUI（streamlit）"),
    (re.compile(r"^(\S*/)?(\./)?start\.sh(\s|$)|^\./open-gui\.sh"), None),  # 画面を開くだけ。止めない
]
ASSIGN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(\"[^\"]*\"|'[^']*'|\S*)\s*")
WRITE_FLAGS = re.compile(
    r"(^|\s)(-X\s*(PUT|POST|DELETE|PATCH)|--request\s*=?\s*(PUT|POST|DELETE|PATCH)"
    r"|-d(\s|\S)|--data\S*|-F(\s|\S)|--form\S*|-T(\s|\S)|--upload-file|--json)")
# 大文字小文字を区別する。区別しないと、読むだけの -f（失敗で止める）・-D（ヘッダを書き出す）まで止めてしまう
REAL_URL = re.compile(rf"(127\.0\.0\.1|localhost|0\.0\.0\.0|\d+\.\d+\.\d+\.\d+):{REAL_PORT}(\D|$)")


def block(message):
    print(message, file=sys.stderr)
    sys.exit(2)


def strip_heredocs(text):
    """ヒアドキュメント（<<'EOF' … EOF）の中身は文字列なので読み飛ばす（block-hard-reset.sh と同じ考え）。

    区切り語が最後まで来なかったら、隠した行を戻す（安全側に倒す）。
    """
    out, held, delim = [], [], None
    for line in text.splitlines():
        if delim is not None:
            if line.replace("\t", "") == delim:
                delim, held = None, []
            else:
                held.append(line)
            continue
        probe = line.replace("<<<", "   ")
        m = re.search(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?", probe)
        if m:
            delim, held = m.group(1), []
        out.append(line)
    if delim is not None:
        out.extend(held)
    return "\n".join(out)


def segments(command):
    text = strip_heredocs(command.replace("\r", ""))
    return [s.strip() for s in re.split(r"[;&|\n]+", text) if s.strip()]


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        block("hook の入力を読めなかったため、止めました。")
    command = ((data or {}).get("tool_input") or {}).get("command") or ""
    if not command:
        return

    # Claude の環境そのものに付いていれば、どれも一時フォルダに向く
    env_set = bool(os.environ.get(ENV))

    for seg in segments(command):
        # 先頭の「名前=値」を剥がしながら、この区切りで付けたかを見る
        body, local = seg, False
        while True:
            m = ASSIGN.match(body)
            if not m:
                break
            if m.group(1) == ENV and m.group(2).strip("\"'"):
                local = True
            body = body[m.end():]
        if body.startswith("export ") and f"{ENV}=" in body:
            env_set = True          # 同じコマンドの後ろの区切りに効く
            continue
        if body.startswith("env "):
            if re.search(rf"(^|\s){ENV}=\S", body):
                local = True
            body = re.sub(r"^env\s+(-\S+\s+)*([A-Za-z_][A-Za-z0-9_]*=\S*\s+)*", "", body)

        for pattern, what in RUNS:
            if pattern.search(body):
                if what and not (local or env_set):
                    block(MESSAGE_RUN.format(what=what))
                break

        if re.match(r"^(\S*/)?curl(\s|$)", body) and REAL_URL.search(body) and WRITE_FLAGS.search(body):
            block(MESSAGE_CURL)


if __name__ == "__main__":
    main()
