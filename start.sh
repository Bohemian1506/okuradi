#!/usr/bin/env bash
# okuradi の作業環境を1つのコマンドで開く。
#
#   ./start.sh [-c|--continue] [--with-freelife | --open-freelife] [--no-attach]
#
#   1. Herdr のサーバーが止まっていれば起動する
#   2. okuradi のワークスペース（タブ main / run）を用意する。あれば使い回す
#   3. メインの Claude を lead という名前で起動する。すでに動いていれば起動しない
#   4. 画面を lead に切り替えて、Herdr を開く（Herdr の中から実行したときは切り替えだけ）
#
#   -c, --continue  前回の会話の続きから Claude を起動する（claude --continue）
#   --with-freelife フリーライフ（~/フリーライフ資料）も起動する。
#                   そのワークスペースの中で、フリーライフの start.sh を実行する（フリーライフ側は変えない）
#   --open-freelife フリーライフのワークスペースを用意し（起動はしない）、最後にフリーライフの画面を開く。
#                   okuradi の準備は同じようにする（F12 の「herdr: フリーライフ資料」用）
#   --no-attach     画面の切り替えも、Herdr を開くこともしない（用意だけする）
#   -h, --help      この説明を出す
#
# 使い方の説明は docs/herdr.md。
# ほぼ同時に2回実行すると、ワークスペースが2つできることがある（1人で使う前提なので防いでいない）。

set -uo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
LABEL="okuradi"
LEAD="lead"

CONTINUE="off"
ATTACH="on"
WITH_FREELIFE="off"
OPEN_FREELIFE="off"
for arg in "$@"; do
  case "$arg" in
    -c|--continue) CONTINUE="on" ;;
    --no-attach)   ATTACH="off" ;;
    --with-freelife) WITH_FREELIFE="on" ;;
    --open-freelife) OPEN_FREELIFE="on" ;;
    -h|--help)     sed -n '2,21p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "知らないオプションです: $arg（--help で使い方を表示）" >&2; exit 1 ;;
  esac
done

say() { printf '%s\n' "$*"; }

# 失敗したら理由を出して止める。
# WezTerm のメニューから開いたときは、すぐ閉じて読めなくならないよう Enter を待つ。
fail() {
  printf 'エラー: %s\n' "$*" >&2
  if [[ "${HERDR_ENV:-}" != "1" && -t 0 && -t 1 ]]; then
    read -rp "Enter で閉じます" _
  fi
  exit 1
}

command -v herdr >/dev/null 2>&1 || fail "herdr が見つかりません（入れ方: https://herdr.dev/docs/install/）"
command -v jq >/dev/null 2>&1 || fail "jq が見つかりません（入れ方: sudo apt install jq）"

# herdr の応答からエラー文を取り出す。取り出せなければ応答をそのまま（先頭だけ）出す
error_of() {
  local msg
  msg=$(jq -r '.error.message // empty' 2>/dev/null <<<"$1") || msg=""
  [[ -n "$msg" ]] || msg="${1:0:200}"
  printf '%s' "$msg"
}

# herdr の状態を日本語にする（docs/herdr.md の呼び方に合わせる）
status_ja() {
  case "$1" in
    working) echo "作業中" ;;
    blocked) echo "承認待ち" ;;
    done|idle) echo "入力待ち" ;;
    *) echo "状態不明" ;;
  esac
}

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

# ラベルでワークスペースを探す
workspace_by_label() {
  herdr workspace list | jq -r --arg l "$1" '[.result.workspaces[]? | select(.label == $l)][0].workspace_id // empty'
}

# ── 1. サーバー ───────────────────────────────────────────────
server_running() { herdr status server --json 2>/dev/null | jq -e '.running == true' >/dev/null 2>&1; }

if ! server_running; then
  say "Herdr を起動します"
  setsid -f herdr server >/dev/null 2>&1 </dev/null
  for _ in $(seq 1 40); do server_running && break; sleep 0.25; done
  server_running || fail "Herdr を起動できませんでした。~/.config/herdr/ のログを見るか、もう一度実行してください"
fi

# ── 1-b. フリーライフ（--with-freelife / --open-freelife のとき）──
# フリーライフの start.sh は「フリーライフのワークスペースの中の、何も動いていないシェル」から
# 実行すると、そのペインを編集局長にし、編集長・副局長も起動する。ここではその入口を用意するだけ。
FL_DIR="${FREELIFE_MAIN_DIR:-$HOME/フリーライフ資料}"
FL_LABEL="$(basename "$FL_DIR")"
fl_ws=""
fl_new_pane=""

