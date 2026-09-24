"""`.claude/hooks/` のテスト（Claude を止める守り）。

この2つは「Claude がうっかり打った危ない git を、実行の前に止める」もの。
弱まっても気づきにくいので、止めるべきものと通すべきものを両方ここで守る。

day-4 に、ヒアストリング（`<<<foo`）をヒアドキュメントの始まりと読み違えて
**後ろの本物が素通りする**穴が見つかった。手で確かめたつもりが、別のブランチの
古い版を測っていて気づけなかった。以降はこのテストで確かめる。
"""

import json
import shutil
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


# ------------------------------------------------------ 行末の CRLF（#112）

@pytest.mark.parametrize("tail", ["\r\n", "\r"])
def test_行末がCRLFでも本物は止める(tail, main_repo):
    """Windows 側から貼り付けた文字列が混ざると、行末に \r が付くことがある。

    `\r` は空白ではないので語にくっついたままになり、比較が外れて素通りしていた。
    """
    assert run("block-main-push.sh", f"{PUSH} origin {MAIN}{tail}", main_repo)
    assert run("block-hard-reset.sh", f"{HARD}{tail}")


def test_CRLFのヒアドキュメントでも中身は通し後ろは止める(main_repo):
    assert run("block-main-push.sh",
               f"cat <<EOF > a.txt\r\n本文\r\nEOF\r\n{PUSH} origin {MAIN}\r\n", main_repo)
    subprocess.run(["git", "-C", str(main_repo), "switch", "-q", "-c", "feature/x"], check=True)
    assert not run("block-main-push.sh",
                   f"git commit -F - <<'MSG'\r\n{PUSH} origin {MAIN} の話。\r\nMSG\r\n", main_repo)


# ------------------------------------------- 始まるときの状態出し（SessionStart）

def run_status(cwd, with_gh=True):
    """SessionStart の hook を走らせ、(終了コード, 出たもの) を返す。"""
    path = "/usr/bin:/bin" if with_gh else str(cwd / "nogh")
    if not with_gh:
        (cwd / "nogh").mkdir(exist_ok=True)
        for name in ("git", "python3"):
            src = shutil.which(name)
            if src:
                (cwd / "nogh" / name).symlink_to(src)
    proc = subprocess.run([str(HOOKS / "session-start-status.py")],
                          capture_output=True, text=True, cwd=str(cwd),
                          env={"PATH": path, "HOME": str(cwd)})
    return proc.returncode, proc.stdout


def test_始まるときの状態出しはgitの外でも止まらない(tmp_path):
    """セッションの開始を妨げてはいけない。"""
    code, out = run_status(tmp_path)
    assert code == 0
    if out.strip():
        json.loads(out)          # 出すなら、壊れていない JSON


