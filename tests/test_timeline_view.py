"""web/media.py の timeline_view / timeline_source_path のテスト（#85 の2段目）。

守るのは3つ。

- 生音の長さと、番組の先頭からの位置が、本編・BGM・SE それぞれに出る
- 音源が無い・長さが読めないクリップは、止めずにそのクリップに理由を付ける
- `timeline.yml` の source をそのまま経路に使わず、00_raw の外を指せない
"""

import subprocess

import pytest

from web import episodes, media, timeline


def sine(path, seconds, rate=48000):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"sine=frequency=440:duration={seconds}:sample_rate={rate}",
         "-ac", "1", "-c:a", "pcm_s16le", str(path)], check=True)
    return path


@pytest.fixture
def ep(tmp_path, monkeypatch):
    ep_dir = tmp_path / "ep01"
    for sub in ["00_raw", "01_clean", "02_text", "03_meta", "04_video"]:
        (ep_dir / sub).mkdir(parents=True)
    monkeypatch.setattr(episodes, "resolve", lambda name, root=None: ep_dir)
    # bgm・se は assets/ から探す（#85 の5段目）。episodes.ROOT は tmp_path とは
    # 別の場所（起動時に決まる）ので、テストではここに向け直す
    monkeypatch.setattr(episodes, "ROOT", tmp_path)
    (tmp_path / "assets").mkdir(parents=True, exist_ok=True)
    return ep_dir


def write_timeline(ep_dir, body):
    (ep_dir / "timeline.yml").write_text(body, encoding="utf-8")


TWO_WITH_BGM = """version: 1
lanes:
  main:
    - {id: op, source: op.wav, gap: 0}
    - {id: imasara, source: zunda.wav, gap: 1.0}
  bgm:
    - {id: bg1, source: bg1.wav, anchor: imasara, at: 2.0}
  se: []
"""


def test_timelineがない回はNoneを返す(ep):
    assert media.timeline_view("ep01") == {"timeline": None}


def test_本編の長さと位置が出る(ep):
    sine(ep / "00_raw" / "op.wav", 2)
    sine(ep / "00_raw" / "zunda.wav", 3)
    sine(ep.parent / "assets" / "bg1.wav", 1)
    write_timeline(ep, TWO_WITH_BGM)

    got = media.timeline_view("ep01")["timeline"]
    op, imasara = got["lanes"]["main"]
    assert op["duration"] == pytest.approx(2.0, abs=0.01)
    assert op["start"] == 0
    assert op["error"] is None
    assert imasara["start"] == pytest.approx(3.0, abs=0.01)   # 2.0 + gap 1.0
    assert imasara["duration"] == pytest.approx(3.0, abs=0.01)


def test_BGMはanchorの位置に置かれる(ep):
    sine(ep / "00_raw" / "op.wav", 2)
    sine(ep / "00_raw" / "zunda.wav", 3)
    sine(ep.parent / "assets" / "bg1.wav", 1)
    write_timeline(ep, TWO_WITH_BGM)

    got = media.timeline_view("ep01")["timeline"]
    bg1 = got["lanes"]["bgm"][0]
    assert bg1["start"] == pytest.approx(5.0, abs=0.01)   # imasara の開始 3.0 + at 2.0
    assert bg1["error"] is None


def test_音源がないクリップは理由を付けて止まらない(ep):
    sine(ep / "00_raw" / "op.wav", 2)
    # zunda.wav を置かない
    sine(ep.parent / "assets" / "bg1.wav", 1)
    write_timeline(ep, TWO_WITH_BGM)

    got = media.timeline_view("ep01")["timeline"]
    op, imasara = got["lanes"]["main"]
    assert op["error"] is None
    assert op["start"] == 0
    assert "音源がありません" in imasara["error"]
    assert imasara["start"] is None

    # 後ろに繋がる BGM も、位置の元になる imasara が壊れているので計算できない
    bg1 = got["lanes"]["bgm"][0]
    assert bg1["start"] is None
    assert "錨" in bg1["error"]


