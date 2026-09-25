# Herdr の使い方（okuradi）

Herdr は、Claude を何人も並べて動かすための端末アプリ。画面を閉じても、中の処理は動き続ける。
各 Claude が「作業中 / 承認待ち / 完了」のどれかを、画面の左（サイドバー）に出し続ける。

- 公式ドキュメント: https://herdr.dev/docs/
- 手元の状態（2026-09-17 に確認）
  - 版: 0.8.2（`herdr --version`）
  - 設定: `~/.config/herdr/config.toml`（通知は WezTerm 経由で Windows のトーストに出す）
  - Claude との連携: `herdr integration install claude` 済み（Claude の会話を復元できる）
  - Claude が Herdr を操作するためのスキル: `~/.claude/skills/herdr/SKILL.md`（`herdr --skill` の出力。Herdr を更新したら入れ直す）

## 言葉

| 言葉 | 意味 |
|---|---|
| ワークスペース（workspace） | 作業場所1つ分の画面のまとまり。okuradi 本体で1つ、並行作業のフォルダごとに1つ |
| タブ（tab） | ワークスペースの中の画面の切り替え |
| ペイン（pane） | 画面の区切り1つ。中で端末や Claude が動く |
| 作業フォルダ（worktree） | 同じリポジトリを、別のブランチで別の場所に取り出したもの。並行作業で使う |
| prefix | Herdr への合図のキー。`Ctrl+b` を押して離してから、次のキーを押す |

## サブエージェントと Herdr の使い分け

| | サブエージェント（`.claude/agents/`） | Herdr |
|---|---|---|
| 何が動くか | メインの Claude が会話の中から呼ぶ担当。結果だけが返る | 別のペインで動く、独立した Claude |
| 向いている作業 | 調査、レビュー、小さめの実装 | Issue 単位の長い実装を並行で進める |
| 人が直接話せるか | 話せない | 話せる（そのペインを開いて入力する） |

まずはメインの Claude（`lead`）1人で使って慣れる。Issue を並行で進めたくなったら、ペインを増やす。

## 起動する

**WezTerm で F12** を押し、開くものを選ぶ（どれも `start.sh` が動く）。

| メニュー | 起動するもの | 開く画面 |
|---|---|---|
| herdr: okuradi | okuradi（`lead`） | okuradi |
| herdr: フリーライフ資料 | okuradi（`lead`）。フリーライフは今までどおり手で起動する | フリーライフ |
| herdr: okuradi + フリーライフ | okuradi（`lead`）と、フリーライフ（編集局長・編集長・副局長） | okuradi |

しばらくは2つを並行して進めるので、フリーライフのメニューからでも okuradi の `lead` まで起動する。

WSL の端末から打つときは、次のどれか。

```bash
~/workspace/okuradi/start.sh                   # okuradi を起動して開く
~/workspace/okuradi/start.sh -c                # 前回の会話の続きから Claude を起動する
~/workspace/okuradi/start.sh --with-freelife   # フリーライフも起動する
~/workspace/okuradi/start.sh --open-freelife   # 最後にフリーライフの画面を開く（フリーライフは起動しない）
~/workspace/okuradi/start.sh -h                # 使い方を出す
```

`start.sh` がまとめてやること:
1. Herdr のサーバーが止まっていれば起動する
2. okuradi のワークスペース（タブ `main` と `run`）を用意する。すでにあれば使い回す
3. `main` タブで、メインの Claude を `lead` という名前で起動する。すでに動いていれば起動しない
4. 画面を `lead` に切り替えて、Herdr を開く

- Herdr の中から実行したときは、4 は画面の切り替えだけになる（Herdr の中から Herdr は開けないため）
- `--no-attach` を付けると、画面は切り替えず、用意だけする
- `lead` が確認の画面（フォルダを信頼するか など）で止まったら、Herdr の画面で答える
- 何度打っても、ワークスペースや `lead` が二重にできることはない
- 失敗したときは、理由と次にすることが出る（WezTerm のメニューから開いたときは、Enter を押すまで画面が残る）

手で起動する場合は、`cd ~/workspace/okuradi && herdr` のあと、最初のペインで
`herdr agent start lead --kind claude --pane "$HERDR_PANE_ID"` を打つ。

Herdr の中で tmux は起動しない（状態の表示が効かなくなる）。

## 画面の構成

```
ワークスペース: okuradi（本体）
├─ タブ main
│  └─ lead        メインの Claude（あなたと話す・指示と回収をする）
└─ タブ run       アプリのサーバー・ログ・長い処理

ワークスペース: okuradi-<ブランチ>（並行作業のとき、Issue ごとに1つ）
└─ タブ
   └─ impl-5      その Issue の実装担当
```

**担当は名前で呼ぶ。** ペインの ID（`w1:p2` など）は、閉じると二度と使われない。

| 名前 | 役割 |
|---|---|
| `lead` | メインの Claude |
| `impl-<Issue 番号>` | その Issue の実装担当（例: `impl-5`） |

## Issue を並行で進める

`lead` に「#5 を別のペインで進めて」と頼むと、次の流れで動く。

