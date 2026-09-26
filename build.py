#!/usr/bin/env python3
"""
30分ラジオ 自動制作パイプライン

工程:
    scan       00_raw   -> 02_text/scan.json        下見の文字起こし（カット点を探す用）
    cut        00_raw   -> 01_cut/cut.wav           config の cuts に従って区間を削除
    clean      01_cut   -> 01_clean/clean.wav       ノイズ除去・前後トリム・音量正規化
    mix        01_clean -> 01_mix/mix.wav           timeline.yml の bgm/se を重ねる（#85）
    transcribe 01_clean -> 02_text/transcript.json  確定版の文字起こし（喋りだけの音を使う）
    meta       02_text  -> 03_meta/meta.json        タイトル・概要欄・チャプター
    video      01_mix   -> 04_video/epNN.mp4        静止画と合成（timeline.yml が無い回は 01_clean を使う）
    upload     04_video -> YouTube（限定公開）

CLI:
    python build.py ep01 --to scan
    python build.py ep01 --from cut --to clean
    python build.py ep01 --from transcribe

GUI:
    streamlit run app.py
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

STEPS = ["scan", "cut", "clean", "mix", "transcribe", "meta", "video", "upload"]

STEP_LABELS = {
    "scan": "下見の文字起こし",
    "cut": "カット",
    "clean": "整音",
    "mix": "ミックス",
    "transcribe": "文字起こし（確定）",
    "meta": "メタデータ生成",
    "video": "動画化",
    "upload": "アップロード",
}


# ---------------------------------------------------------------- ユーティリティ

# 外部コマンド（ffmpeg など）の出力をぜんぶ書き出す先。
# 画面に流すのは工程自身の print だけにして、細かい出力はこちらに残す。
_detail_log = None


def open_detail_log(path):
    """くわしいログの書き出し先を開く。工程ごとに作り直す。"""
    global _detail_log
    close_detail_log()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _detail_log = path.open("w", encoding="utf-8")
    except OSError as exc:
        # ログが書けないだけで工程を止めない。ただし黙らない
        print(f"(くわしいログを残せません: {exc})", flush=True)
        _detail_log = None


def close_detail_log():
    global _detail_log
    if _detail_log:
        _detail_log.close()
        _detail_log = None


def log_detail(text):
    if _detail_log:
        _detail_log.write(text if text.endswith("\n") else text + "\n")
        _detail_log.flush()


def run(cmd):
    """外部コマンドを実行。出力を逐次読むのでGUIでも固まらない。

    画面に出すのは「$ ffmpeg ...」の1行だけ。出力そのものは、
    くわしいログ（00_logs/<工程>.log）に残す。
    """
    print(f"$ {cmd[0]} ...", flush=True)
    log_detail(f"$ {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    tail = []
    for line in proc.stdout:
        tail.append(line)
        if len(tail) > 40:
            tail.pop(0)
        log_detail(line.rstrip("\n"))
    proc.wait()
    if proc.returncode != 0:
        print("".join(tail), file=sys.stderr)
        raise RuntimeError(f"コマンドが失敗しました: {cmd[0]}")


def audio_duration(path):
    # 壊れかけのファイルで ffprobe が止まることがあるので、待ちきりにしない
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    return float(out.stdout.strip())


def hhmmss(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


VIDEO_EXTS = [".mkv", ".mp4", ".mov", ".flv"]
AUDIO_EXTS = [".wav", ".m4a"]


JOINED = "joined.wav"


def _raw_listing(raw_dir):
    """00_raw の中の、仮のファイル（`.` で始まる名前）を除いたファイル一覧。

    `web/sources.py` の `_place_raw` が書き込み中に使う一時ファイル（`.tmp-...`）が
    ここに混ざると、枠が1つしか埋まっていない間でも `_refuse_ambiguous` が
    「音源が2本あります」と誤って断ってしまう（#216 のレビュー）。
    """
    if not raw_dir.is_dir():
        return []
    return [f for f in raw_dir.iterdir() if f.is_file() and not f.name.startswith(".")]


def _timeline_sources(ep):
    """timeline.yml が並べている本編の音源を返す。無ければ None。

    `web/timeline.py` は関数の中で読む。`build.py` は `web/` を知らない側なので、
    トップで読むと向きが逆になる（`web/episodes.py` が `build` を読んでいる）。
    **輪になって落ちるかは試したが、落ちなかった**（2026-09-22。どちらの順に読んでも通る）。
    落ちないので必須ではないが、向きを保つために関数の中に置いている。
    """
    from web import timeline          # noqa: PLC0415（依存の向きを保つためここで読む）
    data = timeline.read(ep["dir"])
    if not data:
        return None
    main = data["lanes"]["main"]
    if len(main) < 2:
        return None

    # 編集点はまだ工程に繋がっていない。黙って無視すると、書いたのにかからない
    # （CLAUDE.md「静かに失敗させない」）
    has_edits = [c["id"] for c in main if c.get("edits")]
    if has_edits:
        raise ValueError(
            f"編集点（カット・エコー）は、まだ工程に繋がっていません: {'・'.join(has_edits)}。"
            "いまは音源を順に繋ぐところまでです")
    return main


def _has_timeline(ep):
    """timeline.yml がある回か（枠の回）。

    `step_clean` が頭の無音を削るかどうかの分かれ目（#85 の4段目）。
    `_timeline_sources` と同じ理由で、関数の中で読む。
    """
    from web import timeline          # noqa: PLC0415（依存の向きを保つためここで読む）
    return timeline.path(ep["dir"]).exists()


def _track_wav(video, cfg):
    """録画から音声トラックを取り出した wav を返す。無ければ作る。

    使うトラックは `config.yml` の `audio.source_track`（既定 0）。
    OBS はマイクとデスクトップ音声を別トラックにできるので、選べるようにしている。
    **`find_raw`（録画1本）と `join_sources`（録画が複数並ぶとき）の両方から呼ぶ。**
    決め方を1か所にまとめないと、片方だけ直して食い違う（#85）。
    """
    track = ((cfg or {}).get("audio") or {}).get("source_track", 0)
    dst = video.with_name(f"{video.stem}.track{track}.wav")
    if not dst.exists() or dst.stat().st_mtime < video.stat().st_mtime:
        run(["ffmpeg", "-y", "-i", str(video), "-map", f"0:a:{track}", "-vn",
             "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)])
        print(f"-> {dst}  (録画から音声を取り出しました)")
    # **取り出し直さないときも、どのトラックを使ったかを毎回出す。** 番号を前の値に戻すと、
    # 古い wav をそのまま使い、繋ぎ直されないことがある（#214）。ログで気づけるように
    print(f"   {video.name}: トラック {track} を使います（config.yml の audio.source_track）")
    return dst


def _clip_source_path(ep, clip, cfg=None):
    """timeline.yml のクリップ1つが指す音源ファイルを返す。

    録画（`VIDEO_EXTS`）なら、音声トラックを取り出した wav に差し替える
    （`find_raw` と同じ決まり。`_track_wav` 参照）。`join_sources`（本編）と
    `step_mix`（BGM・SE）の両方から使う。置き場所は仮置きで本編と同じ
    `00_raw/<Path(source).name>`（#85）。
    """
    found = ep["00_raw"] / Path(clip["source"]).name
    if not found.exists():
        raise FileNotFoundError(f"{clip['id']} の音源がありません: {found}")
    if found.suffix.lower() in VIDEO_EXTS:
        found = _track_wav(found, cfg)
    return found


def join_sources(ep, clips, cfg=None):
    """timeline.yml の並びどおりに音源を繋いで1本にする。

    **形式は必ずそろえてから繋ぐ。** 合っているかを判定して分岐しない。
    24kHz の音を 48kHz として繋ぐと、ffmpeg は何も言わずに倍速・1オクターブ上の音を作る
    （2026-09-22 に実測）。判定を間違えると気づけない壊れ方なので、常にそろえる。

    並んでいる音源が録画（`VIDEO_EXTS`）のときは、`find_raw` と同じ決まりで
    音声トラックを選ぶ（`_track_wav`）。ここで見ないと、録画1本のときと
    2本以上のときでトラックの選び方が食い違う（#85）。
    """
    raw_dir = ep["00_raw"]
    dst = raw_dir / JOINED
    parts = [_clip_source_path(ep, clip, cfg) for clip in clips]

    # **timeline.yml 自身の更新日時も見る。** 音源のファイルだけ見ていると、
    # 並びを入れ替えたときと、行を1つ消したときに繋ぎ直されない
    # （どちらも元のファイルは変わらないため。2026-09-22 にテストで見つかった）
    from web import timeline          # noqa: PLC0415（依存の向きを保つためここで読む）
    stamps = [f.stat().st_mtime for f in parts]
    written = timeline.path(ep["dir"])
    if written.exists():
        stamps.append(written.stat().st_mtime)
    # **同着のときは繋ぎ直す。** `>=` にすると、更新日時がぴったり同じときに
    # 黙って古い音を返す（2026-09-22 に再現した。録り直して 6.0秒になるべき所が 4.0秒のまま）。
    # ext4 はナノ秒まで見るので普段は起きないが、exFAT / FAT32 は粒度が粗い。
    # 同じ PR の「形式を判定して分岐しない」と同じで、迷ったら安全側に倒す
    if dst.exists() and dst.stat().st_mtime > max(stamps):
        return dst

    # 入力を並べる。gap があれば、その長さの無音を手前に挟む。
    # **挟まないと、positions が出す時刻と実際の音が食い違う**
    # （計算は gap を足しているのに、音には入っていない。2026-09-22 に実測）
    cmd = ["ffmpeg", "-y"]
    labels, gaps = [], 0
    for clip, found in zip(clips, parts):
        if clip["gap"] > 0:
            cmd += ["-f", "lavfi", "-i",
                    f"anullsrc=r=48000:cl=mono:d={clip['gap']}"]
            labels.append(None)
            gaps += 1
        cmd += ["-i", str(found)]
        labels.append(found)

    steps, names = [], []
    for i, found in enumerate(labels):
        steps.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=mono[a{i}]")
        names.append(f"[a{i}]")
    graph = ";".join(steps) + ";" + "".join(names)
    graph += f"concat=n={len(labels)}:v=0:a=1[out]"

    cmd += ["-filter_complex", graph, "-map", "[out]",
            "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)]
    run(cmd)
    made = f"{len(parts)}本を繋ぎました"
    if gaps:
        made += f"（間を{gaps}か所はさみました）"
    print(f"-> {dst}  ({made} / {hhmmss(audio_duration(dst))})")
    return dst


def find_raw(ep, cfg=None):
    """収録音声を返す。

    timeline.yml が音源を2本以上並べていれば、繋いだ1本を返す。
    OBS の録画ファイルが置いてあれば、音声だけを「録画名.trackN.wav」に取り出してそれを返す。
    録画が wav より新しければ取り出し直す。
    """
    clips = _timeline_sources(ep)
    if clips:
        return join_sources(ep, clips, cfg)

    raw_dir = ep["00_raw"]
    _refuse_ambiguous(raw_dir)
    videos = sorted(f for f in _raw_listing(raw_dir) if f.suffix.lower() in VIDEO_EXTS)
    if videos:
        return _track_wav(videos[0], cfg)

    files = [f for f in audio_files(raw_dir) if f.name != JOINED]
    if not files:
        raise FileNotFoundError(f"{raw_dir} に音声ファイルがありません")
    return files[0]


def audio_files(raw_dir):
    """音声ファイルを並べる。**拡張子の大文字小文字は見ない。**

    `glob("*.wav")` だと `second.WAV` を拾えない（Linux は大文字小文字を区別する）。
    録画側は `suffix.lower()` で吸収しているのに、音声側だけ吸収していなかった。
    そのせいで **2本あるのに1本しか見えない**ことがあった（2026-09-22 のレビューで再現）。
    """
    return sorted((f for f in _raw_listing(raw_dir) if f.suffix.lower() in AUDIO_EXTS),
                  key=lambda f: f.name)


def source_candidates(raw_dir):
    """人が置いた音源だけを並べる。アプリが作ったものは数えない。

    数えないもの:
      - `録画名.trackN.wav`（録画から取り出したもの。`find_raw` が作る）
      - `joined.wav`（繋いだもの）
    """
    videos = sorted(f for f in _raw_listing(raw_dir) if f.suffix.lower() in VIDEO_EXTS)
    stems = {v.stem for v in videos}
    others = []
    for found in audio_files(raw_dir):
        if found.name == JOINED:
            continue
        # 「録画名.track0.wav」のような名前は、その録画から取り出したもの。
        # **`find_raw` が作るのは wav だけ**なので、m4a は除外しない
        # （人が偶然その名前の m4a を置いたときに、黙って消えてしまう）
        base, _, tail = found.stem.rpartition(".")
        if found.suffix.lower() == ".wav" and base in stems and tail.startswith("track"):
            continue
        others.append(found)
    return videos + others


def _refuse_ambiguous(raw_dir):
    """音源が2本以上あるのに、どれをどの順で使うかが書いていない（#154）。

    **黙って1本目を使わない。** 2本置いた人は2本使うつもりなので、
    1本で進んだ結果は、ほぼ確実に間違っている。
    """
    found = source_candidates(raw_dir)
    if len(found) < 2:
        return
    names = "・".join(f.name for f in found)
    raise ValueError(
        f"音源が{len(found)}本あります（{names}）。どれをどの順で使うかが分かりません。\n"
        f"{raw_dir.parent.name}/timeline.yml に並びを書いてください。書き方は docs/features.md。\n"
        "1本だけ使うなら、ほかを 00_raw から出してください。"
    )


def load_episode(root, name):
    """回のディレクトリを開いて (ep, cfg) を返す。GUIからも使う。"""
    ep_dir = Path(root) / name
    cfg = yaml.safe_load((ep_dir / "config.yml").read_text(encoding="utf-8"))
    ep = {"root": Path(root), "dir": ep_dir, "name": name}
    for sub in ["00_raw", "01_cut", "01_clean", "01_mix", "02_text", "03_meta", "04_video"]:
        ep[sub] = ep_dir / sub
        ep[sub].mkdir(parents=True, exist_ok=True)
    return ep, cfg


def save_config(ep, cfg):
    (ep["dir"] / "config.yml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def preload_cuda_libs():
    """pip で入れた nvidia-cublas-cu12 / nvidia-cudnn-cu12 を先に読み込んでおく。

    ctranslate2 はライブラリを名前で探すので、読み込み済みにしておけば
    LD_LIBRARY_PATH を設定しなくても GPU で動く。入っていなければ何もしない。
    """
    import ctypes
    import site

    for sp in site.getsitepackages():
        for pattern in ["cublas/lib/libcublasLt.so.*", "cublas/lib/libcublas.so.*",
                        "cudnn/lib/libcudnn*.so.*"]:
            for lib in sorted(Path(sp, "nvidia").glob(pattern)):
                try:
                    ctypes.CDLL(str(lib), mode=ctypes.RTLD_GLOBAL)
                except OSError:
                    pass


def transcribe_file(src, cfg):
    from faster_whisper import WhisperModel

    preload_cuda_libs()
    t = cfg.get("transcribe", {})

    def run_on(device, compute_type):
        model = WhisperModel(t.get("model", "medium"), device=device, compute_type=compute_type)
        segments, _ = model.transcribe(
            str(src), language=t.get("language", "ja"), vad_filter=False
        )
        # segments は遅延評価なので、GPU の失敗はここで起きる
        return [
            {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
            for s in segments
        ]

    try:
        rows = run_on("auto", "int8")
    except RuntimeError as exc:
        print(f"(GPU で失敗したので CPU でやり直します: {exc})", flush=True)
        rows = run_on("cpu", "int8")
    return {"segments": rows, "full_text": "".join(r["text"] for r in rows)}


# ---------------------------------------------------------------- 01. 下見

def step_scan(ep, cfg):
    src = find_raw(ep, cfg)
    dst = ep["02_text"] / "scan.json"
    data = transcribe_file(src, cfg)
    data["source"] = src.name
    data["duration"] = audio_duration(src)
    dst.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {dst}  ({len(data['segments'])}セグメント)")


# ---------------------------------------------------------------- 02. カット

def normalize_cuts(cuts, total):
    """[[start, end], ...] を整理。重なりを統合し、範囲外を丸める。"""
    clean = []
    for c in cuts:
        s, e = float(c[0]), float(c[1])
        s, e = max(0.0, min(s, e)), min(total, max(s, e))
        if e - s > 0.01:
            clean.append((s, e))
    clean.sort()
    merged = []
    for s, e in clean:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def invert_ranges(cuts, total):
    """削除範囲から残す範囲を作る。"""
    keeps, pos = [], 0.0
    for s, e in cuts:
        if s - pos > 0.01:
            keeps.append((pos, s))
        pos = e
    if total - pos > 0.01:
        keeps.append((pos, total))
    return keeps


def step_cut(ep, cfg):
    src = find_raw(ep, cfg)
    dst = ep["01_cut"] / "cut.wav"
    total = audio_duration(src)
    cuts = normalize_cuts(cfg.get("cuts") or [], total)

    if not cuts:
        run(["ffmpeg", "-y", "-i", str(src), "-ar", "48000", "-ac", "1", str(dst)])
        print(f"-> {dst}  (カット指定なし / {hhmmss(total)})")
        return

    keeps = invert_ranges(cuts, total)
    if not keeps:
        raise ValueError("カット指定で音声が全部消えます")

    parts, labels = [], []
    for i, (s, e) in enumerate(keeps):
        parts.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[k{i}]")
        labels.append(f"[k{i}]")
    graph = ";".join(parts) + f";{''.join(labels)}concat=n={len(keeps)}:v=0:a=1[out]"

    run(["ffmpeg", "-y", "-i", str(src), "-filter_complex", graph,
         "-map", "[out]", "-ar", "48000", "-ac", "1", str(dst)])

    removed = sum(e - s for s, e in cuts)
    print(f"-> {dst}  ({len(cuts)}箇所 / {removed:.1f}秒カット / "
          f"{hhmmss(total)} -> {hhmmss(total - removed)})")


# ---------------------------------------------------------------- 03. 整音

# エコーのプリセット。多重タップにして、単発エコーの「ポンポン」感を抑える。
# aecho 以外の選択肢（areverb など）はこの ffmpeg には無く、afir は
# インパルス応答のファイルが要るので採らなかった（2026-09-19 の調査）。
ECHO_PRESETS = {
    "light": "aecho=0.85:0.6:40|70:0.25|0.15",
    "hall": "aecho=0.9:0.85:30|55|85|120|160|210:0.35|0.28|0.22|0.16|0.10|0.06",
}

# 区間の繋ぎ目は、そのままだと音量が急に変わってプツッと鳴る。
# 20ms 重ねて繋ぐ（繋ぎ目1か所につき、その分だけ全体が短くなる）。
ECHO_CROSSFADE = 0.02

ECHO_PRESET_LABELS = {"light": "軽め", "hall": "響く"}

# これより短い区間・すき間は扱わない（繋ぎに 20ms 要るため）
ECHO_MIN = 0.3


def normalize_echoes(echoes, total, report=True):
    """エコー区間を整える。時刻は trimmed.wav（前後のトリムまで済ませた音）が基準。

    report=False にすると、飛ばした区間のお知らせを出さない（比べるときに使う）。
    """
    rows = []
    for echo in echoes or []:
        preset = (echo.get("preset") or "").strip()
        start = max(0.0, float(echo.get("start", 0)))
        end = min(float(echo.get("end", 0)), total)
        if preset not in ECHO_PRESETS:
            if report and preset and preset != "none":
                print(f"(エコー区間 {hhmmss(start)}–{hhmmss(end)} の"
                      f"「{preset}」は知らないプリセットなのでかけません)", flush=True)
            continue                      # 「なし」は、かけないのが正しい
        if end - start < ECHO_MIN:
            if report:
                print(f"(エコー区間 {hhmmss(start)}–{hhmmss(end)} は短すぎる"
                      f"（{ECHO_MIN}秒未満）のでかけません)", flush=True)
            continue
        rows.append((start, end, preset))

    rows.sort()
    merged, skipped = [], []
    for start, end, preset in rows:
        if merged and start - merged[-1][1] < ECHO_MIN:
            # 繋ぎ目を作るだけのすき間が無い。飛ばすが、黙って消さない
            skipped.append((start, end))
            continue
        if start < ECHO_MIN:
            start = 0.0                   # 先頭すぐなら頭から
        if total - end < ECHO_MIN:
            end = total                   # 末尾すぐなら最後まで
        merged.append((start, end, preset))

    if report:
        for start, end in skipped:
            print(f"(エコー区間 {hhmmss(start)}–{hhmmss(end)} は、前の区間と近すぎる"
                  f"（{ECHO_MIN}秒未満）のでかけません)", flush=True)
    return merged


def echo_parts(regions, total):
    """音をどこで分けるか。(開始, 終了, プリセット) を順に返す。

    エコーをかける所と、かけない所を交互に並べる。
    フィルタグラフ（echo_graph）と、整音後の位置（echo_positions）の
    両方がこれを使う。分け方を1か所にしておかないと、片方だけ直したときに
    帯の位置が静かにずれる。
    """
    parts, at = [], 0.0
    for start, end, preset in regions:
        if start > at:
            parts.append((at, start, None))
        parts.append((start, end, preset))
        at = end
    if at < total:
        parts.append((at, total, None))
    return parts


def echo_graph(regions, total):
    """区間だけにエコーをかけるフィルタグラフを組む。

    aecho は区間指定（enable）に対応していないので、
    atrim で分けて、かける所だけ通し、acrossfade で繋ぎ直す。
    """
    parts = echo_parts(regions, total)

    lines, labels = [], []
    for index, (start, end, preset) in enumerate(parts):
        chain = f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS"
        if preset:
            chain += "," + ECHO_PRESETS[preset]
        lines.append(f"{chain}[p{index}]")
        labels.append(f"p{index}")

    if len(labels) == 1:
        lines[-1] = lines[-1].replace(f"[{labels[0]}]", "[echoed]")
        return ";".join(lines)

    current = labels[0]
    for index in range(1, len(labels)):
        out = "echoed" if index == len(labels) - 1 else f"x{index}"
        lines.append(f"[{current}][{labels[index]}]acrossfade=d={ECHO_CROSSFADE}[{out}]")
        current = out
    return ";".join(lines)


def echo_tail(preset):
    """aecho が足す長さ（秒）。いちばん遅いエコーの遅れぶん、音が伸びる。

    プリセットの文字列から読むので、プリセットを変えても数字がずれない。
    """
    spec = ECHO_PRESETS.get(preset)
    if not spec:
        return 0.0
    # "aecho=入力:出力:遅れ:減衰"。遅れはミリ秒で、"|" 区切り
    try:
        delays = spec.split("=", 1)[1].split(":")[2]
        return max(float(d) for d in delays.split("|")) / 1000.0
    except (IndexError, ValueError):
        return 0.0


def echo_positions(regions, total):
    """trimmed.wav の時刻で決めた区間が、clean.wav ではどこに来るか。

    2つの理由でずれる。
      - aecho は、いちばん遅いエコーの遅れぶん、その部分を伸ばす
      - acrossfade は、継ぎ目ごとに ECHO_CROSSFADE 秒だけ重ねて縮める
    後ろの区間ほど、前の区間のぶんが積み上がってずれる。
    """
    parts = echo_parts(regions, total)
    out, at = [], 0.0
    for index, (start, end, preset) in enumerate(parts):
        length = (end - start) + echo_tail(preset)
        # 継ぎ目の重なりぶんだけ前へ詰まる
        begin = at - ECHO_CROSSFADE * index
        if preset:
            out.append({"start": round(max(0.0, begin), 3),
                        "end": round(begin + length, 3),
                        "preset": preset})
        at += length
    return out


def step_clean(ep, cfg):
    src = ep["01_cut"] / "cut.wav"
    if not src.exists():
        src = find_raw(ep, cfg)
        print("(カット未実行のため 00_raw をそのまま使います)")
    head = ep["01_clean"] / "head.wav"
    trimmed = ep["01_clean"] / "trimmed.wav"
    dst = ep["01_clean"] / "clean.wav"

    a = cfg.get("audio", {})
    # **枠の回（timeline.yml がある回）は、頭の無音を削らない。** OP は 0:00〜0:15 が
    # 曲だけで、喋り手はヘッドホンで曲を聞きながら黙っている。頭を削ると、曲と喋りの
    # 位置が録音の外では取り戻せない（#85 の4段目・2026-09-26 の決定）。
    # timeline.yml が無い回（ep01 など）は今までどおり前後を削る。
    framed = _has_timeline(ep)

    # 1回目: ノイズ低減と、頭のトリム（枠の回では飛ばす）。
    trim = "silenceremove=start_periods=1:start_duration=0.1:start_threshold=-50dB"
    head_filters = []
    if a.get("denoise", True):
        head_filters.append("afftdn=nf=-25")
    if a.get("trim_silence", True) and not framed:
        head_filters.append(trim)
    before = audio_duration(src)
    run(["ffmpeg", "-y", "-i", str(src), "-af", ",".join(head_filters) or "anull",
         "-ar", "48000", "-ac", "1", str(head)])
    after_head = audio_duration(head)

    # 2回目: 尻のトリム（reverse-trim-reverse。こちらは枠の回でもかける）。
    # エコー区間の時刻はここまでの音（trimmed.wav）が基準なので、途中のファイルとして必ず残す。
    tail_filters = [trim] if a.get("trim_silence", True) else []
    run(["ffmpeg", "-y", "-i", str(head), "-af",
         ("areverse," + ",".join(tail_filters) + ",areverse") if tail_filters else "anull",
         "-ar", "48000", "-ac", "1", str(trimmed)])
    total = audio_duration(trimmed)

    # **denoise（afftdn）の分も含む。** 無音を削っていなくても、フィルタの遅延で
    # 一定量（約0.025秒・2026-09-26 に実測）縮む。トリムだけの量ではないので、
    # ここから「トリムで削れた秒数」を正確に逆算することはできない
    head_removed = round(before - after_head, 2)
    tail_removed = round(after_head - total, 2)
    note = "（枠の回のため頭は削っていません）" if framed else ""
    print(f"-> {trimmed}  ({hhmmss(total)})  前後のトリムまで"
          f"（頭 {head_removed:.1f}秒・尻 {tail_removed:.1f}秒を削除{note}）")

    # 3回目: エコーをかけてから正規化。
    # 正規化は必ず最後。エコーで足した分も、ここで天井に収まる。
    loudnorm = f"loudnorm=I={a.get('target_lufs', -14)}:TP=-1.5:LRA=11"
    regions = normalize_echoes(cfg.get("echoes"), total)

    if regions:
        graph = echo_graph(regions, total) + f";[echoed]{loudnorm}[out]"
        run(["ffmpeg", "-y", "-i", str(trimmed), "-filter_complex", graph,
             "-map", "[out]", "-ar", "48000", "-ac", "1", str(dst)])
        where = ", ".join(f"{ECHO_PRESET_LABELS[p]} {hhmmss(s)}–{hhmmss(e)}"
                          for s, e, p in regions)
        print(f"-> {dst}  ({hhmmss(audio_duration(dst))})  エコー{len(regions)}区間: {where}")
    else:
        run(["ffmpeg", "-y", "-i", str(trimmed), "-af", loudnorm,
             "-ar", "48000", "-ac", "1", str(dst)])
        print(f"-> {dst}  ({hhmmss(audio_duration(dst))})")

    # 整音の結果を残す。GUI がこれを読んで「整音結果」に出す。
    (ep["01_clean"] / "clean.json").write_text(json.dumps({
        "source": src.name,
        "source_duration": round(before, 2),
        "trimmed_duration": round(total, 2),
        "duration": round(audio_duration(dst), 2),
        "removed": round(before - total, 2),
        "head_removed": head_removed,
        "tail_removed": tail_removed,
        "framed": framed,
        "target_lufs": a.get("target_lufs", -14),
        "echoes": [{"start": s, "end": e, "preset": p} for s, e, p in regions],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- 04. ミックス（BGM・SE を重ねる）

MIX_LOUDNORM = "loudnorm=I={target}:TP=-1.5:LRA=11"


def volume_expr(points):
    """音量カーブ（{time, volume} の折れ線）から、ffmpeg `volume` フィルタの式を組む。

    `eval=frame` にすると、区間を切って繋ぎ直す（いまのエコーと同じやり方）よりも
    尺が変わらない（#82 で実測）。点の間は直線で結ぶ。最初の点より前・最後の点より後は、
    その端の値のまま（外側までは動かさない）。
    """
    if not points:
        return None
    pts = sorted(points, key=lambda p: p["time"])
    expr = str(pts[-1]["volume"])
    for i in range(len(pts) - 1, 0, -1):
        t0, v0 = pts[i - 1]["time"], pts[i - 1]["volume"]
        t1, v1 = pts[i]["time"], pts[i]["volume"]
        seg = f"({v0}+({v1}-{v0})*(t-{t0})/({t1}-{t0}))"
        expr = f"if(between(t,{t0},{t1}),{seg},{expr})"
    expr = f"if(lt(t,{pts[0]['time']}),{pts[0]['volume']},{expr})"
    return f"volume=eval=frame:volume='{expr}'"


def _mix_overlay_chain(clip, lane, cfg):
    """1本の BGM・SE クリップを、重ねる前にどう加工するか（フィルタの並び）。

    - **曲（bgm）は、重ねる前に喋りと同じラウドネスにそろえる**（喋り＝clean.wav は触らない）。
      SE（ピンポーン・ブッブーなど）は短く、`loudnorm` は数秒未満の音には向かないので、
      仮置きでかけない（#85 のコメントに無い判断。報告に書く）
    - **音量カーブ（`volume`）は、クリップの先頭からの秒（`eval=frame` の `t`）で当てる。**
      まだ位置をずらす前（`adelay` の前）にかけないと、原点がずれる
    """
    filters = []
    if lane == "bgm":
        target = (cfg.get("audio") or {}).get("target_lufs", -14)
        filters.append(MIX_LOUDNORM.format(target=target))
    expr = volume_expr(clip.get("volume"))
    if expr:
        filters.append(expr)
    return filters


# 本編の「生の長さの積み上げ」と、実際の clean.wav の長さの、許す差。
# denoise（afftdn）だけで、フィルタの遅延ぶん一定に約0.025秒縮むと実測した
# （2026-09-26、レビューで指摘）。その4倍ほどの余白を持たせる。
# これを超えて食い違うのは、カット・config のエコー・（将来の #85 6段目の）
# 編集点で、本編クリップの生の長さと clean.wav の長さの対応が崩れているとき
MIX_POSITION_TOLERANCE = 0.1


def _read_clean_json(ep):
    path = ep["01_clean"] / "clean.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _clip_audio_duration(clip, path):
    """`audio_duration` を、失敗したときにクリップの id が分かる形にして呼ぶ。

    壊れたファイルだと ffprobe が空を返し、`float('')` の
    `ValueError: could not convert string to float: ''` がそのまま出る。
    それだけだと**どのクリップで壊れているか分からない**（レビューで指摘）。
    """
    try:
        return audio_duration(path)
    except ValueError as exc:
        raise ValueError(
            f"{clip['id']} の音源の長さが読めません（壊れているかもしれません）: "
            f"{path}（{exc}）") from exc


def _check_mix_positions(ep, main, durations):
    """本編クリップの生の長さの積み上げが、実際の clean.wav の長さと合っているか。

    合っていないと、`positions()` が出す位置と実際の音がずれる。**cut.wav が
    あるかどうかでは判定しない**（`step_cut` は cuts が空でも毎回 cut.wav を書くので、
    それだけで判定すると、カットを1つも使っていない回まで止まってしまう
    ＝2026-09-26 のレビューで見つかった不具合）。
    """
    clean_json = _read_clean_json(ep)
    if not clean_json or "head_removed" not in clean_json or "tail_removed" not in clean_json:
        print("(位置が合っているか確かめられません: 01_clean/clean.json に記録がありません。"
              "整音をやり直すと確かめられるようになります)", flush=True)
        return

    raw_total = sum(durations[clip["id"]] + clip["gap"] for clip in main)
    expected = raw_total - clean_json["head_removed"] - clean_json["tail_removed"]
    clean_total = audio_duration(ep["01_clean"] / "clean.wav")
    if abs(expected - clean_total) > MIX_POSITION_TOLERANCE:
        raise ValueError(
            f"本編の長さが合いません（生の長さからの見積もり {hhmmss(expected)} / "
            f"実際の clean.wav {hhmmss(clean_total)}）。カットや config.yml の "
            "エコーで長さが変わった可能性があります。位置の変換はまだ実装していません"
            "（#85 の6段目）。"
        )


def step_mix(ep, cfg):
    """整音した喋り（clean.wav）に、timeline.yml の bgm・se を重ねる。

    - **bgm・se が1つも無い回でも mix.wav を作る**（clean.wav と同じ音）。
      `video` がいつも mix.wav を読めるようにするため
    - 重ねるのは `amix=duration=first:normalize=0`（#79 で実測。どちらも既定値だと
      危ない。既定だと尺が伸びる／喋りに被っていない所まで音量が下がる）
    - 位置は `web/timeline.py` の `positions`（錨のクリップの先頭 + `at`）。渡す長さは
      **clean.wav の時間軸に合う長さ**（`step_clean` は頭を削らないので、本編クリップの
      生の長さ + gap でそのまま出る。尻を削った分は最後のクリップの末尾だけに効く）
    """
    src = ep["01_clean"] / "clean.wav"
    if not src.exists():
        raise FileNotFoundError(f"{src} がありません。先に整音（clean）を実行してください")
    dst = ep["01_mix"] / "mix.wav"
    clean_total = audio_duration(src)

    from web import timeline          # noqa: PLC0415（依存の向きを保つためここで読む）
    data = timeline.read(ep["dir"])

    overlays = []           # (lane, clip) の並び。bgm を先に、se を後に重ねる
    if data:
        overlays += [("bgm", c) for c in data["lanes"]["bgm"]]
        overlays += [("se", c) for c in data["lanes"]["se"]]

    if not overlays:
        run(["ffmpeg", "-y", "-i", str(src), "-ar", "48000", "-ac", "1",
             "-c:a", "pcm_s16le", str(dst)])
        print(f"-> {dst}  ({hhmmss(clean_total)})  重ねる BGM・SE はありません"
              "（clean.wav と同じ音です）")
        _write_mix_json(ep, src, dst, clean_total, [])
        return

    main = data["lanes"]["main"]
    durations = {clip["id"]: _clip_audio_duration(clip, _clip_source_path(ep, clip, cfg))
                 for clip in main}
    # **位置がずれていないかは、長さで確かめる**（cut.wav の有無では判定しない。上を参照）
    _check_mix_positions(ep, main, durations)
    positions = timeline.positions(data, durations)

    cmd = ["ffmpeg", "-y", "-i", str(src)]
    chains = []
    labels = ["[0:a]"]
    for index, (lane, clip) in enumerate(overlays, start=1):
        found = _clip_source_path(ep, clip, cfg)
        clip_total = _clip_audio_duration(clip, found)
        at = positions[clip["id"]]

        if at > clean_total + 0.01:
            raise ValueError(
                f"{clip['id']} の位置（{hhmmss(at)}）が番組の長さ（{hhmmss(clean_total)}）"
                "を超えています。timeline.yml の at を見直してください")
        # 曲（bgm）が、被さっているコーナーの終わりより先に尽きるか。
        # **BGM だけ見る**（SE は短く鳴らして終わるものなので、対象外・レビューで指摘）。
        # 「クリップの長さ」ではなく「at + 曲の長さ」でコーナーの終わりと比べる
        # （曲がコーナーの途中から鳴るときは、そこからの残り時間と比べるのが正しい）
        anchor_total = durations.get(clip.get("anchor"))
        if lane == "bgm" and anchor_total is not None:
            covers = clip.get("at", 0) + clip_total
            if covers < anchor_total:
                # 止めない。番組の仕様は「曲の長さ ＞ コーナーの尺」だが、
                # ここで止めると曲を差し替えるまで何も進められなくなる（#82・仮置き）
                print(f"({clip['id']}: 曲がコーナーの終わり（{hhmmss(anchor_total)}）より"
                      f"{hhmmss(anchor_total - covers)}早く尽きます。曲が先に終わります)",
                      flush=True)
        # 曲・SE の終わりが、番組の末尾を超えて切れるか。
        # `amix` は `duration=first` で全体の尺を保つので、超えたぶんは黙って切られる
        if at + clip_total > clean_total + 0.05:
            print(f"({clip['id']}: 終わり（{hhmmss(at + clip_total)}）が番組の長さ"
                  f"（{hhmmss(clean_total)}）を超えるので、末尾が切れます)", flush=True)

        cmd += ["-i", str(found)]
        filters = _mix_overlay_chain(clip, lane, cfg) + [
            f"adelay=delays={round(at * 1000)}:all=1"]
        chains.append(f"[{index}:a]{','.join(filters)}[m{index}]")
        labels.append(f"[m{index}]")

    graph = ";".join(chains) + f";{''.join(labels)}" \
        f"amix=inputs={len(labels)}:duration=first:normalize=0[out]"
    cmd += ["-filter_complex", graph, "-map", "[out]",
            "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)]
    run(cmd)

    mix_total = audio_duration(dst)
    if abs(mix_total - clean_total) > 0.02:
        # amix は duration=first で尺を保つはずなので、ここに来たら組み方がおかしい
        print(f"!! mix.wav の長さ（{mix_total:.3f}秒）が clean.wav（{clean_total:.3f}秒）"
              "と合っていません", flush=True)
    print(f"-> {dst}  ({hhmmss(mix_total)})  BGM {len(data['lanes']['bgm'])}本・"
          f"SE {len(data['lanes']['se'])}本を重ねました")
    _write_mix_json(ep, src, dst, mix_total, overlays)


def _write_mix_json(ep, src, dst, duration, overlays):
    """ミックスの結果を残す。GUI が読んで「古い」判定や表示に使う想定。"""
    (ep["01_mix"] / "mix.json").write_text(json.dumps({
        "source": src.name,
        "duration": round(duration, 2),
        "bgm": sum(1 for lane, _ in overlays if lane == "bgm"),
        "se": sum(1 for lane, _ in overlays if lane == "se"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- 05. 文字起こし（確定）

def step_transcribe(ep, cfg):
    src = ep["01_clean"] / "clean.wav"
    dst = ep["02_text"] / "transcript.json"
    data = transcribe_file(src, cfg)
    # 聴きながら直せるように、元の文字を各行に残す（GUI が直した行に印を付ける）
    for row in data["segments"]:
        row["original"] = row["text"]
    dst.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {dst}  ({len(data['segments'])}セグメント / {len(data['full_text'])}文字)")


# ---------------------------------------------------------------- 06. メタデータ生成

META_INSTRUCTION = """\
あなたはこのラジオ番組の編集担当です。文字起こしを読んで、YouTubeの公開情報を作ってください。

