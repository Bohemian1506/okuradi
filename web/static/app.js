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
  source: "2", scan: "2", clean: "2",
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
};

// どの画面にどの工程があるか（TAB_OF_STEP の裏返し）
const STEPS_OF_TAB = { "1": [], "2": ["source", "scan", "clean"], "3": ["transcribe", "meta", "video"] };

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
  stream: null,
};

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
  state.tab = tab;
  document.querySelectorAll(".tab").forEach((node) => {
    node.classList.toggle("is-active", node.dataset.tab === tab);
  });
  renderSteps();
  renderMain();
}

function renderMain() {
  const main = $("main");
  main.innerHTML = "";

  if (!state.selected) {
    main.appendChild(placeholder("回がありません", "左の「新しい回」から作ってください"));
    return;
  }
  if (state.tab === "1") {
    main.appendChild(segmentsCard());
    return;
  }
  main.appendChild(runsCard());
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

  const issues = { "2": "#6", "3": "#7" };
  box.appendChild(el("div", "segments-note",
    `いまは工程を動かすところだけです。この画面の中身は ${issues[state.tab]} で入れます。`));

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

function placeholder(title, note) {
  const box = el("div", "placeholder");
  box.append(el("div", "placeholder-title", title), el("div", null, note));
  return box;
}

// ---------------------------------------------------------------- 部品8 コーナーの並び

function seriesSelect(value) {
  const select = el("select", "field");
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
  return (rule && rule.hint) || "例: OSI参照モデルの7層";
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
    segments.push({ series: Object.keys(state.series)[0] || "", theme: "" });
    state.rowIds.push(state.nextRowId++);
    markDirty();
    renderMain();
  };
  list.appendChild(add);

  card.append(list, el("div", "segments-note",
    "コーナーの種類ごとにタイトルの型が決まっています。"
    + "タイトルはメタデータの工程で、この並びとテーマから作られます。"));
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
    await reload({ keep: saved.name, keepSelected: true });
  } catch (err) {
    state.save = "error";
    // 「保存できませんでした」はバッジが出すので、帯には理由だけ書く
    state.saveError = err.message;
    renderMain();
  }
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
  logButton.onclick = () => { state.showLog = !state.showLog; renderStatus(); };

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
    const log = el("pre", "log", job.lines.join("\n"));
    box.appendChild(log);
    log.scrollTop = log.scrollHeight;
  }
}

// ---------------------------------------------------------------- 工程を動かす

let ticker = null;

async function runStep(step) {
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
  await reload({ keep: state.selected && state.selected.name, keepSelected: true });
  renderStatus();
  if (state.job && state.job.state === "完了") {
    const done = state.job;
    setTimeout(() => {
      if (state.job === done) { state.job = null; state.showLog = false; renderStatus(); renderMain(); }
    }, 5000);   // 完了は数秒で消える（見本）
  }
}

// ---------------------------------------------------------------- 部品2 新しい回ダイアログ

function openNewEpisode() {
  const overlay = el("div", "overlay");
  const dialog = el("div", "dialog");

  const number = el("input", "field");
  number.type = "number";
  number.min = "1";
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
    setBusy(true);
    error.hidden = true;
    number.classList.remove("is-wrong");
    numberLabel.classList.remove("is-wrong");
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

// ---------------------------------------------------------------- 読み込み

async function selectEpisode(name) {
  const unsaved = state.save === "dirty" || state.save === "error";
  if (unsaved && state.selected && state.selected.name !== name) {
    if (!confirm("保存していない変更があります。破棄して別の回に移りますか？")) return;
  }
  state.selected = await api(`/api/episodes/${name}`);
  resetRows(state.selected.segments);
  state.save = "saved";
  state.saveError = "";
  renderEpisodes();
  renderSteps();
  renderMain();
  renderStatus();
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
}

document.querySelectorAll(".tab").forEach((node) => {
  node.onclick = () => selectTab(node.dataset.tab);
});
$("new-episode").onclick = openNewEpisode;

// 画面を開き直したときに、動いている工程があれば拾う
async function attachRunningJob() {
  try {
    const job = await api("/api/job");
    if (job && job.state === "処理中") {
      state.job = job;
      renderStatus();
      renderMain();
      openStream();
    }
  } catch (err) { /* 拾えなくても画面は使える */ }
}

reload().then(attachRunningJob).catch((err) => {
  $("main").innerHTML = "";
  $("main").appendChild(placeholder("読み込めませんでした", err.message));
});
