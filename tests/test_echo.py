"""build.py のエコー（区間だけに響きを足す）のテスト。

ffmpeg は動かさない。区間の整え方と、組み立てるフィルタグラフを確かめる。
"""

import build


def echoes(*rows):
    return [{"start": s, "end": e, "preset": p} for s, e, p in rows]


# ---------------------------------------------------------------- 区間の整え方

def test_プリセットがなしや知らない名前ならかけない():
    assert build.normalize_echoes(echoes((5, 9, "none")), 60) == []
    assert build.normalize_echoes(echoes((5, 9, "")), 60) == []
    assert build.normalize_echoes(echoes((5, 9, "しらない")), 60) == []


def test_短すぎる区間は飛ばす():
    assert build.normalize_echoes(echoes((5, 5.1, "light")), 60) == []


def test_音の外にはみ出したら中に収める():
    got = build.normalize_echoes(echoes((-3, 70, "light")), 60)
    assert got == [(0.0, 60, "light")]


def test_先頭や末尾のすぐ近くなら端まで伸ばす():
    got = build.normalize_echoes(echoes((0.1, 59.95, "hall")), 60)
    assert got == [(0.0, 60, "hall")]


def test_近すぎる区間は飛ばす():
    """繋ぎ目を作るだけのすき間が無いと、音が途切れてしまう。"""
    got = build.normalize_echoes(echoes((5, 9, "light"), (9.05, 12, "hall")), 60)
    assert got == [(5.0, 9.0, "light")]


def test_順番がばらばらでも並べ直す():
    got = build.normalize_echoes(echoes((20, 24, "hall"), (5, 9, "light")), 60)
    assert [row[0] for row in got] == [5.0, 20.0]


# ---------------------------------------------------------------- フィルタグラフ

def test_区間の前後はそのまま通す():
    graph = build.echo_graph([(5.0, 9.0, "light")], 60)
    assert "atrim=start=0.0:end=5.0" in graph      # 前
    assert "atrim=start=5.0:end=9.0" in graph      # エコーをかける所
    assert "atrim=start=9.0:end=60" in graph       # 後
    assert graph.count(build.ECHO_PRESETS["light"]) == 1
    assert graph.endswith("[echoed]")


def test_繋ぎ目はクロスフェードで繋ぐ():
    graph = build.echo_graph([(5.0, 9.0, "light")], 60)
    assert graph.count(f"acrossfade=d={build.ECHO_CROSSFADE}") == 2   # 前後2か所


def test_全部にかけるときは繋ぎ目がいらない():
    graph = build.echo_graph([(0.0, 60, "hall")], 60)
    assert "acrossfade" not in graph
    assert graph.endswith("[echoed]")


def test_区間が2つなら部分は5つになる():
    graph = build.echo_graph([(5.0, 9.0, "light"), (20.0, 24.0, "hall")], 60)
    assert graph.count("atrim=") == 5
    assert graph.count("acrossfade") == 4


def test_プリセットは2つとも使える():
    graph = build.echo_graph([(5.0, 9.0, "light"), (20.0, 24.0, "hall")], 60)
    assert build.ECHO_PRESETS["light"] in graph
    assert build.ECHO_PRESETS["hall"] in graph


# ---------------------------------------------------------------- 飛ばした区間を黙って消さない

def test_飛ばした区間はお知らせを出す(capsys):
    build.normalize_echoes(echoes((5, 9, "light"), (9.1, 12, "hall")), 60)
    out = capsys.readouterr().out
    assert "0:09" in out and "近すぎる" in out


def test_短すぎる区間もお知らせを出す(capsys):
    build.normalize_echoes(echoes((5, 5.1, "light")), 60)
    assert "短すぎる" in capsys.readouterr().out


def test_知らないプリセットもお知らせを出す(capsys):
    build.normalize_echoes(echoes((5, 9, "ふしぎ")), 60)
    assert "知らないプリセット" in capsys.readouterr().out


def test_なしは黙っていてよい(capsys):
    build.normalize_echoes(echoes((5, 9, "none")), 60)
    assert capsys.readouterr().out == ""


def test_比べるときはお知らせを出さない(capsys):
    build.normalize_echoes(echoes((5, 9, "light"), (9.1, 12, "hall")), 60, report=False)
    assert capsys.readouterr().out == ""


# ---------------------------------------------------------------- 整音後の位置

def test_エコーの尾の長さはプリセットの文字列から読む():
    # 軽めは 40|70 ミリ秒、響くは 30|…|210 ミリ秒。いちばん遅いものを使う
    assert build.echo_tail("light") == 0.07
    assert build.echo_tail("hall") == 0.21
    assert build.echo_tail("none") == 0.0
    assert build.echo_tail("しらない") == 0.0


def test_エコーが無ければ位置も無い():
    assert build.echo_positions([], 60) == []


def test_最初の区間は継ぎ目のぶんだけ前へ詰まる():
    # 頭(0-10) / 区間(10-20) / 尻(20-60) の3つ。区間の手前に継ぎ目が1つ
    got = build.echo_positions([(10.0, 20.0, "light")], 60)
    assert len(got) == 1
    assert got[0]["start"] == round(10.0 - build.ECHO_CROSSFADE, 3)
    # 終わりは、エコーの尾のぶんだけ伸びる
    assert got[0]["end"] == round(10.0 - build.ECHO_CROSSFADE + 10.0 + 0.07, 3)


def test_後ろの区間ほど前の区間のぶんがずれる():
    got = build.echo_positions([(10.0, 20.0, "light"), (30.0, 35.0, "hall")], 57.1149)
    assert [r["preset"] for r in got] == ["light", "hall"]
    # 1つ目: 継ぎ目1つぶん前へ
    assert got[0]["start"] == 9.98
    # 2つ目: 前の区間が 0.07秒 伸ばし、継ぎ目3つで 0.06秒 詰まる
    assert got[1]["start"] == 30.01
    assert got[1]["end"] == 35.22


def test_計算した長さが実際の長さと合う():
    """clean.wav の長さは、部分の合計から継ぎ目の重なりを引いたもの。

    ep01（trimmed 57.1149秒・軽め10-20・響く30-35）を ffmpeg で作ったとき、
    clean.wav は 57.3149秒だった。その数字と合うことを確かめる。
    """
    regions = [(10.0, 20.0, "light"), (30.0, 35.0, "hall")]
    total = 57.1149
    parts = build.echo_parts(regions, total)
    length = (sum((e - s) + build.echo_tail(p) for s, e, p in parts)
              - build.ECHO_CROSSFADE * (len(parts) - 1))
    assert round(length, 4) == 57.3149


def test_区間の位置はエコーをかけた所だけ返す():
    # 部分は5つあるが、エコーをかけたのは2つだけ
    assert len(build.echo_parts([(10.0, 20.0, "light"), (30.0, 35.0, "hall")], 60)) == 5
    assert len(build.echo_positions([(10.0, 20.0, "light"), (30.0, 35.0, "hall")], 60)) == 2
