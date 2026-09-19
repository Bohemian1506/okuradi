// 置くラジ 制作GUI
// 画面の組み立てだけ。処理は build.py（サーバー側）にある。

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

const state = {
  episodes: [],
  series: {},
  nextNumber: 1,
  selected: null,   // 選んでいる回の detail
  tab: "1",
  dirty: false,
  saveMessage: "",
  saveError: false,
};

const $ = (id) => document.getElementById(id);

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

// ---------------------------------------------------------------- 回セレクタ

function renderEpisodes() {
  $("episode-count").textContent = state.episodes.length ? `${state.episodes.length}件` : "";
  const list = $("episode-list");
  list.innerHTML = "";

  if (!state.episodes.length) {
    const empty = document.createElement("div");
    empty.className = "episodes-empty";
    empty.textContent = "まだ回がありません";
    list.appendChild(empty);
    return;
  }

  for (const ep of state.episodes) {
    const button = document.createElement("button");
    button.className = "episode";
    if (state.selected && ep.name === state.selected.name) button.classList.add("is-selected");
    button.onclick = () => selectEpisode(ep.name);

    const top = document.createElement("div");
    top.className = "episode-top";
    top.innerHTML = `<span class="episode-id"></span><span class="episode-progress"></span>`;
    top.querySelector(".episode-id").textContent = ep.name;
    top.querySelector(".episode-progress").textContent = `${ep.done}/${ep.total}`;

    const theme = document.createElement("div");
    theme.className = "episode-theme";
    theme.textContent = ep.theme;

    const dots = document.createElement("div");
    dots.className = "episode-dots";
    for (const step of ep.steps) {
      const dot = document.createElement("span");
      dot.className = `dot ${STATE_CLASS[step.state]}`;
      dot.title = `${step.label}: ${step.state}`;
      dots.appendChild(dot);
    }

    button.append(top, theme, dots);
    list.appendChild(button);
  }
}

// ---------------------------------------------------------------- 工程ステッパー

function renderSteps() {
  const box = $("steps");
  box.querySelectorAll(".step").forEach((el) => el.remove());
  const needle = $("needle");

  const steps = state.selected ? state.selected.steps : [];
  if (!steps.length) {
    needle.hidden = true;
    $("tabs-episode").textContent = "";
    return;
  }
  $("tabs-episode").textContent = state.selected.name;

  steps.forEach((step, index) => {
    const button = document.createElement("button");
    button.className = `step ${STATE_CLASS[step.state]}`;
    if (TAB_OF_STEP[step.key] === state.tab) button.classList.add("is-here");
    button.style.gridColumn = String(index + 1);
    button.onclick = () => selectTab(TAB_OF_STEP[step.key]);
    button.innerHTML = `<span class="step-name"></span><span class="step-state"></span>`;
    button.querySelector(".step-name").textContent = step.label;
    button.querySelector(".step-state").textContent = step.state;
    box.insertBefore(button, box.querySelector(".ticks-fine"));
  });

  // 赤い針は「今いる工程」（最初の未完了）を指す
  let here = steps.findIndex((s) => s.state !== "完了");
  if (here === -1) here = steps.length - 1;
  needle.hidden = false;
  needle.style.left = `calc(100% / ${steps.length} * ${here + 0.5})`;
}

// ---------------------------------------------------------------- タブ