```bash
# 1. ブランチつきの作業フォルダを、別のワークスペースとして作る
herdr worktree create --branch feature/episode-list --base main \
  --path ../okuradi-wt/episode-list --label "#5 回の管理" --no-focus
# → 返ってくる結果の root_pane にペインの ID が入っている

# 2. そのペインで Claude を起動し、名前を付ける
herdr agent start impl-5 --kind claude --pane <ペインのID>

# 3. 指示を送る（送ったらすぐ戻る）
herdr agent prompt impl-5 "Issue #5 を実装して、PR を作ったら報告して"

# 4. ときどき様子を見る（待つのは1回10分まで。長い作業は繰り返す）
herdr agent wait impl-5 --timeout 600000   # 600000 = 10分（単位はミリ秒）
herdr agent get impl-5
herdr agent read impl-5 --source recent-unwrapped --lines 120
```

- `lead` が `worktree create`・`agent start`・`agent prompt` を使うときは、毎回許可を求めてくる。中身（ブランチ名・指示の文）を見て許可する
- 待っている間も、`lead` とは話せる（`lead` が様子見をバックグラウンドで回すため）
- 担当が「承認待ち」になったら、`lead` は勝手に答えず、あなたに知らせる。担当の画面へは次で移る

  ```bash
  herdr agent focus impl-5
  ```

  サイドバーの担当をクリックしても移れる。
- 並べるのは **2つまで** を目安にする（レビューと確認が追いつかなくなるため）

### 片付ける

PR がマージされてから片付ける。**本体の okuradi のワークスペースは対象にしない**（音声や途中のファイルがある）。

```bash
herdr worktree list                               # 並行作業のワークスペースの ID を確かめる
herdr worktree remove --workspace <そのワークスペースのID>
git branch -d feature/episode-list                # 手元のブランチも消す
```

`--workspace` を省くと、今いるワークスペースが対象になる。必ず ID を指定する。

### 作業フォルダで気をつけること

- **音声や途中のファイルは入っていない。** `ep*/0*_*/` は git の管理外なので、新しい作業フォルダには `config.yml` しかない。
  試すときは、テスト用の短い音声を作るか、本体の `ep01` の音声を読むだけにする（本体のファイルは書き換えない）。
- **Python の仮想環境が無い。** 本体の `.venv` を使う（`~/workspace/okuradi/.venv/bin/python`）か、作業フォルダで作る。
- **main への push を止める仕組みは、作業フォルダでも効く。** ただし、その仕組みが main に入った後に作ったブランチに限る。

## よく使うキー

マウスでも全部操作できる（クリックで移動、境目のドラッグで大きさを変える、右クリックでメニュー）。

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

ワークスペースの切り替えは、サイドバーをクリックするか、`herdr agent focus <名前>` で担当ごと移る。

## 戻る・止める

- 画面を離れた後に戻る: もう一度 `start.sh`（`lead` が動いていれば、そのまま開くだけ）
- PC を再起動した後: Herdr の中の処理は止まっている。`start.sh -c` で、前回の会話の続きから起動し直す
  - `-c` を付け忘れて新しい会話で起動してしまったときは、Claude で `/resume` を打つと、前の会話を選び直せる
- その日の作業を終える: Claude で `/作業終了`。区切っていなければ先に区切り、作業のペインを閉じて印を置く。
  **印があると、次に `start.sh -c`（続きから）で開いたときも `/始め` が促される**（#183）。
  `/作業終了` を通さずに閉じた日は、続きから開いた朝に `/始め` を自分で打つ
- 全部止める: `herdr server stop`（中の Claude も止まる。作業中の担当がいないときだけ）

## 作業のペイン（#183）

`/始め` の最後に、Claude の右へ3つ並べる（`.claude/scripts/作業ペイン.sh`）。`/作業終了` で閉じる。

| ペイン | 中身 |
|---|---|
| 変更 | 直前に直した所の差分（`.claude/hooks/show-diff.py` が書き、ペインの中で映し直す）。**最初は空** |
| GUIログ | GUI のサーバーの出力。**`/始め` では立てない。** 使う日に `作業ペイン.sh gui` |
| 今日の一手 | `.claude/state/今日の一手.md` を `less` で |

- ペインは**名前で探す**（ID は毎回変わる）。一部だけあるときは、形が分からないので触らない
- 置き場所の `.claude/state/` は git の管理外

## フリーライフと一緒に使う

Herdr は1つだけ動き、その中にワークスペースが並ぶ。フリーライフ（`フリーライフ資料`）と okuradi は、同じ Herdr の中の別のワークスペースになる。

- どちらのメニュー（F12 の「herdr: フリーライフ資料」「herdr: okuradi」）から開いても、同じ Herdr が開く。左のサイドバーで両方のワークスペースを行き来できる
- `start.sh` がフリーライフに対してするのは、ワークスペースを用意することと、`--with-freelife` のときにフリーライフの `start.sh` を実行することだけ。フリーライフのリポジトリや担当（`director` など）には手を入れない
- `--with-freelife` は、フリーライフの編集局長（`director`）がすでに動いていれば何もしない
- フリーライフの `start.sh` は、フリーライフのワークスペースの中の、何も動いていないシェルで実行する。空いているシェルが無いときは、フリーライフの画面で手で `./start.sh` を実行する
- 担当の名前は Herdr 全体で重ならないようにする（okuradi は `lead` と `impl-<番号>`）
- PC を再起動した後は、F12 →「herdr: okuradi + フリーライフ」で両方を起動し直せる

## 困ったとき

- 状態がおかしい: `herdr agent list`、`herdr agent explain <名前> --json`
- Herdr 全体の様子: `herdr status`
- ログ: `~/.config/herdr/`
