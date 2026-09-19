#!/usr/bin/env python3
"""10分ラジオ 制作GUI（FastAPI）

    uvicorn web.main:app --reload

build.py の関数をそのまま呼ぶだけの皮。処理の実体は build.py 側にある。
工程の実行とログ（SSE）、相談チャットは #6〜#8 で足す。
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from web import episodes

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="置くラジ 制作GUI")


class Segment(BaseModel):
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
    return {
        "episodes": episodes.list_episodes(),
        "series": episodes.series_rules(),
        "next_number": episodes.next_number(),
    }


@app.post("/api/episodes")
def post_episode(body: NewEpisode):
    return _guard(episodes.create_episode, body.episode, _as_dicts(body.segments))


@app.get("/api/episodes/{name}")
def get_episode(name: str):
    return _guard(episodes.detail, name)


@app.put("/api/episodes/{name}/segments")
def put_segments(name: str, body: Segments):
    return _guard(episodes.save_segments, name, _as_dicts(body.segments))


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
