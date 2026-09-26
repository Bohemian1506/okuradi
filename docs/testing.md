# 試すときは一時フォルダに向ける（#221）

`ep*/` と `settings.yml` は本物（ユーザーの回・ユーザーの設定）。
**どの道具でも、本物の `ep*/` と `settings.yml` には書かない。** サーバー・`build.py`・古い GUI（`app.py`）・
ffmpeg や Whisper を直接試すときも、**一時フォルダに向ける**（出力先も一時フォルダにする）。

**Claude が打つコマンドは、hook が止める**（`.claude/hooks/block-real-workspace.py`）:
- 環境変数 `OKURADI_EPISODES_DIR` を付けずに `build.py`・`uvicorn web.main`・`streamlit run app.py` を起動する
- 本物のサーバー（8000番）に書き込む（curl の `-X PUT/POST/DELETE/PATCH`・`-d`・`-F`・`-T` など）

ユーザーが自分の端末で打つコマンドには効かない（番組づくりは今までどおり）。
本物で動かす必要があるときは、ユーザーに `! <コマンド>` で打ってもらう。

## 使い方

```
TMP=$(mktemp -d)
cp -r ep01 "$TMP/"                 # 音声も使うならコピーする（本物の ep01 では何も実行しない）
cp -r assets "$TMP/"               # 動画化まで試すなら、画像も要る（config.yml の images が指す）

# build.py（コマンド）。**--to を必ず付ける**（付けないと最後の upload まで進む）
OKURADI_EPISODES_DIR="$TMP" .venv/bin/python build.py ep01 --from clean --to video

# GUI（サーバー）。**8000 番は使わない**（ユーザーの本物のサーバーの番号）
OKURADI_EPISODES_DIR="$TMP" .venv/bin/python -m uvicorn web.main:app --port <8000 以外の空いている番号>
```

- `OKURADI_EPISODES_DIR`: 「回を置く場所」（`ep01/` などが並ぶ場所）。無ければ今までどおり、
  `build.py` と同じ場所（リポジトリ直下）を見る。`build.py`・新しい GUI・古い GUI（`app.py`）のどれも従う
- **`settings.yml` は、`OKURADI_EPISODES_DIR` を付ければ、その中の `settings.yml` になる**
  （回の場所だけ一時フォルダに向けて、設定だけ本物に書く、を起こさないため。2026-09-26・ユーザーの判断）。
  別の場所にしたいときだけ `OKURADI_SETTINGS` を付ける
- 指定した場所が無い・フォルダでないときは、理由を出して止まる（黙ってリポジトリ直下には戻らない）
- **`gh`・`claude -p` の cwd（コードの場所）はこの環境変数では変わらない。** `gh` はリポジトリの
  中で打つ必要があるため

## 一時フォルダに向けても、本物に届くもの

- **改善メモの登録**（GUI の「Issue に登録」）: `gh issue create` で**本物の GitHub に Issue が立つ**。試さない
- **upload**（YouTube に限定公開）: 一時フォルダには `client_secret.json` が無いので止まるが、`--to` を付けて届かせない
- **`claude -p`**（メタデータ・相談チャット）: サブスクの枠を使う。必要なときだけ

## いま見ている場所の確認

`build.py`・GUI（サーバー）とも、起動時に `[okuradi] 回の置き場所: <パス>` を1行出す。
本物（リポジトリ直下）を見ているつもりが、環境変数のせいで一時フォルダを見ていた・
その逆、を取り違えないための表示。GUI はサーバーを起動した端末に出る（画面には出さない）。

## 確かめ方

一時フォルダに向けたあとは、**最初と最後に**次を見て、リポジトリ直下が変わっていないことを確かめる。

```
ls -la settings.yml
ls -d ep*
ls -la ep*/00_logs ep*/01_mix
```

`git status` は管理外のファイル（`settings.yml`・`ep*/` の音声・中間ファイル）を見せないので、
これだけでは確かめたことにならない。

## 片付け

```
rm -rf "$TMP"
```

サーバーを起動したままにしない（`kill` してから終わる）。