# フリーライフのワークスペースが無ければ作る
ensure_freelife_workspace() {
  local out
  fl_ws=$(workspace_by_label "$FL_LABEL")
  [[ -n "$fl_ws" ]] && return 0
  say "フリーライフのワークスペースを作ります"
  out=$(herdr workspace create --cwd "$FL_DIR" --label "$FL_LABEL" --no-focus 2>&1)
  fl_ws=$(jq -r '.result.workspace.workspace_id // empty' <<<"$out" 2>/dev/null)
  fl_new_pane=$(jq -r '.result.root_pane.pane_id // empty' <<<"$out" 2>/dev/null)
  if [[ -z "$fl_ws" ]]; then
    say "（フリーライフのワークスペースを作れませんでした: $(error_of "$out")）"
    return 1
  fi
}

start_freelife() {
  local pane out director_ws
  director_ws=$(herdr agent get director 2>/dev/null | jq -r '.result.agent.workspace_id // empty' 2>/dev/null)
  if [[ -n "$director_ws" && "$director_ws" == "$fl_ws" ]]; then
    say "フリーライフはすでに動いています"
    return
  fi

  pane=""
  if [[ -n "$fl_new_pane" ]] && wait_idle_shell "$fl_new_pane"; then
    pane="$fl_new_pane"
  else
    for p in $(herdr pane list --workspace "$fl_ws" | jq -r --arg d "$FL_DIR" '.result.panes[]? | select(.cwd == $d) | .pane_id'); do
      if pane_is_idle_shell "$p"; then pane="$p"; break; fi
    done
  fi
  if [[ -z "$pane" ]]; then
    say "（フリーライフのワークスペースに空いているシェルが無いため、フリーライフは起動しませんでした。フリーライフの画面で ./start.sh を実行してください）"
    return
  fi

  out=$(herdr pane run "$pane" ./start.sh 2>&1)
  if [[ -n "$(jq -r '.error.code // empty' <<<"$out" 2>/dev/null)" ]]; then
    say "（フリーライフの start.sh を実行できませんでした: $(error_of "$out")）"
    return
  fi
  say "フリーライフの起動を始めました（編集局長・編集長・副局長が順に立ち上がります）"
}

if [[ "$WITH_FREELIFE" == "on" || "$OPEN_FREELIFE" == "on" ]]; then
  if [[ ! -x "$FL_DIR/start.sh" ]]; then
    say "（フリーライフが見つからないため、okuradi だけ用意します: $FL_DIR）"
    OPEN_FREELIFE="off"
  elif ensure_freelife_workspace; then
    [[ "$WITH_FREELIFE" == "on" ]] && start_freelife
  else
    OPEN_FREELIFE="off"
  fi
fi

# ── 2. ワークスペース ─────────────────────────────────────────
ws=$(workspace_by_label "$LABEL")

root_pane=""
if [[ -z "$ws" ]]; then
  say "okuradi のワークスペースを作ります"
  out=$(herdr workspace create --cwd "$ROOT" --label "$LABEL" --no-focus 2>&1)
  ws=$(jq -r '.result.workspace.workspace_id // empty' <<<"$out" 2>/dev/null)
  [[ -n "$ws" ]] || fail "ワークスペースを作れませんでした（$(error_of "$out")）。もう一度実行してください"
  root_pane=$(jq -r '.result.root_pane.pane_id' <<<"$out")
  herdr tab rename "$(jq -r '.result.tab.tab_id' <<<"$out")" main >/dev/null 2>&1
else
  say "okuradi のワークスペースを使います"
fi

tab_id_of() {
  herdr tab list --workspace "$ws" | jq -r --arg l "$1" '[.result.tabs[]? | select(.label == $l)][0].tab_id // empty'
}

# run タブが無ければ作る（アプリやログ用。無くても続ける）
if [[ -z "$(tab_id_of run)" ]]; then
  herdr tab create --workspace "$ws" --cwd "$ROOT" --label run --no-focus >/dev/null 2>&1 \
    || say "（run タブは作れませんでした。必要なら Herdr の画面で Ctrl+b → c で作ってください）"
fi

# ── 3. lead ───────────────────────────────────────────────────
lead_json=$(herdr agent get "$LEAD" 2>/dev/null)
lead_ws=$(jq -r '.result.agent.workspace_id // empty' <<<"$lead_json" 2>/dev/null)

