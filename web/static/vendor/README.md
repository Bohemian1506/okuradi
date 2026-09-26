# vendor（外から持ってきたファイル）

ネットにつながらなくても波形が出せるよう、リポジトリに置いている（#36 の判断）。
CDN から読まないのは、WSL で作業中にネットが切れると波形が出なくなるため。

| ファイル | 中身 | 版 | ライセンス |
|---|---|---|---|
| `wavesurfer.min.js` | 波形の表示と再生 | 7.8.6 | BSD-3-Clause |
| `regions.min.js` | 区間の選択・伸縮（Regions プラグイン） | 7.8.6 | BSD-3-Clause |
| `multitrack.min.js` | レーンに音源を並べる（wavesurfer-multitrack。#85 のタイムライン） | 0.4.12 | BSD-3-Clause |

どれも UMD 版。読み込むと `window.WaveSurfer` と `window.WaveSurfer.Regions`、`window.Multitrack` が生える。

**ライセンス文は `LICENSE-wavesurfer.txt` と `LICENSE-wavesurfer-multitrack.txt` に置いてある。** 配布ファイル（`.min.js`）には
著作権表示が入っていないが、BSD-3-Clause は再配布のときに表示を残すことを求めている。
このリポジトリは公開なので、消さないこと。版を上げたら、この文も取り直す:
`curl -sSL -o web/static/vendor/LICENSE-wavesurfer.txt https://unpkg.com/wavesurfer.js@<版>/LICENSE`
（multitrack は `https://unpkg.com/wavesurfer-multitrack@<版>/LICENSE` を `LICENSE-wavesurfer-multitrack.txt` へ）

## 版を上げるとき
```
curl -sSL -o web/static/vendor/wavesurfer.min.js https://unpkg.com/wavesurfer.js@<版>/dist/wavesurfer.min.js
curl -sSL -o web/static/vendor/regions.min.js    https://unpkg.com/wavesurfer.js@<版>/dist/plugins/regions.min.js
curl -sSL -o web/static/vendor/multitrack.min.js https://unpkg.com/wavesurfer-multitrack@<版>/dist/multitrack.min.js
```
上げたら、この表の版も直す。エコー区間のドラッグと伸縮を実際に触って確かめる。

**増やしてよいのは、wavesurfer.js の公式プラグインだけ**
（#3 の決定「外部ライブラリは波形表示の wavesurfer.js のみ可」を、**#87 で公式プラグインまで広げた**・2026-09-22）。
**それ以外は増やさない。**

## wavesurfer の本体が2つある（#85・2026-09-26）

`multitrack.min.js` は **wavesurfer 本体を中に同梱している**（`^7.6.3`）。上の `wavesurfer.min.js`（7.8.6）とは別物。

- **両方置く**（2026-09-26・ユーザーの判断・案A）。いまのエコーの画面は 7.8.6 のまま、
  新しいタイムラインの画面だけが `multitrack.min.js` を使う。**置き換えの途中で、いま動いているエコーの操作を壊さないため**
- **エコー区間をタイムラインに取り込み終えたら、7.8.6 を消せるか見る**（#85 の4段目）。
  実装のあとの調整で、結局 multitrack だけ（案B）になってもよい（ユーザー）
- **同じページに読み込んでも互いを壊さない**（2026-09-26 にヘッドレスの Chrome で確かめた）。
  `multitrack.min.js` は `window.Multitrack` だけを生やし、`window.WaveSurfer` は置き換えない。
  3つを読み込んだあとも、7.8.6 の `WaveSurfer.create` + `Regions` と `Multitrack.create` が両方作れた
