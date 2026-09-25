#!/usr/bin/env bash
# 作業の画面（#183）。Claude の右に3つのペインを並べる / 閉じる。
#
#   作業ペイン.sh [open]   ペインが無ければ作り、今日の一手を映す（/始め の最後に呼ぶ）
#   作業ペイン.sh gui      GUI のログのペインで、GUI のサーバーを立てる（使う日だけ）
#   作業ペイン.sh close    3つのペインを閉じる（/作業終了 から呼ぶ）
#
#   ┌──────────────┬──────────────┐
#   │              │ 変更          │ 22行  直前に直した所の差分（最初は空）
#   │   Claude     ├──────────────┤
#   │              │ GUIログ       │ 14行  GUI のサーバーの出力（立てるまで空）
#   │              ├──────────────┤
#   │              │ 今日の一手    │ 12行  .claude/state/今日の一手.md を less で
#   └──────────────┴──────────────┘
#
# ペインは**名前で探す**（ID は毎回変わる）。探すのは、いまのタブの中だけ。
# Herdr の外では何もしないが、**黙らずに1行出す**（CLAUDE.md「静かに失敗させない」）。
# GUI のサーバーは /始め では立てない（2026-09-25・ユーザーの判断。立てない日もある /
# --host 0.0.0.0 は同じ LAN から見える）。
set -u

CMD="${1:-open}"
[ "${HERDR_ENV:-}" = "1" ] || { echo "Herdr の外なので、作業のペインは扱わなかった（$CMD）"; exit 0; }
cd "$(git rev-parse --show-toplevel)" || exit 1

DIFF=変更 LOG=GUIログ TODAY=今日の一手
TODAY_FILE=.claude/state/今日の一手.md
GUI_CMD=".venv/bin/python -m uvicorn web.main:app --host 0.0.0.0 --reload"

TAB=$(herdr pane current | jq -r '.result.pane.tab_id // empty')
[ -n "$TAB" ] || { echo "いまのタブが分からないので、作業のペインは扱わなかった"; exit 0; }

find_pane() {
  herdr pane list | jq -r --arg t "$TAB" --arg l "$1" \
    '.result.panes[]? | select(.tab_id==$t and .label==$l) | .pane_id' | head -1
}

# ペインの中で動いているもの（シェルだけなら空）
fg_of() {
  herdr pane process-info --pane "$1" 2>/dev/null | jq -r '
    .result.process_info as $p
    | if ($p.foreground_processes | length) == 1 and $p.foreground_processes[0].pid == $p.shell_pid
      then "" else ($p.foreground_processes | map(.name) | join(",")) end'
}

# 作ったばかりのペインは、シェルの準備ができるまで何か動いて見える（上限10秒）
wait_idle() {
  for _ in $(seq 1 40); do [ -z "$(fg_of "$1")" ] && return 0; sleep 0.25; done
  return 1
}

D=$(find_pane $DIFF); L=$(find_pane $LOG); T=$(find_pane $TODAY)

case "$CMD" in
open)
  if [ -z "$D$L$T" ]; then
    # 高さは 22 / 14 / 12（48行のとき）。--ratio は元のペインの取り分
    D=$(herdr pane split --current --direction right --cwd "$PWD" --no-focus | jq -r '.result.pane.pane_id // empty')
    [ -n "$D" ] || { echo "ペインを作れなかった（右に割れなかった）"; exit 0; }
    L=$(herdr pane split "$D" --direction down --ratio 0.46 --cwd "$PWD" --no-focus | jq -r '.result.pane.pane_id // empty')
    T=$(herdr pane split "$L" --direction down --ratio 0.54 --cwd "$PWD" --no-focus | jq -r '.result.pane.pane_id // empty')
    [ -n "$L" ] && [ -n "$T" ] || { echo "ペインを途中までしか作れなかった。Herdr の画面で確かめる"; exit 0; }
    herdr pane rename "$D" $DIFF >/dev/null
    herdr pane rename "$L" $LOG >/dev/null
    herdr pane rename "$T" $TODAY >/dev/null
    for p in "$D" "$L" "$T"; do wait_idle "$p" || echo "$p のシェルの準備が終わらない"; done
    echo "作業のペインを作った"
  elif [ -z "$D" ] || [ -z "$L" ] || [ -z "$T" ]; then
    echo "作業のペインが一部だけある（変更:${D:-無} / GUIログ:${L:-無} / 今日の一手:${T:-無}）。形が分からないので触らない"
    exit 0
  fi

  # 変更: 映す係が止まっていれば回す
  [ -z "$(fg_of "$D")" ] && herdr pane run "$D" "clear; .claude/scripts/変更を映す.sh" >/dev/null

  # 今日の一手: 前のを出したままなら閉じてから開き直す
  if [ -f "$TODAY_FILE" ]; then
    case "$(fg_of "$T")" in
      "") ;;
      less) herdr pane send-keys "$T" q >/dev/null; sleep 0.3 ;;
      *) echo "今日の一手のペインで $(fg_of "$T") が動いている。触らない"; exit 0 ;;
    esac
    herdr pane run "$T" "clear; less -R $TODAY_FILE" >/dev/null
    echo "今日の一手を映した"
  else
    echo "$TODAY_FILE が無いので、今日の一手は映していない"
  fi
  ;;

gui)
  [ -n "$L" ] || { echo "GUIログのペインが無い。先に open する"; exit 0; }
  fg=$(fg_of "$L")
  [ -z "$fg" ] || { echo "GUIログのペインで $fg が動いている（もう立っているかもしれない）。触らない"; exit 0; }
  herdr pane run "$L" "clear; $GUI_CMD" >/dev/null
  echo "GUI のサーバーを GUIログのペインで立てた。開くのは ./open-gui.sh"
  ;;

close)
  closed=0
  for p in "$D" "$L" "$T"; do
    [ -n "$p" ] || continue
    [ "$p" = "$L" ] && [ -n "$(fg_of "$L")" ] && echo "GUI のサーバーも止まる（GUIログのペインを閉じるため）"
    herdr pane close "$p" >/dev/null && closed=$((closed + 1))
  done
  echo "作業のペインを ${closed} つ閉じた"
  ;;

*)
  echo "知らないサブコマンド: $CMD（open / gui / close）"; exit 1 ;;
esac
