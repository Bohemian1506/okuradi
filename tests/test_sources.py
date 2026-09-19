"""web/sources.py のテスト（音源の追加と、アプリ全体の設定）。

本物の音声は使わない。長さを測るところ（ffprobe）は差し替える。
"""

import io

import pytest

from web import episodes, sources


@pytest.fixture
def here(tmp_path, monkeypatch):
    """回のディレクトリと settings.yml を、テスト用の場所に向ける。"""
    ep_dir = tmp_path / "ep01"
    (ep_dir / "00_raw").mkdir(parents=True)
    monkeypatch.setattr(sources, "SETTINGS", tmp_path / "settings.yml")
    monkeypatch.setattr(episodes, "resolve", lambda name, root=None: ep_dir)
    monkeypatch.setattr(sources, "duration_of", lambda path: 59.0)
    return ep_dir


# ---------------------------------------------------------------- 設定

def test_設定は書いて読める(here):
    assert sources.read_settings() == {}
    sources.save_settings({"obs_dir": "/mnt/c/Videos"})
    assert sources.read_settings()["obs_dir"] == "/mnt/c/Videos"


def test_壊れた設定は理由を言って断る(here):
    sources.SETTINGS.write_text("obs_dir: [壊れた\n", encoding="utf-8")
    with pytest.raises(episodes.EpisodeError, match="settings.yml が読めません"):
        sources.read_settings()


# ---------------------------------------------------------------- OBS のフォルダ

def test_未設定なら未設定と返す(here):
    assert sources.obs_view()["state"] == "未設定"


def test_無いフォルダなら見つかりませんと返す(here):
    sources.save_settings({"obs_dir": str(here.parent / "ない")})
    assert sources.obs_view()["state"] == "見つかりません"


def test_録画は新しい順に並び関係ないファイルは出さない(here, tmp_path):
    obs = tmp_path / "obs"
    obs.mkdir()
    import os, time
    for index, name in enumerate(["古い.mkv", "新しい.mp4", "memo.txt"]):
        path = obs / name
        path.write_text("x", encoding="utf-8")
        os.utime(path, (time.time() + index, time.time() + index))
    sources.save_settings({"obs_dir": str(obs)})

    view = sources.obs_view()
    assert view["state"] == "ok"
    assert [r["name"] for r in view["recordings"]] == ["新しい.mp4", "古い.mkv"]


# ---------------------------------------------------------------- 収録ファイル

def test_音源がなければ空(here):
    assert sources.source_view("ep01") == {"state": "空"}


def test_取り込むと使えるになる(here):
    sources.add_from_upload("ep01", "rec.wav", io.BytesIO("おと".encode()))
    got = sources.source_view("ep01")
    assert got["state"] == "使える"
    assert got["name"] == "rec.wav"
    assert got["kind"] == "wav"
    assert got["from_video"] is False


def test_録画なら元は録画として見せる(here):
    sources.add_from_upload("ep01", "rec.mkv", io.BytesIO("どうが".encode()))
    got = sources.source_view("ep01")
    assert got["kind"] == "OBSの録画"
    assert got["from_video"] is True


def test_対応していない形式は断る(here):
    with pytest.raises(episodes.EpisodeError, match="対応していません"):
        sources.add_from_upload("ep01", "memo.txt", io.BytesIO(b"x"))


def test_取り込むと前の音源は残らない(here):
    sources.add_from_upload("ep01", "前.wav", io.BytesIO(b"1"))
    sources.add_from_upload("ep01", "後.wav", io.BytesIO(b"2"))
    names = [f.name for f in (here / "00_raw").iterdir()]
    assert names == ["後.wav"]


def test_OBS_から取り込める(here, tmp_path):
    obs = tmp_path / "obs"
    obs.mkdir()
    (obs / "収録.mkv").write_bytes("どうが".encode())
    sources.save_settings({"obs_dir": str(obs)})

    got = sources.add_from_obs("ep01", "収録.mkv")
    assert got["name"] == "収録.mkv"
    assert (here / "00_raw" / "収録.mkv").read_bytes() == "どうが".encode()
    assert (obs / "収録.mkv").exists()      # 元は消さない


def test_OBS_のフォルダの外は指せない(here, tmp_path):
    obs = tmp_path / "obs"
    obs.mkdir()
    outside = tmp_path / "ひみつ.wav"
    outside.write_bytes("だめ".encode())
    sources.save_settings({"obs_dir": str(obs)})

    with pytest.raises(episodes.EpisodeError, match="見つかりません"):
        sources.add_from_obs("ep01", "../ひみつ.wav")
    assert not (here / "00_raw" / "ひみつ.wav").exists()


def test_OBS_が未設定なら取り込めない(here):
    with pytest.raises(episodes.EpisodeError, match="使えません"):
        sources.add_from_obs("ep01", "なにか.mkv")
