#!/usr/bin/env bash
# okuradi の作業環境を1つのコマンドで開く。
#
#   ./start.sh [-c|--continue] [--no-attach]
#
#   1. Herdr のサーバーが止まっていれば起動する
#   2. okuradi のワークスペース（タブ main / run）を用意する。あれば使い回す
#   3. メインの Claude を lead という名前で起動する。すでに動いていれば起動しない
#   4. 画面を lead に切り替えて、Herdr を開く（Herdr の中から実行したときは切り替えだけ）
#
#   -c, --continue  前回の会話の続きから Claude を起動する（claude --continue）
#   --no-attach     画面の切り替えも、Herdr を開くこともしない（用意だけする）
#
# 使い方の説明は docs/herdr.md。

set -uo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
LABEL="okuradi"
LEAD="lead"

CONTINUE="off"
ATTACH="on"
for arg in "$@"; do
  case "$arg" in
    -c|--continue) CONTINUE="on" ;;
    --no-attach)   ATTACH="off" ;;
    -h|--help)     sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "知らないオプションです: $arg（--help で使い方を表示）" >&2; exit 1 ;;
  esac
done

say() { printf '%s\n' "$*"; }
fail() { printf 'エラー: %s\n' "$*" >&2; exit 1; }

command -v herdr >/dev/null 2>&1 || fail "herdr が見つかりません（https://herdr.dev/docs/install/）"
command -v jq >/dev/null 2>&1 || fail "jq が見つかりません（sudo apt install jq）"

# 返ってきた JSON がエラーなら、その文を出す
error_of() { jq -r '.error.message // empty' 2>/dev/null <<<"$1" || printf '%s' "${1:0:200}"; }

# ── 1. サーバー ───────────────────────────────────────────────
server_running() { herdr status server 2>/dev/null | grep -q 'status: running'; }

if ! server_running; then
  say "Herdr のサーバーを起動します"
  setsid -f herdr server >/dev/null 2>&1 </dev/null
  for _ in $(seq 1 40); do server_running && break; sleep 0.25; done
  server_running || fail "Herdr のサーバーが起動しませんでした（ログ: ~/.config/herdr/）"
fi

# ── 2. ワークスペース ─────────────────────────────────────────
ws=$(herdr workspace list | jq -r --arg l "$LABEL" '[.result.workspaces[]? | select(.label == $l)][0].workspace_id // empty')

if [[ -z "$ws" ]]; then
  say "ワークスペース $LABEL を作ります"
  out=$(herdr workspace create --cwd "$ROOT" --label "$LABEL" --no-focus 2>&1)
  ws=$(jq -r '.result.workspace.workspace_id // empty' <<<"$out")
  [[ -n "$ws" ]] || fail "ワークスペースを作れませんでした: $(error_of "$out")"
  main_tab=$(jq -r '.result.tab.tab_id' <<<"$out")
  root_pane=$(jq -r '.result.root_pane.pane_id' <<<"$out")
  herdr tab rename "$main_tab" main >/dev/null 2>&1
  herdr tab create --workspace "$ws" --cwd "$ROOT" --label run --no-focus >/dev/null 2>&1 \
    || say "（run タブは作れませんでした。必要なら Ctrl+b → c で作ってください）"
else
  say "ワークスペース $LABEL（$ws）を使います"
fi

# ── 3. lead ───────────────────────────────────────────────────
lead_json=$(herdr agent get "$LEAD" 2>/dev/null)
lead_ws=$(jq -r '.result.agent.workspace_id // empty' <<<"$lead_json")

if [[ -n "$lead_ws" && "$lead_ws" != "$ws" ]]; then
  fail "$LEAD という名前の Claude が、別のワークスペース（$lead_ws）で動いています。そちらを閉じるか、名前を変えてください"
fi

# ペインが「何も動いていないシェル」か
pane_is_idle_shell() {
  herdr pane process-info --pane "$1" 2>/dev/null | jq -e '
    .result.process_info as $p
    | ($p.foreground_processes | length) == 1
      and $p.foreground_processes[0].pid == $p.shell_pid' >/dev/null 2>&1
}

# 作ったばかりのペインは、シェルの準備ができるまで少し待つ
wait_idle_shell() {
  for _ in $(seq 1 40); do pane_is_idle_shell "$1" && return 0; sleep 0.25; done
  return 1
}

if [[ -n "$lead_ws" ]]; then
  say "$LEAD はすでに動いています（$(jq -r '.result.agent.agent_status' <<<"$lead_json")）"
else
  main_tab=$(herdr tab list --workspace "$ws" | jq -r '
    [.result.tabs[]? | select(.label == "main")][0].tab_id
    // .result.tabs[0].tab_id // empty')
  [[ -n "$main_tab" ]] || fail "ワークスペース $ws のタブが見つかりません"

  # main タブの中で、何も動いていないシェルのペインを探す。無ければ分割して作る
  pane=""
  if [[ -n "${root_pane:-}" ]] && wait_idle_shell "$root_pane"; then
    pane="$root_pane"
  fi
  [[ -z "$pane" ]] && for p in $(herdr pane list --workspace "$ws" | jq -r --arg t "$main_tab" '.result.panes[]? | select(.tab_id == $t) | .pane_id'); do
    if pane_is_idle_shell "$p"; then pane="$p"; break; fi
  done
  if [[ -z "$pane" ]]; then
    first=$(herdr pane list --workspace "$ws" | jq -r --arg t "$main_tab" '[.result.panes[]? | select(.tab_id == $t)][0].pane_id // empty')
    out=$(herdr pane split --pane "$first" --direction right --cwd "$ROOT" --no-focus 2>&1)
    pane=$(jq -r '.result.pane.pane_id // empty' <<<"$out")
    [[ -n "$pane" ]] || fail "Claude を起動するペインを作れませんでした: $(error_of "$out")"
    wait_idle_shell "$pane" || fail "ペイン $pane のシェルが準備できませんでした"
  fi

  args=()
  [[ "$CONTINUE" == "on" ]] && args=(-- --continue)

  say "$LEAD を起動します（ペイン $pane）"
  # 作ったばかりのシェルは、まだ入力を受け付けないことがあるので、少し待ってやり直す
  for _ in $(seq 1 20); do
    out=$(herdr agent start "$LEAD" --kind claude --pane "$pane" "${args[@]}" 2>&1)
    code=$(jq -r 'if .error then .error.code elif .result then "" else "unknown" end' <<<"$out" 2>/dev/null) || code="unknown"
    [[ -z "$code" || "$code" == "agent_not_ready" ]] && break
    sleep 0.5
  done
  case "$code" in
    "") say "$LEAD を起動しました" ;;
    agent_not_ready)
      say "$LEAD は起動しましたが、確認の画面で止まっています。Herdr の画面で答えてください" ;;
    *) fail "$LEAD を起動できませんでした（$code）: $(error_of "$out")" ;;
  esac
fi

# ── 4. 画面を切り替えて開く ───────────────────────────────────
if [[ "$ATTACH" == "off" ]]; then
  say "準備ができました。Herdr の画面で okuradi を開いてください"
  exit 0
fi

herdr workspace focus "$ws" >/dev/null 2>&1
herdr agent focus "$LEAD" >/dev/null 2>&1

if [[ "${HERDR_ENV:-}" != "1" && -t 0 && -t 1 ]]; then
  cd "$ROOT" && exec herdr
fi
say "準備ができました。okuradi に切り替えました"
