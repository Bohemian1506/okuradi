"""web/timeline.py のテスト。

決めたことは #79 の論点1（2026-09-22）。ここで守るのは3つ。

- **錨から番組の時刻が出る。** クリップの長さが変わったら、後ろとそこに付いた SE が一緒に動く
- **おかしな形を黙って通さない**（CLAUDE.md「静かに失敗させない」）
- **config.yml と timeline.yml のキーが混ざらない**
"""

import pytest

from web import episodes, timeline


def tl(main=None, bgm=None, se=None):
    return {"version": 1, "lanes": {
        "main": main if main is not None else [
            {"id": "op", "source": "00_raw/op.wav", "gap": 0},
            {"id": "imasara", "source": "00_raw/zunda.wav", "gap": 1.0},
        ],
        "bgm": bgm or [],
        "se": se or [],
    }}


DUR = {"op": 240.0, "imasara": 473.308}


# ---------------------------------------------------------------- 番組の時刻

def test_本編のクリップは間をあけて順に並ぶ():
    got = timeline.positions(tl(), DUR)
    assert got["op"] == 0
    assert got["imasara"] == 241.0          # 240 + 間 1.0


def test_SEはクリップの先頭からの秒数で置かれる():
    data = tl(se=[{"id": "pin", "source": "assets/pin.wav", "anchor": "imasara", "at": 12.5}])
    assert timeline.positions(data, DUR)["pin"] == 253.5   # 241.0 + 12.5


def test_前のクリップが伸びるとSEも一緒に動く():
    """これが錨を使う理由。絶対秒で持っていたら、ここで書き直しになる。"""
    data = tl(se=[{"id": "pin", "source": "assets/pin.wav", "anchor": "imasara", "at": 12.5}])
    before = timeline.positions(data, DUR)
    after = timeline.positions(data, {**DUR, "op": 300.0})   # OP を録り直して60秒伸びた
    assert after["imasara"] - before["imasara"] == 60.0
    assert after["pin"] - before["pin"] == 60.0              # SE も同じだけ動く


def test_クリップの中の秒数を番組の時刻に直す():
    assert timeline.program_seconds(tl(), DUR, "imasara", 30.0) == 271.0


def test_番組全体の長さは本編と間の足し算():
    assert timeline.total_seconds(tl(), DUR) == 714.308      # 240 + 1.0 + 473.308


def test_長さが分からないクリップがあれば断る():
    with pytest.raises(episodes.EpisodeError, match="長さが分かりません"):
        timeline.positions(tl(), {"op": 240.0})


# ---------------------------------------------------------------- 検証

def test_錨が本編に無ければ断る():
    data = tl(se=[{"id": "pin", "source": "a.wav", "anchor": "いない", "at": 1}])
    with pytest.raises(episodes.EpisodeError, match="錨"):
        timeline.validate(data)


def test_錨が書いていなければ断る():
    data = tl(bgm=[{"id": "b1", "source": "a.wav", "at": 1}])
    with pytest.raises(episodes.EpisodeError, match="錨がありません"):
        timeline.validate(data)


def test_idが重なっていれば断る():
    data = tl(main=[{"id": "op", "source": "a.wav"}, {"id": "op", "source": "b.wav"}])
    with pytest.raises(episodes.EpisodeError, match="重なって"):
        timeline.validate(data)


def test_音源が無ければ断る():
    with pytest.raises(episodes.EpisodeError, match="音源がありません"):
        timeline.validate(tl(main=[{"id": "op"}]))


def test_知らないレーンは断る():
    with pytest.raises(episodes.EpisodeError, match="知らないレーン"):
        timeline.validate({"version": 1, "lanes": {"talk": []}})


def test_versionが違えば断る():
    with pytest.raises(episodes.EpisodeError, match="version"):
        timeline.validate({"version": 2, "lanes": {}})


def test_編集点の終了が開始より前なら断る():
    data = tl(main=[{"id": "op", "source": "a.wav",
                     "edits": [{"kind": "cut", "start": 10, "end": 5}]}])
    with pytest.raises(episodes.EpisodeError, match="終了が開始より後"):
        timeline.validate(data)


def test_編集点は開始で並べ直される():
    data = tl(main=[{"id": "op", "source": "a.wav", "edits": [
        {"kind": "echo", "start": 30, "end": 40}, {"kind": "cut", "start": 10, "end": 20}]}])
    got = timeline.validate(data)["lanes"]["main"][0]["edits"]
    assert [r["start"] for r in got] == [10, 30]


def test_カットとエコーが同じ並びに入る():
    """1つの並びに種類を付けて持つ（#79 の論点1）。原点が違うまま別々に持たない。"""
    data = tl(main=[{"id": "op", "source": "a.wav", "edits": [
        {"kind": "cut", "start": 180, "end": 360},
        {"kind": "echo", "start": 12.5, "end": 20, "preset": "light"}]}])
    got = timeline.validate(data)["lanes"]["main"][0]["edits"]
    assert [r["kind"] for r in got] == ["echo", "cut"]
    assert got[0]["preset"] == "light"


