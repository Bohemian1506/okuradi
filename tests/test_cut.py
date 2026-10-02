"""build.py の cut 工程（config.yml の cuts）と、整音（step_clean）が使う音の選び方。

#225: cuts を空に戻しても、古い 01_cut/cut.wav を使い続けない。
枠の回（timeline.yml がある回）は、カットが join_sources で済んでいるので、
そもそも 01_cut/cut.wav を見ない。
"""

import json
import subprocess

import pytest

import build


def sine(path, seconds, rate=48000):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"sine=frequency=440:duration={seconds}:sample_rate={rate}",
         "-ac", "1", "-c:a", "pcm_s16le", str(path)], check=True)
    return path


@pytest.fixture
def ep(tmp_path):
    made = {"dir": tmp_path, "name": "ep98", "root": tmp_path}
    for sub in ["00_raw", "01_cut", "01_clean"]:
        made[sub] = tmp_path / sub
        made[sub].mkdir()
    return made


CFG = {"cuts": [], "audio": {"denoise": False, "trim_silence": False}}


def clean_json(ep):
    return json.loads((ep["01_clean"] / "clean.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- step_cut がサイドカーを残す

def test_cutが記録を残す(ep):
    sine(ep["00_raw"] / "rec.wav", 10)
    build.step_cut(ep, {**CFG, "cuts": [[2, 4]]})

    record = json.loads((ep["01_cut"] / "cut.json").read_text(encoding="utf-8"))
    assert record["cuts"] == [[2.0, 4.0]]
    assert build.audio_duration(ep["01_cut"] / "cut.wav") == pytest.approx(8.0, abs=0.02)


def test_cutsが空でも記録を残す(ep):
    sine(ep["00_raw"] / "rec.wav", 10)
    build.step_cut(ep, CFG)

    record = json.loads((ep["01_cut"] / "cut.json").read_text(encoding="utf-8"))
    assert record["cuts"] == []


# ---------------------------------------------------------------- #225: 古い cut.wav を使い続けない

def test_cutsが合っていればcutwavを使う(ep):
    sine(ep["00_raw"] / "rec.wav", 10)
    cfg = {**CFG, "cuts": [[2, 4]]}
    build.step_cut(ep, cfg)

    build.step_clean(ep, cfg)

    assert clean_json(ep)["source"] == "cut.wav"


def test_cutsを空に戻したら古いcutwavを使わない(ep, capsys):
    """#225: 一度カットを使うと、cuts を空に戻しても古い cut.wav を使い続けていた。"""
    sine(ep["00_raw"] / "rec.wav", 10)
    build.step_cut(ep, {**CFG, "cuts": [[2, 4]]})   # cut.wav は 8秒のまま残る

    build.step_clean(ep, CFG)                        # cuts を空に戻して、cut をやり直さず整音だけ

    assert clean_json(ep)["source"] == "rec.wav"
    assert build.audio_duration(ep["01_clean"] / "clean.wav") == pytest.approx(10.0, abs=0.3)
    assert "cuts を変えた" in capsys.readouterr().out


def test_cutsを変えたら古いcutwavを使わない(ep):
    sine(ep["00_raw"] / "rec.wav", 10)
    build.step_cut(ep, {**CFG, "cuts": [[2, 4]]})

    build.step_clean(ep, {**CFG, "cuts": [[5, 6]]})   # 違うカットに変えた

    assert clean_json(ep)["source"] == "rec.wav"


def test_サイドカーが無いcutwavは使わない(ep):
    """前のバージョンで作った cut.wav（サイドカーが無い）は、安全側に倒して使わない。"""
    sine(ep["00_raw"] / "rec.wav", 10)
    (ep["01_cut"] / "cut.wav").write_bytes(b"dummy")

    build.step_clean(ep, CFG)

    assert clean_json(ep)["source"] == "rec.wav"


def test_記録が無いcutwavは記録が無いと言う(ep, capsys):
    """レビュー指摘: 記録（cut.json）が無いだけなのに「cuts を変えたので」と
    事実と違う理由が出ていた（ep01 のような、前のバージョンで作った cut.wav）。"""
    sine(ep["00_raw"] / "rec.wav", 10)
    (ep["01_cut"] / "cut.wav").write_bytes(b"dummy")

    build.step_clean(ep, CFG)

    out = capsys.readouterr().out
    assert "記録（cut.json）が無いので" in out
    assert "cuts を変えたので" not in out


def test_カット未実行なら今までどおり(ep, capsys):
    sine(ep["00_raw"] / "rec.wav", 10)

    build.step_clean(ep, CFG)

    assert clean_json(ep)["source"] == "rec.wav"
    assert "カット未実行のため" in capsys.readouterr().out


# ---------------------------------------------------------------- 枠の回は cut.wav を見ない

def test_枠の回はcutwavがあっても見ない(ep):
    sine(ep["00_raw"] / "op.wav", 10)
    (ep["dir"] / "timeline.yml").write_text(
        "version: 1\nlanes:\n  main: [{id: op, source: op.wav, gap: 0}]\n"
        "  bgm: []\n  se: []\n", encoding="utf-8")
    # 前のバージョンで作った・手で置いたなどで、たまたま cut.wav が残っているとする
    (ep["01_cut"] / "cut.wav").write_bytes(b"dummy")

    build.step_clean(ep, CFG)

    assert clean_json(ep)["source"] == "op.wav"


def test_枠の回でconfigのcutsが空でなければ静かに無視しない(ep, capsys):
    """レビュー指摘: 枠に切り替わったのに config.yml の cuts が残っていても、
    黙って無視していた（静かに失敗させない。CLAUDE.md）。"""
    sine(ep["00_raw"] / "op.wav", 10)
    (ep["dir"] / "timeline.yml").write_text(
        "version: 1\nlanes:\n  main: [{id: op, source: op.wav, gap: 0}]\n"
        "  bgm: []\n  se: []\n", encoding="utf-8")

    build.step_clean(ep, {**CFG, "cuts": [[1, 2]]})

    out = capsys.readouterr().out
    assert "config.yml の cuts" in out
    assert "使いません" in out


def test_枠の回でconfigのcutsが空ならログに出さない(ep, capsys):
    sine(ep["00_raw"] / "op.wav", 10)
    (ep["dir"] / "timeline.yml").write_text(
        "version: 1\nlanes:\n  main: [{id: op, source: op.wav, gap: 0}]\n"
        "  bgm: []\n  se: []\n", encoding="utf-8")

    build.step_clean(ep, CFG)

    assert "config.yml の cuts" not in capsys.readouterr().out


def test_枠の回のclean_jsonにカットの記録が残る(ep):
    """#85 の6段目のレビュー対応: `web/episodes.py`・`web/media.py` の「古い」判定が
    これを読む。"""
    sine(ep["00_raw"] / "op.wav", 10)
    (ep["dir"] / "timeline.yml").write_text(
        "version: 1\nlanes:\n  main:\n    - id: op\n      source: op.wav\n      gap: 0\n"
        "      edits: [{start: 1.0, end: 2.0, kind: cut}]\n  bgm: []\n  se: []\n",
        encoding="utf-8")

    build.step_clean(ep, CFG)

    assert clean_json(ep)["cuts"] == {"op": [[1.0, 2.0]]}
