# 申し送り

作業を区切るときに、次の人（次のセッションの Claude）へ残すメモ。**最新の1回分だけを書き、区切るたびに上書きする。** 経緯は `docs/dev-log/` を見る。

## 2026-09-17（day-2 の終わり）

### いまの状態
- main は `d3fce27`。作業中のブランチや、マージしていない PR は無い
- この日にマージした PR: #9（部品の洗い出し）、#10（担当・Herdr・議事録の体制）、#11（議事録）、#13（起動コマンド）、#14（議事録）
- 開いている Issue: #3 技術構成 → #4 デザイン → #5〜#8 実装（#5〜#8 は #4 待ち、#4 は #3 待ち）
- Herdr の中で、okuradi の `lead` と、フリーライフの `director` / `chief-editor` / `deputy` が動いたまま（どれも入力待ち）

### 次にやること
1. **#3 GUI の技術構成を決める**
   - Issue #3 に候補（FastAPI + 自前の画面 がおすすめ / Streamlit のまま / Rails）と、決めることの一覧がある
   - `app.py`（Streamlit）を作り直すかどうかも、ここで決める（まだ決まっていない）
   - 部品と画面は `docs/components.md`、機能は `docs/features.md`
2. #3 が決まったら、#4 で Claude Design を使ってデザインする

### 作業の始め方
- WezTerm の F12 から開く（使い方は `docs/herdr.md`）
  - 「herdr: okuradi」: okuradi だけ
  - 「herdr: フリーライフ資料」: okuradi の `lead` も起動してから、フリーライフを開く
  - 「herdr: okuradi + フリーライフ」: 両方を起動して、okuradi を開く
- 前の会話の続きから始めるときは、端末で `~/workspace/okuradi/start.sh -c`
- 作業のルールは `CLAUDE.md`（Issue から始める / 勝手に決めない / レビュー担当は必要なときに呼ぶ / マージしたらすぐ議事録の PR）

### まだ確かめていないこと
- PC を再起動した後、「herdr: okuradi + フリーライフ」で、止まった状態から両方が起動するか
- Herdr で Issue を並行で進める流れ（`herdr worktree create` → 実装担当の起動 → 片付け）。利用者担当のレビューで「練習用の Issue で一度通すとよい」と提案があった

### リポジトリの外にある設定（消えたら作り直す）
| 設定 | 場所 | 作り直し方 |
|---|---|---|
| F12 のメニュー（3つ） | `C:\Users\hiros\.wezterm.lua` の `launch_menu` | 書き方は `docs/dev-log/day-2.md` の #13 と `docs/herdr.md` |
| Herdr の Claude 連携 | `~/.claude/hooks/herdr-agent-state.sh` など | `herdr integration install claude` |
| Claude が Herdr を操作するスキル | `~/.claude/skills/herdr/SKILL.md` | `herdr --skill > ~/.claude/skills/herdr/SKILL.md`（Herdr を更新したときも） |
| main への push を止める git のフック | リポジトリの git 設定 | `git config core.hooksPath .githooks`（clone し直したとき） |
| GitHub 側の main の保護 | リポジトリの設定（Branches） | 直接 push の禁止・管理者にも適用・承認は不要・強制 push と削除の禁止 |

### 気をつけること
- リポジトリは公開になった。認証情報（`client_secret.json` / `token.json`）と音声は git の管理外なので出ないが、コミットする前に確かめる
- Herdr の担当の名前は、Herdr 全体で重ならないようにする（フリーライフは `director` など、okuradi は `lead` と `impl-<番号>`）
- `herdr worktree remove` は、`--workspace` を省くと今いる場所が対象になる。必ず ID を指定する
