// MTG Scanner page: polls the scanner's state and renders it.
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = v => v == null ? "No price" : "$" + v.toFixed(2);
  // Bin names come from the Bins page (state.bin_names); these are the defaults until it answers.
  let BIN_NAMES = { 0: "Unknown", 1: "Bulk", 2: "$1–10", 3: "$10+" };
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

  function applyLook() {
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
    if (state) drawOutlines(state);     // the outlines follow the accent color
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
    $("accentCustom").oninput = e => { look.accent = e.target.value; applyLook(); };
    $("binColors").oninput = e => { const i = e.target.dataset.bin; if (i != null) { look.bins = [...look.bins]; look.bins[i] = e.target.value; applyLook(); } };
    for (const seg of document.querySelectorAll(".drawer .seg"))
      seg.onclick = e => { const b = e.target.closest("button"); if (b) { look[seg.dataset.key] = b.dataset.v; applyLook(); } };
    for (const inp of document.querySelectorAll(".switch input"))
      inp.onchange = () => { look[inp.dataset.key] = inp.checked; applyLook(); };
    for (const inp of document.querySelectorAll(".slider input"))
      inp.oninput = () => { look[inp.dataset.key] = +inp.value; applyLook(); };
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
  const STATUS = { starting: "Starting camera…", waiting: "No camera found. Check the cable, then restart the Pi", looking: "Looking for cards", recognizing: "Recognizing…", locked: "Cards recognized", unknown: "Not recognized" };
  let selected = null;     // the card shown big: its track id
  let editing = false, drag = null;   // Slots mode: drawing boxes on the picture, and the box being dragged

  function selectedCard(s) {
    const cards = s.cards;
    let c = cards.find(x => x.track === selected);
    if (!c) { c = cards.find(x => x.card) || cards[0] || null; selected = c ? c.track : null; }
    return c;
  }

  // Each card's outline and number over the camera picture, and in Slots mode the
  // slots too. The scanner gives corners as fractions of the frame; with the SVG's
  // viewBox set to the frame and "meet" fitting it like object-fit: contain fits the
  // picture, they land on the cards at any page size. Badges are sized in screen
  // pixels, then converted (k = frame pixels per screen pixel).
  function drawOutlines(s) {
    const svg = $("overlay"), { w, h } = s.frame, box = svg.parentElement;
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    const shown = Math.min(box.clientWidth, box.clientHeight * w / h) || w;   // the picture's width on screen
    const k = w / shown;
    const f = v => v.toFixed(1);
    const badge = (x, y, n, r) => `<circle cx="${f(x)}" cy="${f(y)}" r="${f(r * k)}" vector-effect="non-scaling-stroke"/><text x="${f(x)}" y="${f(y)}" font-size="${f(14 * k)}">${n}</text>`;
    const dashes = `stroke-dasharray="${f(8 * k)} ${f(6 * k)}"`;
    const taken = new Set(s.cards.map(x => x.number));
    const slots = s.mode !== "slots" ? "" : s.slots.map((sl, i) => {
      if (taken.has(i + 1) && !editing) return "";      // the card in it shows its own outline
      const x0 = sl[0] * w, y0 = sl[1] * h, x1 = sl[2] * w, y1 = sl[3] * h;
      const del = !editing ? "" : `<g class="del" data-del="${i}" transform="translate(${f(x1)} ${f(y0)}) scale(${k.toFixed(3)})"><circle r="9"/><path d="M-3.5 -3.5 3.5 3.5M3.5 -3.5 -3.5 3.5" vector-effect="non-scaling-stroke"/></g>`;
      return `<g class="slot"><rect x="${f(x0)}" y="${f(y0)}" width="${f(x1 - x0)}" height="${f(y1 - y0)}" vector-effect="non-scaling-stroke" ${dashes}/>${badge((x0 + x1) / 2, (y0 + y1) / 2, i + 1, 11)}${del}</g>`;
    }).join("");
    const cards = s.cards.map(x => {
      const pts = x.corners.map(([cx, cy]) => [cx * w, cy * h]);
      const mx = pts.reduce((a, p) => a + p[0], 0) / pts.length, my = pts.reduce((a, p) => a + p[1], 0) / pts.length;
      const cls = `card-outline s-${x.status}${x.saved ? " saved" : ""}${x.track === selected ? " sel" : ""}`;
      return `<g class="${cls}" data-track="${x.track}"><polygon points="${pts.map(p => f(p[0]) + "," + f(p[1])).join(" ")}" vector-effect="non-scaling-stroke"/>${badge(mx, my, x.number, 13)}</g>`;
    }).join("");
    let drawing = "";
    if (drag) {
      const [ax, ay] = drag.from, [bx, by] = drag.to;
      drawing = `<rect class="drawing" x="${f(Math.min(ax, bx) * w)}" y="${f(Math.min(ay, by) * h)}" width="${f(Math.abs(bx - ax) * w)}" height="${f(Math.abs(by - ay) * h)}" vector-effect="non-scaling-stroke" ${dashes}/>`;
    }
    svg.innerHTML = slots + cards + drawing;
  }

  function render(s) {
    state = s;
    if (s.bin_names) BIN_NAMES = s.bin_names;
    $("meta").classList.remove("down");
    $("metaText").textContent = `${s.db_count.toLocaleString()} cards` + (s.learned ? ` + ${s.learned.toLocaleString()} learned` : "") + ` · ${s.prices}`;
    const st = $("camStatus"); st.textContent = STATUS[s.status] || s.status; st.className = "camera-status " + s.status;
    document.querySelector(".camera").classList.toggle("locked", s.status === "locked");
    const slotsOn = s.mode === "slots";
    if (!slotsOn) editing = false;
    document.querySelector(".camera").classList.toggle("slots", slotsOn);
    $("modeBtn").setAttribute("aria-pressed", slotsOn);
    $("modeText").textContent = slotsOn ? "Slots" : "Auto";
    $("editSlotsBtn").hidden = !slotsOn;
    $("editSlotsBtn").textContent = editing ? "Done" : "Edit slots";
    $("editSlotsBtn").setAttribute("aria-pressed", editing);
    $("clearSlotsBtn").hidden = !editing || !s.slots.length;
    $("slotHint").hidden = !editing;
    $("overlay").classList.toggle("editing", editing);

    const sel = selectedCard(s), c = sel?.card;
    drawOutlines(s);
    $("emptyCard").hidden = !!c; $("cardView").hidden = !c;
    $("whichBtn").hidden = !sel || sel.status !== "unknown";
    $("emptyText").textContent = !sel ? (!slotsOn ? "Lay cards on the table under the camera" : s.slots.length ? "Put a card in a slot" : "Draw a box around each card spot: Edit slots, under the picture")
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
        <td><span class="pill bin-${r.bin}">${r.bin} · ${esc(r.bin_label || BIN_NAMES[r.bin])}</span></td>
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
    pickCard(+row.dataset.track);
  };
  $("overlay").onclick = e => { const g = e.target.closest("[data-track]"); if (g) pickCard(+g.dataset.track); };
  function pickCard(track) {
    selected = track; render(state);
    if (state.cards.find(c => c.track === selected)?.status === "unknown") openPicker({ live: true, track: selected });
  }

  // ---------- slots: boxes you draw on the picture, one per card position ----------
  function setEditing(on) { editing = on; drag = null; if (state) render(state); }
  $("modeBtn").onclick = async () => {
    const mode = state?.mode === "slots" ? "auto" : "slots";
    render(await api("/api/settings", { mode }));
    setEditing(mode === "slots" && !state.slots.length);     // nothing drawn yet: start drawing
    toast(mode === "slots" ? "Looking for cards in the slots only" : "Looking for cards anywhere");
  };
  $("editSlotsBtn").onclick = () => setEditing(!editing);
  $("clearSlotsBtn").onclick = async () => { render(await api("/api/settings", { slots: [] })); toast("Slots cleared"); };
  // Where on the camera frame the pointer is, as fractions of its width and height.
  function framePoint(e) {
    const svg = $("overlay"), p = new DOMPoint(e.clientX, e.clientY).matrixTransform(svg.getScreenCTM().inverse());
    return [Math.min(1, Math.max(0, p.x / state.frame.w)), Math.min(1, Math.max(0, p.y / state.frame.h))];
  }
  const overlay = $("overlay");
  overlay.onpointerdown = async e => {
    if (!editing || !state || e.button) return;
    const del = e.target.closest("[data-del]");
    if (del) { render(await api("/api/settings", { slots: state.slots.filter((_, i) => i !== +del.dataset.del) })); return; }
    drag = { from: framePoint(e), to: framePoint(e) };
    overlay.setPointerCapture(e.pointerId); e.preventDefault();
    drawOutlines(state);
  };
  overlay.onpointermove = e => { if (drag) { drag.to = framePoint(e); drawOutlines(state); } };
  overlay.onpointerup = async e => {
    if (!drag) return;
    const [ax, ay] = drag.from, [bx, by] = framePoint(e); drag = null;
    const slot = [Math.min(ax, bx), Math.min(ay, by), Math.max(ax, bx), Math.max(ay, by)];
    if (slot[2] - slot[0] < 0.02 || slot[3] - slot[1] < 0.02) return drawOutlines(state);   // a click, not a box
    render(await api("/api/settings", { slots: [...state.slots, slot] }));
  };
  overlay.onpointercancel = () => { drag = null; if (state) drawOutlines(state); };
  const setting = (key) => api("/api/settings", { [key]: !state[key] }).then(render);

  $("saveBtn").onclick = saveCurrent;
  $("foilBtn").onclick = () => setting("foil");
  $("autoBtn").onclick = () => setting("auto");
  $("collectBtn").onclick = () => setting("collect").then(() => toast(state.collect ? "Collecting scans" : "Stopped collecting"));
  $("collectSwitch").onchange = e => api("/api/settings", { collect: e.target.checked }).then(render);
  $("learnSwitch").onchange = e => api("/api/settings", { learn: e.target.checked }).then(render);
  $("wrongBtn").onclick = markWrong;
  $("printBtn").onclick = otherPrinting;
  $("whichBtn").onclick = () => openPicker({ live: true, track: selected });
  $("undoBtn").onclick = async () => { const name = state.session[0]?.name; render(await api("/api/undo", {})); if (name) toast(`Removed ${name}`); };
  $("stream").onerror = () => { $("camStatus").textContent = "Camera stream lost. Reload the page"; };

  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !$("pick").hidden) return closePicker();
    if (e.key === "Escape" && drawerOpen()) return setDrawer(false);
    if (e.key === "Escape" && editing) return setEditing(false);
    if (e.target.matches("input, textarea") || e.metaKey || e.ctrlKey || e.altKey || drawerOpen() || !$("pick").hidden) return;
    if (e.key === "c" || e.key === "C") return setDrawer(true);
    if ($("tab-live").hidden) return;
    if (e.code === "Space") { e.preventDefault(); saveCurrent(); }
    else if (e.key === "f" || e.key === "F") setting("foil");
    else if (e.key === "a" || e.key === "A") setting("auto");
    else if (e.key === "r" || e.key === "R") $("collectBtn").click();
    else if (e.key === "s" || e.key === "S") $("modeBtn").click();
    else if ((e.key === "w" || e.key === "W") && selected != null) markWrong();
    else if ((e.key === "p" || e.key === "P") && selected != null) otherPrinting();
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
  // Right card, wrong set: list every printing of it (Scryfall's full list when online).
  async function otherPrinting() {
    const c = state?.cards.find(x => x.track === selected)?.card;
    if (!c) return;
    openPicker({ live: true, track: selected });
    $("pickInput").value = c.name;
    $("pickResults").innerHTML = '<p class="pick-hint">Looking up every printing…</p>';
    const n = ++searchN;
    try {
      const cards = await api(`/api/printings?name=${encodeURIComponent(c.name)}&foil=${state.foil ? 1 : 0}`);
      if (n === searchN) showPicks(cards, c.id);
    } catch (e) { if (n === searchN) $("pickResults").innerHTML = '<p class="pick-hint">Couldn\'t look up the printings</p>'; }
  }
  function showPicks(cards, current) {
    $("pickResults").innerHTML = cards.length ? cards.map(c => `<button class="pick-card${c.id === current ? " is-current" : ""}" data-id="${esc(c.id)}" data-name="${esc(c.name)}">
        <img src="${esc(c.image.replace("version=normal", "version=small"))}" alt="" loading="lazy">
        <b>${esc(c.name)}</b><span>${esc(c.set)} #${esc(c.number)} · ${money(c.price)}</span></button>`).join("")
      : '<p class="pick-hint">No card by that name in the database</p>';
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
      showPicks(cards);
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

  // The Maintenance button shows a dot when the Pi's check-up finds a problem.
  async function checkHealth() {
    try {
      const h = await api("/api/health"), b = $("healthBtn");
      if (h.overall === "ok") { delete b.dataset.state; b.title = "Maintenance"; }
      else { b.dataset.state = h.overall; b.title = "Maintenance: " + h.problems.map(p => p.label + ": " + p.summary).join(" · "); }
    } catch (e) {}
  }

  buildControls();
  applyLook();
  poll();
  checkHealth(); setInterval(checkHealth, 60000);
})();
