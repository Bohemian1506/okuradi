# okuradi（置くラジ）

10分ラジオの制作パイプライン。

収録ファイル（wav / m4a / OBSの録画）を1本置いて、コマンドを2回叩くと限定公開までいく。

## 工程

```
scan  -> cut -> clean -> transcribe -> meta -> video -> upload
下見     カット  整音     文字起こし   メタ    動画化   限定公開
```

GUIを使う場合（作っている途中。いまは回の管理だけ）:

```
uvicorn web.main:app --reload     # http://127.0.0.1:8000
```

今までの GUI（Streamlit）も、新しい GUI で1回分を通せるまで残してある:

```
streamlit run app.py
```

## ディレクトリ

```
okuradi/
├── build.py              # パイプライン本体（全回共通。基本いじらない）
├── app.py                # 今までのGUI（Streamlit）
├── web/                  # 新しいGUI（FastAPI + 素のHTML/CSS/JS）
│   ├── main.py           # APIと画面の配信
│   ├── episodes.py       # 回の一覧・作成と、工程の状態
│   ├── runner.py         # 工程の実行・中止・ログの配信
│   ├── sources.py        # 音源の追加と、アプリ全体の設定
│   ├── media.py          # 文字起こしを読む・音声を画面に配る
│   └── static/           # index.html / style.css / app.js
├── settings.yml          # OBSの録画フォルダなど（git管理外。GUIの画面から作れる）
├── tests/
├── docs/design/          # 画面のデザインの見本（Claude Design から取り込み）
├── requirements.txt
├── client_secret.json    # YouTube API の認証情報（自分で配置）
├── token.json            # 初回認証後に自動生成
├── assets/
│   └── normal.png        # 背景画像。将来ここに表情差分が並ぶ
└── ep01/
    ├── config.yml        # この回の設定。毎回ここだけ書き換える
    ├── 00_raw/           # 収録ファイルを置く（wav / m4a / OBSの録画）
    ├── 01_cut/           # カット後
    ├── 01_clean/         # 整音後
    ├── 02_text/          # 文字起こし
    ├── 03_meta/          # タイトル・概要欄・チャプター
    └── 04_video/         # 完成mp4
```

## セットアップ（初回のみ）

### 1. FFmpeg

すでに入っているはず。確認だけ。

```
ffmpeg -version
```

入っていなければ `winget install Gyan.FFmpeg`

### 2. Pythonパッケージ

```
pip install -r requirements.txt
```

NVIDIA の GPU で文字起こしを速くする場合は、CUDA のライブラリも入れる（約2GB）。
build.py が自動で読み込むので、LD_LIBRARY_PATH の設定は要らない。
入れなくても CPU で動く（遅くなるだけ）。

```
pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
```

### 3. Claude Code

Claude の呼び出しは `claude -p`（Claude Code の headless モード）経由。
APIキーは使わず、サブスクの枠で動く。Claude Code にログインしてあればよい。

```
claude auth status   # authMethod が claude.ai になっていること
```

環境変数 `ANTHROPIC_API_KEY` は呼び出し時に外すので、設定されていても従量課金にはならない。

### 4. YouTube API

1. Google Cloud Console でプロジェクトを作る
2. 「YouTube Data API v3」を有効化
3. OAuth同意画面を作る（外部・テストユーザーに自分を追加）
4. 認証情報 → OAuthクライアントID → **デスクトップアプリ** を選択
5. JSONをダウンロードして `client_secret.json` としてこのフォルダに置く

初回の `upload` でブラウザが開くので許可する。以降は `token.json` が
自動更新されるので、認証作業はもう出てこない。

## 使い方

```
# 1. ep01/00_raw/ に収録ファイルを置く
# 2. ep01/config.yml の theme を書き換える

python build.py ep01 --to scan           # 下見の文字起こし
#   → 02_text/scan.json を見てカット点を探す

# config.yml の cuts に区間を書く（GUIなら波形上で指定）

python build.py ep01 --from cut --to clean   # カットして整音
#   → 01_clean/clean.wav を聴く（ゲート1）

python build.py ep01 --from transcribe   # 残り全部
#   → 限定公開のURLが出る（ゲート2）

# 3. YouTubeで観て、良ければ公開ボタン
```

やり直しは工程単位で効く。

```
python build.py ep01 --from meta --to meta     # タイトルだけ作り直す
python build.py ep01 --from video --to video   # 画像を変えて動画だけ再生成
```

## OBS で録る場合

録画ファイル（mkv / mp4 / mov / flv）を `00_raw/` にそのまま置けばよい。
最初に使うときに音声だけが `録画名.track0.wav`（48kHz・モノラル・16bit）として
取り出され、以降の工程はそれを使う。録り直して録画が新しくなれば取り出し直す。

マイクとデスクトップ音声を別トラックで録っている場合は、config.yml の
`audio.source_track` で使うトラックを選ぶ（0 始まり。既定は 0）。

## 2回目以降

`ep01` をコピーして `ep02` にして、中身を空にする。config.yml の
`episode` と `segments` を書き換えるだけ。

## 設計メモ

- **中間ファイルを全工程で残す。** 1箇所こけても最初からにならない。
- **無音の自動カットはしない。** 一発録りの「間」を機械的に詰めると
  喋りが死ぬ。前後のトリムだけ。
- **画像はconcat方式。** 1枚でも配列で扱うので、表情差分を足すときに
  コードを書き換えなくていい。
- **segmentsは配列。** 将来のおはスタ型（複数コーナー）に移るとき、
  要素を増やすだけで済む。
- **アップは常に限定公開。** これ自体がレビューゲート。

## 将来の拡張ポイント

- 表情差分: `assets/` に画像を足して config の `images` に並べる
- BGM: `bgm` にパスを入れる（ミックス処理の追加が要る）
- コーナー制: `segments` に要素を足す
- 表情の自動割り当て: `meta` 工程で章ごとに感情タグを吐かせて
  `video` 工程で画像に対応させる