# 番組について
{concept}

# この回のコーナー
{segments}

# タイトルの規則
{title_rules}

# 章の見出しの規則
{chapter_rules}

# 文字起こし（タイムコード付き）
{transcript}

# 出力の条件
- title: 60文字以内。タイトル規則に従う。煽らない。内容と一致させる。
- description: 概要欄。3〜5行。最後に訂正歓迎の一文を必ず入れる。
- chapters: [{{"seconds": 数値, "label": "見出し"}}] の配列。上の「この回のコーナー」と1対1にする（同じ数・同じ順番）。最初は必ず seconds: 0。**見出しは「章の見出しの規則」のとおりに書く。**
- tags: 文字列の配列。5〜10個。日本語中心。
"""


META_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "chapters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"seconds": {"type": "number"}, "label": {"type": "string"}},
                "required": ["seconds", "label"],
            },
        },
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "description", "chapters", "tags"],
}


def call_claude(prompt, schema=None, system=None, resume=None, persist=False):
    """Claude Code を headless で呼ぶ。サブスクの枠で動かす。

    戻り値は claude -p --output-format json の結果そのまま。
    schema を渡すと structured_output に検証済みの値が入る。
    会話を続けるときは persist=True で始め、session_id を resume に渡す。
    """
    cmd = ["claude", "-p", "--output-format", "json", "--model", "sonnet",
           # 文章を返すだけなので、ツール・MCP・スキル・ユーザー設定は読ませない
           "--tools", "", "--strict-mcp-config", "--disable-slash-commands",
           "--setting-sources", ""]
    if system:
        cmd += ["--system-prompt", system]
    if schema:
        cmd += ["--json-schema", json.dumps(schema, ensure_ascii=False)]
    if resume:
        cmd += ["--resume", resume]
    elif not persist:
        cmd.append("--no-session-persistence")

    # APIキーがあるとサブスクではなく従量課金で呼ばれるので外す
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    # --resume は同じ作業ディレクトリでないとセッションを見つけられない
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              env=env, cwd=Path(__file__).parent, timeout=600)
    except FileNotFoundError:
        raise RuntimeError(
            "claude コマンドが見つかりません（Claude Code を入れてログインしてください）")
    except subprocess.TimeoutExpired:
        raise RuntimeError("claude の返事が10分を過ぎました。もう一度お試しください")
    except OSError as exc:
        raise RuntimeError(f"claude を呼べませんでした: {exc}")
    try:
        res = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"claude の実行に失敗しました: {proc.stderr or proc.stdout}")
    if res.get("is_error"):
        raise RuntimeError(f"claude がエラーを返しました: {res.get('result')}")
    return res


CHAPTER_HEAD = "--- 目次 ---"

# 概要欄に必ず入れるクレジット（#137）。
# **毎回付ける。「この回は使ったか」で判定しない。**
# 判定が要ると、判定を間違えた回だけ落ちる。規約の義務なので、落ちても気づけない形は避ける。
CREDITS = ["VOICEVOX:ずんだもん"]


def _flat(text):
    """クレジットを見比べるための形にそろえる。

    大文字小文字・全角半角のコロン・空白のゆれで、二重に付くのを防ぐ
    （2026-09-22 のレビューで `voicevox:` や `VOICEVOX: ` が二重になった）。
    """
    return (text or "").lower().replace("：", ":").replace(" ", "").replace("\u3000", "")


def credits_in(description):
    """概要欄に入っているクレジットを返す。画面が「入っているか」を見るのに使う。

    **行がまるごと一致するかで見る。** 部分一致だと、本文でクレジットに触れただけで
    「入っている」ことになり、**規約が求める体裁の行が入らないまま確定する**
    （番組が VOICEVOX を扱う回は普通にある。2026-09-22 のレビューで再現した）。
    """
    lines = {_flat(line) for line in (description or "").splitlines()}
    return [c for c in CREDITS if _flat(c) in lines]


def youtube_description(meta):
    """YouTube に貼る概要欄。クレジットと目次を、本文のうしろにつなげる。

    **通しも切り抜きも、必ずここを通す**（#137 / #91）。道が分かれると、
    片方だけクレジットが落ちても気づけない。

    #7 より前に作った meta.json は、概要欄にすでに目次が焼き込まれている。
    そのときは足さない（足すと目次が二重に付く）。
    """
    description = (meta.get("description") or "").rstrip()

    # クレジットは毎回。すでに入っていれば足さない（手で書いた回と二重にしない）
    have = credits_in(description)
    missing = [c for c in CREDITS if c not in have]
    if missing:
        block = "\n".join(missing)
        if CHAPTER_HEAD in description:
            # 古い回は概要欄に目次が焼き込まれている。**その前に入れる**。
            # うしろに付けると「本文 → クレジット → 目次」の並びが崩れる
            head, _, tail = description.partition(CHAPTER_HEAD)
            description = f"{head.rstrip()}\n\n{block}\n\n{CHAPTER_HEAD}{tail}"
        else:
            description = "\n\n".join(filter(None, [description, block]))

    chapters = sorted(meta.get("chapters") or [], key=lambda c: c.get("seconds", 0))
    if not chapters or CHAPTER_HEAD in description:
        return description
    lines = "\n".join(f"{hhmmss(c['seconds'])} {c['label']}" for c in chapters)
    return f"{description}\n\n{CHAPTER_HEAD}\n{lines}"


def step_meta(ep, cfg):
    transcript = json.loads((ep["02_text"] / "transcript.json").read_text(encoding="utf-8"))
    dst = ep["03_meta"] / "meta.json"

    rules = cfg.get("series_rules", {})
    seg_lines, rule_lines, chapter_lines = [], [], []
    for s in cfg["segments"]:
        r = rules.get(s["series"], {})
        label = r.get("label", s["series"])
        seg_lines.append(f"- 枠: {label} / テーマ: {s['theme']}")
        # title_hint が無いコーナー（OP・告知・ED）は、タイトルの規則に出さない。
        # 空の行を出すと、規則が無いのか書き忘れたのか分からなくなる。
        if r.get("title_hint"):
            rule_lines.append(f"- {label}: {r['title_hint']}")
        # 章の見出し（r-hoso #52・案c）。
        # **コーナー名と違うことがある**（「告知」→目次では「お知らせ」）。
        # **テーマを付けるのは中身のあるコーナーだけ**（目次は検索の入口）。
        head = r.get("chapter_label") or label
        if r.get("chapter_theme"):
            chapter_lines.append(f"- {label} → 「{head} ＋ その回のテーマ」")
        else:
            chapter_lines.append(f"- {label} → 「{head}」だけ。テーマは付けない")

    body = "\n".join(f"[{hhmmss(r['start'])}] {r['text']}" for r in transcript["segments"])
    res = call_claude(META_INSTRUCTION.format(
        concept=cfg["concept"].strip(),
        segments="\n".join(seg_lines),
        chapter_rules="\n".join(chapter_lines),
        title_rules="\n".join(rule_lines),
        transcript=body,
    ), schema=META_SCHEMA)

    # 失敗時の切り分け用に生の応答を残す
    (ep["03_meta"] / "raw_response.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    meta = res["structured_output"]

    meta["tags"] = list(dict.fromkeys(
        meta.get("tags", []) + cfg.get("youtube", {}).get("extra_tags", [])
    ))
    # 章は概要欄に焼き込まない。別に持っておき、YouTube に貼るときにつなげる。
    # 焼き込むと、章だけを直せなくなる（docs/components.md）。
    meta["chapters"] = sorted(meta.get("chapters", []), key=lambda c: c["seconds"])

    dst.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {dst}\n   タイトル: {meta['title']}")


# ---------------------------------------------------------------- 07. 動画化

def step_video(ep, cfg):
    # **timeline.yml が無い回（枠でない回。ep01 など）は、mix を待たない。**
    # 重ねる曲が無い回なので、整音の音（clean.wav）をそのまま使う（2026-09-26 のユーザーの判断）。
    # timeline.yml がある回は、今までどおり mix.wav が無ければ止める
    # （黙って clean.wav に切り替えない。CLAUDE.md「静かに失敗させない」）
    if _has_timeline(ep):
        wav = ep["01_mix"] / "mix.wav"
        if not wav.exists():
            raise FileNotFoundError(
                f"{wav} がありません。先にミックス（mix）を実行してください")
    else:
        wav = ep["01_clean"] / "clean.wav"
        if not wav.exists():
            raise FileNotFoundError(
                f"{wav} がありません。先に整音（clean）を実行してください")
        print("(曲が無い回なので、整音の音を使います)")
    dst = ep["04_video"] / f"ep{cfg['episode']:02d}.mp4"
    total = audio_duration(wav)

    images = cfg.get("images", [])
    if not images:
        raise ValueError("config.yml の images が空です")

    lines = []
    for img in images:
        path = (ep["root"] / img["file"]).resolve()
        if not path.exists():
            raise FileNotFoundError(f"画像がありません: {path}")
        dur = total if img.get("duration") == "full" else float(img["duration"])
        lines.append(f"file '{path.as_posix()}'\nduration {dur:.3f}")
    last = (ep["root"] / images[-1]["file"]).resolve()
    lines.append(f"file '{last.as_posix()}'")

    listfile = ep["04_video"] / "images.txt"
    listfile.write_text("\n".join(lines) + "\n", encoding="utf-8")

    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
         "-i", str(wav), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "2",
         "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
         "-c:a", "aac", "-b:a", "192k", "-shortest", str(dst)])
    print(f"-> {dst}")


# ---------------------------------------------------------------- 08. アップロード

def step_upload(ep, cfg):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    root = ep["root"]
    token_path, secret_path = root / "token.json", root / "client_secret.json"

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # 初回だけブラウザが開く。GUIの外に出る唯一の操作。
            flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), scopes)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    meta = json.loads((ep["03_meta"] / "meta.json").read_text(encoding="utf-8"))
    video = ep["04_video"] / f"ep{cfg['episode']:02d}.mp4"
    yt = cfg.get("youtube", {})

    youtube = build("youtube", "v3", credentials=creds)
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": meta["title"],
                "description": youtube_description(meta),
                "tags": meta["tags"],
                "categoryId": yt.get("category_id", "28"),
            },
            "status": {
                "privacyStatus": yt.get("privacy", "unlisted"),
                "selfDeclaredMadeForKids": False,
            },
        },
        media_body=MediaFileUpload(str(video), chunksize=-1, resumable=True),
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"アップロード中 {int(status.progress() * 100)}%", flush=True)

    url = f"https://youtu.be/{response['id']}"
    (ep["04_video"] / "url.txt").write_text(url, encoding="utf-8")
    print(f"-> {url}\n限定公開で上がりました。観てから自分で公開してください。")


# ---------------------------------------------------------------- 実行

HANDLERS = {
    "scan": step_scan, "cut": step_cut, "clean": step_clean, "mix": step_mix,
    "transcribe": step_transcribe, "meta": step_meta,
    "video": step_video, "upload": step_upload,
}


def episodes_root():
    """回（ep01 など）を置く場所。

    既定はこのファイル（build.py）と同じ場所。環境変数 `OKURADI_EPISODES_DIR` が
    あれば、そこを使う（担当が一時フォルダに向けて試すため。#221）。
    **`claude -p` や `gh` の cwd（コードの場所）はこれと別**で、そちらは変えない
    （`call_claude` の `cwd=Path(__file__).parent` を見よ）。

    指定された場所が無い・フォルダでないときは、黙って直下に戻さず理由を出して
    止める（本物のつもりで一時フォルダの綴りを間違えたときに気づけるように）。
    """
    override = os.environ.get("OKURADI_EPISODES_DIR")
    if not override:
        # **Claude から起動されたのに一時フォルダが指定されていなければ、本物を使わずに止める**（#221・案A'）。
        # Claude Code が打つコマンドには環境変数 CLAUDECODE が付き、`bash -c`・`nohup`・子のプロセスにも
        # 引き継がれる。コマンドの文字列を読む hook と違い、書き方ではすり抜けられない。
        # ユーザーの端末には付かないので、番組づくりは今までどおり。ユーザーが `!` で本物を動かすときは
        # OKURADI_REAL=1 を付ける（Claude の打つコマンドにこの語があれば hook が止める。`!` には hook が効かない）
        if os.environ.get("CLAUDECODE") and os.environ.get("OKURADI_REAL") != "1":
            raise RuntimeError(
                "Claude から起動されたので、本物の回（リポジトリ直下）は使いません（#221）。"
                "試すときは OKURADI_EPISODES_DIR を一時フォルダに向けてください（docs/testing.md）。"
                "本物で動かすときは、ユーザーが自分の端末か `! OKURADI_REAL=1 ...` で打ちます")
        return Path(__file__).parent.resolve()
    root = Path(override).expanduser().resolve()
    if not root.is_dir():
        raise RuntimeError(
            f"OKURADI_EPISODES_DIR がフォルダではありません: {root}"
        )
    return root


def main():
    p = argparse.ArgumentParser(description="30分ラジオ 自動制作パイプライン")
    p.add_argument("episode")
    p.add_argument("--from", dest="start", choices=STEPS, default=STEPS[0])
    p.add_argument("--to", dest="end", choices=STEPS, default=STEPS[-1])
    args = p.parse_args()

    try:
        root = episodes_root()
    except RuntimeError as exc:
        sys.exit(str(exc))
    print(f"[okuradi] 回の置き場所: {root}")

    if not (root / args.episode).exists():
        sys.exit(f"{root / args.episode} がありません")

    ep, cfg = load_episode(root, args.episode)
    for name in STEPS[STEPS.index(args.start): STEPS.index(args.end) + 1]:
        print(f"\n[{name}] {STEP_LABELS[name]}")
        open_detail_log(ep["dir"] / "00_logs" / f"{name}.log")
        try:
            HANDLERS[name](ep, cfg)
        except BaseException as exc:
            # **止まった理由をログに残す。** これが無いと 00_logs/<工程>.log には
            # ffmpeg の出力までしか入らず、なぜ止まったかは端末にしか出ない（#154）。
            # **BaseException で受けるのは、Ctrl+C で止めたことも残したいため。**
            # 必ず投げ直すので、握りつぶしにはならない
            log_detail(f"!! {STEP_LABELS[name]}が止まりました: {type(exc).__name__}: {exc}")
            print(f"!! {STEP_LABELS[name]}が止まりました: {exc}", file=sys.stderr)
            raise
        finally:
            close_detail_log()
    print("\n完了")


if __name__ == "__main__":
    main()
