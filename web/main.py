#!/usr/bin/env python3
"""10分ラジオ 制作GUI（FastAPI）

    uvicorn web.main:app --reload

build.py の関数をそのまま呼ぶだけの皮。処理の実体は build.py 側にある。
工程の実行とログ（SSE）、相談チャットは #6〜#8 で足す。
"""

from pathlib import Path

import json
import queue

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from web import episodes, media, runner, sources

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="置くラジ 制作GUI")


class Segment(BaseModel):
    # 表情差分や BGM など、将来 segments に足すキーをそのまま通す
    model_config = ConfigDict(extra="allow")

    series: str
    theme: str = ""


class NewEpisode(BaseModel):
    episode: int
    segments: list[Segment]


class Segments(BaseModel):
    segments: list[Segment]


def _as_dicts(segments):
    return [s.model_dump() for s in segments]


def _guard(fn, *args, **kwargs):
    """EpisodeError を、そのまま画面に出せる形にして返す。"""
    try:
        return fn(*args, **kwargs)
    except episodes.EpisodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/episodes")
def get_episodes():
    return _guard(lambda: {
        "episodes": episodes.list_episodes(),
        "series": episodes.series_rules(),
        "next_number": episodes.next_number(),
    })


@app.post("/api/episodes")
def post_episode(body: NewEpisode):
    return _guard(episodes.create_episode, body.episode, _as_dicts(body.segments))


@app.get("/api/episodes/{name}")
def get_episode(name: str):
    return _guard(episodes.detail, name)


@app.put("/api/episodes/{name}/segments")
def put_segments(name: str, body: Segments):
    return _guard(episodes.save_segments, name, _as_dicts(body.segments))


# ---------------------------------------------------------------- 音源と設定


class Settings(BaseModel):
    obs_dir: str = ""


class FromObs(BaseModel):
    file: str


class Echo(BaseModel):
    start: float
    end: float
    preset: str = "none"


class Echoes(BaseModel):
    echoes: list[Echo]


class Transcript(BaseModel):
    texts: list[str]


class Chapter(BaseModel):
    seconds: float
    label: str = ""


class Meta(BaseModel):
    title: str = ""
    description: str = ""
    chapters: list[Chapter] = []
    tags: list[str] = []


@app.get("/api/settings")
def get_settings():
    return {"obs_dir": _guard(sources.read_settings).get("obs_dir", "")}


@app.put("/api/settings")
def put_settings(body: Settings):
    _guard(sources.save_settings, {"obs_dir": body.obs_dir.strip()})
    return {"obs_dir": body.obs_dir.strip(), "obs": sources.obs_view()}


@app.get("/api/obs")
def get_obs():
    return _guard(sources.obs_view)


@app.get("/api/episodes/{name}/source")
def get_source(name: str):
    return _guard(sources.source_view, name)


@app.post("/api/episodes/{name}/source")
async def post_source(name: str, file: UploadFile = File(...)):
    return _guard(sources.add_from_upload, name, file.filename, file.file)


@app.post("/api/episodes/{name}/source/from-obs")
def post_source_from_obs(name: str, body: FromObs):
    return _guard(sources.add_from_obs, name, body.file)


@app.get("/api/episodes/{name}/scan")
def get_scan(name: str):
    return _guard(media.read_scan, name)


@app.get("/api/episodes/{name}/waveform")
def get_waveform(name: str):
    return _guard(media.waveform, name)


@app.get("/api/episodes/{name}/echoes")
def get_echoes(name: str):
    return {"echoes": _guard(episodes.read_echoes, name)}


@app.put("/api/episodes/{name}/echoes")
def put_echoes(name: str, body: Echoes):
    return {"echoes": _guard(episodes.save_echoes, name,
                             [e.model_dump() for e in body.echoes])}


@app.get("/api/episodes/{name}/echo-preview")
def get_echo_preview(name: str, start: float, end: float, preset: str = "none"):
    path = _guard(media.echo_preview, name, start, end, preset)
    return FileResponse(path, headers={"Cache-Control": "no-store"})


@app.get("/api/episodes/{name}/transcript")
def get_transcript(name: str):
    return _guard(media.read_transcript, name)


@app.put("/api/episodes/{name}/transcript")
def put_transcript(name: str, body: Transcript):
    return _guard(media.save_transcript, name, body.texts)


@app.get("/api/episodes/{name}/meta")
def get_meta(name: str):
    return _guard(media.read_meta, name)


@app.put("/api/episodes/{name}/meta")
def put_meta(name: str, body: Meta):
    return _guard(media.save_meta, name, body.title, body.description,
                  [c.model_dump() for c in body.chapters], body.tags)


@app.get("/api/episodes/{name}/copy")
def get_copy(name: str):
    return _guard(media.copy_texts, name)


@app.get("/api/episodes/{name}/clean")
def get_clean(name: str):
    return _guard(media.clean_result, name)


@app.post("/api/episodes/{name}/clean/confirm")
def post_clean_confirm(name: str):
    return _guard(media.confirm_clean, name)


@app.get("/api/episodes/{name}/audio/{kind}")
def get_audio(name: str, kind: str):
    path = _guard(media.audio_path, name, kind)
    # ブラウザが途中から読めるように（シーク）、Range に対応した返し方にする
    return FileResponse(path, headers={"Accept-Ranges": "bytes"})


# ---------------------------------------------------------------- 工程の実行


@app.post("/api/episodes/{name}/steps/{step}/run")
def run_step(name: str, step: str):
    return _guard(runner.start, name, step).snapshot()


@app.post("/api/job/cancel")
def cancel_job():
    return _guard(runner.cancel).snapshot(with_lines=False)


@app.get("/api/job")
def get_job():
    job = runner.current()
    return job.snapshot() if job else {"state": "なし"}


@app.get("/api/job/stream")
def stream_job():
    """実行中の工程のログと状態を流す（SSE）。"""
    job = runner.current()
    if job is None:
        raise HTTPException(status_code=404, detail="実行中の工程がありません")

    def events():
        channel = job.subscribe()
        try:
            # つないだ時点までのログを先に渡す
            yield _sse({"kind": "start", "job": job.snapshot()})
            while True:
                try:
                    event = channel.get(timeout=15)
                except queue.Empty:
                    yield ": keep-alive\n\n"   # 途中で切られないようにする
                    continue
                yield _sse(event)
                if event["kind"] == "end":
                    break
        finally:
            job.unsubscribe(channel)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


def _sse(event):
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
