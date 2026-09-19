#!/usr/bin/env python3
"""
10分ラジオ 自動制作パイプライン

工程:
    scan       00_raw   -> 02_text/scan.json        下見の文字起こし（カット点を探す用）
    cut        00_raw   -> 01_cut/cut.wav           config の cuts に従って区間を削除
    clean      01_cut   -> 01_clean/clean.wav       ノイズ除去・前後トリム・音量正規化
    transcribe 01_clean -> 02_text/transcript.json  確定版の文字起こし
    meta       02_text  -> 03_meta/meta.json        タイトル・概要欄・チャプター
    video      01_clean -> 04_video/epNN.mp4        静止画と合成
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

STEPS = ["scan", "cut", "clean", "transcribe", "meta", "video", "upload"]

STEP_LABELS = {
    "scan": "下見の文字起こし",
    "cut": "カット",
    "clean": "整音",
    "transcribe": "文字起こし（確定）",
    "meta": "メタデータ生成",
    "video": "動画化",
    "upload": "アップロード",
}


# ---------------------------------------------------------------- ユーティリティ

def run(cmd):
    """外部コマンドを実行。出力を逐次読むのでGUIでも固まらない。"""
    print(f"$ {cmd[0]} ...", flush=True)
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    tail = []
    for line in proc.stdout:
        tail.append(line)
        if len(tail) > 40:
            tail.pop(0)
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


def find_raw(ep, cfg=None):
    """収録音声を返す。

    OBS の録画ファイルが置いてあれば、音声だけを「録画名.trackN.wav」に取り出してそれを返す。
    録画が wav より新しければ取り出し直す。
    """
    raw_dir = ep["00_raw"]
    videos = sorted(f for f in raw_dir.iterdir() if f.suffix.lower() in VIDEO_EXTS)
    if videos:
        # OBS はマイクとデスクトップ音声を別トラックにできるので、使うトラックを選べるようにする
        track = ((cfg or {}).get("audio") or {}).get("source_track", 0)
        src = videos[0]
        dst = src.with_name(f"{src.stem}.track{track}.wav")
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            run(["ffmpeg", "-y", "-i", str(src), "-map", f"0:a:{track}", "-vn",
                 "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)])
            print(f"-> {dst}  (録画から音声を取り出しました)")
        return dst

    files = sorted(raw_dir.glob("*.wav")) + sorted(raw_dir.glob("*.m4a"))
    if not files:
        raise FileNotFoundError(f"{raw_dir} に音声ファイルがありません")
    return files[0]


def load_episode(root, name):
    """回のディレクトリを開いて (ep, cfg) を返す。GUIからも使う。"""
    ep_dir = Path(root) / name
    cfg = yaml.safe_load((ep_dir / "config.yml").read_text(encoding="utf-8"))
    ep = {"root": Path(root), "dir": ep_dir, "name": name}
    for sub in ["00_raw", "01_cut", "01_clean", "02_text", "03_meta", "04_video"]:
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


def echo_graph(regions, total):
    """区間だけにエコーをかけるフィルタグラフを組む。

    aecho は区間指定（enable）に対応していないので、
    atrim で分けて、かける所だけ通し、acrossfade で繋ぎ直す。
    """
    parts, at = [], 0.0
    for start, end, preset in regions:
        if start > at:
            parts.append((at, start, None))
        parts.append((start, end, preset))
        at = end
    if at < total:
        parts.append((at, total, None))

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


def step_clean(ep, cfg):
    src = ep["01_cut"] / "cut.wav"
    if not src.exists():
        src = find_raw(ep, cfg)
        print("(カット未実行のため 00_raw をそのまま使います)")
    trimmed = ep["01_clean"] / "trimmed.wav"
    dst = ep["01_clean"] / "clean.wav"

    a = cfg.get("audio", {})

    # 1回目: ノイズ低減と前後のトリムまで。
    # エコー区間の時刻はこの音が基準なので、途中のファイルとして必ず残す。
    filters = []
    if a.get("denoise", True):
        filters.append("afftdn=nf=-25")
    if a.get("trim_silence", True):
        trim = "silenceremove=start_periods=1:start_duration=0.1:start_threshold=-50dB"
        filters += [trim, "areverse", trim, "areverse"]
    before = audio_duration(src)
    run(["ffmpeg", "-y", "-i", str(src), "-af", ",".join(filters) or "anull",
         "-ar", "48000", "-ac", "1", str(trimmed)])
    total = audio_duration(trimmed)
    print(f"-> {trimmed}  ({hhmmss(total)})  前後のトリムまで"
          f"（前後で {before - total:.1f}秒を削除）")

    # 2回目: エコーをかけてから正規化。
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
        "target_lufs": a.get("target_lufs", -14),
        "echoes": [{"start": s, "end": e, "preset": p} for s, e, p in regions],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- 04. 文字起こし（確定）

def step_transcribe(ep, cfg):
    src = ep["01_clean"] / "clean.wav"
    dst = ep["02_text"] / "transcript.json"
    data = transcribe_file(src, cfg)
    # 聴きながら直せるように、元の文字を各行に残す（GUI が直した行に印を付ける）
    for row in data["segments"]:
        row["original"] = row["text"]
    dst.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {dst}  ({len(data['segments'])}セグメント / {len(data['full_text'])}文字)")


# ---------------------------------------------------------------- 05. メタデータ生成

META_INSTRUCTION = """\
あなたはこのラジオ番組の編集担当です。文字起こしを読んで、YouTubeの公開情報を作ってください。

