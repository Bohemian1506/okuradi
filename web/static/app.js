// 置くラジ 制作GUI
// 画面の組み立てだけ。処理は build.py（サーバー側）にある。
// デザインの見本: docs/design/frame-common-v2.dc.html（共通の枠）
//                 docs/design/screen1-episode-settings.dc.html（画面1）

const STATE_CLASS = {
  "未実行": "is-todo",
  "実行できる": "is-ready",
  "完了": "is-done",
  "古い": "is-stale",
  "不要": "is-skip",   // timeline.yml が無い回のミックス（要らないが、実行はできる）
};

// 工程がどの画面にあるか（docs/components.md の画面の割り当て）
const TAB_OF_STEP = {
  source: "2", scan: "2", clean: "2", mix: "2",
  transcribe: "3", meta: "3", video: "3",
};

const SVG = {
  plus: '<path d="M7 1.5v11M1.5 7h11"/>',
  trash: '<path d="M2 3.5h10M5.5 3.5V2h3v1.5M3.5 3.5l.7 8h5.6l.7-8" stroke-linejoin="round"/>',
  up: '<path d="M2 8l4-4 4 4"/>',
  down: '<path d="M2 4l4 4 4-4"/>',
  play: '<path d="M3 2l9 5-9 5z"/>',
  redo: '<path d="M11.5 7A4.5 4.5 0 1 1 9.8 3.5M9 1.5l1.5 2L8.3 4.7" stroke-linecap="round"/>',
  check: '<path d="M1.5 5l2.5 2.5 4.5-5"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5" stroke-linecap="round" stroke-linejoin="round"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
  playBig: '<path d="M4 2l10 6-10 6z"/>',
  pause: '<path d="M3 2h4v12H3zM9 2h4v12H9z"/>',
  send: '<path d="M7 12V2M2.5 6.5L7 2l4.5 4.5" stroke-linecap="round" stroke-linejoin="round"/>',
  memo: '<path d="M3 1.5h6l3 3v8H3z" stroke-linejoin="round"/><path d="M5 7h4M5 9.5h4"/>',
  close: '<path d="M2 2l10 10M12 2L2 12"/>',
  title: '<path d="M2 3.5h10M4 3.5v7.5M10 3.5v7.5" stroke-linecap="round"/>',
  lines: '<path d="M2 3h10M2 6h10M2 9h7M2 12h4" stroke-linecap="round"/>',
  tag: '<path d="M2 2h5l5 5-5 5-5-5z" stroke-linejoin="round"/><circle cx="4.5" cy="4.5" r=".8" fill="currentColor"/>',
};

const ACCEPTED_TEXT = "wav / m4a / mkv / mp4 / mov / flv";

// どの画面にどの工程があるか（TAB_OF_STEP の裏返し）
const STEPS_OF_TAB = { "1": [], "2": ["source", "scan", "clean", "mix"], "3": ["transcribe", "meta", "video"] };

const state = {
  episodes: [],
  series: {},        // { キー: {label, hint} }
  nextNumber: 1,
  selected: null,    // 選んでいる回の detail
  rowIds: [],        // 行ごとの見分け札（segments と同じ並び）
  savedRows: null,   // 札 -> 保存されている中身（直した行を見分けるため）
  nextRowId: 0,
  tab: "1",
  save: "saved",     // saved / dirty / saving / error
  saveError: "",
  job: null,         // 実行中（か直前に終わった）工程
  showLog: false,
  logKind: "かんたん",   // かんたん / くわしい
  chatOpen: false,
  chat: null,        // 相談チャット
  chatDraft: "",
  chatWaiting: false,
  chatError: "",
  detailLog: null,
  stream: null,
  source: null,      // いま入っている収録ファイル（コーナーの枠が無い回だけ使う。#85 の3段目）
  obs: null,         // OBS のフォルダの様子
  sourceBusy: false,
  sourceError: "",
  frames: null,      // コーナーの枠の一覧（#85 の3段目）
  framesError: "",
  frameBusy: {},     // 枠ごとの取り込み中・削除中（枠のid -> true）
  frameObsOpen: null, // OBSの一覧を開いている枠のid
  cutFrame: null,    // カット（言い直し）を引いている枠のid（#85 の6段目）
  cutsWork: {},      // 枠id -> 作業用のカット配列（保存するまでサーバーへ送らない。エコー・BGM と同じ作法）
  cutsSaved: {},     // 枠id -> 保存されている中身のスナップショット（JSON文字列。未保存かを見分ける）
  cutPicked: -1,     // 選んでいる区間（カット用。エコーの state.picked とは別に持つ）
  cutSaving: false,  // 「保存する」を押してから終わるまで（BGM と同じ作法。#85 の6段目のレビュー）
  cutSkip: false,    // カットした所を飛ばして聴くか
  cutSeekPending: null, // 下見の「カットへ」で来たときの飛び先（{frameId, at}）。波形が
                        // 読み込み中でも、読み終わってからの再描画で拾えるよう控えておく
  scan: null,        // 下見の文字起こし
  at: 0,             // 再生位置（秒）
  playing: false,
  wave: null,        // 波形に使う音（trimmed.wav）の在りかと長さ
  timeline: null,    // timeline.yml の並び（#85 の2段目。無い回は null のまま）
  timelineError: "", // timeline.yml が壊れているときの理由（黙って隠さない）
  music: null,       // assets/music/ の曲の一覧（BGM を置く選択肢。#85 の5段目）
  musicError: "",
  bgmOpen: false,    // 「曲を置く」フォームを開いているか
  bgmSource: "",     // フォームで選んでいる曲
  bgmAnchor: "",     // フォームで選んでいるコーナー（錨）
  bgmBusy: {},       // BGM の id ごとの処理中（いまは "new" キー＝曲を置いている間だけ使う）
  bgm: [],           // BGM の並び（画面の作業用。エコー区間と同じく、保存するまでサーバーへ送らない）
  bgmSaved: "[]",    // 保存されている中身のスナップショット（未保存かを見分ける。#85 の5段目のレビュー）
  bgmSaving: false,  // 「保存する」を押してから終わるまで
  echoes: [],        // エコー区間
  echoesSaved: "",   // 保存されている中身（未保存かを見分ける）
  picked: -1,        // 選んでいる区間
  previewing: -1,    // 試聴中の区間
  clean: null,       // 整音の結果
  mix: null,         // ミックスの結果
  listening: "scan", // いま鳴らしているもの（scan / clean / mix / preview）
  transcript: null,  // 確定版の文字起こし
  texts: [],         // 画面で直している文字（行ごと）
  textsSaved: "",    // 保存されている中身
  editing: -1,       // 書き換え中の行
  draft: "",         // 書き換え中の文字
  showOrig: {},      // 元の文字を開いている行
  meta: null,        // メタデータ（保存されているもの）
  draftMeta: null,   // 画面で直しているメタデータ
  metaSaved: "",
  newTag: "",
  video: null,       // 動画の様子
  copyText: null,    // コピー用のひとそろい（保存済みから）
  copyDraft: null,   // コピー用のひとそろい（保存前の直しから）
  copyBusy: false,
  copied: "",        // いまコピーしたもの（数秒だけ出す）
};

const TITLE_LIMIT = 60;   // YouTube は60文字を超えると途中で切れる

const PRESETS = { none: "なし", light: "軽め", hall: "響く" };

// 音は1つだけ鳴らす
const audio = new Audio();

const $ = (id) => document.getElementById(id);

function icon(path, size = 14, width = 1.8, box = 14) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${box} ${box}" fill="none"
    stroke="currentColor" stroke-width="${width}">${path}</svg>`;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function api(path, options) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch (err) { /* JSON でない応答はそのまま出す */ }
    throw new Error(detail);
  }
  return res.json();
}

// ---------------------------------------------------------------- 部品1 回セレクタ

function renderEpisodes() {
  $("episode-count").textContent = state.episodes.length ? `${state.episodes.length}件` : "";
  const list = $("episode-list");
  list.innerHTML = "";

  // ひな型にする回が無いと新しい回は作れないので、押す前に理由を出す
  const canCreate = Object.keys(state.series).length > 0;
  const newButton = $("new-episode");
  newButton.disabled = !canCreate;
  newButton.title = canCreate ? "" : "ひな型にする回がありません";

  if (!state.episodes.length) {
    list.appendChild(el("div", "episodes-empty", canCreate
      ? "まだ回がありません"
      : "まだ回がありません。最初の回は手で作ってください（ep01 のように）"));
    return;
  }

  for (const ep of state.episodes) {
    const button = el("button", "episode");
    if (state.selected && ep.name === state.selected.name) button.classList.add("is-selected");
    if (ep.error) {
      button.classList.add("is-broken");
      button.disabled = true;
      button.title = ep.error;
    } else {
      button.onclick = () => selectEpisode(ep.name);
    }

    const top = el("div", "episode-top");
    top.append(el("span", "episode-id", ep.name),
               el("span", "episode-progress", `${ep.done}/${ep.total}`));
    button.append(top, el("div", "episode-theme", ep.theme));

    if (ep.error) {
      button.appendChild(el("div", "episode-error", ep.error));
    } else {
      const dots = el("div", "episode-dots");
      for (const step of ep.steps) {
        const dot = el("span", `dot ${STATE_CLASS[step.state]}`);
        dot.title = `${step.label}: ${step.state}`;
        dots.appendChild(dot);
      }
      button.appendChild(dots);
    }
    list.appendChild(button);
    // 回が増えると、選んでいる回が一覧の外に隠れてしまう
    if (button.classList.contains("is-selected")) {
      button.scrollIntoView({ block: "nearest" });
    }
  }
}

// ---------------------------------------------------------------- 部品3 工程ステッパー

function renderSteps() {
  const box = $("steps");
  box.querySelectorAll(".step").forEach((node) => node.remove());
  const needle = $("needle");

  const steps = state.selected ? state.selected.steps : [];
  if (!steps.length) {
    needle.hidden = true;
    $("tabs-episode").textContent = "";
    return;
  }
  $("tabs-episode").textContent = state.selected.name;
  // 工程の数が変わっても、列の幅と目盛りの数を CSS 側で書き換えずに済むように
  box.style.setProperty("--step-count", steps.length);

  steps.forEach((step, index) => {
    const button = el("button", `step ${STATE_CLASS[step.state]}`);
    if (TAB_OF_STEP[step.key] === state.tab) button.classList.add("is-here");
    button.style.gridColumn = String(index + 1);
    button.title = `${step.label}: ${step.state}`;
    button.onclick = () => selectTab(TAB_OF_STEP[step.key]);
    button.append(el("span", "step-name", step.label),
                  el("span", "step-state", step.state));
    box.insertBefore(button, box.querySelector(".ticks-fine"));
  });

  // 赤い針は「今いる工程」（最初の未完了）を指す。全部終わっていれば指す先がないので隠す。
  const here = steps.findIndex((s) => s.state !== "完了");
  needle.hidden = here === -1;
  if (here !== -1) needle.style.left = `calc(100% / ${steps.length} * ${here + 0.5})`;
}

// ---------------------------------------------------------------- タブ

function selectTab(tab) {
  if (!tab) return;
  if (tab !== state.tab) { stopWaves(); stopVideo(); }  // 見えない場所で鳴らさない
  state.tab = tab;
  document.querySelectorAll(".tab[data-tab]").forEach((node) => {
    node.classList.toggle("is-active", node.dataset.tab === tab);
  });
  renderSteps();
  renderMain();
}

// renderMain() は毎回 main.innerHTML = "" で組み立て直す。timelineView.box は
// 使い回している（波形の widget を作り直さないため）ので、その一瞬だけ画面から外れる。
// **外れると scrollLeft が 0 に戻る**（ブラウザの仕様。#98 のレビューで見つけた）ので、
// 組み立て終わったあとに restoreTimelineScroll() で戻す
function renderMain() {
  renderMainInner();
  restoreTimelineScroll();
  restoreWaveScroll("cut");
}

function renderMainInner() {
  const main = $("main");
  main.innerHTML = "";

  // 失敗はどの画面でも見えるようにする（CLAUDE.md「静かに失敗させない」）
  if (state.actionError) main.appendChild(errorBanner());

  if (!state.selected) {
    main.appendChild(placeholder("回がありません", "左の「新しい回」から作ってください"));
    return;
  }
  if (state.tab === "1") {
    main.appendChild(segmentsCard());
    return;
  }
  if (state.tab === "2") {
    main.appendChild(screenRecording());
  } else {
    main.appendChild(screenFinishing());
  }
}

// ---------------------------------------------------------------- 部品9・10 音源

function section(no, title, note, body, step, right) {
  const box = el("div", "section");
  const head = el("div", "section-head");
  const titles = el("div", "section-titles");
  titles.append(el("div", "section-title", title), el("div", "section-note", note));
  head.append(el("div", "section-no", String(no)), titles);
  if (right) head.appendChild(right);
  if (step) head.appendChild(runRow(step));
  box.append(head, body);
  return box;
}

function stepOf(key) {
  return state.selected.steps.find((s) => s.key === key);
}

function screenRecording() {
  const box = el("div", "sections");
  // 枠に分けて入れる形にするかは、サーバー（`sources.is_framed`）が決めた値をそのまま使う。
  // 画面側で条件を作り直すと、サーバーの判定とずれることがある（#216 のレビュー）。
  const framed = !!(state.frames && state.frames.framed);

  if (state.framesError) {
    // 取得に失敗したときは、黙って「1本だけの回」の形に戻さない（#216 のレビュー）
    const card = el("div", "source-error");
    card.append(el("span", "mark", "!"), el("span", null,
      `音源の枠を読み込めませんでした: ${state.framesError}`));
    box.appendChild(section(1, "音源を入れる",
      "コーナーごとの枠に、収録ファイルを入れます。", card));
  } else if (framed) {
    box.appendChild(section(1, "音源を入れる",
      "コーナーごとの枠に、収録ファイルを入れます。OBSの録画なら、工程を動かすときに音声を取り出します。",
      framesSection()));
  } else {
    const has = state.source && state.source.state === "使える";
    box.appendChild(section(1, "音源を入れる",
      "収録ファイルを1本置く。OBSの録画なら、工程を動かすときに音声を取り出します。",
      has ? sourceCard() : sourceAdd()));
  }

  box.appendChild(section(2, "下見を読む",
    "ざっくりの文字起こし。行を押すとそこから再生。読むだけで直せません（カット点を探す用）。",
    scanCard(), stepOf("scan")));

  if (!framed && !state.framesError) {
    // 枠の無い回（config.yml が1コーナーだけの回。ep01 など）は、画面からカットを
    // 引けない。節の番号はそろえたまま、案内だけにする（#85 の6段目のレビュー）
    const card = el("div", "panel-card");
    card.appendChild(el("div", "wave-empty",
      "この回はコーナーが1つの回なので、カットは config.yml の cuts で指定します。"));
    box.appendChild(section(3, "カット（言い直し）を決める", "", card));
  } else {
    box.appendChild(section(3, "カット（言い直し）を決める",
      "コーナーを選び、その生音の波形をドラッグして区間を選ぶ。カットは消すだけ（#85 の6段目）。"
      + "カットの時刻は、そのコーナーの生音（00_raw）の時刻。",
      cutCard(), null, cutSaveRow()));
  }

  box.appendChild(section(4, "エコー区間を決める",
    "波形をドラッグして区間を選び、プリセットを付ける。タイトルコールなど一部だけに。",
    echoCard(), null, echoSave()));

  box.appendChild(section(5, "整音して聴く",
    "前後の無音を切り、音量をそろえ、エコーをかける。聴いて確かめる1つ目の確認ポイント。",
    cleanCard(), stepOf("clean")));

  box.appendChild(section(6, "ミックス（曲を重ねる）して聴く",
    "整音した喋りに、timeline.yml の BGM・SE を重ねる。無ければ喋りだけの音のまま。"
    + "重ねた曲の大きさ・位置が合っているかを聴いて確かめる。"
    + "BGM は下の「タイムラインの並びを確かめる」欄から置ける。"
    + "SE を画面で置く部品はこのあと足す（いまは timeline.yml を直に書く）。",
    mixCard(), stepOf("mix")));

  // timeline.yml がある回だけ出す（#85 の2段目・5段目）
  const timelineNote = "timeline.yml に書いた音源の並び。BGM は曲を置く・ドラッグで位置を合わせる・"
    + "音量の点を動かす・削除ができる（#85 の5段目）。本編・SE はまだ見るだけ。"
    + "位置は出来上がり（カットしたぶんを引いた）の長さで出しています"
    + "（#85 の6段目。カットは上の「カット（言い直し）を決める」で引きます）。";
  if (state.timelineError) {
    destroyTimelineMultitrack();
    const card = el("div", "panel-card");
    const note = el("div", "wave-note is-error");
    note.append(el("span", "mark", "!"),
                el("span", null, `タイムラインを読み込めませんでした: ${state.timelineError}`));
    card.appendChild(note);
    box.appendChild(section(7, "タイムラインの並びを確かめる", timelineNote, card));
  } else if (state.timeline && state.timeline.timeline) {
    box.appendChild(section(7, "タイムラインの並びを確かめる", timelineNote, timelineCard()));
  }
  return box;
}

// ---------------------------------------------------------------- 画面3 仕上げ

function screenFinishing() {
  const box = el("div", "sections");

  box.appendChild(section(1, "文字起こしを直す",
    "確定版。文字を押すとその場で書き換え。直した行には印が付き、元の文字も見られます。",
    transcriptCard(), stepOf("transcribe"), transcriptSave()));

  box.appendChild(section(2, "タイトル・概要欄・章・タグを直す",
    "AIが作った案を直す。直した文字起こしから作り直すこともできます。",
    metaCard(), stepOf("meta"), metaSave()));

  box.appendChild(section(3, "動画を確かめる",
    "背景画像と音声で mp4 を作る。BGM・SE を重ねた回はミックスの音、"
    + "重ねていない回は整音の音をそのまま使う。これを YouTube に上げます。",
    videoCard(), stepOf("video")));

  box.appendChild(section(4, "コピーして YouTube に貼る",
    "動画をアップロードしたら、順に貼るだけ。章とクレジットは概要欄の末尾に自動で付きます。",
    copyCard(), null, studioLink()));
  return box;
}

// ---------------------------------------------------------------- 部品19 動画プレビュー

// 動画も、renderMain() のたびに作り直さない。作り直すと再生が止まる。
const videoView = { node: null, src: null, at: 0, playing: false, duration: 0 };

function videoNode(src, poster) {
  if (!videoView.node) {
    const node = el("video");
    node.preload = "metadata";
    node.playsInline = true;
    node.onplay = () => {
      videoView.playing = true;
      audio.pause();            // 音は1つだけ鳴らす（自分は止めない）
      stopWaves();
      renderMain();
    };
    node.onpause = () => { videoView.playing = false; renderMain(); };
    node.onended = () => { videoView.playing = false; videoView.at = 0; renderMain(); };
    node.onloadedmetadata = () => { videoView.duration = node.duration || 0; renderMain(); };
    node.ontimeupdate = () => {
      // 毎コマ作り直すと重いので、1秒に4回まで
      if (Math.floor(node.currentTime * 4) === Math.floor(videoView.at * 4)) {
        videoView.at = node.currentTime;
        return;
      }
      videoView.at = node.currentTime;
      if (state.tab === "3") renderMain();
    };
    videoView.node = node;
  }
  // 絵が無いときは消す。消さないと、前の回の絵が残ったまま
  // 「作れません」の理由と並んで出る（表示が嘘をつく）
  if (poster) {
    if (videoView.node.getAttribute("poster") !== poster) videoView.node.poster = poster;
  } else if (videoView.node.hasAttribute("poster")) {
    videoView.node.removeAttribute("poster");
  }
  if (videoView.src !== src) {
    videoView.src = src;
    videoView.node.src = src;      // 作り直したら新しい動画を読む
    videoView.at = 0;
    videoView.playing = false;
    videoView.duration = 0;
  }
  return videoView.node;
}

function toggleVideo() {
  const node = videoView.node;
  if (!node) return;
  if (videoView.playing) { node.pause(); return; }
  node.play().catch((err) => {
    state.actionError = `動画を再生できませんでした: ${err.message}`;
    renderMain();
  });
}

function seekVideo(seconds, play = false) {
  const node = videoView.node;
  if (!node) return;
  node.currentTime = seconds;
  videoView.at = seconds;
  if (play && !videoView.playing) node.play().catch(() => {});
  renderMain();
}

function videoCard() {
  const data = state.video || { state: "未実行" };
  const box = el("div", "video-panel");

  const banner = jobBanner("video", "動画");
  if (banner) { box.appendChild(banner); if (data.state === "未実行") return box; }

  if (data.state === "未実行") {
    box.appendChild(el("div", "lines-empty",
      "まだ動画がありません。右上の「動画を実行」を押すと作られます。"));
    return box;
  }

  const stale = data.state === "古い";
  if (stale) box.classList.add("is-stale");
  const top = el("div", "video-top");
  const badge = el("span", stale ? "badge-stale" : "badge-done");
  badge.append(el("span", "mark"), document.createTextNode(stale ? "古い" : "完了"));
  const about = [data.name, data.duration, data.resolution, data.size]
    .filter(Boolean).join(" · ");

  const open = el("button", "btn-tiny is-quiet");
  open.innerHTML = `<svg width="13" height="13" viewBox="0 0 16 16" fill="none"
    stroke="currentColor" stroke-width="1.7"><path d="M2 4.5A1.5 1.5 0 0 1 3.5 3h3l1.5
    1.5h4.5A1.5 1.5 0 0 1 14 6v6a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 2 12z"/></svg>`
    + "フォルダを開く";
  open.onclick = () => openVideoFolder();

  top.append(badge, el("span", "video-about", about), el("span", "spacer"));
  if (stale) {
    const redo = el("button", "btn-primary");
    redo.innerHTML = icon(SVG.redo, 14) + "動画をやり直す";
    redo.onclick = () => runStep("video");
    top.appendChild(redo);
  }
  top.appendChild(open);
  box.appendChild(top);
  if (stale) {
    const why = el("div", "result-stale");
    why.append(el("span", "mark", "!"), el("span", null,
      `${data.stale_reason}。作り直すと、いまの音で動画ができます。`));
    box.appendChild(why);
  }

  // 再生前の絵が作れなかったら、黙って隠さず理由を出す
  if (data.poster_error) {
    const note = el("div", "wave-note is-error");
    note.append(el("span", "mark", "!"), el("span", null, data.poster_error));
    box.appendChild(note);
  }

  const body = el("div", "video-body");
  const stage = el("div", "video-stage");
  const player = videoNode(
    `/api/episodes/${state.selected.name}/video/file?t=${data.at || 0}`,
    data.poster || "");

  // 絵の中央にも大きな再生ボタンを重ねる（#64）。
  // 動画だけは「サムネイルを押す＝再生」の慣習が強いので、下のボタンと両方置く。
  // 止めている間だけ出す（再生中は絵を隠さない）
  const shell = el("div", "video-shell");
  shell.appendChild(player);
  if (!videoView.playing) {
    const big = el("button", "video-bigplay");
    big.innerHTML = `<svg width="30" height="30" viewBox="0 0 16 16" fill="currentColor">${SVG.playBig}</svg>`;
    big.title = "動画を再生";
    big.setAttribute("aria-label", "動画を再生");
    big.onclick = () => toggleVideo();
    shell.appendChild(big);
  }
  stage.appendChild(shell);
  const total = videoView.duration || data.seconds || 0;
  stage.appendChild(playerRow({
    total, at: videoView.at, playing: videoView.playing,
    disabled: !total, label: "動画",
    onToggle: () => toggleVideo(),
    onSeek: (to) => seekVideo(to, true),
  }));
  body.appendChild(stage);

  const marks = el("div", "video-marks");
  marks.appendChild(el("div", "lead", "章マーカー"));
  const chapters = (state.draftMeta && state.draftMeta.chapters) || [];
  if (!chapters.length) {
    marks.appendChild(el("div", "lead", "章がありません（②で足せます）"));
  }
  for (const chapter of chapters) {
    const row = el("button", "video-mark");
    row.append(el("span", "at", clock(chapter.seconds)),
               el("span", "what", chapter.label || "（見出しなし）"));
    row.title = "この位置から見る";
    row.onclick = () => seekVideo(chapter.seconds, true);
    marks.appendChild(row);
  }
  body.appendChild(marks);
  box.appendChild(body);
  return box;
}

async function openVideoFolder() {
  try {
    await api(`/api/episodes/${state.selected.name}/video/folder`, { method: "POST" });
  } catch (err) {
    state.actionError = err.message;
    renderMain();
  }
}

// ---------------------------------------------------------------- 部品18 コピーボタン

function studioLink() {
  const link = el("a", "meta-note", "YouTube Studio を開く ↗");
  link.href = "https://studio.youtube.com/";
  link.target = "_blank";
  link.rel = "noopener";
  link.style.whiteSpace = "nowrap";
  return link;
}

function copyCard() {
  const box = el("div", "copy-panel");
  const data = state.copyDraft || state.copyText;
  if (!data) {
    box.appendChild(el("div", "lines-empty",
      "まだメタデータがありません。②で作ると、ここからコピーできます。"));
    return box;
  }

  const issues = data.issues;
  if (issues.length) {
    const warn = el("div", "copy-warn");
    warn.append(el("span", "mark", "!"), document.createTextNode(
      "保留チェックに問題があるので、まだコピーできません（②を直してください）"));
    box.appendChild(warn);
  }

  const rows = el("div", "copies");
  // 概要欄は、目次が付いているかを押す前に確かめられるようにする
  const chapters = (data.description.match(/\n\d+:\d\d /g) || []).length;
  // クレジットは規約で要るもの（#137）。**入っていないことに気づけるようにする**
  const credited = (data.credits || []).length > 0;
  const added = [credited ? "クレジット" : null, chapters ? `目次${chapters}件` : null]
    .filter(Boolean).join("・");
  const descPeek = `${data.description.split("\n")[0]}`
    + (added ? ` …＋${added}` : "")
    + (credited ? "" : "（クレジットなし）");

  const items = [
    ["title", "タイトル", SVG.title, data.title],
    ["description", "概要欄（章・クレジットつき）", SVG.lines, descPeek],
    ["tags", "タグ", SVG.tag, data.tags],
  ];
  for (const [key, label, mark, peek] of items) {
    const button = el("button", "btn-copy");
    if (state.copied === key) button.classList.add("is-copied");
    button.disabled = issues.length > 0;
    const what = el("span", "what");
    what.innerHTML = icon(mark, 14, 1.6);
    what.append(document.createTextNode(state.copied === key ? "コピーしました" : label));
    button.append(what, el("span", "peek", peek || "（空）"));
    button.onclick = () => copyOne(key, data[key]);
    rows.appendChild(button);
  }
  box.appendChild(rows);

  // **YouTube は章が3件未満だと目次を表示しない**（#106 の6番）。
  // 1コーナーの回は正しい動きなので、**止めずに知らせるだけ**にする。
  // 貼った先で章にならないことに、いまは気づけなかった
  if (chapters > 0 && chapters < 3) {
    const note = el("div", "copy-note");
    note.append(el("span", "mark", "i"), document.createTextNode(
      `章が${chapters}件です。YouTube は3件以上ないと目次を出しません`
      + "（コーナーが少ない回では、これで正しいです）"));
    box.appendChild(note);
  }
  return box;
}

