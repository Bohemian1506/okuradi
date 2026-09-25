"""`.claude/hooks/` のテスト（Claude を止める守り）。

この2つは「Claude がうっかり打った危ない git を、実行の前に止める」もの。
弱まっても気づきにくいので、止めるべきものと通すべきものを両方ここで守る。

day-4 に、ヒアストリング（`<<<foo`）をヒアドキュメントの始まりと読み違えて
**後ろの本物が素通りする**穴が見つかった。手で確かめたつもりが、別のブランチの
古い版を測っていて気づけなかった。以降はこのテストで確かめる。
"""

import json
import re
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

def run_begin(project_dir, source, raw=None):
    """SessionStart の入力を渡し、(終了コード, 出たもの) を返す。

    **必ず `CLAUDE_PROJECT_DIR` を渡す。** 渡さないと、hook はスクリプトの位置から
    見た本物のリポジトリを見に行く。手元に `.claude/state/作業終了` があると、
    そちらを拾って「resume で黙る」テストが崩れる（#183）。
    """
    payload = raw if raw is not None else json.dumps(
        {"hook_event_name": "SessionStart", "source": source}, ensure_ascii=False)
    proc = subprocess.run([str(HOOKS / "session-start-begin.py")],
                          input=payload, capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(project_dir)})
    return proc.returncode, proc.stdout


def test_起動のときは始めの手順を渡す(tmp_path):
    code, out = run_begin(tmp_path, "startup")
    assert code == 0
    d = json.loads(out)
    assert d["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    ctx = d["hookSpecificOutput"]["additionalContext"]
    assert "始め" in ctx
    assert "起動" in ctx


@pytest.mark.parametrize("source", ["resume", "compact", "clear", "知らない値"])
def test_起動以外では黙る(source, tmp_path):
    """要約（compact）でも走る。ここで出すと、作業の真っ最中に始まってしまう。

    知らない値でも出さない。出しすぎる側に倒れると、作業を邪魔する。
    `resume` は印（`.claude/state/作業終了`）が無い場合の話（印があるときは #183 で別）。
    """
    code, out = run_begin(tmp_path, source)
    assert code == 0
    assert out.strip() == ""


@pytest.mark.parametrize("raw", ["", "これは JSON ではない", "{}", "null"])
def test_入力が壊れていてもセッションを止めない(raw, tmp_path):
    code, out = run_begin(tmp_path, None, raw=raw)
    assert code == 0
    assert out.strip() == ""


# --------------------------- `/作業終了` の印があれば resume でも促す（#183）

def mark_path(project_dir):
    return project_dir / ".claude" / "state" / "作業終了"


def put_mark(project_dir):
    p = mark_path(project_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("", encoding="utf-8")
    return p


def test_印があればresumeでも始めを促す(tmp_path):
    put_mark(tmp_path)
    code, out = run_begin(tmp_path, "resume")
    assert code == 0
    d = json.loads(out)
    ctx = d["hookSpecificOutput"]["additionalContext"]
    assert "続きから" in ctx
    assert "始め" in ctx


def test_促したら印を消す(tmp_path):
    put_mark(tmp_path)
    run_begin(tmp_path, "resume")
    assert not mark_path(tmp_path).exists()


def test_startupは印の有無に関係なく出し印があれば消す(tmp_path):
    put_mark(tmp_path)
    code, out = run_begin(tmp_path, "startup")
    assert code == 0
    assert "起動" in json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert not mark_path(tmp_path).exists(), "出したら印は消す"


def test_startupは印が無くても出る(tmp_path):
    code, out = run_begin(tmp_path, "startup")
    assert code == 0
    assert "起動" in json.loads(out)["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize("source", ["compact", "clear", "知らない値"])
def test_compactやclearは印があっても出さず印も消さない(source, tmp_path):
    """作業の途中で起きるものなので、印があっても割り込まない。印は次の resume のために残す。"""
    put_mark(tmp_path)
    code, out = run_begin(tmp_path, source)
    assert code == 0
    assert out.strip() == ""
    assert mark_path(tmp_path).exists(), "出さないときは印を消してはいけない"


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


# ------------------------------------------- 「変更」ペインへの差分の書き出し（#183）

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def run_show_diff(project_dir, data):
    """PostToolUse の入力を渡し、(終了コード, 書き出したファイルの中身 or None) を返す。"""
    proc = subprocess.run([str(HOOKS / "show-diff.py")],
                          input=json.dumps(data, ensure_ascii=False),
                          capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(project_dir)})
    out = project_dir / ".claude" / "state" / "変更.txt"
    return proc.returncode, (ANSI.sub("", out.read_text(encoding="utf-8")) if out.exists() else None)


def test_structuredPatchの行番号がそのまま出る(tmp_path):
    """本物のパッチがあれば、そちらを信じる（予備の作り方で作り直さない）。"""
    data = {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(tmp_path / "a.txt")},
        "tool_response": {"structuredPatch": [
            {"oldStart": 10, "oldLines": 2, "newStart": 10, "newLines": 3,
             "lines": [" 変わらない行", "+増えた行", " もう1行"]},
        ]},
    }
    code, content = run_show_diff(tmp_path, data)
    assert code == 0
    assert "@@ -10,2 +10,3 @@" in content
    assert "+増えた行" in content


def test_structuredPatchが無ければ予備の作り方でプラスマイナスが出る(tmp_path):
    data = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(tmp_path / "a.txt"),
            "old_string": "前\n",
            "new_string": "後\n",
        },
    }
    code, content = run_show_diff(tmp_path, data)
    assert code == 0
    assert "-前" in content
    assert "+後" in content