def test_壊れたtimelineymlは理由を画面に出せる形で断る(ep):
    write_timeline(ep, "{壊れた yaml: [")
    with pytest.raises(episodes.EpisodeError, match="timeline.yml が読めません"):
        media.timeline_view("ep01")


def test_音の在りかはファイル名だけで配る(ep):
    sine(ep / "00_raw" / "op.wav", 1)
    got = media.timeline_source_path("ep01", "main", "op.wav")
    assert got == ep / "00_raw" / "op.wav"


def test_音源のパスは00_rawの外を指せない(ep, tmp_path):
    outside = tmp_path / "ひみつ.wav"
    outside.write_bytes("だめ".encode())
    (ep / "00_raw" / "ひみつ.wav").write_bytes("00_rawの中身".encode())
    # 名前だけを使うので、../ を混ぜても 00_raw の中しか見ない
    got = media.timeline_source_path("ep01", "main", "../ひみつ.wav")
    assert got == ep / "00_raw" / "ひみつ.wav"
    assert got.read_bytes() == "00_rawの中身".encode()


def test_音源がない名前は断る(ep):
    with pytest.raises(episodes.EpisodeError, match="音源がありません"):
        media.timeline_source_path("ep01", "main", "no-such.wav")


@pytest.mark.parametrize("name", ["..", "."])
def test_フォルダを指す名前は断る(ep, name):
    # 基底名にしても `..` と `.` は残り、回のフォルダや 00_raw 自身を指す。ファイルでなければ断る
    with pytest.raises(episodes.EpisodeError, match="音源がありません"):
        media.timeline_source_path("ep01", "main", name)


def test_知らないレーンは断る(ep):
    with pytest.raises(episodes.EpisodeError, match="知らないレーン"):
        media.timeline_source_path("ep01", "talk", "a.wav")


def test_bgmはassetsから配る(ep):
    (ep.parent / "assets" / "music").mkdir(parents=True)
    sine(ep.parent / "assets" / "music" / "song.wav", 1)
    got = media.timeline_source_path("ep01", "bgm", "music/song.wav")
    assert got == ep.parent / "assets" / "music" / "song.wav"


def test_bgmはassetsの外を指せない(ep, tmp_path):
    outside = tmp_path / "ひみつ.wav"
    outside.write_bytes("だめ".encode())
    with pytest.raises(episodes.EpisodeError, match="音源がありません"):
        media.timeline_source_path("ep01", "bgm", "../ひみつ.wav")


def test_sourceがフォルダを指していても止まらず理由を返す(ep):
    # timeline_source_path と同じ守りを通っているか（直す前は 00_raw 自身を指して
    # ffprobe に渡り、「could not convert string to float」という分かりにくい失敗をしていた）
    write_timeline(ep, """version: 1
lanes:
  main:
    - {id: op, source: '..', gap: 0}
  bgm: []
  se: []
""")
    got = media.timeline_view("ep01")["timeline"]
    op = got["lanes"]["main"][0]
    assert "音源がありません" in op["error"]
    assert "could not convert" not in op["error"]
    assert op["start"] is None


# ---------------------------------------------------------------- web/timeline.py との整合性

def test_位置の計算はtimeline_positionsと一致する(ep):
    """timeline_view は positions() を直接使わず（長さが読めなくても止めないため）、
    同じ式を別に書いている。durations が全部そろっているときは、答えが一致するはず。"""
    sine(ep / "00_raw" / "op.wav", 2)
    sine(ep / "00_raw" / "zunda.wav", 3)
    sine(ep.parent / "assets" / "bg1.wav", 1)
    write_timeline(ep, TWO_WITH_BGM)

    got = media.timeline_view("ep01")["timeline"]
    durations = {c["id"]: c["duration"] for lane in got["lanes"].values() for c in lane}

    data = timeline.read(ep)
    expected = timeline.positions(data, durations)

    for lane in got["lanes"].values():
        for clip in lane:
            assert clip["start"] == pytest.approx(expected[clip["id"]], abs=0.001), clip["id"]
