"""timeline.yml の並びどおりに音源を繋ぐところ（build.find_raw / join_sources）。

**形式は必ずそろえてから繋ぐ。** 24kHz の音を 48kHz として繋ぐと、ffmpeg は何も言わずに
倍速・1オクターブ上の音を作る（2026-09-22 に実測）。気づけない壊れ方なので、
「合っていたらそのまま」に分岐しない。
"""

import os
import subprocess
import time
import wave

import numpy as np
import pytest

import build


def sine(path, seconds, rate=48000, freq=440):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"sine=frequency={freq}:duration={seconds}:sample_rate={rate}",
         "-ac", "1", "-c:a", "pcm_s16le", str(path)], check=True)
    return path


def silence(path, seconds, rate=48000):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"anullsrc=r={rate}:cl=mono",
         "-t", str(seconds), "-ac", "1", "-c:a", "pcm_s16le", str(path)], check=True)
    return path


def mean_abs(path, ms=100, rate=48000):
    """繋いだ wav の先頭 ms ミリ秒の音量（平均振幅）。無音か音かの見分けに使う。"""
    with wave.open(str(path), "rb") as w:
        data = w.readframes(int(rate * ms / 1000))
    arr = np.frombuffer(data, dtype=np.int16)
    return float(np.abs(arr).mean()) if len(arr) else 0.0


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


THREE = """version: 1
lanes:
  main:
    - {id: a, source: a.wav, gap: 0}
    - {id: b, source: b.wav, gap: 0}
    - {id: c, source: c.wav, gap: 0}
  bgm: []
  se: []
"""

TWO_AC = """version: 1
lanes:
  main:
    - {id: a, source: a.wav, gap: 0}
    - {id: c, source: c.wav, gap: 0}
  bgm: []
  se: []
"""

TWO_SWAPPED = """version: 1
lanes:
  main:
    - {id: b, source: b.wav, gap: 0}
    - {id: a, source: a.wav, gap: 0}
  bgm: []
  se: []
"""


def test_並びだけ変えたら繋ぎ直す(ep):
    """入れ替えたのに古い順番の音が流れ続けるのは、使う人から見て明らかにおかしい。
    音源ファイル自体の更新日時が変わっていなくても、timeline.yml の並びを変えたら
    繋ぎ直されるべき。

    a は無音、b は音のある sine にして、繋いだ音の「先頭が無音か音か」で
    実際にどちらが先に来ているかを確かめる（長さだけでは並び替えを検出できない）。
    """
    a = silence(ep["00_raw"] / "a.wav", 1)
    b = sine(ep["00_raw"] / "b.wav", 1)
    base = time.time() - 1000
    os.utime(a, (base, base))
    os.utime(b, (base, base))

    timeline_yml(ep, TWO)
    os.utime(ep["dir"] / "timeline.yml", (base + 1, base + 1))

    dst = build.find_raw(ep)
    os.utime(dst, (base + 2, base + 2))
    assert mean_abs(dst) < 50, "a（無音）が先のはず"

    # 並びだけ入れ替える。a.wav・b.wav の中身・更新日時はさわらない
    timeline_yml(ep, TWO_SWAPPED)
    os.utime(ep["dir"] / "timeline.yml", (base + 3, base + 3))

    got = build.find_raw(ep)
    assert mean_abs(got) > 500, "並びを入れ替えたのだから、b（音）が先になるはず"


def test_音源を1本減らしたら繋ぎ直す(ep):
    """timeline.yml から行を消したのに、消した音源がまだ繋いだファイルに
    残っているのは使う人から見ておかしい。残った音源の更新日時が変わっていなくても
    繋ぎ直されるべき。
    """
    a = sine(ep["00_raw"] / "a.wav", 2)
    b = sine(ep["00_raw"] / "b.wav", 2, freq=660)
    c = sine(ep["00_raw"] / "c.wav", 2, freq=880)
    base = time.time() - 1000
    for f in (a, b, c):
        os.utime(f, (base, base))

    timeline_yml(ep, THREE)
    os.utime(ep["dir"] / "timeline.yml", (base + 1, base + 1))

    dst = build.find_raw(ep)
    os.utime(dst, (base + 2, base + 2))
    assert build.audio_duration(dst) == pytest.approx(6.0, abs=0.01)

    # b を消す。a.wav・c.wav の中身・更新日時はさわらない
    timeline_yml(ep, TWO_AC)
    os.utime(ep["dir"] / "timeline.yml", (base + 3, base + 3))

    got = build.find_raw(ep)
    assert build.audio_duration(got) == pytest.approx(4.0, abs=0.01), \
        "b を消したのだから、繋いだ音は a + c の長さになるはず"


