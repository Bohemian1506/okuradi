#!/usr/bin/env bash
# Claude Code の PreToolUse hook: git reset --hard を止める。
#
# 役割: コミットしていない変更を、確かめずに消してしまうのを防ぐ。
# day-4 に、ユーザーが GUI で保存した設定を git reset --hard で消した事故がある。
# 追跡ファイルの作業中の変更は、reflog にも残らないので取り戻せない。

set -uo pipefail

if ! command -v jq >/dev/null 2>&1; then
  echo "jq が無いため、git reset --hard かどうかを確認できません。jq を入れてください。" >&2
  exit 2
fi

command=$(jq -r '.tool_input.command // empty' 2>/dev/null) || {
  echo "hook の入力を読めなかったため、止めました。" >&2
  exit 2
}
[[ -z "$command" ]] && exit 0

block() {
  cat >&2 <<'MSG'
git reset --hard は止めています。

コミットしていない変更が、確かめずに消えます。追跡ファイルの作業中の変更は
reflog にも残らないので、取り戻せません（day-4 に実際に消した事故があります）。

代わりに:
  git status                     まず何が残っているかを見る
  git checkout -- <ファイル>      捨てるものをファイル単位で指定する
  git reset --soft <位置>         コミットだけ戻す（作業中の変更は残る）
  git stash                      いったん退避する

どうしても必要なときは、ユーザーに「! git reset --hard ...」で
実行してもらってください。
MSG
  exit 2
}

# ヒアドキュメント（<<'EOF' … EOF）の中身は、コマンドではなく文字列なので読み飛ばす。
# これが無いと、コミットメッセージに「git reset --hard」と書いただけで止まってしまう。
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
# （引用符の中の「git reset --hard」などの文字列には反応させないため）
while IFS= read -r segment; do
  [[ "$segment" =~ ^[[:space:]]*git[[:space:]] ]] || continue

  # git と reset の間のオプション（-C <パス>、-c <設定> など）を読み飛ばす
  read -ra words <<<"$segment"
  i=1
  while (( i < ${#words[@]} )); do
    case "${words[i]}" in
      -C|-c|--git-dir|--work-tree|--namespace) i=$((i + 2)) ;;
      -*) i=$((i + 1)) ;;
      *) break ;;
    esac
  done
  [[ "${words[i]:-}" == "reset" ]] || continue

  for arg in "${words[@]:i+1}"; do
    arg=${arg//\"/}
    arg=${arg//\'/}
    [[ "$arg" == "--hard" ]] && block
  done
done < <(printf '%s\n' "$command" | strip_heredocs | tr ';&|' '\n\n\n')

exit 0
