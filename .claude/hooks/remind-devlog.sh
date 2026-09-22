#!/usr/bin/env bash
# Claude Code の PostToolUse hook: PR をマージした直後に、議事録を思い出させる。
#
# 役割: 「マージしたら、次の作業に入る前に議事録を書く」（CLAUDE.md）の書き忘れを防ぐ。
# day-6 に、#145 と #146 をマージしたあと議事録を書かずに次の実装に入った。
# ルールは読んでいたのに飛ばした。読ませるのではなく、その場で知らせる形にする。
#
# **止めない。知らせるだけ。** CLAUDE.md に「誤字直しなど、経緯を残すほどでない PR は
# 省いてよい」とあるので、機械が一律に止めると、省いてよい場面まで止まる。
# 判定できないものを止める側に倒すと、判定の不具合で作業が全部止まる。
#
# **gh を呼ばない。** 固まると毎回それだけ待つことになる
# （始まるときの hook が gh で 45秒かかった件）。

set -uo pipefail

# jq が無くても、知らせるだけなので黙って通す（止める守りとは違う）
command -v jq >/dev/null 2>&1 || exit 0

command=$(jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
[[ -z "$command" ]] && exit 0

# ヒアドキュメントの中身は文字列なので見ない。
# これが無いと、PR 本文に「gh pr merge」と書いただけで知らせが出る。
strip_heredocs() {
  local line probe delim="" in_body=0
  while IFS= read -r line; do
    if (( in_body )); then
      [[ "${line//$'\t'/}" == "$delim" ]] && in_body=0
      continue
    fi
    probe=${line//<<</  }
    if [[ "$probe" =~ \<\<-?[[:space:]]*[\'\"]?([A-Za-z_][A-Za-z0-9_]*)[\'\"]? ]]; then
      delim="${BASH_REMATCH[1]}"
      in_body=1
    fi
    printf '%s\n' "$line"
  done
}

merged=0
while IFS= read -r segment; do
  [[ "$segment" =~ ^[[:space:]]*gh[[:space:]] ]] || continue
  read -ra words <<<"$segment"
  [[ "${words[1]:-}" == "pr" && "${words[2]:-}" == "merge" ]] && merged=1
done < <(printf '%s\n' "$command" | tr -d '\r' | strip_heredocs | tr ';&|' '\n\n\n')

(( merged )) || exit 0

cat >&2 <<'MSG'
PR をマージしました。CLAUDE.md の「作業の流れ」7 では、次はこれです。

  次の作業に入る前に、その PR に至った経緯を docs/dev-log/day-N.md に追記し、
  議事録だけの PR を作ってマージする。

- 書くことは docs/dev-log/README.md（きっかけ / 検討したこと / 決めたこと / やったこと / 困ったこと）
- 冒頭のまとめは docs/dev-log/day-stats.sh で測り直す。前の版から写さない
- ブランチは main に戻ってから切る（git switch main && git pull && git switch -c ...）

いま流したのが議事録の PR そのものなら、この知らせは無視してください。
経緯を残すほどでない PR（誤字直しなど）も省いてよい、と CLAUDE.md にあります。
MSG
exit 0
