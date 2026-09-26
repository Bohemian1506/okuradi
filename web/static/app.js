// 置くラジ 制作GUI
// 画面の組み立てだけ。処理は build.py（サーバー側）にある。
// デザインの見本: docs/design/frame-common-v2.dc.html（共通の枠）
//                 docs/design/screen1-episode-settings.dc.html（画面1）

const STATE_CLASS = {
  "未実行": "is-todo",
  "実行できる": "is-ready",
  "完了": "is-done",
  "古い": "is-stale",
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
  scan: null,        // 下見の文字起こし
  at: 0,             // 再生位置（秒）
  playing: false,
  wave: null,        // 波形に使う音（trimmed.wav）の在りかと長さ
  timeline: null,    // timeline.yml の並び（#85 の2段目。無い回は null のまま）
  timelineError: "", // timeline.yml が壊れているときの理由（黙って隠さない）
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

function renderMain() {
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

  box.appendChild(section(3, "エコー区間を決める",
    "波形をドラッグして区間を選び、プリセットを付ける。タイトルコールなど一部だけに。",
    echoCard(), null, echoSave()));

  box.appendChild(section(4, "整音して聴く",
    "前後の無音を切り、音量をそろえ、エコーをかける。聴いて確かめる1つ目の確認ポイント。",
    cleanCard(), stepOf("clean")));

  box.appendChild(section(5, "ミックスして聴く",
    "整音した喋りに、timeline.yml の BGM・SE を重ねる。無ければ喋りだけの音のまま。"
    + "BGM・SE を画面で置く・音量カーブを描く部品はこのあと足す（いまは timeline.yml を直に書く）。",
    mixCard(), stepOf("mix")));

  // timeline.yml がある回だけ出す（#85 の2段目。いまは見るだけ）
  const timelineNote = "timeline.yml に書いた音源の並び（見るだけ）。"
    + "位置はカット前（生音）の長さで出しています。カット（edits）を書くと下見が失敗します"
    + "（まだ工程に繋がっていません）。";
  if (state.timelineError) {
    destroyTimelineMultitrack();
    const card = el("div", "panel-card");
    const note = el("div", "wave-note is-error");
    note.append(el("span", "mark", "!"),
                el("span", null, `タイムラインを読み込めませんでした: ${state.timelineError}`));
    card.appendChild(note);
    box.appendChild(section(6, "タイムラインの並びを確かめる", timelineNote, card));
  } else if (state.timeline && state.timeline.timeline) {
    box.appendChild(section(6, "タイムラインの並びを確かめる", timelineNote, timelineCard()));
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
    "背景画像と整音後の音声で mp4 を作る。これを YouTube に上げます。",
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

  const banner = jobBanner("mix", "ミックス");
  if (banner) { card.appendChild(banner); if (result.state === "未実行") return card; }

  if (result.state === "未実行") {
    card.appendChild(el("div", "result-empty",
      "ミックスを実行すると、ここで聴いて確かめられます"));
    return card;
  }

  const step = stepOf("mix");
  const stale = !!(step && step.state === "古い");
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
                     at: 0, playing: false, duration, sig: null, applying: false });

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
  });
  w.ws.on("error", (err) => {
    w.phase = "失敗";
    w.error = `波形を作れませんでした: ${(err && err.message) || err}`;
    renderMain();
  });
  w.ws.on("timeupdate", (at) => {
    // 毎コマ作り直すと重いので、1秒に4回まで
    if (Math.floor(at * 4) === Math.floor(w.at * 4)) { w.at = at; return; }
    w.at = at;
    if (state.tab === "2") renderMain();
  });
  w.ws.on("interaction", (at) => { w.at = at; renderMain(); });
  w.ws.on("play", () => { w.playing = true; renderMain(); });
  w.ws.on("pause", () => { w.playing = false; renderMain(); });
  w.ws.on("finish", () => { w.playing = false; w.at = 0; renderMain(); });

  if (w.regions && editable) bindRegions(key, w);
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
    disabled: w.phase !== "表示", label: key === "clean" ? "整音結果" : "波形",
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

