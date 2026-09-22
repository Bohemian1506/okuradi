"""壊れると取り返しがつかない約束を、テストで守る。

議事録の day-3 に「『安全にしてある』と書いたら、それを守るテストまで書く」とある
（#58 と #63 で2回やった）。ここはその3回目になりかけていた所。

- Claude はサブスクの枠で呼ぶ（API キーが混ざると従量課金になり、実費が出る）
- 認証情報と音声は git に入れない（公開リポジトリ）

どちらも仕組みは前からあったが、守るテストが無く、消しても何も落ちなかった。
"""

import os
import subprocess
from pathlib import Path

import pytest

import build


ROOT = Path(build.__file__).resolve().parent


# ---------------------------------------------------------------- サブスクの枠で呼ぶ

def test_claudeを呼ぶときにAPIキーを環境から外す(monkeypatch):
    """API キーが残っていると、サブスクではなく従量課金で呼ばれる（build.py の env）。"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ずっと残っていてはいけない値")
    seen = {}

    def fake_run(cmd, **kw):
        seen["env"] = kw["env"]
        return subprocess.CompletedProcess(cmd, 0, stdout='{"result": "ok"}', stderr="")

    monkeypatch.setattr(build.subprocess, "run", fake_run)
    build.call_claude("あ")

    assert "ANTHROPIC_API_KEY" not in seen["env"]
    # 他の環境変数は渡す（PATH が無いと claude 自体が見つからない）
    assert seen["env"].get("PATH") == os.environ.get("PATH")


def test_APIキーが無いときも呼べる(monkeypatch):
    """外す処理が、キーが無い環境で落ちないこと。"""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(build.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(
        cmd, 0, stdout='{"result": "ok"}', stderr=""))
    assert build.call_claude("あ") == {"result": "ok"}


# ---------------------------------------------------------------- git に入れないもの

def _ignored(path):
    """git がそのパスを無視するか。管理外なら True。"""
    return subprocess.run(["git", "check-ignore", "-q", path],
                          cwd=ROOT, capture_output=True).returncode == 0


@pytest.mark.parametrize("path", ["client_secret.json", "token.json", "settings.yml"])
def test_認証情報と機械ごとの設定はgitの管理外(path):
    assert _ignored(path), f"{path} が .gitignore から外れている"


@pytest.mark.parametrize("path", [
    "ep01/00_raw/収録.wav",
    "ep01/01_clean/clean.wav",
    "ep01/02_text/transcript.json",
    "ep01/04_video/ep01.mp4",
    "ep99/00_logs/chat.json",
])
def test_回の音声と途中のファイルはgitの管理外(path):
    assert _ignored(path), f"{path} が .gitignore から外れている"


def test_回のフォルダで追跡しているのは設定ファイルだけ():
    """音声を1つでもコミットしたら、ここで落ちる。

    **`timeline.yml` も git で追跡すると決めた**（2026-09-22・#144）。
    まだどの回にも無いので、いまは `config.yml` だけが並ぶ。
    """
    out = subprocess.run(["git", "ls-files", "ep01/"],
                         cwd=ROOT, capture_output=True, text=True, check=True)
    assert set(out.stdout.split()) <= {"ep01/config.yml", "ep01/timeline.yml"}
    assert "ep01/config.yml" in out.stdout.split()


def test_タイムラインはgitの管理下に置く():
    """`timeline.yml` を `.gitignore` に足さない（2026-09-22 に決めた・#144）。

    どこをカットしたか・どこにエコーをかけたかは、**消えたら手で作り直せない**。
    音声や中間ファイルとは性質が違うので、git で守る。
    """
    assert not _ignored("ep01/timeline.yml"), \
        "timeline.yml が .gitignore に入っている（追跡すると決めた）"
