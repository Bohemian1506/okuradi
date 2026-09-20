# 申し送り

作業を区切るときに、次の人（次のセッションの Claude）へ残すメモ。**最新の1回分だけを書き、区切るたびに上書きする。** 経緯は `docs/dev-log/` を見る。

**main の位置に、コミットの番号や PR 番号を書かない。** この申し送りはその PR の中で書くので、
番号を書くとマージした瞬間に1つ古くなる。直してもその直しがまた main を進めるので、永久に追いつかない。
位置が要るときは `git log --oneline -1` を打つ。ここに書くのは**番号が変わっても正しいこと**だけにする。

## 2026-09-20（day-4 の途中で中断）

### いまの状態
- main は、**この申し送りを載せた PR をマージした所**（位置は `git log --oneline -1`）。**開いている PR は無し。ローカルのブランチは `main` だけ**（マージ済みのブランチは消してある）
- day-3 で GUI を最初から最後まで実装した（#5 枠 → #6 収録〜整音 → #7 仕上げ → #8 ログ・チャット・改善メモ）。day-4 は #77（GUI の開き方）と、30分番組化の設計 Issue 2件
- **必須の17機能と、部品1〜19 の実装がすべて終わった**（`docs/features.md` の「実装の状況」）。`pytest` 188件が通る
- **`ep01/config.yml` に、コミットしていない変更が1つある。** ユーザーが GUI で保存したエコー区間（`10.69〜14.01 / light`）。消さずに残してある。要らなければ `git checkout ep01/config.yml`
- 波形は wavesurfer.js（#36）。ファイルは `web/static/vendor/` に置いてあり、CDN からは読まない
- 回のデータは `ep01` だけ。音声と途中のファイルは git の管理外

### 開いている Issue
| Issue | 内容 | いま |
|---|---|---|
| #53 | 新しい GUI だけで1回分を通し、`app.py` を消す | **ユーザーが実物の音声でやる**（Claude にはできない）。**v1 の最後の関門** |
| #79 | mix 工程を新設する（30分番組化） | **着手しない。** 論点を洗い出しただけ |
| #82 | OP テーマソングの音量カーブ（#79 の子） | **着手しない。** 同上 |

### 次にやること
1. **#53 通しリハーサル**（ユーザー）— 実際の収録で最初から最後まで通して、詰まった所を Issue にする
   - 開き方は下の「GUI の起動」
   - 通せたら消すもの: `app.py` / `requirements.txt` の streamlit・altair・pandas・**numpy** / `CLAUDE.md` の「古い GUI」の行 / `README.md` の Streamlit の節と「まだ1回分を通していない」の断り
2. 通して詰まった所が出たら、Issue にしてから直す。**Claude ができるのはここから**
3. **#79 / #82 は着手しない。** #53 を通してから。30分の形に手を入れてから壊れると、mix のせいか元からかが切り分けられなくなる

### 作業の始め方
- GUI の開き方は下の「GUI の起動」（**ここに書くと2か所になって片方が古くなる**）
- コマンド: `.venv/bin/python build.py ep01 --from clean --to clean`（GUI が無くても番組を作れる状態は保つ）
- 追加インストールは `uv pip install --python .venv/bin/python <名前>`（この `.venv` は uv が作ったもので、pip が入っていない）
- WezTerm の F12 から開く（使い方は `docs/herdr.md`）
  - 「herdr: okuradi」: okuradi だけ
  - 「herdr: フリーライフ資料」: okuradi の `lead` も起動してから、フリーライフを開く
  - 「herdr: okuradi + フリーライフ」: 両方を起動して、okuradi を開く
- 前の会話の続きから始めるときは、端末で `~/workspace/okuradi/start.sh -c`
- 作業のルールは `CLAUDE.md`（Issue から始める / 勝手に決めない / レビュー担当は必要なときに呼ぶ / マージしたらすぐ議事録の PR）

### GUI の起動
```
.venv/bin/python -m uvicorn web.main:app --host 0.0.0.0 --reload   # 起動
./open-gui.sh                                                       # ブラウザで開く
```
- **`--host 0.0.0.0` が要る。** 付けないと WSL の中だけで待ち、Windows 側のブラウザから入れない
- **`http://localhost:8000` は通らない**（Windows 10 では WSL の localhost 転送が効かない。#77 で確かめた）
- `./open-gui.sh` が、そのときの WSL の IP を調べてブラウザを開く。**IP は再起動すると変わる**ので、数字を文書に書かないこと
- サーバーが動いていない / `127.0.0.1` だけで待っているときは、`open-gui.sh` が開かずに理由を出して止まる
- `--host 0.0.0.0` は同じ LAN の他の機械からも見える。外のネットワークでは避ける

