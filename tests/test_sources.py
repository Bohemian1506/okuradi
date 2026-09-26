"""web/sources.py のテスト（音源の追加と、アプリ全体の設定）。

本物の音声は使わない。長さを測るところ（ffprobe）は差し替える。
"""

import io

import pytest
import yaml

from web import episodes, sources, timeline


@pytest.fixture
def here(tmp_path, monkeypatch):
    """回のディレクトリと settings.yml を、テスト用の場所に向ける。"""
    ep_dir = tmp_path / "ep01"
    (ep_dir / "00_raw").mkdir(parents=True)
    monkeypatch.setattr(sources, "SETTINGS", tmp_path / "settings.yml")
    monkeypatch.setattr(episodes, "resolve", lambda name, root=None: ep_dir)
    monkeypatch.setattr(sources, "duration_of", lambda path: 59.0)
    return ep_dir


# ---------------------------------------------------------------- 設定

def test_設定は書いて読める(here):
    assert sources.read_settings() == {}
    sources.save_settings({"obs_dir": "/mnt/c/Videos"})
    assert sources.read_settings()["obs_dir"] == "/mnt/c/Videos"


def test_壊れた設定は理由を言って断る(here):
    sources.SETTINGS.write_text("obs_dir: [壊れた\n", encoding="utf-8")
    with pytest.raises(episodes.EpisodeError, match="settings.yml が読めません"):
        sources.read_settings()


# ---------------------------------------------------------------- OBS のフォルダ

def test_未設定なら未設定と返す(here):
    assert sources.obs_view()["state"] == "未設定"


def test_無いフォルダなら見つかりませんと返す(here):
    sources.save_settings({"obs_dir": str(here.parent / "ない")})
    assert sources.obs_view()["state"] == "見つかりません"


def test_録画は新しい順に並び関係ないファイルは出さない(here, tmp_path):
    obs = tmp_path / "obs"
    obs.mkdir()
    import os, time
    for index, name in enumerate(["古い.mkv", "新しい.mp4", "memo.txt"]):
        path = obs / name
        path.write_text("x", encoding="utf-8")
        os.utime(path, (time.time() + index, time.time() + index))
    sources.save_settings({"obs_dir": str(obs)})

    view = sources.obs_view()
    assert view["state"] == "ok"
    assert [r["name"] for r in view["recordings"]] == ["新しい.mp4", "古い.mkv"]


# ---------------------------------------------------------------- 収録ファイル

def test_音源がなければ空(here):
    assert sources.source_view("ep01") == {"state": "空"}


def test_取り込むと使えるになる(here):
    sources.add_from_upload("ep01", "rec.wav", io.BytesIO("おと".encode()))
    got = sources.source_view("ep01")
    assert got["state"] == "使える"
    assert got["name"] == "rec.wav"
    assert got["kind"] == "wav"
    assert got["from_video"] is False


def test_録画なら元は録画として見せる(here):
    sources.add_from_upload("ep01", "rec.mkv", io.BytesIO("どうが".encode()))
    got = sources.source_view("ep01")
    assert got["kind"] == "OBSの録画"
    assert got["from_video"] is True


def test_対応していない形式は断る(here):
    with pytest.raises(episodes.EpisodeError, match="対応していません"):
        sources.add_from_upload("ep01", "memo.txt", io.BytesIO(b"x"))


def test_取り込むと前の音源は残らない(here):
    sources.add_from_upload("ep01", "前.wav", io.BytesIO(b"1"))
    sources.add_from_upload("ep01", "後.wav", io.BytesIO(b"2"))
    names = [f.name for f in (here / "00_raw").iterdir()]
    assert names == ["後.wav"]


def test_OBS_から取り込める(here, tmp_path):
    obs = tmp_path / "obs"
    obs.mkdir()
    (obs / "収録.mkv").write_bytes("どうが".encode())
    sources.save_settings({"obs_dir": str(obs)})

    got = sources.add_from_obs("ep01", "収録.mkv")
    assert got["name"] == "収録.mkv"
    assert (here / "00_raw" / "収録.mkv").read_bytes() == "どうが".encode()
    assert (obs / "収録.mkv").exists()      # 元は消さない


def test_OBS_のフォルダの外は指せない(here, tmp_path):
    obs = tmp_path / "obs"
    obs.mkdir()
    outside = tmp_path / "ひみつ.wav"
    outside.write_bytes("だめ".encode())
    sources.save_settings({"obs_dir": str(obs)})

    with pytest.raises(episodes.EpisodeError, match="見つかりません"):
        sources.add_from_obs("ep01", "../ひみつ.wav")
    assert not (here / "00_raw" / "ひみつ.wav").exists()


