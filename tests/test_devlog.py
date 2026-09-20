"""`docs/dev-log/day-stats.sh` のテスト（議事録の冒頭を測るコマンド）。

これが黙って壊れると、また手で数えて、また前の版から写す。
day-4 に、朝書いた「実装らしい実装はしていない日」を夕方まで残した。
"""

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "docs" / "dev-log" / "day-stats.sh"


def git(repo, *args, **kw):
    return subprocess.run(["git", "-C", str(repo)] + list(args),
                          capture_output=True, text=True, check=True, **kw)


@pytest.fixture
def repo(tmp_path):
    """1日ぶんのコミットがある使い捨てリポジトリ。"""
    git(tmp_path.parent, "init", "-q", str(tmp_path))
    (tmp_path / "docs").mkdir()
    (tmp_path / "最初.txt").write_text("x\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "-c", "user.email=t@e.x", "-c", "user.name=t",
        "commit", "-qm", "はじめ", env={"GIT_AUTHOR_DATE": "2026-01-01T09:00:00",
                                         "GIT_COMMITTER_DATE": "2026-01-01T09:00:00",
                                         "PATH": "/usr/bin:/bin", "HOME": str(tmp_path)})
    return tmp_path


def run_stats(repo, day):
    return subprocess.run([str(SCRIPT), day], capture_output=True, text=True,
                          cwd=str(repo))


def add_commit(repo, name, body, day):
    (repo / name).parent.mkdir(parents=True, exist_ok=True)
    (repo / name).write_text(body, encoding="utf-8")
    git(repo, "add", "-A")
    stamp = f"{day}T12:00:00"
    git(repo, "-c", "user.email=t@e.x", "-c", "user.name=t", "commit", "-qm", name,
        env={"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp,
             "PATH": "/usr/bin:/bin", "HOME": str(repo)})


def test_コミットが無い日は何もないと言う(repo):
    out = run_stats(repo, "2026-02-02")
    assert out.returncode == 0
    assert "コミットはありません" in out.stdout


def test_コードと文書を分けて数える(repo):
    add_commit(repo, "web/app.py", "\n".join(f"line{i}" for i in range(10)) + "\n",
               "2026-02-03")
    add_commit(repo, "docs/note.md", "\n".join(f"行{i}" for i in range(3)) + "\n",
               "2026-02-03")
    out = run_stats(repo, "2026-02-03")
    assert out.returncode == 0, out.stderr
    assert "10 insertions" in out.stdout, "コード側の行数が出ていない"
    assert "3 insertions" in out.stdout, "文書側の行数が出ていない"


def test_claudeの中のmdは道具として数える(repo):
    """`.claude/commands/*.md` は文書ではなく道具。文書側に入れない。"""
    add_commit(repo, ".claude/commands/なにか.md", "a\nb\nc\n", "2026-02-04")
    out = run_stats(repo, "2026-02-04")
    assert out.returncode == 0, out.stderr
    code_line = [l for l in out.stdout.splitlines() if l.startswith("それ以外")][0]
    doc_line = [l for l in out.stdout.splitlines() if l.startswith("文書")][0]
    assert "3 insertions" in code_line
    assert "変更なし" in doc_line


def test_日本語のファイル名も読める(repo):
    """core.quotepath でエスケープされると行数が取れなくなる。"""
    add_commit(repo, "区切り.sh", "a\nb\n", "2026-02-05")
    out = run_stats(repo, "2026-02-05")
    assert out.returncode == 0, out.stderr
    assert "区切り.sh" in out.stdout
    assert "2行" in out.stdout
