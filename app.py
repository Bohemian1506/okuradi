#!/usr/bin/env python3
"""
10分ラジオ 制作GUI

    streamlit run app.py

build.py の関数をそのまま呼ぶだけの皮。処理の実体は build.py 側にある。
"""

import io
import json
import wave
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import build

ROOT = Path(__file__).parent.resolve()

st.set_page_config(page_title="ラジオ制作", layout="wide")


# ---------------------------------------------------------------- ヘルパ

def episodes():
    return sorted(d.name for d in ROOT.iterdir()
                  if d.is_dir() and (d / "config.yml").exists())


def run_step(name, ep, cfg):
    """工程を実行してログを画面に出す。"""
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            build.HANDLERS[name](ep, cfg)
    except Exception as exc:
        st.error(f"{build.STEP_LABELS[name]} で失敗しました: {exc}")
        st.code(buf.getvalue() or "(出力なし)")
        return False
    st.success(f"{build.STEP_LABELS[name]} 完了")
    with st.expander("ログ"):
        st.code(buf.getvalue() or "(出力なし)")
    return True


def envelope(path, points=1200):
    """波形の外形をDataFrameで返す。"""
    with wave.open(str(path)) as w:
        sr, n = w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    chunk = max(1, len(data) // points)
    usable = len(data) // chunk * chunk
    amp = np.abs(data[:usable].reshape(-1, chunk)).max(axis=1)
    return pd.DataFrame({"秒": np.arange(len(amp)) * chunk / sr, "音量": amp})


def waveform_chart(path, cuts):
    df = envelope(path)
    base = (alt.Chart(df)
            .mark_area(color="#5DCAA5")
            .encode(x=alt.X("秒:Q"), y=alt.Y("音量:Q", scale=alt.Scale(domain=[0, 1]))))
    if cuts:
        cdf = pd.DataFrame(cuts, columns=["start", "end"])
        overlay = (alt.Chart(cdf)
                   .mark_rect(color="#E24B4A", opacity=0.35)
                   .encode(x="start:Q", x2="end:Q"))
        return base + overlay
    return base


CUT_SCHEMA = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["start", "end", "reason"],
            },
        },
    },
    "required": ["candidates"],
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


# ---------------------------------------------------------------- サイドバー

st.sidebar.title("ラジオ制作")

eps = episodes()
if not eps:
    st.sidebar.error("回のディレクトリが見つかりません")
    st.stop()

ep_name = st.sidebar.selectbox("回", eps)
ep, cfg = build.load_episode(ROOT, ep_name)

st.sidebar.divider()
st.sidebar.caption("この回のテーマ")
for i, seg in enumerate(cfg.get("segments", [])):
    seg["theme"] = st.sidebar.text_input(
        f"{cfg['series_rules'].get(seg['series'], {}).get('label', seg['series'])}",
        seg["theme"], key=f"theme{i}",
    )
if st.sidebar.button("テーマを保存"):
    build.save_config(ep, cfg)
    st.sidebar.success("保存しました")

st.sidebar.divider()
st.sidebar.caption("進捗")
checkpoints = {
    "下見": ep["02_text"] / "scan.json",
    "カット": ep["01_cut"] / "cut.wav",
    "整音": ep["01_clean"] / "clean.wav",
    "文字起こし": ep["02_text"] / "transcript.json",
    "メタデータ": ep["03_meta"] / "meta.json",
    "動画": ep["04_video"] / f"ep{cfg['episode']:02d}.mp4",
}
for label, path in checkpoints.items():
    st.sidebar.write(("完了 " if path.exists() else "未 ") + label)


# ---------------------------------------------------------------- タブ

tab_scan, tab_cut, tab_finish, tab_chat = st.tabs(
    ["1. 下見", "2. カット", "3. 仕上げ", "Claudeに相談"]
)


# --- 1. 下見 -------------------------------------------------------

with tab_scan:
    st.subheader("収録音声を文字起こしする")
    st.caption("カット点を耳で探すのは遅いので、先にテキストにして目で探します。")

    try:
        raw = build.find_raw(ep)
        st.write(f"音声: `{raw.name}`  /  {build.hhmmss(build.audio_duration(raw))}")
        st.audio(str(raw))
    except FileNotFoundError:
        st.warning(f"{ep['00_raw']} に収録wavを置いてください")
        raw = None

    if raw and st.button("下見の文字起こしを実行", type="primary"):
        with st.spinner("Whisperで処理中（数分かかります）"):
            run_step("scan", ep, cfg)

    scan = load_json(ep["02_text"] / "scan.json")
    if scan:
        rows = [{"開始": build.hhmmss(s["start"]), "秒": s["start"], "内容": s["text"]}
                for s in scan["segments"]]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=420)


# --- 2. カット -----------------------------------------------------

