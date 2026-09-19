"""web/media.py のテスト（下見の文字起こしと、音声の配り方）。"""

import json

import pytest

from web import episodes, media


@pytest.fixture
def ep(tmp_path, monkeypatch):
    ep_dir = tmp_path / "ep01"
    for sub in ["00_raw", "01_clean", "02_text"]:
        (ep_dir / sub).mkdir(parents=True)
    monkeypatch.setattr(episodes, "resolve", lambda name, root=None: ep_dir)
    return ep_dir


def write_scan(ep_dir, source="rec.wav", segments=None):
    (ep_dir / "02_text" / "scan.json").write_text(json.dumps({
        "segments": segments if segments is not None else [
            {"start": 0.0, "end": 5.0, "text": " こんばんは "},
        ],
        "full_text": "こんばんは",
        "source": source,
        "duration": 59.5,
    }, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- 下見

def test_下見がなければ未実行(ep):
    assert media.read_scan("ep01") == {"state": "未実行", "segments": []}


def test_下見を読むと行と長さが返る(ep):
    write_scan(ep)
    got = media.read_scan("ep01")
    assert got["state"] == "表示"
    assert got["duration"] == 59.5
    assert got["source"] == "rec.wav"
    assert got["segments"] == [{"start": 0.0, "end": 5.0, "text": "こんばんは"}]


def test_壊れた下見は理由を言って断る(ep):
    (ep / "02_text" / "scan.json").write_text("{壊れた", encoding="utf-8")
    with pytest.raises(episodes.EpisodeError, match="scan.json が読めません"):
        media.read_scan("ep01")


# ---------------------------------------------------------------- 音声

def test_下見の音は下見をかけた音そのもの(ep):
    (ep / "00_raw" / "rec.wav").write_bytes(b"a")
    (ep / "00_raw" / "ほか.wav").write_bytes(b"b")
    write_scan(ep, source="rec.wav")
    assert media.audio_path("ep01", "scan").name == "rec.wav"


def test_下見の前でも音源は聴ける(ep):
    (ep / "00_raw" / "rec.m4a").write_bytes(b"a")
    assert media.audio_path("ep01", "scan").name == "rec.m4a"


def test_音源がなければ断る(ep):
    with pytest.raises(episodes.EpisodeError, match="音源がありません"):
        media.audio_path("ep01", "scan")


def test_下見のsourceで回の外は指せない(ep, tmp_path):
    outside = tmp_path / "ひみつ.wav"
    outside.write_bytes("だめ".encode())
    (ep / "00_raw" / "rec.wav").write_bytes(b"a")
    write_scan(ep, source="../ひみつ.wav")
    # 名前だけを使うので、00_raw の外には出ない
    got = media.audio_path("ep01", "scan")
    assert got.parent == ep / "00_raw"
    assert got.name == "rec.wav"


def test_整音後の音はclean_wav(ep):
    (ep / "01_clean" / "clean.wav").write_bytes(b"a")
    assert media.audio_path("ep01", "clean").name == "clean.wav"


def test_整音していなければ断る(ep):
    with pytest.raises(episodes.EpisodeError, match="整音後の音声がありません"):
        media.audio_path("ep01", "clean")


def test_知らない種類は断る(ep):
    with pytest.raises(episodes.EpisodeError, match="知らない種類"):
        media.audio_path("ep01", "なにか")