async function copyOne(key, text) {
  try {
    await navigator.clipboard.writeText(text || "");
    state.copied = key;
    renderMain();
    setTimeout(() => {
      if (state.copied === key) { state.copied = ""; renderMain(); }
    }, 2000);
  } catch (err) {
    state.actionError = `コピーできませんでした: ${err.message}`;
    renderMain();
  }
}

// ---------------------------------------------------------------- 部品16・17 メタデータと保留チェック

function metaDirty() {
  return JSON.stringify(state.draftMeta) !== state.metaSaved;
}

function metaSave() {
  const box = el("div", "segments-actions");
  if (!state.draftMeta) return box;
  const dirty = metaDirty();
  const badge = el("span", `save-badge ${dirty ? "is-dirty" : "is-saved"}`);
  badge.append(el("span", "mark"),
               document.createTextNode(dirty ? "未保存の変更あり" : "保存済み"));
  const save = el("button", `btn-save ${dirty ? "is-dirty" : "is-saved"}`,
                  dirty ? "保存する" : "保存");
  save.disabled = !dirty;
  save.onclick = () => saveMeta();
  box.append(badge, save);
  return box;
}

let copyTimer = null;

function refreshCopy() {
  // 打つたびに呼ばれるので、少し待ってからまとめて聞く
  clearTimeout(copyTimer);
  copyTimer = setTimeout(async () => {
    if (!state.draftMeta || !state.selected) return;
    try {
      state.copyDraft = await api(`/api/episodes/${state.selected.name}/copy`, {
        method: "POST", body: JSON.stringify(state.draftMeta),
      });
    } catch (err) {
      state.copyDraft = null;      // 作れなければ保存済みのほうを使う
    }
    renderMain();
  }, 300);
}

function metaCard() {
  const box = el("div", "section");
  const data = state.meta || { state: "未実行" };
  const running = state.job && state.job.state === "処理中"
    && state.job.episode === state.selected.name && state.job.step === "meta";

  if (running) {
    box.appendChild(el("div", "lines-empty", "タイトル・概要欄・章・タグを作っています…"));
    return box;
  }
  if (data.state !== "表示" || !state.draftMeta) {
    box.appendChild(el("div", "lines-empty",
      "まだ作っていません。右上の「メタデータを実行」を押すと作られます。"));
    return box;
  }

  const draft = state.draftMeta;
  const issues = pendingIssues(draft);
  if (issues.length) box.appendChild(issuesBox(issues));

  const card = el("div", "meta-card");

  // タイトル
  const titleField = el("div", "meta-field is-wide");
  const head = el("div", "meta-head");
  const over = draft.title.length > TITLE_LIMIT;
  head.append(el("div", "meta-label", "タイトル"),
              el("span", `meta-count ${over ? "is-over" : ""}`,
                 `${draft.title.length} / ${TITLE_LIMIT}`));
  const title = el("input", `meta-input ${over ? "is-over" : ""}`);
  title.value = draft.title;
  title.oninput = () => { draft.title = title.value; refreshCopy(); renderMain(); };
  titleField.append(head, title);
  if (over) {
    titleField.appendChild(el("div", "meta-warn",
      "60文字を超えています。YouTubeでは途中で切れて表示されます。"));
  }
  card.appendChild(titleField);

  // 概要欄
  const descField = el("div", "meta-field");
  const desc = el("textarea", "meta-text");
  desc.rows = 9;
  desc.value = draft.description;
  desc.oninput = () => { draft.description = desc.value; refreshCopy(); renderMain(); };
  descField.append(el("div", "meta-label", "概要欄"), desc,
                   el("div", "meta-note", "章とクレジットはコピー時に概要欄の末尾へ自動で付きます"));
  card.appendChild(descField);

  // 章とタグ
  const right = el("div", "meta-field");
  right.style.gap = "14px";
  right.append(chaptersField(draft), tagsField(draft));
  card.appendChild(right);

  box.appendChild(card);
  return box;
}

function issuesBox(issues) {
  const box = el("div", "issues");
  const body = el("div", "body");
  body.appendChild(el("div", "lead", "動画化に進む前に直してください"));
  for (const one of issues) {
    const row = el("div", "one");
    row.append(el("span", "dot", "•"), el("span", null, one));
    body.appendChild(row);
  }
  box.append(el("span", "mark", "!"), body);
  return box;
}

// サーバーと同じ決まりで見る（保存する前でも出せるように、画面でも数える）
function pendingIssues(meta) {
  const issues = [];
  if (!meta.title.trim()) issues.push("タイトルが空です");
  else if (meta.title.includes("（保留中）")) issues.push("タイトルが（保留中）のままです");
  if (!meta.description.trim()) issues.push("概要欄が空です");
  else if (meta.description.includes("（保留中）")) issues.push("概要欄が（保留中）のままです");
  if (!meta.chapters.length) issues.push("章がありません。1つ以上必要です");
  else {
    // **コーナーと1対1**（#106 で決めた）。サーバー側の pending_issues と同じ決まり
    const want = (state.selected && state.selected.segments || []).length;
    if (want && meta.chapters.length !== want) {
      issues.push(`章が${meta.chapters.length}件ですが、コーナーは${want}件です。`
        + "コーナーと1対1になるよう、メタデータを作り直すか章を直してください");
    }
    const blank = meta.chapters.find((c) => !c.label.trim());
    if (blank) issues.push(`${clock(blank.seconds)} の章に見出しがありません`);
  }
  return issues;
}

function chaptersField(draft) {
  const field = el("div", "meta-field");
  field.appendChild(el("div", "meta-label", "章"));

  const list = el("div", "chapters");
  if (!draft.chapters.length) {
    list.appendChild(el("div", "chapters-empty", "章がありません。1つ以上必要です。"));
  }
  draft.chapters.forEach((chapter, index) => {
    const row = el("div", "chapter");
    const at = el("button", "chapter-at", clock(chapter.seconds));
    at.title = "この位置から再生";
    at.onclick = () => listenTo("clean", chapter.seconds);

    const label = el("input");
    label.value = chapter.label;
    label.placeholder = "見出し";
    label.oninput = () => { chapter.label = label.value; refreshCopy(); renderMain(); };

    const remove = el("button", "btn-x");
    remove.innerHTML = icon(SVG.trash, 13);
    remove.title = "この章を削除";
    remove.setAttribute("aria-label", "この章を削除");
    remove.onclick = () => { draft.chapters.splice(index, 1); refreshCopy(); renderMain(); };

    row.append(at, label, remove);
    list.appendChild(row);
  });
  field.appendChild(list);

  const add = el("button", "btn-add-small");
  add.innerHTML = icon(SVG.plus, 11, 2) + "今の再生位置に章を追加";
  add.onclick = () => {
    const at = state.listening === "clean" ? Math.round(state.at) : 0;
    if (draft.chapters.some((c) => Math.abs(c.seconds - at) < 0.5)) return;
    draft.chapters.push({ seconds: at, label: "" });
    draft.chapters.sort((a, b) => a.seconds - b.seconds);
    refreshCopy();
    renderMain();
  };
  field.appendChild(add);
  return field;
}

function tagsField(draft) {
  const field = el("div", "meta-field");
  field.appendChild(el("div", "meta-label", "タグ"));

  const box = el("div", "tags");
  draft.tags.forEach((name, index) => {
    const chip = el("span", "tag", name);
    const x = el("button");
    x.innerHTML = `<svg width="9" height="9" viewBox="0 0 14 14" fill="none"
      stroke="currentColor" stroke-width="2.2"><path d="M2 2l10 10M12 2L2 12"/></svg>`;
    x.title = "タグを削除";
    x.setAttribute("aria-label", "タグを削除");
    x.onclick = () => { draft.tags.splice(index, 1); refreshCopy(); renderMain(); };
    chip.appendChild(x);
    box.appendChild(chip);
  });

  const input = el("input");
  input.placeholder = "追加して Enter";
  input.value = state.newTag;
  input.oninput = () => { state.newTag = input.value; };
  input.onkeydown = (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const name = input.value.trim();
    if (name && !draft.tags.includes(name)) draft.tags.push(name);
    state.newTag = "";
    refreshCopy();
    renderMain();
  };
  box.appendChild(input);
  field.appendChild(box);
  return field;
}

async function saveMeta() {
  try {
    state.meta = await api(`/api/episodes/${state.selected.name}/meta`, {
      method: "PUT", body: JSON.stringify(state.draftMeta),
    });
    setDraftMeta(state.meta);
    state.copyText = await api(`/api/episodes/${state.selected.name}/copy`)
      .catch(() => null);
    await reload({ keep: state.selected.name, keepSelected: true });
  } catch (err) {
    state.actionError = `メタデータを保存できませんでした: ${err.message}`;
  }
  renderMain();
}

function setDraftMeta(meta) {
  state.draftMeta = meta && meta.state === "表示" ? {
    title: meta.title, description: meta.description,
    chapters: meta.chapters.map((c) => ({ ...c })), tags: [...meta.tags],
  } : null;
  state.metaSaved = JSON.stringify(state.draftMeta);
  state.newTag = "";
}

async function loadMeta(name) {
  state.meta = await api(`/api/episodes/${name}/meta`).catch(() => null);
  setDraftMeta(state.meta);
  state.copyText = await api(`/api/episodes/${name}/copy`).catch(() => null);
  state.copyDraft = null;
}

async function loadVideo(name) {
  state.video = await api(`/api/episodes/${name}/video`).catch(() => null);
}

// ---------------------------------------------------------------- 部品12 文字起こし（確定版）

function textsDirty() {
  return JSON.stringify(state.texts) !== state.textsSaved;
}

function transcriptSave() {
  const box = el("div", "segments-actions");
  const dirty = textsDirty();
  const badge = el("span", `save-badge ${dirty ? "is-dirty" : "is-saved"}`);
  badge.append(el("span", "mark"),
               document.createTextNode(dirty ? "未保存の変更あり" : "保存済み"));

  const save = el("button", `btn-save ${dirty ? "is-dirty" : "is-saved"}`,
                  dirty ? "保存する" : "保存");
  save.disabled = !dirty;
  save.onclick = () => saveTranscript();
  box.append(badge, save);
  return box;
}

function transcriptCard() {
  const card = el("div", "panel-card");
  const data = state.transcript || { state: "未実行", segments: [] };
  const running = state.job && state.job.state === "処理中"
    && state.job.episode === state.selected.name && state.job.step === "transcribe";

  card.appendChild(cleanPlayerRow());

  if (running) {
    card.appendChild(el("div", "lines-empty", "確定版の文字起こしを作っています…"));
    return card;
  }
  if (data.state !== "表示" || !data.segments.length) {
    card.appendChild(el("div", "lines-empty",
      "まだ確定版の文字起こしがありません。右上の「文字起こしを実行」を押すと作られます。"));
    return card;
  }

  const list = el("div", "tlines");
  data.segments.forEach((line, index) => {
    list.appendChild(transcriptRow(line, index));
  });
  card.appendChild(list);
  return card;
}

function transcriptRow(line, index) {
  const row = el("div", "tline");
  const now = state.listening === "clean" && state.at >= line.start && state.at < line.end;
  if (now) row.classList.add("is-now");
  if (state.editing === index) row.classList.add("is-editing");

  const at = el("button", "tline-at", clock(line.start));
  at.title = "ここから再生";
  at.onclick = () => listenTo("clean", line.start);
  row.appendChild(at);

  const body = el("div", "tline-body");
  const text = state.texts[index];
  const changed = text !== line.original;

  if (state.editing === index) {
    const box = el("textarea", "tline-edit");
    box.rows = 2;
    box.value = state.draft;
    box.oninput = () => { state.draft = box.value; };
    box.onkeydown = (event) => {
      if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); commitEdit(index); }
      if (event.key === "Escape") { state.editing = -1; renderMain(); }
    };
    body.appendChild(box);

    const tools = el("div", "tline-tools");
    const ok = el("button", "btn-tiny", "この行を確定");
    ok.onclick = () => commitEdit(index);
    const no = el("button", "btn-tiny is-plain", "やめる");
    no.onclick = () => { state.editing = -1; renderMain(); };
    const again = el("button", "btn-tiny is-quiet");
    again.innerHTML = icon(SVG.play, 11, 0) + "この行を聴き直す";
    again.querySelector("svg").setAttribute("fill", "currentColor");
    again.onclick = () => listenTo("clean", line.start);
    tools.append(ok, no, again, el("span", "tline-hint", "Enter で確定 · Esc でやめる"));
    body.appendChild(tools);
    setTimeout(() => { box.focus(); box.setSelectionRange(box.value.length, box.value.length); }, 0);
  } else {
    const show = el("button", "tline-text", text);
    show.title = "押すと書き換えられます";
    show.onclick = () => {
      state.editing = index;
      state.draft = state.texts[index];
      renderMain();
    };
    body.appendChild(show);
  }

  if (changed && state.showOrig[index]) {
    const orig = el("div", "tline-orig");
    const struck = el("s", null, line.original);
    orig.append(el("span", "label", "元"), struck);
    body.appendChild(orig);
  }
  row.appendChild(body);

  const markBox = el("div", "tline-mark");
  if (changed) {
    const mark = el("button", "btn-mark");
    mark.append(el("span", "mark"), document.createTextNode("直した"));
    mark.title = "元の文字起こしを見る";
    mark.onclick = () => {
      state.showOrig[index] = !state.showOrig[index];
      renderMain();
    };
    markBox.appendChild(mark);
  }
  row.appendChild(markBox);
  return row;
}

async function loadTranscript(name) {
  state.transcript = await api(`/api/episodes/${name}/transcript`).catch(() => null);
  state.texts = ((state.transcript && state.transcript.segments) || []).map((r) => r.text);
  state.textsSaved = JSON.stringify(state.texts);
  state.editing = -1;
  state.showOrig = {};
}

function commitEdit(index) {
  state.texts[index] = state.draft.trim();
  state.editing = -1;
  renderMain();
}

async function saveTranscript() {
  try {
    state.transcript = await api(`/api/episodes/${state.selected.name}/transcript`, {
      method: "PUT", body: JSON.stringify({ texts: state.texts }),
    });
    state.texts = state.transcript.segments.map((r) => r.text);
    state.textsSaved = JSON.stringify(state.texts);
    await reload({ keep: state.selected.name, keepSelected: true });
  } catch (err) {
    state.actionError = `文字起こしを保存できませんでした: ${err.message}`;
  }
  renderMain();
}

// 整音後の音を鳴らすプレーヤー（確定版の文字起こしは clean.wav が基準）
function cleanPlayerRow() {
  const box = el("div", "player");
  const total = (state.clean && state.clean.duration)
    || (state.transcript && state.transcript.duration) || 0;
  box.appendChild(cleanPlayer({ duration: total }));
  return box;
}

// ---------------------------------------------------------------- 部品15 整音結果パネル

// その工程がいま動いているか、直前に失敗・中止したか
function jobFor(step) {
  const job = state.job;
  if (!job || !state.selected) return null;
  if (job.episode !== state.selected.name || job.step !== step) return null;
  return job;
}

// パネルの中に出す「処理中」と「エラー・中止」（見本の部品15・19）
function jobBanner(step, label) {
  const job = jobFor(step);
  if (!job) return null;

  if (job.state === "処理中") {
    const box = el("div", "result");
    const top = el("div", "result-top");
    const badge = el("span", "badge-running");
    badge.append(el("span", "mark"),
                 document.createTextNode(`処理中 ${clock(job.elapsed)}`));
    const tail = (job.lines || []).filter((l) => l.trim()).slice(-1)[0] || "";
    const stop = el("button", "btn-plain", "中止");
    stop.onclick = () => cancelJob();
    top.append(badge, el("span", "result-about", tail), el("span", "spacer"), stop);
    box.append(top, el("div", "running-bar"));
    return box;
  }

  if (job.state === "エラー" || job.state === "中止") {
    const box = el("div", "result");
    const top = el("div", "result-top");
    const badge = el("span", "badge-failed");
    badge.append(el("span", "mark", "!"), document.createTextNode(job.state));
    const why = job.state === "中止" ? "結果は前のままです"
      : ((job.lines || []).filter((l) => l.trim()).slice(-1)[0] || "");
    const again = el("button", "btn-plain", "もう一度実行");
    again.onclick = () => runStep(step);
    top.append(badge, el("span", "result-about", why), el("span", "spacer"), again);
    box.appendChild(top);
    return box;
  }
  return null;
}

function cleanCard() {
  const card = el("div", "panel-card");
  const result = state.clean || { state: "未実行" };

  const banner = jobBanner("clean", "整音");
  if (banner) { card.appendChild(banner); if (result.state === "未実行") return card; }

  if (result.state === "未実行") {
    card.appendChild(el("div", "result-empty",
      "整音を実行すると、ここで聴いて確かめられます"));
    return card;
  }
  const stale = result.state === "古い";
  if (stale) card.classList.add("is-stale");

  const box = el("div", "result");
  const top = el("div", "result-top");

  const badge = el("span", stale ? "badge-stale"
    : result.confirmed ? "badge-done is-confirmed" : "badge-done");
  const mark = el("span", "mark");
  if (result.confirmed && !stale) {
    mark.innerHTML = icon(SVG.check, 11, 2.2, 10).replace('stroke="currentColor"', 'stroke="#fff"');
  }
  badge.append(mark, document.createTextNode(
    stale ? "古い" : result.confirmed ? "確認した" : "完了 · 未確認"));

  const about = ["clean.wav", clock(result.duration)];
  if (result.removed) about.push(`前後で ${result.removed.toFixed(1)}秒を削除`);
  if (result.target_lufs !== undefined && result.target_lufs !== null) {
    about.push(`目標 ${result.target_lufs} LUFS`);   // 実測ではない
  }
  if (result.echoes) about.push(`エコー${result.echoes}区間`);

  top.append(badge, el("span", "result-about", about.join(" · ")),
             el("span", "spacer"));
  if (stale) {
    const redo = el("button", "btn-primary");
    redo.innerHTML = icon(SVG.redo, 14) + "整音をやり直す";
    redo.onclick = () => runStep("clean");
    top.appendChild(redo);
  } else if (!result.confirmed) {
    // 確認済みになったらボタンは出さない（もう押す必要がない）
    const done = el("button", "btn-primary", "確認した");
    done.onclick = () => confirmClean();
    top.appendChild(done);
  }
  box.appendChild(top);

  if (stale) {
    const why = el("div", "result-stale");
    why.append(el("span", "mark", "!"), el("span", null,
      `${result.stale_reason}。整音をやり直すまで、次の工程には前の結果が使われます。`));
    box.appendChild(why);
  }

  // 波形は clean.wav から出す。いま聴いている音そのものなので、長さも形も合う
  const cw = ensureWave("clean", {
    url: `/api/episodes/${state.selected.name}/audio/clean?t=${result.at}`,
    duration: result.duration || 0,
    regions: true,          // エコーをかけた所を帯で見せる（動かせない）
  });
  syncRegions("clean", result.bands || [], false);
  syncWaveCover(cw);
  const wave = el("div", `result-wave ${stale ? "is-stale" : ""}`);
  wave.appendChild(cw.box);
  box.appendChild(wave);
  const note = waveNote(cw);
  if (note) box.appendChild(note);
  // エコーをかけたのに帯が出せないときは、そう言う。
  // 黙っていると「エコー無し」と見分けが付かない（#61）
  if (result.bands_error) {
    const why = el("div", "wave-note is-error");
    why.append(el("span", "mark", "!"), el("span", null, result.bands_error));
    box.appendChild(why);
  }
  // 斜線だけに頼らず、言葉でも言う（#65）
  if ((result.bands || []).length) {
    box.appendChild(el("div", "result-bands",
      "斜線の所にエコーがかかっています（ここでは動かせません。"
      + "変えるときは上の「エコー区間を決める」で直して、整音をやり直します）"));
  }

  box.appendChild(wavePlayer("clean"));
  card.appendChild(box);
  return card;
}

function cleanPlayer(result) {
  const total = result.duration || 0;
  const now = state.listening === "clean";
  return playerRow({
    total, at: now ? state.at : 0, playing: now && state.playing,
    label: "整音結果",
    onToggle: () => {
      if (now && state.playing) { audio.pause(); return; }
      listenTo("clean", now ? state.at : 0);
    },
    onSeek: (to) => listenTo("clean", to),
  });
}

// ---------------------------------------------------------------- ミックス結果パネル（#85 の4段目）
// 見た目は最低限（BGM・SE を画面で編集する部品は次の段。いまはコマンド／timeline.yml で置く）。

function mixCard() {
  const card = el("div", "panel-card");
  const result = state.mix || { state: "未実行" };
  const step = stepOf("mix");

  // timeline.yml が無い回は、ミックスが要らない（動画化は整音の音をそのまま使う）。
  // まだ実行していなくても、それが分かるようにする（2026-09-26 のレビューで指摘）
  if (step && step.state === "不要" && result.state === "未実行") {
    card.appendChild(el("div", "result-empty",
      "この回は timeline.yml が無いので、BGM・SE を重ねません。"
      + "動画化は整音の音（clean.wav）をそのまま使います（実行してもかまいません）。"));
    return card;
  }

  const banner = jobBanner("mix", "ミックス");
  if (banner) { card.appendChild(banner); if (result.state === "未実行") return card; }

  if (result.state === "未実行") {
    card.appendChild(el("div", "result-empty",
      "ミックスを実行すると、ここで聴いて確かめられます"));
    return card;
  }

  const stale = result.state === "古い";
  if (stale) card.classList.add("is-stale");

  const box = el("div", "result");
  const top = el("div", "result-top");
  const badge = el("span", stale ? "badge-stale" : "badge-done");
  badge.append(document.createTextNode(stale ? "古い" : "完了"));
  const about = ["mix.wav", clock(result.duration || 0),
                 `BGM ${result.bgm || 0}本`, `SE ${result.se || 0}本`];
  top.append(badge, el("span", "result-about", about.join(" · ")), el("span", "spacer"));
  if (stale) {
    const redo = el("button", "btn-primary");
    redo.innerHTML = icon(SVG.redo, 14) + "ミックスをやり直す";
    redo.onclick = () => runStep("mix");
    top.appendChild(redo);
  }
  box.appendChild(top);
  if (stale) {
    const why = el("div", "result-stale");
    why.append(el("span", "mark", "!"), el("span", null,
      `${result.stale_reason}。ミックスをやり直すまで、次の工程には前の結果が使われます。`));
    box.appendChild(why);
  }
  box.appendChild(mixPlayer(result));
  card.appendChild(box);
  return card;
}

function mixPlayer(result) {
  const total = result.duration || 0;
  const now = state.listening === "mix";
  return playerRow({
    total, at: now ? state.at : 0, playing: now && state.playing,
    label: "ミックス結果",
    onToggle: () => {
      if (now && state.playing) { audio.pause(); return; }
      listenTo("mix", now ? state.at : 0);
    },
    onSeek: (to) => listenTo("mix", to),
  });
}

function listenTo(kind, at) {
  stopVideo();
  stopWaves();                      // 音は1つだけ鳴らす
  const url = `/api/episodes/${state.selected.name}/audio/${kind}`;
  if (state.listening !== kind || !audio.src.includes(`/audio/${kind}`)) {
    state.listening = kind;
    audio.src = url;
  }
  audio.currentTime = at || 0;
  state.at = at || 0;
  audio.play().catch((err) => {
    state.actionError = `再生できませんでした: ${err.message}`;
    renderMain();
  });
}

async function confirmClean() {
  try {
    state.clean = await api(`/api/episodes/${state.selected.name}/clean/confirm`,
                            { method: "POST" });
  } catch (err) {
    state.actionError = `確認を記録できませんでした: ${err.message}`;
  }
  renderMain();
}

// ---------------------------------------------------------------- 波形の土台（wavesurfer.js）
// renderMain() は毎回 DOM を作り直すが、波形は音を読み直すと重い（10分の回で数十MB）。
// 器と本体は作り直さず、鳴らす音が変わったときだけ読み直す。
const waves = {};

const ECHO_MIN = 0.3;   // これより短い選択は区間にしない（build.py と同じ）

const WAVE_COLORS = {
  light: "oklch(0.65 0.18 45 / .26)",
  hall: "oklch(0.55 0.2 25 / .3)",
  none: "rgba(230, 211, 179, .18)",
};

// wavesurfer は波形を shadow DOM の中に描く。style.css はそこへ届かないので、
// 区間の帯の見た目だけはここに書いて、器ごとに差し込む。
// （--accent などの色は shadow の中にも受け継がれるので、そのまま使える）
const WAVE_CSS = `
[part~="region"] {
  /* wavesurfer が要素に border-left:none を直接書くので、ここは !important が要る */
  border-left: 1.5px solid var(--accent) !important;
  border-right: 1.5px solid var(--accent) !important;
  box-sizing: border-box;
  display: flex; align-items: flex-start; justify-content: center;
  cursor: grab;
}
[part~="region"]:active { cursor: grabbing; }
[part~="region"].is-hall { border-color: oklch(0.55 0.2 25) !important; }
[part~="region"].is-none { border-color: var(--wood-text) !important; }
[part~="region"].is-picked { box-shadow: inset 0 0 0 2px var(--cream); }
[part~="region-handle"] { border-color: var(--cream) !important; width: 8px !important; }
/* 見るだけの帯（整音結果）。掴めないので、その形に見せる（#65 案A）。
   斜線を重ねると、面の手ざわりが変わるので離れて見ても掴める帯と区別が付く。
   色と札はそのままなので、どのプリセットがかかったかは読める */
[part~="region"].is-fixed { cursor: default; }
[part~="region"].is-fixed [part~="region-handle"] { display: none; }
[part~="region"].is-fixed {
  background-image: repeating-linear-gradient(45deg,
    rgba(255, 250, 240, .30) 0 3px, transparent 3px 8px);
}
[part~="region"] .tag {
  margin-top: 4px; padding: 1px 7px; border-radius: 999px;
  background: var(--ink-deep); color: var(--cream-on-wood);
  font: 500 10px var(--mono); white-space: nowrap;
  pointer-events: none;
}
`;

