# 申し送り

作業を区切るときに、次の人（次のセッションの Claude）へ残すメモ。**最新の1回分だけを書き、区切るたびに上書きする。** 経緯は `docs/dev-log/` を見る。

## 2026-09-19（day-3 の終わり）

### いまの状態
- main は `f51efd5`。**開いている PR は無し。ローカルのブランチは `main` だけ**（マージ済みのブランチは消してある）
- day-3 で GUI を最初から最後まで実装した（#5 枠 → #6 収録〜整音 → #7 仕上げ → #8 ログ・チャット・改善メモ）。マージした PR は #18〜#62
- **必須の17機能はすべて実装済み**（`docs/features.md` の「実装の状況」）。`pytest` 166件が通る
- 波形は wavesurfer.js（#36）。ファイルは `web/static/vendor/` に置いてあり、CDN からは読まない
- 回のデータは `ep01` だけ。音声と途中のファイルは git の管理外

### 開いている Issue
| Issue | 内容 | いま |
|---|---|---|
| #42 | 整音結果パネルを見本にそろえる | 状態の見た目は #55、波形は #58 で済んだ。残りは下記 |
| #53 | 新しい GUI だけで1回分を通し、`app.py` を消す | **ユーザーが実物の音声でやる**（Claude にはできない） |
| #59 | 波形まわりの見た目と読み上げを見本にそろえる | #58 のレビューから。操作は妨げない |
| #60 | 未保存の区間があるとき、閉じる前に知らせる | #58 のレビューから |
| #61 | 整音結果の取り直しの失敗を黙らせない | #58 のレビューから |

### 次にやること
1. **#42 の残り**
   - エコーをかけた区間の帯を、整音結果の波形にも出す
     - **注意**: エコー区間の時刻は `trimmed.wav` が基準。`clean.wav` はエコーで長さが変わるので、そのまま重ねるとずれる。`01_clean/clean.json` の記録を使って置き直す
   - 動画プレビューの再生コントロールを自前にし、ポスター画像を出す
2. **#53 通しリハーサル**（ユーザー）— 実際の収録で最初から最後まで通して、詰まった所を Issue にする。通せたら `app.py`・`requirements.txt` の streamlit / altair / pandas / **numpy**・`CLAUDE.md` の「古い GUI」の行を消す
3. #59 / #60 / #61 — どれも急がない。#53 の前でも後でもよい

### 作業の始め方
- GUI: `.venv/bin/python -m uvicorn web.main:app --reload`（`http://127.0.0.1:8000`）
- コマンド: `.venv/bin/python build.py ep01 --from clean --to clean`（GUI が無くても番組を作れる状態は保つ）
- 追加インストールは `uv pip install --python .venv/bin/python <名前>`（この `.venv` は uv が作ったもので、pip が入っていない）
- WezTerm の F12 から開く（使い方は `docs/herdr.md`）
  - 「herdr: okuradi」: okuradi だけ
  - 「herdr: フリーライフ資料」: okuradi の `lead` も起動してから、フリーライフを開く
  - 「herdr: okuradi + フリーライフ」: 両方を起動して、okuradi を開く
- 前の会話の続きから始めるときは、端末で `~/workspace/okuradi/start.sh -c`
- 作業のルールは `CLAUDE.md`（Issue から始める / 勝手に決めない / レビュー担当は必要なときに呼ぶ / マージしたらすぐ議事録の PR）

### まだ確かめていないこと
- **1回分を通しで作れるか（#53）。** 工程ごとには `ep01` で動かして確かめたが、収録から公開用のコピーまで一続きに通してはいない
- PC を再起動した後、「herdr: okuradi + フリーライフ」で、止まった状態から両方が起動するか
- Herdr で Issue を並行で進める流れ（`herdr worktree create` → 実装担当の起動 → 片付け）

### リポジトリの外にある設定（消えたら作り直す）

| 設定 | 場所 | 作り直し方 |
|---|---|---|
| F12 のメニュー（3つ） | `C:\Users\hiros\.wezterm.lua` の `launch_menu` | 書き方は `docs/dev-log/day-2.md` の #13 と `docs/herdr.md` |
| Herdr の Claude 連携 | `~/.claude/hooks/herdr-agent-state.sh` など | `herdr integration install claude` |
| Claude が Herdr を操作するスキル | `~/.claude/skills/herdr/SKILL.md` | `herdr --skill > ~/.claude/skills/herdr/SKILL.md`（Herdr を更新したときも） |
| Claude Design とつなぐ MCP | `~/.claude.json`（`-s user` で入れた。公開リポジトリなので `.mcp.json` は作らない） | `claude mcp add -s user --transport http claude_design https://api.anthropic.com/v1/design/mcp` → `/design-login` → **Claude を立ち上げ直す**（`claude --continue` で会話の続きから戻る）。詳しくは `docs/dev-log/day-3.md` |
| main への push を止める git のフック | リポジトリの git 設定 | `git config core.hooksPath .githooks`（clone し直したとき） |
| GitHub 側の main の保護 | リポジトリの設定（Branches） | 直接 push の禁止・管理者にも適用・承認は不要・強制 push と削除の禁止 |

### 気をつけること
- リポジトリは公開。認証情報（`client_secret.json` / `token.json`）と音声は git の管理外だが、コミットする前に確かめる
- **`Closes #N` をバッククォートで囲むと GitHub が読まない。** 囲まずに書くか、マージした後に手で閉じる（day-3 で2回やった）
- **`ep*/00_logs/` には相談チャットの記録（`chat.json`）が入っている。** ログの掃除のつもりでフォルダごと消すと会話が消える
- **`ep*/00_logs/<工程>.log` は、その工程を動かすたびに上書きされる。** 失敗の様子を残したいときは、動かし直す前に控える
- レビューの指摘は、コードか実際の動きで確かめてから採用する（day-3 で、前提そのものが無い指摘が2件あった）
- **新しくできるようにした操作には、既存の操作が持っている守りを付け忘れやすい**（#58 で、端を掴んで縮めるときだけ最小長の確認が抜けていた）
- **対称なはずのものは、両方向を試す**（#58 で「音は1つだけ鳴る」を片方向しか確かめていなかった）
- **文書に数字を書くときも「動かしていないものは未確認と書く」**（#58 で「10分で数秒かかる」と断定し、測ったら 1.7秒だった）
- 画面の確かめには、ヘッドレスの Chrome を CDP（`node --experimental-websocket`）で動かせる。実際にマウスを動かしてドラッグまで試せる
- Herdr の担当の名前は、Herdr 全体で重ならないようにする（フリーライフは `director` など、okuradi は `lead` と `impl-<番号>`）
- `herdr worktree remove` は、`--workspace` を省くと今いる場所が対象になる。必ず ID を指定する