def test_structuredPatchが空リストでも予備の作り方に回る(tmp_path):
    """`structuredPatch: []` は「無い」と同じ扱いにする（存在チェックだけだと空リストで空振りする）。"""
    data = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(tmp_path / "a.txt"),
            "old_string": "前\n",
            "new_string": "後\n",
        },
        "tool_response": {"structuredPatch": []},
    }
    code, content = run_show_diff(tmp_path, data)
    assert code == 0
    assert "-前" in content
    assert "+後" in content


def test_MultiEditも予備の作り方でプラスマイナスが出る(tmp_path):
    data = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": str(tmp_path / "a.txt"),
            "edits": [
                {"old_string": "あ\n", "new_string": "い\n"},
                {"old_string": "う\n", "new_string": "え\n"},
            ],
        },
    }
    code, content = run_show_diff(tmp_path, data)
    assert code == 0
    assert "-あ" in content and "+い" in content
    assert "-う" in content and "+え" in content


def test_Writeで新規ファイルの中身は出さずN行とだけ書く(tmp_path):
    """新規ファイルは structuredPatch が無い。中身をそのまま出すと、秘密がペインに映る。"""
    data = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(tmp_path / "secret.txt"),
            "content": "SECRET_TOKEN=abcdef\n2行目\n3行目",
        },
    }
    code, content = run_show_diff(tmp_path, data)
    assert code == 0
    assert "SECRET_TOKEN" not in content
    assert "3行" in content


def test_EditWriteMultiEdit以外は何もしない(tmp_path):
    data = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
    code, content = run_show_diff(tmp_path, data)
    assert code == 0
    assert content is None, "対象外のツールでファイルを作ってはいけない"


@pytest.mark.parametrize("raw", ["", "これは JSON ではない", "{}", "null",
                                  '{"tool_name": "Edit"}'])
def test_壊れた入力でも終了コードは0(tmp_path, raw):
    proc = subprocess.run([str(HOOKS / "show-diff.py")],
                          input=raw, capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(tmp_path)})
    assert proc.returncode == 0


def test_パスはリポジトリ相対で1行目に書く(tmp_path):
    data = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(tmp_path / "ep01" / "config.yml"),
            "old_string": "a",
            "new_string": "b",
        },
    }
    code, content = run_show_diff(tmp_path, data)
    assert code == 0
    head = content.splitlines()[0]
    assert "ep01/config.yml" in head
    assert str(tmp_path) not in head, "見せるのは相対パス（フルパスは長くて読みにくい）"
    assert "Edit" in head


def test_show_diffがsettingsに登録してある():
    """ファイルがあっても、設定に載っていなければ動かない。"""
    settings = json.loads((HOOKS.parent / "settings.json").read_text(encoding="utf-8"))
    commands = [h["command"]
                for group in settings["hooks"]["PostToolUse"]
                for h in group["hooks"]]
    assert any("show-diff.py" in c for c in commands)


# ------------------------------------------------------- 作業ペイン.sh（#183）

SCRIPTS = Path(__file__).resolve().parents[1] / ".claude" / "scripts"


@pytest.mark.parametrize("sub", [[], ["open"], ["gui"], ["close"]])
def test_herdrの外では何もせず1行出して終わる(sub, tmp_path):
    """この開発環境自体が Herdr の中で動くので、HERDR_ENV をわざと外して確かめる。

    **本物の herdr は絶対に呼ばない**（herdr をあえて PATH から外し、呼んだら失敗するようにする）。
    """
    proc = subprocess.run(
        [str(SCRIPTS / "作業ペイン.sh"), *sub],
        capture_output=True, text=True, cwd=str(tmp_path),
        env={"PATH": "/usr/bin:/bin"},   # HERDR_ENV は渡さない。herdr も置かない
    )
    assert proc.returncode == 0
    assert "Herdr の外" in proc.stdout