function selectTab(tab) {
  if (!tab) return;
  state.tab = tab;
  document.querySelectorAll(".tab").forEach((el) => {
    el.classList.toggle("is-active", el.dataset.tab === tab);
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
  const box = document.createElement("div");
  box.className = "placeholder";
  box.innerHTML = `<div class="placeholder-title"></div><div></div>`;
  box.querySelector(".placeholder-title").textContent = title;
  box.querySelectorAll("div")[1].textContent = note;
  return box;
}

// ---------------------------------------------------------------- 部品8 コーナー・テーマ編集

function seriesSelect(value) {
  const select = document.createElement("select");
  select.className = "field";
  for (const [key, label] of Object.entries(state.series)) {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = label;
    if (key === value) option.selected = true;
    select.appendChild(option);
  }
  if (value && !state.series[value]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    option.selected = true;
    select.appendChild(option);
  }
  return select;
}

function segmentsCard() {
  const card = document.createElement("div");
  card.className = "card";

  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = "コーナーとテーマ";

  const note = document.createElement("div");
  note.className = "card-note";
  note.textContent = "この回で話すコーナーを、上から順に並べます。config.yml の segments に保存します。";

  const rows = document.createElement("div");
  rows.className = "segments";

  const draw = () => {
    rows.innerHTML = "";
    state.selected.segments.forEach((segment, index) => {
      const row = document.createElement("div");
      row.className = "segment";

      const order = document.createElement("div");
      order.className = "segment-order";
      order.textContent = `${index + 1}.`;

      const select = seriesSelect(segment.series);
      select.onchange = () => { segment.series = select.value; markDirty(); };

      const theme = document.createElement("input");
      theme.className = "field";
      theme.placeholder = "例: OSI参照モデルの7層";
      theme.value = segment.theme || "";
      theme.oninput = () => { segment.theme = theme.value; markDirty(); };

      const remove = document.createElement("button");
      remove.className = "btn-quiet";
      remove.textContent = "削除";
      remove.disabled = state.selected.segments.length <= 1;
      remove.onclick = () => {
        state.selected.segments.splice(index, 1);
        markDirty();
        draw();
      };

      row.append(order, select, theme, remove);
      rows.appendChild(row);
    });
  };
  draw();

  const add = document.createElement("button");
  add.className = "btn-plain";
  add.textContent = "＋ コーナーを足す";
  add.onclick = () => {
    state.selected.segments.push({ series: Object.keys(state.series)[0] || "", theme: "" });
    markDirty();
    draw();
  };

  const save = document.createElement("button");
  save.className = "btn-primary";
  save.textContent = "保存";
  save.onclick = () => saveSegments();

  const message = document.createElement("span");
  message.className = "save-state" + (state.saveError ? " is-error" : state.dirty ? " is-dirty" : "");
  message.textContent = state.saveError ? state.saveMessage
    : state.dirty ? "未保存の変更があります"
    : state.saveMessage;

  const foot = document.createElement("div");
  foot.className = "card-foot";
  foot.append(save, message);

  card.append(title, note, rows, add, foot);
  return card;
}

function markDirty() {
  state.dirty = true;
  state.saveError = false;
  state.saveMessage = "";
  const message = document.querySelector(".save-state");
  if (message) {
    message.className = "save-state is-dirty";
    message.textContent = "未保存の変更があります";
  }
}

async function saveSegments() {
  try {
    const saved = await api(`/api/episodes/${state.selected.name}/segments`, {
      method: "PUT",
      body: JSON.stringify({ segments: state.selected.segments }),
    });
    state.selected = saved;
    state.dirty = false;
    state.saveError = false;
    state.saveMessage = "保存しました";
  } catch (err) {
    state.saveError = true;
    state.saveMessage = `保存できませんでした: ${err.message}`;
  }
  await reload({ keep: state.selected.name });
}

// ---------------------------------------------------------------- 部品2 新しい回ダイアログ

function openNewEpisode() {
  const overlay = document.createElement("div");
  overlay.className = "overlay";

  const dialog = document.createElement("div");
  dialog.className = "dialog";

  const number = document.createElement("input");
  number.className = "field";
  number.type = "number";
  number.min = "1";
  number.value = String(state.nextNumber);

  const error = document.createElement("div");
  error.className = "form-error";
  error.hidden = true;

  const select = seriesSelect(Object.keys(state.series)[0]);
  const theme = document.createElement("input");
  theme.className = "field";
  theme.placeholder = "例: OSI参照モデルの7層";

  const cancel = document.createElement("button");
  cancel.className = "btn-plain";
  cancel.textContent = "キャンセル";
  cancel.onclick = () => overlay.remove();

  const create = document.createElement("button");
  create.className = "btn-primary";
  create.textContent = "作成";
  create.onclick = async () => {
    create.disabled = true;
    create.textContent = "作成中";
    error.hidden = true;
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
      create.disabled = false;
      create.textContent = "作成";
    }
  };

  dialog.innerHTML = `<div class="dialog-title">新しい回</div>`;
  dialog.append(
    field("回の番号", number), error,
    field("コーナー", select),
    field("テーマ", theme),
  );
  const foot = document.createElement("div");
  foot.className = "dialog-foot";
  foot.append(cancel, create);
  dialog.appendChild(foot);

  overlay.appendChild(dialog);
  overlay.onclick = (event) => { if (event.target === overlay) overlay.remove(); };
  document.body.appendChild(overlay);
  number.focus();
}

function field(label, input) {
  const row = document.createElement("label");
  row.className = "form-row";
  const text = document.createElement("span");
  text.className = "form-label";
  text.textContent = label;
  row.append(text, input);
  return row;
}

// ---------------------------------------------------------------- 読み込み

async function selectEpisode(name) {
  state.selected = await api(`/api/episodes/${name}`);
  state.dirty = false;
  state.saveMessage = "";
  state.saveError = false;
  renderEpisodes();
  renderSteps();
  renderMain();
}

async function reload({ keep } = {}) {
  const data = await api("/api/episodes");
  state.episodes = data.episodes;
  state.series = data.series;
  state.nextNumber = data.next_number;

  const wanted = keep || (state.selected && state.selected.name);
  const found = state.episodes.find((ep) => ep.name === wanted) || state.episodes[0];
  if (found) {
    await selectEpisode(found.name);
  } else {
    state.selected = null;
    renderEpisodes();
    renderSteps();
    renderMain();
  }
}

document.querySelectorAll(".tab").forEach((el) => {
  el.onclick = () => selectTab(el.dataset.tab);
});
$("new-episode").onclick = openNewEpisode;

reload().catch((err) => {
  $("main").innerHTML = "";
  $("main").appendChild(placeholder("読み込めませんでした", err.message));
});
