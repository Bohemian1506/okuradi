"""timeline.yml の並びどおりに音源を繋ぐところ（build.find_raw / join_sources）。

**形式は必ずそろえてから繋ぐ。** 24kHz の音を 48kHz として繋ぐと、ffmpeg は何も言わずに
倍速・1オクターブ上の音を作る（2026-09-22 に実測）。気づけない壊れ方なので、
「合っていたらそのまま」に分岐しない。
"""

import subprocess

import pytest

import build


def sine(path, seconds, rate=48000, freq=440):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"sine=frequency={freq}:duration={seconds}:sample_rate={rate}",
         "-ac", "1", "-c:a", "pcm_s16le", str(path)], check=True)
    return path


@pytest.fixture
def ep(tmp_path):
    made = {"dir": tmp_path, "name": "ep98"}
    for sub in ["00_raw", "01_cut", "01_clean", "02_text", "03_meta", "04_video"]:
        made[sub] = tmp_path / sub
        made[sub].mkdir()
    return made


def timeline_yml(ep, body):
    (ep["dir"] / "timeline.yml").write_text(body, encoding="utf-8")


TWO = """version: 1
lanes:
  main:
    - {id: a, source: a.wav, gap: 0}
    - {id: b, source: b.wav, gap: 0}
  bgm: []
  se: []
"""


def test_2本並んでいれば繋いだ1本を返す(ep):
    sine(ep["00_raw"] / "a.wav", 2)
    sine(ep["00_raw"] / "b.wav", 3, freq=660)
    timeline_yml(ep, TWO)
    got = build.find_raw(ep)
    assert got.name == build.JOINED
    assert build.audio_duration(got) == pytest.approx(5.0, abs=0.01)


def test_サンプリングレートが違っても正しい長さで繋がる(ep):
    """ここが一番危ない。そろえずに繋ぐと、黙って倍速になる。"""
    sine(ep["00_raw"] / "a.wav", 2, rate=48000)
    sine(ep["00_raw"] / "b.wav", 3, rate=24000)
    timeline_yml(ep, TWO)
    got = build.find_raw(ep)
    assert build.audio_duration(got) == pytest.approx(5.0, abs=0.01)


def test_元が新しくなければ繋ぎ直さない(ep):
    sine(ep["00_raw"] / "a.wav", 2)
    sine(ep["00_raw"] / "b.wav", 2)
    timeline_yml(ep, TWO)
    first = build.find_raw(ep)
    before = first.stat().st_mtime_ns
    assert build.find_raw(ep).stat().st_mtime_ns == before


def test_元が新しくなったら繋ぎ直す(ep):
    sine(ep["00_raw"] / "a.wav", 2)
    sine(ep["00_raw"] / "b.wav", 2)
    timeline_yml(ep, TWO)
    build.find_raw(ep)
    sine(ep["00_raw"] / "b.wav", 4)          # 録り直した
    assert build.audio_duration(build.find_raw(ep)) == pytest.approx(6.0, abs=0.01)


def test_編集点があれば黙って進まない(ep):
    """まだ工程に繋がっていない。無視すると、書いたのにかからない。"""
    sine(ep["00_raw"] / "a.wav", 2)
    sine(ep["00_raw"] / "b.wav", 2)
    timeline_yml(ep, """version: 1
lanes:
  main:
    - id: a
      source: a.wav
      gap: 0
      edits: [{start: 0.5, end: 1.0, kind: cut}]
    - {id: b, source: b.wav, gap: 0}
  bgm: []
  se: []
""")
    with pytest.raises(ValueError, match="まだ工程に繋がっていません"):
        build.find_raw(ep)


def test_音源が足りなければ理由を出す(ep):
    sine(ep["00_raw"] / "a.wav", 2)
    timeline_yml(ep, TWO)
    with pytest.raises(FileNotFoundError, match="b の音源がありません"):
        build.find_raw(ep)


def test_タイムラインが無ければ今までどおり1本を使う(ep):
    sine(ep["00_raw"] / "a.wav", 2)
    assert build.find_raw(ep).name == "a.wav"


def test_タイムラインが1本だけなら今までどおり(ep):
    sine(ep["00_raw"] / "a.wav", 2)
    timeline_yml(ep, """version: 1
lanes:
  main: [{id: a, source: a.wav, gap: 0}]
  bgm: []
  se: []
""")
    assert build.find_raw(ep).name == "a.wav"


def test_繋いだ音を音源として拾わない(ep):
    """joined.wav は名前順で a.wav より前に来る。拾うと繋いだものを繋ぐことになる。"""
    sine(ep["00_raw"] / "a.wav", 2)
    sine(ep["00_raw"] / build.JOINED, 9)
    assert build.find_raw(ep).name == "a.wav"
