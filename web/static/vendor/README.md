# vendor（外から持ってきたファイル）

ネットにつながらなくても波形が出せるよう、リポジトリに置いている（#36 の判断）。
CDN から読まないのは、WSL で作業中にネットが切れると波形が出なくなるため。

| ファイル | 中身 | 版 | ライセンス |
|---|---|---|---|
| `wavesurfer.min.js` | 波形の表示と再生 | 7.8.6 | BSD-3-Clause |
| `regions.min.js` | 区間の選択・伸縮（Regions プラグイン） | 7.8.6 | BSD-3-Clause |

どちらも UMD 版。読み込むと `window.WaveSurfer` と `window.WaveSurfer.Regions` が生える。

**ライセンス文は `LICENSE-wavesurfer.txt` に置いてある。** 配布ファイル（`.min.js`）には
著作権表示が入っていないが、BSD-3-Clause は再配布のときに表示を残すことを求めている。
このリポジトリは公開なので、消さないこと。版を上げたら、この文も取り直す:
`curl -sSL -o web/static/vendor/LICENSE-wavesurfer.txt https://unpkg.com/wavesurfer.js@<版>/LICENSE`

## 版を上げるとき
```
curl -sSL -o web/static/vendor/wavesurfer.min.js https://unpkg.com/wavesurfer.js@<版>/dist/wavesurfer.min.js
curl -sSL -o web/static/vendor/regions.min.js    https://unpkg.com/wavesurfer.js@<版>/dist/plugins/regions.min.js
```
上げたら、この表の版も直す。エコー区間のドラッグと伸縮を実際に触って確かめる。

**増やしてよいのは、wavesurfer.js の公式プラグインだけ**
（#3 の決定「外部ライブラリは波形表示の wavesurfer.js のみ可」を、**#87 で公式プラグインまで広げた**・2026-09-22）。
**それ以外は増やさない。**

## まだ置いていないが、置くと決めたもの

`wavesurfer-multitrack`（#87 で採ると決めた。**実際に置くのは #85 の実装のとき**）。

- 版 0.4.12 / BSD-3-Clause / UMD / 64,024 バイト。読み込むと `window.Multitrack` が生える
- **wavesurfer 本体を同梱している。** 実測で、`multitrack.min.js` だけを読み込んで動いた
- **同梱しているのは `^7.6.3`。この表の 7.8.6 と2つ同居することになる。**
  どちらを使うか（片方を消すか、両方置くか）は、置くときに決める
