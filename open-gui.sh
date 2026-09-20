#!/usr/bin/env bash
# 制作GUI を Windows のブラウザで開く。
#
#   ./open-gui.sh [ポート]
#
#   WSL の IP は再起動すると変わるので、毎回ここで調べ直して開く。
#   サーバーの起動はしない（動いていなければ、そう言って止まる）。
#
#   サーバーの起動:
#     .venv/bin/python -m uvicorn web.main:app --host 0.0.0.0 --reload
#
#   --host 0.0.0.0 が要るのは、付けないと WSL の中だけで待ち、
#   Windows のブラウザから入れないため（#77）。
#
#   -h, --help  この説明を出す

set -uo pipefail

PORT="8000"
for arg in "$@"; do
  case "$arg" in
    -h|--help) sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    ''|*[!0-9]*) echo "ポートは数字で指定してください: $arg（--help で使い方を表示）" >&2; exit 1 ;;
    *) PORT="$arg" ;;
  esac
done

say() { printf '%s\n' "$*"; }
fail() { printf 'エラー: %s\n' "$*" >&2; exit 1; }

# WSL の中で動いているか。Windows のブラウザを開くのに explorer.exe を使うため
command -v explorer.exe >/dev/null 2>&1 \
  || fail "explorer.exe が見つかりません。WSL の中で実行してください"

ip=$(hostname -I 2>/dev/null | awk '{print $1}')
[[ -n "$ip" ]] || fail "WSL の IP が分かりませんでした（hostname -I が何も返しません）"

url="http://$ip:$PORT"

# サーバーが動いていなければ、開く前に言う。
# 動いていない画面を開くと「住所が違うのか、落ちているのか」が分からなくなる
if ! curl -s -o /dev/null --max-time 3 "http://127.0.0.1:$PORT/" 2>/dev/null; then
  fail "$PORT 番でサーバーが動いていません。先に起動してください:

  .venv/bin/python -m uvicorn web.main:app --host 0.0.0.0 --reload"
fi

# 0.0.0.0 で待っていないと、WSL の外からは入れない
if ! curl -s -o /dev/null --max-time 3 "$url/" 2>/dev/null; then
  fail "WSL の中からは開けますが、$ip からは開けません。
サーバーが 127.0.0.1 だけで待っている可能性があります。--host 0.0.0.0 を付けて起動し直してください:

  .venv/bin/python -m uvicorn web.main:app --host 0.0.0.0 --reload"
fi

say "$url を開きます"
# explorer.exe は成功しても 1 を返すことがあるので、戻り値は見ない
explorer.exe "$url" >/dev/null 2>&1 || true
