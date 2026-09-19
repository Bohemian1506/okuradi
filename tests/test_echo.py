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