function paintWave(w) {
  // 器の shadow DOM に、帯の見た目を1度だけ入れる
  try {
    const root = w.ws.getWrapper().getRootNode();
    if (!root || !root.appendChild || root.querySelector("style[data-okuradi]")) return;
    const style = document.createElement("style");
    style.dataset.okuradi = "wave";
    style.textContent = WAVE_CSS;
    root.appendChild(style);
  } catch (err) {
    // 見た目が付かないだけで、波形と区間は使える
    console.warn("波形の見た目を入れられませんでした", err);
  }
}

function waveOf(key) {
  if (!waves[key]) {
    waves[key] = {
      box: el("div", "wave"),   // この器は作り直さない
      ws: null, regions: null, url: null,
      phase: "空",              // 空 / 読み込み中 / 表示 / 失敗
      percent: 0, error: "",
      at: 0, playing: false, duration: 0,
      sig: null, applying: false,
      // 拡大縮小（#85 の6段目のレビュー・部品13 のカット用。タイムライン欄の
      // 拡大縮小と同じ考え方。null は「全体を見る」）
      pxPerSec: null, lastWidth: 0, scrollLeft: 0,
    };
  }
  return waves[key];
}

// 波形の音を止める。器が画面から消えても、本体は生きているので明示的に止める
function stopWaves(except) {
  for (const [key, w] of Object.entries(waves)) {
    if (key !== except && w.ws && w.playing) w.ws.pause();
  }
}

function stopVideo() {
  if (videoView.node && !videoView.node.paused) videoView.node.pause();
}

// 音は1つだけ鳴らす
function stopOtherSounds(except) {
  audio.pause();
  stopVideo();
  stopWaves(except);
}

function ensureWave(key, { url, duration = 0, regions = false, editable = false }) {
  const w = waveOf(key);
  if (w.url === url) return w;

  if (w.ws) { w.ws.destroy(); w.ws = null; w.regions = null; }
  w.box.innerHTML = "";
  Object.assign(w, { url, phase: "読み込み中", percent: 0, error: "",
                     at: 0, playing: false, duration, sig: null, applying: false,
                     // 音が変わったら、拡大縮小は「全体を見る」に戻す（器の幅は変わらないので残す）
                     pxPerSec: null, scrollLeft: 0 });

  // 部品が読めていないことを黙って隠さない。
  // regions.min.js は本体が無くても window.WaveSurfer を空で作るので、
  // 「ある/なし」ではなく create が使えるかで見る
  const lib = window.WaveSurfer;
  if (!lib || typeof lib.create !== "function") {
    w.phase = "失敗";
    w.error = "波形の部品（wavesurfer.js）が読み込めませんでした。"
            + "web/static/vendor/ にファイルがあるか確かめてください";
    return w;
  }

  const plugins = [];
  if (regions) {
    if (lib.Regions && typeof lib.Regions.create === "function") {
      w.regions = lib.Regions.create();
      plugins.push(w.regions);
    } else {
      w.error = "区間を選ぶ部品（regions.min.js）が読み込めませんでした。"
              + "波形は出ますが、ドラッグで区間を選べません";
    }
  }

  try {
    w.ws = lib.create({
      container: w.box,
      height: 120,
      waveColor: "#8a6f5c",
      progressColor: "#c98a5a",
      cursorColor: "#e8c39e",
      cursorWidth: 2,
      barWidth: 2, barGap: 1, barRadius: 1,
      normalize: true,
      url,
      plugins,
    });
  } catch (err) {
    // ここで投げると画面がまるごと消える。波形だけ諦めて、理由を出す
    w.ws = null;
    w.regions = null;
    w.phase = "失敗";
    w.error = `波形を作れませんでした: ${err.message}`;
    return w;
  }

  paintWave(w);

  w.ws.on("loading", (percent) => {
    // 読み込みのたびに画面を作り直すと重いので、5%ごとに出す
    if (Math.abs(percent - w.percent) < 5 && percent < 100) return;
    w.percent = percent;
    renderMain();
  });
  w.ws.on("ready", () => {
    w.phase = "表示";
    w.duration = w.ws.getDuration() || duration;
    // 帯は、描き直しのときに echoCard / cleanCard が入れ直す
    renderMain();
    // 器の幅は、renderMain() で画面に付いたあとでないと測れない（timelineView と同じ
    // 理由。#98）。1コマ待って、拡大縮小の目盛りに使う幅を控える
    setTimeout(() => { w.lastWidth = w.box.clientWidth || w.lastWidth || 800; }, 0);
  });
  w.ws.on("error", (err) => {
    w.phase = "失敗";
    w.error = `波形を作れませんでした: ${(err && err.message) || err}`;
    renderMain();
  });
  // 拡大しているときの横スクロール位置を控える（renderMain() のたびに器が画面から
  // 外れて 0 に戻るので、restoreWaveScroll() で戻すため。#98 と同じ理由）
  w.ws.on("scroll", (startTime, endTime, startPx) => { w.scrollLeft = startPx; });
  w.ws.on("timeupdate", (at) => {
    // カットを飛ばして聴くとき（#85 の6段目）。区間に入ったら終わりへ飛ぶだけの仮置き
    if (key === "cut" && state.cutSkip) {
      const hit = cutRows(state.cutFrame).find((c) => at >= c.start && at < c.end - 0.02);
      if (hit) { w.ws.setTime(hit.end); w.at = hit.end; return; }
    }
    // 毎コマ作り直すと重いので、1秒に4回まで
    if (Math.floor(at * 4) === Math.floor(w.at * 4)) { w.at = at; return; }
    w.at = at;
    if (state.tab === "2") renderMain();
  });
  w.ws.on("interaction", (at) => { w.at = at; renderMain(); });
  w.ws.on("play", () => { w.playing = true; renderMain(); });
  w.ws.on("pause", () => { w.playing = false; renderMain(); });
  w.ws.on("finish", () => { w.playing = false; w.at = 0; renderMain(); });

  if (w.regions && editable) {
    // 区間の並び先は key によって別（エコーは state.echoes、カットは state.cutsWork。#85 の6段目）
    if (key === "cut") bindCutRegions(key, w);
    else bindRegions(key, w);
  }
  return w;
}

function echoIndexOf(region) {
  const index = Number(String(region.id).replace("echo-", ""));
  return Number.isInteger(index) ? index : -1;
}

function bindRegions(key, w) {
  w.regions.enableDragSelection({ color: WAVE_COLORS.light });

  // ドラッグで選び終えたとき（enableDragSelection は離した時だけ知らせる）
  w.regions.on("region-created", (region) => {
    if (w.applying) return;                       // 自分で並べたものは見ない
    const start = round2(Math.min(region.start, region.end));
    const end = round2(Math.max(region.start, region.end));
    // ここですぐ消すと、wavesurfer が後から付ける後始末と行き違って帯が残る。
    // 1コマ待ってから、state.echoes をもとに並べ直す
    setTimeout(() => {
      region.remove();
      if (end - start < ECHO_MIN) {
        seekWave(key, start);
        return;
      }
      state.echoes.push({ start, end, preset: "light" });
      state.echoes.sort((a, b) => a.start - b.start);
      state.picked = state.echoes.findIndex((e) => e.start === start);
      w.sig = null;
      renderMain();
    }, 0);
  });

  // 端を掴んで伸ばした / まるごと動かしたとき
  w.regions.on("region-updated", (region) => {
    if (w.applying) return;
    const echo = state.echoes[echoIndexOf(region)];
    if (!echo) return;
    const start = round2(Math.min(region.start, region.end));
    const end = round2(Math.max(region.start, region.end));
    // 0.3秒より短い区間は build.py が読み飛ばす。黙って効かない区間を
    // 作らせず、元の長さに戻して理由を出す
    if (end - start < ECHO_MIN) {
      state.actionError = `エコー区間は ${ECHO_MIN}秒より短くできません`
        + "（短いと整音のときに読み飛ばされます）";
      w.sig = null;                 // 帯を元の位置に戻す
      renderMain();
      return;
    }
    echo.start = start;
    echo.end = end;
    state.echoes.sort((a, b) => a.start - b.start);
    state.picked = state.echoes.indexOf(echo);
    w.sig = null;
    renderMain();
  });

  w.regions.on("region-clicked", (region, event) => {
    event.stopPropagation();
    const index = echoIndexOf(region);
    if (index < 0) return;
    state.picked = index;
    renderMain();
  });
}

// 区間を、波形の上の帯に映す。
// rows は {start, end, preset} の並び。editable=false なら見るだけ（動かせない）
function syncRegions(key, rows, editable = false) {
  const w = waveOf(key);
  if (!w.regions || w.phase !== "表示") return;
  const picked = editable ? state.picked : -1;
  const sig = `${JSON.stringify(rows)}|${picked}`;
  if (sig === w.sig) return;

  w.applying = true;
  w.regions.clearRegions();
  rows.forEach((row, index) => {
    const tag = el("span", "tag", PRESETS[row.preset] || row.preset);
    const region = w.regions.addRegion({
      id: `echo-${index}`,
      start: row.start, end: row.end,
      drag: editable, resize: editable,
      color: WAVE_COLORS[row.preset] || WAVE_COLORS.light,
      content: tag,
    });
    region.element.classList.add(`is-${row.preset}`);
    if (!editable) region.element.classList.add("is-fixed");
    if (index === picked) region.element.classList.add("is-picked");
  });
  w.applying = false;
  w.sig = sig;
}

function toggleWave(key) {
  const w = waveOf(key);
  if (!w.ws || w.phase !== "表示") return;
  if (w.playing) { w.ws.pause(); return; }
  stopOtherSounds(key);
  w.ws.play().catch((err) => {
    state.actionError = `再生できませんでした: ${err.message}`;
    renderMain();
  });
}

function seekWave(key, seconds, play = false) {
  const w = waveOf(key);
  if (!w.ws || w.phase !== "表示") return;
  w.ws.setTime(seconds);
  w.at = seconds;
  if (play && !w.playing) {
    stopOtherSounds(key);
    w.ws.play().catch(() => {});
  }
  renderMain();
}

function wavePlayer(key) {
  const w = waveOf(key);
  return playerRow({
    total: w.duration, at: w.at, playing: w.playing,
    disabled: w.phase !== "表示",
    label: key === "clean" ? "整音結果" : key === "cut" ? "カット確認" : "波形",
    onToggle: () => toggleWave(key),
    onSeek: (to) => seekWave(key, to, true),
  });
}

// 読み込み中は、箱の中に重ねて出す（見本どおり）。
// 箱の外に小さい文字だけだと、真っ黒な箱が「壊れている」ように見える（#59）
function syncWaveCover(w) {
  const have = w.box.querySelector(".wave-cover");
  if (w.phase !== "読み込み中") {
    if (have) have.remove();
    return;
  }
  const text = w.percent
    ? `音を読み込んでいます… ${Math.round(w.percent)}%`
    : "音を読み込んでいます…";
  if (have) { have.querySelector(".wave-cover-text").textContent = text; return; }
  const cover = el("div", "wave-cover");
  cover.append(el("span", "wave-cover-mark"), el("span", "wave-cover-text", text));
  w.box.appendChild(cover);
}

// 失敗を必ず見せる（黙って空のままにしない）
function waveNote(w) {
  if (w.error) {
    const box = el("div", "wave-note is-error");
    box.append(el("span", "mark", "!"), el("span", null, w.error));
    return box;
  }
  return null;
}

// ---------------------------------------------------------------- 波形の拡大縮小
// カットの波形に付ける（#85 の6段目のレビュー・5段目「数字の欄と拡大の両方」に合わせる。
// lead の仮置き）。操作の形はタイムライン欄の拡大縮小（timelineView）と同じにそろえる

function waveFitPxPerSec(w) {
  const width = w.lastWidth || 800;
  if (!w.duration) return ZOOM_STEPS[0];
  return width / w.duration;
}

function waveZoomLevels(w) {
  const fit = waveFitPxPerSec(w);
  const steps = ZOOM_STEPS.filter((v) => v > fit * 1.02);   // 下限に近すぎる段は候補から外す
  return [fit, ...steps];
}

// 見ている中心（秒）。拡大縮小の前後で同じ位置を見せ続けるため（timelineCenterSeconds と同じ考え方）
function waveCenterSeconds(w) {
  const px = w.pxPerSec != null ? w.pxPerSec : waveFitPxPerSec(w);
  if (!px) return null;
  const width = w.lastWidth || 0;
  const left = w.scrollLeft || 0;
  return (left + width / 2) / px;
}

function waveRestoreCenter(w, seconds, pxPerSec) {
  if (seconds == null || !pxPerSec || !w.ws) return;
  const width = w.lastWidth || 0;
  const left = Math.max(0, seconds * pxPerSec - width / 2);
  w.scrollLeft = left;   // 控えは常にここで確定させる
  w.ws.setScroll(left);  // 画面に付いていればその場でも反映する。外れている途中なら
                          // restoreWaveScroll() が renderMain() の最後に反映する
}

// ＋／－／全体を見る、共通の操作
function setWaveZoom(key, pxPerSec) {
  const w = waveOf(key);
  if (!w.ws || w.phase !== "表示") return;   // 復号が終わる前は押せない
  w.lastWidth = w.box.clientWidth || w.lastWidth || 800;
  const center = waveCenterSeconds(w);
  try {
    w.ws.zoom(pxPerSec);
  } catch (err) {
    // 静かに諦めない（CLAUDE.md）
    console.warn("波形: 拡大縮小に失敗しました", err);
    state.actionError = `波形の拡大縮小に失敗しました: ${err.message}`;
    renderMain();
    return;
  }
  w.pxPerSec = pxPerSec;
  waveRestoreCenter(w, center, pxPerSec);
  renderMain();
}

// ボタン「－」「＋」「全体を見る」。タイムライン欄の zoomControls() と同じ形
function waveZoomControls(key) {
  const w = waveOf(key);
  const box = el("div", "timeline-zoom wave-zoom");
  const ready = w.phase === "表示";
  const levels = waveZoomLevels(w);
  const current = w.pxPerSec != null ? w.pxPerSec : levels[0];
  let idx = 0;
  levels.forEach((v, i) => { if (Math.abs(v - current) < Math.abs(levels[idx] - current)) idx = i; });

  const zoomOut = el("button", "btn-icon", "－");
  zoomOut.title = "縮小";
  zoomOut.setAttribute("aria-label", "波形を縮小");
  zoomOut.disabled = !ready || idx <= 0;
  zoomOut.onclick = () => setWaveZoom(key, levels[Math.max(0, idx - 1)]);

  const zoomIn = el("button", "btn-icon", "＋");
  zoomIn.title = "拡大";
  zoomIn.setAttribute("aria-label", "波形を拡大");
  zoomIn.disabled = !ready || idx >= levels.length - 1;
  zoomIn.onclick = () => setWaveZoom(key, levels[Math.min(levels.length - 1, idx + 1)]);

  const fit = el("button", "btn-tiny is-plain", "全体を見る");
  fit.disabled = !ready;
  fit.onclick = () => setWaveZoom(key, levels[0]);

  box.append(zoomOut, zoomIn, fit);
  if (!ready) box.appendChild(el("span", "timeline-zoom-note", "音の読み込みが終わると押せます"));
  return box;
}

// main.innerHTML = "" で器が画面から外れると scrollLeft が 0 に戻る（#98 と同じ理由）ので、
// renderMain() の最後で毎回戻す
function restoreWaveScroll(key) {
  const w = waves[key];
  if (!w || !w.ws || w.pxPerSec == null) return;
  w.ws.setScroll(w.scrollLeft || 0);
}

// ---------------------------------------------------------------- 部品13・14 波形とエコー区間

function echoDirty() {
  return JSON.stringify(state.echoes) !== state.echoesSaved;
}

function echoSave() {
  const box = el("div", "segments-actions");
  const dirty = echoDirty();

  const badge = el("span", `save-badge ${dirty ? "is-dirty" : "is-saved"}`);
  badge.append(el("span", "mark"),
               document.createTextNode(dirty ? "未保存の変更あり" : "保存済み"));

  const save = el("button", `btn-save ${dirty ? "is-dirty" : "is-saved"}`,
                  dirty ? "保存する" : "保存");
  save.disabled = !dirty;
  save.onclick = () => saveEchoes();

  box.append(badge, save);
  return box;
}

function echoCard() {
  const card = el("div", "panel-card");
  const wave = state.wave || { state: "未実行" };

  if (wave.state !== "表示") {
    card.appendChild(el("div", "wave-empty",
      wave.reason || "先に整音を1度実行すると、波形が出ます"));
    card.appendChild(regionList(0));
    return card;
  }

  // 整音をやり直したら読み直す（古い音を使い回さない）
  const w = ensureWave("echo", {
    url: `${wave.url}?t=${wave.at}`,
    duration: wave.duration,
    regions: true,
    editable: true,
  });
  syncRegions("echo", state.echoes, true);
  syncWaveCover(w);

  card.appendChild(w.box);
  const note = waveNote(w);
  if (note) card.appendChild(note);

  const ruler = el("div", "wave-ruler");
  const total = w.duration || wave.duration;
  for (let i = 0; i < 5; i += 1) {
    ruler.appendChild(el("span", null, clock(total * i / 4)));
  }
  // ほかのパネルは .player / .result が余白を持つが、ここは器が無い（#59）
  const pad = el("div", "wave-player");
  pad.appendChild(wavePlayer("echo"));
  card.append(ruler, pad, regionList(total));
  return card;
}

function round2(value) {
  return Math.round(value * 100) / 100;
}

function regionList(duration) {
  const box = el("div", "regions");

  const head = el("div", "region-head");
  head.append(el("span"), el("span", null, "開始 – 終了"), el("span", null, "プリセット"),
              el("span"), el("span"));
  box.appendChild(head);

  if (!state.echoes.length) {
    box.appendChild(el("div", "region-empty",
      duration ? "区間はまだありません。波形の上でドラッグして選びます。端を掴むと伸び縮みします。"
               : "区間はまだありません。"));
    return box;
  }

  state.echoes.forEach((echo, index) => {
    const row = el("div", "region");
    if (index === state.picked) row.classList.add("is-picked");
    row.onclick = () => { state.picked = index; seekWave("echo", echo.start, true); };

    row.appendChild(el("span", `region-swatch is-${echo.preset}`));
    row.appendChild(el("span", "region-range",
      `${clock(echo.start)} – ${clock(echo.end)}`));

    const preset = el("select", "field");
    for (const [key, label] of Object.entries(PRESETS)) {
      const option = el("option", null, label);
      option.value = key;
      if (key === echo.preset) option.selected = true;
      preset.appendChild(option);
    }
    preset.onclick = (event) => event.stopPropagation();
    preset.onchange = () => { echo.preset = preset.value; renderMain(); };
    row.appendChild(preset);

    const listen = el("button", "btn-preview");
    listen.innerHTML = icon(SVG.play, 12, 0) + (state.previewing === index ? "作成中" : "この区間を試聴");
    listen.querySelector("svg").setAttribute("fill", "currentColor");
    listen.disabled = state.previewing !== -1;
    listen.onclick = (event) => { event.stopPropagation(); previewEcho(index); };
    row.appendChild(listen);

    const remove = el("button", "btn-icon");
    remove.innerHTML = icon(SVG.trash);
    remove.title = "この区間を削除";
    remove.setAttribute("aria-label", "この区間を削除");
    remove.onclick = (event) => {
      event.stopPropagation();
      state.echoes.splice(index, 1);
      state.picked = -1;
      renderMain();
    };
    row.appendChild(remove);
    box.appendChild(row);
  });
  return box;
}

async function previewEcho(index) {
  const echo = state.echoes[index];
  state.previewing = index;
  renderMain();
  try {
    audio.pause();
    state.listening = "preview";
    audio.src = `/api/episodes/${state.selected.name}/echo-preview`
      + `?start=${echo.start}&end=${echo.end}&preset=${echo.preset}&t=${Date.now()}`;
    await audio.play();
  } catch (err) {
    state.actionError = `試聴できませんでした: ${err.message}`;
  }
  state.previewing = -1;
  renderMain();
}

async function saveEchoes() {
  try {
    const got = await api(`/api/episodes/${state.selected.name}/echoes`, {
      method: "PUT", body: JSON.stringify({ echoes: state.echoes }),
    });
    state.echoes = got.echoes;
    state.echoesSaved = JSON.stringify(got.echoes);
    // 区間を変えたら整音は「古い」になる。取り直さないとパネルが嘘をつく。
    // 取り直しそのものが失敗したときも黙らない（#61）
    try {
      state.clean = await api(`/api/episodes/${state.selected.name}/clean`);
    } catch (err) {
      state.actionError = "区間は保存しましたが、整音の状態を読み直せませんでした"
        + `（${err.message}）。画面を開き直してください`;
    }
  } catch (err) {
    state.actionError = `区間を保存できませんでした: ${err.message}`;
  }
  renderMain();
}

// ---------------------------------------------------------------- カット（言い直し）（#85 の6段目）
// コーナー（枠）を選ぶと、そのコーナーの生音（00_raw）の波形が下に出る。ドラッグで区間を選ぶ
// 操作は部品13（波形ビュー）を流用する（案A・2026-09-27・ユーザーの判断）。
// カットにプリセットは無く「消すだけ」（docs/features.md「決定3を取り下げた理由」の表）。
// カットの時刻は、そのクリップの生音の時刻（`docs/features.md`「時刻は2つ。混ぜない」）。
// 保存はエコー・BGM と同じ明示的な作法（「保存する」を押すまでサーバーへ送らない）。

const CUT_MIN = ECHO_MIN;   // これより短い選択は区間にしない。カット専用の決まりは`build.py`
                            // 側に無いが、エコーと同じ目安をそろえる（仮置き）

function cutFrameList() {
  return (state.frames && state.frames.frames) || [];
}

// 作業用のカット配列を、まだ無ければ枠の現在値（サーバー側）から作る。
// すでに触っている枠は、直しかけの中身をそのまま使う（枠を切り替えても消えない）
function ensureCutWork(frame) {
  if (!(frame.id in state.cutsWork)) {
    const rows = (frame.cuts || []).map((c) => ({ start: c.start, end: c.end }));
    state.cutsWork[frame.id] = rows;
    state.cutsSaved[frame.id] = JSON.stringify(rows);
  }
}

function cutRows(frameId) {
  return state.cutsWork[frameId] || [];
}

function cutDirty(frameId) {
  if (!frameId || !(frameId in state.cutsWork)) return false;
  return JSON.stringify(state.cutsWork[frameId]) !== state.cutsSaved[frameId];
}

// unsavedThings() から呼ぶ。いま選んでいる枠に関わらず、直したまま保存していない枠が
// 1つでもあれば拾う（枠を切り替えても直しかけを持ち越すため。#60 と同じ考え方）
function anyCutDirty() {
  return Object.keys(state.cutsWork).some((id) => cutDirty(id));
}

// 枠を差し替える・外すと、サーバー側のカットは空に戻る（#216）。古い作業中の直しを
// 持ち越さない（別の録音のカットには意味が無いため）
function forgetCutWork(frameId) {
  delete state.cutsWork[frameId];
  delete state.cutsSaved[frameId];
  if (state.cutFrame === frameId) {
    state.cutFrame = null;
    state.cutPicked = -1;
  }
  if (state.cutSeekPending && state.cutSeekPending.frameId === frameId) {
    state.cutSeekPending = null;
  }
}

function cutIndexOf(region) {
  const index = Number(String(region.id).replace("cut-", ""));
  return Number.isInteger(index) ? index : -1;
}

function bindCutRegions(key, w) {
  w.regions.enableDragSelection({ color: WAVE_COLORS.light });

  w.regions.on("region-created", (region) => {
    if (w.applying) return;
    const start = round2(Math.min(region.start, region.end));
    const end = round2(Math.max(region.start, region.end));
    setTimeout(() => {
      region.remove();
      if (end - start < CUT_MIN) {
        seekWave(key, start);
        return;
      }
      const rows = cutRows(state.cutFrame);
      rows.push({ start, end });
      rows.sort((a, b) => a.start - b.start);
      state.cutPicked = rows.findIndex((r) => r.start === start);
      w.sig = null;
      renderMain();
    }, 0);
  });

  w.regions.on("region-updated", (region) => {
    if (w.applying) return;
    const rows = cutRows(state.cutFrame);
    const row = rows[cutIndexOf(region)];
    if (!row) return;
    const start = round2(Math.min(region.start, region.end));
    const end = round2(Math.max(region.start, region.end));
    if (end - start < CUT_MIN) {
      state.actionError = `カット区間は ${CUT_MIN}秒より短くできません`;
      w.sig = null;
      renderMain();
      return;
    }
    row.start = start;
    row.end = end;
    rows.sort((a, b) => a.start - b.start);
    state.cutPicked = rows.indexOf(row);
    w.sig = null;
    renderMain();
  });

  w.regions.on("region-clicked", (region, event) => {
    event.stopPropagation();
    const index = cutIndexOf(region);
    if (index < 0) return;
    state.cutPicked = index;
    renderMain();
  });
}

// 区間を波形の上の帯に映す（部品13 の syncRegions と同じ考え方）。プリセットが無いので
// タグは付けない。エコーの state.picked / state.echoes とは混ざらないよう別に持つ
function syncCutRegions(key, rows) {
  const w = waveOf(key);
  if (!w.regions || w.phase !== "表示") return;
  const sig = `${JSON.stringify(rows)}|${state.cutPicked}`;
  if (sig === w.sig) return;

  w.applying = true;
  w.regions.clearRegions();
  rows.forEach((row, index) => {
    // 帯に「カット」の文字を出す（部品13 のエコーの帯のタグと同じ作り。#85 の6段目のレビュー）
    const tag = el("span", "tag", "カット");
    const region = w.regions.addRegion({
      id: `cut-${index}`,
      start: row.start, end: row.end,
      drag: true, resize: true,
      color: WAVE_COLORS.light,
      content: tag,
    });
    if (index === state.cutPicked) region.element.classList.add("is-picked");
  });
  w.applying = false;
  w.sig = sig;
}