def test_音源を1本足したら繋ぎ直す(ep):
    """新しく置いた音源ファイルは更新日時が新しいので、繋ぎ直されるはず
    （3つのうちここだけは、いまの実装でも動くと見込んでいる）。
    """
    a = sine(ep["00_raw"] / "a.wav", 2)
    b = sine(ep["00_raw"] / "b.wav", 2, freq=660)
    base = time.time() - 1000
    os.utime(a, (base, base))
    os.utime(b, (base, base))

    timeline_yml(ep, TWO)
    os.utime(ep["dir"] / "timeline.yml", (base + 1, base + 1))

    dst = build.find_raw(ep)
    os.utime(dst, (base + 2, base + 2))
    assert build.audio_duration(dst) == pytest.approx(4.0, abs=0.01)

    # c を新しく置く（mtime はさわらない = 「いま」のまま、dst より新しい）
    sine(ep["00_raw"] / "c.wav", 2, freq=880)
    timeline_yml(ep, THREE)
    os.utime(ep["dir"] / "timeline.yml", (base + 3, base + 3))

    got = build.find_raw(ep)
    assert build.audio_duration(got) == pytest.approx(6.0, abs=0.01), \
        "c を足したのだから、繋いだ音は a + b + c の長さになるはず"


def test_gapのぶんの無音がはさまる(ep):
    """**入れないと、positions が出す時刻と実際の音が食い違う。**

    計算は gap を足しているのに、繋いだ音には入っていない、という形で
    2026-09-22 に見つかった（計算 6.5秒 / 実際 5.0秒）。
    """
    sine(ep["00_raw"] / "a.wav", 2)
    sine(ep["00_raw"] / "b.wav", 3)
    timeline_yml(ep, """version: 1
lanes:
  main:
    - {id: a, source: a.wav, gap: 0}
    - {id: b, source: b.wav, gap: 1.5}
  bgm: []
  se: []
""")
    got = build.find_raw(ep)
    assert build.audio_duration(got) == pytest.approx(6.5, abs=0.02)


def test_繋いだ音の長さがtimelineの計算と合う(ep):
    """計算（total_seconds）と実際の音が、同じ答えになること。"""
    from web import timeline

    sine(ep["00_raw"] / "a.wav", 2)
    sine(ep["00_raw"] / "b.wav", 3)
    timeline_yml(ep, """version: 1
lanes:
  main:
    - {id: a, source: a.wav, gap: 0.25}
    - {id: b, source: b.wav, gap: 1.5}
  bgm: []
  se: []
""")
    got = build.find_raw(ep)
    data = timeline.read(ep["dir"])
    計算 = timeline.total_seconds(data, {"a": 2.0, "b": 3.0})
    assert build.audio_duration(got) == pytest.approx(計算, abs=0.02)


def test_gapを変えたら繋ぎ直す(ep):
    sine(ep["00_raw"] / "a.wav", 2)
    sine(ep["00_raw"] / "b.wav", 2)
    timeline_yml(ep, TWO)
    assert build.audio_duration(build.find_raw(ep)) == pytest.approx(4.0, abs=0.02)
    timeline_yml(ep, TWO.replace("{id: b, source: b.wav, gap: 0}",
                                 "{id: b, source: b.wav, gap: 2.0}"))
    assert build.audio_duration(build.find_raw(ep)) == pytest.approx(6.0, abs=0.02)


def test_更新日時が同着なら繋ぎ直す(ep):
    """`>=` だと、ぴったり同じ時刻のときに黙って古い音を返していた。

    ext4 はナノ秒まで見るので普段は起きないが、exFAT / FAT32 は粒度が粗い。
    起きても何も出ないのが一番まずい（CLAUDE.md「静かに失敗させない」）。
    """
    import os

    sine(ep["00_raw"] / "a.wav", 2)
    sine(ep["00_raw"] / "b.wav", 2)
    timeline_yml(ep, TWO)
    first = build.find_raw(ep)
    assert build.audio_duration(first) == pytest.approx(4.0, abs=0.02)

    sine(ep["00_raw"] / "b.wav", 4)                     # 録り直した
    same = first.stat().st_mtime
    for name in ("a.wav", "b.wav"):
        os.utime(ep["00_raw"] / name, (same, same))
    os.utime(ep["dir"] / "timeline.yml", (same, same))

    assert build.audio_duration(build.find_raw(ep)) == pytest.approx(6.0, abs=0.02)
