"""build.py の step_scan: 枠の回で、カットの記録と下見の並び（layout）を残す
（#85 の6段目のレビュー対応）。

Whisper は重いので `transcribe_file` を差し替える（`tests/test_meta.py` と同じやり方）。
"""

import json
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
    made = {"dir": tmp_path, "name": "ep98", "root": tmp_path}
    for sub in ["00_raw", "01_cut", "01_clean", "02_text"]:
        made[sub] = tmp_path / sub
        made[sub].mkdir()
    return made


@pytest.fixture(autouse=True)
def fake_transcribe(monkeypatch):
    monkeypatch.setattr(build, "transcribe_file", lambda src, cfg: {
        "segments": [], "full_text": "",
    })


def timeline_yml(ep, body):
    (ep["dir"] / "timeline.yml").write_text(body, encoding="utf-8")


def scan_json(ep):
    return json.loads((ep["02_text"] / "scan.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- cuts の記録

def test_カットが無ければcutsは空の並び(ep):
    sine(ep["00_raw"] / "a.wav", 2)
    timeline_yml(ep, "version: 1\nlanes:\n  main: [{id: a, source: a.wav, gap: 0}]\n"
                      "  bgm: []\n  se: []\n")
    build.step_scan(ep, {})
    assert scan_json(ep)["cuts"] == {"a": []}


def test_カットがあればcutsに残る(ep):
    sine(ep["00_raw"] / "a.wav", 4)
    timeline_yml(ep, "version: 1\nlanes:\n  main:\n    - id: a\n      source: a.wav\n"
                      "      gap: 0\n      edits: [{start: 1.0, end: 2.0, kind: cut}]\n"
                      "  bgm: []\n  se: []\n")
    build.step_scan(ep, {})
    assert scan_json(ep)["cuts"] == {"a": [[1.0, 2.0]]}


def test_枠でない回はcutsが空でlayoutも無い(ep):
    sine(ep["00_raw"] / "a.wav", 2)
    build.step_scan(ep, {})
    data = scan_json(ep)
    assert data["cuts"] == {}
    assert "layout" not in data


# ---------------------------------------------------------------- 下見の並び（layout）

def test_1本の枠でもlayoutが出る(ep):
    """cut edits が無い1本の回は join を通らないが（find_raw の最適化）、layout はそれでも出る。"""
    sine(ep["00_raw"] / "a.wav", 2)
    timeline_yml(ep, "version: 1\nlanes:\n  main: [{id: a, source: a.wav, gap: 0}]\n"
                      "  bgm: []\n  se: []\n")
    build.step_scan(ep, {})
    layout = scan_json(ep)["layout"]
    assert len(layout) == 1
    row = layout[0]
    assert row["id"] == "a"
    assert row["start"] == 0.0
    assert row["end"] == pytest.approx(2.0, abs=0.05)
    assert row["keeps"] == [[0.0, pytest.approx(2.0, abs=0.05)]]


def test_layoutは繋いだ音での開始秒とkeepsを持つ(ep):
    sine(ep["00_raw"] / "a.wav", 4)
    sine(ep["00_raw"] / "b.wav", 2, freq=660)
    timeline_yml(ep, "version: 1\nlanes:\n  main:\n"
                      "    - id: a\n      source: a.wav\n      gap: 0\n"
                      "      edits: [{start: 1.0, end: 2.0, kind: cut}]\n"
                      "    - id: b\n      source: b.wav\n      gap: 0.5\n"
                      "  bgm: []\n  se: []\n")
    build.step_scan(ep, {})
    layout = scan_json(ep)["layout"]

    a, b = layout
    assert a["id"] == "a"
    assert a["start"] == 0.0
    assert a["end"] == pytest.approx(3.0, abs=0.05)          # 4秒 - 1秒カット
    assert a["keeps"] == [[0.0, pytest.approx(1.0, abs=0.05)],
                          [2.0, pytest.approx(4.0, abs=0.05)]]

    assert b["id"] == "b"
    assert b["start"] == pytest.approx(3.5, abs=0.05)        # a(3.0) + gap(0.5)
    assert b["end"] == pytest.approx(5.5, abs=0.05)
    assert b["keeps"] == [[0.0, pytest.approx(2.0, abs=0.05)]]


def test_下見の音の長さとlayoutの終わりがそろう(ep):
    """layout の最後のクリップの end が、実際に下見をかけた音（joined.wav）の長さと合うこと。"""
    sine(ep["00_raw"] / "a.wav", 3)
    sine(ep["00_raw"] / "b.wav", 2, freq=660)
    timeline_yml(ep, "version: 1\nlanes:\n  main:\n"
                      "    - id: a\n      source: a.wav\n      gap: 0\n"
                      "    - id: b\n      source: b.wav\n      gap: 0\n"
                      "  bgm: []\n  se: []\n")
    build.step_scan(ep, {})
    data = scan_json(ep)
    assert data["layout"][-1]["end"] == pytest.approx(data["duration"], abs=0.05)
