"""工程を動かし、進み具合とログを流す。

#3 で「サーバーの中の別スレッドで実行し、ログと状態を SSE で流す」と決めた。
ただし `docs/components.md` の「実装で直すところ」に
「中止できるようにする。工程を別のプロセスで動かし、止められるようにする」ともある。

そこで **サーバーのスレッドが、工程の子プロセスを見張る** 形にした。
- サーバーは止まらない（#3 の狙い）
- 子プロセスなので止められる（components.md の狙い）。faster-whisper は
  Python の中で動くので、スレッドのままでは止める手段がない

子プロセスは `python build.py <回> --from <工程> --to <工程>`。
コマンドで番組を作る道と同じものを通るので、GUI と CLI で処理がずれない
（CLAUDE.md「GUI が完成するまでもコマンドで番組を作れる状態を保つ」）。
"""

import queue
import os
import signal
import subprocess
import sys
import threading
import time

import build

from web import episodes

# build.py 自身の場所（コードの場所）。回を置く場所（episodes.ROOT）とは別
# （#221）。子プロセスの cwd も、これまでどおりコードの場所にする
ROOT = episodes.CODE_ROOT

# GUI から動かせる工程。build.py の cut と upload は GUI では使わない。
RUNNABLE = ["scan", "clean", "mix", "transcribe", "meta", "video"]


class Job:
    """実行中（または直前に終わった）1つの工程。"""

    def __init__(self, episode, step):
        self.episode = episode
        self.step = step
        self.label = build.STEP_LABELS[step]
        self.state = "処理中"
        self.lines = []
        self.started_at = time.time()
        self.ended_at = None
        self.cancelled = False
        self.proc = None
        self._lock = threading.Lock()
        self._subscribers = []

    # ---------------------------------------------------------- 見せる形

    def snapshot(self, with_lines=True):
        data = {
            "episode": self.episode,
            "step": self.step,
            "label": self.label,
            "state": self.state,
            "elapsed": round((self.ended_at or time.time()) - self.started_at, 1),
        }
        if with_lines:
            data["lines"] = list(self.lines)
        return data

    # ---------------------------------------------------------- 流す

    def subscribe(self):
        channel = queue.Queue()
        with self._lock:
            self._subscribers.append(channel)
        return channel

    def unsubscribe(self, channel):
        with self._lock:
            if channel in self._subscribers:
                self._subscribers.remove(channel)

    def _publish(self, event):
        with self._lock:
            for channel in self._subscribers:
                channel.put(event)

    def add_line(self, line):
        self.lines.append(line)
        # ログが際限なく伸びないようにする（画面で見るのは末尾）
        if len(self.lines) > 2000:
            del self.lines[:1000]
        self._publish({"kind": "log", "line": line})

    def finish(self, state):
        self.state = state
        self.ended_at = time.time()
        self._publish({"kind": "state", "job": self.snapshot(with_lines=False)})
        self._publish({"kind": "end"})


_current = None
_lock = threading.Lock()


def current():
    return _current


def busy():
    return _current is not None and _current.state == "処理中"


def start(name, step):
    """工程を1つ動かし始める。すぐ返る。"""
    global _current
    if step not in RUNNABLE:
        raise episodes.EpisodeError(f"GUI からは動かせない工程です: {step}")
    ep_dir = episodes.resolve(name)

    with _lock:
        if busy():
            raise episodes.EpisodeError(
                f"{_current.episode} の{_current.label}を実行中です。終わるまで待つか、中止してください"
            )
        job = Job(name, step)
        _current = job

    cfg = episodes.read_config(ep_dir)
    target = episodes.artifact(ep_dir, step, cfg)
    # 途中で止めた・失敗したときに、作りかけを見分けるための置き場
    job.target = {
        "scan": ep_dir / "02_text" / "scan.json",
        "clean": ep_dir / "01_clean" / "clean.wav",
        "mix": ep_dir / "01_mix" / "mix.wav",
        "transcribe": ep_dir / "02_text" / "transcript.json",
        "meta": ep_dir / "03_meta" / "meta.json",
        "video": ep_dir / "04_video" / f"ep{episodes.episode_number(cfg, ep_dir):02d}.mp4",
    }[step]
    job.target_before = target.stat().st_mtime if target else None

    threading.Thread(target=_run, args=(job,), daemon=True).start()
    return job


def _run(job):
    cmd = [sys.executable, str(ROOT / "build.py"), job.episode,
           "--from", job.step, "--to", job.step]
    job.add_line(f"$ {' '.join(cmd[1:])}")
    try:
        # 自分のプロセスグループにしておくと、子の子（ffmpeg）ごと止められる。
        # env=os.environ のまま渡す（環境変数をそのまま引き継ぐ）。build.py が
        # OKURADI_EPISODES_DIR を見て「回を置く場所」を決めるので、GUI と CLI で
        # ずれないようにするため（#221）
        job.proc = subprocess.Popen(
            cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, start_new_session=True, env=dict(os.environ),
        )
    except OSError as exc:
        job.add_line(f"工程を始められませんでした: {exc}")
        job.finish("エラー")
        return

    for line in job.proc.stdout:
        job.add_line(line.rstrip("\n"))
    code = job.proc.wait()

    if job.cancelled:
        _discard_unfinished(job)
        job.add_line("中止しました")
        job.finish("中止")
    elif code == 0:
        job.finish("完了")
    else:
        _discard_unfinished(job)
        job.add_line(f"失敗しました（終了コード {code}）")
        job.finish("エラー")


def _discard_unfinished(job):
    """この実行で作りかけになったファイルを消す。

    前の実行でできていたファイルは消さない（更新日時で見分ける）。
    """
    target = job.target
    if not target.exists():
        return
    if job.target_before is not None and target.stat().st_mtime <= job.target_before:
        return  # 前のまま。手を付けていない
    try:
        target.unlink()
        job.add_line(f"作りかけを消しました: {target.name}")
    except OSError as exc:
        job.add_line(f"作りかけを消せませんでした: {exc}")


def cancel():
    job = _current
    if job is None or job.state != "処理中":
        raise episodes.EpisodeError("実行中の工程がありません")
    job.cancelled = True
    if job.proc and job.proc.poll() is None:
        try:
            os.killpg(os.getpgid(job.proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError) as exc:
            job.add_line(f"止められませんでした: {exc}")
    return job
