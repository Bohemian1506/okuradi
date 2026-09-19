"""web/chat.py のテスト（相談チャット）。

本物の claude は呼ばない（課金と時間がかかるため）。差し替えて確かめる。
"""

import json

import pytest

from web import chat, episodes


@pytest.fixture
def ep(tmp_path, monkeypatch):
    ep_dir = tmp_path / "ep01"
    for sub in ["00_logs", "02_text"]:
        (ep_dir / sub).mkdir(parents=True)
    (ep_dir / "config.yml").write_text(
        "episode: 1\nconcept: 番組の芯\n"
        "segments:\n- series: imasara\n  theme: OSI\n"
        "series_rules:\n  imasara:\n    label: 今更聞けない\n",
        encoding="utf-8")
    monkeypatch.setattr(episodes, "resolve", lambda name, root=None: ep_dir)
    return ep_dir


def write_text_file(ep_dir, which, rows):
    (ep_dir / "02_text" / which).write_text(
        json.dumps({"segments": rows}, ensure_ascii=False), encoding="utf-8")


def fake_claude(monkeypatch, answer="わかりました", session="s-1"):
    """claude の代わり。渡されたプロンプトを覚えておく。"""
    seen = {}

    def call(prompt, schema=None, system=None, resume=None, persist=False):
        seen["prompt"] = prompt
        seen["system"] = system
        seen["resume"] = resume
        seen["persist"] = persist
        return {"result": answer, "session_id": session}

    monkeypatch.setattr(chat.build, "call_claude", call)
    return seen


# ---------------------------------------------------------------- 読んでいるもの

def test_文字起こしが無ければ文字起こしなし(ep):
    assert chat.read_chat("ep01")["reading"] == "文字起こしなし"


def test_下見しかなければ下見(ep):
    write_text_file(ep, "scan.json", [{"start": 0, "text": "あ"}])
    assert chat.read_chat("ep01")["reading"] == "下見"


def test_確定版があれば確定版(ep):
    write_text_file(ep, "scan.json", [{"start": 0, "text": "あ"}])
    write_text_file(ep, "transcript.json", [{"start": 0, "text": "い"}])
    assert chat.read_chat("ep01")["reading"] == "確定版"


def test_中身が空なら次を見る(ep):
    write_text_file(ep, "transcript.json", [])
    write_text_file(ep, "scan.json", [{"start": 0, "text": "あ"}])
    assert chat.read_chat("ep01")["reading"] == "下見"


# ---------------------------------------------------------------- 会話

def test_1回目は材料を渡す(ep, monkeypatch):
    write_text_file(ep, "scan.json", [{"start": 12.0, "text": "こんばんは"}])
    seen = fake_claude(monkeypatch)
    chat.ask("ep01", "どこで切れそう？")

    assert seen["persist"] is True and seen["resume"] is None
    assert "番組の芯" in seen["prompt"]
    assert "今更聞けない" in seen["prompt"]
    assert "[0:12] こんばんは" in seen["prompt"]      # 時刻つきで渡す
    assert "どこで切れそう？" in seen["prompt"]


def test_2回目は材料を渡し直さない(ep, monkeypatch):
    write_text_file(ep, "scan.json", [{"start": 0, "text": "あ"}])
    seen = fake_claude(monkeypatch)
    chat.ask("ep01", "1つ目")
    chat.ask("ep01", "2つ目")

    assert seen["resume"] == "s-1"
    assert seen["prompt"] == "2つ目"                 # 質問だけ


def test_会話は残って続きから見える(ep, monkeypatch):
    fake_claude(monkeypatch, answer="はい")
    chat.ask("ep01", "聞きたいこと")
    got = chat.read_chat("ep01")
    assert [m["who"] for m in got["messages"]] == ["あなた", "Claude"]
    assert got["messages"][1]["text"] == "はい"
    assert got["session"] == "s-1"


def test_リセットすると会話が消える(ep, monkeypatch):
    fake_claude(monkeypatch)
    chat.ask("ep01", "あ")
    assert chat.reset("ep01")["messages"] == []
    assert chat.read_chat("ep01")["session"] is None


def test_空の質問は断る(ep):
    with pytest.raises(episodes.EpisodeError, match="聞きたいこと"):
        chat.ask("ep01", "   ")


def test_claude_が失敗したら理由を言って断る(ep, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("claude コマンドが見つかりません")
    monkeypatch.setattr(chat.build, "call_claude", boom)
    with pytest.raises(episodes.EpisodeError, match="Claude に聞けませんでした"):
        chat.ask("ep01", "あ")


def test_文字起こしが無くても聞ける(ep, monkeypatch):
    seen = fake_claude(monkeypatch)
    chat.ask("ep01", "あ")
    assert "まだ文字起こしがありません" in seen["prompt"]


def test_会話の記録が壊れていても落ちない(ep, monkeypatch):
    (ep / "00_logs" / "chat.json").write_text("{壊れた", encoding="utf-8")
    got = chat.read_chat("ep01")
    assert got["messages"] == [] and got["session"] is None


# ---------------------------------------------------------------- 読んでいるものの取り違え

def test_会話を始めた版を覚えておく(ep, monkeypatch):
    write_text_file(ep, "scan.json", [{"start": 0, "text": "あ"}])
    fake_claude(monkeypatch)
    chat.ask("ep01", "質問")
    assert chat.read_chat("ep01")["reading"] == "下見"
    assert chat.read_chat("ep01")["stale"] is None


def test_あとで確定版ができたらお知らせを出す(ep, monkeypatch):
    """材料は1回目にしか渡していないので、画面が取り違えないようにする。"""
    write_text_file(ep, "scan.json", [{"start": 0, "text": "あ"}])
    fake_claude(monkeypatch)
    chat.ask("ep01", "質問")

    write_text_file(ep, "transcript.json", [{"start": 0, "text": "い"}])
    got = chat.read_chat("ep01")
    assert got["reading"] == "下見"                  # 会話を始めた版のまま
    assert "リセット" in got["stale"]


def test_リセットしたあとは確定版で始まる(ep, monkeypatch):
    write_text_file(ep, "scan.json", [{"start": 0, "text": "あ"}])
    seen = fake_claude(monkeypatch)
    chat.ask("ep01", "1回目")
    write_text_file(ep, "transcript.json", [{"start": 0, "text": "い"}])
    chat.reset("ep01")
    chat.ask("ep01", "2回目")

    assert seen["persist"] is True                   # 新しいセッション
    assert chat.read_chat("ep01")["reading"] == "確定版"
    assert chat.read_chat("ep01")["stale"] is None
