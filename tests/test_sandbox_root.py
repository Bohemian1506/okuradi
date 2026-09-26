"""`OKURADI_EPISODES_DIR` / `OKURADI_SETTINGS` のテスト（#221）。

サブスク担当が本物の `ep*/`・`settings.yml` に触らず、一時フォルダに向けて
試せるようにする。「回を置く場所」と「settings.yml の置き場所」を、環境変数で
切り替えられること・無ければ今までどおりなこと・存在しない場所なら止まること・
runner が子プロセスに環境変数を渡すこと・本物のパスに書かれないことを確かめる。
"""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

import build

BUILD_PY = Path(build.__file__).resolve()
REAL_CODE_ROOT = BUILD_PY.parent


# ---------------------------------------------------------------- build.episodes_root()

def test_環境変数が無ければコードの場所(monkeypatch):
    monkeypatch.delenv("OKURADI_EPISODES_DIR", raising=False)
    assert build.episodes_root() == REAL_CODE_ROOT


def test_環境変数があればそこに変わる(tmp_path, monkeypatch):
    monkeypatch.setenv("OKURADI_EPISODES_DIR", str(tmp_path))
    assert build.episodes_root() == tmp_path.resolve()


def test_存在しない場所は理由を出して止まる(tmp_path, monkeypatch):
    missing = tmp_path / "ない"
    monkeypatch.setenv("OKURADI_EPISODES_DIR", str(missing))
    with pytest.raises(RuntimeError, match="フォルダではありません"):
        build.episodes_root()


def test_フォルダでない場所も止まる(tmp_path, monkeypatch):
    not_a_dir = tmp_path / "file.txt"
    not_a_dir.write_text("x", encoding="utf-8")
    monkeypatch.setenv("OKURADI_EPISODES_DIR", str(not_a_dir))
    with pytest.raises(RuntimeError, match="フォルダではありません"):
        build.episodes_root()


# ---------------------------------------------------------------- build.py（CLI）

def run_build(args, env_extra):
    import os
    env = dict(os.environ)
    env.pop("OKURADI_EPISODES_DIR", None)
    env.pop("OKURADI_SETTINGS", None)
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(BUILD_PY), *args],
        capture_output=True, text=True, timeout=30, env=env, cwd=str(REAL_CODE_ROOT),
    )


def test_CLIは指定した一時フォルダを見て本物には触らない(tmp_path):
    """一時フォルダに回が無いときの断り方に、一時フォルダのパスが出る
    （本物の ep01 の場所ではないことの確認）。本物には一切書き込まない。
    """
    before_settings = list(REAL_CODE_ROOT.glob("settings.yml"))
    before_ep = sorted(p.name for p in REAL_CODE_ROOT.glob("ep*"))

    out = run_build(["epXX", "--to", "scan"], {"OKURADI_EPISODES_DIR": str(tmp_path)})

    assert out.returncode != 0
    assert str(tmp_path) in out.stdout, out.stdout
    assert "[okuradi] 回の置き場所" in out.stdout
    assert str(REAL_CODE_ROOT) not in out.stdout.replace(str(tmp_path), "")

    assert list(REAL_CODE_ROOT.glob("settings.yml")) == before_settings
    assert sorted(p.name for p in REAL_CODE_ROOT.glob("ep*")) == before_ep


def test_CLIは環境変数が無ければ今までどおり本物の場所を見る():
    """本物の ep01 は既にあるはずなので「がありません」にはならない
    （読むだけで確かめる。書き込む工程は動かさない）。"""
    out = run_build(["epXX-には無い回", "--to", "scan"], {})
    assert out.returncode != 0
    assert str(REAL_CODE_ROOT) in out.stdout


def test_CLIは存在しない場所を渡すと理由を出して止まる(tmp_path):
    missing = tmp_path / "ない"
    out = run_build(["ep01", "--to", "scan"], {"OKURADI_EPISODES_DIR": str(missing)})
    assert out.returncode != 0
    assert "フォルダではありません" in (out.stdout + out.stderr)


# ---------------------------------------------------------------- web.episodes / web.sources

@pytest.fixture
def reload_web(monkeypatch):
    """OKURADI_EPISODES_DIR / OKURADI_SETTINGS を付けて web.episodes・web.sources を
    作り直し、テストが終わったら必ず元（環境変数なし）に戻す。

    ROOT・SETTINGS は import 時に1度だけ計算されるので、切り替えを試すには
    reload が要る。戻し忘れると、あとの他のテストが一時フォルダを見てしまう。
    """
    import web.episodes as episodes_mod
    import web.sources as sources_mod

    def reload():
        importlib.reload(episodes_mod)
        importlib.reload(sources_mod)
        return episodes_mod, sources_mod

    try:
        yield reload
    finally:
        monkeypatch.delenv("OKURADI_EPISODES_DIR", raising=False)
        monkeypatch.delenv("OKURADI_SETTINGS", raising=False)
        episodes_mod, sources_mod = reload()
        assert episodes_mod.ROOT == REAL_CODE_ROOT
        assert sources_mod.SETTINGS == REAL_CODE_ROOT / "settings.yml"