def test_知らない種類は断る():
    data = tl(main=[{"id": "op", "source": "a.wav",
                     "edits": [{"kind": "ぼかす", "start": 1, "end": 2}]}])
    with pytest.raises(episodes.EpisodeError, match="種類"):
        timeline.validate(data)


def test_種類を書き忘れたら断る():
    data = tl(main=[{"id": "op", "source": "a.wav", "edits": [{"start": 1, "end": 2}]}])
    with pytest.raises(episodes.EpisodeError, match="種類"):
        timeline.validate(data)


def test_知らないキーはそのまま残す():
    """あとから表情差分・フェードなどを足せるように（README の設計メモ）。"""
    data = tl(main=[{"id": "op", "source": "a.wav", "fade_in": 0.5}])
    assert timeline.validate(data)["lanes"]["main"][0]["fade_in"] == 0.5


# ---------------------------------------------------------------- 2つのファイルを混ぜない

@pytest.mark.parametrize("key", ["segments", "series_rules", "youtube", "episode"])
def test_configの項目が混ざっていたら断る(key):
    data = tl()
    data[key] = "なにか"
    with pytest.raises(episodes.EpisodeError, match="混ざって"):
        timeline.validate(data)


def test_人が書く項目は全部はじける():
    """CONFIG_ONLY の取りこぼしを防ぐ。

    **実物の ep01/config.yml は読まない。** ユーザーが GUI で書き換えると前提が動くため
    （次の PR で確かめるために手で lanes: を足したら、無関係な理由で落ちる）。
    """
    for key in timeline.CONFIG_ONLY:
        data = tl()
        data[key] = "なにか"
        with pytest.raises(episodes.EpisodeError, match="混ざって"):
            timeline.validate(data)


# ---------------------------------------------------------------- 読み書き

def test_タイムラインが無い回はNoneを返す(tmp_path):
    assert timeline.read(tmp_path) is None


def test_書いたものを読み直せる(tmp_path):
    saved = timeline.save(tmp_path, tl(se=[
        {"id": "pin", "source": "assets/pin.wav", "anchor": "op", "at": 3.25}]))
    again = timeline.read(tmp_path)
    assert again == saved
    assert again["lanes"]["se"][0]["at"] == 3.25


def test_壊れたファイルは理由をつけて断る(tmp_path):
    (tmp_path / "timeline.yml").write_text("lanes: [壊れて\n", encoding="utf-8")
    with pytest.raises(episodes.EpisodeError, match="読めません"):
        timeline.read(tmp_path)


# ---------------------------------------------------------------- レビューで見つかった分

def test_全体の長さと最後のクリップの終わりが一致する():
    """足し算を2か所に置いていたとき、丸め方の違いで 0.0013秒 食い違った。"""
    seq = [(0.34, 456.705482), (1.083, 147.547683), (0.292, 335.3775),
           (0.297, 10.131609), (0.289, 232.495655)]
    main = [{"id": f"c{i}", "source": f"{i}.wav", "gap": g} for i, (g, _) in enumerate(seq)]
    durs = {f"c{i}": d for i, (_, d) in enumerate(seq)}
    data = {"version": 1, "lanes": {"main": main, "bgm": [], "se": []}}
    pos = timeline.positions(data, durs)
    assert timeline.total_seconds(data, durs) == round(pos["c4"] + durs["c4"], 3)


def test_本編が空なら全体の長さは0():
    assert timeline.total_seconds(tl(main=[]), {}) == 0.0


def test_編集点が生音の長さをはみ出していたら断る():
    data = tl(main=[{"id": "op", "source": "a.wav",
                     "edits": [{"kind": "cut", "start": 100, "end": 9999}]}])
    with pytest.raises(episodes.EpisodeError, match="はみ出して"):
        timeline.check_edits(data, {"op": 50.0, "imasara": 10.0})


def test_編集点が生音の長さに収まっていれば通る():
    data = tl(main=[{"id": "op", "source": "a.wav",
                     "edits": [{"kind": "echo", "start": 10, "end": 20}]}])
    assert timeline.check_edits(data, {"op": 50.0, "imasara": 10.0})


def test_はみ出しの検証に渡すのは生音の長さ():
    """`check_edits` は生音の長さ、`positions` は出来上がりの長さ。混ぜないことを形で示す。"""
    data = tl(main=[{"id": "op", "source": "a.wav", "gap": 0,
                     "edits": [{"kind": "cut", "start": 100, "end": 200}]}])
    # 生音は 600秒。100秒カットしたので、出来上がりは 500秒
    assert timeline.check_edits(data, {"op": 600.0})
    assert timeline.total_seconds(data, {"op": 500.0}) == 500.0
    # 生音の長さを positions に渡すと、番組が100秒長いことになってしまう
    assert timeline.total_seconds(data, {"op": 600.0}) == 600.0


def test_本編以外に編集点は書けない():
    """黙って残すと、値の形すら確かめないまま通っていた（レビューで見つかった）。"""
    data = tl(bgm=[{"id": "b1", "source": "b.wav", "anchor": "op", "at": 0,
                    "edits": "完全に壊れた文字列"}])
    with pytest.raises(episodes.EpisodeError, match="書けません"):
        timeline.validate(data)
