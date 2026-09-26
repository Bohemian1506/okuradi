# 試すときは一時フォルダに向ける（#221）

`ep*/` と `settings.yml` は本物（ユーザーの回・ユーザーの設定）。
**どの道具でも、本物の `ep*/` と `settings.yml` には書かない。** サーバー・`build.py`・古い GUI（`app.py`）・
ffmpeg や Whisper を直接試すときも、**一時フォルダに向ける**（出力先も一時フォルダにする）。

**守りは2段**（#221・案A'・2026-09-26・ユーザーの判断）:

1. **起動の守りは `build.py` の中**（`build.episodes_root()`）。Claude Code が打つコマンドには環境変数 `CLAUDECODE` が付く
   （`bash -c`・`nohup`・子のプロセスにも引き継がれる）。それがあって `OKURADI_EPISODES_DIR` が無ければ、
   `build.py`・GUI のサーバー・`app.py` は**本物を使わずに止まる**。書き方ではすり抜けられない
2. **hook**（`.claude/hooks/block-real-workspace.py`）が、Claude の打つコマンドの中の次の3つを止める
   - `OKURADI_REAL`（本物を使う合言葉。下）という語
   - 1 が見る印を外すこと（`env -u`・`unset`・`env -i`）
   - 本物のサーバー（8000番）への書き込み（curl・wget・Python から。`:08000`・`127.1`・番号を変数に入れる、も）。
     **ヘッドレスの Chrome で 8000 番のボタンを押す、などは止められない。8000番は開かない**

**止めるのは、うっかりと軽い回避まで。わざと隠す形（語を分けて組み立てる、など）は越えられる。**
文字列を読む守りの限界として、2026-09-26 にユーザーが受け入れた（#228・案A）。day-9 の2件は、決まりを忘れた・
軽く見た形で、わざと隠したものではなかった。

**ユーザーの端末には `CLAUDECODE` が付かないので、番組づくりは今までどおり。**
ユーザーが Claude の画面から `!` で本物を動かすときは、`!` にも `CLAUDECODE` が付くので、**合言葉を付ける**:

```
! OKURADI_REAL=1 .venv/bin/python build.py ep00 --from clean --to clean
```

`!` には hook が効かない（2026-09-26 に確かめた）ので、合言葉を使えるのはユーザーだけ。
GUI を立てる `.claude/scripts/作業ペイン.sh gui` は別のペイン（`CLAUDECODE` が付かない）でサーバーを立てるので、今までどおり使える。
**`作業ペイン.sh gui` は lead がユーザーの求めで打つもの。担当は打たない。**

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
