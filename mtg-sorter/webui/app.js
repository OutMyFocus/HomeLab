// MTG Scanner page: polls the scanner's state and renders it.
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = v => v == null ? "No price" : "$" + v.toFixed(2);
  const BIN_NAMES = { 0: "Unknown", 1: "Bulk", 2: "$1–10", 3: "$10+" };
  let state = null, shownId = null, toastT;

  function toast(msg) {
    const t = $("toast"); $("toastText").textContent = msg;
    t.hidden = true; void t.offsetWidth; t.hidden = false;   // restart the slide-in
    clearTimeout(toastT); toastT = setTimeout(() => t.hidden = true, 2200);
  }

  async function api(path, body) {
    const r = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }

  // ---------- look (saved in this browser only) ----------
  const LOOK_KEY = "mtg-scanner-look";
  const ACCENTS = [
    ["Ember", "#e8772e"], ["Plains", "#d6a93c"], ["Island", "#3b8eea"], ["Swamp", "#9a6bdc"],
    ["Mountain", "#e5484d"], ["Forest", "#2fa66a"], ["Teal", "#14b8a6"], ["Rose", "#ec4899"],
  ];
  const FONTS = {
    sans: '"Inter", "Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, "Helvetica Neue", Arial, sans-serif',
    rounded: 'ui-rounded, "SF Pro Rounded", "Nunito", "Quicksand", "Varela Round", "Segoe UI Variable Text", "Segoe UI", sans-serif',
    serif: '"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif',
    mono: 'ui-monospace, "Cascadia Code", "SF Mono", Menlo, Consolas, monospace',
  };
  const DEFAULT_LOOK = {
    theme: "system", accent: "#e8772e", bins: ["#6b7280", "#8b93a1", "#2bb3a3", "#d6a93c"],
    layout: "left", density: "cozy", font: "sans", size: 15, radius: 16,
    glow: true, finder: true, shine: true, stats: true, source: true, match: true, time: true, keys: true, motion: true,
  };
  const SWITCHES = ["glow", "finder", "shine", "stats", "source", "match", "time", "keys", "motion"];

  let look = { ...DEFAULT_LOOK };
  try { look = { ...DEFAULT_LOOK, ...JSON.parse(localStorage.getItem(LOOK_KEY) || "{}") }; } catch (e) {}

  // Dark text on light colors, white text on dark ones.
  function onColor(hex) {
    const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(c => c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4);
    return .2126 * r + .7152 * g + .0722 * b > .42 ? "#121417" : "#ffffff";
  }

  function applyLook(sendOutline = true) {
    const root = document.documentElement, css = root.style;
    root.dataset.theme = look.theme;
    root.dataset.layout = look.layout;
    root.dataset.density = look.density;
    css.setProperty("--accent", look.accent);
    css.setProperty("--on-accent", onColor(look.accent));
    look.bins.forEach((c, i) => { css.setProperty(`--bin${i}`, c); css.setProperty(`--on-bin${i}`, onColor(c)); });
    css.setProperty("--font", FONTS[look.font] || FONTS.sans);
    css.setProperty("--radius", look.radius + "px");
    css.fontSize = look.size + "px";
    for (const k of SWITCHES) root.classList.toggle("no-" + k, !look[k]);
    try { localStorage.setItem(LOOK_KEY, JSON.stringify(look)); } catch (e) {}
    syncControls();
    moveTabIndicator();
    // The card outline in the camera picture is drawn by the scanner, so tell it the color too.
    if (sendOutline) api("/api/settings", { outline: look.accent }).catch(() => {});
  }

  function syncControls() {
    for (const seg of document.querySelectorAll(".drawer .seg"))
      for (const b of seg.children) b.setAttribute("aria-pressed", look[seg.dataset.key] === b.dataset.v);
    for (const s of document.querySelectorAll(".swatch")) s.setAttribute("aria-pressed", s.dataset.c.toLowerCase() === look.accent.toLowerCase());
    $("accentCustom").value = look.accent;
    for (const inp of document.querySelectorAll("#binColors input")) inp.value = look.bins[inp.dataset.bin];
    for (const inp of document.querySelectorAll('.switch input')) inp.checked = !!look[inp.dataset.key];
    for (const inp of document.querySelectorAll('.slider input')) inp.value = look[inp.dataset.key];
    $("sizeOut").textContent = look.size + "px";
    $("radiusOut").textContent = look.radius + "px";
  }

  function buildControls() {
    $("accentSwatches").innerHTML = ACCENTS.map(([name, c]) =>
      `<button class="swatch" style="--c:${c}" data-c="${c}" title="${name}" aria-label="${name}"></button>`).join("");
    $("binColors").innerHTML = [3, 2, 1, 0].map(i =>
      `<label><span><span class="pill bin-${i}">Bin ${i}</span>${BIN_NAMES[i]}</span><input type="color" data-bin="${i}"></label>`).join("");

    $("accentSwatches").onclick = e => { const s = e.target.closest(".swatch"); if (s) { look.accent = s.dataset.c; applyLook(); } };
    $("accentCustom").oninput = e => { look.accent = e.target.value; applyLook(false); };
    $("accentCustom").onchange = () => applyLook();
    $("binColors").oninput = e => { const i = e.target.dataset.bin; if (i != null) { look.bins = [...look.bins]; look.bins[i] = e.target.value; applyLook(false); } };
    for (const seg of document.querySelectorAll(".drawer .seg"))
      seg.onclick = e => { const b = e.target.closest("button"); if (b) { look[seg.dataset.key] = b.dataset.v; applyLook(false); } };
    for (const inp of document.querySelectorAll(".switch input"))
      inp.onchange = () => { look[inp.dataset.key] = inp.checked; applyLook(false); };
    for (const inp of document.querySelectorAll(".slider input"))
      inp.oninput = () => { look[inp.dataset.key] = +inp.value; applyLook(false); };
    $("resetLook").onclick = () => { look = { ...DEFAULT_LOOK }; applyLook(); toast("Look reset"); };
  }

  const drawerOpen = () => $("drawer").classList.contains("open");
  function setDrawer(open) {
    $("drawer").classList.toggle("open", open);
    $("drawer").setAttribute("aria-hidden", !open);
    $("scrim").hidden = !open;
    if (open) $("closeLook").focus(); else $("lookBtn").focus();
  }
  $("lookBtn").onclick = () => setDrawer(true);
  $("closeLook").onclick = $("scrim").onclick = () => setDrawer(false);

  // ---------- live ----------
  const STATUS = { starting: "Starting camera…", looking: "Looking for cards", recognizing: "Recognizing…", locked: "Cards recognized", unknown: "Not recognized" };
  let selected = null;     // the card shown big: its track id

  function selectedCard(s) {
    const cards = s.cards;
    let c = cards.find(x => x.track === selected);
    if (!c) { c = cards.find(x => x.card) || cards[0] || null; selected = c ? c.track : null; }
    return c;
  }

  function render(s) {
    state = s;
    $("meta").classList.remove("down");
    $("metaText").textContent = `${s.db_count.toLocaleString()} cards` + (s.learned ? ` + ${s.learned.toLocaleString()} learned` : "") + ` · ${s.prices}`;
    const st = $("camStatus"); st.textContent = STATUS[s.status] || s.status; st.className = "camera-status " + s.status;
    document.querySelector(".camera").classList.toggle("locked", s.status === "locked");

    const sel = selectedCard(s), c = sel?.card;
    $("emptyCard").hidden = !!c; $("cardView").hidden = !c;
    $("whichBtn").hidden = !sel || sel.status !== "unknown";
    $("emptyText").textContent = !sel ? "Lay cards on the table under the camera"
      : sel.status === "unknown" ? `Card ${sel.number} isn't recognized` : `Recognizing card ${sel.number}…`;
    if (c) {
      if (shownId !== c.id) { $("cardImg").src = c.image; $("cardImg").alt = c.name; shownId = c.id; }
      $("cardArt").classList.toggle("foil", !!c.foil);
      $("cardName").textContent = c.name;
      $("cardSet").textContent = `${c.set_name} · ${c.set} #${c.number} · ${c.rarity}${c.foil ? " · foil" : ""}`;
      $("cardPrice").textContent = money(c.price);
      $("cardSource").textContent = c.price_source ? c.price_source : "";
      const b = $("cardBin"); b.textContent = `Bin ${c.bin} · ${c.bin_label}`; b.className = "bin bin-" + c.bin;
      const m = $("cardMatch"); m.className = "match opt-match " + (c.match || "good");
      m.textContent = c.match == null ? "You picked this" : c.match === "good" ? "Good match" : "Fair match: check the set";
    } else shownId = null;

    const value = s.cards.reduce((v, x) => v + (x.card?.price || 0), 0);
    $("tableCount").textContent = s.cards.length ? s.cards.length : "";
    $("tableValue").textContent = s.cards.length ? money(value) : "";
    $("cardList").hidden = s.cards.length < 2;
    $("cardList").innerHTML = s.cards.map(x => {
      const name = x.card ? esc(x.card.name) : x.status === "unknown" ? "Not recognized" : "Recognizing…";
      const sub = x.card ? `${esc(x.card.set)} #${esc(x.card.number)} · ${money(x.card.price)}` : x.status === "unknown" ? "Tell it which card" : "";
      const thumb = x.card ? `<img src="${esc(x.card.image.replace("version=normal", "version=small"))}" alt="" loading="lazy">` : "<i></i>";
      const end = x.saved ? '<span class="done" title="Saved"><svg><use href="#i-check"/></svg></span>'
        : x.card ? `<span class="pill bin-${x.card.bin}">${x.card.bin}</span><button class="mini" data-save="${x.track}" title="Save this card"><svg><use href="#i-check"/></svg></button>` : "";
      return `<div class="tcard s-${x.status}${x.saved ? " saved" : ""}${x.track === selected ? " sel" : ""}" data-track="${x.track}">
        <span class="num">${x.number}</span><span class="thumb">${thumb}</span>
        <span class="info"><b>${name}</b><small>${sub}</small></span>${end}</div>`;
    }).join("");

    const save = $("saveBtn");
    const unsaved = s.cards.filter(x => x.card && !x.saved).length, saved = s.cards.filter(x => x.saved).length;
    save.disabled = !unsaved;
    save.classList.toggle("saved", !unsaved && saved > 0);
    save.innerHTML = !unsaved && saved ? '<svg><use href="#i-check"/></svg>All saved'
      : unsaved > 1 ? `Save all ${unsaved} cards <kbd>Space</kbd>` : "Save card <kbd>Space</kbd>";
    $("learnSwitch").checked = s.learn;
    $("foilBtn").setAttribute("aria-pressed", s.foil);
    $("autoBtn").setAttribute("aria-pressed", s.auto);
    $("collectBtn").setAttribute("aria-pressed", s.collect);
    $("collectSwitch").checked = s.collect;
    const k = s.captures;
    $("collectInfo").textContent = s.collect
      ? `On · ${k.total + k.open} scans, ${k.labeled} confirmed` + (s.learn ? " · learning" : "")
      : "Off. Keeps each scan to train the scanner";

    const t = s.totals;
    $("statCount").textContent = t.count.toLocaleString();
    $("statValue").textContent = money(t.value);
    const bins = [3, 2, 1, 0].map(b => [b, t.bins[b] || 0]);
    $("binBar").innerHTML = bins.map(([b, n]) => `<span class="bin-${b}" style="flex-grow:${n}"></span>`).join("");
    $("binLegend").innerHTML = bins.map(([b, n]) => `<span><i class="bin-${b}"></i>${BIN_NAMES[b]} <b>${n}</b></span>`).join("");

    $("sessionRows").innerHTML = s.session.length ? s.session.map(r => `<tr>
        <td>${esc(r.name)}${r.foil ? '<span class="foil-tag">foil</span>' : ""}</td>
        <td>${esc(r.set)} #${esc(r.number)}</td>
        <td class="num">${money(r.price)}</td>
        <td><span class="pill bin-${r.bin}">${r.bin} · ${esc(BIN_NAMES[r.bin] || r.bin_label)}</span></td>
        <td class="num opt-time">${esc(r.time)}</td></tr>`).join("")
      : '<tr class="empty-row"><td colspan="5">No cards saved yet</td></tr>';
    $("undoBtn").disabled = !s.session.length;
  }

  async function poll() {
    try {
      render(await api("/api/state"));
      if (!camsLoadedAt) { camsLoadedAt = Date.now(); loadCameras(); }
      else if (state.camera?.index !== camIndex && !$("camPick").classList.contains("busy")) { camsLoadedAt = Date.now(); loadCameras(); }
    }
    catch (e) { $("meta").classList.add("down"); $("metaText").textContent = "Can't reach the scanner. Is app.py still running?"; }
    setTimeout(poll, 400);
  }

  async function saveCurrent() {
    const n = state ? state.cards.filter(x => x.card && !x.saved).length : 0;
    if (!n) return;
    render(await api("/api/save_all", { foil: state.foil }));
    toast(n === 1 ? `Saved ${state.session[0].name}` : `Saved ${n} cards`);
  }
  $("cardList").onclick = async e => {
    const row = e.target.closest(".tcard"); if (!row) return;
    const b = e.target.closest("[data-save]");
    if (b) {
      const x = state.cards.find(c => c.track === +b.dataset.save);
      render(await api("/api/add", { id: x.card.id, foil: state.foil, track: x.track }));
      return toast(`Saved ${x.card.name}`);
    }
    selected = +row.dataset.track; render(state);
    if (state.cards.find(c => c.track === selected)?.status === "unknown") openPicker({ live: true, track: selected });
  };
  const setting = (key) => api("/api/settings", { [key]: !state[key] }).then(render);

  $("saveBtn").onclick = saveCurrent;
  $("foilBtn").onclick = () => setting("foil");
  $("autoBtn").onclick = () => setting("auto");
  $("collectBtn").onclick = () => setting("collect").then(() => toast(state.collect ? "Collecting scans" : "Stopped collecting"));
  $("collectSwitch").onchange = e => api("/api/settings", { collect: e.target.checked }).then(render);
  $("learnSwitch").onchange = e => api("/api/settings", { learn: e.target.checked }).then(render);
  $("wrongBtn").onclick = markWrong;
  $("whichBtn").onclick = () => openPicker({ live: true, track: selected });
  $("undoBtn").onclick = async () => { const name = state.session[0]?.name; render(await api("/api/undo", {})); if (name) toast(`Removed ${name}`); };
  $("stream").onerror = () => { $("camStatus").textContent = "Camera stream lost. Reload the page"; };

  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !$("pick").hidden) return closePicker();
    if (e.key === "Escape" && drawerOpen()) return setDrawer(false);
    if (e.target.matches("input, textarea") || e.metaKey || e.ctrlKey || e.altKey || drawerOpen() || !$("pick").hidden) return;
    if (e.key === "c" || e.key === "C") return setDrawer(true);
    if ($("tab-live").hidden) return;
    if (e.code === "Space") { e.preventDefault(); saveCurrent(); }
    else if (e.key === "f" || e.key === "F") setting("foil");
    else if (e.key === "a" || e.key === "A") setting("auto");
    else if (e.key === "r" || e.key === "R") $("collectBtn").click();
    else if ((e.key === "w" || e.key === "W") && selected != null) markWrong();
  });

  // ---------- "which card is it?" ----------
  // live: the card under the camera (saves it and remembers the right answer).
  // crop: a collected scan in the Train tab (just labels it).
  let pickFor = null, searchT, searchN = 0;
  async function markWrong() {
    const track = selected;
    if (state?.collect) render(await api("/api/wrong", { track }));
    openPicker({ live: true, track });
  }
  function openPicker(target) {
    pickFor = target;
    $("pickScan").hidden = !target.crop;
    if (target.crop) $("pickScan").src = "/captures/" + target.crop;
    $("pickResults").innerHTML = '<p class="pick-hint">Type at least 2 letters of the card\'s name</p>';
    $("pick").hidden = false;
    $("pickInput").value = ""; $("pickInput").focus();
  }
  function closePicker() { $("pick").hidden = true; pickFor = null; }
  $("pickClose").onclick = closePicker;
  $("pick").onclick = e => { if (e.target === $("pick")) closePicker(); };
  $("pickInput").oninput = () => {
    clearTimeout(searchT);
    searchT = setTimeout(async () => {
      const q = $("pickInput").value.trim(), n = ++searchN;
      if (q.length < 2) { $("pickResults").innerHTML = '<p class="pick-hint">Type at least 2 letters of the card\'s name</p>'; return; }
      const cards = await api("/api/search?q=" + encodeURIComponent(q));
      if (n !== searchN) return;     // a newer search already answered
      $("pickResults").innerHTML = cards.length ? cards.map(c => `<button class="pick-card" data-id="${esc(c.id)}" data-name="${esc(c.name)}">
          <img src="${esc(c.image.replace("version=normal", "version=small"))}" alt="" loading="lazy">
          <b>${esc(c.name)}</b><span>${esc(c.set)} #${esc(c.number)} · ${money(c.price)}</span></button>`).join("")
        : '<p class="pick-hint">No card by that name in the database</p>';
    }, 180);
  };
  $("pickInput").onkeydown = e => { if (e.key === "Enter") $("pickResults").querySelector(".pick-card")?.click(); };
  $("pickResults").onclick = async e => {
    const b = e.target.closest(".pick-card"); if (!b || !pickFor) return;
    const target = pickFor; closePicker();
    if (target.live) {
      render(await api("/api/correct", { id: b.dataset.id, foil: state.foil, track: target.track }));
      toast(`Saved ${b.dataset.name}` + (state.collect ? " and noted it for training" : ""));
    } else {
      renderTraining(await api("/api/label?" + trainQuery(), { crop: target.crop, id: b.dataset.id }));
      toast(`Labeled as ${b.dataset.name}`);
    }
  };

  // ---------- train tab ----------
  let reviewShow = "need", training = null;
  const includeAuto = () => $("includeAuto").checked;
  try { $("includeAuto").checked = localStorage.getItem("mtg-scanner-include-auto") !== "0"; } catch (e) {}
  const trainQuery = () => `show=${reviewShow}&auto=${includeAuto() ? 1 : 0}`;
  const VERDICTS = { "saved": "Confirmed", "auto-saved": "Auto-saved", "corrected": "Corrected", "wrong": "Marked wrong", "ignore": "Skipped" };

  async function loadTraining() { try { renderTraining(await api("/api/training?" + trainQuery())); } catch (e) {} }

  function renderTraining(t) {
    training = t;
    $("trTotal").textContent = t.counts.total.toLocaleString();
    $("trLabeled").textContent = t.counts.labeled.toLocaleString();
    $("trReady").textContent = t.ready.toLocaleString();
    $("trLearned").textContent = t.learned.toLocaleString();
    $("trainBtn").disabled = !t.ready && !t.learned;
    for (const b of $("reviewSeg").children) b.setAttribute("aria-pressed", b.dataset.v === reviewShow);
    $("scanGrid").innerHTML = t.scans.length ? t.scans.map(r => {
      const verdict = r.verdict || (r.result === "unknown" ? "unknown" : "");
      const label = r.true_name || (r.result === "unknown" ? "Not recognized" : r.name);
      const guess = r.true_name && r.name && r.true_name !== r.name ? `<span>guessed ${esc(r.name)}</span>` : "";
      const right = !r.true_name && r.result === "recognized" && r.verdict !== "wrong" ? `<button class="btn" data-act="right" title="The guess is right">Right</button>` : "";
      return `<div class="scan" data-crop="${esc(r.crop)}">
        <img src="/captures/${esc(r.crop)}" alt="" loading="lazy">
        <div class="name">${esc(label)}</div>
        <div class="meta-line">${verdict ? `<span class="verdict v-${verdict}">${VERDICTS[verdict] || "Unknown"}</span>` : ""}${guess}<span>${esc(r.time.slice(5, 16))}</span></div>
        <div class="acts">${right}<button class="btn" data-act="pick">${r.true_name ? "Change" : "Which card?"}</button>${r.verdict === "ignore" ? "" : '<button class="btn ghost" data-act="ignore" title="Bad picture, don\'t learn from it">Skip</button>'}</div>
      </div>`;
    }).join("") : `<p class="grid-empty">${t.counts.total ? "Nothing needs a label. Nice work." : "No scans yet. Turn on Collect scans, then scan some cards."}</p>`;
  }

  $("scanGrid").onclick = async e => {
    const b = e.target.closest("[data-act]"); if (!b) return;
    const crop = b.closest(".scan").dataset.crop;
    if (b.dataset.act === "pick") return openPicker({ crop });
    renderTraining(await api("/api/label?" + trainQuery(), { crop, verdict: b.dataset.act === "right" ? "saved" : "ignore" }));
  };
  $("reviewSeg").onclick = e => { const b = e.target.closest("button"); if (b) { reviewShow = b.dataset.v; loadTraining(); } };
  $("includeAuto").onchange = () => { try { localStorage.setItem("mtg-scanner-include-auto", includeAuto() ? "1" : "0"); } catch (e) {} loadTraining(); };
  $("trainBtn").onclick = async () => {
    const btn = $("trainBtn"); btn.disabled = true; btn.lastChild.textContent = "Training…";
    try {
      const r = await api("/api/train", { include_auto: includeAuto() });
      toast(r.added || r.removed ? `Learned ${r.added} new scan${r.added === 1 ? "" : "s"}` + (r.removed ? `, forgot ${r.removed}` : "") : "Already up to date");
    } finally { btn.lastChild.textContent = "Train now"; loadTraining(); }
  };
  $("forgetBtn").onclick = async () => {
    if (!confirm("Forget everything the scanner learned from your scans? Your collected scans stay, so you can train again.")) return;
    const r = await api("/api/forget", {}); toast(`Forgot ${r.removed} learned scans`); loadTraining();
  };

  // ---------- camera picker ----------
  let camIndex = undefined;
  async function loadCameras() {
    let cams = [];
    try { cams = await api("/api/cameras"); } catch (e) {}
    const sel = $("camSelect"), cur = state?.camera;
    const opts = cams.map(c => `<option value="${c.index}">${esc(c.name)}</option>`);
    if (!cur) opts.unshift('<option value="" disabled>Demo photos</option>');
    if (!cams.length) opts.push('<option value="" disabled>No cameras found</option>');
    sel.innerHTML = opts.join("");
    sel.value = cur ? String(cur.index) : "";
    camIndex = cur?.index;
  }
  $("camSelect").onchange = async e => {
    const sel = e.target, index = +sel.value, name = sel.selectedOptions[0].textContent;
    $("camPick").classList.add("busy");
    $("camStatus").textContent = `Switching to ${name}…`;
    try {
      const r = await fetch("/api/camera", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ index, name }) });
      const body = await r.json();
      if (!r.ok) { toast(body.error || "Couldn't switch camera"); sel.value = camIndex ?? ""; }
      else { render(body); camIndex = index; toast(`Using ${name}`); }
    } catch (err) { toast("Couldn't switch camera"); sel.value = camIndex ?? ""; }
    $("camPick").classList.remove("busy");
  };
  // Refresh the list when it's opened, so newly plugged-in cameras show up.
  $("camSelect").addEventListener("mousedown", () => { if (!$("camPick").classList.contains("busy")) refreshCams(); });
  let camsLoadedAt = 0;
  function refreshCams() { if (Date.now() - camsLoadedAt > 5000) { camsLoadedAt = Date.now(); loadCameras(); } }

  // ---------- tabs ----------
  function moveTabIndicator() {
    const b = document.querySelector('.tabs button[aria-selected="true"]'), ind = $("tabInd");
    ind.style.width = b.offsetWidth + "px";
    ind.style.transform = `translateX(${b.offsetLeft}px)`;
  }
  for (const b of document.querySelectorAll(".tabs button")) b.onclick = () => {
    for (const x of document.querySelectorAll(".tabs button")) x.setAttribute("aria-selected", x === b);
    for (const s of document.querySelectorAll(".tab")) s.hidden = s.id !== "tab-" + b.dataset.tab;
    moveTabIndicator();
    if (b.dataset.tab === "train") loadTraining();
  };
  addEventListener("resize", moveTabIndicator);
  document.fonts?.ready.then(moveTabIndicator);

  // ---------- photos ----------
  let photoResults = [];
  async function scanPhotos(files) {
    if (!files.length) return;
    $("photoBar").hidden = false; $("photoSummary").textContent = `Scanning ${files.length} photo${files.length > 1 ? "s" : ""}…`;
    $("addAllBtn").disabled = true;
    const fd = new FormData(); for (const f of files) fd.append("photos", f);
    const urls = new Map([...files].map(f => [f.name, URL.createObjectURL(f)]));
    const r = await fetch("/api/photos", { method: "POST", body: fd });
    const results = (await r.json()).map(x => ({ ...x, preview: urls.get(x.file), added: false, foil: false }));
    photoResults = [...results, ...photoResults];
    renderPhotos();
  }

  function renderPhotos() {
    const found = photoResults.filter(p => p.card);
    const waiting = found.filter(p => !p.added);
    $("photoSummary").textContent = `${found.length} of ${photoResults.length} recognized` + (waiting.length < found.length ? ` · ${found.length - waiting.length} added` : "");
    $("addAllBtn").disabled = !waiting.length;
    $("photoGrid").innerHTML = photoResults.map((p, i) => p.card ? `<div class="panel photo">
        <img src="${esc(p.card.image)}" alt="${esc(p.card.name)}" loading="lazy">
        <div class="name">${esc(p.card.name)}</div>
        <div class="sub">${esc(p.card.set)} #${esc(p.card.number)}${p.card.match === "fair" ? " · check the set" : ""}</div>
        <div class="row"><b>${money(p.card.price)}</b><span class="pill bin-${p.card.bin}">Bin ${p.card.bin}</span></div>
        <div class="row"><label><input type="checkbox" data-foil="${i}" ${p.foil ? "checked" : ""} ${p.added ? "disabled" : ""}> Foil</label>
          <button class="btn ${p.added ? "saved" : ""}" data-add="${i}" ${p.added ? "disabled" : ""}>${p.added ? "Added ✓" : "Add"}</button></div>
      </div>` : `<div class="panel photo">
        <img src="${esc(p.preview || "")}" alt="">
        <div class="name">${esc(p.file)}</div><div class="err">${esc(p.error)}</div>
      </div>`).join("");
  }

  async function addPhoto(i) {
    const p = photoResults[i]; if (!p || p.added) return;
    render(await api("/api/add", { id: p.card.id, foil: p.foil }));
    p.added = true;
  }

  $("photoGrid").addEventListener("click", async e => {
    const b = e.target.closest("[data-add]"); if (!b) return;
    await addPhoto(+b.dataset.add); renderPhotos(); toast("Added to collection");
  });
  $("photoGrid").addEventListener("change", e => {
    const c = e.target.closest("[data-foil]"); if (c) photoResults[+c.dataset.foil].foil = c.checked;
  });
  $("addAllBtn").onclick = async () => {
    let n = 0; for (let i = 0; i < photoResults.length; i++) if (photoResults[i].card && !photoResults[i].added) { await addPhoto(i); n++; }
    renderPhotos(); toast(`Added ${n} card${n === 1 ? "" : "s"}`);
  };
  $("photoInput").onchange = e => { scanPhotos(e.target.files); e.target.value = ""; };
  const drop = $("drop");
  drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", e => { e.preventDefault(); drop.classList.remove("over"); scanPhotos(e.dataTransfer.files); });

  buildControls();
  applyLook();
  poll();
})();
