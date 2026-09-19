"""web/media.py のテスト（下見の文字起こしと、音声の配り方）。"""

import json

import pytest

from web import episodes, media


@pytest.fixture
def ep(tmp_path, monkeypatch):
    ep_dir = tmp_path / "ep01"
    for sub in ["00_raw", "01_clean", "02_text", "03_meta", "04_video"]:
        (ep_dir / sub).mkdir(parents=True)
    monkeypatch.setattr(episodes, "resolve", lambda name, root=None: ep_dir)
    return ep_dir


def write_scan(ep_dir, source="rec.wav", segments=None):
    (ep_dir / "02_text" / "scan.json").write_text(json.dumps({
        "segments": segments if segments is not None else [
            {"start": 0.0, "end": 5.0, "text": " こんばんは "},
        ],
        "full_text": "こんばんは",
        "source": source,
        "duration": 59.5,
    }, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- 下見

def test_下見がなければ未実行(ep):
    assert media.read_scan("ep01") == {"state": "未実行", "segments": []}


def test_下見を読むと行と長さが返る(ep):
    write_scan(ep)
    got = media.read_scan("ep01")
    assert got["state"] == "表示"
    assert got["duration"] == 59.5
    assert got["source"] == "rec.wav"
    assert got["segments"] == [{"start": 0.0, "end": 5.0, "text": "こんばんは"}]


def test_壊れた下見は理由を言って断る(ep):
    (ep / "02_text" / "scan.json").write_text("{壊れた", encoding="utf-8")
    with pytest.raises(episodes.EpisodeError, match="scan.json が読めません"):
        media.read_scan("ep01")


# ---------------------------------------------------------------- 音声

def test_下見の音は下見をかけた音そのもの(ep):
    (ep / "00_raw" / "rec.wav").write_bytes(b"a")
    (ep / "00_raw" / "ほか.wav").write_bytes(b"b")
    write_scan(ep, source="rec.wav")
    assert media.audio_path("ep01", "scan").name == "rec.wav"


def test_下見の前でも音源は聴ける(ep):
    (ep / "00_raw" / "rec.m4a").write_bytes(b"a")
    assert media.audio_path("ep01", "scan").name == "rec.m4a"


def test_音源がなければ断る(ep):
    with pytest.raises(episodes.EpisodeError, match="音源がありません"):
        media.audio_path("ep01", "scan")


def test_下見のsourceで回の外は指せない(ep, tmp_path):
    outside = tmp_path / "ひみつ.wav"
    outside.write_bytes("だめ".encode())
    (ep / "00_raw" / "rec.wav").write_bytes(b"a")
    write_scan(ep, source="../ひみつ.wav")
    # 名前だけを使うので、00_raw の外には出ない
    got = media.audio_path("ep01", "scan")
    assert got.parent == ep / "00_raw"
    assert got.name == "rec.wav"


def test_整音後の音はclean_wav(ep):
    (ep / "01_clean" / "clean.wav").write_bytes(b"a")
    assert media.audio_path("ep01", "clean").name == "clean.wav"


def test_整音していなければ断る(ep):
    with pytest.raises(episodes.EpisodeError, match="整音後の音声がありません"):
        media.audio_path("ep01", "clean")


def test_知らない種類は断る(ep):
    with pytest.raises(episodes.EpisodeError, match="知らない種類"):
        media.audio_path("ep01", "なにか")


# ---------------------------------------------------------------- 波形

def make_wav(path, seconds=1.0, rate=48000):
    import math
    import struct
    import wave as wavemod
    with wavemod.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        frames = int(rate * seconds)
        out.writeframes(b"".join(
            struct.pack("<h", int(20000 * math.sin(i / 50))) for i in range(frames)
        ))


def test_整音していなければ波形は未実行(ep):
    got = media.waveform("ep01")
    assert got["state"] == "未実行"
    assert "整音" in got["reason"]


def test_波形はtrimmedの長さと在りかを返す(ep):
    # 形（peaks）はブラウザが wav を読んで描くので、サーバーは在りかだけを返す（#36）
    make_wav(ep / "01_clean" / "trimmed.wav", seconds=1.0)
    got = media.waveform("ep01")
    assert got["state"] == "表示"
    assert round(got["duration"], 2) == 1.0
    assert got["url"] == "/api/episodes/ep01/audio/trimmed"
    assert got["at"] > 0                # 作り直したら読み直させるための目印


def test_波形の音はtrimmedを配る(ep):
    make_wav(ep / "01_clean" / "trimmed.wav", seconds=1.0)
    assert media.audio_path("ep01", "trimmed").name == "trimmed.wav"


def test_整音前はtrimmedを配らない(ep):
    with pytest.raises(episodes.EpisodeError, match="先に整音"):
        media.audio_path("ep01", "trimmed")


def test_波形はcleanではなくtrimmedを見る(ep):
    make_wav(ep / "01_clean" / "clean.wav")
    assert media.waveform("ep01")["state"] == "未実行"


# ---------------------------------------------------------------- 試聴

def test_整音前は試聴できない(ep):
    with pytest.raises(episodes.EpisodeError, match="先に整音"):
        media.echo_preview("ep01", 1.0, 2.0, "light")


def test_短すぎる区間は試聴できない(ep):
    make_wav(ep / "01_clean" / "trimmed.wav", seconds=3.0)
    with pytest.raises(episodes.EpisodeError, match="短すぎます"):
        media.echo_preview("ep01", 1.0, 1.01, "light")


# ---------------------------------------------------------------- 整音の結果

def test_整音していなければ結果は未実行(ep):
    assert media.clean_result("ep01") == {"state": "未実行"}


def test_整音の結果を読む(ep):
    (ep / "01_clean" / "clean.wav").write_bytes(b"a")
    (ep / "01_clean" / "clean.json").write_text(json.dumps({
        "duration": 57.14, "removed": 2.47, "target_lufs": -14,
        "echoes": [{"start": 5, "end": 9, "preset": "light"}],
    }), encoding="utf-8")
    got = media.clean_result("ep01")
    assert got["state"] == "完了"
    assert got["confirmed"] is False
    assert got["duration"] == 57.14
    assert got["removed"] == 2.47
    assert got["echoes"] == 1


def test_記録が無くても結果は出す(ep):
    (ep / "01_clean" / "clean.wav").write_bytes(b"a")
    got = media.clean_result("ep01")
    assert got["state"] == "完了"
    assert got["duration"] is None


def test_確認したを押すと確認済みになる(ep):
    (ep / "01_clean" / "clean.wav").write_bytes(b"a")
    assert media.confirm_clean("ep01")["confirmed"] is True
    assert media.clean_result("ep01")["confirmed"] is True


def test_整音をやり直すと未確認に戻る(ep):
    import os
    import time
    clean = ep / "01_clean" / "clean.wav"
    clean.write_bytes(b"a")
    media.confirm_clean("ep01")
    time.sleep(0.01)
    os.utime(clean, (time.time(), time.time()))       # やり直した
    assert media.clean_result("ep01")["confirmed"] is False


def test_整音していなければ確認できない(ep):
    with pytest.raises(episodes.EpisodeError, match="まだ整音していません"):
        media.confirm_clean("ep01")


# ---------------------------------------------------------------- 「古い」の判定

def clean_with(ep_dir, echoes, trimmed=57.11):
    (ep_dir / "01_clean" / "clean.wav").write_bytes(b"a")
    (ep_dir / "01_clean" / "clean.json").write_text(json.dumps({
        "duration": 57.14, "removed": 2.47, "target_lufs": -14,
        "trimmed_duration": trimmed, "echoes": echoes,
    }), encoding="utf-8")


def set_echoes(ep_dir, echoes):
    import yaml
    (ep_dir / "config.yml").write_text(
        yaml.safe_dump({"episode": 1, "echoes": echoes}, allow_unicode=True),
        encoding="utf-8")


def test_エコー区間を変えると古いになる(ep):
    clean_with(ep, [{"start": 5, "end": 9, "preset": "light"}])
    set_echoes(ep, [{"start": 20, "end": 24, "preset": "hall"}])
    got = media.clean_result("ep01")
    assert got["state"] == "古い"
    assert "エコー区間" in got["stale_reason"]


def test_同じエコー区間なら古くならない(ep):
    rows = [{"start": 5, "end": 9, "preset": "light"}]
    clean_with(ep, rows)
    set_echoes(ep, rows)
    assert media.clean_result("ep01")["state"] == "完了"


def test_かからない区間が残っていても古くならない(ep):
    """config には飛ばされた区間も残る。clean.json には実際にかけた分だけ入る。"""
    clean_with(ep, [{"start": 5, "end": 9, "preset": "light"}])
    set_echoes(ep, [
        {"start": 5, "end": 9, "preset": "light"},
        {"start": 9.1, "end": 12, "preset": "hall"},   # 近すぎるので、かからない
        {"start": 30, "end": 34, "preset": "none"},    # 「なし」なので、かからない
    ])
    assert media.clean_result("ep01")["state"] == "完了"


def test_音源を差し替えると古いになる(ep):
    import os
    import time
    clean_with(ep, [])
    set_echoes(ep, [])
    later = time.time() + 10
    (ep / "00_raw" / "rec.wav").write_bytes(b"a")
    os.utime(ep / "00_raw" / "rec.wav", (later, later))
    got = media.clean_result("ep01")
    assert got["state"] == "古い"
    assert "音源" in got["stale_reason"]


def test_古いときは確認済みにならない(ep):
    clean_with(ep, [{"start": 5, "end": 9, "preset": "light"}])
    set_echoes(ep, [{"start": 5, "end": 9, "preset": "light"}])
    media.confirm_clean("ep01")
    assert media.clean_result("ep01")["confirmed"] is True
    set_echoes(ep, [{"start": 20, "end": 24, "preset": "hall"}])
    assert media.clean_result("ep01")["confirmed"] is False


def test_clean_json_が壊れた形でも落ちない(ep):
    (ep / "01_clean" / "clean.wav").write_bytes(b"a")
    (ep / "01_clean" / "clean.json").write_text(json.dumps({"echoes": 5}), encoding="utf-8")
    got = media.clean_result("ep01")
    assert got["state"] in ("完了", "古い")
    assert got["echoes"] == 0


def test_整音後の波形に出す帯を返す(ep):
    """帯は clean.wav の時刻。trimmed の時刻のままだと後ろほどずれる（#42）。"""
    (ep / "01_clean" / "clean.wav").write_bytes(b"a")
    (ep / "01_clean" / "clean.json").write_text(json.dumps({
        "trimmed_duration": 57.1149, "duration": 57.31,
        "echoes": [{"start": 10.0, "end": 20.0, "preset": "light"},
                   {"start": 30.0, "end": 35.0, "preset": "hall"}],
    }), encoding="utf-8")
    bands = media.clean_result("ep01")["bands"]
    assert [b["preset"] for b in bands] == ["light", "hall"]
    assert bands[0]["start"] == 9.98          # 継ぎ目のぶん前へ詰まる
    assert bands[1]["start"] == 30.01         # 前の区間の尾のぶん後ろへ
    assert bands[1]["end"] == 35.22


def test_エコーが無ければ帯も無い(ep):
    (ep / "01_clean" / "clean.wav").write_bytes(b"a")
    (ep / "01_clean" / "clean.json").write_text(json.dumps({
        "trimmed_duration": 57.11, "echoes": [],
    }), encoding="utf-8")
    assert media.clean_result("ep01")["bands"] == []


def test_記録が壊れていても帯で落ちない(ep):
    (ep / "01_clean" / "clean.wav").write_bytes(b"a")
    (ep / "01_clean" / "clean.json").write_text(json.dumps({
        "trimmed_duration": 57.11, "echoes": [{"start": "あ", "end": 9}],
    }), encoding="utf-8")
    assert media.clean_result("ep01")["bands"] == []


def test_記録に長さが無ければ帯は出さない(ep):
    # trimmed_duration が無いと、どこに来るか計算できない
    (ep / "01_clean" / "clean.wav").write_bytes(b"a")
    (ep / "01_clean" / "clean.json").write_text(json.dumps({
        "echoes": [{"start": 10.0, "end": 20.0, "preset": "light"}],
    }), encoding="utf-8")
    assert media.clean_result("ep01")["bands"] == []


# ---------------------------------------------------------------- 動画のポスター

def test_動画が無ければポスターも無い(ep):
    (ep / "config.yml").write_text("episode: 1\n", encoding="utf-8")
    path, why = media.make_poster(ep)
    assert path is None and why is None


def test_ffmpegが無ければ理由を返す(ep, monkeypatch):
    (ep / "config.yml").write_text("episode: 1\n", encoding="utf-8")
    (ep / "04_video" / "ep01.mp4").write_bytes(b"a")

    def missing(cmd):
        raise FileNotFoundError("ffmpeg")
    monkeypatch.setattr(media.build, "run", missing)
    path, why = media.make_poster(ep)
    assert path is None
    assert "ffmpeg" in why            # 黙って隠さない


def test_ffmpegが何も出さなければ理由を返す(ep, monkeypatch):
    (ep / "config.yml").write_text("episode: 1\n", encoding="utf-8")
    (ep / "04_video" / "ep01.mp4").write_bytes(b"a")
    monkeypatch.setattr(media.build, "run", lambda cmd: None)
    path, why = media.make_poster(ep)
    assert path is None
    assert why


def test_動画より新しいポスターは作り直さない(ep, monkeypatch):
    (ep / "config.yml").write_text("episode: 1\n", encoding="utf-8")
    (ep / "04_video" / "ep01.mp4").write_bytes(b"a")
    (ep / "04_video" / "poster.jpg").write_bytes(b"p")
    called = []
    monkeypatch.setattr(media.build, "run", lambda cmd: called.append(cmd))
    path, why = media.make_poster(ep)
    assert path is not None and why is None
    assert called == []               # ffmpeg を動かさない


# ---------------------------------------------------------------- 確定版の文字起こし

def write_transcript(ep_dir, rows):
    (ep_dir / "02_text" / "transcript.json").write_text(json.dumps({
        "segments": rows, "full_text": "".join(r.get("text", "") for r in rows),
    }, ensure_ascii=False), encoding="utf-8")


def test_文字起こしが無ければ未実行(ep):
    got = media.read_transcript("ep01")
    assert got["state"] == "未実行" and got["segments"] == []


def test_元の文字が無い古いファイルは直していない扱い(ep):
    write_transcript(ep, [{"start": 0, "end": 4, "text": "こんばんは"}])
    got = media.read_transcript("ep01")
    assert got["segments"][0]["original"] == "こんばんは"
    assert got["segments"][0]["changed"] is False
    assert got["changed"] == 0


def test_直した行に印が付く(ep):
    write_transcript(ep, [
        {"start": 0, "end": 4, "text": "直した", "original": "もとの"},
        {"start": 4, "end": 8, "text": "そのまま", "original": "そのまま"},
    ])
    got = media.read_transcript("ep01")
    assert [r["changed"] for r in got["segments"]] == [True, False]
    assert got["changed"] == 1


def test_保存すると元の文字が残る(ep):
    write_transcript(ep, [{"start": 0, "end": 4, "text": "もとの"}])
    got = media.save_transcript("ep01", ["直した"])
    assert got["segments"][0]["text"] == "直した"
    assert got["segments"][0]["original"] == "もとの"      # 古いファイルにも足す
    assert got["changed"] == 1


def test_二度目の保存でも最初の元の文字を保つ(ep):
    write_transcript(ep, [{"start": 0, "end": 4, "text": "もとの"}])
    media.save_transcript("ep01", ["一度目"])
    got = media.save_transcript("ep01", ["二度目"])
    assert got["segments"][0]["original"] == "もとの"


def test_行の数が合わなければ断る(ep):
    write_transcript(ep, [{"start": 0, "end": 4, "text": "あ"}])
    with pytest.raises(episodes.EpisodeError, match="行の数が合いません"):
        media.save_transcript("ep01", ["あ", "い"])


def test_保存すると全文も作り直す(ep):
    write_transcript(ep, [{"start": 0, "end": 4, "text": "あ"},
                          {"start": 4, "end": 8, "text": "い"}])
    media.save_transcript("ep01", ["A", "B"])
    saved = json.loads((ep / "02_text" / "transcript.json").read_text(encoding="utf-8"))
    assert saved["full_text"] == "AB"


def test_文字起こしをしていなければ保存できない(ep):
    with pytest.raises(episodes.EpisodeError, match="まだ文字起こし"):
        media.save_transcript("ep01", ["あ"])


def test_壊れた文字起こしは理由を言って断る(ep):
    (ep / "02_text" / "transcript.json").write_text("{壊れた", encoding="utf-8")
    with pytest.raises(episodes.EpisodeError, match="transcript.json が読めません"):
        media.read_transcript("ep01")


# ---------------------------------------------------------------- メタデータ

def write_meta(ep_dir, **data):
    base = {"title": "タイトル", "description": "本文", "chapters": [], "tags": []}
    base.update(data)
    (ep_dir / "03_meta" / "meta.json").write_text(
        json.dumps(base, ensure_ascii=False), encoding="utf-8")


def test_メタデータが無ければ未実行(ep):
    assert media.read_meta("ep01")["state"] == "未実行"


def test_章は時刻の順に並べて返す(ep):
    write_meta(ep, chapters=[{"seconds": 60, "label": "後"}, {"seconds": 0, "label": "先"}])
    got = media.read_meta("ep01")
    assert [c["label"] for c in got["chapters"]] == ["先", "後"]


# ---- 保留チェック

def test_保留中が残っていたら止める(ep):
    write_meta(ep, title="（保留中）", description="（保留中）")
    issues = media.read_meta("ep01")["issues"]
    assert "タイトルが（保留中）のままです" in issues
    assert "概要欄が（保留中）のままです" in issues


def test_章が無ければ止める(ep):
    write_meta(ep, chapters=[])
    assert "章がありません。1つ以上必要です" in media.read_meta("ep01")["issues"]


def test_見出しの無い章があれば止める(ep):
    write_meta(ep, chapters=[{"seconds": 0, "label": "あいさつ"},
                             {"seconds": 60, "label": "  "}])
    assert any("見出しがありません" in i for i in media.read_meta("ep01")["issues"])


def test_そろっていれば問題なし(ep):
    write_meta(ep, title="今更聞けない○○", description="本文\n訂正歓迎です。",
               chapters=[{"seconds": 0, "label": "あいさつ"}], tags=["RUNTEQ"])
    assert media.read_meta("ep01")["issues"] == []


def test_タイトルが空でも止める(ep):
    write_meta(ep, title="   ")
    assert "タイトルが空です" in media.read_meta("ep01")["issues"]


# ---- 保存

def test_保存すると章は並び直しタグの重なりは1つになる(ep):
    write_meta(ep)
    got = media.save_meta("ep01", "題", "本文",
                          [{"seconds": 60, "label": "後"}, {"seconds": 0, "label": "先"}],
                          ["RUNTEQ", "RUNTEQ", " OSI ", ""])
    assert [c["label"] for c in got["chapters"]] == ["先", "後"]
    assert got["tags"] == ["RUNTEQ", "OSI"]


def test_メタデータを作っていなければ保存できない(ep):
    with pytest.raises(episodes.EpisodeError, match="まだメタデータ"):
        media.save_meta("ep01", "題", "本文", [], [])


# ---- コピー

def test_コピーは概要欄の末尾に目次を付ける(ep):
    write_meta(ep, title="題", description="本文",
               chapters=[{"seconds": 0, "label": "あいさつ"},
                         {"seconds": 125, "label": "本題"}],
               tags=["RUNTEQ", "OSI"])
    got = media.copy_texts("ep01")
    assert got["issues"] == []
    assert got["description"] == "本文\n\n--- 目次 ---\n0:00 あいさつ\n2:05 本題"
    assert got["tags"] == "RUNTEQ, OSI"


def test_コピーにも保留チェックの結果を付ける(ep):
    write_meta(ep, title="（保留中）", chapters=[])
    assert len(media.copy_texts("ep01")["issues"]) >= 2


# ---------------------------------------------------------------- 動画

def test_動画が無ければ未実行(ep):
    (ep / "config.yml").write_text("episode: 1\n", encoding="utf-8")
    assert media.video_view("ep01")["state"] == "未実行"


def test_動画があれば置き場と大きさを返す(ep, monkeypatch):
    (ep / "config.yml").write_text("episode: 1\n", encoding="utf-8")
    (ep / "04_video" / "ep01.mp4").write_bytes(b"x" * 2048)
    monkeypatch.setattr(media, "duration_of", lambda path: 676.0)
    monkeypatch.setattr(media, "video_size", lambda path: "1920x1080")
    got = media.video_view("ep01")
    assert got["state"] == "完了"
    assert got["name"] == "ep01/04_video/ep01.mp4"
    assert got["duration"] == "11:16"
    assert got["resolution"] == "1920x1080"
    assert got["size"] == "2.0 KB"


def test_大きさの書き方():
    assert media.human_size(900) == "900 B"
    assert media.human_size(1536) == "1.5 KB"
    assert media.human_size(224561234) == "214.2 MB"


def test_動画の置き場が無ければフォルダを開けない(ep):
    (ep / "config.yml").write_text("episode: 1\n", encoding="utf-8")
    import shutil as sh
    (ep / "04_video").rmdir()
    with pytest.raises(episodes.EpisodeError, match="置き場"):
        media.open_folder("ep01")


# ---------------------------------------------------------------- コピー（保存前の直しから）

def test_コピーは保存前の直しからも作れる(ep):
    write_meta(ep, title="（保留中）", description="（保留中）", chapters=[])
    draft = {"title": "直した題", "description": "直した本文",
             "chapters": [{"seconds": 0, "label": "あいさつ"}], "tags": ["RUNTEQ"]}
    got = media.copy_texts("ep01", draft)
    assert got["issues"] == []
    assert got["title"] == "直した題"
    assert got["description"] == "直した本文\n\n--- 目次 ---\n0:00 あいさつ"


def test_下書きが保留のままなら問題を返す(ep):
    write_meta(ep)
    draft = {"title": "（保留中）", "description": "本文", "chapters": [], "tags": []}
    assert len(media.copy_texts("ep01", draft)["issues"]) >= 2


# ---------------------------------------------------------------- 読めないとき

def test_長さが読めなくても落ちない(ep):
    assert media.duration_of(ep / "ありません.mp4") is None


def test_大きさが読めなくても落ちない(ep):
    assert media.video_size(ep / "ありません.mp4") == ""


def test_開く手立てが無ければ場所を伝えて断る(ep, monkeypatch):
    (ep / "config.yml").write_text("episode: 1\n", encoding="utf-8")
    monkeypatch.setattr(media.shutil, "which", lambda name: None)
    with pytest.raises(episodes.EpisodeError, match="この環境では開けません"):
        media.open_folder("ep01")


# ---------------------------------------------------------------- くわしいログ

def test_ログが無ければなしと返す(ep):
    assert media.detail_log("ep01", "clean") == {"state": "なし", "lines": []}


def test_ログを読む(ep):
    (ep / "00_logs").mkdir()
    (ep / "00_logs" / "clean.log").write_text("$ ffmpeg ...\nsize= 1kB\n", encoding="utf-8")
    got = media.detail_log("ep01", "clean")
    assert got["state"] == "表示"
    assert got["lines"] == ["$ ffmpeg ...", "size= 1kB"]
    assert got["dropped"] == 0


def test_長いログは末尾だけ返す(ep):
    (ep / "00_logs").mkdir()
    (ep / "00_logs" / "clean.log").write_text(
        "\n".join(str(i) for i in range(500)), encoding="utf-8")
    got = media.detail_log("ep01", "clean")
    assert len(got["lines"]) == media.LOG_TAIL
    assert got["lines"][-1] == "499"
    assert got["dropped"] == 500 - media.LOG_TAIL


def test_GUI_で使わない工程のログは断る(ep):
    with pytest.raises(episodes.EpisodeError, match="知らない工程"):
        media.detail_log("ep01", "cut")


# ---------------------------------------------------------------- 動画の「古い」

def test_整音をやり直すと動画が古いになる(ep, monkeypatch):
    import os
    import time
    (ep / "config.yml").write_text("episode: 1\n", encoding="utf-8")
    monkeypatch.setattr(media, "duration_of", lambda path: 57.0)
    monkeypatch.setattr(media, "video_size", lambda path: "1920x1080")

    (ep / "04_video" / "ep01.mp4").write_bytes(b"x")
    (ep / "01_clean" / "clean.wav").write_bytes(b"x")
    later = time.time() + 10
    os.utime(ep / "01_clean" / "clean.wav", (later, later))

    got = media.video_view("ep01")
    assert got["state"] == "古い"
    assert got["stale_reason"] == "整音をやり直しました"


def test_整音より新しければ完了のまま(ep, monkeypatch):
    import os
    import time
    (ep / "config.yml").write_text("episode: 1\n", encoding="utf-8")
    monkeypatch.setattr(media, "duration_of", lambda path: 57.0)
    monkeypatch.setattr(media, "video_size", lambda path: "")

    (ep / "01_clean" / "clean.wav").write_bytes(b"x")
    (ep / "04_video" / "ep01.mp4").write_bytes(b"x")
    later = time.time() + 10
    os.utime(ep / "04_video" / "ep01.mp4", (later, later))

    got = media.video_view("ep01")
    assert got["state"] == "完了"
    assert got["stale_reason"] is None
    assert got["at"] > 0           # 作り直したら新しい動画を読ませるための印


def test_長さが読めなくても完了として出す(ep, monkeypatch):
    (ep / "config.yml").write_text("episode: 1\n", encoding="utf-8")
    monkeypatch.setattr(media, "duration_of", lambda path: None)
    monkeypatch.setattr(media, "video_size", lambda path: "")
    (ep / "04_video" / "ep01.mp4").write_bytes(b"x")
    assert media.video_view("ep01")["duration"] == ""
