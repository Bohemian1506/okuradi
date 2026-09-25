#!/usr/bin/env bash
# 「変更」のペインの中で回し続ける。.claude/state/変更.txt が書き換わったら映し直す。
#
# 書くのは .claude/hooks/show-diff.py（Edit / Write のたび）。
# **最初は空**（#183・ユーザーの指定）。起動したときにあった古い中身は映さず、
# 直した1回目で初めて映る。
# 入りきらない分は切って、残りの行数を出す（全体はファイルを見る）。
set -u
cd "$(git rev-parse --show-toplevel)" || exit 1
F=.claude/state/変更.txt

stamp() { stat -c %y "$F" 2>/dev/null; }

clear
last=$(stamp)
while :; do
  now=$(stamp)
  if [ -n "$now" ] && [ "$now" != "$last" ]; then
    last=$now
    rows=$(tput lines 2>/dev/null || echo 22)
    total=$(wc -l < "$F")
    clear
    if [ "$total" -le "$rows" ]; then
      cat "$F"
    else
      head -n $((rows - 1)) "$F"
      printf '\033[2m… ほか %d 行（全体は %s）\033[0m' $((total - rows + 1)) "$F"
    fi
  fi
  sleep 0.5
done