// コーナーを選ぶタブ（音源が入っていない枠は押せない。押せない理由も言う）
function cutFrameTabs(frames) {
  const box = el("div", "tabs cut-frame-tabs");
  for (const frame of frames) {
    const usable = frame.state === "使える";
    const btn = el("button", `tab${frame.id === state.cutFrame ? " is-active" : ""}`, frame.label);
    btn.disabled = !usable;
    btn.title = usable ? "" : "先に「音源を入れる」でこのコーナーに音源を入れてください";
    btn.onclick = () => { state.cutFrame = frame.id; state.cutPicked = -1; renderMain(); };
    box.appendChild(btn);
  }
  return box;
}

function numberField(value, label, onCommit) {
  const wrap = el("span", "cut-number-wrap");
  const input = el("input", "field cut-number");
  input.type = "number";
  input.step = "0.01";
  input.min = "0";
  input.value = round2(value);
  input.setAttribute("aria-label", label);
  input.onclick = (event) => event.stopPropagation();
  input.onchange = () => onCommit(Number(input.value) || 0);
  wrap.append(input, el("span", "cut-number-unit", "秒"));
  return wrap;
}

// 数字の欄で直す（30分の回でもドラッグだけに頼らずに済むように。#85 の6段目・部品14 の一覧を流用）
function commitCutEdit(frameId, index, key, value) {
  const rows = cutRows(frameId);
  const row = rows[index];
  if (!row) return;
  const start = key === "start" ? round2(Math.max(0, value)) : row.start;
  const end = key === "end" ? round2(Math.max(0, value)) : row.end;
  if (end - start < CUT_MIN) {
    state.actionError = `カット区間は開始 < 終了・${CUT_MIN}秒以上にしてください`;
    renderMain();
    return;
  }
  row.start = start;
  row.end = end;
  rows.sort((a, b) => a.start - b.start);
  state.cutPicked = rows.indexOf(row);
  waveOf("cut").sig = null;   // 波形の帯も、数字の直しに合わせて描き直す
  renderMain();
}

function cutList(frameId, total) {
  const box = el("div", "cut-rows");

  // エコー区間の一覧（部品14）と同じ5列のグリッドにそろえる（開始・終了・長さ・空き・削除）。
  // 4つしか要素が無いと、削除ボタンが空きの1fr列に寄ってずれる（#85 の6段目のレビュー）
  const head = el("div", "cut-row-head");
  head.append(el("span", null, "開始"), el("span", null, "終了"), el("span", null, "長さ"),
              el("span"), el("span"));
  box.appendChild(head);

  const rows = cutRows(frameId);
  if (!rows.length) {
    box.appendChild(el("div", "region-empty",
      total ? "区間はまだありません。波形の上でドラッグして選びます。端を掴むと伸び縮みします。"
            : "区間はまだありません。"));
    return box;
  }

  rows.forEach((row, index) => {
    const line = el("div", `cut-row${index === state.cutPicked ? " is-picked" : ""}`);
    line.onclick = () => { state.cutPicked = index; seekWave("cut", row.start, true); };

    line.append(
      numberField(row.start, "カット区間の開始（秒）", (v) => commitCutEdit(frameId, index, "start", v)),
      numberField(row.end, "カット区間の終了（秒）", (v) => commitCutEdit(frameId, index, "end", v)),
      el("span", "region-range", clock(Math.max(0, row.end - row.start))),
      el("span"),
    );

    const remove = el("button", "btn-icon");
    remove.innerHTML = icon(SVG.trash);
    remove.title = "このカット区間を削除";
    remove.setAttribute("aria-label", "このカット区間を削除");
    remove.onclick = (event) => {
      event.stopPropagation();
      rows.splice(index, 1);
      state.cutPicked = -1;
      renderMain();
    };
    line.appendChild(remove);
    box.appendChild(line);
  });
  return box;
}

function cutCard() {
  const card = el("div", "panel-card");
  const frames = cutFrameList();
  const usable = frames.filter((f) => f.state === "使える");

  if (!usable.length) {
    card.appendChild(el("div", "wave-empty",
      "音源が入っている枠がありません。先に「音源を入れる」でコーナーに音源を入れてください。"));
    return card;
  }

  if (!state.cutFrame || !usable.some((f) => f.id === state.cutFrame)) {
    state.cutFrame = usable[0].id;
    state.cutPicked = -1;
  }
  card.appendChild(cutFrameTabs(frames));

  const frame = frames.find((f) => f.id === state.cutFrame);
  ensureCutWork(frame);

  const url = `/api/episodes/${state.selected.name}/timeline-source/main/${encodeURIComponent(frame.name)}`
    + `?t=${encodeURIComponent(frame.recorded_at || "")}`;
  const w = ensureWave("cut", { url, regions: true, editable: true });
  syncCutRegions("cut", cutRows(frame.id));
  syncWaveCover(w);

  // 下見の行の「カットへ」で来たとき（#85 の6段目のレビュー）。波形が読み込み中なら、
  // 読み終わってからの再描画（ensureWave の ready ハンドラ）で改めてここを通る
  if (state.cutSeekPending && state.cutSeekPending.frameId === frame.id && w.phase === "表示") {
    const { at } = state.cutSeekPending;
    // **w.at を先に控える。** wavesurfer の setTime() は同期で timeupdate を発火し、
    // ensureWave の timeupdate ハンドラが w.at との差を見て renderMain() を呼ぶ。
    // 順番を逆にすると、いまの render の途中で renderMain() が再入し、main に
    // section が二重に付く（実機で見つけた）
    w.at = at;
    w.ws.setTime(at);
    if (w.pxPerSec != null) waveRestoreCenter(w, at, w.pxPerSec);   // 拡大していれば見える位置へ
    state.cutSeekPending = null;
  }

  card.appendChild(w.box);
  const note = waveNote(w);
  if (note) card.appendChild(note);
  card.appendChild(waveZoomControls("cut"));

  const total = w.duration;
  const ruler = el("div", "wave-ruler");
  for (let i = 0; i < 5; i += 1) {
    ruler.appendChild(el("span", null, clock(total * i / 4)));
  }
  const pad = el("div", "wave-player");
  pad.appendChild(wavePlayer("cut"));

  // 「区間に入ったら終わりへ飛ぶ」程度の仮置き（lead の指示）。言い直しが消えたかを耳で確かめる用
  const skip = el("label", "cut-skip-toggle");
  const checkbox = el("input");
  checkbox.type = "checkbox";
  checkbox.checked = state.cutSkip;
  checkbox.onchange = () => { state.cutSkip = checkbox.checked; renderMain(); };
  skip.append(checkbox, document.createTextNode(
    "カットした所を飛ばして聴く（言い直しが消えたかを確かめる用。区間に入ったら終わりへ飛びます）"));

  // 保存の作法は部品14（エコー区間）と同じく、section() の見出し脇（right）に1つだけ置く
  card.append(ruler, pad, skip, cutList(frame.id, total));
  return card;
}

// 直したコーナー（枠）が複数あっても、「保存する」1回で全部保存する
// （#85 の6段目のレビュー。前は選んでいる枠しか保存されず、タブを切り替えて
// 直した分がそのままだと消えたように見えた）
function dirtyCutFrameIds() {
  return Object.keys(state.cutsWork).filter((id) => cutDirty(id));
}

function dirtyCutFrameLabel(frameId) {
  const frame = cutFrameList().find((f) => f.id === frameId);
  return (frame && frame.label) || frameId;
}

function cutSaveRow() {
  const box = el("div", "segments-actions");
  const dirty = anyCutDirty();
  const saving = state.cutSaving;

  const badge = el("span", `save-badge ${dirty ? "is-dirty" : "is-saved"}`);
  badge.append(el("span", "mark"),
               document.createTextNode(dirty ? "未保存の変更あり" : "保存済み"));

  const save = el("button", `btn-save ${dirty ? "is-dirty" : "is-saved"}`,
                  saving ? "保存しています…" : (dirty ? "保存する" : "保存"));
  save.disabled = !dirty || saving;
  save.onclick = () => saveAllCuts();

  box.append(badge, save);
  return box;
}

// 直した枠だけ、順に PUT で送る。**1件が失敗しても、残りは送り切る**（BGM の保存
// （saveBgm）と同じ扱い。失敗は id ごとに集めて、あとでまとめて出す）
async function saveAllCuts() {
  if (!anyCutDirty() || state.cutSaving) return;
  const name = state.selected.name;
  const dirtyIds = dirtyCutFrameIds();
  state.cutSaving = true;
  state.actionError = "";
  renderMain();

  const failed = [];
  let got = null;
  for (const frameId of dirtyIds) {
    const rows = cutRows(frameId).map((r) => ({ start: r.start, end: r.end }));
    try {
      got = await api(
        `/api/episodes/${name}/frames/${encodeURIComponent(frameId)}/cuts`,
        { method: "PUT", body: JSON.stringify({ cuts: rows }) },
      );
    } catch (err) {
      failed.push({ id: frameId, message: err.message });
    }
  }

  state.cutSaving = false;
  // 保存している間に別の回へ移っていたら、この画面（もう表示していない回のもの）には
  // 書き戻さない。**保存そのものは、ここまでで元の回に対して最後まで進めている**
  // （saveBgm と同じ用心）
  if (!state.selected || state.selected.name !== name) {
    if (failed.length) {
      console.warn("カットの保存で失敗がありましたが、すでに別の回へ移っていたため画面には出しません", failed);
    }
    return;
  }

  if (got) state.frames = got;
  // カットを変えると出来上がりの長さが変わる（タイムラインの位置・BGMの錨・「古い」の判定）。
  // 取り直さないとパネルが嘘をつく（#61 と同じ考え方）
  await loadTimeline(name);

  // 成功した枠だけ、作業中スナップショットを保存済みにそろえる。失敗した枠は
  // 未保存のまま画面に残す（黙って消えたように見せない。もう一度「保存する」で直せる）
  const failedIds = new Set(failed.map((f) => f.id));
  for (const frameId of dirtyIds) {
    if (failedIds.has(frameId)) continue;
    const saved = ((state.frames && state.frames.frames) || []).find((f) => f.id === frameId);
    const rows = ((saved && saved.cuts) || []).map((c) => ({ start: c.start, end: c.end }));
    state.cutsWork[frameId] = rows;
    state.cutsSaved[frameId] = JSON.stringify(rows);
  }

  if (failed.length) {
    const detail = failed.map((f) => `${dirtyCutFrameLabel(f.id)}（${f.message}）`).join("、");
    state.actionError = `カットを保存できませんでした: ${detail}。`
      + "直しは保存されていません（もう一度「保存する」を押してください）";
  }

  await reload({ keep: name, keepSelected: true });
  renderMain();
}

// ---------------------------------------------------------------- タイムライン（見るだけ・#85 の2段目）
// timeline.yml がある回だけ、収録〜整音の画面に「並びを確かめる」欄を足す。
// wavesurfer-multitrack（vendor/README.md）で本編・BGM・SEのクリップを1行ずつ並べる。
// **見るだけ**（ドラッグでの移動・保存は次の段）。再生ボタンも置かない
// （lib 側の初期化は音を鳴らさないので、静かなプレビューのまま）。
const timelineView = {
  box: el("div", "timeline-multitrack"),
  mt: null, phase: "空", error: "", sig: null, timeoutId: null,
  // 拡大縮小（#99・PR #239 のレビューで前に出した）。null は「全体を見る」（そのつど
  // 器の幅から計算し直す）。ユーザーが＋／－を押したら px/秒 の実数を持つ
  pxPerSec: null,
  // 直近に実際に測れた器の幅。render の途中（timelineView.box がまだ画面から
  // 外れている瞬間）は clientWidth が 0 になるため、その間はこれを使う
  lastWidth: 0,
  totalSeconds: 0,
  // 作り直す（destroy→create）の前後で、見ていた時刻を保つ（#98）
  pendingCenter: null,
  // 直近のスクロール位置（px）。**renderMain() は毎回 main.innerHTML = "" で
  // timelineView.box をいったん画面から外すので、その瞬間に scrollLeft が 0 に戻る**
  // （ブラウザの仕様。実機で確かめた。#98・PR #239 のレビュー）。これを控えておき、
  // render のたびに restoreTimelineScroll() で戻す。null なら戻さない（新しく作った
  // ばかりで、まだ位置が無い）
  scrollLeft: null,
  // setTrackStartPosition・setEnvelopePoints で部品を直接書き換えている間、
  // その通知（start-position-change・envelope-points-change）を自分の変更として
  // 拾い直さないためのフラグ
  applying: false,
};

const LANE_LABEL = { main: "本編", bgm: "BGM", se: "SE" };
const LANE_COLOR = { main: "#8a6f5c", bgm: "#5c7a8a", se: "#7a8a5c" };
const LANES = ["main", "bgm", "se"];

// 1トラック（wavesurfer-multitrack の1行）の高さ。CSS 側（.timeline-lane-label）
// にも同じ数を書かず、ここから値渡しする（#86 で決めた「同じレーンは1行へ重ねる」の
// 重ね幅と、見出しの高さを合わせるため。数を2か所に書き写すと片方だけ直っておかしくなる）
const TRACK_HEIGHT = 40;

// envelope（wavesurfer-multitrack）は、最初の点より前を volume 0 から、最後の点より後を
// volume 0 へ補間する（ソースの onTimeUpdate を読んで確認。2026-09-27・lead の指摘）。
// build.py の volume_expr は逆に「端の値のまま」なので、画面の試聴と実際のミックスが
// 食い違う（既定の [{15,1.0},{16,0.251}] だと、画面では 0〜15秒が無音からのフェードインに
// 聞こえる）。**画面で描く・鳴らす点にだけ、端に補助点を足してそろえる**（保存前提の
// timeline.yml の値は変えない。ユーザーが触ったときだけ、そのまま保存してよい）。
// volume が無い（null・空）クリップは envelope 自体を付けない（points=[] のまま envelope を
// 登録すると、点が無い間 onTimeUpdate が常に volume 0 を返し、無音のまま鳴らなくなるバグが
// あった。#85 の5段目で見つけた）
//
// **足した端の補助点は、保存の対象にしない。** ユーザーが動かしていない補助点まで
// state.bgm に取り込むと、数字の欄の点が2つ→4つに増えて見える（PR #239 の2回目レビュー・
// 🚨。前回「触ったら保存してよい」としたのは誤りだった）。onBgmEnvelope の
// stripUntouchedPadding が、動かされていない補助点だけを外す
function bgmEnvelopePoints(volume, duration) {
  if (!volume || !volume.length) return null;
  const pts = volume.map((p) => ({ time: p.time, volume: p.volume })).sort((a, b) => a.time - b.time);
  if (pts[0].time > 0.001) pts.unshift({ time: 0, volume: pts[0].volume });
  if (duration != null && pts[pts.length - 1].time < duration - 0.001) {
    pts.push({ time: duration, volume: pts[pts.length - 1].volume });
  }
  return pts;
}

// onBgmEnvelope が受け取る points から、bgmEnvelopePoints が足しただけで
// ユーザーが動かしていない先頭・末尾の補助点を外す（PR #239 の2回目レビュー・🚨）。
// 「動かしていない」＝時刻も音量も、足したときの値のまま。どちらかが変わっていたら
// （フェードインを作る、など）本物の点として残す。点の数そのものが変わっていたら
// （追加・削除が起きていたら）判定がずれるので、何もしない
function stripUntouchedPadding(points, savedVolume, duration) {
  const real = (savedVolume || []).map((p) => ({ time: round2(p.time), volume: round2(p.volume) }))
    .sort((a, b) => a.time - b.time);
  if (!real.length) return points;
  const hasStartPad = real[0].time > 0.001;
  const hasEndPad = duration != null && real[real.length - 1].time < duration - 0.001;
  const expectedLen = real.length + (hasStartPad ? 1 : 0) + (hasEndPad ? 1 : 0);
  if (points.length !== expectedLen) return points;

  let out = points;
  if (hasStartPad) {
    const p0 = out[0];
    const untouched = Math.abs(p0.time) < 0.005 && Math.abs(p0.volume - real[0].volume) < 0.005;
    if (untouched) out = out.slice(1);
  }
  if (hasEndPad) {
    const last = out[out.length - 1];
    const untouched = Math.abs(last.time - duration) < 0.005
      && Math.abs(last.volume - real[real.length - 1].volume) < 0.005;
    if (untouched) out = out.slice(0, -1);
  }
  return out;
}

function timelineTracks(lanes) {
  const tracks = [];
  for (const lane of LANES) {
    for (const clip of lanes[lane] || []) {
      // 位置が出せないクリップ（音源が無い・長さが読めない）は widget に混ぜず、
      // 上の理由のバナーだけで見せる（止めずに、そのクリップにだけ理由を付ける）
      if (clip.error || clip.start == null) continue;
      const track = {
        id: `${lane}-${clip.id}`,
        lane,
        url: clip.url,
        startPosition: clip.start,
        // BGM のクリップだけ、ドラッグで位置を合わせられる（#85 の5段目）。
        // 本編・SE はまだ動かせない（本編は edits・並びの話、SE は8段目）
        draggable: lane === "bgm",
        options: { waveColor: LANE_COLOR[lane], progressColor: LANE_COLOR[lane], height: TRACK_HEIGHT },
        markers: [{ time: 0, label: `${LANE_LABEL[lane]}: ${clip.id}`, color: "rgba(0,0,0,.35)" }],
      };
      // BGM の音量カーブは wavesurfer-multitrack の envelope 機能で描き、動かす
      // （#85 の5段目）。points の形は timeline.yml の volume と同じ（time 秒・volume 0〜1）で、
      // ソース（vendor/multitrack.min.js）を読んで確かめた（envelope-points-change で受け取る）。
      // volume が無い（null）クリップは envelope を付けない（次のコメント参照）
      if (lane === "bgm") {
        const points = bgmEnvelopePoints(clip.volume, clip.duration);
        if (points) track.envelope = points;
      }
      tracks.push(track);
    }
  }
  return tracks;
}

// 同じレーンのクリップを1行へ重ねる（#86 の決定）。
// ライブラリの描画は書き換えず、トラックの箱に負の margin-top を足すだけ
// （#86 で実機確認済みの方法）。高さは決め打ちにせず、実際に描かれた箱の高さを測る
// （TRACK_HEIGHT はあくまで指定値。ライブラリが余白などを足していないかは測って確かめる）。
// SE のクリップには最低幅を付ける（#86。全体表示だと1px未満になって掴めなくなるため）
function overlapLaneRows(mt, tracks) {
  const containers = (mt.rendering && mt.rendering.containers) || [];
  if (!tracks.length) return;
  if (containers.length < tracks.length) {
    // 静かに諦めない（CLAUDE.md）。トラックの箱が足りないと、以降は全部ずれて重ならない
    console.warn("タイムライン: multitrack のトラックの箱が足りません。重ねずに並びます",
                 { containers: containers.length, tracks: tracks.length });
  }
  let prevLane = null;
  tracks.forEach((track, index) => {
    const box = containers[index];
    if (!box) {
      console.warn(`タイムライン: ${track.id} の箱が見つかりません`);
      return;
    }
    if (track.lane === "se") box.classList.add("timeline-clip-se");
    if (track.lane === prevLane) {
      const height = box.getBoundingClientRect().height || TRACK_HEIGHT;
      box.style.marginTop = `-${height}px`;
    }
    prevLane = track.lane;
  });
}

// レーンの中でクリップの時間が重なっていないか（#86「重なりは止めずに注意を出す」）。
// 見た目でまったく分からなくなる（#86 で実機確認済み）ので、気づけるようにする
function laneOverlaps(clips) {
  const usable = (clips || [])
    .filter((c) => c.start != null && c.duration != null)
    .sort((a, b) => a.start - b.start);
  for (let i = 1; i < usable.length; i++) {
    if (usable[i].start < usable[i - 1].start + usable[i - 1].duration - 0.001) return true;
  }
  return false;
}

// 回を移る・タイムラインの無い回に移ったときに片付ける（AudioContext などを残さない）
function destroyTimelineMultitrack() {
  if (timelineView.timeoutId) { clearTimeout(timelineView.timeoutId); timelineView.timeoutId = null; }
  if (timelineView.mt) { timelineView.mt.destroy(); timelineView.mt = null; }
  timelineView.box.innerHTML = "";
  timelineView.phase = "空";
  timelineView.error = "";
  timelineView.sig = null;
  timelineView.pxPerSec = null;
  timelineView.lastWidth = 0;
  timelineView.pendingCenter = null;
  timelineView.scrollLeft = null;
}

// 部品に渡す tracks（id・url・startPosition）から、作り直しが要るかを見分ける印。
// envelope（音量カーブ）は含めない。数字の欄からの直しは setEnvelopePoints で
// その場に反映するので、作り直しの判定には使わない
function sigOfTracks(tracks) {
  return JSON.stringify(tracks.map((t) => [t.id, t.url, t.startPosition]));
}

function ensureTimelineMultitrack(lanes) {
  const tracks = timelineTracks(lanes);
  const sig = sigOfTracks(tracks);
  if (timelineView.sig === sig) return;
  timelineView.sig = sig;

  if (timelineView.mt) {
    // 作り直す前に、いま見ている時刻を控えておく（#98）。全体表示（拡大縮小なし）の
    // ときは pxPerSec が無いので、直近に測った幅から計算し直す
    timelineView.pendingCenter = timelineCenterSeconds();
    timelineView.mt.destroy();
    timelineView.mt = null;
    timelineView.scrollLeft = null;   // 古い widget の位置。新しい widget にはそのまま使えない
  }
  if (timelineView.timeoutId) { clearTimeout(timelineView.timeoutId); timelineView.timeoutId = null; }
  timelineView.box.innerHTML = "";
  timelineView.phase = "読み込み中";
  timelineView.error = "";

  if (!tracks.length) {
    timelineView.phase = "失敗";
    timelineView.error = "位置が出せるクリップがありません";
    return;
  }

  // multitrack は作るときに器の横幅（clientWidth）を1度だけ測って以後使い回す。
  // ここはまだ renderMain() が組み立てている途中で、器は画面に付いていない
  // （clientWidth が 0）ので、いま作ると波形の幅が0のまま固定される。
  // 1コマ待って、画面に付いてから作る
  setTimeout(() => buildTimelineMultitrack(sig, tracks), 0);
}

function buildTimelineMultitrack(sig, tracks) {
  if (timelineView.sig !== sig) return;   // 待っている間に並びが変わっていたら作らない

  // 部品が読めていないことを黙って隠さない（部品13 と同じ考え方）
  const lib = window.Multitrack;
  if (!lib || typeof lib.create !== "function") {
    timelineView.phase = "失敗";
    timelineView.error = "タイムラインの部品（multitrack.min.js）が読み込めませんでした。"
                        + "web/static/vendor/ にファイルがあるか確かめてください";
    renderMain();
    return;
  }

  // ここは1コマ待ったあと（renderMain が組み立て終わったあと）なので、器の幅が測れる。
  // 測れた値は、次に render の途中でしか呼べない場面（zoomControls など）のために控える
  timelineView.lastWidth = timelineView.box.clientWidth || timelineView.lastWidth || 800;
  const pxPerSec = timelineView.pxPerSec != null
    ? timelineView.pxPerSec : timelineFitPxPerSec(timelineView.totalSeconds);

  try {
    timelineView.mt = lib.create(tracks, {
      container: timelineView.box,
      cursorWidth: 2,
      cursorColor: "#e8c39e",
      minPxPerSec: pxPerSec,
      // trackBorderColor は付けない。ライブラリはトラックの間に2pxの仕切りを挟むので、
      // 同じレーンで重ねた分だけ隙間が積み重なってずれる（レーンの境目は左の見出しで示す）
    });
  } catch (err) {
    timelineView.phase = "失敗";
    timelineView.error = `タイムラインを作れませんでした: ${err.message}`;
    renderMain();
    return;
  }

  // ユーザーがマウス・ホイールで直接スクロールしたときも控えておく（ボタンでの
  // 拡大縮小だけでなく、素のドラッグでも renderMain() のたびに 0 へ戻らないように）
  const sc = timelineScrollEl();
  if (sc) sc.addEventListener("scroll", () => { timelineView.scrollLeft = sc.scrollLeft; });

  timelineView.mt.once("canplay", () => {
    if (timelineView.sig !== sig) return;
    overlapLaneRows(timelineView.mt, tracks);
    waitForTimelineReady(sig, timelineView.mt);
  });
  // BGM をドラッグした・音量の点を動かしたら、画面の作業用の並びに取り込む
  // （保存は「保存する」を押すまでしない。#85 の5段目・PR #239 のレビュー）。
  // この widget はここで作った回にしか出ていない（回を移ると destroyTimelineMultitrack が
  // 先に壊す）ので、そのつど state.selected.name を見ればよい
  timelineView.mt.on("start-position-change", ({ id, startPosition }) => onBgmDrag(id, startPosition));
  timelineView.mt.on("envelope-points-change", ({ id, points }) => onBgmEnvelope(id, points));
  armTimelineTimeout(sig);
}

// 読み込みが終わったことを知らせるイベントが来ないまま固まったら、待ち続けない。
// **段ごとに数え直す**（canplay まで / 全トラックの ready まで）。1つの15秒で2段をまかなうと、
// 長い回で実際には読めているのに「失敗」と出る（#212 のレビュー）
function armTimelineTimeout(sig) {
  if (timelineView.timeoutId) clearTimeout(timelineView.timeoutId);
  timelineView.timeoutId = setTimeout(() => {
    if (timelineView.sig !== sig || timelineView.phase !== "読み込み中") return;
    timelineView.phase = "失敗";
    timelineView.error = "音の読み込みに時間がかかっています。画面を開き直してください";
    renderMain();
  }, 15000);
}

