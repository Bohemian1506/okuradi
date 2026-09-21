#!/usr/bin/env bash
# その日の実態を測る。議事録の冒頭のまとめを、写さずに書き直すため。
#
#   docs/dev-log/day-stats.sh [YYYY-MM-DD]   （省略したら今日）
#
# day-4 に「実装らしい実装はしていない日」と朝に書き、夕方に629行書いたのに
# そのまま残した。前に書いたものを写して、数え直さなかった。
# 数えるのが面倒だと写すので、1つのコマンドにした。
#
# 日付は手元の時刻で数える（git の --since は手元の時刻。gh の時刻は UTC なので別物）。

set -uo pipefail

day="${1:-$(date +%F)}"
next=$(date -d "$day +1 day" +%F 2>/dev/null) || { echo "日付が読めません: $day" >&2; exit 1; }

first=$(git log --since="$day 00:00" --until="$next 00:00" --pretty=%H | tail -1)
if [[ -z "$first" ]]; then
  echo "$day のコミットはありません"
  exit 0
fi
base=$(git rev-parse "$first^" 2>/dev/null) || base=$(git hash-object -t tree /dev/null)

echo "== $day の実態 =="
echo
printf 'マージした PR: %s件\n' "$(git log --since="$day 00:00" --until="$next 00:00" --merges --pretty=%H | grep -c '^' || true)"
echo

# 文書とそれ以外に分ける。「実装したか」はここで決まる
# 文書 = docs/ と、根っこの README.md / CLAUDE.md だけ。
# .claude/ の中は .md でも道具（/区切り など）なので、コード側に数える
docs_spec=(docs README.md CLAUDE.md)
code_spec=(. ':(exclude)docs' ':(exclude,top)README.md' ':(exclude,top)CLAUDE.md')
doc=$(git diff --shortstat "$base" HEAD -- "${docs_spec[@]}" 2>/dev/null)
code=$(git diff --shortstat "$base" HEAD -- "${code_spec[@]}" 2>/dev/null)
printf '文書（docs/ と README/CLAUDE）: %s\n' "${doc:-変更なし}"
printf 'それ以外（コード・道具・テスト）: %s\n' "${code:-変更なし}"
echo

echo "新しく足したファイル（文書以外）:"
# core.quotepath=false を付けないと、日本語のファイル名がエスケープされて読めない
added=$(git -c core.quotepath=false diff --diff-filter=A --name-only "$base" HEAD -- "${code_spec[@]}" 2>/dev/null)
if [[ -n "$added" ]]; then
  printf '%s\n' "$added" | while IFS= read -r f; do
    n=$(git show "HEAD:$f" 2>/dev/null | grep -c '^') || n=0
    printf '  %s  %s行\n' "$f" "$n"
  done
else
  echo "  無し"
fi
echo

# テストの件数。申し送りに書く数字を、写さずに数え直すため。
# day-5 の申し送りは 232件、その前は 225件。どちらも「前の版から写して古くなった」形。
# --collect-only は走らせずに数えるだけなので速い（実測 0.4秒）。
root=$(git rev-parse --show-toplevel 2>/dev/null)
if [[ -n "$root" && -x "$root/.venv/bin/python" ]]; then
  tests=$("$root/.venv/bin/python" -m pytest --collect-only -q 2>/dev/null |
          grep -oE '[0-9]+ tests? collected' | grep -oE '^[0-9]+')
  printf 'pytest: %s件\n' "${tests:-数えられませんでした}"
else
  echo 'pytest: .venv が見つからないので数えていません'
fi
echo
echo "※ この数字を議事録の冒頭に書く。前の版から写さない。"
echo "※ pytest の件数は申し送りに書く。ここも写さない。"
