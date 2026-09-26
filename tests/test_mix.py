"""build.py の mix 工程（BGM・SE を重ねる）と、枠の回でのトリムの変え方のテスト。

#85 の4段目。実際に ffmpeg を動かして確かめる（sine/silence を使い、本物の声は使わない）。
"""

import subprocess
import wave

import numpy as np
import pytest

import build
from web import episodes


def sine(path, seconds, rate=48000, freq=440, amp=0.5):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"sine=frequency={freq}:duration={seconds}:sample_rate={rate}",
         "-af", f"volume={amp}",
         "-ac", "1", "-c:a", "pcm_s16le", str(path)], check=True)
    return path


def silence(path, seconds, rate=48000):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"anullsrc=r={rate}:cl=mono",
         "-t", str(seconds), "-ac", "1", "-c:a", "pcm_s16le", str(path)], check=True)
    return path


def silence_tone_silence(path, head=2.0, tone=3.0, tail=2.0, rate=48000):
    """頭と尻に無音、真ん中にトーンがある音。トリムの確かめに使う。"""
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"anullsrc=r={rate}:cl=mono:d={head}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={tone}:sample_rate={rate}",
        "-f", "lavfi", "-i", f"anullsrc=r={rate}:cl=mono:d={tail}",
        "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
        "-map", "[out]", "-ac", "1", "-c:a", "pcm_s16le", str(path),
    ], check=True)
    return path


def mean_abs(path, at=0.0, ms=200, rate=48000):
    """指定した位置からの、ある長さの平均振幅。無音か音かの見分けに使う。"""
    with wave.open(str(path), "rb") as w:
        w.setpos(min(int(at * rate), w.getnframes()))
        data = w.readframes(int(rate * ms / 1000))
    arr = np.frombuffer(data, dtype=np.int16)
    return float(np.abs(arr).mean()) if len(arr) else 0.0


def rms(path, start, end, rate=48000):
    """区間の実効値（RMS）。音量カーブで下がった量を測るのに使う。"""
    with wave.open(str(path), "rb") as w:
        w.setpos(int(start * rate))
        data = w.readframes(int((end - start) * rate))
    arr = np.frombuffer(data, dtype=np.int16).astype(np.float64)
    return float(np.sqrt(np.mean(arr ** 2))) if len(arr) else 0.0


def timeline_yml(ep, body):
    (ep["dir"] / "timeline.yml").write_text(body, encoding="utf-8")


def write_clean_json(ep, head_removed=0.0, tail_removed=0.0):
    """`_check_mix_positions` が読む記録を、テストの前提に合わせて用意する。

    実際に `step_clean` を通していないテストでは、この記録が無いと
    「位置が合っているか確かめられません」という警告だけが出て終わる
    （止まりはしない）。位置の食い違いを検知するテストでは、わざと
    ズレた値を書く。
    """
    import json
    (ep["01_clean"] / "clean.json").write_text(json.dumps({
        "head_removed": head_removed, "tail_removed": tail_removed,
    }), encoding="utf-8")


@pytest.fixture
def ep(tmp_path):
    made = {"dir": tmp_path, "name": "ep98", "root": tmp_path}
    for sub in ["00_raw", "01_cut", "01_clean", "01_mix"]:
        made[sub] = tmp_path / sub
        made[sub].mkdir()
    return made


CFG = {"audio": {"target_lufs": -14, "denoise": False, "trim_silence": True}}


# ---------------------------------------------------------------- 枠の回でのトリム（step_clean）

def test_枠の回では頭の無音を削らず尻だけ削る(ep):
    silence_tone_silence(ep["00_raw"] / "rec.wav", head=2.0, tone=3.0, tail=2.0)
    timeline_yml(ep, "version: 1\nlanes:\n"
                     "  main: [{id: op, source: rec.wav, gap: 0}]\n  bgm: []\n  se: []\n")

    build.step_clean(ep, CFG)

    trimmed = ep["01_clean"] / "trimmed.wav"
    total = build.audio_duration(trimmed)
    # 頭の無音(2秒)は残り、尻の無音(2秒)だけ削れるので、およそ head+tone=5秒になる
    assert total == pytest.approx(5.0, abs=0.3)
    # 先頭がまだ無音のままであることを確かめる（削られていたら、すぐ音が鳴る）
    assert mean_abs(trimmed, at=0.0, ms=300) < 50

    detail = _clean_json(ep)
    assert detail["framed"] is True
    assert detail["head_removed"] == pytest.approx(0.0, abs=0.3)
    assert detail["tail_removed"] == pytest.approx(2.0, abs=0.3)


