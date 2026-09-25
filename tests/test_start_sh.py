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


# ------------------------------------------ 最初の一言として /始め を送る（#194・#205）

def run_func(tmp_path, name, *, cont, mark, call):
    """start.sh から関数 `name` だけを取り出し、`call` を動かした結果を返す。"""
    body = subprocess.run(
        ["sed", "-n", f"/^{name}()/,/^}}/p", str(START)],
        capture_output=True, text=True, check=True).stdout
    assert body.strip(), f"{name} が start.sh に無い"
    if mark:
        (tmp_path / ".claude" / "state").mkdir(parents=True)
        (tmp_path / ".claude" / "state" / "作業終了").touch()
    script = f'set -uo pipefail\nROOT="{tmp_path}"\nCONTINUE="{"on" if cont else "off"}"\n{body}\n{call}'
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout


def lead_args(tmp_path, *, cont, mark):
    return run_func(tmp_path, "lead_args", cont=cont, mark=mark, call="lead_args").split()


def wants_hajime(tmp_path, *, cont, mark):
    out = run_func(tmp_path, "wants_hajime", cont=cont, mark=mark,
                   call="wants_hajime && echo yes || echo no")
    return out.strip() == "yes"


@pytest.mark.parametrize("cont", [False, True])
@pytest.mark.parametrize("mark", [False, True])
def test_起動の引数に始めを入れない(tmp_path, cont, mark):
    """渡すと Claude がすぐ作業を始め、Herdr が入力待ちを確かめられずに lead の名前を付けない（#205）。"""
    got = lead_args(tmp_path, cont=cont, mark=mark)
    assert "/始め" not in got
    assert got == (["--continue"] if cont else [])


@pytest.mark.parametrize("mark", [False, True])
def test_新しく起動したら始めを送る(tmp_path, mark):
    """起動の hook は知らせを渡すだけで、Claude は人の最初の一言を待つ（day-8 に分かった）。"""
    assert wants_hajime(tmp_path, cont=False, mark=mark)


def test_続きからで印が無ければ送らない(tmp_path):
    """作業の途中で開き直したとき。ここで送ると、作業の真っ最中に突き合わせが始まる。"""
    assert not wants_hajime(tmp_path, cont=True, mark=False)


def test_作業終了の印があれば続きからでも送る(tmp_path):
    assert wants_hajime(tmp_path, cont=True, mark=True)


def test_組み立てた引数をclaudeに渡している():
    """関数を作っても、呼び出しに使っていなければ効かない。"""
    text = START.read_text(encoding="utf-8")
    assert "< <(lead_args)" in text
    assert '--pane "$pane" "${args[@]}"' in text


def test_始めは名前が付いたあとでpromptで送る():
    """送るのは起動に成功した枝の中だけ。確認の画面で止まっているときに送ると、答えとして入ってしまう。"""
    text = START.read_text(encoding="utf-8")
    ok = text.index('say "$LEAD を起動しました"')
    not_ready = text.index("    agent_not_ready)")
    send = text.index('herdr agent prompt "$LEAD" "/始め"')
    assert text.count('herdr agent prompt "$LEAD"') == 1
    assert ok < send < not_ready
    assert "wants_hajime" in text[ok:send]


def test_名前の付いた作業のペインにはClaudeを置かない():
    """GUIログのペインは、サーバーを立てるまで「何も動いていないシェル」に見える。
    /作業終了 を通さずに閉じた翌朝、lead がそこ（14行）で起動してしまう（#194 で見つけた）。"""
    body = subprocess.run(
        ["sed", "-n", "/^find_idle_pane()/,/^}/p", str(START)],
        capture_output=True, text=True, check=True).stdout
    script = textwrap.dedent(f"""
        set -uo pipefail
        {body}
        herdr() {{ printf '{{"result":{{"panes":[{{"tab_id":"t1","pane_id":"pL","label":"GUIログ"}},{{"tab_id":"t1","pane_id":"p1"}}]}}}}'; }}
        pane_is_idle_shell() {{ true; }}
        export FIND_IDLE_TRIES=1 FIND_IDLE_WAIT=0.01
        find_idle_pane ws t1
    """)
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True).stdout
    assert out == "p1"


@pytest.mark.parametrize("cont,mark,expected", [
    (False, False, []),
    (False, True, []),
    (True, False, ["--continue"]),
    (True, True, ["--continue"]),
])
def test_claudeに渡る直前の引数を通しで見る(tmp_path, cont, mark, expected):
    """`lead_args` から `herdr agent start` の呼び出しまでを、**start.sh の実物の行**で通す（#198 のレビュー）。

    関数だけ試すと、組み立て方（`args=(--)`・`mapfile -O 1`）を変えたときの壊れ方に気づけない。
    `herdr` は偽物にして、受け取った引数を1行に1つ返させる。
    """
    text = START.read_text(encoding="utf-8")
    func = subprocess.run(["sed", "-n", "/^lead_args()/,/^}/p", str(START)],
                          capture_output=True, text=True, check=True).stdout
    lines = [l.strip() for l in text.splitlines()]
    build = [l for l in lines if l in ("args=(--)", "mapfile -t -O 1 args < <(lead_args)")]
    call = [l for l in lines if l.startswith('out=$(herdr agent start "$LEAD"')]
    assert len(build) == 2 and len(call) == 1, "組み立てと呼び出しの行が見つからない"
    if mark:
        (tmp_path / ".claude" / "state").mkdir(parents=True)
        (tmp_path / ".claude" / "state" / "作業終了").touch()
    script = "\n".join([
        "set -uo pipefail",
        f'ROOT="{tmp_path}"', f'CONTINUE="{"on" if cont else "off"}"', 'LEAD=lead', 'pane=p1',
        "herdr() { printf '%s\\n' \"$@\"; }",
        func, *build, *call, 'printf "%s" "$out"',
    ])
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout
    got = out.splitlines()
    assert got[:6] == ["agent", "start", "lead", "--kind", "claude", "--pane"]
    assert got[7] == "--", "claude への引数は -- のあと"
    assert got[8:] == expected