def test_OBS_が未設定なら取り込めない(here):
    with pytest.raises(episodes.EpisodeError, match="使えません"):
        sources.add_from_obs("ep01", "なにか.mkv")


# ---------------------------------------------------------------- コーナーの枠（#85 の3段目）

CONFIG = """episode: 1
segments:
- series: op
  theme: OP
- series: imasara
  theme: OSI参照モデルの7層
- series: imasara
  theme: 2つめ
series_rules:
  op:
    label: OP
  imasara:
    label: 今さら聞けない
"""


@pytest.fixture
def framed(here):
    """segments が3つ（同じ series を2つ含む）の回。"""
    (here / "config.yml").write_text(CONFIG, encoding="utf-8")
    return here


def test_枠はsegmentsの順に並び音源がなければ空(framed):
    got = sources.frames_view("ep01")
    ids = [f["id"] for f in got["frames"]]
    assert ids == ["op", "imasara", "imasara-2"]
    assert [f["state"] for f in got["frames"]] == ["空", "空", "空"]
    assert got["frames"][1]["label"] == "今さら聞けない OSI参照モデルの7層"
    assert got["orphans"] == []


def test_枠にファイルを入れると使えるになる(framed):
    got = sources.add_frame_from_upload(
        "ep01", "imasara", "録音.wav", io.BytesIO(b"1"))
    frame = next(f for f in got["frames"] if f["id"] == "imasara")
    assert frame["state"] == "使える"
    assert frame["name"] == "imasara.wav"           # 名前は枠のidに付け替える
    assert (framed / "00_raw" / "imasara.wav").exists()


def test_知らない枠には入れられない(framed):
    with pytest.raises(episodes.EpisodeError, match="その枠がありません"):
        sources.add_frame_from_upload("ep01", "ed", "x.wav", io.BytesIO(b"1"))
    with pytest.raises(episodes.EpisodeError, match="その枠がありません"):
        sources.add_frame_from_upload("ep01", "../ed", "x.wav", io.BytesIO(b"1"))


def test_差し替えると前の1本だけ消え他の枠は残る(framed):
    sources.add_frame_from_upload("ep01", "op", "op.wav", io.BytesIO(b"1"))
    sources.add_frame_from_upload("ep01", "imasara", "録音.wav", io.BytesIO(b"2"))

    sources.add_frame_from_upload("ep01", "imasara", "撮り直し.wav", io.BytesIO(b"3"))

    names = {f.name for f in (framed / "00_raw").iterdir()}
    assert names == {"op.wav", "imasara.wav"}        # imasara の前のファイルは残らない
    assert (framed / "00_raw" / "imasara.wav").read_bytes() == b"3"
    assert (framed / "00_raw" / "op.wav").read_bytes() == b"1"   # op は触らない


def test_録画から取り出したtrackファイルも一緒に消える(framed):
    sources.add_frame_from_upload("ep01", "op", "op.mkv", io.BytesIO(b"1"))
    # find_raw が作る「録画名.trackN.wav」を模してこしらえる
    (framed / "00_raw" / "op.track0.wav").write_bytes(b"track")

    sources.add_frame_from_upload("ep01", "op", "撮り直し.mp4", io.BytesIO(b"2"))

    names = {f.name for f in (framed / "00_raw").iterdir()}
    assert names == {"op.mp4"}


def test_外すとファイルも消えてtimelineからも消える(framed):
    sources.add_frame_from_upload("ep01", "op", "op.wav", io.BytesIO(b"1"))
    sources.add_frame_from_upload("ep01", "imasara", "録音.wav", io.BytesIO(b"2"))

    got = sources.remove_frame("ep01", "op")

    assert not (framed / "00_raw" / "op.wav").exists()
    frame = next(f for f in got["frames"] if f["id"] == "op")
    assert frame["state"] == "空"
    data = timeline.read(framed)
    assert [c["id"] for c in data["lanes"]["main"]] == ["imasara"]


def test_timelineはコーナーの順で書かれる(framed):
    # 先に imasara、あとから op を入れる（順番を逆にして試す）
    sources.add_frame_from_upload("ep01", "imasara", "録音.wav", io.BytesIO(b"1"))
    sources.add_frame_from_upload("ep01", "op", "op.wav", io.BytesIO(b"2"))

    data = timeline.read(framed)
    assert [c["id"] for c in data["lanes"]["main"]] == ["op", "imasara"]


