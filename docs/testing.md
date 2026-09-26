# 試すときは一時フォルダに向ける（#221）

`ep*/` と `settings.yml` は本物（ユーザーの回・ユーザーの設定）。
サーバーや `build.py` を試しに動かすときは、**一時フォルダに向ける**。

## 使い方

```
TMP=$(mktemp -d)
cp -r ep01 "$TMP/"                 # 音声も使うならコピーする（本物の ep01 では何も実行しない）
cp -r assets "$TMP/"               # 動画化まで試すなら、画像も要る（config.yml の images が指す）

# build.py（コマンド）
OKURADI_EPISODES_DIR="$TMP" OKURADI_SETTINGS="$TMP/settings.yml" \
  .venv/bin/python build.py ep01 --from clean --to video

# GUI（サーバー）
OKURADI_EPISODES_DIR="$TMP" OKURADI_SETTINGS="$TMP/settings.yml" \
  .venv/bin/python -m uvicorn web.main:app --port <空いている番号>
```

- `OKURADI_EPISODES_DIR`: 「回を置く場所」（`ep01/` などが並ぶ場所）。無ければ今までどおり、
  `build.py` と同じ場所（リポジトリ直下）を見る
- `OKURADI_SETTINGS`: 「`settings.yml` の場所」。無ければ今までどおり、リポジトリ直下の
  `settings.yml` を見る
- 2つは別々に切り替えられる（片方だけ付けてもよい）
- 指定した場所が無い・フォルダでないときは、理由を出して止まる（黙ってリポジトリ直下には戻らない）
- **`gh`・`claude -p` の cwd（コードの場所）はこの環境変数では変わらない。** `gh` はリポジトリの
  中で打つ必要があるため（Issue の登録・改善メモ）

## いま見ている場所の確認

`build.py`・GUI（サーバー）とも、起動時に `[okuradi] 回の置き場所: <パス>` を1行出す。
本物（リポジトリ直下）を見ているつもりが、環境変数のせいで一時フォルダを見ていた・
その逆、を取り違えないための表示。GUI はサーバーを起動した端末に出る（画面には出さない）。

## 確かめ方

一時フォルダに向けたあとは、**最初と最後に**次を見て、リポジトリ直下が変わっていないことを確かめる。

```
ls -la settings.yml
ls -d ep*
ls -la ep01/00_logs ep01/01_mix
```

`git status` は管理外のファイル（`settings.yml`・`ep*/` の音声・中間ファイル）を見せないので、
これだけでは確かめたことにならない。

## 片付け

```
rm -rf "$TMP"
```

サーバーを起動したままにしない（`kill` してから終わる）。
