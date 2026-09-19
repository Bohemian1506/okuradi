"""web/episodes.py のテスト。

工程の状態（未実行 / 実行できる / 完了 / 古い）の判定と、回の作成を確かめる。
本物の音声は使わず、中身の無いファイルの更新日時だけで判定できることを利用する。
"""

import os
import time

import pytest
import yaml

from web import episodes

CONFIG = {
    "episode": 1,
    "segments": [{"series": "imasara", "theme": "OSI参照モデルの7層"}],
    "series_rules": {
        "imasara": {"label": "今更聞けない"},
        "it_news": {"label": "ITニュースざっくり"},
    },
    "cuts": [],
}


def make_episode(root, number=1, files=(), config=None):
    """回のディレクトリを作る。files は新しい順ではなく、渡した順に古い→新しいで作る。"""
    ep_dir = root / f"ep{number:02d}"
    for sub in ["00_raw", "01_cut", "01_clean", "02_text", "03_meta", "04_video"]:
        (ep_dir / sub).mkdir(parents=True, exist_ok=True)
    cfg = dict(config or CONFIG)
    cfg["episode"] = number
    (ep_dir / "config.yml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    base = time.time() - 1000
    for index, name in enumerate(files):
        path = ep_dir / name
        path.write_text("x", encoding="utf-8")
        os.utime(path, (base + index, base + index))
    return ep_dir


ALL_FILES = [
    "00_raw/rec.wav",
    "02_text/scan.json",
    "01_clean/clean.wav",
    "02_text/transcript.json",
    "03_meta/meta.json",
    "04_video/ep01.mp4",
]


def states(ep_dir):
    cfg = episodes.read_config(ep_dir)
    return {s["key"]: s["state"] for s in episodes.step_states(ep_dir, cfg)}


# ---------------------------------------------------------------- 工程の状態

def test_音源が無ければ全部未実行(tmp_path):
    ep_dir = make_episode(tmp_path)
    assert states(ep_dir) == {
        "source": "未実行", "scan": "未実行", "clean": "未実行",
        "transcribe": "未実行", "meta": "未実行", "video": "未実行",
    }


def test_音源を置くと下見と整音が実行できるになる(tmp_path):
    ep_dir = make_episode(tmp_path, files=["00_raw/rec.wav"])
    got = states(ep_dir)
    assert got["source"] == "完了"
    assert got["scan"] == "実行できる"
    assert got["clean"] == "実行できる"
    # 整音が済んでいないので、その先はまだ実行できない
    assert got["transcribe"] == "未実行"


def test_全部そろえば全部完了(tmp_path):
    ep_dir = make_episode(tmp_path, files=ALL_FILES)
    assert set(states(ep_dir).values()) == {"完了"}


def test_整音をやり直すと文字起こしと動画が古いになる(tmp_path):
    ep_dir = make_episode(tmp_path, files=ALL_FILES)
    clean = ep_dir / "01_clean" / "clean.wav"
    os.utime(clean, (time.time(), time.time()))

    got = states(ep_dir)
    assert got["clean"] == "完了"
    assert got["transcribe"] == "古い"   # 整音から作るので作り直しが要る
    assert got["video"] == "古い"        # 整音とメタデータから作る
    assert got["meta"] == "完了"         # メタデータは文字起こしから作るので、直接は影響しない
    assert got["scan"] == "完了"         # 下見は音源から作るので、影響しない


def test_進み具合は完了の数だけ数える(tmp_path):
    ep_dir = make_episode(tmp_path, files=ALL_FILES)
    os.utime(ep_dir / "01_clean" / "clean.wav", (time.time(), time.time()))
    data = episodes.summary(ep_dir, episodes.read_config(ep_dir))
    assert (data["done"], data["total"]) == (4, 6)


def test_動画は回の番号のファイル名で探す(tmp_path):
    ep_dir = make_episode(tmp_path, number=3, files=["04_video/ep03.mp4"])
    cfg = episodes.read_config(ep_dir)
    assert episodes.artifact(ep_dir, "video", cfg) is not None


# ---------------------------------------------------------------- 一覧と作成

def test_一覧はテーマをコーナー名つきで出す(tmp_path):
    make_episode(tmp_path)
    got = episodes.list_episodes(tmp_path)
    assert got[0]["theme"] == "今更聞けない OSI参照モデルの7層"


def test_新しい回は直前の回から番組の設定を写す(tmp_path):
    make_episode(tmp_path, number=1, config={**CONFIG, "concept": "番組の芯", "cuts": [[1, 2]]})
    episodes.create_episode(2, [{"series": "it_news", "theme": "新しい話"}], root=tmp_path)

    cfg = episodes.read_config(tmp_path / "ep02")
    assert cfg["concept"] == "番組の芯"           # 番組の設定は引き継ぐ
    assert cfg["episode"] == 2
    assert cfg["cuts"] == []                      # 回ごとのものは持ち越さない
    assert cfg["segments"] == [{"series": "it_news", "theme": "新しい話"}]
    assert (tmp_path / "ep02" / "02_text").is_dir()  # 中間ファイルの置き場もできる


def test_同じ番号の回は作れない(tmp_path):
    make_episode(tmp_path, number=2)
    with pytest.raises(episodes.EpisodeError, match="ep02"):
        episodes.create_episode(2, [{"series": "imasara", "theme": "x"}], root=tmp_path)


def test_テーマが空なら断る(tmp_path):
    make_episode(tmp_path)
    with pytest.raises(episodes.EpisodeError, match="テーマ"):
        episodes.create_episode(2, [{"series": "imasara", "theme": "  "}], root=tmp_path)


def test_知らないコーナーは断る(tmp_path):
    make_episode(tmp_path)
    with pytest.raises(episodes.EpisodeError, match="コーナー"):
        episodes.create_episode(2, [{"series": "nope", "theme": "x"}], root=tmp_path)


def test_ひな型にする回が無ければ理由を言って断る(tmp_path):
    with pytest.raises(episodes.EpisodeError, match="手で作って"):
        episodes.create_episode(1, [{"series": "imasara", "theme": "x"}], root=tmp_path)


def test_次の番号は最後の回の次(tmp_path):
    make_episode(tmp_path, number=1)
    make_episode(tmp_path, number=5)
    assert episodes.next_number(tmp_path) == 6


def test_コーナーを保存すると設定ファイルに書かれる(tmp_path):
    make_episode(tmp_path)
    episodes.save_segments("ep01", [
        {"series": "imasara", "theme": "1つ目"},
        {"series": "it_news", "theme": "2つ目"},
    ], root=tmp_path)
    cfg = episodes.read_config(tmp_path / "ep01")
    assert [s["theme"] for s in cfg["segments"]] == ["1つ目", "2つ目"]


# ---------------------------------------------------------------- レビューで見つかった壊れ方

def test_回の外は読み書きできない(tmp_path):
    """name に `..` を渡しても、回のディレクトリの外に出ない。"""
    root = tmp_path / "repo"
    root.mkdir()
    make_episode(root)
    outside = tmp_path / "config.yml"
    outside.write_text("secret: yes\nsegments: []\n", encoding="utf-8")

    with pytest.raises(episodes.EpisodeError):
        episodes.detail("..", root=root)
    with pytest.raises(episodes.EpisodeError):
        episodes.save_segments("..", [{"series": "imasara", "theme": "x"}], root=root)
    assert outside.read_text(encoding="utf-8") == "secret: yes\nsegments: []\n"


def test_壊れた回があっても他の回は一覧に出る(tmp_path):
    make_episode(tmp_path, number=1)
    broken = tmp_path / "ep02"
    broken.mkdir()
    (broken / "config.yml").write_text("episode: [壊れた\n", encoding="utf-8")

    rows = episodes.list_episodes(tmp_path)
    assert [r["name"] for r in rows] == ["ep01", "ep02"]
    assert "error" not in rows[0]
    assert "読めません" in rows[1]["error"]
    assert rows[1]["theme"] == "（設定が読めません）"


def test_壊れた回があってもコーナーの選択肢と次の番号は出る(tmp_path):
    make_episode(tmp_path, number=1)
    broken = tmp_path / "ep02"
    broken.mkdir()
    (broken / "config.yml").write_text("episode: [壊れた\n", encoding="utf-8")

    rules = episodes.series_rules(tmp_path)
    assert sorted(rules) == ["imasara", "it_news"]
    assert rules["imasara"]["label"] == "今更聞けない"
    assert episodes.next_number(tmp_path) == 3


def test_コーナーを保存しても知らないキーは消えない(tmp_path):
    """表情差分や BGM を segments に足したあとでも、保存で消えない。"""
    config = dict(CONFIG)
    config["segments"] = [{"series": "imasara", "theme": "x",
                           "image": "assets/warai.png", "bgm": "a.mp3"}]
    make_episode(tmp_path, config=config)

    keep = episodes.detail("ep01", root=tmp_path)["segments"]
    keep[0]["theme"] = "直した"
    episodes.save_segments("ep01", keep, root=tmp_path)

    saved = episodes.read_config(tmp_path / "ep01")["segments"][0]
    assert saved["theme"] == "直した"
    assert saved["image"] == "assets/warai.png"
    assert saved["bgm"] == "a.mp3"


def test_動画はメタデータを直しても古くならない(tmp_path):
    """build.py の step_video は meta.json を読まないので、依存に入れない。"""
    ep_dir = make_episode(tmp_path, files=ALL_FILES)
    os.utime(ep_dir / "03_meta" / "meta.json", (time.time(), time.time()))
    assert states(ep_dir)["video"] == "完了"


def test_その回のコーナーは新しい回の設定に引きずられない(tmp_path):
    """ep02 で別のコーナーを使っていても、ep01 のテーマは直せる。"""
    make_episode(tmp_path, number=1)
    make_episode(tmp_path, number=2, config={
        "segments": [{"series": "tokubetsu", "theme": "y"}],
        "series_rules": {"tokubetsu": {"label": "特別編"}},
    })
    episodes.save_segments("ep01", [{"series": "imasara", "theme": "直した"}], root=tmp_path)
    assert episodes.read_config(tmp_path / "ep01")["segments"][0]["theme"] == "直した"


def test_作成が途中で失敗したらフォルダを残さない(tmp_path, monkeypatch):
    make_episode(tmp_path, number=1)

    def boom(*args, **kwargs):
        raise OSError("書き込めません")

    monkeypatch.setattr(episodes.build, "save_config", boom)
    with pytest.raises(OSError):
        episodes.create_episode(2, [{"series": "imasara", "theme": "x"}], root=tmp_path)
    assert not (tmp_path / "ep02").exists()


def test_読めない理由は1行におさめる(tmp_path):
    """YAML のエラーは何行にもなるので、画面に出す分は切り詰める。"""
    broken = tmp_path / "ep02"
    broken.mkdir()
    (broken / "config.yml").write_text("episode: [壊れた\n", encoding="utf-8")
    message = episodes.list_episodes(tmp_path)[0]["error"]
    assert len(message.splitlines()) == 1


def test_テーマ欄のヒントは型を示す最初の文だけ使う(tmp_path):
    config = dict(CONFIG)
    config["series_rules"] = {
        "imasara": {"label": "今更聞けない",
                    "title_hint": "「今更聞けない○○」の形。○○は具体的な用語や概念にする"},
    }
    make_episode(tmp_path, config=config)
    assert episodes.series_rules(tmp_path)["imasara"]["hint"] == "「今更聞けない○○」の形"