// canplay はメタデータが読めた合図でしかなく、波形を描き終わった合図ではない
// （実尺に近い7本・最大45MBで確かめたところ、canplay の0.35秒後では7本中1本しか
// 描けていなかった。そろうまで8秒）。個々のトラックの内部 wavesurfer が出す
// "ready"（波形を描き終えた合図）が全部そろうまで、読み込み中の帯を残す
function waitForTimelineReady(sig, mt) {
  const wavesurfers = mt.wavesurfers || [];
  if (!wavesurfers.length) {
    console.warn("タイムライン: 個々の波形が見つかりません。描き終わりを待たずに表示します");
    finishTimelineLoad(sig);
    return;
  }
  armTimelineTimeout(sig);
  let remaining = wavesurfers.length;
  wavesurfers.forEach((ws) => {
    const done = () => {
      if (timelineView.sig !== sig) return;
      remaining -= 1;
      if (remaining <= 0) finishTimelineLoad(sig);
    };
    ws.once("ready", done);
    // 個別に失敗しても、ほかが描けているならそこまでは見せる（待ち続けない）
    ws.once("error", () => {
      console.warn("タイムライン: 波形を1つ描けませんでした");
      done();
    });
  });
}

function finishTimelineLoad(sig) {
  if (timelineView.sig !== sig) return;
  timelineView.phase = "表示";
  if (timelineView.timeoutId) { clearTimeout(timelineView.timeoutId); timelineView.timeoutId = null; }
  // 作り直す前に見ていた時刻があれば、描き終わってから戻す（#98）
  if (timelineView.pendingCenter != null) {
    const px = timelineView.pxPerSec != null
      ? timelineView.pxPerSec : timelineFitPxPerSec(timelineView.totalSeconds);
    timelineRestoreCenter(timelineView.pendingCenter, px);
    timelineView.pendingCenter = null;
  }
  renderMain();
}

// ---------------------------------------------------------------- 拡大縮小（#99・PR #239 のレビューで前に出した）
//
// wavesurfer-multitrack の zoom(pxPerSec) は命令だけで、ボタンもホイールも付いてこない
// （#99）。段階は #99 の表の4つ（0.64 / 2 / 10 / 20 px/秒）を目安にする。下限は決め打ちにせず、
// 全体が器に収まる倍率をそのつど計算する。上限は #99 でも決まっていないので、表の最大（20）にする
const ZOOM_STEPS = [0.64, 2, 10, 20];

function timelineFitPxPerSec(totalSeconds) {
  const width = timelineView.lastWidth || 800;
  if (!totalSeconds) return ZOOM_STEPS[0];
  return width / totalSeconds;
}

function timelineZoomLevels() {
  const fit = timelineFitPxPerSec(timelineView.totalSeconds);
  const steps = ZOOM_STEPS.filter((v) => v > fit * 1.02);   // 下限に近すぎる段は候補から外す
  return [fit, ...steps];
}

// multitrack が作る、横にスクロールする器（app.js からは見えない内部の div。
// vendor/multitrack.js を読んで確かめた。#98・#99）。timelineView.box の最初の子がそれにあたる
function timelineScrollEl() {
  return timelineView.box.firstElementChild || null;
}

// **DOM を直接読まない。** renderMain() は毎回 timelineView.box をいったん画面から
// 外すので（main.innerHTML = ""）、その瞬間は scrollLeft・clientWidth のどちらを読んでも
// 0 になる（実機で確かめた。#98 のレビューで気づいた）。代わりに、控えてある値
// （timelineView.scrollLeft・lastWidth）から計算する。ensureTimelineMultitrack が
// 作り直しの前に呼ぶのも、まさにこの「画面から外れた直後」なので、DOM 頼みだと壊れる
function timelineCenterSeconds() {
  const px = timelineView.pxPerSec != null
    ? timelineView.pxPerSec : timelineFitPxPerSec(timelineView.totalSeconds);
  if (!px) return null;
  const width = timelineView.lastWidth || 0;
  const left = timelineView.scrollLeft || 0;
  return (left + width / 2) / px;
}

function timelineRestoreCenter(seconds, pxPerSec) {
  if (seconds == null || !pxPerSec) return;
  const width = timelineView.lastWidth || 0;
  const left = Math.max(0, seconds * pxPerSec - width / 2);
  timelineView.scrollLeft = left;   // 控えは常にここで確定させる
  const sc = timelineScrollEl();
  // 画面に付いていれば、その場でも反映する。外れている途中なら、restoreTimelineScroll()
  // が render の最後（main へ付け直したあと）に反映する
  if (sc) sc.scrollLeft = left;
}

// renderMain() の最後に呼ぶ。timelineView.box は毎回いったん外れて付け直されるので、
// 付け直したあとで、控えてあるスクロール位置を戻す（#98 のレビューで見つけた不具合）。
// 拡大縮小のボタンを押していなくても、素のドラッグでスクロールした位置も対象になる
function restoreTimelineScroll() {
  if (timelineView.scrollLeft == null) return;
  const sc = timelineScrollEl();
  if (sc) sc.scrollLeft = timelineView.scrollLeft;
}

// ＋／－／全体を見る、共通の操作。#98（見ている時刻を保つ）もここでまとめて行う
function setTimelineZoom(pxPerSec) {
  if (!timelineView.mt || timelineView.phase !== "表示") return;   // 復号が終わる前は押せない（#99）
  const center = timelineCenterSeconds();
  try {
    timelineView.mt.zoom(pxPerSec);
  } catch (err) {
    // "No audio loaded" など。静かに諦めない（CLAUDE.md）
    console.warn("タイムライン: 拡大縮小に失敗しました", err);
    state.actionError = `タイムラインの拡大縮小に失敗しました: ${err.message}`;
    renderMain();
    return;
  }
  timelineView.pxPerSec = pxPerSec;
  timelineRestoreCenter(center, pxPerSec);
  renderMain();
}

// ボタン「＋」「－」「全体を見る」（仮置き。#99 の決めること1は着手時点でまだ決まっていない）
function zoomControls() {
  const box = el("div", "timeline-zoom");
  const ready = timelineView.phase === "表示";
  const levels = timelineZoomLevels();
  const current = timelineView.pxPerSec != null ? timelineView.pxPerSec : levels[0];
  let idx = 0;
  levels.forEach((v, i) => { if (Math.abs(v - current) < Math.abs(levels[idx] - current)) idx = i; });

  const zoomOut = el("button", "btn-icon", "－");
  zoomOut.title = "縮小";
  zoomOut.setAttribute("aria-label", "タイムラインを縮小");
  zoomOut.disabled = !ready || idx <= 0;
  zoomOut.onclick = () => setTimelineZoom(levels[Math.max(0, idx - 1)]);

  const zoomIn = el("button", "btn-icon", "＋");
  zoomIn.title = "拡大";
  zoomIn.setAttribute("aria-label", "タイムラインを拡大");
  zoomIn.disabled = !ready || idx >= levels.length - 1;
  zoomIn.onclick = () => setTimelineZoom(levels[Math.min(levels.length - 1, idx + 1)]);

  const fit = el("button", "btn-tiny is-plain", "全体を見る");
  fit.disabled = !ready;
  fit.onclick = () => setTimelineZoom(levels[0]);

  box.append(zoomOut, zoomIn, fit);
  if (!ready) box.appendChild(el("span", "timeline-zoom-note", "音の読み込みが終わると押せます"));
  return box;
}

// 読み込み中は、波形の箱の中に重ねて出す（部品13 の syncWaveCover と同じ作り。#59）。
// 描き終わるまで消えないよう、waitForTimelineReady がそろうまで phase は「読み込み中」のまま
function syncTimelineCover() {
  const have = timelineView.box.querySelector(".wave-cover");
  if (timelineView.phase !== "読み込み中") {
    if (have) have.remove();
    return;
  }
  const text = "音を読み込んでいます…";
  if (have) return;
  const cover = el("div", "wave-cover");
  cover.append(el("span", "wave-cover-mark"), el("span", "wave-cover-text", text));
  timelineView.box.appendChild(cover);
}

function timelineCard() {
  const tl = state.timeline;
  if (!tl || !tl.timeline) return null;   // timeline.yml が無い回では出さない

  const card = el("div", "panel-card");
  // BGM だけ、画面の作業用の並び（state.bgm。保存するまでサーバーへ送らない）に差し替える
  const lanes = currentLanes();

  for (const lane of LANES) {
    for (const clip of lanes[lane] || []) {
      if (!clip.error) continue;
      const note = el("div", "wave-note is-error");
      note.append(el("span", "mark", "!"),
                  el("span", null, `${LANE_LABEL[lane]} ${clip.id}: ${clip.error}`));
      card.appendChild(note);
    }
  }

  // レーンの中で時間が重なっていたら注意を出す（止めない。#86 の仮置き）
  const overlapping = LANES.filter((lane) => laneOverlaps(lanes[lane]));
  if (overlapping.length) {
    const note = el("div", "wave-note is-caution");
    note.append(el("span", "mark", "!"), el("span", null,
      `${overlapping.map((l) => LANE_LABEL[l]).join("・")}のクリップの時間が重なっています`
      + "（重なった下のクリップは掴めません。見た目でも判別できません）"));
    card.appendChild(note);
  }

  // 曲がコーナーの終わりを越えて、次のコーナーの下でも鳴り続けるか（build.py の mix と同じ
  // 判定・同じ文言。処理側は 01_mix のログに出す。#85 の5段目・PR #239 のレビュー）
  const mainDurations = bgmMainDurations(lanes);
  for (const clip of lanes.bgm || []) {
    const overrun = bgmOverrunNote(clip, mainDurations);
    if (!overrun) continue;
    const note = el("div", "wave-note is-caution");
    note.append(el("span", "mark", "!"), el("span", null, overrun));
    card.appendChild(note);
  }

  // クリップが1件も無い timeline.yml は、失敗ではなく空の状態として見せる
  // （部品13 の .wave-empty と同じ扱い）
  const totalClips = LANES.reduce((n, lane) => n + (lanes[lane] || []).length, 0);
  if (!totalClips) {
    destroyTimelineMultitrack();
    card.appendChild(el("div", "wave-empty", "まだクリップがありません"));
    card.appendChild(bgmAddForm(lanes));
    return card;
  }

  // 行の見出し（本編 / BGM / SE）。#86 の決定で同じレーンは1行に重ねるので、
  // クリップが1件でもあるレーンの分だけ、その順で並べる（仮置きの見た目）
  const laneRow = el("div", "timeline-row");
  const shown = LANES.filter((lane) => (lanes[lane] || []).some((c) => c.start != null));
  if (shown.length) {
    const labels = el("div", "timeline-lane-labels");
    shown.forEach((lane) => {
      const label = el("div", "timeline-lane-label", LANE_LABEL[lane]);
      label.style.height = `${TRACK_HEIGHT}px`;
      labels.appendChild(label);
    });
    laneRow.appendChild(labels);
  }

  timelineView.totalSeconds = timelineTotalSeconds(lanes);
  ensureTimelineMultitrack(lanes);
  syncTimelineCover();
  laneRow.appendChild(timelineView.box);
  card.appendChild(laneRow);
  card.appendChild(zoomControls());

  if (timelineView.phase === "失敗") {
    const note = el("div", "wave-note is-error");
    note.append(el("span", "mark", "!"), el("span", null, timelineView.error));
    card.appendChild(note);
  }

  // BGM の一覧（数字で位置・音量を直す、削除）と「曲を置く」欄（#85 の5段目）
  card.appendChild(bgmSaveRow());
  const list = bgmList(lanes);
  if (list) card.appendChild(list);
  card.appendChild(bgmAddForm(lanes));

  return card;
}

// 番組全体の長さ（見えている範囲。main・bgm・se のうち、位置が出ているものの右端）。
// web/timeline.py の total_seconds と同じ考え方（#88）だが、ここは見るだけの計算で保存しない
function timelineTotalSeconds(lanes) {
  let total = 0;
  for (const lane of LANES) {
    for (const clip of lanes[lane] || []) {
      if (clip.start != null && clip.duration != null) total = Math.max(total, clip.start + clip.duration);
    }
  }
  return total;
}

// ---------------------------------------------------------------- BGM の行（#85 の5段目）
//
// 保存の作法はエコー区間（部品13・14）と同じにする（PR #239 のレビュー・ユーザーの判断・
// 案A）。ドラッグ・音量の点・数字の欄のどれで変えても、その場では保存しない。
// 画面はいったん state.bgm（作業用の並び）を直し、「保存する」を押したときだけ
// 変わったクリップだけ PUT で送る。回をまたいで混ざらないよう、debounce で待っている間に
// 別の回へ移ったら破棄する（commitBgmDrag が state.selected を見て確かめる）

// timeline.yml から読んだ「保存されている」形と、画面の作業用の形を行き来する。
// duration・error・url・start（サーバーが計算した値）はそのまま持ち回り、
// anchor・at・volume だけを画面で直す
function syncBgmFromTimeline() {
  const tl = state.timeline;
  const rows = (tl && tl.timeline && tl.timeline.lanes.bgm) || [];
  state.bgm = rows.map((c) => ({ ...c, volume: c.volume ? c.volume.map((p) => ({ ...p })) : c.volume }));
  state.bgmSaved = JSON.stringify(state.bgm.map(bgmEditableSnapshot));
}

// 保存する・しないの比較に使う形（id・anchor・at・volume だけ。丸めをそろえる）
function bgmEditableSnapshot(clip) {
  return {
    id: clip.id,
    anchor: clip.anchor,
    at: round2(clip.at || 0),
    volume: (clip.volume || []).map((p) => ({ time: round2(p.time), volume: round2(p.volume) })),
  };
}

function bgmDirty() {
  return JSON.stringify(state.bgm.map(bgmEditableSnapshot)) !== state.bgmSaved;
}

// 本編（main）の、番組内での開始秒。位置が出せているクリップだけ
function bgmMainStarts(lanes) {
  const map = {};
  for (const c of lanes.main || []) if (c.start != null) map[c.id] = c.start;
  return map;
}

// 本編（main）の長さ。#85 の5段目のレビューで足した「曲がコーナーの終わりを
// 越えて鳴り続ける」の判定に使う
function bgmMainDurations(lanes) {
  const map = {};
  for (const c of lanes.main || []) if (c.duration != null) map[c.id] = c.duration;
  return map;
}

// state.bgm（作業用）1件を、画面に出す形にする。start はここで計算し直す
// （サーバーから来た start は、保存されている anchor・at のときのもの。
// 画面で anchor・at を直したら、ここで計算し直さないと帯の位置が古いまま）
function bgmClipDisplay(clip, mainStarts) {
  if (clip.error) return { ...clip, start: null };
  const anchorStart = mainStarts[clip.anchor];
  if (anchorStart == null) {
    return { ...clip, start: null, error: `錨（${clip.anchor}）の位置が分かりません` };
  }
  return { ...clip, start: round2(anchorStart + (clip.at || 0)) };
}

// timelineCard・timelineTracks などに渡す、BGM だけ作業用に差し替えた並び
function currentLanes() {
  const tl = state.timeline;
  if (!tl || !tl.timeline) return null;
  const mainStarts = bgmMainStarts(tl.timeline.lanes);
  return {
    main: tl.timeline.lanes.main,
    se: tl.timeline.lanes.se,
    bgm: state.bgm.map((c) => bgmClipDisplay(c, mainStarts)),
  };
}

// build.py の _volume_at と同じ計算（#85 の4段目）。曲がコーナーの終わりを
// 越えて鳴り続けるかを画面でも見るために、同じ式を JS 側に持つ
function volumeAt(points, t) {
  if (!points || !points.length) return 1;
  const pts = [...points].sort((a, b) => a.time - b.time);
  if (t <= pts[0].time) return pts[0].volume;
  if (t >= pts[pts.length - 1].time) return pts[pts.length - 1].volume;
  for (let i = 1; i < pts.length; i += 1) {
    const p0 = pts[i - 1];
    const p1 = pts[i];
    if (p0.time <= t && t <= p1.time) {
      if (p1.time === p0.time) return p1.volume;
      return p0.volume + (p1.volume - p0.volume) * (t - p0.time) / (p1.time - p0.time);
    }
  }
  return pts[pts.length - 1].volume;
}

// build.py の mix と同じ判定・同じ文言（#85 の4段目のログと合わせる。処理側は
// 01_mix のログに出し、ここは画面にも出す。PR #239 のレビュー）
function bgmOverrunNote(clip, mainDurations) {
  if (clip.error || clip.duration == null) return null;
  const anchorTotal = mainDurations[clip.anchor];
  if (anchorTotal == null) return null;
  const covers = (clip.at || 0) + clip.duration;
  if (covers <= anchorTotal + 0.001) return null;
  const tEnd = anchorTotal - (clip.at || 0);
  if (volumeAt(clip.volume, tEnd) <= 0) return null;   // 音量の点で下げ切っているなら注意は不要
  return `${clip.id}: 曲がコーナーの終わり（${clock(anchorTotal)}）を`
       + `${clock(covers - anchorTotal)}越えて鳴ります。次のコーナーの下でも`
       + "鳴ります（音量の点で下げるか消してください）";
}

// dB ⇔ 倍率（timeline.yml の volume は0〜1の倍率）。0倍率は「無音」（-∞dB）として
// 別扱いする（#85 の5段目のレビュー）
function volumeToDb(volume) {
  return volume > 0 ? 20 * Math.log10(volume) : null;
}
function dbToVolume(db) {
  return Math.min(1, Math.max(0, 10 ** (db / 20)));
}

// 音量の点は time で昇順・重複なし（web/timeline.py の _volume と同じ決まり）。
// 数字の欄で自由に打たせると崩れうるので、保存の前に画面側でも整える
function normalizeVolumePoints(points) {
  const sorted = [...(points || [])].sort((a, b) => a.time - b.time);
  for (let i = 1; i < sorted.length; i += 1) {
    if (sorted[i].time <= sorted[i - 1].time) {
      sorted[i] = { ...sorted[i], time: round2(sorted[i - 1].time + 0.01) };
    }
  }
  return sorted;
}

// widget の中の、この BGM クリップのトラックの番号（0始まり）。setTrackStartPosition・
// setEnvelopePoints はこの番号で指す（vendor/multitrack.js を取り寄せて確かめた。
// multitrack.d.ts に載っている命令。#85 の5段目のレビュー）
function bgmTrackIndex(clipId) {
  if (!timelineView.mt || !Array.isArray(timelineView.mt.tracks)) return -1;
  return timelineView.mt.tracks.findIndex((t) => t.id === `bgm-${clipId}`);
}

// 数字の欄で位置を直したときは、作り直さずにその場で widget に反映する
// （作り直すと、実尺に近い回では数秒〜十数秒の復号待ちが起きる。#212）。
// 反映できたら true。できなければ（widget が無い・音源が無いなど）呼び出し側が
// 作り直しにフォールバックする
function bgmApplyPosition(clipId, newStart) {
  const idx = bgmTrackIndex(clipId);
  if (idx < 0) return false;
  timelineView.applying = true;
  try {
    timelineView.mt.setTrackStartPosition(idx, newStart);
  } finally {
    timelineView.applying = false;
  }
  const applied = timelineView.mt.tracks[idx];
  return !!applied && Math.abs((applied.startPosition || 0) - newStart) < 0.01;
}

// 数字の欄で音量の点を直したときの、その場への反映。**音量カーブの有無（envelope
// プラグインがあるかどうか）は widget を作った時にしか決まらない**ので、
// 「点が無かった曲に初めて点を足す」「最後の点を消して空にする」ときは
// その場では反映できず、呼び出し側で作り直しになる（頻度は低い操作）
function bgmApplyVolume(clipId, volume, duration) {
  const idx = bgmTrackIndex(clipId);
  if (idx < 0) return false;
  const track = timelineView.mt.tracks[idx];
  const hasEnvelope = !!(track && track.envelope);
  const points = bgmEnvelopePoints(volume, duration);
  if (!hasEnvelope || !points) return false;
  timelineView.applying = true;
  try {
    timelineView.mt.setEnvelopePoints(idx, points);
  } finally {
    timelineView.applying = false;
  }
  return true;
}

// 位置（anchor・at）を数字の欄から直す
function bgmCommitPosition(clipId, changes) {
  const clip = state.bgm.find((c) => c.id === clipId);
  if (!clip) return;
  Object.assign(clip, changes);
  clip.at = Math.max(0, round2(clip.at || 0));

  const lanes = currentLanes();
  let applied = false;
  if (lanes) {
    const mainStarts = bgmMainStarts(lanes);
    const display = bgmClipDisplay(clip, mainStarts);
    if (display.start != null) applied = bgmApplyPosition(clipId, display.start);
  }
  timelineView.sig = applied && lanes ? sigOfTracks(timelineTracks(lanes)) : null;
  renderMain();
}

// 音量の点を数字の欄から直す（追加・削除・時刻・dB のどれでもここを通す）
function bgmCommitVolume(clipId, points) {
  const clip = state.bgm.find((c) => c.id === clipId);
  if (!clip) return;
  clip.volume = normalizeVolumePoints(points);

  const lanes = currentLanes();
  const applied = lanes ? bgmApplyVolume(clipId, clip.volume, clip.duration) : false;
  if (!applied) timelineView.sig = null;   // 作り直す（envelope の有無が変わった、など）
  renderMain();
}

// ドラッグ・音量の点を動かしたあと、少し待ってから state.bgm に取り込む
// （連打のたびに取り込まない。CLAUDE.md）。widget 自体はすでに動かした見た目に
// なっているので、ここでは state.bgm と timelineView.sig を合わせるだけでよい
const bgmDragPending = {};

function scheduleBgmDragCommit(clipId, changes) {
  const name = state.selected && state.selected.name;
  const pending = bgmDragPending[clipId] || { changes: {}, name };
  pending.changes = { ...pending.changes, ...changes };
  pending.name = name;   // 待っている間に回を移ったら、最新の回で判定する
  clearTimeout(pending.timer);
  pending.timer = setTimeout(() => commitBgmDrag(clipId), 400);
  bgmDragPending[clipId] = pending;
}

function commitBgmDrag(clipId) {
  const pending = bgmDragPending[clipId];
  if (!pending) return;
  delete bgmDragPending[clipId];
  // 待っている間に別の回へ移っていたら、この widget はもう無い（回をまたいで
  // 混ざらないようにする。code-reviewer の指摘・PR #239 のレビュー）
  if (!state.selected || state.selected.name !== pending.name) return;
  const clip = state.bgm.find((c) => c.id === clipId);
  if (!clip) return;
  Object.assign(clip, pending.changes);
  const lanes = currentLanes();
  // widget はドラッグで既に正しい見た目になっているので、sig だけ合わせて
  // 無駄な作り直しを起こさない
  if (lanes) timelineView.sig = sigOfTracks(timelineTracks(lanes));
  renderMain();
}

// ドラッグの手離しは multitrack が知らせてくれない（動かすたびに来る）ので、
// scheduleBgmDragCommit の待ち時間で「離した」とみなす
function onBgmDrag(trackId, startPosition) {
  if (timelineView.applying || !trackId.startsWith("bgm-")) return;
  const clipId = trackId.slice("bgm-".length);
  const lanes = currentLanes();
  if (!lanes) return;
  const anchor = bgmAnchorForPosition(lanes.main, startPosition);
  if (!anchor) return;
  const at = Math.max(0, round2(startPosition - anchor.start));
  // 変わっていなければ取り込まない（widget を作り直しただけでも動く。#85 の5段目で気づいた）
  const clip = state.bgm.find((c) => c.id === clipId);
  if (clip && clip.anchor === anchor.id && Math.abs((clip.at || 0) - at) < 0.005) return;
  scheduleBgmDragCommit(clipId, { anchor: anchor.id, at });
}

// 新しい位置が入るコーナー（本編クリップ）を錨にする。無ければ最初のコーナーの頭に寄せる
// （lead の仮置き。at が負にならないようにする）
function bgmAnchorForPosition(mainClips, position) {
  const usable = (mainClips || []).filter((c) => c.start != null)
    .sort((a, b) => a.start - b.start);
  if (!usable.length) return null;
  let anchor = usable[0];
  for (const clip of usable) {
    if (clip.start <= position) anchor = clip;
    else break;
  }
  return anchor;
}

function bgmVolumeEqual(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  return a.every((p, i) => Math.abs(p.time - b[i].time) < 0.005 && Math.abs(p.volume - b[i].volume) < 0.005);
}

function onBgmEnvelope(trackId, points) {
  if (timelineView.applying || !trackId.startsWith("bgm-")) return;
  const clipId = trackId.slice("bgm-".length);
  // クリップ相対の秒はそのまま。volume は0〜1の倍率で、timeline.yml と同じ意味
  // （vendor/multitrack.min.js を読んで確かめた。#85 の5段目）
  const volume = points.map((p) => ({ time: round2(p.time), volume: round2(p.volume) }));
  // widget を作った直後にも1回この事象が起きる（もとの点を読み込むだけで発火する。
  // ライブラリの仕様）。**画面用に足した端の補助点（bgmEnvelopePoints）ぶんも含めて**、
  // いま state.bgm に持っている中身と同じなら、まだユーザーは触っていないので取り込まない
  const clip = state.bgm.find((c) => c.id === clipId);
  if (clip) {
    const expected = (bgmEnvelopePoints(clip.volume, clip.duration) || [])
      .map((p) => ({ time: round2(p.time), volume: round2(p.volume) }));
    if (bgmVolumeEqual(expected, volume)) return;
  }
  // 何かは変わったが、それが補助点そのものとは限らない。動かしていない補助点は
  // ここで外してから取り込む（PR #239 の2回目レビュー・🚨）
  const real = clip ? stripUntouchedPadding(volume, clip.volume, clip.duration) : volume;
  scheduleBgmDragCommit(clipId, { volume: normalizeVolumePoints(real) });
}

// 「保存する」ボタンと未保存の表示（部品14 のエコー区間と同じ見た目・作法）
function bgmSaveRow() {
  const box = el("div", "segments-actions bgm-save-row");
  const dirty = bgmDirty();

  const badge = el("span", `save-badge ${dirty ? "is-dirty" : "is-saved"}`);
  badge.append(el("span", "mark"),
               document.createTextNode(dirty ? "未保存の変更あり" : "保存済み"));

  const save = el("button", `btn-save ${dirty ? "is-dirty" : "is-saved"}`,
                  state.bgmSaving ? "保存しています…" : (dirty ? "保存する" : "保存"));
  save.disabled = !dirty || state.bgmSaving;
  save.onclick = () => saveBgm();

  box.append(badge, save);
  return box;
}

