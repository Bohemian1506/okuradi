#!/usr/bin/env bash
# Claude Code の PreToolUse hook: main ブランチへの push を止める。
#
# 役割: Claude が打つ push を早めに止める。書き方の見落としがあっても、
# 人が打った場合も含めて .githooks/pre-push と GitHub 側の設定で止まる。

set -uo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo "jq が無いため、main への push かどうかを確認できません。jq を入れてください。" >&2
  exit 2
fi

command=$(jq -r '.tool_input.command // empty' 2>/dev/null) || {
  echo "hook の入力を読めなかったため、止めました。" >&2
  exit 2
}
[[ -z "$command" ]] && exit 0

block() {
  cat >&2 <<'MSG'
main ブランチへの直接 push は止めています（CLAUDE.md の「絶対ルール」）。
作業ブランチで push し、gh pr create --base main で PR を作ってください。
MSG
  exit 2
}

# ; & | 改行 で区切り、先頭が git で始まる部分だけを見る。
# （引用符の中の「git push main」などの文字列には反応させないため）
while IFS= read -r segment; do
  [[ "$segment" =~ ^[[:space:]]*git[[:space:]] ]] || continue

  # git と push の間のオプション（-C <パス>、-c <設定> など）を読み飛ばす
  read -ra words <<<"$segment"
  i=1
  while (( i < ${#words[@]} )); do
    case "${words[i]}" in
      -C|-c|--git-dir|--work-tree|--namespace) i=$((i + 2)) ;;
      -*) i=$((i + 1)) ;;
      *) break ;;
    esac
  done
  [[ "${words[i]:-}" == "push" ]] || continue

  args=("${words[@]:i+1}")
  refs=()
  for arg in "${args[@]}"; do
    arg=${arg//\"/}
    arg=${arg//\'/}
    case "$arg" in
      --no-verify|--all|--mirror) block ;;
      -*) ;;
      *) refs+=("$arg") ;;
    esac
  done

  # 送り先の指定が無い push（今のブランチを送る）は、main にいれば止める
  if (( ${#refs[@]} <= 1 )) || [[ " ${refs[*]:1} " =~ [[:space:]]HEAD[[:space:]] ]]; then
    branch=$(git -C "${CLAUDE_PROJECT_DIR:-.}" branch --show-current 2>/dev/null || true)
    [[ "$branch" == "main" ]] && block
  fi

  # 2つ目以降（ブランチの指定）に main があれば止める
  for ref in "${refs[@]:1}"; do
    ref=${ref#+}
    dst=${ref##*:}
    [[ "$dst" == "main" || "$dst" == "refs/heads/main" ]] && block
  done
done < <(printf '%s\n' "$command" | tr ';&|' '\n\n\n')

exit 0
