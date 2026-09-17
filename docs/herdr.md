# Herdr の使い方（okuradi）

Herdr は、Claude を何人も並べて動かすための端末アプリ。tmux と同じく、画面を閉じても中の処理は動き続ける。
各ペインの Claude が「作業中 / 承認待ち / 完了」のどれかを、サイドバーに出し続ける。

- 公式ドキュメント: https://herdr.dev/docs/
- 入っている版: 0.8.2（`herdr --version`）
- 設定: `~/.config/herdr/config.toml`（通知は WezTerm 経由で Windows のトーストに出す設定済み）
- Claude との連携: `herdr integration install claude` 済み（会話の復元ができる）
- Claude が Herdr を操作するためのスキル: `~/.claude/skills/herdr/SKILL.md`（`herdr --skill` の出力。Herdr を更新したら入れ直す）

## サブエージェントと Herdr の使い分け

| | サブエージェント（`.claude/agents/`） | Herdr |
|---|---|---|
| 何が動くか | メインの会話の中から呼ぶ担当。結果だけが返る | 別のペインで動く、独立した Claude |
| 向いている作業 | 調査、レビュー、小さめの実装 | Issue 単位の長い実装を並行で進める |
| 人が直接話せるか | 話せない | 話せる（そのペインを開いて入力する） |

まずはサブエージェントで回し、Issue を並行で進めたくなったら Herdr のペインを増やす。

## 画面の構成

```
workspace: okuradi
├─ tab "main"
│  ├─ lead        メインの Claude（あなたと話す・指示と回収をする） @ okuradi
│  └─ （必要なとき）impl-5 など、Issue ごとの実装担当
├─ tab "run"       アプリのサーバー・ログ・長い処理
└─ workspace: okuradi-<ブランチ>   herdr worktree create で作る、並行作業用の作業フォルダ
```

**宛先は名前で指定する。** ペインの ID（`w1:p2` など）は閉じると二度と使われないので、覚えておいても役に立たない。

| 名前 | 役割 |
|---|---|
| `lead` | メインの Claude |
| `impl-<Issue 番号>` | その Issue の実装担当（例: `impl-5`） |

## 起動のしかた

1. WSL の端末（WezTerm）で `cd ~/workspace/okuradi && herdr`
2. 最初のペインで `claude` を起動する
3. メインの Claude に名前を付ける（Claude に頼んでもよい）

   ```bash
   herdr agent rename "$HERDR_PANE_ID" lead
   ```

Herdr の中から `herdr` をもう一度起動することはできない（入れ子を防ぐ仕様）。
Herdr の中で tmux も起動しない（状態の表示が効かなくなる）。

## Issue を並行で進める

メインの Claude（`lead`）に「#5 を別のペインで進めて」と頼むと、次の流れで動く。

```bash
# 1. ブランチつきの作業フォルダを、別の workspace として作る
herdr worktree create --branch feature/episode-list --base main \
  --path ../okuradi-wt/episode-list --label "#5 回の管理" --no-focus
# → 返ってきた JSON の root_pane の ID を使う

# 2. そのペインで Claude を起動して名前を付ける
herdr agent start impl-5 --kind claude --pane <ペインID>

# 3. 指示を送り、区切りがつくまで待つ
herdr agent prompt impl-5 "Issue #5 を実装して、PR を作ったら報告して" --wait --timeout 1800000

# 4. 様子を見る
herdr agent get impl-5
herdr agent read impl-5 --source recent-unwrapped --lines 120
```

- 担当が「承認待ち」になったら、`lead` は勝手に答えず、あなたに確認する
- 並べるのは **2つまで** を目安にする（レビューと確認が追いつかなくなるため）
- 終わった作業フォルダは、PR がマージされてから `herdr worktree remove` で片付ける

### 作業フォルダで気をつけること

- **音声や途中のファイルは入っていない。** `ep*/0*_*/` は git の管理外なので、新しい作業フォルダには `config.yml` しかない。
  試すときは、テスト用の短い音声を作るか、元のフォルダの `ep01` を読むだけにする。
- **Python の仮想環境が無い。** 元のフォルダの `.venv` を使う（`../../okuradi/.venv/bin/python`）か、作業フォルダで作る。
- **`git config core.hooksPath .githooks` は作業フォルダでも効く**（リポジトリ共通の設定なので）。

## よく使うキー

prefix は `Ctrl+b`（tmux と同じ）。マウスでも全部操作できる。

| 操作 | キー |
|---|---|
| ペインの移動 | `Ctrl+b` → `h` / `j` / `k` / `l` |
| タブの切り替え | `Ctrl+b` → `1`〜`9` |
| 新しいタブ | `Ctrl+b` → `c` |
| ペインの分割（右 / 下） | `Ctrl+b` → `v` / `-` |
| ペインを全画面にする | `Ctrl+b` → `z` |
| 通知の出たペインへ移る | `Ctrl+b` → `o` |
| 画面を離れる（処理は続く） | `Ctrl+b` → `q` |
| キーの一覧 | `Ctrl+b` → `?` |

戻るときは、もう一度 `herdr` を起動する。全部止めるときだけ `herdr server stop`（中の Claude も止まる）。

## 困ったとき

- 状態がおかしい: `herdr agent list`、`herdr agent explain <名前> --json`
- Herdr 全体の様子: `herdr status`
- ログ: `~/.config/herdr/`