// 変わったクリップだけ PUT で送る。消した分だけ DELETE。窓口は既存のまま
// （PUT /bgm/{id}・DELETE /bgm/{id}。#85 の5段目のレビュー）
async function saveBgm() {
  if (!bgmDirty() || state.bgmSaving) return;
  const name = state.selected.name;
  state.bgmSaving = true;
  state.actionError = "";
  renderMain();

  const savedById = new Map(JSON.parse(state.bgmSaved || "[]").map((c) => [c.id, c]));
  // 読み直しで state.bgm が上書きされる前に、いまの直しを控えておく（失敗した分を戻すため）
  const pendingBgm = state.bgm.map((c) => ({ ...c, volume: c.volume ? c.volume.map((p) => ({ ...p })) : c.volume }));
  const currentIds = new Set(pendingBgm.map((c) => c.id));
  const removedIds = [...savedById.keys()].filter((id) => !currentIds.has(id));

  // **1件が失敗しても、残りは送り切る。** 失敗は id ごとに集めて、あとでまとめて出す
  // （PR #239 の2回目レビュー・🚨。前は最初の失敗で止まり、以降が1件も送られなかった）
  const failed = [];
  for (const id of removedIds) {
    try {
      await api(`/api/episodes/${name}/bgm/${encodeURIComponent(id)}`, { method: "DELETE" });
    } catch (err) {
      failed.push({ id, message: err.message });
    }
  }
  for (const clip of pendingBgm) {
    const before = savedById.get(clip.id);
    const now = bgmEditableSnapshot(clip);
    const changes = {};
    if (!before || before.anchor !== now.anchor) changes.anchor = now.anchor;
    if (!before || Math.abs(before.at - now.at) > 0.004) changes.at = now.at;
    if (!before || JSON.stringify(before.volume) !== JSON.stringify(now.volume)) {
      changes.volume = now.volume.length ? now.volume : null;
    }
    if (!Object.keys(changes).length) continue;
    try {
      await api(`/api/episodes/${name}/bgm/${encodeURIComponent(clip.id)}`, {
        method: "PUT", body: JSON.stringify(changes),
      });
    } catch (err) {
      failed.push({ id: clip.id, message: err.message });
    }
  }

  state.bgmSaving = false;
  // 保存している間に別の回へ移っていたら、この画面（もう表示していない回のもの）には
  // 書き戻さない。**保存そのものは、ここまでで元の回に対して最後まで進めている**
  // （commitBgmDrag と同じ用心。PR #239 の2回目レビュー・🚨）
  if (!state.selected || state.selected.name !== name) {
    if (failed.length) {
      console.warn("BGM の保存で失敗がありましたが、すでに別の回へ移っていたため画面には出しません", failed);
    }
    return;
  }

  await loadTimeline(name);
  syncBgmFromTimeline();

  // 失敗した分は、読み直した並びの上に、保存できなかった直しを載せ直す。
  // **黙って消えたように見せない**（保存できたのか、直しごと消えたのか区別が付かなくなる）。
  // 未保存のまま画面に残し、もう一度「保存する」を押せば直せる形にした（PR #239 の
  // 2回目レビュー・🚨。読み直しで消える案は採らなかった）
  if (failed.length) {
    const failedIds = new Set(failed.map((f) => f.id));
    const pendingById = new Map(pendingBgm.map((c) => [c.id, c]));
    const stillOnServer = new Set(state.bgm.map((c) => c.id));

    state.bgm = state.bgm.map((clip) => {
      if (!failedIds.has(clip.id)) return clip;
      const pending = pendingById.get(clip.id);
      if (!pending) return clip;   // 消すはずが消えていない（DELETE 失敗）方は下で扱う
      return { ...clip, anchor: pending.anchor, at: pending.at, volume: pending.volume };
    });

    // DELETE が失敗して、まだサーバーに残っているクリップは、画面でも「消すつもり」の
    // ままにする（読み直した並びにはまだ入っているので、もう一度外す）
    const stillWantRemoved = removedIds.filter((id) => failedIds.has(id) && stillOnServer.has(id));
    if (stillWantRemoved.length) {
      state.bgm = state.bgm.filter((c) => !stillWantRemoved.includes(c.id));
    }

    const detail = failed.map((f) => `${f.id}（${f.message}）`).join("、");
    state.actionError = `BGM を保存できませんでした: ${detail}。`
      + "直しは保存されていません（もう一度「保存する」を押してください）";
  }

  timelineView.sig = null;
  await reload({ keep: name, keepSelected: true });
}

// 位置（錨・頭からの秒）と音量の点の一覧（数字の欄。#85 の5段目のレビュー・案C）
function bgmPositionFields(clip, anchors) {
  const row = el("div", "bgm-row-pos");

  const anchorSelect = el("select", "field");
  anchors.forEach((c) => {
    const option = el("option", null, `${c.id}（${clock(c.start)}）`);
    option.value = c.id;
    if (c.id === clip.anchor) option.selected = true;
    anchorSelect.appendChild(option);
  });
  anchorSelect.setAttribute("aria-label", `${clip.id} を付けるコーナー`);
  anchorSelect.onchange = () => bgmCommitPosition(clip.id, { anchor: anchorSelect.value });

  const atInput = el("input", "field");
  atInput.type = "number";
  atInput.step = "0.1";
  atInput.min = "0";
  atInput.value = round2(clip.at || 0);
  atInput.setAttribute("aria-label", `${clip.id} の位置（コーナーの頭から何秒）`);
  atInput.onchange = () => bgmCommitPosition(clip.id, { at: Number(atInput.value) || 0 });

  row.append(
    field(el("span", "form-label", "どのコーナーに付けるか"), anchorSelect),
    field(el("span", "form-label", "コーナーの頭から何秒"), atInput),
    el("span", "bgm-row-where", clip.start != null ? `番組内では ${clock(clip.start)} から` : ""),
  );
  return row;
}

function bgmVolumePointRow(clip, points, index) {
  const point = points[index];
  const row = el("div", "bgm-volume-row");

  const timeInput = el("input", "field");
  timeInput.type = "number";
  timeInput.step = "0.1";
  timeInput.min = "0";
  timeInput.value = round2(point.time);
  timeInput.setAttribute("aria-label", `${clip.id} の音量の点 ${index + 1} の秒（曲の先頭から）`);
  timeInput.onchange = () => {
    const time = Math.max(0, Number(timeInput.value) || 0);
    bgmCommitVolume(clip.id, points.map((p, i) => (i === index ? { ...p, time } : p)));
  };

  const muted = point.volume <= 0;
  const dbInput = el("input", "field");
  dbInput.type = "number";
  dbInput.step = "0.5";
  dbInput.max = "0";
  dbInput.value = muted ? "" : round2(volumeToDb(point.volume));
  dbInput.placeholder = muted ? "無音" : "dB";
  dbInput.disabled = muted;
  dbInput.setAttribute("aria-label", `${clip.id} の音量の点 ${index + 1} の音量（dB）`);
  dbInput.onchange = () => {
    const db = Math.min(0, Number(dbInput.value) || 0);
    bgmCommitVolume(clip.id, points.map((p, i) => (i === index ? { ...p, volume: dbToVolume(db) } : p)));
  };

  const mute = el("button", "btn-tiny is-plain", muted ? "音を戻す" : "無音にする");
  mute.onclick = () => {
    const volume = muted ? dbToVolume(-6) : 0;   // 音を戻すときの既定は -6dB（仮置き。根拠は無い）
    bgmCommitVolume(clip.id, points.map((p, i) => (i === index ? { ...p, volume } : p)));
  };

  const remove = el("button", "btn-icon");
  remove.innerHTML = icon(SVG.trash);
  remove.title = "この点を削除";
  remove.setAttribute("aria-label", `${clip.id} の音量の点 ${index + 1} を削除`);
  remove.onclick = () => bgmCommitVolume(clip.id, points.filter((_, i) => i !== index));

  row.append(
    field(el("span", "form-label", "曲の先頭から何秒"), timeInput),
    field(el("span", "form-label", "音量"), dbInput),
    mute, remove,
  );
  return row;
}

function bgmVolumeEditor(clip) {
  const box = el("div", "bgm-volume");
  box.appendChild(el("div", "bgm-volume-label", "音量の点（曲の先頭から何秒・何dB）"));
  box.appendChild(el("div", "bgm-volume-hint",
    "点と点の間は直線でつながって変わります。ある秒までその音量を保ちたいときは、"
    + "手前にも同じ音量の点を置いてください"));
  const points = clip.volume || [];
  if (!points.length) box.appendChild(el("div", "region-empty", "点はまだありません。曲は等倍のまま鳴ります。"));
  points.forEach((_, index) => box.appendChild(bgmVolumePointRow(clip, points, index)));

  const add = el("button", "btn-add");
  add.innerHTML = icon(SVG.plus, 12, 2) + "点を追加";
  add.onclick = () => {
    const last = points[points.length - 1];
    const time = round2((last ? last.time : 0) + 1);
    bgmCommitVolume(clip.id, [...points, { time, volume: last ? last.volume : 1 }]);
  };
  box.appendChild(add);
  return box;
}

function bgmList(lanes) {
  const clips = lanes.bgm || [];
  if (!clips.length) return null;
  const anchors = (lanes.main || []).filter((c) => c.start != null);
  const box = el("div", "bgm-list");
  clips.forEach((clip) => {
    const row = el("div", `bgm-row${clip.error ? " is-error" : ""}`);

    const head = el("div", "bgm-row-head");
    head.appendChild(el("span", "bgm-row-id", clip.id));
    head.appendChild(el("span", "bgm-row-source", clip.source));
    if (clip.error) head.appendChild(el("span", "bgm-row-error", clip.error));

    const remove = el("button", "btn-icon");
    remove.innerHTML = icon(SVG.trash);
    remove.title = "この BGM を削除";
    remove.setAttribute("aria-label", `${clip.id} を削除`);
    remove.onclick = () => removeBgm(clip.id);
    head.appendChild(remove);
    row.appendChild(head);

    if (!clip.error) {
      row.appendChild(bgmPositionFields(clip, anchors));
      row.appendChild(bgmVolumeEditor(clip));
    }
    box.appendChild(row);
  });
  return box;
}

// 削除は、エコー区間の削除と同じくローカルだけ変える（保存するまでサーバーには送らない。
// #85 の5段目のレビュー・案A）。取り消しにくい操作の確認は「保存する」の時点でなく
// ここで出すほどではない（保存するまでは、画面を開き直せば元に戻る）
function removeBgm(clipId) {
  state.bgm = state.bgm.filter((c) => c.id !== clipId);
  timelineView.sig = null;   // 本数が変わるので作り直す（消す操作は頻度が低い）
  renderMain();
}

// 「曲を置く」欄。開くまでは小さいボタンだけ（#85 の5段目）
function bgmAddForm(lanes) {
  const box = el("div", "bgm-add");
  if (!state.bgmOpen) {
    const open = el("button", "btn-add");
    open.innerHTML = icon(SVG.plus, 13, 2) + "曲を置く";
    open.onclick = () => { state.bgmOpen = true; renderMain(); };
    box.appendChild(open);
    return box;
  }

  const close = el("button", "btn-icon");
  close.innerHTML = icon(SVG.close);
  close.title = "やめる";
  close.setAttribute("aria-label", "曲を置くのをやめる");
  close.onclick = () => { state.bgmOpen = false; renderMain(); };

  if (state.musicError) {
    box.appendChild(close);
    const note = el("div", "wave-note is-error");
    note.append(el("span", "mark", "!"),
      el("span", null, `曲の一覧を読み込めませんでした: ${state.musicError}`));
    box.appendChild(note);
    return box;
  }
  if (!state.music || !state.music.files.length) {
    box.appendChild(close);
    const note = el("div", "wave-note is-caution");
    note.append(el("span", "mark", "!"), el("span", null,
      `曲がありません。${(state.music && state.music.dir) || "assets/music/"} に置いてください`));
    box.appendChild(note);
    return box;
  }

  const anchors = (lanes.main || []).filter((c) => c.start != null);
  if (!anchors.length) {
    box.appendChild(close);
    box.appendChild(el("div", "wave-note is-caution",
      "本編の位置が出せないので、置く場所を選べません"));
    return box;
  }

  if (!state.bgmSource || !state.music.files.some((f) => f.source === state.bgmSource)) {
    state.bgmSource = state.music.files[0].source;
  }
  if (!state.bgmAnchor || !anchors.some((c) => c.id === state.bgmAnchor)) {
    state.bgmAnchor = anchors[0].id;
  }

  const musicSelect = el("select", "field");
  state.music.files.forEach((f) => {
    const option = el("option", null, `${f.name}（${f.duration}）`);
    option.value = f.source;
    musicSelect.appendChild(option);
  });
  musicSelect.value = state.bgmSource;
  musicSelect.onchange = () => { state.bgmSource = musicSelect.value; };

  const anchorSelect = el("select", "field");
  anchors.forEach((c) => {
    const option = el("option", null, `${c.id}（${clock(c.start)}）`);
    option.value = c.id;
    anchorSelect.appendChild(option);
  });
  anchorSelect.value = state.bgmAnchor;
  anchorSelect.onchange = () => { state.bgmAnchor = anchorSelect.value; };

  const busy = !!state.bgmBusy.new;
  const add = el("button", "btn-preview");
  add.textContent = busy ? "置いています…" : "この位置に置く";
  add.disabled = busy;
  add.onclick = () => addBgm();

  const row = el("div", "bgm-add-row");
  row.append(field(el("span", "form-label", "曲"), musicSelect),
             field(el("span", "form-label", "どのコーナーに付けるか"), anchorSelect),
             add, close);
  box.appendChild(row);
  return box;
}

// 「置く」は、いまも直接 POST する（保存するまでローカルに留める echo と違う扱い。
// #85 の5段目のレビュー・仮の判断）。曲の既定の位置・音量カーブ（BGM_DEFAULT_AT・
// BGM_DEFAULT_VOLUME）と id の重複避け（_unique_bgm_id）はサーバー側にしかなく、
// `/api/assets/music` は曲の長さを「1:23」の文字でしか返さない（秒の数字ではない）ため、
// 画面だけでは同じ既定値を再現できない。曲を置いたら、それより前のドラッグ・数字の欄の
// 未保存の直しは読み直しで失われるので、未保存があれば先に確認する
async function addBgm() {
  if (bgmDirty() && !confirm("BGM の未保存の変更を破棄して、曲を置きますか？")) return;
  const name = state.selected.name;
  state.bgmBusy = { ...state.bgmBusy, new: true };
  state.actionError = "";
  renderMain();
  let failMessage = "";
  try {
    await api(`/api/episodes/${name}/bgm`, {
      method: "POST",
      body: JSON.stringify({ source: state.bgmSource, anchor: state.bgmAnchor }),
    });
  } catch (err) {
    failMessage = `曲を置けませんでした: ${err.message}`;
  }
  state.bgmBusy = { ...state.bgmBusy, new: false };
  // 置いている間に別の回へ移っていたら、この画面には書き戻さない（saveBgm・commitBgmDrag
  // と同じ用心。置く命令そのものは元の回に対して最後まで進めている。PR #239 の2回目レビュー・🚨）
  if (!state.selected || state.selected.name !== name) {
    if (failMessage) console.warn("曲を置けませんでしたが、すでに別の回へ移っていたため画面には出しません", failMessage);
    return;
  }
  state.actionError = failMessage;
  if (!failMessage) state.bgmOpen = false;
  await loadTimeline(name);
  syncBgmFromTimeline();
  timelineView.sig = null;
  await reload({ keep: name, keepSelected: true });
}

// ---------------------------------------------------------------- 部品11・12 下見

// 下見の行から、カット編集の該当コーナー・生音の時刻へ飛ぶ（案A・2026-09-27・ユーザーの判断）。
// 下見（scan.json）は全コーナーを繋いだ音の時刻、カットはコーナーの生音の時刻なので、
// 処理側が残す layout（[{id, start, end, keeps: [[生音の開始, 生音の終わり], ...]}, ...]）で変換する。
// layout が無い（古い下見・枠の無い回）ときは「カットへ」を出さない
function scanCutTarget(line) {
  const layout = state.scan && state.scan.layout;
  if (!Array.isArray(layout) || !layout.length) return null;
  const entry = layout.find((e) => line.start >= e.start && line.start < e.end);
  if (!entry) return null;
  const frame = cutFrameList().find((f) => f.id === entry.id);
  if (!frame || frame.state !== "使える") return null;   // 押しても飛べない枠は出さない
  const at = scanOffsetToRaw(entry, line.start - entry.start);
  if (at == null) return null;
  return { frameId: entry.id, at };
}

// つないだ音の中でのオフセット（そのコーナーの頭から何秒か）を、keeps（残した生音の区間の並び）
// に沿って生音の秒に直す。keeps を1つも持たない（記録が壊れている）ときは変換できない
function scanOffsetToRaw(entry, offset) {
  const keeps = entry.keeps || [];
  if (!keeps.length) return null;
  let acc = 0;
  for (const [rawStart, rawEnd] of keeps) {
    const len = Math.max(0, rawEnd - rawStart);
    if (offset <= acc + len + 0.001) return rawStart + Math.max(0, offset - acc);
    acc += len;
  }
  return keeps[keeps.length - 1][1];   // 端に寄せる
}

function goToCut(frameId, at) {
  state.cutFrame = frameId;
  state.cutPicked = -1;
  state.cutSeekPending = { frameId, at };
  renderMain();
}

function scanCard() {
  const card = el("div", "panel-card");
  const scan = state.scan || { state: "未実行", segments: [] };
  const running = state.job && state.job.state === "処理中"
    && state.job.episode === state.selected.name && state.job.step === "scan";

  card.appendChild(player(scan));

  if (running) {
    card.appendChild(el("div", "lines-empty", "下見の文字起こしを作っています…"));
    return card;
  }
  if (scan.state !== "表示" || !scan.segments.length) {
    card.appendChild(el("div", "lines-empty",
      "まだ下見がありません。右上の「下見を実行」を押すと作られます。"));
    return card;
  }

  const list = el("div", "lines");
  scan.segments.forEach((line) => {
    // 行の中に複数の押せるものを並べるので、外側はボタンにしない（ボタンの中にボタンは置けない）
    const row = el("div", "line");
    if (state.at >= line.start && state.at < line.end) row.classList.add("is-now");

    const seek = el("button", "line-seek");
    seek.append(el("span", "at", clock(line.start)), el("span", "say", line.text));
    seek.onclick = () => seekTo(line.start);
    row.appendChild(seek);

    const target = scanCutTarget(line);
    if (target) {
      const jump = el("button", "btn-tiny is-plain line-cut-jump", "カットへ");
      jump.title = "このコーナーのカット編集へ移動して、生音のこの位置へ";
      jump.onclick = () => goToCut(target.frameId, target.at);
      row.appendChild(jump);
    }

    list.appendChild(row);
  });
  card.appendChild(list);
  return card;
}

