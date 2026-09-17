#!/usr/bin/env bash
# Claude Code の PreToolUse hook: `git push ... main` を止める。
# 人が直接打った場合は .githooks/pre-push が止める。

set -euo pipefail

command=$(jq -r '.tool_input.command // empty' 2>/dev/null || true)
[[ -z "$command" ]] && exit 0

# git push を含む部分だけを見る（コミットメッセージ中の "main" で誤検知しないため、改行でも区切る）
push_segments=$(printf '%s' "$command" | awk -v RS='[;&|\n]+' '/(^|[[:space:]])git[[:space:]]+push([[:space:]]|$)/')
[[ -z "$push_segments" ]] && exit 0

if printf '%s' "$push_segments" | grep -Eq '(^|[[:space:]])main([[:space:]]|$)|:main([[:space:]]|$)|(^|[[:space:]])--(all|mirror)([[:space:]]|$)'; then
  cat >&2 <<'MSG'
main ブランチへの直接 push は止めています（CLAUDE.md の「絶対ルール」）。
作業ブランチで push し、gh pr create --base main で PR を作ってください。
MSG
  exit 2
fi
exit 0