def test_herdr_envが1でなければ同じく何もしない(tmp_path):
    proc = subprocess.run(
        [str(SCRIPTS / "作業ペイン.sh")],
        capture_output=True, text=True, cwd=str(tmp_path),
        env={"PATH": "/usr/bin:/bin", "HERDR_ENV": "0"},
    )
    assert proc.returncode == 0
    assert "Herdr の外" in proc.stdout


def test_印を消せなくても促しは出す(tmp_path):
    """消すのは後片付け。**消せないせいで促しまで消えると、この hook の目的を裏切る**（#193 のレビュー）。"""
    mark = put_mark(tmp_path)
    mark.parent.chmod(0o555)          # 親の書き込み権を外すと、消せなくなる
    try:
        code, out = run_begin(tmp_path, "startup")
    finally:
        mark.parent.chmod(0o755)
    assert code == 0
    assert "始め" in json.loads(out)["hookSpecificOutput"]["additionalContext"]


# ------------------------------------ 作業ペイン.sh を偽の herdr で動かす（#193 のレビュー）

FAKE_HERDR = r'''#!/usr/bin/env bash
# 本物の herdr の代わり。呼ばれた引数を記録し、決めておいた答えを返す
echo "$*" >> "$FAKE_DIR/calls"
case "$1 $2" in
  "pane current") echo '{"result":{"pane":{"tab_id":"t1"}}}' ;;
  "pane list")
    [ -f "$FAKE_DIR/list_fails" ] && exit 1
    echo '{"result":{"panes":[
      {"pane_id":"p1","tab_id":"t1"},
      {"pane_id":"pD","tab_id":"t1","label":"変更"},
      {"pane_id":"pL","tab_id":"t1","label":"GUIログ"},
      {"pane_id":"pT","tab_id":"t1","label":"今日の一手"}]}}' ;;
  "pane process-info")
    if [ "$4" = "pL" ] && [ -f "$FAKE_DIR/gui_busy" ]; then
      echo '{"result":{"process_info":{"shell_pid":1,"foreground_processes":[{"pid":1,"name":"bash"},{"pid":2,"name":"python"}]}}}'
    else
      echo '{"result":{"process_info":{"shell_pid":1,"foreground_processes":[{"pid":1,"name":"bash"}]}}}'
    fi ;;
  *) echo '{"result":{}}' ;;
esac
'''


def run_panes(tmp_path, *args, gui_busy=False, list_fails=False):
    """偽の herdr を PATH の先頭に置いて 作業ペイン.sh を動かし、(proc, 呼ばれた herdr の一覧) を返す。"""
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "herdr").write_text(FAKE_HERDR, encoding="utf-8")
    (fake / "herdr").chmod(0o755)
    if gui_busy:
        (tmp_path / "gui_busy").touch()
    if list_fails:
        (tmp_path / "list_fails").touch()
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    proc = subprocess.run(
        [str(SCRIPTS / "作業ペイン.sh"), *args],
        capture_output=True, text=True, cwd=str(repo),
        env={"PATH": f"{fake}:/usr/bin:/bin", "HERDR_ENV": "1", "FAKE_DIR": str(tmp_path)},
    )
    calls = (tmp_path / "calls").read_text(encoding="utf-8").splitlines() \
        if (tmp_path / "calls").exists() else []
    return proc, calls


def test_GUIログで何か動いていたらどれも閉じない(tmp_path):
    """GUI のサーバーごと閉じると、裏の工程（build.py は別のプロセスグループ）が取り残され、
    作りかけのファイルを消す後片付けも走らない（#193 のレビュー・`web/runner.py`）。"""
    proc, calls = run_panes(tmp_path, "close", gui_busy=True)
    assert proc.returncode == 3
    assert "閉じなかった" in proc.stdout
    assert not [c for c in calls if c.startswith("pane close")]


def test_GUIログが空なら3つとも閉じる(tmp_path):
    proc, calls = run_panes(tmp_path, "close")
    assert proc.returncode == 0
    assert sorted(c for c in calls if c.startswith("pane close")) == \
        ["pane close pD", "pane close pL", "pane close pT"]


@pytest.mark.parametrize("sub", ["open", "gui", "close"])
def test_ペインの一覧が取れなければ触らない(sub, tmp_path):
    """失敗を「ペインが無い」と読むと、二重に作る・二重に立てる（#193 のレビュー）。"""
    proc, calls = run_panes(tmp_path, sub, list_fails=True)
    assert proc.returncode == 0
    assert "取れなかった" in proc.stdout
    assert not [c for c in calls if c.split()[:2] in (["pane", "split"], ["pane", "close"], ["pane", "run"])]