// 再生ボタン・シークバー・時刻。部品11（下見）と部品15（整音結果）で同じものを使う
function playerRow({ total, at, playing, disabled, onToggle, onSeek, label }) {
  const row = el("div", "player-row");

  const play = el("button", "btn-play");
  play.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">${
    playing ? SVG.pause : SVG.playBig}</svg>`;
  // どの音かを言う。画面では見出しで分かるが、読み上げやキーボードでは分からない（#59）
  const what = label || "";
  play.title = playing ? `${what}を停止` : `${what}を再生`;
  play.setAttribute("aria-label", play.title);
  play.disabled = !!disabled;
  play.onclick = onToggle;

  // キーボードでも動かせるようにする（矢印で5秒、Home/End で端へ）
  const seek = el("button", "seek");
  seek.type = "button";
  seek.setAttribute("role", "slider");
  seek.setAttribute("aria-label", what ? `${what}の再生位置` : "再生位置");
  seek.setAttribute("aria-valuemin", "0");
  seek.setAttribute("aria-valuemax", String(Math.round(total)));
  seek.setAttribute("aria-valuenow", String(Math.round(at)));
  seek.setAttribute("aria-valuetext", `${clock(at)} / ${clock(total)}`);
  seek.disabled = !!disabled || !total;

  const track = el("div", "seek-track");
  const ratio = total ? Math.min(at / total, 1) : 0;
  const fill = el("div", "seek-fill");
  fill.style.width = `${ratio * 100}%`;
  const knob = el("div", "seek-knob");
  knob.style.left = `${ratio * 100}%`;
  track.append(fill, knob);
  seek.appendChild(track);

  seek.onclick = (event) => {
    if (!total) return;
    const rect = track.getBoundingClientRect();
    onSeek(Math.max(0, Math.min((event.clientX - rect.left) / rect.width, 1)) * total);
  };
  seek.onkeydown = (event) => {
    if (!total) return;
    const step = event.shiftKey ? 30 : 5;
    const moves = {
      ArrowLeft: at - step, ArrowRight: at + step,
      ArrowDown: at - step, ArrowUp: at + step,
      Home: 0, End: total,
    };
    if (!(event.key in moves)) return;
    event.preventDefault();
    onSeek(Math.max(0, Math.min(moves[event.key], total)));
  };

  const time = el("span", "player-time");
  time.append(document.createTextNode(clock(at)),
              el("span", "total", ` / ${clock(total)}`));

  row.append(play, seek, time);
  return row;
}

function player(scan) {
  const box = el("div", "player");
  const total = (scan && scan.duration) || audio.duration || 0;
  box.appendChild(playerRow({
    total, at: state.at, playing: state.playing,
    disabled: !(state.source && state.source.state === "使える"), label: "下見",
    onToggle: () => togglePlay(),
    onSeek: (to) => seekTo(to),
  }));
  return box;
}

function ensureAudio() {
  const want = `/api/episodes/${state.selected.name}/audio/scan`;
  if (state.listening !== "scan" || !audio.src.includes("/audio/scan")) {
    state.listening = "scan";
    audio.src = want;
    state.at = 0;
  }
}

function togglePlay() {
  ensureAudio();
  if (state.playing) {
    audio.pause();
  } else {
    stopWaves();                    // 音は1つだけ鳴らす
    audio.play().catch((err) => {
      state.playing = false;
      state.actionError = `再生できませんでした: ${err.message}`;
      renderMain();
    });
  }
}

function seekTo(seconds) {
  ensureAudio();
  audio.currentTime = seconds;
  state.at = seconds;
  if (!state.playing) audio.play().catch(() => {});
  renderMain();
}

audio.addEventListener("play", () => { state.playing = true; renderMain(); });
audio.addEventListener("pause", () => { state.playing = false; renderMain(); });
audio.addEventListener("ended", () => { state.playing = false; state.at = 0; renderMain(); });
audio.addEventListener("timeupdate", () => {
  state.at = audio.currentTime;
  if (state.tab === "2") renderMain();
});

function sourceCard() {
  const info = state.source;
  const card = el("div", "source-card");
  const body = el("div", "body");
  body.append(el("div", "name", info.name));
  const about = [info.duration, info.kind, `録った日時 ${info.recorded_at}`].join(" · ");
  body.append(el("div", "about", about));

  const badge = el("span", "badge-ok");
  badge.append(el("span", "mark"), document.createTextNode("使える"));

  const replace = el("button", "btn-plain", "差し替える");
  replace.onclick = () => {
    if (confirm("いまの音源を差し替えますか？前の音源のファイルは消えます。")) {
      state.source = { state: "空" };
      state.actionError = "";
      renderMain();
    }
  };
  card.append(body, badge, replace);
  return card;
}

function sourceAdd() {
  const box = el("div", "source-add");
  box.appendChild(el("div", "source-add-title", "音源を追加"));

  const zone = el("div", "dropzone");
  zone.innerHTML = `<svg width="26" height="26" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="1.8">${SVG.upload}</svg>`;
  zone.append(el("div", "lead", state.sourceBusy ? "取り込んでいます…" : "ファイルをドロップ"),
              el("div", "kinds", ACCEPTED_TEXT));

  const picker = el("input");
  picker.type = "file";
  picker.accept = ".wav,.m4a,.mkv,.mp4,.mov,.flv";
  picker.hidden = true;
  picker.onchange = () => { if (picker.files[0]) uploadSource(picker.files[0]); };

  const pick = el("button", "btn-plain", "ファイルを選ぶ");
  pick.disabled = state.sourceBusy;
  pick.onclick = () => picker.click();
  zone.append(pick, picker);

  zone.ondragover = (e) => { e.preventDefault(); zone.classList.add("is-over"); };
  zone.ondragleave = () => zone.classList.remove("is-over");
  zone.ondrop = (e) => {
    e.preventDefault();
    zone.classList.remove("is-over");
    if (e.dataTransfer.files[0]) uploadSource(e.dataTransfer.files[0]);
  };
  box.append(zone, el("div", "or-line", "または"));

  const head = el("div", "obs-head");
  head.appendChild(el("span", "title", "OBSのフォルダから選ぶ"));
  const obs = state.obs || { state: "未設定", recordings: [] };
  if (obs.state === "ok") head.appendChild(el("span", "where", `${obs.dir} · 新しい順`));
  box.appendChild(head);

  if (obs.state === "ok" && obs.recordings.length) {
    const list = el("div", "obs-list");
    for (const rec of obs.recordings) {
      const row = el("button", "obs-row");
      row.disabled = state.sourceBusy;
      const body = el("div", "body");
      body.append(el("span", "name", rec.name),
                  el("span", "when", [rec.duration, rec.recorded_at].filter(Boolean).join(" · ")));
      row.append(el("span", "mark"), body);
      row.onclick = () => takeFromObs(rec.name);
      list.appendChild(row);
    }
    box.appendChild(list);
  } else {
    const why = {
      "未設定": "見張るフォルダが設定されていません。OBSの録画先を指定すると、新しい録画がここに並びます。",
      "見つかりません": `フォルダが見つかりません: ${obs.dir}`,
      "ok": "このフォルダに録画がありません。",
    }[obs.state];
    box.appendChild(el("div", "obs-empty", why));
    const set = el("button", "btn-plain", "フォルダを指定");
    set.onclick = () => openObsDialog();
    box.appendChild(set);
  }
  return box;
}

function openObsDialog() {
  const overlay = el("div", "overlay");
  const dialog = el("div", "dialog");
  const input = el("input", "field");
  input.value = (state.obs && state.obs.dir) || "";
  input.placeholder = "/mnt/c/Users/…/Videos";

  const error = el("div", "form-error");
  error.hidden = true;

  const cancel = el("button", "btn-plain", "キャンセル");
  cancel.onclick = () => overlay.remove();
  const save = el("button", "btn-primary", "保存");
  save.onclick = async () => {
    save.disabled = true;
    try {
      const got = await api("/api/settings", {
        method: "PUT", body: JSON.stringify({ obs_dir: input.value }),
      });
      state.obs = got.obs;
      overlay.remove();
      renderMain();
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
      save.disabled = false;
    }
  };

  dialog.appendChild(el("div", "dialog-title", "OBSの録画フォルダ"));
  dialog.appendChild(el("div", "segments-note",
    "Windows のフォルダは WSL から /mnt/c/… の形で指定します。"));
  dialog.append(field(el("span", "form-label", "フォルダ"), input), error);
  const foot = el("div", "dialog-foot");
  foot.append(cancel, save);
  dialog.appendChild(foot);
  overlay.appendChild(dialog);
  overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
  document.body.appendChild(overlay);
  input.focus();
}

async function uploadSource(file) {
  state.sourceBusy = true;
  state.actionError = "";
  renderMain();
  const form = new FormData();
  form.append("file", file);
  try {
    const res = await fetch(`/api/episodes/${state.selected.name}/source`,
                            { method: "POST", body: form });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || `${res.status}`);
    state.source = body;
  } catch (err) {
    state.actionError = err.message;
  }
  state.sourceBusy = false;
  await reload({ keep: state.selected.name, keepSelected: true });
  renderMain();
}

async function takeFromObs(name) {
  state.sourceBusy = true;
  state.actionError = "";
  renderMain();
  try {
    state.source = await api(`/api/episodes/${state.selected.name}/source/from-obs`, {
      method: "POST", body: JSON.stringify({ file: name }),
    });
  } catch (err) {
    state.actionError = err.message;
  }
  state.sourceBusy = false;
  await reload({ keep: state.selected.name, keepSelected: true });
  renderMain();
}

// ---------------------------------------------------------------- コーナーの枠に音源を入れる（#85 の3段目）
// config.yml の segments（コーナーの並び）から枠を先に並べ、各枠に音源を入れる（案B）。
// segments が空の回は、いまの1本の入口（sourceCard / sourceAdd）のまま（仮置き）。

function framesSection() {
  const box = el("div", "frames-list");
  const obs = state.obs || { state: "未設定" };
  if (obs.state !== "ok") {
    const head = el("div", "obs-head");
    head.appendChild(el("span", "title", obs.state === "見つかりません"
      ? `OBSのフォルダが見つかりません: ${obs.dir}`
      : "OBSの録画フォルダが未設定です"));
    const set = el("button", "btn-plain", "フォルダを指定");
    set.onclick = () => openObsDialog();
    head.appendChild(set);
    box.appendChild(head);
  }

  // どのコーナーにも当たらないクリップがある間は、枠の出し入れを止める
  // （案A・2026-09-26・ユーザーの判断。黙って timeline.yml から落とすと edits まで消えるため）。
  // 押せない理由は、OBS の注意と同じく枠の一覧より前に出す（#216 のレビュー）
  const orphans = state.frames.orphans || [];
  const blocked = orphans.length > 0;
  if (blocked) {
    box.appendChild(orphansSection(orphans));
  }

  for (const frame of state.frames.frames) {
    box.appendChild(frameRow(frame, blocked));
  }

  // 失敗は上の共通バナー（`errorBanner`）に出るので、ここでは重ねて出さない（#216 のレビュー）
  return box;
}

function orphansSection(orphans) {
  const row = el("div", "frame-row");
  row.appendChild(el("div", "frame-row-label", "どのコーナーにも当たらないクリップ"));
  const note = el("div", "wave-note is-caution");
  note.append(el("span", "mark", "!"), el("span", null,
    "コーナーを削除・並べ替えたときに残ったクリップです。ファイルは消していません。"
    + "このクリップがある間は、枠に入れる・外すができません。外すか、コーナーを戻してください。"));
  row.appendChild(note);
  for (const orphan of orphans) {
    row.appendChild(orphanCard(orphan));
  }
  return row;
}

// 枠と同じバッジ・エラーの見せ方にする（#216 のレビュー）
function orphanCard(orphan) {
  const busy = !!state.frameBusy[orphan.id];
  const onRemove = () => {
    if (confirm(`${orphan.name || orphan.id} を外しますか？（ファイルも消えます）`)) removeOrphan(orphan.id);
  };

  if (orphan.state !== "使える") {
    // エラー帯（.source-error）の中のボタンは、既存の作法（.save-error の中の
    // .btn-tiny.is-plain）にそろえる（#216 のレビュー）
    const remove = el("button", "btn-tiny is-plain", busy ? "処理中…" : "外す");
    remove.disabled = busy;
    remove.onclick = onRemove;
    const err = el("div", "source-error");
    err.append(el("span", "mark", "!"), el("span", null, orphan.error || "音源がありません"), remove);
    return err;
  }

  const remove = el("button", "btn-plain", busy ? "処理中…" : "外す");
  remove.disabled = busy;
  remove.onclick = onRemove;
  const card = el("div", "source-card");
  const body = el("div", "body");
  body.append(el("div", "name", orphan.name));
  const about = [orphan.duration, orphan.kind, `録った日時 ${orphan.recorded_at}`].join(" · ");
  body.append(el("div", "about", about));
  const badge = el("span", "badge-ok");
  badge.append(el("span", "mark"), document.createTextNode("使える"));
  card.append(body, badge, remove);
  return card;
}

function frameRow(frame, blocked) {
  const row = el("div", "frame-row");
  row.appendChild(el("div", "frame-row-label", frame.label));
  const busy = !!state.frameBusy[frame.id];
  if (frame.state === "使える") {
    row.appendChild(frameCard(frame, busy, blocked));
  } else if (frame.state === "エラー") {
    const err = el("div", "source-error");
    err.append(el("span", "mark", "!"), el("span", null, frame.error || "音源がありません"));
    row.appendChild(err);
    row.appendChild(frameAdd(frame, busy, blocked));
  } else {
    row.appendChild(frameAdd(frame, busy, blocked));
  }
  return row;
}

// 差し替える前の確認の文。部品10（収録ファイルカード）の差し替えと同じ形に、
// カットの件数を足す（差し替えると edits は空になるため。案A・2026-09-26・#216 のレビュー）
function replaceConfirmText(frame) {
  let msg = `${frame.label} の音源を差し替えますか？前の音源のファイルは消えます。`;
  if (frame.edits) msg += `\n前の録音のカットが${frame.edits}件あります。これも消えます。`;
  return msg;
}

// 空の枠・エラーの枠に入れる前の確認。**カットが残っている枠だけ**確認を挟む
// （「エラー」＝音源ファイルが見つからない枠でも、クリップ自体にカットが
// 残っていることがある。黙って入れ替えると気づかず消える。design・code のレビュー・#216）
function placeConfirmText(frame) {
  if (!frame.edits) return null;
  return `${frame.label} に音源を入れますか？`
    + `\n前の録音のカットが${frame.edits}件あります。これも消えます。`;
}

function frameCard(frame, busy, blocked) {
  const wrap = el("div", "frame-card-wrap");
  const card = el("div", "source-card");
  const body = el("div", "body");
  body.append(el("div", "name", frame.name));
  const about = [frame.duration, frame.kind, `録った日時 ${frame.recorded_at}`].join(" · ");
  body.append(el("div", "about", about));

  const badge = el("span", "badge-ok");
  badge.append(el("span", "mark"), document.createTextNode("使える"));

  const disabled = busy || blocked;
  const title = blocked ? "どのコーナーにも当たらないクリップを外してください" : "";
  const picker = el("input");
  picker.type = "file";
  picker.accept = ".wav,.m4a,.mkv,.mp4,.mov,.flv";
  picker.hidden = true;
  picker.onchange = () => { if (picker.files[0]) uploadFrame(frame.id, picker.files[0]); };

  const replace = el("button", "btn-plain", busy ? "処理中…" : "差し替える");
  replace.disabled = disabled;
  replace.title = title;
  replace.onclick = () => {
    if (confirm(replaceConfirmText(frame))) picker.click();
  };

  const remove = el("button", "btn-plain", "外す");
  remove.disabled = disabled;
  remove.title = title;
  remove.onclick = () => {
    if (confirm(`${frame.label} の音源を外しますか？（ファイルも消えます）`)) removeFrame(frame.id);
  };
  card.append(body, badge, replace, remove, picker);
  wrap.appendChild(card);
  // 埋まっている枠でも、OBS から選んで差し替えられるようにする（user のレビュー）
  wrap.appendChild(obsPicker(frame, busy, blocked, (name) => replaceConfirmText(frame)
    + `\n選ぶ録画: ${name}`));
  return wrap;
}

function frameAdd(frame, busy, blocked) {
  const box = el("div", "frame-add");
  const disabled = busy || blocked;
  const title = blocked ? "どのコーナーにも当たらないクリップを外してください" : "";

  const zone = el("div", "dropzone frame-dropzone");
  zone.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="1.8">${SVG.upload}</svg>`;
  zone.append(el("div", "lead", busy ? "取り込んでいます…" : "ファイルをドロップ"),
              el("div", "kinds", ACCEPTED_TEXT));

  // カットが残っている枠（音源ファイルが見つからない「エラー」の状態でも起こる）は、
  // 差し替えと同じ確認を挟む。無ければ確認なしでそのまま入れる（#216 のレビュー）
  const confirmPlace = () => {
    const msg = placeConfirmText(frame);
    return !msg || confirm(msg);
  };

  const picker = el("input");
  picker.type = "file";
  picker.accept = ".wav,.m4a,.mkv,.mp4,.mov,.flv";
  picker.hidden = true;
  picker.onchange = () => {
    if (picker.files[0] && confirmPlace()) uploadFrame(frame.id, picker.files[0]);
  };

  const pick = el("button", "btn-plain", "ファイルを選ぶ");
  pick.disabled = disabled;
  pick.title = title;
  pick.onclick = () => picker.click();
  zone.append(pick, picker);

  zone.ondragover = (e) => {
    e.preventDefault();
    if (!blocked) zone.classList.add("is-over");
  };
  zone.ondragleave = () => zone.classList.remove("is-over");
  zone.ondrop = (e) => {
    e.preventDefault();
    zone.classList.remove("is-over");
    if (blocked) return;
    if (e.dataTransfer.files[0] && confirmPlace()) uploadFrame(frame.id, e.dataTransfer.files[0]);
  };
  box.appendChild(zone);
  box.appendChild(obsPicker(frame, busy, blocked, (name) => {
    const msg = placeConfirmText(frame);
    return msg && `${msg}\n選ぶ録画: ${name}`;
  }));
  return box;
}

// 枠の OBS からの取り込み（空の枠・埋まっている枠のどちらでも使う。#216 のレビュー）。
// confirmText(recordingName) を渡すと、選んだときに確認を挟む（差し替えのとき）。
// 文言は部品9（音源の追加）の「OBSのフォルダから選ぶ」にそろえる。
function obsPicker(frame, busy, blocked, confirmText) {
  const box = el("div", "obs-inline");
  const obs = state.obs || { state: "未設定", recordings: [] };
  if (obs.state !== "ok") return box;

  const open = state.frameObsOpen === frame.id;
  const toggle = el("button", "btn-plain", open ? "閉じる" : "OBSのフォルダから選ぶ");
  // 一覧が開いたまま操作が止まっても、閉じるボタンは押せるようにする（user のレビュー）
  toggle.disabled = open ? false : (busy || blocked);
  toggle.title = open ? "" : (blocked
    ? "どのコーナーにも当たらないクリップを外してください" : "");
  toggle.onclick = () => {
    state.frameObsOpen = open ? null : frame.id;
    renderMain();
  };
  box.appendChild(toggle);
  if (!open) return box;

  if (obs.recordings.length) {
    const list = el("div", "obs-list");
    for (const rec of obs.recordings) {
      const row = el("button", "obs-row");
      row.disabled = busy || blocked;
      const rbody = el("div", "body");
      rbody.append(el("span", "name", rec.name),
                   el("span", "when", [rec.duration, rec.recorded_at].filter(Boolean).join(" · ")));
      row.append(el("span", "mark"), rbody);
      row.onclick = () => {
        // confirmText はカットが無ければ falsy を返す。そのときは確認しない（#216 のレビュー）
        const msg = confirmText && confirmText(rec.name);
        if (msg && !confirm(msg)) return;
        frameFromObs(frame.id, rec.name);
      };
      list.appendChild(row);
    }
    box.appendChild(list);
  } else {
    // 録画が0件のときも説明を出す（部品9 と同じ文言。#216 のレビュー）
    box.appendChild(el("div", "obs-empty", "このフォルダに録画がありません。"));
  }
  return box;
}

async function uploadFrame(frameId, file) {
  state.frameBusy = { ...state.frameBusy, [frameId]: true };
  state.actionError = "";
  renderMain();
  const form = new FormData();
  form.append("file", file);
  try {
    const res = await fetch(
      `/api/episodes/${state.selected.name}/frames/${encodeURIComponent(frameId)}`,
      { method: "POST", body: form },
    );
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || `${res.status}`);
    state.frames = body;
    // 差し替えるとサーバー側のカットは空に戻る（#216）。作業中の古い直しは持ち越さない
    forgetCutWork(frameId);
    await loadTimeline(state.selected.name);
  } catch (err) {
    state.actionError = err.message;
  }
  state.frameBusy = { ...state.frameBusy, [frameId]: false };
  await reload({ keep: state.selected.name, keepSelected: true });
  renderMain();
}

async function frameFromObs(frameId, name) {
  state.frameBusy = { ...state.frameBusy, [frameId]: true };
  state.actionError = "";
  state.frameObsOpen = null;
  renderMain();
  try {
    state.frames = await api(
      `/api/episodes/${state.selected.name}/frames/${encodeURIComponent(frameId)}/from-obs`,
      { method: "POST", body: JSON.stringify({ file: name }) },
    );
    // 差し替えるとサーバー側のカットは空に戻る（#216）。作業中の古い直しは持ち越さない
    forgetCutWork(frameId);
    await loadTimeline(state.selected.name);
  } catch (err) {
    state.actionError = err.message;
  }
  state.frameBusy = { ...state.frameBusy, [frameId]: false };
  await reload({ keep: state.selected.name, keepSelected: true });
  renderMain();
}

async function removeFrame(frameId) {
  state.frameBusy = { ...state.frameBusy, [frameId]: true };
  state.actionError = "";
  renderMain();
  try {
    state.frames = await api(
      `/api/episodes/${state.selected.name}/frames/${encodeURIComponent(frameId)}`,
      { method: "DELETE" },
    );
    // 外すと、その枠のカットはもう意味を持たない。作業中の古い直しは持ち越さない
    forgetCutWork(frameId);
    await loadTimeline(state.selected.name);
  } catch (err) {
    state.actionError = err.message;
  }
  state.frameBusy = { ...state.frameBusy, [frameId]: false };
  await reload({ keep: state.selected.name, keepSelected: true });
  renderMain();
}

async function removeOrphan(orphanId) {
  state.frameBusy = { ...state.frameBusy, [orphanId]: true };
  state.actionError = "";
  renderMain();
  try {
    state.frames = await api(
      `/api/episodes/${state.selected.name}/orphans/${encodeURIComponent(orphanId)}`,
      { method: "DELETE" },
    );
    await loadTimeline(state.selected.name);
  } catch (err) {
    state.actionError = err.message;
  }
  state.frameBusy = { ...state.frameBusy, [orphanId]: false };
  await reload({ keep: state.selected.name, keepSelected: true });
  renderMain();
}

// ---------------------------------------------------------------- 部品4 工程実行ボタン

function jobOf(step) {
  const job = state.job;
  if (!job || job.episode !== state.selected.name || job.step !== step.key) return null;
  return job;
}

function runsCard() {
  const box = el("div", "runs");
  const steps = state.selected.steps
    .filter((step) => STEPS_OF_TAB[state.tab].includes(step.key));

  const rest = {
    "2": "下見の文字起こし・波形・エコー区間は #6 の続きで入れます。",
    "3": "文字起こしの修正・メタデータの編集・動画のプレビューは #7 で入れます。",
  };
  box.appendChild(el("div", "segments-note", rest[state.tab]));

  for (const step of steps) {
    if (step.key === "source") continue;   // 音源は「実行」ではなく追加するもの（#6）
    box.appendChild(runRow(step));
  }
  return box;
}

function runRow(step) {
  const row = el("div", "run");
  const job = jobOf(step);
  const running = job && job.state === "処理中";
  const failed = job && (job.state === "エラー" || job.state === "中止");

  let look = "is-ready";
  let label = `${step.label}を実行`;
  let mark = SVG.play;
  let note = "";

  if (running) {
    look = "is-running"; label = "中止"; mark = null;
  } else if (failed) {
    look = "is-failed"; label = "もう一度実行";
  } else if (step.state === "未実行") {
    look = "is-todo"; note = step.reason || "";
  } else if (step.state === "完了") {
    look = "is-done"; label = "やり直す"; mark = SVG.redo;
  } else if (step.state === "古い") {
    note = "前の工程をやり直したので、作り直しが要ります";
  } else if (step.state === "不要") {
    // 「未実行」と違って押せない理由ではないので、ボタンは止めない（実行してもよい）
    look = "is-skip"; note = step.reason || "";
  }

  const button = el("button", `btn-run ${look}`);
  if (running) {
    button.append(el("span", "spinner"), document.createTextNode("中止"),
                  el("span", "elapsed", clock(job.elapsed)));
    button.onclick = () => cancelJob();
  } else {
    button.innerHTML = icon(mark, 14, mark === SVG.redo ? 1.8 : 0) + label;
    if (mark === SVG.play) button.querySelector("svg").setAttribute("fill", "currentColor");
    button.disabled = step.state === "未実行" || (state.job && state.job.state === "処理中");
    button.onclick = () => runStep(step.key);
  }

  row.appendChild(button);
  if (note) row.appendChild(el("div", "run-note", note));
  return row;
}

function clock(seconds) {
  const total = Math.floor(seconds || 0);
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

function errorBanner() {
  const box = el("div", "save-error");
  const close = el("button", "btn-tiny is-plain", "閉じる");
  close.onclick = () => { state.actionError = ""; renderMain(); };
  box.append(el("span", "mark", "!"), el("span", null, state.actionError),
             el("span", "spacer"), close);
  return box;
}

function placeholder(title, note) {
  const box = el("div", "placeholder");
  box.append(el("div", "placeholder-title", title), el("div", null, note));
  return box;
}

// ---------------------------------------------------------------- 部品8 コーナーの並び

function seriesSelect(value) {
  const select = el("select", "field");
  if (!value) {
    // 足したばかりの行。**選ばせる**（#106 の2番）
    const first = el("option", null, "選んでください");
    first.value = "";
    first.selected = true;
    select.appendChild(first);
  }
  for (const [key, rule] of Object.entries(state.series)) {
    const option = el("option", null, rule.label);
    option.value = key;
    if (key === value) option.selected = true;
    select.appendChild(option);
  }
  // その回だけで使っているコーナーも選べるようにしておく
  if (value && !state.series[value]) {
    const option = el("option", null, value);
    option.value = value;
    option.selected = true;
    select.appendChild(option);
  }
  return select;
}

function themeHint(series) {
  const rule = state.series[series];
  // ヒントが無いコーナーに「例: OSI参照モデルの7層」を出すと、
  // OP の欄に「今さら聞けない」用の例文が出る（#106 の1番）
  return (rule && rule.hint) || "このコーナーで何を喋るかを一言";
}

// 行の並びは変わる（消せる・足せる）ので、位置ではなく札で突き合わせる。
// 位置で比べると、1行目を消しただけで残りの行が「直した」ことになってしまう。
function resetRows(segments) {
  state.rowIds = segments.map((_, index) => index);
  state.savedRows = new Map(segments.map((segment, index) =>
    [index, { series: segment.series, theme: segment.theme }]));
  state.nextRowId = segments.length;
}

function isChanged(index) {
  const before = state.savedRows.get(state.rowIds[index]);
  if (!before) return true;   // 足したばかりの行
  const now = state.selected.segments[index];
  return before.series !== now.series || before.theme !== now.theme;
}

function saveBadge() {
  const kinds = {
    saved: ["is-saved", "保存済み"],
    dirty: ["is-dirty", "未保存の変更あり"],
    saving: ["is-saving", "保存中"],
    error: ["is-error", "保存できませんでした"],
  };
  const [cls, label] = kinds[state.save];
  const badge = el("span", `save-badge ${cls}`);
  badge.append(el("span", "mark"), document.createTextNode(label));
  return badge;
}

function segmentsCard() {
  const card = el("div", "segments-card");
  const segments = state.selected.segments;

  const heading = el("div", "segments-head");
  const titles = el("div");
  titles.append(el("div", "segments-title", "コーナーの並び"));
  const actions = el("div", "segments-actions");

  const labels = { saved: "保存", dirty: "保存する", saving: "保存中", error: "もう一度保存" };
  const saveButton = el("button", `btn-save is-${state.save}`, labels[state.save]);
  saveButton.disabled = state.save === "saved" || state.save === "saving";
  saveButton.onclick = () => saveSegments();

  actions.append(saveBadge(), saveButton);
  heading.append(titles, actions);
  card.appendChild(heading);

  if (state.save === "error") {
    const banner = el("div", "save-error");
    banner.append(el("span", "mark", "!"),
                  el("span", null, `${state.saveError}。入力した内容は残っています。`));
    card.appendChild(banner);
  }

  const list = el("div", "segment-list");
  if (state.save === "dirty" || state.save === "error") list.classList.add("is-dirty");
  if (state.save === "saving") list.classList.add("is-saving");

  const head = el("div", "segment-head");
  head.append(el("span"), el("span", null, "順"), el("span", null, "コーナー"),
              el("span", null, "テーマ"), el("span"));
  list.appendChild(head);

  const busy = state.save === "saving";

  segments.forEach((segment, index) => {
    const row = el("div", "segment");
    if (isChanged(index)) row.classList.add("is-changed");

    const select = seriesSelect(segment.series);
    select.disabled = busy;
    const theme = el("input", "field");
    theme.placeholder = themeHint(segment.series);
    theme.value = segment.theme || "";
    theme.disabled = busy;

    select.onchange = () => {
      segment.series = select.value;
      theme.placeholder = themeHint(segment.series);
      markDirty();
    };
    theme.oninput = () => { segment.theme = theme.value; markDirty(); };

    const remove = el("button", "btn-icon");
    remove.innerHTML = icon(SVG.trash);
    remove.title = "この行を削除";
    remove.setAttribute("aria-label", "この行を削除");
    remove.disabled = busy || segments.length <= 1;
    remove.onclick = () => {
      segments.splice(index, 1);
      state.rowIds.splice(index, 1);
      markDirty();
      renderMain();
    };

    const arrows = el("div", "segment-move");
    arrows.append(moveButton(index, -1, busy), moveButton(index, 1, busy));

    row.append(arrows, el("div", "segment-no", String(index + 1)), select, theme, remove);
    list.appendChild(row);
  });

  const add = el("button", "btn-add");
  add.innerHTML = icon(SVG.plus, 13, 2) + "コーナーを追加";
  add.disabled = busy;
  add.onclick = () => {
    // **初期値を空にする。** series_rules の先頭（OP）を入れていたので、
    // 足した行は全部「OP」から始まり、変え忘れると OP が並ぶ（#106 の2番）
    segments.push({ series: "", theme: "" });
    state.rowIds.push(state.nextRowId++);
    markDirty();
    renderMain();
  };
  list.appendChild(add);

  card.append(list, el("div", "segments-note",
    "コーナーの種類ごとにタイトルの型が決まっています。"
    + "タイトルはメタデータの工程で、この並びとテーマから作られます。"));

  // 同じコーナーが2つ以上あることを知らせる（#106 の2番）。**止めない**
  for (const note of state.selected.segment_notes || []) {
    const row = el("div", "copy-note");
    row.append(el("span", "mark", "i"), document.createTextNode(note));
    card.appendChild(row);
  }
  return card;
}

function moveButton(index, step, busy) {
  const segments = state.selected.segments;
  const up = step < 0;
  const button = el("button", "btn-move");
  button.innerHTML = icon(up ? SVG.up : SVG.down, 12, 2, 12);
  button.title = up ? "上へ" : "下へ";
  button.setAttribute("aria-label", up ? "上へ" : "下へ");
  button.disabled = busy || (up ? index === 0 : index === segments.length - 1);
  button.onclick = () => {
    const to = index + step;
    [segments[index], segments[to]] = [segments[to], segments[index]];
    // 札も一緒に動かす。そうしないと、直した行の印が別の行に付いてしまう
    [state.rowIds[index], state.rowIds[to]] = [state.rowIds[to], state.rowIds[index]];
    markDirty();
    renderMain();
  };
  return button;
}


function markDirty() {
  if (state.save !== "dirty") {
    state.save = "dirty";
    state.saveError = "";
    renderMain();
  }
}

async function saveSegments() {
  state.save = "saving";
  renderMain();
  try {
    const saved = await api(`/api/episodes/${state.selected.name}/segments`, {
      method: "PUT",
      body: JSON.stringify({ segments: state.selected.segments }),
    });
    state.selected = saved;
    resetRows(saved.segments);
    state.save = "saved";
    state.saveError = "";
    // コーナーを変えると枠（画面2）も変わるので、ここで取り直す
    // （`reload` は selectEpisode を呼ばないため、放っておくと枠が古いまま。#216 のレビュー）
    await loadFrames(saved.name);
    await loadTimeline(saved.name);
    await reload({ keep: saved.name, keepSelected: true });
  } catch (err) {
    state.save = "error";
    // 「保存できませんでした」はバッジが出すので、帯には理由だけ書く
    state.saveError = err.message;
    renderMain();
  }
}

// ---------------------------------------------------------------- 部品6 相談チャット

function renderChat() {
  const box = $("chat");
  document.querySelector(".cabinet").classList.toggle("has-chat", state.chatOpen);
  $("chat-toggle").classList.toggle("is-active", state.chatOpen);
  box.hidden = !state.chatOpen;
  if (!state.chatOpen) return;

  box.innerHTML = "";
  const data = state.chat || { reading: "…", messages: [] };

  const head = el("div", "chat-head");
  const close = el("button", "btn-x");
  close.innerHTML = icon(SVG.close);
  close.title = "閉じる";
  close.setAttribute("aria-label", "閉じる");
  close.onclick = () => toggleChat();
  head.append(el("div", "title", "相談"), close);

  const sub = el("div", "chat-sub");
  const what = el("span");
  what.append(document.createTextNode("読んでいるもの: "),
              el("strong", null, data.reading));
  const clear = el("button", null, "会話をリセット");
  clear.disabled = !data.messages.length;
  clear.onclick = () => resetChat();
  sub.append(what, clear);

  const body = el("div", "chat-body");
  if (data.stale) {
    const note = el("div", "chat-stale");
    note.append(el("span", "mark", "!"), el("span", null, data.stale));
    body.appendChild(note);
  }
  if (!data.messages.length) {
    body.appendChild(el("div", "chat-empty",
      "この回の文字起こしを読んだ Claude に聞けます。\n例:「オープニングが長い気がする。どこで切れそう？」"));
  }
  for (const line of data.messages) {
    body.appendChild(el("div", line.who === "あなた" ? "say-me" : "say-claude", line.text));
  }
  if (state.chatWaiting) {
    const wait = el("div", "say-waiting");
    wait.append(el("span", "dots"), document.createTextNode("考えています…"));
    body.appendChild(wait);
  }
  if (state.chatError) {
    const bad = el("div", "say-error");
    const again = el("button", "btn-tiny is-plain", "もう一度送る");
    again.onclick = () => sendChat();
    bad.append(el("span", "mark", "!"), el("span", null, state.chatError), again);
    body.appendChild(bad);
  }

  const foot = el("div", "chat-foot");
  const input = el("div", "chat-input");
  const text = el("textarea");
  text.rows = 2;
  text.placeholder = "この回について聞く";
  text.value = state.chatDraft;
  text.disabled = state.chatWaiting;
  text.oninput = () => { state.chatDraft = text.value; };
  text.onkeydown = (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      sendChat();
    }
  };
  const send = el("button", "btn-send");
  send.innerHTML = icon(SVG.send, 14, 2);
  send.title = "送信（Ctrl+Enter）";
  send.setAttribute("aria-label", "送信");
  send.disabled = state.chatWaiting || !state.chatDraft.trim();
  send.onclick = () => sendChat();
  input.append(text, send);

  const memo = el("button", "btn-memo");
  memo.innerHTML = icon(SVG.memo, 13) + "改善メモに残す";
  memo.disabled = !data.messages.length || state.chatWaiting;
  memo.title = data.messages.length ? "会話から Issue の下書きを作ります"
                                    : "先に相談してください";
  memo.onclick = () => openMemo();

  foot.append(input, memo);
  box.append(head, sub, body, foot);
  body.scrollTop = body.scrollHeight;
}

