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


# ---------------------------------------------------------------- 波形

def make_wav(path, seconds=1.0, rate=48000):
    import math
    import struct
    import wave as wavemod
    with wavemod.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        frames = int(rate * seconds)
        out.writeframes(b"".join(
            struct.pack("<h", int(20000 * math.sin(i / 50))) for i in range(frames)
        ))


def test_整音していなければ波形は未実行(ep):
    got = media.waveform("ep01")
    assert got["state"] == "未実行"
    assert "整音" in got["reason"]


def test_波形はtrimmedから作る(ep):
    make_wav(ep / "01_clean" / "trimmed.wav", seconds=1.0)
    got = media.waveform("ep01", points=20)
    assert got["state"] == "表示"
    assert round(got["duration"], 2) == 1.0
    assert len(got["peaks"]) == 20
    assert all(0.0 <= p <= 1.0 for p in got["peaks"])
    assert max(got["peaks"]) > 0.5      # 音が入っている


def test_波形はcleanではなくtrimmedを見る(ep):
    make_wav(ep / "01_clean" / "clean.wav")
    assert media.waveform("ep01")["state"] == "未実行"


# ---------------------------------------------------------------- 試聴

def test_整音前は試聴できない(ep):
    with pytest.raises(episodes.EpisodeError, match="先に整音"):
        media.echo_preview("ep01", 1.0, 2.0, "light")


def test_短すぎる区間は試聴できない(ep):
    make_wav(ep / "01_clean" / "trimmed.wav", seconds=3.0)
    with pytest.raises(episodes.EpisodeError, match="短すぎます"):
        media.echo_preview("ep01", 1.0, 1.01, "light")


# ---------------------------------------------------------------- 整音の結果

def test_整音していなければ結果は未実行(ep):
    assert media.clean_result("ep01") == {"state": "未実行"}


def test_整音の結果を読む(ep):
    (ep / "01_clean" / "clean.wav").write_bytes(b"a")
    (ep / "01_clean" / "clean.json").write_text(json.dumps({
        "duration": 57.14, "removed": 2.47, "target_lufs": -14,
        "echoes": [{"start": 5, "end": 9, "preset": "light"}],
    }), encoding="utf-8")
    got = media.clean_result("ep01")
    assert got["state"] == "完了"
    assert got["confirmed"] is False
    assert got["duration"] == 57.14
    assert got["removed"] == 2.47
    assert got["echoes"] == 1


def test_記録が無くても結果は出す(ep):
    (ep / "01_clean" / "clean.wav").write_bytes(b"a")
    got = media.clean_result("ep01")
    assert got["state"] == "完了"
    assert got["duration"] is None


def test_確認したを押すと確認済みになる(ep):
    (ep / "01_clean" / "clean.wav").write_bytes(b"a")
    assert media.confirm_clean("ep01")["confirmed"] is True
    assert media.clean_result("ep01")["confirmed"] is True


def test_整音をやり直すと未確認に戻る(ep):
    import os
    import time
    clean = ep / "01_clean" / "clean.wav"
    clean.write_bytes(b"a")
    media.confirm_clean("ep01")
    time.sleep(0.01)
    os.utime(clean, (time.time(), time.time()))       # やり直した
    assert media.clean_result("ep01")["confirmed"] is False


def test_整音していなければ確認できない(ep):
    with pytest.raises(episodes.EpisodeError, match="まだ整音していません"):
        media.confirm_clean("ep01")


# ---------------------------------------------------------------- 「古い」の判定

def clean_with(ep_dir, echoes, trimmed=57.11):
    (ep_dir / "01_clean" / "clean.wav").write_bytes(b"a")
    (ep_dir / "01_clean" / "clean.json").write_text(json.dumps({
        "duration": 57.14, "removed": 2.47, "target_lufs": -14,
        "trimmed_duration": trimmed, "echoes": echoes,
    }), encoding="utf-8")


def set_echoes(ep_dir, echoes):
    import yaml
    (ep_dir / "config.yml").write_text(
        yaml.safe_dump({"episode": 1, "echoes": echoes}, allow_unicode=True),
        encoding="utf-8")


def test_エコー区間を変えると古いになる(ep):
    clean_with(ep, [{"start": 5, "end": 9, "preset": "light"}])
    set_echoes(ep, [{"start": 20, "end": 24, "preset": "hall"}])
    got = media.clean_result("ep01")
    assert got["state"] == "古い"
    assert "エコー区間" in got["stale_reason"]


def test_同じエコー区間なら古くならない(ep):
    rows = [{"start": 5, "end": 9, "preset": "light"}]
    clean_with(ep, rows)
    set_echoes(ep, rows)
    assert media.clean_result("ep01")["state"] == "完了"


def test_かからない区間が残っていても古くならない(ep):
    """config には飛ばされた区間も残る。clean.json には実際にかけた分だけ入る。"""
    clean_with(ep, [{"start": 5, "end": 9, "preset": "light"}])
    set_echoes(ep, [
        {"start": 5, "end": 9, "preset": "light"},
        {"start": 9.1, "end": 12, "preset": "hall"},   # 近すぎるので、かからない
        {"start": 30, "end": 34, "preset": "none"},    # 「なし」なので、かからない
    ])
    assert media.clean_result("ep01")["state"] == "完了"


def test_音源を差し替えると古いになる(ep):
    import os
    import time
    clean_with(ep, [])
    set_echoes(ep, [])
    later = time.time() + 10
    (ep / "00_raw" / "rec.wav").write_bytes(b"a")
    os.utime(ep / "00_raw" / "rec.wav", (later, later))
    got = media.clean_result("ep01")
    assert got["state"] == "古い"
    assert "音源" in got["stale_reason"]


def test_古いときは確認済みにならない(ep):
    clean_with(ep, [{"start": 5, "end": 9, "preset": "light"}])
    set_echoes(ep, [{"start": 5, "end": 9, "preset": "light"}])
    media.confirm_clean("ep01")
    assert media.clean_result("ep01")["confirmed"] is True
    set_echoes(ep, [{"start": 20, "end": 24, "preset": "hall"}])
    assert media.clean_result("ep01")["confirmed"] is False


def test_clean_json_が壊れた形でも落ちない(ep):
    (ep / "01_clean" / "clean.wav").write_bytes(b"a")
    (ep / "01_clean" / "clean.json").write_text(json.dumps({"echoes": 5}), encoding="utf-8")
    got = media.clean_result("ep01")
    assert got["state"] in ("完了", "古い")
    assert got["echoes"] == 0