with tab_cut:
    st.subheader("消す区間を決める")

    scan = load_json(ep["02_text"] / "scan.json")
    cuts = [list(c) for c in (cfg.get("cuts") or [])]

    try:
        raw = build.find_raw(ep)
        total = build.audio_duration(raw)
    except FileNotFoundError:
        st.warning("収録wavがありません")
        st.stop()

    st.altair_chart(waveform_chart(raw, cuts), use_container_width=True)
    st.caption("赤い帯が削除される区間です。")

    left, right = st.columns([3, 2])

    with left:
        st.markdown("**区間を編集**")
        edited = st.data_editor(
            pd.DataFrame(cuts or [[0.0, 0.0]], columns=["開始秒", "終了秒"]),
            num_rows="dynamic", use_container_width=True, key="cut_editor",
        )
        if st.button("カット指定を保存"):
            cfg["cuts"] = [
                [float(r["開始秒"]), float(r["終了秒"])]
                for _, r in edited.iterrows()
                if pd.notna(r["開始秒"]) and pd.notna(r["終了秒"])
                and float(r["終了秒"]) > float(r["開始秒"])
            ]
            build.save_config(ep, cfg)
            st.success(f"{len(cfg['cuts'])}箇所を保存しました")
            st.rerun()

    with right:
        st.markdown("**Claudeに候補を出させる**")
        st.caption("言い直し・詰まり・長すぎる沈黙を拾わせます。採用は自分で選びます。")

        if not scan:
            st.info("先に下見の文字起こしを実行してください")
        elif st.button("カット候補を抽出"):
            body = "\n".join(
                f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}" for s in scan["segments"]
            )
            prompt = (
                "ラジオ収録の文字起こしです。明らかな言い直し、言い淀み、"
                "録り直しのための中断、意味のない長い沈黙の区間を抽出してください。\n"
                "内容として成立している部分は絶対に含めないでください。"
                "喋りの自然な「間」も残します。迷ったら含めない方針で。\n\n"
                f"{body}"
            )
            with st.spinner("Claudeが読んでいます"):
                try:
                    res = build.call_claude(prompt, schema=CUT_SCHEMA)
                    st.session_state["candidates"] = res["structured_output"]["candidates"]
                except Exception as exc:
                    st.error(f"失敗しました: {exc}")

        for i, c in enumerate(st.session_state.get("candidates", [])):
            col_a, col_b = st.columns([4, 1])
            col_a.write(
                f"{build.hhmmss(c['start'])}〜{build.hhmmss(c['end'])}  {c.get('reason', '')}"
            )
            if col_b.button("追加", key=f"add{i}"):
                cfg.setdefault("cuts", []).append([c["start"], c["end"]])
                build.save_config(ep, cfg)
                st.rerun()

    st.divider()
    if st.button("カットして整音する", type="primary"):
        with st.spinner("処理中"):
            if run_step("cut", ep, cfg):
                run_step("clean", ep, cfg)

    clean_wav = ep["01_clean"] / "clean.wav"
    if clean_wav.exists():
        st.markdown("**整音後（ここが1つ目の確認ポイント）**")
        st.write(build.hhmmss(build.audio_duration(clean_wav)))
        st.audio(str(clean_wav))
        st.altair_chart(waveform_chart(clean_wav, []), use_container_width=True)


# --- 3. 仕上げ -----------------------------------------------------

with tab_finish:
    st.subheader("文字起こしから公開まで")

    cols = st.columns(4)
    if cols[0].button("文字起こし"):
        with st.spinner("処理中"):
            run_step("transcribe", ep, cfg)
    if cols[1].button("メタデータ生成"):
        with st.spinner("Claudeが書いています"):
            run_step("meta", ep, cfg)
    if cols[2].button("動画化"):
        with st.spinner("エンコード中"):
            run_step("video", ep, cfg)
    if cols[3].button("限定公開でアップ", type="primary"):
        with st.spinner("アップロード中"):
            run_step("upload", ep, cfg)

    st.divider()

    meta_path = ep["03_meta"] / "meta.json"
    meta = load_json(meta_path)
    if meta:
        st.markdown("**タイトルと概要欄（手で直せます）**")
        meta["title"] = st.text_input("タイトル", meta["title"])
        meta["description"] = st.text_area("概要欄", meta["description"], height=260)
        meta["tags"] = [
            t.strip() for t in
            st.text_input("タグ（カンマ区切り）", ", ".join(meta["tags"])).split(",")
            if t.strip()
        ]
        if st.button("メタデータを保存"):
            meta_path.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            st.success("保存しました")

    mp4 = ep["04_video"] / f"ep{cfg['episode']:02d}.mp4"
    if mp4.exists():
        st.markdown("**完成動画**")
        st.video(str(mp4))

    url_file = ep["04_video"] / "url.txt"
    if url_file.exists():
        st.info(f"限定公開URL: {url_file.read_text(encoding='utf-8')}")
        st.caption("観てから、YouTube側で公開に切り替えてください。")


# --- Claudeに相談 --------------------------------------------------

with tab_chat:
    st.subheader("Claudeに相談する")
    st.caption("この回の文字起こしを読んだ状態で答えます。")

    scan = load_json(ep["02_text"] / "scan.json")
    transcript = load_json(ep["02_text"] / "transcript.json") or scan

    if not transcript:
        st.info("先に下見の文字起こしを実行すると、内容を踏まえた相談ができます。")

    if "chat" not in st.session_state:
        st.session_state["chat"] = []

    for m in st.session_state["chat"]:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    if prompt := st.chat_input("例: チャプターの切り方を提案して"):
        st.session_state["chat"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        context = f"# 番組について\n{cfg['concept']}\n"
        if transcript:
            body = "\n".join(
                f"[{build.hhmmss(s['start'])}] {s['text']}"
                for s in transcript["segments"]
            )
            context += f"\n# この回の文字起こし\n{body}\n"

        with st.chat_message("assistant"):
            with st.spinner("考えています"):
                try:
                    # 履歴は Claude Code のセッション側が持つので、送るのは今回の発言だけ
                    res = build.call_claude(
                        prompt, system=context, persist=True,
                        resume=st.session_state.get("chat_session"),
                    )
                    st.session_state["chat_session"] = res["session_id"]
                    answer = res["result"]
                except Exception as exc:
                    answer = f"失敗しました: {exc}"
            st.markdown(answer)
        st.session_state["chat"].append({"role": "assistant", "content": answer})

    if st.session_state["chat"] and st.button("会話をリセット"):
        st.session_state["chat"] = []
        st.session_state.pop("chat_session", None)
        st.rerun()