# 番組について
{concept}

# この回のコーナー
{segments}

# タイトルの規則
{title_rules}

# 文字起こし（タイムコード付き）
{transcript}

# 出力の条件
- title: 60文字以内。タイトル規則に従う。煽らない。内容と一致させる。
- description: 概要欄。3〜5行。最後に訂正歓迎の一文を必ず入れる。
- chapters: [{{"seconds": 数値, "label": "見出し"}}] の配列。3〜6個。最初は必ず seconds: 0。
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
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                          env=env, cwd=Path(__file__).parent, timeout=600)
    try:
        res = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"claude の実行に失敗しました: {proc.stderr or proc.stdout}")
    if res.get("is_error"):
        raise RuntimeError(f"claude がエラーを返しました: {res.get('result')}")
    return res


CHAPTER_HEAD = "--- 目次 ---"


def youtube_description(meta):
    """YouTube に貼る概要欄。概要欄のうしろに目次をつなげる。

    #7 より前に作った meta.json は、概要欄にすでに目次が焼き込まれている。
    そのときは足さない（足すと目次が二重に付く）。
    """
    description = (meta.get("description") or "").rstrip()
    chapters = sorted(meta.get("chapters") or [], key=lambda c: c.get("seconds", 0))
    if not chapters or CHAPTER_HEAD in description:
        return description
    lines = "\n".join(f"{hhmmss(c['seconds'])} {c['label']}" for c in chapters)
    return f"{description}\n\n{CHAPTER_HEAD}\n{lines}"


def step_meta(ep, cfg):
    transcript = json.loads((ep["02_text"] / "transcript.json").read_text(encoding="utf-8"))
    dst = ep["03_meta"] / "meta.json"

    rules = cfg.get("series_rules", {})
    seg_lines, rule_lines = [], []
    for s in cfg["segments"]:
        r = rules.get(s["series"], {})
        seg_lines.append(f"- 枠: {r.get('label', s['series'])} / テーマ: {s['theme']}")
        rule_lines.append(f"- {r.get('label', s['series'])}: {r.get('title_hint', '')}")

    body = "\n".join(f"[{hhmmss(r['start'])}] {r['text']}" for r in transcript["segments"])
    res = call_claude(META_INSTRUCTION.format(
        concept=cfg["concept"].strip(),
        segments="\n".join(seg_lines),
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


# ---------------------------------------------------------------- 06. 動画化

def step_video(ep, cfg):
    wav = ep["01_clean"] / "clean.wav"
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


# ---------------------------------------------------------------- 07. アップロード

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
    "scan": step_scan, "cut": step_cut, "clean": step_clean,
    "transcribe": step_transcribe, "meta": step_meta,
    "video": step_video, "upload": step_upload,
}


def main():
    p = argparse.ArgumentParser(description="10分ラジオ 自動制作パイプライン")
    p.add_argument("episode")
    p.add_argument("--from", dest="start", choices=STEPS, default=STEPS[0])
    p.add_argument("--to", dest="end", choices=STEPS, default=STEPS[-1])
    args = p.parse_args()

    root = Path(__file__).parent.resolve()
    if not (root / args.episode).exists():
        sys.exit(f"{root / args.episode} がありません")

    ep, cfg = load_episode(root, args.episode)
    for name in STEPS[STEPS.index(args.start): STEPS.index(args.end) + 1]:
        print(f"\n[{name}] {STEP_LABELS[name]}")
        HANDLERS[name](ep, cfg)
    print("\n完了")


if __name__ == "__main__":
    main()
