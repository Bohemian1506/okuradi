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
};

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
};

const $ = (id) => document.getElementById(id);

function icon(path, size = 14, width = 1.8) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 14 14" fill="none"
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
  const names = { "2": "2. 収録〜整音", "3": "3. 仕上げ" };
  const issues = { "2": "#6", "3": "#7" };
  main.appendChild(placeholder(names[state.tab], `この画面の中身は ${issues[state.tab]} で入れます`));
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
  head.append(el("span", null, "順"), el("span", null, "コーナー"),
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

    row.append(el("div", "segment-no", String(index + 1)), select, theme, remove);
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
}

document.querySelectorAll(".tab").forEach((node) => {
  node.onclick = () => selectTab(node.dataset.tab);
});
$("new-episode").onclick = openNewEpisode;

reload().catch((err) => {
  $("main").innerHTML = "";
  $("main").appendChild(placeholder("読み込めませんでした", err.message));
});
