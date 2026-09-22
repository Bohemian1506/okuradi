"""`start.sh` のテスト（#135）。

**PC を再起動しないと再現しない**直しなので、ペインを探す所だけ関数に切り出して、
そこを単体で試す。

day-6 に、Herdr のサーバーが応答してから前回のペインのシェルが生えるまでの数秒の間に
`start.sh` が「空いているシェルが無い」と早合点し、**ペインを割って Claude を2つ立てた**。
"""

import subprocess
import textwrap
from pathlib import Path

import pytest

START = Path(__file__).resolve().parents[1] / "start.sh"


def find_idle_pane(*, ready_after, panes='["p1"]', tries=6):
    """`find_idle_pane` だけを取り出して動かす。

    `herdr` と `pane_is_idle_shell` は、この中で作り替える（偽物にする）。
    `ready_after` 回目の呼び出しから「空いている」と答える。
    """
    body = subprocess.run(
        ["sed", "-n", "/^find_idle_pane()/,/^}/p", str(START)],
        capture_output=True, text=True, check=True).stdout
    assert body.strip(), "find_idle_pane が start.sh に無い"

    script = textwrap.dedent(f"""
        set -uo pipefail
        {body}
        COUNT_FILE=$(mktemp)
        echo 0 > "$COUNT_FILE"
        herdr() {{ printf '{{"result":{{"panes":[{{"tab_id":"t1","pane_id":"p1"}}]}}}}'; }}
        pane_is_idle_shell() {{
          n=$(cat "$COUNT_FILE"); n=$((n + 1)); echo "$n" > "$COUNT_FILE"
          [ "$n" -ge {ready_after} ]
        }}
        export FIND_IDLE_TRIES={tries} FIND_IDLE_WAIT=0.01
        if got=$(find_idle_pane ws t1); then echo "FOUND:$got"; else echo "NONE"; fi
        echo "TRIES:$(cat "$COUNT_FILE")"
    """)
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True).stdout
    return dict(line.split(":", 1) for line in out.strip().splitlines() if ":" in line)


def test_すぐ空いていればすぐ返す():
    got = find_idle_pane(ready_after=1)
    assert got["FOUND"] == "p1"
    assert got["TRIES"] == "1", "1回で見つかるなら待たない"


def test_あとから生えてきても見つける():
    """**これが #135 の本体。** 待たずに探すと、ここで空を返してペインを割っていた。"""
    got = find_idle_pane(ready_after=3)
    assert got.get("FOUND") == "p1", f"待たずに諦めた: {got}"
    assert int(got["TRIES"]) >= 3


def test_いつまでも空かなければ諦める():
    """全ペインで Claude が動いているときは、割るのが正しい。"""
    got = find_idle_pane(ready_after=999, tries=3)
    assert "FOUND" not in got
    assert got["TRIES"] == "3", "上限まで試してから諦める"


def test_startshの文法が通る():
    subprocess.run(["bash", "-n", str(START)], check=True)


def test_ペインを探す所で待つようになっている():
    """`find_idle_pane` を経由せずに探す書き方に戻っていないか。"""
    text = START.read_text(encoding="utf-8")
    assert "find_idle_pane" in text
    # 呼び出しは1か所（lead を起動するペインを選ぶ所）
    assert text.count("find_idle_pane") == 2, "定義1つと呼び出し1つのはず"