def test_web_episodesは環境変数で回の場所が変わる(tmp_path, monkeypatch, reload_web):
    monkeypatch.setenv("OKURADI_EPISODES_DIR", str(tmp_path))
    episodes_mod, _ = reload_web()
    assert episodes_mod.ROOT == tmp_path.resolve()
    # コードの場所（gh・claude -p の cwd）は変わらない
    assert episodes_mod.CODE_ROOT == REAL_CODE_ROOT


def test_web_sourcesは環境変数でsettingsの場所が変わる(tmp_path, monkeypatch, reload_web):
    (tmp_path / "here").mkdir()
    settings_path = tmp_path / "here" / "settings.yml"
    monkeypatch.setenv("OKURADI_SETTINGS", str(settings_path))
    _, sources_mod = reload_web()
    assert sources_mod.SETTINGS == settings_path.resolve()


def test_settingsの置き場所のフォルダが無ければ読み込みが止まる(tmp_path, monkeypatch, reload_web):
    """回の置き場所と同じく、理由を出して止める。黙って進むと保存した瞬間に落ちる。"""
    monkeypatch.setenv("OKURADI_SETTINGS", str(tmp_path / "ない" / "settings.yml"))
    with pytest.raises(RuntimeError, match="OKURADI_SETTINGS の置き場所のフォルダがありません"):
        reload_web()


def test_回の場所だけ付けるとsettingsもその中になる(tmp_path, monkeypatch, reload_web):
    """回の場所だけ一時フォルダに向けて、設定だけ本物に書く、を起こさない（2026-09-26・ユーザーの判断）。"""
    monkeypatch.setenv("OKURADI_EPISODES_DIR", str(tmp_path))
    _, sources_mod = reload_web()
    assert sources_mod.SETTINGS == tmp_path.resolve() / "settings.yml"


def test_app_pyも回の場所の切り替えに乗る():
    """古い GUI も build.episodes_root() を使う（#228 のレビュー）。直書きの Path(__file__) に戻さない。"""
    text = (REAL_CODE_ROOT / "app.py").read_text(encoding="utf-8")
    assert "ROOT = build.episodes_root()" in text


def test_web_episodesは環境変数が無ければ今までどおり(reload_web):
    episodes_mod, sources_mod = reload_web()
    assert episodes_mod.ROOT == REAL_CODE_ROOT
    assert sources_mod.SETTINGS == REAL_CODE_ROOT / "settings.yml"


def test_web_episodesは存在しない場所だと読み込みが止まる(tmp_path, monkeypatch, reload_web):
    monkeypatch.setenv("OKURADI_EPISODES_DIR", str(tmp_path / "ない"))
    with pytest.raises(RuntimeError, match="フォルダではありません"):
        reload_web()


def test_環境変数を向けた状態でも本物のsettingsとep一覧には書かれない(
        tmp_path, monkeypatch, reload_web):
    """一時フォルダに向けたまま `save_settings` を呼んでも、本物の
    settings.yml は増えない・変わらないことを確かめる（本物に一切書かない）。"""
    real_settings = REAL_CODE_ROOT / "settings.yml"
    existed_before = real_settings.exists()
    before_text = real_settings.read_text(encoding="utf-8") if existed_before else None

    tmp_ep = tmp_path / "ep01"
    tmp_ep.mkdir()
    settings_path = tmp_path / "settings.yml"
    monkeypatch.setenv("OKURADI_EPISODES_DIR", str(tmp_path))
    monkeypatch.setenv("OKURADI_SETTINGS", str(settings_path))
    episodes_mod, sources_mod = reload_web()

    sources_mod.save_settings({"obs_dir": "/どこか一時的な場所"})

    assert settings_path.exists()
    assert sources_mod.read_settings()["obs_dir"] == "/どこか一時的な場所"

    assert real_settings.exists() == existed_before
    if existed_before:
        assert real_settings.read_text(encoding="utf-8") == before_text


# ---------------------------------------------------------------- runner が子プロセスに渡す

def test_runnerは環境変数をそのまま子プロセスに渡す(monkeypatch):
    """`_run` が組み立てる Popen の env に、環境変数がそのまま入っていることを確かめる。

    実際に子プロセスは立てず、Popen をすり替えて渡された kwargs だけ見る
    （build.py を動かすのはこのテストの範囲ではない）。
    """
    import web.runner as runner

    monkeypatch.setenv("OKURADI_EPISODES_DIR", "/tmp/どこかの一時フォルダ")
    seen = {}

    class FakeProc:
        pid = 12345
        stdout = []

        def wait(self):
            return 0

    def fake_popen(cmd, **kwargs):
        seen.update(kwargs)
        return FakeProc()

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)

    job = runner.Job("epXX", "scan")
    runner._run(job)

    assert seen.get("env", {}).get("OKURADI_EPISODES_DIR") == "/tmp/どこかの一時フォルダ"
