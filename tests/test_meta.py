"""build.py のメタデータまわりのテスト（章の扱いと、文字起こしの元の文字）。"""

import json

import pytest
import yaml

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


# ---------------------------------------------------------------- claude を呼べないとき

def test_claude_が無ければ理由を言って断る(monkeypatch):
    """subprocess.run の例外も RuntimeError にして、画面まで理由を届ける。"""
    import subprocess

    def missing(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "claude")

    monkeypatch.setattr(build.subprocess, "run", missing)
    with pytest.raises(RuntimeError, match="claude コマンドが見つかりません"):
        build.call_claude("あ")


def test_claude_が時間切れなら理由を言って断る(monkeypatch):
    import subprocess

    def slow(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=600)

    monkeypatch.setattr(build.subprocess, "run", slow)
    with pytest.raises(RuntimeError, match="10分を過ぎました"):
        build.call_claude("あ")


# ---------------------------------------------------------------- メタデータの指示文

def _prompt_of(tmp_path, monkeypatch, segments, rules):
    """step_meta を動かし、claude に渡った指示文を返す。"""
    ep_dir = tmp_path / "ep99"
    ep_dir.mkdir()
    (ep_dir / "config.yml").write_text(yaml.safe_dump(
        {"episode": 99, "concept": "テスト番組", "segments": segments, "series_rules": rules},
        allow_unicode=True, sort_keys=False), encoding="utf-8")
    ep, cfg = build.load_episode(tmp_path, "ep99")
    (ep["02_text"] / "transcript.json").write_text(json.dumps(
        {"segments": [{"start": 0, "text": "こんばんは"}], "full_text": "こんばんは"},
        ensure_ascii=False), encoding="utf-8")

    sent = {}

    def fake(prompt, schema=None, **kw):
        sent["prompt"] = prompt
        return {"structured_output": {"title": "T", "description": "D",
                                      "chapters": [], "tags": []}}

    monkeypatch.setattr(build, "call_claude", fake)
    build.step_meta(ep, cfg)
    return sent["prompt"]


def test_章の数を指示文に書かない(tmp_path, monkeypatch):
    prompt = _prompt_of(
        tmp_path, monkeypatch,
        [{"series": "imasara", "theme": "OSI"}],
        {"imasara": {"label": "今さら聞けない", "title_hint": "「今さら聞けない○○」の形"}},
    )
    assert "3〜6" not in prompt
    assert "1対1" in prompt


def test_コーナーが増えれば指示文のコーナー欄も増える(tmp_path, monkeypatch):
    rules = {"op": {"label": "OP"},
             "imasara": {"label": "今さら聞けない", "title_hint": "「今さら聞けない○○」の形"},
             "ed": {"label": "ED"}}
    segments = [{"series": "op", "theme": "オープニング"},
                {"series": "imasara", "theme": "OSI"},
                {"series": "ed", "theme": "おわり"}]
    prompt = _prompt_of(tmp_path, monkeypatch, segments, rules)
    corners = [line for line in prompt.splitlines() if line.startswith("- 枠: ")]
    assert len(corners) == 3
    assert corners[0] == "- 枠: OP / テーマ: オープニング"


def test_タイトルの規則には規則のあるコーナーだけ出す(tmp_path, monkeypatch):
    """OP・告知・ED には title_hint が無い。空の行を出さない。"""
    rules = {"op": {"label": "OP"},
             "imasara": {"label": "今さら聞けない", "title_hint": "「今さら聞けない○○」の形"}}
    segments = [{"series": "op", "theme": "オープニング"},
                {"series": "imasara", "theme": "OSI"}]
    prompt = _prompt_of(tmp_path, monkeypatch, segments, rules)
    rules_block = prompt.split("# タイトルの規則\n")[1].split("\n# ")[0]
    assert rules_block.strip() == "- 今さら聞けない: 「今さら聞けない○○」の形"
