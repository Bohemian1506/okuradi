"""コピー欄の「章が3件未満」の知らせ（#106 の6番）。

**YouTube は章が3件未満だと目次を表示しない。** 1コーナーの回では正しい動きなので、
**止めずに知らせるだけ**にした（#106 に「止めるではなく知らせる」とある）。

画面のコードを直接は動かせないので、**知らせを出す条件の式と、出す文**を、
`app.js` から取り出して確かめる。
"""

import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "web" / "static" / "app.js"
CSS = Path(__file__).resolve().parents[1] / "web" / "static" / "style.css"


def source():
    return APP.read_text(encoding="utf-8")


def count_chapters(description):
    """`app.js` が章を数えている式と、同じ数え方。"""
    return len(re.findall(r"\n\d+:\d\d ", description))


@pytest.mark.parametrize("description, chapters, shown", [
    ("本文\n\n--- 目次 ---\n0:00 あ", 1, True),
    ("本文\n\n--- 目次 ---\n0:00 あ\n1:00 い", 2, True),
    ("本文\n\n--- 目次 ---\n0:00 あ\n1:00 い\n2:00 う", 3, False),
    ("本文だけ", 0, False),
])
def test_章が1件か2件のときだけ知らせる(description, chapters, shown):
    """**3件以上では出さない**（目次が出るので言うことがない）。
    **0件でも出さない**（章がありません、は保留チェックが別に言う）。
    """
    assert count_chapters(description) == chapters
    assert (0 < chapters < 3) is shown


def test_知らせを出す条件が画面に書いてある():
    assert "chapters > 0 && chapters < 3" in source()


def test_知らせの文に理由と断りが入っている():
    text = source()
    assert "YouTube は3件以上ないと目次を出しません" in text
    # **1コーナーの回は正しい動き。** 不具合だと思わせない
    assert "コーナーが少ない回では、これで正しいです" in text


def test_止めていない():
    """`copy-warn`（押せません）ではなく `copy-note`（知らせるだけ）を使う。"""
    text = source()
    assert 'el("div", "copy-note")' in text
    # 知らせのところで、ボタンを押せなくしていない
    after = text[text.index('el("div", "copy-note")"'[:-1]):]
    assert "disabled" not in after[:400]


def test_知らせの見た目がある():
    css = CSS.read_text(encoding="utf-8")
    assert ".copy-note {" in css
    assert ".copy-note .mark {" in css