def test_gapとbgmとseは残るがeditsは差し替えで空になる(framed):
    """差し替えたら edits（カット）は空にする（案A・2026-09-26・ユーザーの判断・#216 のレビュー）。

    前の録音のカットは、新しい録音には合わない。gap（並びの間の秒数）と
    bgm / se（出来上がりの時刻が基準）は音源そのものとは関係ないので残す。
    """
    sources.add_frame_from_upload("ep01", "op", "op.wav", io.BytesIO(b"1"))
    sources.add_frame_from_upload("ep01", "imasara", "録音.wav", io.BytesIO(b"2"))

    data = timeline.read(framed)
    data["lanes"]["main"][1]["gap"] = 1.5
    data["lanes"]["main"][1]["edits"] = [{"kind": "cut", "start": 1, "end": 2}]
    data["lanes"]["bgm"] = [{"id": "bg1", "source": "bg1.wav", "anchor": "op", "at": 0}]
    timeline.save(framed, data)

    sources.add_frame_from_upload("ep01", "imasara", "撮り直し.wav", io.BytesIO(b"3"))

    after = timeline.read(framed)
    imasara = next(c for c in after["lanes"]["main"] if c["id"] == "imasara")
    assert imasara["gap"] == 1.5
    assert imasara["edits"] == []                # 差し替えたので空になる
    assert imasara["source"] == "imasara.wav"   # 名前は枠のidに付け替えるので変わらない
    assert after["lanes"]["bgm"][0]["id"] == "bg1"


def test_segmentsに無いクリップは消えずに一覧に出る(framed):
    sources.add_frame_from_upload("ep01", "op", "op.wav", io.BytesIO(b"1"))
    # コーナーを消した後のように、timeline.yml に知らない id を混ぜる
    data = timeline.read(framed)
    data["lanes"]["main"].append({"id": "old", "source": "old.wav", "gap": 0, "edits": []})
    timeline.save(framed, data)
    (framed / "00_raw" / "old.wav").write_bytes(b"x")

    got = sources.frames_view("ep01")
    assert [o["id"] for o in got["orphans"]] == ["old"]
    assert got["orphans"][0]["state"] == "使える"
    assert (framed / "00_raw" / "old.wav").exists()   # ファイルは消さない


def test_名前の付け方は枠のidプラス元の拡張子(framed):
    sources.add_frame_from_upload("ep01", "imasara", "元の名前.MP4", io.BytesIO(b"1"))
    assert (framed / "00_raw" / "imasara.mp4").exists()


def test_00_rawの外には書けない(framed):
    with pytest.raises(episodes.EpisodeError, match="その枠がありません"):
        sources.add_frame_from_upload("ep01", "../../evil", "x.wav", io.BytesIO(b"1"))
    assert not (framed.parent / "evil.wav").exists()


# ---------------------------------------------------------------- orphan（どのコーナーにも当たらないクリップ）
# 案A（2026-09-26・ユーザーの判断）: orphan がある間は枠の出し入れを止める。
# 外すと操作できるようになる。edits は黙って消えない。検証で断られたらファイルは変わらない。

CONFIG3 = """episode: 1
segments:
- series: op
  theme: OP
- series: imasara
  theme: OSI参照モデルの7層
- series: it_news
  theme: ニュース
series_rules:
  op:
    label: OP
  imasara:
    label: 今さら聞けない
  it_news:
    label: ITニュース
"""


@pytest.fixture
def framed3(here):
    """segments が3つ（series は重ならない）の回。orphan のテスト用。"""
    (here / "config.yml").write_text(CONFIG3, encoding="utf-8")
    return here


