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

# ヒアドキュメント（<<'EOF' … EOF）の中身は、コマンドではなく文字列なので読み飛ばす。
# これが無いと、コミットメッセージや Issue の本文に文字列として書いただけで止まってしまう（#108）。
strip_heredocs() {
  local line probe delim="" in_body=0
  local -a held=()
  while IFS= read -r line; do
    if (( in_body )); then
      # 区切り語の行に来たら本文の終わり（<<- はタブの字下げを許す）
      if [[ "${line//$'\t'/}" == "$delim" ]]; then
        in_body=0
        held=()
        continue
      fi
      held+=("$line")
      continue
    fi
    # <<< はヒアストリングで、その行で終わる。ヒアドキュメントと見分けるため先に消す。
    # これが無いと「cat <<<foo」を本文の始まりと読み違え、後ろの本物が隠れる。
    probe=${line//<<</  }
    if [[ "$probe" =~ \<\<-?[[:space:]]*[\'\"]?([A-Za-z_][A-Za-z0-9_]*)[\'\"]? ]]; then
      delim="${BASH_REMATCH[1]}"
      in_body=1
      held=()
    fi
    printf '%s\n' "$line"
  done
  # 区切り語が最後まで来なかった（書きかけ・読み違え）。隠した行を戻して、安全側に倒す
  if (( in_body )) && (( ${#held[@]} )); then
    printf '%s\n' "${held[@]}"
  fi
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
# tr -d '\r' は、Windows 側から貼り付けた文字列が混ざったときのため（#112）。
# \r は空白ではないので語にくっついたままになり、比較が外れて素通りしていた。
# 読むのは判定のためだけなので、実行されるコマンドには影響しない。
done < <(printf '%s\n' "$command" | tr -d '\r' | strip_heredocs | tr ';&|' '\n\n\n')

exit 0
