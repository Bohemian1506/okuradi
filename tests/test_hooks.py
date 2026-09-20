"""`.claude/hooks/` のテスト（Claude を止める守り）。

この2つは「Claude がうっかり打った危ない git を、実行の前に止める」もの。
弱まっても気づきにくいので、止めるべきものと通すべきものを両方ここで守る。

day-4 に、ヒアストリング（`<<<foo`）をヒアドキュメントの始まりと読み違えて
**後ろの本物が素通りする**穴が見つかった。手で確かめたつもりが、別のブランチの
古い版を測っていて気づけなかった。以降はこのテストで確かめる。
"""

import json
import subprocess
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"

# フック自身が文字列に反応しないよう、危ない語はここで組み立てる
PUSH = "git " + "push"
MAIN = "m" + "ain"
HARD = "git reset " + "--hard"


def run(hook, command, cwd=None):
    """フックに1回の Bash 呼び出しを渡し、止めたかどうかを返す。"""
    proc = subprocess.run(
        [str(HOOKS / hook)],
        input=json.dumps({"tool_input": {"command": command}}, ensure_ascii=False),
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(cwd or Path.cwd())},
    )
    return proc.returncode != 0


@pytest.fixture
def main_repo(tmp_path):
    """main ブランチにいる使い捨てリポジトリ（送り先を省いた push の判定に要る）。"""
    subprocess.run(["git", "init", "-q", "-b", MAIN, str(tmp_path)], check=True)
    (tmp_path / "a").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "a"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.email=t@e.x",
                    "-c", "user.name=t", "commit", "-qm", "i"], check=True)
    return tmp_path


# ------------------------------------------------------------------ 止めるもの

@pytest.mark.parametrize("command", [
    f"{PUSH} origin {MAIN}",
    f"{PUSH} origin foo:{MAIN}",
    f"{PUSH} origin foo:refs/heads/{MAIN}",
    f"{PUSH} --no-verify origin {MAIN}",
    f"{PUSH} --all",
    f"{PUSH} --mirror",
    f"git status; {PUSH} origin {MAIN}",
    f"cd foo && {PUSH} origin {MAIN}",
])
def test_mainへのpushは止める(command, main_repo):
    assert run("block-main-push.sh", command, main_repo)


@pytest.mark.parametrize("command", [
    f"{HARD}",
    f"{HARD} origin/{MAIN}",
    f"git -C /somewhere reset --hard HEAD",
    f"git status; {HARD}",
    f"cd foo && {HARD} HEAD~1",
])
def test_hard_resetは止める(command):
    assert run("block-hard-reset.sh", command)


def test_mainにいるときは送り先を省いたpushも止める(main_repo):
    assert run("block-main-push.sh", PUSH, main_repo)
    assert run("block-main-push.sh", f"{PUSH} origin HEAD", main_repo)


# ------------------------------------------------------------------ 通すもの

@pytest.mark.parametrize("command", [
    f"{PUSH} -u origin docs/day-4",
    f"{PUSH} origin foo:bar",
    "git status --short",
    f'echo "{PUSH} origin {MAIN} は禁止"',
    f'grep -rn "{PUSH} origin {MAIN}" docs/',
])
def test_mainと関係ないpushは通す(command, main_repo):
    # 作業ブランチにいる状態にする（main にいると無指定 push が止まるため）
    subprocess.run(["git", "-C", str(main_repo), "switch", "-q", "-c", "feature/x"], check=True)
    assert not run("block-main-push.sh", command, main_repo)


@pytest.mark.parametrize("command", [
    "git reset --soft HEAD~1",
    "git reset HEAD ep01/config.yml",
    "git checkout -- ep01/config.yml",
    "git status --short",
    f'echo "{HARD} は使わない"',
])
def test_hard_resetでないものは通す(command):
    assert not run("block-hard-reset.sh", command)


# ---------------------------------------------- ヒアドキュメント（#108 の直し）

def test_ヒアドキュメントの中身は文字列なので通す(main_repo):
    subprocess.run(["git", "-C", str(main_repo), "switch", "-q", "-c", "feature/x"], check=True)
    assert not run("block-main-push.sh",
                   f"git commit -F - <<'MSG'\ndocs: 議事録\n\n{PUSH} origin {MAIN} の話。\nMSG",
                   main_repo)
    assert not run("block-hard-reset.sh",
                   f"git commit -F - <<'MSG'\ndocs: 議事録\n\n{HARD} の話。\nMSG")


@pytest.mark.parametrize("opener", ["<<EOF", "<<'EOF'", '<<"EOF"'])
def test_ヒアドキュメントの後ろにある本物は止める(opener, main_repo):
    assert run("block-main-push.sh",
               f"cat {opener} > a.txt\n本文\nEOF\n{PUSH} origin {MAIN}", main_repo)
    assert run("block-hard-reset.sh",
               f"cat {opener} > a.txt\n本文\nEOF\n{HARD}")


def test_字下げありのヒアドキュメントも読み飛ばす(main_repo):
    assert run("block-main-push.sh",
               f"cat <<-EOF > a.txt\n\t本文\n\tEOF\n{PUSH} origin {MAIN}", main_repo)


# ------------------------------------------------ ここから day-4 に見つけた穴

@pytest.mark.parametrize("here_string", ["<<<foo", '<<<"$var"', "<<<$var"])
def test_ヒアストリングの後ろにある本物は止める(here_string, main_repo):
    """`<<<` は1行で終わる。ヒアドキュメントの始まりと読み違えると、後ろが隠れる。"""
    assert run("block-main-push.sh",
               f"cat {here_string}\n{PUSH} origin {MAIN}", main_repo)
    assert run("block-hard-reset.sh", f"cat {here_string}\n{HARD}")


def test_区切り語が来ないヒアドキュメントでも本物は止める(main_repo):
    """書きかけ・読み違えで本文が閉じないとき、そこから先を全部隠してはいけない。"""
    assert run("block-main-push.sh", f"cat <<EOF\n{PUSH} origin {MAIN}", main_repo)
    assert run("block-hard-reset.sh", f"cat <<EOF\n{HARD}")


def test_2つのフックの読み飛ばしは同じ中身(main_repo):
    """片方だけ直して食い違うのを防ぐ。"""
    def strip_fn(name):
        lines = (HOOKS / name).read_text(encoding="utf-8").splitlines()
        start = next(i for i, x in enumerate(lines) if x.startswith("strip_heredocs() {"))
        end = next(i for i, x in enumerate(lines[start:], start) if x == "}")
        return lines[start:end + 1]

    assert strip_fn("block-main-push.sh") == strip_fn("block-hard-reset.sh")