function toggleChat() {
  state.chatOpen = !state.chatOpen;
  if (state.chatOpen && !state.chat) loadChat();
  renderChat();
}

async function loadChat() {
  if (!state.selected) return;
  state.chat = await api(`/api/episodes/${state.selected.name}/chat`).catch(() => null);
  renderChat();
}

async function sendChat() {
  const question = state.chatDraft.trim();
  if (!question || state.chatWaiting) return;
  state.chatWaiting = true;
  state.chatError = "";
  state.chatDraft = "";
  // 送ったことがすぐ見えるように、先に画面へ足す
  if (state.chat) state.chat.messages = state.chat.messages.concat({ who: "あなた", text: question });
  renderChat();
  try {
    state.chat = await api(`/api/episodes/${state.selected.name}/chat`, {
      method: "POST", body: JSON.stringify({ question }),
    });
    state.chatError = "";
  } catch (err) {
    // 送った質問は消さない。理由もチャットの中に出す
    state.chatError = err.message;
    state.chatDraft = question;      // 打ち直さなくて済むように戻す
  }
  state.chatWaiting = false;
  renderChat();
}

async function resetChat() {
  if (!confirm("この回の会話をリセットしますか？")) return;
  try {
    state.chat = await api(`/api/episodes/${state.selected.name}/chat`, { method: "DELETE" });
  } catch (err) {
    state.actionError = err.message;
    renderMain();
  }
  renderChat();
}

// ---------------------------------------------------------------- 部品7 改善メモの下書き

function openMemo() {
  const overlay = el("div", "overlay");
  const dialog = el("div", "dialog is-wide");
  overlay.appendChild(dialog);
  const memo = { state: "作成中", title: "", body: "", url: "", error: "" };
  // 登録中は閉じさせない。閉じると結果が伝わらず、二重に登録しかねない
  const canClose = () => memo.state !== "登録中";
  overlay.onclick = (event) => {
    if (event.target === overlay && canClose()) overlay.remove();
  };
  document.body.appendChild(overlay);

  const draw = () => {
    dialog.innerHTML = "";
    const head = el("div", "memo-head");
    head.append(el("div", "dialog-title", "改善メモの下書き"),
                el("span", "memo-label", "ラベル: 改善メモ"));
    dialog.appendChild(head);
    dialog.appendChild(el("div", "segments-note",
      "公開リポジトリの Issue に出ます。人に見せたくないことは消してください。"));

    if (memo.state === "作成中") {
      const wait = el("div", "memo-waiting");
      wait.append(el("span", "spinner"), document.createTextNode("会話を要約しています"));
      dialog.appendChild(wait);
    } else if (memo.state === "登録済み") {
      const done = el("div", "memo-done");
      const link = el("a", null, memo.url || "Issue を開く");
      link.href = memo.url;
      link.target = "_blank";
      link.rel = "noopener";
      done.append(document.createTextNode("Issue に登録しました"), link);
      dialog.appendChild(done);
    } else {
      if (memo.error) dialog.appendChild(el("div", "form-error", memo.error));
      const busy = memo.state === "登録中";
      const title = el("input", "field");
      title.value = memo.title;
      title.disabled = busy;
      title.oninput = () => { memo.title = title.value; };
      const body = el("textarea", "memo-text");
      body.rows = 6;
      body.value = memo.body;
      body.disabled = busy;
      body.oninput = () => { memo.body = body.value; };
      dialog.append(field(el("span", "form-label", "タイトル"), title),
                    field(el("span", "form-label", "本文"), body));
    }

    const foot = el("div", "dialog-foot");
    const close = el("button", "btn-plain", memo.state === "登録済み" ? "閉じる" : "キャンセル");
    close.disabled = !canClose();
    close.onclick = () => { if (canClose()) overlay.remove(); };
    foot.appendChild(close);

    if (memo.state !== "登録済み") {
      const create = el("button", "btn-primary");
      if (memo.state === "登録中") {
        create.append(el("span", "spinner"), document.createTextNode("登録中"));
      } else {
        create.textContent = "Issueに登録";
      }
      create.disabled = memo.state !== "編集中" || !memo.title.trim();
      create.onclick = async () => {
        memo.state = "登録中"; memo.error = ""; draw();
        try {
          const got = await api(`/api/episodes/${state.selected.name}/memo`, {
            method: "POST",
            body: JSON.stringify({ title: memo.title, body: memo.body }),
          });
          memo.url = got.url;
          memo.state = "登録済み";
        } catch (err) {
          memo.error = err.message;
          memo.state = "編集中";
        }
        draw();
      };
      foot.appendChild(create);
    }
    dialog.appendChild(foot);
  };

  draw();
  api(`/api/episodes/${state.selected.name}/memo/draft`, { method: "POST" })
    .then((got) => {
      memo.title = got.title;
      memo.body = got.body;
      memo.state = "編集中";
      draw();
    })
    .catch((err) => {
      memo.error = err.message;
      memo.state = "編集中";
      draw();
    });
}

// ---------------------------------------------------------------- 部品5 処理状況バーとログ

const STATUS_LOOK = {
  "処理中": ["is-running", (j) => `${j.label} を処理中`],
  "完了": ["is-done", (j) => `${j.label} が完了しました`],
  "エラー": ["is-failed", (j) => `${j.label} でエラー`],
  "中止": ["is-stopped", (j) => `${j.label} を中止しました`],
};

function renderStatus() {
  const box = $("status");
  box.innerHTML = "";
  box.className = "status";
  const job = state.job;

  const line = el("div", "status-line");
  const logButton = el("button", "btn-log", state.showLog ? "ログ ▴" : "ログ ▾");
  logButton.disabled = !job || !job.lines || !job.lines.length;
  logButton.onclick = () => {
    state.showLog = !state.showLog;
    if (state.showLog && state.logKind === "くわしい") loadDetailLog();
    renderStatus();
  };

  if (!job || !STATUS_LOOK[job.state]) {
    line.append(el("span", "status-mark is-idle"),
                el("span", null, "何もしていません"), el("span", "spacer"), logButton);
    box.appendChild(line);
    return;
  }

  const [look, text] = STATUS_LOOK[job.state];
  box.classList.add(look);
  const mark = el("span", `status-mark ${look}`);
  if (job.state === "完了") mark.innerHTML = icon(SVG.check, 9, 2.2, 10).replace('stroke="currentColor"', 'stroke="#fff"');
  if (job.state === "エラー") mark.textContent = "!";
  line.append(mark, el("span", "status-what", text(job)));

  if (job.state === "処理中") {
    line.append(el("span", "status-time", clock(job.elapsed)));
    const tail = (job.lines || []).filter((l) => l.trim()).slice(-1)[0] || "";
    line.append(el("span", "status-tail", tail));
    const stop = el("button", "btn-plain", "中止");
    stop.onclick = () => cancelJob();
    line.append(stop);
  } else if (job.state === "完了") {
    line.append(el("span", "status-time", clock(job.elapsed)), el("span", "spacer"),
                el("span", "status-tail", "数秒で消えます"));
  } else {
    if (job.state === "中止") {
      line.append(el("span", null, "結果は前のままです"));
    } else {
      const last = (job.lines || []).filter((l) => l.trim()).slice(-1)[0] || "";
      line.append(el("span", null, last));
    }
    line.append(el("span", "spacer"));
    const again = el("button", "btn-plain", "もう一度実行");
    again.onclick = () => runStep(job.step);
    line.append(again);
  }

  line.appendChild(logButton);
  box.appendChild(line);

  if (state.showLog && job.lines && job.lines.length) {
    box.appendChild(logSwitch());
    const detail = state.detailLog;
    let text;
    if (state.logKind === "くわしい") {
      if (!detail) text = "読み込んでいます…";
      else if (detail.state !== "表示") text = "この工程のくわしいログはまだありません。";
      else text = (detail.dropped ? `（古い ${detail.dropped}行は省きました）\n` : "")
        + detail.lines.join("\n");
    } else {
      text = job.lines.join("\n");
    }
    const log = el("pre", "log", text);
    box.appendChild(log);
    log.scrollTop = log.scrollHeight;
  }
}

function logSwitch() {
  const box = el("div", "log-switch");
  for (const kind of ["かんたん", "くわしい"]) {
    const button = el("button", `log-tab ${state.logKind === kind ? "is-active" : ""}`, kind);
    button.onclick = () => {
      state.logKind = kind;
      if (kind === "くわしい") loadDetailLog();
      renderStatus();
    };
    box.appendChild(button);
  }
  box.appendChild(el("span", "log-note",
    state.logKind === "かんたん" ? "工程が出したことだけ"
                                 : "ffmpeg などの出力もぜんぶ（00_logs/ に残ります）"));
  return box;
}

async function loadDetailLog() {
  const job = state.job;
  if (!job) return;
  state.detailLog = null;
  try {
    state.detailLog = await api(`/api/episodes/${job.episode}/log/${job.step}`);
  } catch (err) {
    state.detailLog = { state: "なし", lines: [] };
  }
  renderStatus();
}

// ---------------------------------------------------------------- 工程を動かす

let ticker = null;

async function runStep(step) {
  // 文字起こしをやり直すと、聴きながら直した分が消える
  if (step === "transcribe") {
    const changed = (state.transcript && state.transcript.changed) || 0;
    const unsaved = textsDirty();
    if (changed || unsaved) {
      const what = [];
      if (changed) what.push(`保存した${changed}行の直し`);
      if (unsaved) what.push("未保存の直し");
      if (!confirm(`文字起こしをやり直すと、${what.join("と")}が消えます。\nやり直しますか？`)) {
        return;
      }
    }
  }

  // カットが未保存のまま整音すると、前のカットのままの音ができてしまう
  // （未保存のあるコーナー名を言う。echoDirty の確認と同じ形。#85 の6段目のレビュー）
  if (step === "clean" && anyCutDirty()) {
    const names = dirtyCutFrameIds().map((id) => dirtyCutFrameLabel(id)).join("・");
    const ok = confirm(`カットの未保存の変更があります（${names}）。保存してから整音しますか？\n`
      + "「キャンセル」を選ぶと、保存されている前のカットで整音します。");
    if (ok) {
      await saveAllCuts();
      if (anyCutDirty()) return;      // 保存に失敗したら、実行しない
    }
  }

  // エコー区間が未保存のまま整音すると、前の設定の音ができてしまう
  if (step === "clean" && echoDirty()) {
    const ok = confirm("エコー区間が未保存です。保存してから整音しますか？\n"
      + "「キャンセル」を選ぶと、保存されている前の区間で整音します。");
    if (ok) {
      await saveEchoes();
      if (echoDirty()) return;        // 保存に失敗したら、実行しない
    }
  }
  try {
    state.job = await api(`/api/episodes/${state.selected.name}/steps/${step}/run`, { method: "POST" });
  } catch (err) {
    state.job = { episode: state.selected.name, step, label: step,
                  state: "エラー", elapsed: 0, lines: [err.message] };
    renderStatus();
    renderMain();
    return;
  }
  state.showLog = false;
  state.detailLog = null;
  renderStatus();
  renderMain();
  openStream();
}

async function cancelJob() {
  try {
    await api("/api/job/cancel", { method: "POST" });
  } catch (err) {
    // すでに終わっていた場合など。流れてくる状態にまかせる
  }
}

function openStream() {
  if (state.stream) state.stream.close();
  state.stream = new EventSource("/api/job/stream");
  clearInterval(ticker);
  ticker = setInterval(() => {
    if (state.job && state.job.state === "処理中") {
      state.job.elapsed += 1;
      renderStatus();
      renderMain();
    }
  }, 1000);

  state.stream.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.kind === "start") {
      state.job = data.job;
    } else if (data.kind === "log") {
      state.job.lines = (state.job.lines || []).concat(data.line);
    } else if (data.kind === "state") {
      state.job = { ...state.job, ...data.job };
    } else if (data.kind === "end") {
      closeStream();
      finishJob();
      return;
    }
    renderStatus();
  };
  state.stream.onerror = () => { closeStream(); };
}

function closeStream() {
  if (state.stream) { state.stream.close(); state.stream = null; }
  clearInterval(ticker);
  ticker = null;
}

async function finishJob() {
  // 工程が終わると成果物が増えるので、状態を読み直す
  if (state.job && state.selected) {
    const name = state.selected.name;
    if (state.job.step === "scan") {
      state.scan = await api(`/api/episodes/${name}/scan`).catch(() => null);
    }
    if (state.job.step === "clean") {
      state.wave = await api(`/api/episodes/${name}/waveform`).catch(() => null);
      state.clean = await api(`/api/episodes/${name}/clean`).catch(() => null);
    }
    if (state.job.step === "mix") {
      state.mix = await api(`/api/episodes/${name}/mix`).catch(() => null);
    }
    if (state.job.step === "transcribe") {
      await loadTranscript(name);
    }
    if (state.job.step === "meta") {
      await loadMeta(name);
    }
    if (state.job.step === "video") {
      await loadVideo(name);
    }
  }
  await reload({ keep: state.selected && state.selected.name, keepSelected: true });
  if (state.showLog && state.logKind === "くわしい") await loadDetailLog();
  renderStatus();
  if (state.job && state.job.state === "完了") {
    const done = state.job;
    setTimeout(() => {
      if (state.job === done) { state.job = null; state.showLog = false; renderStatus(); renderMain(); }
    }, 5000);   // 完了は数秒で消える（見本）。エラー・中止は残す
  }
}

// ---------------------------------------------------------------- 部品2 新しい回ダイアログ

function openNewEpisode() {
  const overlay = el("div", "overlay");
  const dialog = el("div", "dialog");

  const number = el("input", "field");
  number.type = "number";
  number.min = "0";   // 第0回（テスト収録）を作れるように
  number.value = String(state.nextNumber);

  const numberLabel = el("span", "form-label", "回の番号");
  const error = el("div", "form-error");
  error.hidden = true;

  const select = seriesSelect(Object.keys(state.series)[0]);
  const theme = el("input", "field");
  theme.placeholder = themeHint(select.value);
  select.onchange = () => { theme.placeholder = themeHint(select.value); };

  const cancel = el("button", "btn-plain", "キャンセル");
  const create = el("button", "btn-primary", "作成");
  const fields = [number, select, theme];

  const setBusy = (busy) => {
    fields.forEach((node) => { node.disabled = busy; });
    cancel.disabled = busy;
    create.disabled = busy;
    create.innerHTML = "";
    if (busy) {
      create.append(el("span", "spinner"), document.createTextNode("作成中"));
    } else {
      create.textContent = "作成";
    }
  };

  cancel.onclick = () => overlay.remove();
  create.onclick = async () => {
    error.hidden = true;
    number.classList.remove("is-wrong");
    numberLabel.classList.remove("is-wrong");
    // 空欄は Number("") で 0 になり、黙って ep00 ができてしまう。先に止める
    if (number.value.trim() === "") {
      error.textContent = "回の番号を入れてください";
      error.hidden = false;
      number.classList.add("is-wrong");
      numberLabel.classList.add("is-wrong");
      return;
    }
    setBusy(true);
    try {
      const made = await api("/api/episodes", {
        method: "POST",
        body: JSON.stringify({
          episode: Number(number.value),
          segments: [{ series: select.value, theme: theme.value }],
        }),
      });
      overlay.remove();
      await reload({ keep: made.name });
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
      // 回の番号が原因なら、その欄を赤くする
      if (err.message.includes("番号")) {
        number.classList.add("is-wrong");
        numberLabel.classList.add("is-wrong");
      }
      setBusy(false);
    }
  };

  dialog.appendChild(el("div", "dialog-title", "新しい回"));
  dialog.append(field(numberLabel, number), error,
                field(el("span", "form-label", "コーナー"), select),
                field(el("span", "form-label", "テーマ"), theme));
  const foot = el("div", "dialog-foot");
  foot.append(cancel, create);
  dialog.appendChild(foot);

  overlay.appendChild(dialog);
  overlay.onclick = (event) => { if (event.target === overlay) overlay.remove(); };
  document.body.appendChild(overlay);
  number.focus();
}

function field(label, input) {
  const row = el("label", "form-row");
  row.append(label, input);
  return row;
}

// ---------------------------------------------------------------- 未保存のもの

// 保存していない変更を1か所で数える。回を移るときと、画面を閉じるときの両方で使う（#60）
function unsavedThings() {
  const rows = [];
  if (!state.selected) return rows;
  if (state.save === "dirty" || state.save === "error") rows.push("コーナー・テーマ");
  try {
    if (echoDirty()) rows.push("エコー区間");
    if (bgmDirty()) rows.push("BGM の位置・音量");
    if (anyCutDirty()) rows.push("カット区間");
    // まだ確定していない行も数える。確定（Enter / 「この行を確定」）を
    // 通るまで state.texts は変わらないので、打ちかけが黙って消えていた
    if (state.editing >= 0
        && state.draft.trim() !== (state.texts[state.editing] || "")) {
      rows.push("書きかけの行");
    }
    if (state.transcript && textsDirty()) rows.push("文字起こしの直し");
    if (state.draftMeta && metaDirty()) rows.push("タイトル・概要欄");
  } catch (err) {
    // 数えられなかったときは「無い」ことにしない。黙って閉じさせると、
    // #60 で防ごうとしたことがそのまま起きる
    console.warn("未保存のものを数えられませんでした", err);
    rows.push("保存していないもの");
  }
  return rows;
}

// 閉じる／読み込み直すときに、ブラウザに確認を出させる。
// 前は何も出ず、伸び縮みさせた区間が黙って消えていた（#60）
window.addEventListener("beforeunload", (event) => {
  if (!unsavedThings().length) return;
  event.preventDefault();
  event.returnValue = "";   // 文言はブラウザが決める
});

// ---------------------------------------------------------------- 読み込み

// 枠の一覧を取り直す。**読めないときは、黙って古い一覧や「1本だけの回」の形に戻さない**
// （#216 のレビュー）。戻すと、枠の回なのに古い入口を出したり、消したコーナーの枠を出し続けたりする。
// 回を選んだとき（selectEpisode）と、コーナーを保存したとき（saveSegments）の両方から呼ぶ
async function loadFrames(name) {
  state.frames = null;
  state.framesError = "";
  // 枠の入れ替え・コーナーの変更で id がずれることがあるので、作業中のカットは
  // 読み直すたびにサーバーの値へ作り直す（#85 の6段目）
  state.cutsWork = {};
  state.cutsSaved = {};
  state.cutFrame = null;
  state.cutPicked = -1;
  state.cutSkip = false;
  state.cutSaving = false;
  state.cutSeekPending = null;
  try {
    state.frames = await api(`/api/episodes/${name}/frames`);
  } catch (err) {
    state.framesError = err.message;
  }
}

async function selectEpisode(name) {
  // 保存している最中は、「破棄しますか」は実態と違う（破棄ではなく、終わるのを待つだけ）。
  // PR #239 の2回目レビュー・🟡
  if (state.bgmSaving && state.selected && state.selected.name !== name) {
    alert("BGM を保存しています。終わるまで待ってから移ってください");
    return;
  }
  if (state.cutSaving && state.selected && state.selected.name !== name) {
    alert("カットを保存しています。終わるまで待ってから移ってください");
    return;
  }
  const unsaved = unsavedThings();
  if (unsaved.length && state.selected && state.selected.name !== name) {
    if (!confirm(`${unsaved.join("・")}を保存していません。\n破棄して別の回に移りますか？`)) return;
  }
  state.selected = await api(`/api/episodes/${name}`);
  resetRows(state.selected.segments);
  state.actionError = "";
  audio.pause();
  audio.removeAttribute("src");
  // 別のタブにいると波形や動画のパネルが出ないので、ここで止めないと
  // 見えない場所で前の回の音が鳴り続ける
  stopWaves();
  stopVideo();
  // 前の回のタイムライン（AudioContext を持つ）も片付ける。次に必要なら作り直す
  destroyTimelineMultitrack();
  state.at = 0;
  state.playing = false;
  state.scan = await api(`/api/episodes/${name}/scan`).catch(() => null);
  state.wave = await api(`/api/episodes/${name}/waveform`).catch(() => null);
  await loadTimeline(name);
  syncBgmFromTimeline();
  await loadMusic();
  state.bgmOpen = false;
  state.bgmSource = "";
  state.bgmAnchor = "";
  state.bgmBusy = {};
  const echoes = await api(`/api/episodes/${name}/echoes`).catch(() => ({ echoes: [] }));
  state.echoes = echoes.echoes;
  state.echoesSaved = JSON.stringify(echoes.echoes);
  state.picked = -1;
  state.listening = "scan";
  state.clean = await api(`/api/episodes/${name}/clean`).catch(() => null);
  state.mix = await api(`/api/episodes/${name}/mix`).catch(() => null);
  await loadTranscript(name);
  await loadMeta(name);
  await loadVideo(name);
  state.chat = null;
  state.chatDraft = "";
  if (state.chatOpen) await loadChat();
  [state.source, state.obs] = await Promise.all([
    api(`/api/episodes/${name}/source`).catch(() => ({ state: "空" })),
    api("/api/obs").catch(() => ({ state: "未設定", recordings: [] })),
  ]);
  await loadFrames(name);
  state.frameBusy = {};
  state.frameObsOpen = null;
  state.save = "saved";
  state.saveError = "";
  renderEpisodes();
  renderSteps();
  renderMain();
  renderStatus();
}

// timeline.yml の並び（部品5・#85 の2段目）を読み直す。枠に音源を入れる・外すたびにも呼ぶ
async function loadTimeline(name) {
  // timeline.yml が壊れているときは EpisodeError の文が来るので、無い回（null）と分けて残す
  state.timeline = null;
  state.timelineError = "";
  try {
    state.timeline = await api(`/api/episodes/${name}/timeline`);
  } catch (err) {
    state.timelineError = err.message;
  }
}

// assets/music/ の曲の一覧（回をまたいで共有。#85 の5段目の「曲を置く」欄で使う）
async function loadMusic() {
  state.music = null;
  state.musicError = "";
  try {
    state.music = await api("/api/assets/music");
  } catch (err) {
    state.musicError = err.message;
  }
}

async function reload({ keep, keepSelected } = {}) {
  const data = await api("/api/episodes");
  state.episodes = data.episodes;
  state.series = data.series;
  state.nextNumber = data.next_number;

  const wanted = keep || (state.selected && state.selected.name);
  const found = state.episodes.find((ep) => ep.name === wanted) || state.episodes[0];
  if (!found) {
    state.selected = null;
  } else if (keepSelected && state.selected && state.selected.name === found.name) {
    // 保存した直後。読み直すと編集中の表示が消えるので、選び直さない
    state.selected.steps = found.steps;
  } else {
    await selectEpisode(found.name);
    return;
  }
  renderEpisodes();
  renderSteps();
  renderMain();
  renderStatus();
  renderChat();
}

document.querySelectorAll(".tab[data-tab]").forEach((node) => {
  node.onclick = () => selectTab(node.dataset.tab);
});
$("new-episode").onclick = openNewEpisode;
$("chat-toggle").onclick = () => toggleChat();

// 画面を開き直したときに、直前の工程を拾う。
// 処理中なら続きを流し、終わっていても結果とログを見られるようにする
// （待っている間にタブを開き直すと、失敗の理由が見えなくなっていた）
async function attachRunningJob() {
  try {
    const job = await api("/api/job");
    if (!job || job.state === "なし") return;
    state.job = job;
    renderStatus();
    renderMain();
    if (job.state === "処理中") openStream();
  } catch (err) { /* 拾えなくても画面は使える */ }
}

reload().then(attachRunningJob).catch((err) => {
  $("main").innerHTML = "";
  $("main").appendChild(placeholder("読み込めませんでした", err.message));
});
