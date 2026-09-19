"""web/runner.py のテスト。

実際に工程を動かすところ（子プロセス）は、本物の音声と ffmpeg・Whisper が要るので
ここでは確かめない。断り方と、作りかけの後始末を確かめる。
"""

import time

import pytest

from web import episodes, runner


def test_GUI_から動かせない工程は断る():
    with pytest.raises(episodes.EpisodeError, match="動かせない工程"):
        runner.start("ep01", "cut")
    with pytest.raises(episodes.EpisodeError, match="動かせない工程"):
        runner.start("ep01", "upload")


def test_無い回は断る():
    with pytest.raises(episodes.EpisodeError, match="がありません"):
        runner.start("ありません", "scan")


def test_回の外は指せない():
    with pytest.raises(episodes.EpisodeError):
        runner.start("..", "scan")


def test_ほかの工程を実行中なら断る(monkeypatch):
    job = runner.Job("ep01", "scan")           # state は「処理中」で始まる
    monkeypatch.setattr(runner, "_current", job)
    with pytest.raises(episodes.EpisodeError, match="実行中"):
        runner.start("ep01", "clean")


def test_終わった工程のあとは始められる(monkeypatch):
    job = runner.Job("ep01", "scan")
    job.state = "完了"
    monkeypatch.setattr(runner, "_current", job)
    assert runner.busy() is False


# ---------------------------------------------------------------- 作りかけの後始末

def make_job(tmp_path, before=None):
    job = runner.Job("ep01", "clean")
    job.target = tmp_path / "clean.wav"
    job.target_before = before
    return job


def test_この実行で作ったファイルは消す(tmp_path):
    job = make_job(tmp_path, before=None)      # 前は無かった
    job.target.write_text("とちゅう", encoding="utf-8")
    runner._discard_unfinished(job)
    assert not job.target.exists()


def test_前からあるファイルは消さない(tmp_path):
    target = tmp_path / "clean.wav"
    target.write_text("前の結果", encoding="utf-8")
    job = make_job(tmp_path, before=target.stat().st_mtime)
    runner._discard_unfinished(job)
    assert target.read_text(encoding="utf-8") == "前の結果"


def test_前からあっても上書きされていれば消す(tmp_path):
    target = tmp_path / "clean.wav"
    target.write_text("前の結果", encoding="utf-8")
    before = target.stat().st_mtime
    time.sleep(0.01)
    target.write_text("とちゅう", encoding="utf-8")
    job = make_job(tmp_path, before=before)
    runner._discard_unfinished(job)
    assert not target.exists()


def test_ファイルが無くても落ちない(tmp_path):
    runner._discard_unfinished(make_job(tmp_path))


# ---------------------------------------------------------------- 流す

def test_ログは購読している画面に届く():
    job = runner.Job("ep01", "scan")
    channel = job.subscribe()
    job.add_line("こんにちは")
    assert channel.get_nowait() == {"kind": "log", "line": "こんにちは"}
    job.unsubscribe(channel)
    job.add_line("もう届かない")
    assert channel.empty()


def test_終わると状態と終わりの合図が流れる():
    job = runner.Job("ep01", "scan")
    channel = job.subscribe()
    job.finish("完了")
    state = channel.get_nowait()
    assert state["kind"] == "state" and state["job"]["state"] == "完了"
    assert channel.get_nowait()["kind"] == "end"


def test_ログは伸び続けない():
    job = runner.Job("ep01", "scan")
    for i in range(2100):
        job.add_line(str(i))
    assert len(job.lines) <= 2000
    assert job.lines[-1] == "2099"     # 新しいほうを残す
