"""build.py のメタデータまわりのテスト（章の扱いと、文字起こしの元の文字）。"""

import json

import build


# ---------------------------------------------------------------- 概要欄と章

def test_概要欄のうしろに目次をつなげる():
    got = build.youtube_description({
        "description": "本文です。\n訂正歓迎です。",
        "chapters": [{"seconds": 125, "label": "本題"}, {"seconds": 0, "label": "あいさつ"}],
    })
    assert got == "本文です。\n訂正歓迎です。\n\n--- 目次 ---\n0:00 あいさつ\n2:05 本題"


def test_章は時刻の順に並べ直す():
    got = build.youtube_description({
        "description": "本文",
        "chapters": [{"seconds": 60, "label": "後"}, {"seconds": 10, "label": "先"}],
    })
    assert got.index("先") < got.index("後")


def test_章が無ければ概要欄だけ():
    assert build.youtube_description({"description": "本文だけ", "chapters": []}) == "本文だけ"
    assert build.youtube_description({"description": "本文だけ"}) == "本文だけ"


def test_概要欄が空でも落ちない():
    assert build.youtube_description({}) == ""
    assert build.youtube_description({"description": None, "chapters": None}) == ""


def test_概要欄の末尾の空白は落とす():
    got = build.youtube_description({
        "description": "本文\n\n\n", "chapters": [{"seconds": 0, "label": "あ"}],
    })
    assert got.startswith("本文\n\n--- 目次 ---")


# ---------------------------------------------------------------- 文字起こしの元の文字

def test_文字起こしは元の文字を各行に残す(tmp_path, monkeypatch):
    """聴きながら直せるように、直す前の文字を持たせる。"""
    monkeypatch.setattr(build, "transcribe_file", lambda src, cfg: {
        "segments": [{"start": 0.0, "end": 5.0, "text": "こんばんは"}],
        "full_text": "こんばんは",
    })
    ep = {"01_clean": tmp_path, "02_text": tmp_path}
    (tmp_path / "clean.wav").write_bytes(b"a")

    build.step_transcribe(ep, {})

    saved = json.loads((tmp_path / "transcript.json").read_text(encoding="utf-8"))
    assert saved["segments"][0]["original"] == "こんばんは"


def test_古い概要欄には目次を足さない():
    """#7 より前の meta.json は、概要欄にすでに目次が焼き込まれている。"""
    old = {
        "description": "本文です。\n\n--- 目次 ---\n0:00 あいさつ",
        "chapters": [{"seconds": 0, "label": "あいさつ"}],
    }
    got = build.youtube_description(old)
    assert got.count("--- 目次 ---") == 1
    assert got == old["description"]


# ---------------------------------------------------------------- くわしいログの書き出し

def test_外部コマンドの出力はくわしいログに残る(tmp_path, capsys):
    """画面には「$ ふしぎ ...」だけ、ファイルには出力がぜんぶ残る。"""
    log = tmp_path / "clean.log"
    build.open_detail_log(log)
    try:
        build.run(["echo", "こんにちは"])
    finally:
        build.close_detail_log()

    shown = capsys.readouterr().out
    assert shown.strip() == "$ echo ..."          # 画面はこれだけ
    saved = log.read_text(encoding="utf-8")
    assert "$ echo こんにちは" in saved           # ファイルには命令も
    assert "こんにちは" in saved                  # 出力も


def test_ログが書けなくても工程は止まらない(tmp_path, capsys):
    build.open_detail_log(tmp_path / "ありません" / "x" / "clean.log" / "だめ" / "log")
    out = capsys.readouterr().out
    build.close_detail_log()
    assert "くわしいログを残せません" in out or out == ""
