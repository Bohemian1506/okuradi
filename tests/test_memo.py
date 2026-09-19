"""web/memo.py のテスト（改善メモの下書きと、Issue への登録）。

本物の claude も gh も呼ばない。差し替えて確かめる。
**Issue を実際に作るのは、画面で下書きを確認したあとだけ**なので、
ここでは「どんな命令を組み立てるか」を見る。
"""

import json

import pytest

from web import chat, episodes, memo


@pytest.fixture
def ep(tmp_path, monkeypatch):
    ep_dir = tmp_path / "ep01"
    (ep_dir / "00_logs").mkdir(parents=True)
    (ep_dir / "config.yml").write_text("episode: 1\n", encoding="utf-8")
    monkeypatch.setattr(episodes, "resolve", lambda name, root=None: ep_dir)
    monkeypatch.setattr(episodes, "ROOT", tmp_path)
    return ep_dir


def write_chat(ep_dir, messages):
    (ep_dir / "00_logs" / "chat.json").write_text(
        json.dumps({"session": "s-1", "messages": messages}, ensure_ascii=False),
        encoding="utf-8")


# ---------------------------------------------------------------- 下書き

def test_会話が無ければ断る(ep):
    with pytest.raises(episodes.EpisodeError, match="まだ会話がありません"):
        memo.draft("ep01")


def test_会話を渡して下書きを作る(ep, monkeypatch):
    write_chat(ep, [{"who": "あなた", "text": "長い気がする"},
                    {"who": "Claude", "text": "02:14 で切れます"}])
    seen = {}

    def call(prompt, schema=None, **kwargs):
        seen["prompt"] = prompt
        seen["schema"] = schema
        return {"structured_output": {"title": " 短くする ", "body": " 理由 "}}

    monkeypatch.setattr(memo.build, "call_claude", call)
    got = memo.draft("ep01")

    assert "あなた: 長い気がする" in seen["prompt"]
    assert "Claude: 02:14 で切れます" in seen["prompt"]
    assert seen["schema"]["required"] == ["title", "body"]
    assert got == {"title": "短くする", "body": "理由", "label": "改善メモ"}


def test_claude_が失敗したら理由を言って断る(ep, monkeypatch):
    write_chat(ep, [{"who": "あなた", "text": "あ"}])

    def boom(*args, **kwargs):
        raise RuntimeError("claude が見つかりません")

    monkeypatch.setattr(memo.build, "call_claude", boom)
    with pytest.raises(episodes.EpisodeError, match="下書きを作れませんでした"):
        memo.draft("ep01")


# ---------------------------------------------------------------- 登録

class FakeRun:
    """subprocess.run の代わり。何を渡されたか覚えておく。"""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_タイトルが空なら登録しない(ep, monkeypatch):
    monkeypatch.setattr(memo, "has_label", lambda: True)
    with pytest.raises(episodes.EpisodeError, match="タイトル"):
        memo.create("ep01", "  ", "本文")


def test_gh_が無ければ理由を言って断る(ep, monkeypatch):
    monkeypatch.setattr(memo.shutil, "which", lambda name: None)
    with pytest.raises(episodes.EpisodeError, match="gh コマンドがありません"):
        memo.create("ep01", "題", "本文")


def test_ラベルが無ければ作り方を伝えて断る(ep, monkeypatch):
    monkeypatch.setattr(memo.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(memo, "has_label", lambda: False)
    with pytest.raises(episodes.EpisodeError, match="gh label create"):
        memo.create("ep01", "題", "本文")


def test_登録するとラベル付きで作られURLが返る(ep, monkeypatch):
    monkeypatch.setattr(memo.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(memo, "has_label", lambda: True)
    seen = {}

    def run(cmd, **kwargs):
        seen["cmd"] = cmd
        return FakeRun(stdout="https://github.com/x/y/issues/9\n")

    monkeypatch.setattr(memo.subprocess, "run", run)
    got = memo.create("ep01", "短くする", "理由")

    assert got["url"] == "https://github.com/x/y/issues/9"
    assert seen["cmd"][:3] == ["gh", "issue", "create"]
    assert "--label" in seen["cmd"] and "改善メモ" in seen["cmd"]
    body = seen["cmd"][seen["cmd"].index("--body") + 1]
    assert body.startswith("理由")
    assert "ep01 の相談から。" in body      # どの回の相談か残す


def test_gh_が失敗したら理由をそのまま伝える(ep, monkeypatch):
    monkeypatch.setattr(memo.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(memo, "has_label", lambda: True)
    monkeypatch.setattr(memo.subprocess, "run",
                        lambda cmd, **kw: FakeRun(returncode=1, stderr="権限がありません"))
    with pytest.raises(episodes.EpisodeError, match="権限がありません"):
        memo.create("ep01", "題", "本文")