def _drop_segment(ep_dir, series):
    """コーナーを削除したのと同じ状況を作る（config.yml から1つ外す）。"""
    cfg = yaml.safe_load((ep_dir / "config.yml").read_text(encoding="utf-8"))
    cfg["segments"] = [s for s in cfg["segments"] if s["series"] != series]
    (ep_dir / "config.yml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_orphanがあると枠への出し入れを断る(framed3):
    sources.add_frame_from_upload("ep01", "op", "op.wav", io.BytesIO(b"1"))
    sources.add_frame_from_upload("ep01", "imasara", "im.wav", io.BytesIO(b"2"))
    _drop_segment(framed3, "imasara")   # imasara が orphan になる

    with pytest.raises(episodes.EpisodeError, match="どのコーナーにも当たらない"):
        sources.add_frame_from_upload("ep01", "it_news", "it.wav", io.BytesIO(b"3"))
    with pytest.raises(episodes.EpisodeError, match="どのコーナーにも当たらない"):
        sources.remove_frame("ep01", "op")

    # 断られた操作でファイルは増えていない
    names = {f.name for f in (framed3 / "00_raw").iterdir()}
    assert names == {"op.wav", "imasara.wav"}


def test_orphanを外すと操作できるようになる(framed3):
    sources.add_frame_from_upload("ep01", "op", "op.wav", io.BytesIO(b"1"))
    sources.add_frame_from_upload("ep01", "imasara", "im.wav", io.BytesIO(b"2"))
    _drop_segment(framed3, "imasara")

    got = sources.remove_orphan("ep01", "imasara")
    assert got["orphans"] == []
    assert not (framed3 / "00_raw" / "imasara.wav").exists()

    # もう出し入れができる
    sources.add_frame_from_upload("ep01", "it_news", "it.wav", io.BytesIO(b"3"))
    assert (framed3 / "00_raw" / "it_news.wav").exists()


def test_知らないorphanは外せない(framed3):
    with pytest.raises(episodes.EpisodeError, match="ありません"):
        sources.remove_orphan("ep01", "no-such")


def test_枠のidと同じ名前は外側からorphanとして外せない(framed3):
    # "op" はいまも枠として使われている（orphan ではない）ので、
    # remove_orphan の対象にはしない
    sources.add_frame_from_upload("ep01", "op", "op.wav", io.BytesIO(b"1"))
    with pytest.raises(episodes.EpisodeError, match="ありません"):
        sources.remove_orphan("ep01", "op")


def test_orphanのeditsは黙って消えない(framed3):
    sources.add_frame_from_upload("ep01", "op", "op.wav", io.BytesIO(b"1"))
    sources.add_frame_from_upload("ep01", "imasara", "im.wav", io.BytesIO(b"2"))
    data = timeline.read(framed3)
    for clip in data["lanes"]["main"]:
        if clip["id"] == "imasara":
            clip["edits"] = [{"kind": "cut", "start": 1, "end": 2}]
    timeline.save(framed3, data)
    _drop_segment(framed3, "imasara")

    with pytest.raises(episodes.EpisodeError, match="どのコーナーにも当たらない"):
        sources.add_frame_from_upload("ep01", "it_news", "it.wav", io.BytesIO(b"3"))

    after = timeline.read(framed3)
    imasara = next(c for c in after["lanes"]["main"] if c["id"] == "imasara")
    assert imasara["edits"] == [{"kind": "cut", "start": 1, "end": 2}]


def test_検証で断られたらファイルもtimelineも変わっていない(framed3):
    sources.add_frame_from_upload("ep01", "op", "op.wav", io.BytesIO(b"1"))
    data = timeline.read(framed3)
    data["lanes"]["bgm"] = [{"id": "bg1", "source": "bg1.wav", "anchor": "op", "at": 0}]
    timeline.save(framed3, data)

    # op を外すと、bg1 の錨が本編から無くなるので検証で断られる
    with pytest.raises(episodes.EpisodeError, match="錨"):
        sources.remove_frame("ep01", "op")

    # ファイルは消えていない
    assert (framed3 / "00_raw" / "op.wav").exists()
    # timeline.yml も書き換わっていない
    after = timeline.read(framed3)
    assert [c["id"] for c in after["lanes"]["main"]] == ["op"]
    assert after["lanes"]["bgm"][0]["id"] == "bg1"


# ---------------------------------------------------------------- PR #216 レビューの直し

class _FlakyStream:
    """読み出しでいきなり失敗するストリーム（書き込みが途中で切れる状況を再現）。"""

    def read(self, n=-1):
        raise OSError("接続が切れました")


def test_書き込みが失敗すると前のファイルが残り一時ファイルも残らない(framed):
    sources.add_frame_from_upload("ep01", "op", "op.wav", io.BytesIO("前の音源".encode()))
    before = (framed / "00_raw" / "op.wav").read_bytes()
    before_timeline = timeline.read(framed)

    with pytest.raises(episodes.EpisodeError, match="音源を置けませんでした"):
        sources.add_frame_from_upload("ep01", "op", "op.wav", _FlakyStream())

    # 前のファイルはそのまま（0バイトで残らない）
    assert (framed / "00_raw" / "op.wav").read_bytes() == before
    # 一時ファイルも残らない
    names = [f.name for f in (framed / "00_raw").iterdir()]
    assert names == ["op.wav"]
    assert not any(n.startswith(".tmp") for n in names)
    # timeline.yml も書き換わっていない
    assert timeline.read(framed) == before_timeline


def test_書き込みが失敗するとOBSからの取り込みでも前のファイルが残る(framed, tmp_path):
    obs = tmp_path / "obs"
    obs.mkdir()
    (obs / "録画.mkv").write_bytes("どうが".encode())
    sources.save_settings({"obs_dir": str(obs)})
    sources.add_frame_from_upload("ep01", "op", "op.wav", io.BytesIO("前の音源".encode()))
    before = (framed / "00_raw" / "op.wav").read_bytes()

    def broken_copy(src, dst):
        raise OSError("コピーに失敗しました")

    import shutil as shutil_module
    orig = shutil_module.copy2
    shutil_module.copy2 = broken_copy
    try:
        with pytest.raises(episodes.EpisodeError, match="音源を置けませんでした"):
            sources.add_frame_from_obs("ep01", "op", "録画.mkv")
    finally:
        shutil_module.copy2 = orig

    assert (framed / "00_raw" / "op.wav").read_bytes() == before
    names = [f.name for f in (framed / "00_raw").iterdir()]
    assert names == ["op.wav"]


def test_枠の回では古い1本の入口を断る(framed):
    sources.add_frame_from_upload("ep01", "op", "op.wav", io.BytesIO(b"1"))
    with pytest.raises(episodes.EpisodeError, match="コーナーの枠"):
        sources.add_from_upload("ep01", "old.wav", io.BytesIO(b"2"))
    # 00_raw は消えていない
    assert (framed / "00_raw" / "op.wav").exists()


def test_枠の回のOBS入口も断る(framed, tmp_path):
    obs = tmp_path / "obs"
    obs.mkdir()
    (obs / "録画.mkv").write_bytes("どうが".encode())
    sources.save_settings({"obs_dir": str(obs)})
    sources.add_frame_from_upload("ep01", "op", "op.wav", io.BytesIO(b"1"))

    with pytest.raises(episodes.EpisodeError, match="コーナーの枠"):
        sources.add_from_obs("ep01", "録画.mkv")
    assert (framed / "00_raw" / "op.wav").exists()


def test_コーナーを1つに減らしてもtimelineがあれば枠のまま(framed):
    """`is_framed` は timeline.yml があれば true。segments の数だけでは判定しない。"""
    sources.add_frame_from_upload("ep01", "op", "op.wav", io.BytesIO(b"1"))
    sources.add_frame_from_upload("ep01", "imasara", "im.wav", io.BytesIO(b"2"))
    sources.add_frame_from_upload("ep01", "imasara-2", "im2.wav", io.BytesIO(b"3"))
    _drop_segment_series(framed, keep=["op"])   # コーナーを1つに減らす

    assert sources.is_framed(framed) is True
    # 当たらないクリップの守りも効く
    with pytest.raises(episodes.EpisodeError, match="どのコーナーにも当たらない"):
        sources.remove_frame("ep01", "op")
    # 古い1本の入口も断られる
    with pytest.raises(episodes.EpisodeError, match="コーナーの枠"):
        sources.add_from_upload("ep01", "old.wav", io.BytesIO(b"4"))


def test_timelineが無くコーナーが1つなら枠にしない(framed):
    cfg = yaml.safe_load((framed / "config.yml").read_text(encoding="utf-8"))
    cfg["segments"] = [{"series": "op", "theme": "OP"}]
    (framed / "config.yml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")

    assert sources.is_framed(framed) is False
    # 古い1本の入口が使える
    sources.add_from_upload("ep01", "op.wav", io.BytesIO(b"1"))
    assert (framed / "00_raw" / "op.wav").exists()


def _drop_segment_series(ep_dir, keep):
    cfg = yaml.safe_load((ep_dir / "config.yml").read_text(encoding="utf-8"))
    cfg["segments"] = [s for s in cfg["segments"] if s["series"] in keep]
    (ep_dir / "config.yml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_関係ない拡張子のファイルは消さない(framed):
    sources.add_frame_from_upload("ep01", "op", "op.wav", io.BytesIO(b"1"))
    (framed / "00_raw" / "op.txt").write_text("メモ", encoding="utf-8")

    sources.add_frame_from_upload("ep01", "op", "撮り直し.wav", io.BytesIO(b"2"))

    assert (framed / "00_raw" / "op.txt").exists()
    names = {f.name for f in (framed / "00_raw").iterdir()}
    assert names == {"op.wav", "op.txt"}