def test_枠でない回は今までどおり前後を削る(ep):
    """timeline.yml が無い回（ep01 など）は、いままでどおり前後とも削る。"""
    silence_tone_silence(ep["00_raw"] / "rec.wav", head=2.0, tone=3.0, tail=2.0)

    build.step_clean(ep, CFG)

    trimmed = ep["01_clean"] / "trimmed.wav"
    total = build.audio_duration(trimmed)
    assert total == pytest.approx(3.0, abs=0.3)   # 頭も尻も削れて、トーンの3秒だけ残る

    detail = _clean_json(ep)
    assert detail["framed"] is False
    assert detail["head_removed"] == pytest.approx(2.0, abs=0.3)
    assert detail["tail_removed"] == pytest.approx(2.0, abs=0.3)


def _clean_json(ep):
    import json
    return json.loads((ep["01_clean"] / "clean.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- mix: 重ねるものが無い回

def test_bgmもseも無ければclean_wavと同じ音のmixができる(ep):
    sine(ep["01_clean"] / "clean.wav", 4, amp=0.3)

    build.step_mix(ep, CFG)

    mix = ep["01_mix"] / "mix.wav"
    assert mix.exists()
    clean_total = build.audio_duration(ep["01_clean"] / "clean.wav")
    assert build.audio_duration(mix) == pytest.approx(clean_total, abs=0.01)
    # 音そのものも変わらないはず
    assert mean_abs(mix, at=1.0) == pytest.approx(
        mean_abs(ep["01_clean"] / "clean.wav", at=1.0), rel=0.05)


def test_timelineがあってもbgmもseも空ならclean_wavと同じ(ep):
    sine(ep["01_clean"] / "clean.wav", 4, amp=0.3)
    timeline_yml(ep, "version: 1\nlanes:\n"
                     "  main: [{id: op, source: rec.wav, gap: 0}]\n  bgm: []\n  se: []\n")

    build.step_mix(ep, CFG)

    clean_total = build.audio_duration(ep["01_clean"] / "clean.wav")
    assert build.audio_duration(ep["01_mix"] / "mix.wav") == pytest.approx(clean_total, abs=0.01)


# ---------------------------------------------------------------- mix: 位置と長さ

TWO_CORNERS = """version: 1
lanes:
  main:
    - {{id: op, source: op.wav, gap: 0}}
    - {{id: talk, source: talk.wav, gap: 0}}
  bgm:
    - {{id: theme, source: bgm.wav, anchor: talk, at: {at}}}
  se: []
"""


def test_mixの長さはclean_wavと1サンプルも変わらない(ep):
    silence(ep["00_raw"] / "op.wav", 4)
    silence(ep["00_raw"] / "talk.wav", 6)
    sine(ep["01_clean"] / "clean.wav", 10, amp=0.2)
    sine(ep["00_raw"] / "bgm.wav", 3, freq=1000, amp=0.6)
    timeline_yml(ep, TWO_CORNERS.format(at=1.0))
    write_clean_json(ep)

    build.step_mix(ep, CFG)

    clean_total = build.audio_duration(ep["01_clean"] / "clean.wav")
    mix_total = build.audio_duration(ep["01_mix"] / "mix.wav")
    assert mix_total == pytest.approx(clean_total, abs=0.0005)


def test_曲は正しい位置から鳴りその位置より前は鳴らない(ep):
    silence(ep["00_raw"] / "op.wav", 4)
    silence(ep["00_raw"] / "talk.wav", 6)
    sine(ep["01_clean"] / "clean.wav", 10, freq=100, amp=0.05)   # 喋りに見立てた小さい音
    sine(ep["00_raw"] / "bgm.wav", 3, freq=1000, amp=0.8)        # 曲。振幅を大きくして見分ける
    timeline_yml(ep, TWO_CORNERS.format(at=1.0))                  # 位置 = 4 + 1 = 5秒
    write_clean_json(ep)

    build.step_mix(ep, CFG)
    mix = ep["01_mix"] / "mix.wav"

    before = mean_abs(mix, at=2.0, ms=500)     # 曲の位置(5秒)より前
    during = mean_abs(mix, at=6.0, ms=500)     # 曲の位置の中（5〜8秒）
    after = mean_abs(mix, at=9.0, ms=500)      # 曲が終わったあと（8秒以降）

    assert during > before * 3, "曲の位置のはずなのに、音量が増えていない"
    assert after < during / 2, "曲が終わったはずなのに、鳴り続けている"


def test_位置が番組の長さを超えたら断る(ep):
    silence(ep["00_raw"] / "op.wav", 4)
    silence(ep["00_raw"] / "talk.wav", 6)
    sine(ep["01_clean"] / "clean.wav", 10, amp=0.2)
    sine(ep["00_raw"] / "bgm.wav", 2)
    timeline_yml(ep, TWO_CORNERS.format(at=100))   # 4 + 100 = 104秒。番組は10秒しか無い
    write_clean_json(ep)

    with pytest.raises(ValueError, match="番組の長さ"):
        build.step_mix(ep, CFG)


def test_曲のファイルが無ければ理由を出して断る(ep):
    silence(ep["00_raw"] / "op.wav", 4)
    silence(ep["00_raw"] / "talk.wav", 6)
    sine(ep["01_clean"] / "clean.wav", 10, amp=0.2)
    # bgm.wav をわざと置かない
    timeline_yml(ep, TWO_CORNERS.format(at=1.0))
    write_clean_json(ep)

    with pytest.raises(FileNotFoundError, match="theme の音源がありません"):
        build.step_mix(ep, CFG)


def test_錨のクリップが無ければ断る(ep):
    sine(ep["01_clean"] / "clean.wav", 10, amp=0.2)
    timeline_yml(ep, """version: 1
lanes:
  main: [{id: op, source: op.wav, gap: 0}]
  bgm: [{id: theme, source: bgm.wav, anchor: いない, at: 0}]
  se: []
""")
    with pytest.raises(episodes.EpisodeError, match="錨"):
        build.step_mix(ep, CFG)


def test_曲が錨のコーナーより短ければ警告だけ出して止まらない(ep, capsys):
    silence(ep["00_raw"] / "op.wav", 4)
    silence(ep["00_raw"] / "talk.wav", 6)
    sine(ep["01_clean"] / "clean.wav", 10, amp=0.2)
    sine(ep["00_raw"] / "bgm.wav", 1)              # talk（6秒）よりずっと短い曲
    timeline_yml(ep, TWO_CORNERS.format(at=0))
    write_clean_json(ep)

    build.step_mix(ep, CFG)                         # 止まらない

    assert (ep["01_mix"] / "mix.wav").exists()
    assert "曲が先に終わります" in capsys.readouterr().out


def test_曲が短いという警告はseには出ない(ep, capsys):
    """レビューで指摘: 短さの警告は BGM だけ。SE は短く鳴って終わるのが普通"""
    silence(ep["00_raw"] / "op.wav", 4)
    silence(ep["00_raw"] / "talk.wav", 6)
    sine(ep["01_clean"] / "clean.wav", 10, amp=0.2)
    sine(ep["00_raw"] / "pin.wav", 1)               # talk（6秒）よりずっと短い SE
    timeline_yml(ep, """version: 1
lanes:
  main:
    - {id: op, source: op.wav, gap: 0}
    - {id: talk, source: talk.wav, gap: 0}
  bgm: []
  se:
    - {id: pin, source: pin.wav, anchor: talk, at: 0}
""")
    write_clean_json(ep)

    build.step_mix(ep, CFG)

    assert "曲が先に終わります" not in capsys.readouterr().out


def test_曲の終わりが番組の末尾を超えると切れることをログに出す(ep, capsys):
    silence(ep["00_raw"] / "op.wav", 4)
    silence(ep["00_raw"] / "talk.wav", 6)
    sine(ep["01_clean"] / "clean.wav", 10, amp=0.2)
    sine(ep["00_raw"] / "bgm.wav", 8)               # at=4 だと 4+8=12秒。番組は10秒しかない
    timeline_yml(ep, TWO_CORNERS.format(at=4))
    write_clean_json(ep)

    build.step_mix(ep, CFG)                          # 止まらない

    assert (ep["01_mix"] / "mix.wav").exists()
    assert "末尾が切れます" in capsys.readouterr().out


def test_bgmもseもファイルが壊れているとidを含めて断る(ep):
    silence(ep["00_raw"] / "op.wav", 4)
    silence(ep["00_raw"] / "talk.wav", 6)
    sine(ep["01_clean"] / "clean.wav", 10, amp=0.2)
    (ep["00_raw"] / "bgm.wav").write_bytes(b"not really audio")
    timeline_yml(ep, TWO_CORNERS.format(at=0))
    write_clean_json(ep)

    with pytest.raises(ValueError, match="theme の音源の長さが読めません"):
        build.step_mix(ep, CFG)


# ---------------------------------------------------------------- mix: カットとの組み合わせ

def test_cutwavがあるだけでは断らない(ep):
    """`step_cut` は cuts が空でも毎回 cut.wav を書く。**それだけで止めない**
    （2026-09-26 のレビューで見つかった不具合。cut.wav の有無ではなく、長さで確かめる）。
    """
    silence(ep["00_raw"] / "op.wav", 4)
    silence(ep["00_raw"] / "talk.wav", 6)
    sine(ep["01_clean"] / "clean.wav", 10, amp=0.2)   # 実際にカットされていない
    sine(ep["00_raw"] / "bgm.wav", 2)
    timeline_yml(ep, TWO_CORNERS.format(at=0))
    (ep["01_cut"] / "cut.wav").write_bytes(b"dummy")   # cuts が空でも書かれるファイル
    write_clean_json(ep)                                # 実際は削れていない（head=0, tail=0）

    build.step_mix(ep, CFG)                             # 止まらない

    assert (ep["01_mix"] / "mix.wav").exists()


def test_本編の長さが合わなければ断る(ep):
    """カットやエコーで本編の長さが変わっているのに、位置の変換をしていない場合。"""
    silence(ep["00_raw"] / "op.wav", 4)
    silence(ep["00_raw"] / "talk.wav", 6)
    sine(ep["01_clean"] / "clean.wav", 10, amp=0.2)
    sine(ep["00_raw"] / "bgm.wav", 2)
    timeline_yml(ep, TWO_CORNERS.format(at=0))
    # 生の長さ(10秒)から5秒引いた記録＝本当は5秒のはずなのに、実際は10秒のまま
    write_clean_json(ep, head_removed=5.0, tail_removed=0.0)

    with pytest.raises(ValueError, match="本編の長さが合いません"):
        build.step_mix(ep, CFG)


def test_clean_jsonが無ければ確かめずに警告だけ出す(ep, capsys):
    silence(ep["00_raw"] / "op.wav", 4)
    silence(ep["00_raw"] / "talk.wav", 6)
    sine(ep["01_clean"] / "clean.wav", 10, amp=0.2)
    sine(ep["00_raw"] / "bgm.wav", 2)
    timeline_yml(ep, TWO_CORNERS.format(at=0))
    # clean.json を書かない

    build.step_mix(ep, CFG)                             # 止まらない

    assert (ep["01_mix"] / "mix.wav").exists()
    assert "確かめられません" in capsys.readouterr().out


# ---------------------------------------------------------------- mix: ラウドネスをそろえる

def test_曲は喋りと同じラウドネスにそろえる(ep):
    """曲（bgm）だけを、build.py が組む filter を通して測る。"""
    bgm = sine(ep["00_raw"] / "bgm.wav", 6, amp=0.9)
    clip = {"id": "theme", "anchor": "op"}
    filters = build._mix_overlay_chain(clip, "bgm", CFG)
    assert any(f.startswith("loudnorm=") for f in filters)

    out = ep["01_mix"] / "measured.wav"
    build.run(["ffmpeg", "-y", "-i", str(bgm), "-af", ",".join(filters),
               "-ar", "48000", "-ac", "1", str(out)])

    measured = _integrated_loudness(out)
    assert measured == pytest.approx(-14.0, abs=1.5)


def _integrated_loudness(path):
    proc = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    lines = [line for line in proc.stderr.splitlines() if line.strip().startswith("I:")]
    assert lines, f"ebur128 の出力から I: が見つかりません:\n{proc.stderr[-500:]}"
    return float(lines[-1].split()[1])


# ---------------------------------------------------------------- mix: 音量カーブ

def test_音量カーブで下げた区間だけ音量が下がる(ep):
    src = sine(ep["01_mix"] / "src.wav", 5, amp=0.5)
    points = [{"time": 0, "volume": 1.0}, {"time": 2.0, "volume": 1.0},
              {"time": 2.2, "volume": 0.25}, {"time": 4.0, "volume": 0.25}]
    expr = build.volume_expr(points)

    out = ep["01_mix"] / "with_volume.wav"
    build.run(["ffmpeg", "-y", "-i", str(src), "-af", expr,
               "-ar", "48000", "-ac", "1", str(out)])

    base = rms(out, 0.5, 1.5)      # まだ 1.0 のところ
    dropped = rms(out, 2.5, 3.5)   # 0.25 に下げたところ
    ratio = dropped / base
    assert ratio == pytest.approx(0.25, abs=0.03)


# ---------------------------------------------------------------- 動画化: 枠でない回は mix を待たない

def make_image(path):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", "color=c=blue:s=64x64:d=1", "-frames:v", "1", str(path)], check=True)


def _video_cfg(ep, episode=99):
    (ep["dir"] / "04_video").mkdir()
    ep["04_video"] = ep["dir"] / "04_video"
    (ep["dir"] / "assets").mkdir()
    make_image(ep["dir"] / "assets" / "pic.png")
    return {**CFG, "episode": episode, "images": [{"file": "assets/pic.png", "duration": "full"}]}


def test_枠でない回はvideoが整音の音を使う(ep, capsys):
    """timeline.yml が無い回（ep01 のような回）は、動画化はミックスを待たない
    （2026-09-26・ユーザーの判断）。"""
    sine(ep["01_clean"] / "clean.wav", 2, amp=0.2)
    cfg = _video_cfg(ep)
    # timeline.yml を書かない・01_mix/mix.wav も作らない

    build.step_video(ep, cfg)

    assert (ep["04_video"] / "ep99.mp4").exists()
    assert "曲が無い回なので、整音の音を使います" in capsys.readouterr().out


def test_枠の回はmixが無いと理由を出して断る(ep):
    silence(ep["00_raw"] / "op.wav", 2)
    sine(ep["01_clean"] / "clean.wav", 2, amp=0.2)
    timeline_yml(ep, "version: 1\nlanes:\n  main: [{id: op, source: op.wav, gap: 0}]\n"
                     "  bgm: []\n  se: []\n")
    cfg = _video_cfg(ep)
    # 01_mix/mix.wav を作らない

    with pytest.raises(FileNotFoundError, match="先にミックス"):
        build.step_video(ep, cfg)


def test_枠の回はmixがあればそれを使う(ep):
    silence(ep["00_raw"] / "op.wav", 2)
    sine(ep["01_clean"] / "clean.wav", 2, amp=0.2)
    sine(ep["01_mix"] / "mix.wav", 2, amp=0.2)
    timeline_yml(ep, "version: 1\nlanes:\n  main: [{id: op, source: op.wav, gap: 0}]\n"
                     "  bgm: []\n  se: []\n")
    cfg = _video_cfg(ep)

    build.step_video(ep, cfg)

    assert (ep["04_video"] / "ep99.mp4").exists()