### まだ確かめていないこと
- **1回分を通しで作れるか（#53）。** 工程ごとには `ep01` で動かして確かめたが、収録から公開用のコピーまで一続きに通してはいない
- **`.wslconfig` の `networkingMode=mirrored` を消すと `localhost` が通るようになるか。** 無効な値が入っていることで localhost 転送まで巻き添えになっている可能性がある（#77 に記録）。確かめるには `wsl --shutdown` が要るので、作業中はできない
- PC を再起動した後、「herdr: okuradi + フリーライフ」で、止まった状態から両方が起動するか
- Herdr で Issue を並行で進める流れ（`herdr worktree create` → 実装担当の起動 → 片付け）

### リポジトリの外にある設定（消えたら作り直す）

| 設定 | 場所 | 作り直し方 |
|---|---|---|
| `.wslconfig`（Windows 側） | `C:\Users\hiros\.wslconfig` に `networkingMode=mirrored` と書いてあるが、**Windows 10 では効かない**（mirrored は Windows 11 22H2 以降）。消すか注記するかは #77 で決める |
| F12 のメニュー（3つ） | `C:\Users\hiros\.wezterm.lua` の `launch_menu` | 書き方は `docs/dev-log/day-2.md` の #13 と `docs/herdr.md` |
| Herdr の Claude 連携 | `~/.claude/hooks/herdr-agent-state.sh` など | `herdr integration install claude` |
| Claude が Herdr を操作するスキル | `~/.claude/skills/herdr/SKILL.md` | `herdr --skill > ~/.claude/skills/herdr/SKILL.md`（Herdr を更新したときも） |
| Claude Design のプロジェクト | `共通の枠を出しました`（claude.ai/design）。**見本はここが正本**。実装が見本を追い越したら、`github.md` の同期メモと一緒に直す（#65・#70 でやった）。**直したら `docs/design/` にも取り込み直す**（`serve_url` に `&raw=1` を付けると元のファイルが取れる）。どちらの見本を見るかは `docs/design/README.md` の表 |
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
- **「安全にしてある」と書いたら、それを守るテストまで書く**（#63 で「同じ分け方をたどるので安全」と書いたのに、実際は2か所に写し取られていた。#58 と合わせて2回やった）
- **外部コマンドの振る舞いは、読んで決めつけず測る**（#63 で `acrossfade` で縮むと思っていたら、`aecho` が伸ばすぶんが勝っていた）
- **レビューの指摘は、指摘の中身だけでなく、指摘が立っている前提も確かめる**（#63 で、担当が置いた前提そのものが事実と違った）
- **`git add -A` を確かめずに使わない。** 文書だけの PR ではファイル名で指定する。使ったら `git diff --cached --name-only` を見てからコミットする（#78 で、ユーザーの作業を混ぜた）
- **「確かめたつもり」に気をつける。** WSL の中で `curl` が 200 を返しても、Windows 側から開ける確認にはならない（#75 → #77）
- **Issue を書く前に実機で測る。** #82 で、既存のやり方を流用する案が使えないと分かった（尺が 0.04秒 縮む）
- **文書に「〜だから使わない」と書くときは、その理由が明日も成り立つかを見る**（#70 で、自分で立てた Issue が直った瞬間に嘘になる理由を書いた）
- **「失敗しても進む」は、進んでよい場面かどうかを1つずつ見る**（#70 で、未保存を数えられないときに「無い」ことにして閉じさせていた）
- 画面の確かめに使うブラウザは `~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome`。**版は勝手に入れ替わる**ので、決め打ちせず `ls` で探す。CDP の接続がおかしくなったら Chrome を立て直す
- 画面の確かめには、ヘッドレスの Chrome を CDP（`node --experimental-websocket`）で動かせる。実際にマウスを動かしてドラッグまで試せる
- Herdr の担当の名前は、Herdr 全体で重ならないようにする（フリーライフは `director` など、okuradi は `lead` と `impl-<番号>`）
- `herdr worktree remove` は、`--workspace` を省くと今いる場所が対象になる。必ず ID を指定する