// ---------------------------------------------------------------- タイムライン（見るだけ・#85 の2段目）
// timeline.yml がある回だけ、収録〜整音の画面に「並びを確かめる」欄を足す。
// wavesurfer-multitrack（vendor/README.md）で本編・BGM・SEのクリップを1行ずつ並べる。
// **見るだけ**（ドラッグでの移動・保存は次の段）。再生ボタンも置かない
// （lib 側の初期化は音を鳴らさないので、静かなプレビューのまま）。
const timelineView = {
  box: el("div", "timeline-multitrack"),
  mt: null, phase: "空", error: "", sig: null, timeoutId: null,
};

const LANE_LABEL = { main: "本編", bgm: "BGM", se: "SE" };
const LANE_COLOR = { main: "#8a6f5c", bgm: "#5c7a8a", se: "#7a8a5c" };
const LANES = ["main", "bgm", "se"];

// 1トラック（wavesurfer-multitrack の1行）の高さ。CSS 側（.timeline-lane-label）
// にも同じ数を書かず、ここから値渡しする（#86 で決めた「同じレーンは1行へ重ねる」の
// 重ね幅と、見出しの高さを合わせるため。数を2か所に書き写すと片方だけ直っておかしくなる）
const TRACK_HEIGHT = 40;

function timelineTracks(lanes) {
  const tracks = [];
  for (const lane of LANES) {
    for (const clip of lanes[lane] || []) {
      // 位置が出せないクリップ（音源が無い・長さが読めない）は widget に混ぜず、
      // 上の理由のバナーだけで見せる（止めずに、そのクリップにだけ理由を付ける）
      if (clip.error || clip.start == null) continue;
      tracks.push({
        id: `${lane}-${clip.id}`,
        lane,
        url: clip.url,
        startPosition: clip.start,
        draggable: false,
        options: { waveColor: LANE_COLOR[lane], progressColor: LANE_COLOR[lane], height: TRACK_HEIGHT },
        markers: [{ time: 0, label: `${LANE_LABEL[lane]}: ${clip.id}`, color: "rgba(0,0,0,.35)" }],
      });
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
}

function ensureTimelineMultitrack(lanes) {
  const tracks = timelineTracks(lanes);
  const sig = JSON.stringify(tracks.map((t) => [t.id, t.url, t.startPosition]));
  if (timelineView.sig === sig) return;
  timelineView.sig = sig;

  if (timelineView.mt) { timelineView.mt.destroy(); timelineView.mt = null; }
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

  try {
    timelineView.mt = lib.create(tracks, {
      container: timelineView.box,
      cursorWidth: 2,
      cursorColor: "#e8c39e",
      // trackBorderColor は付けない。ライブラリはトラックの間に2pxの仕切りを挟むので、
      // 同じレーンで重ねた分だけ隙間が積み重なってずれる（レーンの境目は左の見出しで示す）
    });
  } catch (err) {
    timelineView.phase = "失敗";
    timelineView.error = `タイムラインを作れませんでした: ${err.message}`;
    renderMain();
    return;
  }

  timelineView.mt.once("canplay", () => {
    if (timelineView.sig !== sig) return;
    overlapLaneRows(timelineView.mt, tracks);
    waitForTimelineReady(sig, timelineView.mt);
  });
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
  renderMain();
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
  const lanes = tl.timeline.lanes;

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

  // クリップが1件も無い timeline.yml は、失敗ではなく空の状態として見せる
  // （部品13 の .wave-empty と同じ扱い）
  const totalClips = LANES.reduce((n, lane) => n + (lanes[lane] || []).length, 0);
  if (!totalClips) {
    destroyTimelineMultitrack();
    card.appendChild(el("div", "wave-empty", "まだクリップがありません"));
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

  ensureTimelineMultitrack(lanes);
  syncTimelineCover();
  laneRow.appendChild(timelineView.box);
  card.appendChild(laneRow);

  if (timelineView.phase === "失敗") {
    const note = el("div", "wave-note is-error");
    note.append(el("span", "mark", "!"), el("span", null, timelineView.error));
    card.appendChild(note);
  }
  return card;
}

// ---------------------------------------------------------------- 部品11・12 下見

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
    const row = el("button", "line");
    if (state.at >= line.start && state.at < line.end) row.classList.add("is-now");
    row.append(el("span", "at", clock(line.start)), el("span", "say", line.text));
    row.onclick = () => seekTo(line.start);
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
  try {
    state.frames = await api(`/api/episodes/${name}/frames`);
  } catch (err) {
    state.framesError = err.message;
  }
}

async function selectEpisode(name) {
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