if [[ -n "$lead_ws" && "$lead_ws" != "$ws" ]]; then
  fail "$LEAD という名前の Claude が、okuradi 以外のワークスペースで動いています。
そちらの Claude を終了するか、名前を変えてから、もう一度実行してください。
  名前の変え方: herdr agent rename $LEAD <新しい名前>"
fi

if [[ -n "$lead_ws" ]]; then
  say "$LEAD はすでに動いています（$(status_ja "$(jq -r '.result.agent.agent_status' <<<"$lead_json")")）"
else
  main_tab=$(tab_id_of main)
  [[ -n "$main_tab" ]] || main_tab=$(herdr tab list --workspace "$ws" | jq -r '.result.tabs[0].tab_id // empty')
  [[ -n "$main_tab" ]] || fail "okuradi のワークスペースにタブがありません。Herdr の画面でワークスペースを閉じてから、もう一度実行してください"

  # Claude を起動するペイン: 作ったばかりの最初のペイン → main タブの空いているシェル → 分割して作る
  pane=""
  if [[ -n "$root_pane" ]] && wait_idle_shell "$root_pane"; then
    pane="$root_pane"
  fi
  if [[ -z "$pane" ]]; then
    for p in $(herdr pane list --workspace "$ws" | jq -r --arg t "$main_tab" '.result.panes[]? | select(.tab_id == $t) | .pane_id'); do
      if pane_is_idle_shell "$p"; then pane="$p"; break; fi
    done
  fi
  if [[ -z "$pane" ]]; then
    first=$(herdr pane list --workspace "$ws" | jq -r --arg t "$main_tab" '[.result.panes[]? | select(.tab_id == $t)][0].pane_id // empty')
    [[ -n "$first" ]] || fail "main タブにペインがありません。Herdr の画面でワークスペースを閉じてから、もう一度実行してください"
    out=$(herdr pane split --pane "$first" --direction right --cwd "$ROOT" --no-focus 2>&1)
    pane=$(jq -r '.result.pane.pane_id // empty' <<<"$out" 2>/dev/null)
    [[ -n "$pane" ]] || fail "Claude を起動するペインを作れませんでした（$(error_of "$out")）。もう一度実行してください"
    wait_idle_shell "$pane" || fail "Claude を起動するペインの準備ができませんでした。もう一度実行してください"
  fi

  args=()
  [[ "$CONTINUE" == "on" ]] && args=(-- --continue)

  if [[ "$CONTINUE" == "on" ]]; then
    say "$LEAD を、前回の会話の続きから起動します"
  else
    say "$LEAD を起動します"
  fi
  # シェルがまだ入力を受け付けない（agent_pane_busy）ときだけ、少し待ってやり直す
  for _ in $(seq 1 10); do
    out=$(herdr agent start "$LEAD" --kind claude --pane "$pane" "${args[@]}" 2>&1)
    code=$(jq -r 'if .error then .error.code elif .result then "" else "unknown" end' <<<"$out" 2>/dev/null) || code="unknown"
    [[ "$code" == "agent_pane_busy" ]] || break
    sleep 0.5
  done
  case "$code" in
    "") say "$LEAD を起動しました" ;;
    agent_not_ready)
      say "$LEAD は起動しましたが、確認の画面で止まっています。Herdr の画面で答えてください" ;;
    *) fail "$LEAD を起動できませんでした（$(error_of "$out")）。
もう一度実行してください。続けて失敗するときは、Herdr の画面の okuradi の main タブで claude を手で起動し、
Claude に「Herdr での自分の名前を $LEAD にして」と頼んでください" ;;
  esac
fi

# ── 4. 画面を切り替えて開く ───────────────────────────────────
if [[ "$ATTACH" == "off" ]]; then
  if [[ "$OPEN_FREELIFE" == "on" ]]; then
    say "準備ができました。Herdr の画面でフリーライフを開いてください"
  else
    say "準備ができました。Herdr の画面で okuradi を開いてください"
  fi
  exit 0
fi

if [[ "$OPEN_FREELIFE" == "on" ]]; then
  herdr workspace focus "$fl_ws" >/dev/null 2>&1
  open_dir="$FL_DIR"
  opened="フリーライフ"
else
  herdr workspace focus "$ws" >/dev/null 2>&1
  herdr agent focus "$LEAD" >/dev/null 2>&1
  open_dir="$ROOT"
  opened="okuradi"
fi

if [[ "${HERDR_ENV:-}" != "1" && -t 0 && -t 1 ]]; then
  cd "$open_dir" && exec herdr
fi
say "準備ができました。$opened に切り替えました"