def test_始まるときの状態出しはghが無くても止まらない(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    code, out = run_status(tmp_path, with_gh=False)
    assert code == 0
    assert out.strip(), "gh が無くても、手元の状態は出す"
    d = json.loads(out)
    assert d["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "ブランチ" in d["hookSpecificOutput"]["additionalContext"]


def test_始まるときの状態出しは未コミットの変更を知らせる(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    code, out = run_status(tmp_path, with_gh=False)
    assert code == 0
    assert "コミットしていない変更がある" in json.loads(out)["hookSpecificOutput"]["additionalContext"]


# ---------------------------------------------------------------- 議事録の知らせ（day-6）

MERGE = "gh pr " + "merge"


def run_remind(command):
    """議事録の hook を1回走らせる。"""
    return subprocess.run(
        [str(HOOKS / "remind-devlog.sh")],
        input=json.dumps({"tool_input": {"command": command}}, ensure_ascii=False),
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(Path.cwd())},
    )


def remind(command):
    """議事録の知らせが出たかどうか。**止めないので、終了コードではなく中身で見る。**

    **stdout の JSON を見る。** day-6 の最初の版は stderr に文字を出していて、
    **2日間ずっと誰にも届いていなかった**のに、ここが `proc.stderr` を見ていたので
    **テストは緑のままだった**（#188）。
    """
    proc = run_remind(command)
    assert proc.returncode == 0, "知らせるだけの hook なので、止めてはいけない"
    if not proc.stdout.strip():
        return False
    d = json.loads(proc.stdout)        # 壊れた JSON なら、ここで落ちる
    assert d["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    return "議事録" in d["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize("command", [
    f"{MERGE} 150 --merge",
    f"git switch main && {MERGE} 12 --squash",
    f"echo ok\n{MERGE} 3",
])
def test_マージしたら議事録を知らせる(command):
    assert remind(command)


@pytest.mark.parametrize("command", [
    "gh pr view 150",
    'gh pr create --base main --title "x"',
    "ls -la",
    "gh issue comment 79 --body x",
])
def test_マージでないものには黙る(command):
    assert not remind(command)


def test_ヒアドキュメントの中身は文字列なので黙る():
    """PR 本文に書いただけで知らせが出ると、うるさくて読まれなくなる。"""
    assert not remind(f'gh pr create --body "$(cat <<EOF\n{MERGE} のことを説明する文章\nEOF\n)"')


def test_コミットメッセージに書いただけでは黙る():
    assert not remind(f'git commit -m "{MERGE} のルールを直す"')


def test_知らせはstdoutに出す():
    """**stderr に出すと、終了コード 0 ではどこにも表示されない**（#188）。

    day-6 の最初の版はここで消えていた。**作ったことと、届いたことは別。**
    """
    proc = run_remind(f"{MERGE} 1 --merge")
    assert proc.stdout.strip(), "知らせは stdout に出す"
    assert "議事録" not in proc.stderr, "stderr に出すと、誰にも届かない"


def test_止めない():
    """CLAUDE.md に「経緯を残すほどでない PR は省いてよい」とある。

    機械が一律に止めると、省いてよい場面まで止まる。**知らせるだけにする。**
    """
    proc = subprocess.run(
        [str(HOOKS / "remind-devlog.sh")],
        input=json.dumps({"tool_input": {"command": f"{MERGE} 1"}}, ensure_ascii=False),
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(Path.cwd())},
    )
    assert proc.returncode == 0


# ------------------------------------------- 起動のときだけ `/始め` を促す（#180）

def run_begin(source, raw=None):
    """SessionStart の入力を渡し、(終了コード, 出たもの) を返す。"""
    payload = raw if raw is not None else json.dumps(
        {"hook_event_name": "SessionStart", "source": source}, ensure_ascii=False)
    proc = subprocess.run([str(HOOKS / "session-start-begin.py")],
                          input=payload, capture_output=True, text=True)
    return proc.returncode, proc.stdout


def test_起動のときは始めの手順を渡す():
    code, out = run_begin("startup")
    assert code == 0
    d = json.loads(out)
    assert d["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "始め" in d["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize("source", ["resume", "compact", "clear", "知らない値"])
def test_起動以外では黙る(source):
    """要約（compact）でも走る。ここで出すと、作業の真っ最中に始まってしまう。

    知らない値でも出さない。出しすぎる側に倒れると、作業を邪魔する。
    """
    code, out = run_begin(source)
    assert code == 0
    assert out.strip() == ""


@pytest.mark.parametrize("raw", ["", "これは JSON ではない", "{}", "null"])
def test_入力が壊れていてもセッションを止めない(raw):
    code, out = run_begin(None, raw=raw)
    assert code == 0
    assert out.strip() == ""


def test_渡す手順の正本がある():
    """hook は手順を写さず、場所だけを指す。指す先が消えたら気づけるようにする。"""
    assert (HOOKS.parent / "commands" / "始め.md").exists()
    text = (HOOKS / "session-start-begin.py").read_text(encoding="utf-8")
    assert "commands/始め.md" in text


def test_起動の促しがsettingsに登録してある():
    """ファイルがあっても、設定に載っていなければ動かない（静かに効かなくなる）。"""
    settings = json.loads((HOOKS.parent / "settings.json").read_text(encoding="utf-8"))
    commands = [h["command"]
                for group in settings["hooks"]["SessionStart"]
                for h in group["hooks"]]
    assert any("session-start-begin.py" in c for c in commands)
