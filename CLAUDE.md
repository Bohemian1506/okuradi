# CLAUDE.md

okuradi（置くラジ）で作業するときのルール。毎回読まれるので、短く保つ。

## 絶対ルール

### main に直接コミット・push しない
1. `git switch main && git pull`
2. `git switch -c <種別>/<内容>`（種別: `feature/` `fix/` `docs/` `refactor/` `chore/`）
3. 作業 → コミット → `git push -u origin <ブランチ>` → `gh pr create --base main`
4. マージしたらブランチを消す

守り: `.claude/hooks/block-main-push.sh`（Claude 側）と `.githooks/pre-push`（人が打った場合）。
clone し直したら `git config core.hooksPath .githooks` を実行する（`.git/hooks/` のフックは使われなくなる）。

### 勝手に決めない
- 選べる案があるときは、**それぞれで何が変わるか**を説明し、おすすめを添えて、ユーザーが決めるのを待つ
- 取り返しのつかない操作（削除・上書き・外部への送信）は、実行前に確認する
- 見積もりや先送りには根拠を添える。分からないときは分からないと言う

## プロジェクト

10分ラジオの制作パイプライン。収録ファイルを置くと、整音・文字起こし・タイトル作り・動画化まで進む。
いまは、確認と編集を GUI でできるようにしている。

- **誰のためか**: 番組を1人で作る本人。収録のあと、速く・迷わず公開までいけることが目的
- **守ること**
  - 中間ファイルを全工程で残す（1か所で失敗しても最初からやり直さずに済む）
  - 無音の自動カットはしない（喋りの「間」を残す）
  - Claude は `claude -p` から呼ぶ（サブスクの枠で動かし、API キーの従量課金にしない）
  - **GUI が完成するまでも、コマンド（`python build.py ep01 ...`）で番組を作れる状態を保つ**。GUI で使わない `cut`・`upload` の工程も消さない
  - 将来の拡張（表情差分・BGM・コーナー制）を塞がない。画像の並びや `segments` は配列のまま扱う（README の設計メモ）
- **決まっていること**: `docs/features.md`（機能）、`docs/components.md`（部品・画面）、Issue

| 項目 | 内容 |
|---|---|
| 処理 | `build.py`（Python / FFmpeg / faster-whisper / `claude -p`） |
| 今の GUI | `app.py`（Streamlit）。作り直すかどうかも含めて、技術構成は Issue #3 で決める |
| 回のデータ | `ep01/` など。`config.yml` だけ git で管理し、音声と途中のファイルは管理外 |
| 動かす場所 | WSL。仮想環境は `.venv/` |

## 担当（サブエージェント `.claude/agents/`）

| 担当 | 役割 |
|---|---|
| `pipeline-implementer` | 処理側（`build.py` と、GUI から工程を呼ぶ部分）の実装 |
| `ui-implementer` | 画面の実装 |
| `test-writer` | pytest のテスト |
| `audio-researcher` | FFmpeg・Whisper などの調査（実装しない） |
| `code-reviewer` | コードの細部のレビュー |
| `scope-reviewer` | 方針・範囲のレビュー |
| `design-reviewer` | 見た目・情報の並べ方のレビュー |
| `user-reviewer` | 番組を作る本人の立場でのレビュー |

レビュー担当は毎回全員ではなく、変更に合わせて必要な担当だけを呼ぶ（`/review-team` が選び、理由を示す）。

作業環境は `./start.sh` で開く（Herdr の起動と、メインの Claude `lead` の起動をまとめてやる）。
Issue を並行で進めるときは Herdr で Claude を増やす。使い方は `docs/herdr.md`。

## 作業の流れ
0. 始めるときは `docs/handoff.md`（申し送り）を読む。区切るときは上書きして PR にする
1. Issue を確かめる（無ければ作る）
2. ブランチを作る
3. 調査（必要なとき `audio-researcher`）→ 実装 → テスト
4. 変えた工程を実際の音声で通す
5. PR を作る → `/review-team <PR番号>` → 指摘を直すかユーザーが決める
6. ユーザーがよければマージ
7. すぐ議事録を書き、議事録の PR をマージする（下の「開発記録」）

## 進め方
- 作業は Issue から始める。Issue とその本文は、検討した案・決めたこと・理由を残す場所にする
- 指示の範囲だけを変える。ついでの改修はしない（気づいたことは報告するか Issue にする）
- **完了は「変えた工程を、実際の音声で通した」とき**。動かしていないものは「未確認」と書く
- 外部コマンド（ffmpeg / claude / Whisper）の失敗や、代わりの処理への切り替えは、必ずログか画面に出す（静かに失敗させない）
- レビューの指摘や memory・ドキュメントの記述は、コードや実際の動きで確かめてから採用する
- 画面の細部の作り込みは、機能がそろってから。操作を妨げる問題はすぐ直す
- 説明は専門用語を避けた短い日本語で。1回の説明で扱う考え方は1つにする

## 開発記録（議事録）
PR をマージしたら、次の作業に入る前に、その PR に至った経緯を `docs/dev-log/day-N.md` に追記し、議事録だけの PR を作ってマージする。
付け方と書くことは `docs/dev-log/README.md`。
