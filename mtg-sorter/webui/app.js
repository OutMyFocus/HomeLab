// MTG Scanner page: polls the scanner's state and renders it.
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = v => v == null ? "No price" : "$" + v.toFixed(2);
  // Bin names come from the Bins page (state.bin_names); these are the defaults until it answers.
  let BIN_NAMES = { 0: "Unknown", 1: "Bulk", 2: "$1–10", 3: "$10+" };
  let state = null, shownId = null, toastT;
  // This page's own scanner, once its device becomes a camera: a token the page made up,
  // which names that scanner in every request (and the name typed as "who's scanning").
  const device = { on: false, stream: null, token: null, facing: "environment", torch: false, who: "",
    name: /Mobi|Android|iPhone|iPad/.test(navigator.userAgent) ? "Phone camera" : "Computer camera" };
  try { device.token = sessionStorage.getItem("mtg-cam-token"); device.who = localStorage.getItem("mtg-scanner-who") || ""; } catch (e) {}
  if (!device.token) {
    device.token = (crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2) + Date.now());
    try { sessionStorage.setItem("mtg-cam-token", device.token); } catch (e) {}
  }
  // Set an element's HTML only when it changed. The state arrives several times a second,
  // and rebuilding unchanged rows restarts their animations and reloads their pictures.
  const setHTML = (el, html) => { if (el._html !== html) { el._html = html; el.innerHTML = html; } };

  function toast(msg) {
    const t = $("toast"); $("toastText").textContent = msg;
    t.hidden = true; void t.offsetWidth; t.hidden = false;   // restart the slide-in
    clearTimeout(toastT); toastT = setTimeout(() => t.hidden = true, 2200);
  }

  // Every request names this page's scanner (see "this device's camera" below). Until the
  // device scans, that name is unknown to the app and the machine's scanner answers.
  const scannerHeaders = () => ({ "X-Scanner": device.token });
  async function api(path, body) {
    const r = await fetch(path, body === undefined ? { headers: scannerHeaders() }
      : { method: "POST", headers: { "Content-Type": "application/json", ...scannerHeaders() }, body: JSON.stringify(body) });
    if (r.status === 401) { location.href = "/lock?next=/scan"; throw new Error("Locked"); }   // the PIN lock (Settings page)
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }

  // ---------- look (saved in this browser only) ----------
  const LOOK_KEY = "mtg-scanner-look";
  const ACCENTS = [
    ["Aether", "#7c5cff"], ["Ember", "#e8772e"], ["Plains", "#d6a93c"], ["Island", "#3b8eea"], ["Swamp", "#9a6bdc"],
    ["Mountain", "#e5484d"], ["Forest", "#2fa66a"], ["Teal", "#14b8a6"], ["Rose", "#ec4899"],
  ];
  const FONTS = {
    sans: '"Inter Var", "Inter", "Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, "Helvetica Neue", Arial, sans-serif',
    rounded: 'ui-rounded, "SF Pro Rounded", "Nunito", "Quicksand", "Varela Round", "Segoe UI Variable Text", "Segoe UI", sans-serif',
    serif: '"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif',
    mono: 'ui-monospace, "Cascadia Code", "SF Mono", Menlo, Consolas, monospace',
  };
  const DEFAULT_LOOK = {
    v: 2, theme: "system", accent: "#7c5cff", bins: ["#6b7280", "#8b93a1", "#22b3a3", "#f2a93b"],
    layout: "left", density: "cozy", font: "sans", size: 15, radius: 18,
    glow: true, finder: true, shine: true, stats: true, source: true, match: true, time: true, keys: true, motion: true,
  };
  const SWITCHES = ["glow", "finder", "shine", "stats", "source", "match", "time", "keys", "motion"];

  let look = { ...DEFAULT_LOOK };
  try {
    const saved = JSON.parse(localStorage.getItem(LOOK_KEY) || "{}") || {};
    // Saved before SortR with the old defaults (Ember orange, 16 px corners): take the new ones (see look.js).
    if (!saved.v) {
      if ((saved.accent || "").toLowerCase() === "#e8772e") delete saved.accent;
      if (saved.radius === 16) delete saved.radius;
      if (JSON.stringify(saved.bins) === JSON.stringify(["#6b7280", "#8b93a1", "#2bb3a3", "#d6a93c"])) delete saved.bins;
      delete saved.v;
    }
    look = { ...DEFAULT_LOOK, ...saved, v: 2 };
  } catch (e) {}
  // The light/dark button in the top bar changes the theme without going through this panel.
  window.addEventListener("mtg-look", e => { if (e.detail?.theme) { look.theme = e.detail.theme; syncControls(); } });

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
  const STATUS = { starting: "Starting camera…", waiting: "No camera connected", paused: "Camera paused", looking: "Looking for cards", recognizing: "Recognizing…", locked: "Cards recognized", unknown: "Not recognized" };
  let selected = null;     // the card shown big: its track id
  let editing = false, drag = null;   // Slots mode: drawing boxes on the picture, and the box being dragged
  let cropping = false;               // drawing the crop box (the part of the picture to keep)

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
    setHTML(svg, slots + cards + drawing);
  }

  function render(s) {
    state = s;
    if (s.bin_names) BIN_NAMES = s.bin_names;
    $("meta").classList.remove("down");
    $("metaText").textContent = `${s.db_count.toLocaleString()} cards` + (s.learned ? ` + ${s.learned.toLocaleString()} learned` : "") + ` · ${s.prices}`;
    const others = (s.scanners || []).map(o => o.owner || o.name);
    $("othersScanning").hidden = !others.length;
    $("othersScanning").textContent = others.length ? `Also scanning: ${others.join(", ")}` : "";
    if (device.on && isPhone && s.status === "locked" && state?.status !== "locked") { try { navigator.vibrate?.(25); } catch (e) {} }
    const st = $("camStatus"); st.textContent = STATUS[s.status] || s.status; st.className = "camera-status " + s.status;
    showCamera(s.status !== "waiting");
    $("noCamHint").textContent = s.on_pi
      ? "On the Pi: power off, reseat the ribbon cable (contacts facing the board at both ends), then power on. It keeps looking, so the picture appears by itself once a camera works."
      : navigator.mediaDevices ? `To scan with this ${deviceWord}'s camera, open the app at its https address (through Tailscale: see deploy/UNRAID.md).`
      : "This browser can't share its camera. Try Chrome, Safari or Firefox, at the app's https address.";
    document.querySelector(".camera").classList.toggle("locked", s.status === "locked");
    const slotsOn = s.mode === "slots";
    if (!slotsOn) editing = false;
    document.querySelector(".camera").classList.toggle("slots", slotsOn);
    $("modeBtn").setAttribute("aria-pressed", slotsOn);
    $("modeText").textContent = slotsOn ? "Slots" : "Auto";
    renderFocus(s.camera?.focus);
    renderView(s);
    $("editSlotsBtn").hidden = !slotsOn;
    $("editSlotsBtn").textContent = editing ? "Done" : "Edit slots";
    $("editSlotsBtn").setAttribute("aria-pressed", editing);
    $("clearSlotsBtn").hidden = !editing || !s.slots.length;
    $("slotHint").hidden = !editing;
    $("overlay").classList.toggle("editing", editing || cropping);

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
      window.Montreal?.show($("cardMontreal"), c);  // today's prices at Face to Face Games and other Montreal stores
      const b = $("cardBin"); b.textContent = `Bin ${c.bin} · ${c.bin_label}`; b.className = "bin bin-" + c.bin;
      const m = $("cardMatch"); m.className = "match opt-match " + (c.match || "good");
      $("cardWanted").hidden = !c.wanted;
      m.textContent = c.match == null ? "You picked this" : c.match === "good" ? "Good match" : "Fair match: check the set";
    } else { shownId = null; window.Montreal?.show($("cardMontreal"), null); }

    const value = s.cards.reduce((v, x) => v + (x.card?.price || 0), 0);
    $("tableCount").textContent = s.cards.length ? s.cards.length : "";
    $("tableValue").textContent = s.cards.length ? money(value) : "";
    $("cardList").hidden = s.cards.length < 2;
    setHTML($("cardList"), s.cards.map(x => {
      const name = x.card ? esc(x.card.name) : x.status === "unknown" ? "Not recognized" : "Recognizing…";
      const sub = x.card ? `${esc(x.card.set)} #${esc(x.card.number)} · ${money(x.card.price)}` : x.status === "unknown" ? "Tell it which card" : "";
      const thumb = x.card ? `<img src="${esc(x.card.image.replace("version=normal", "version=small"))}" alt="" loading="lazy">` : "<i></i>";
      const end = x.saved ? '<span class="done" title="Saved"><svg><use href="#i-check"/></svg></span>'
        : x.card ? `<span class="pill bin-${x.card.bin}">${x.card.bin}</span><button class="mini" data-save="${x.track}" title="Save this card"><svg><use href="#i-check"/></svg></button>` : "";
      return `<div class="tcard s-${x.status}${x.saved ? " saved" : ""}${x.track === selected ? " sel" : ""}" data-track="${x.track}">
        <span class="num">${x.number}</span><span class="thumb">${thumb}</span>
        <span class="info"><b>${name}</b><small>${sub}</small></span>${end}</div>`;
    }).join(""));

    const save = $("saveBtn");
    const unsaved = s.cards.filter(x => x.card && !x.saved).length, saved = s.cards.filter(x => x.saved).length;
    save.disabled = !unsaved;
    save.classList.toggle("saved", !unsaved && saved > 0);
    save.innerHTML = !unsaved && saved ? '<svg><use href="#i-check"/></svg>All saved'
      : unsaved > 1 ? `Save all ${unsaved} cards <kbd>Space</kbd>` : "Save card <kbd>Space</kbd>";
    $("learnSwitch").checked = s.learn;
    showSorter(s);
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
    setHTML($("binBar"), bins.map(([b, n]) => `<span class="bin-${b}" style="flex-grow:${n}"></span>`).join(""));
    setHTML($("binLegend"), bins.map(([b, n]) => `<span><i class="bin-${b}"></i>${esc(BIN_NAMES[b])} <b>${n}</b></span>`).join(""));

    announce(s);
    const more = (s.session_count || s.session.length) - s.session.length;
    setHTML($("sessionRows"), (s.session.length ? s.session.map(r => `<tr${r.wanted ? ' class="wanted"' : ""}>
        <td>${esc(r.name)}${r.foil ? '<span class="foil-tag">foil</span>' : ""}</td>
        <td>${esc(r.set)} #${esc(r.number)}</td>
        <td class="num">${money(r.price)}</td>
        <td><span class="pill bin-${r.bin}">${r.bin} · ${esc(r.bin_label || BIN_NAMES[r.bin])}</span></td>
        <td class="num opt-time">${esc(r.time)}</td></tr>`).join("")
      : '<tr class="empty-row"><td colspan="5">No cards saved yet</td></tr>')
      + (more > 0 ? `<tr class="empty-row"><td colspan="5">and ${more.toLocaleString()} earlier this session, on the <a href="/history">History</a> page</td></tr>` : ""));
    $("undoBtn").disabled = !s.session.length;
  }

  // ---------- alerts: a valuable card or a wishlist card was just saved (Settings page) ----------
  let lastSaved = null, bannerT;
  function announce(s) {
    const newest = s.session[0]?.scanned_at || "";
    if (lastSaved === null) { lastSaved = newest; return; }      // the page just opened: nothing is new
    if (!newest || newest === lastSaved) return;
    const fresh = s.session.filter(r => r.scanned_at > lastSaved);
    lastSaved = newest;
    const a = s.alerts || {};
    const big = a.big_card != null ? fresh.filter(r => (r.price || 0) >= a.big_card).sort((x, y) => y.price - x.price)[0] : null;
    const wish = a.wishlist ? fresh.find(r => r.wanted) : null;
    const hit = wish || big;
    if (!hit) return;
    const b = $("alertBanner");
    b.className = "alert-banner" + (hit === wish ? " wish" : "");
    b.innerHTML = `<img src="${esc(hit.image.replace("version=normal", "version=small"))}" alt=""><span>${hit === wish ? "On your wishlist!" : "Valuable card!"} ${esc(hit.name)}<small>${money(hit.price)} · ${esc(hit.set)} · bin ${hit.bin}</small></span>`;
    b.hidden = true; void b.offsetWidth; b.hidden = false;
    clearTimeout(bannerT); bannerT = setTimeout(() => b.hidden = true, 5000);
    if (a.sound) window.mtgChime?.(hit === wish ? "wish" : "big");
  }
  $("alertBanner").onclick = () => $("alertBanner").hidden = true;

  // ---------- no camera: a plain message instead of an empty picture ----------
  // The picture only streams while there's a camera, so a missing one doesn't keep a
  // connection to the Pi open for nothing.
  // With this device's own camera, the page shows its video straight from the camera
  // (no round trip) and the scanner's outlines are drawn over it.
  let camShown = null, streamRetry;
  function showCamera(on) {
    const want = on ? (device.on ? "local" : "stream") : "off";
    if (want === camShown) return;
    camShown = want;
    document.querySelector(".camera").classList.toggle("no-cam", !on);
    $("noCamera").hidden = on;
    $("localCam").hidden = want !== "local";
    if (want === "stream") $("stream").src = "/stream.mjpg?" + Date.now(); else $("stream").removeAttribute("src");
    $("stream").hidden = want === "local";
  }
  $("stream").onerror = () => {   // the stream dropped (the app restarted, Wi-Fi blinked): try again
    if (camShown !== "stream") return;
    $("camStatus").textContent = "Reconnecting to the camera…";
    clearTimeout(streamRetry);
    streamRetry = setTimeout(() => { if (camShown === "stream") $("stream").src = "/stream.mjpg?" + Date.now(); }, 3000);
  };
  $("usePhotosBtn").onclick = () => showTab("photos");

  // ---------- this device's camera: the phone or computer scans with its own camera ----------
  // The browser opens the camera, and the page sends a picture to the scanner several
  // times a second. Browsers only allow the camera on https (or localhost).
  const isPhone = /Mobi|Android|iPhone|iPad/.test(navigator.userAgent);
  const deviceWord = isPhone ? "phone" : "computer";
  const canUseDevice = !!navigator.mediaDevices?.getUserMedia && window.isSecureContext;
  const deviceHint = canUseDevice ? "" : !navigator.mediaDevices ? "This browser can't share its camera" : "Needs an https address (see Maintenance)";
  const canvas = document.createElement("canvas"), ctx = canvas.getContext("2d", { willReadFrequently: false });
  let sendT = null;

  // Open the camera (the back one on a phone, by default) and show it in the picture box.
  async function openDeviceStream() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: false,
      video: { facingMode: { ideal: device.facing }, width: { ideal: 1920 }, height: { ideal: 1080 } } });
    device.stream?.getTracks().forEach(t => t.stop());
    device.stream = stream;
    const v = $("localCam"); v.srcObject = stream;
    try { await v.play(); } catch (e) {}
    const track = stream.getVideoTracks()[0];
    track.onended = () => { if (device.on) { stopDeviceCamera(true); toast("The camera was closed"); } };
    // The picture box takes the camera's shape (a phone held upright gives a tall picture).
    fitDeviceBox();
    v.onresize = fitDeviceBox;
    // Tools that this camera supports: a light, and switching between cameras.
    const caps = track.getCapabilities?.() || {};
    $("torchBtn").hidden = !caps.torch;
    $("torchBtn").setAttribute("aria-pressed", "false"); device.torch = false;
    try {
      const cams = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === "videoinput");
      $("flipCamBtn").hidden = cams.length < 2;
    } catch (e) { $("flipCamBtn").hidden = true; }
  }
  function fitDeviceBox() {
    const v = $("localCam"), box = document.querySelector(".camera");
    if (device.on && v.videoWidth && v.videoHeight) box.style.aspectRatio = `${v.videoWidth} / ${v.videoHeight}`;
    else box.style.aspectRatio = "";
    if (state) drawOutlines(state);
  }

  async function startDeviceCamera() {
    if (device.on) return true;
    if (!canUseDevice) { toast(deviceHint); return false; }
    $("camStatus").textContent = `Opening this ${deviceWord}'s camera…`;
    try {
      await openDeviceStream();
    } catch (e) {
      toast(e.name === "NotAllowedError" ? "Camera permission was refused" : `Couldn't open this ${deviceWord}'s camera`);
      return false;
    }
    device.on = true; camIndex = "browser";
    document.querySelector(".camera").classList.add("device");
    $("camDevice").hidden = false;
    fitDeviceBox();
    device.who = $("whoInput").value.trim().slice(0, 40);
    try { localStorage.setItem("mtg-scanner-who", device.who); } catch (e) {}
    $("camStatus").textContent = "Handing the camera to the scanner…";
    try { render(await claimScanner()); }
    catch (e) { stopDeviceCamera(false); toast("Couldn't hand the camera to the scanner. Check the connection and try again"); return false; }
    camsLoadedAt = Date.now(); loadCameras();   // the menu now shows this device as the camera
    sendFrame();
    toast(device.who ? `Scanning as ${device.who}` : `Scanning with this ${deviceWord}'s camera`);
    return true;
  }

  $("flipCamBtn").onclick = async () => {
    device.facing = device.facing === "environment" ? "user" : "environment";
    try { await openDeviceStream(); } catch (e) { toast("Couldn't switch camera"); }
  };
  $("torchBtn").onclick = async () => {
    const track = device.stream?.getVideoTracks()[0]; if (!track) return;
    try {
      await track.applyConstraints({ advanced: [{ torch: !device.torch }] });
      device.torch = !device.torch;
      $("torchBtn").setAttribute("aria-pressed", device.torch);
    } catch (e) { toast("This camera's light can't be turned on from here"); }
  };
  $("stopDeviceBtn").onclick = () => { stopDeviceCamera(true); toast("Stopped scanning with this device"); loadCameras(); };

  // Asking the scanner for this device's camera. A phone on cellular (or Tailscale waking
  // up) drops the odd request, so a failed ask is tried again a few times before giving up.
  async function claimScanner() {
    const ask = { index: "browser", name: device.name, token: device.token, who: device.who };
    let wait = 600;
    for (let tries = 0; ; tries++) {
      try { return await api("/api/camera", ask); }
      catch (e) {
        if (e.message === "Locked" || e.message === "400" || tries >= 3 || !device.on) throw e;
        await new Promise(res => setTimeout(res, wait)); wait *= 2;
      }
    }
  }

  // One picture after another: the next one goes as soon as the scanner took the last,
  // at most about 8 a second, and not while the page is hidden. Pictures shrink while the
  // link is slow (a phone on cellular) and grow back once it keeps up: a small picture
  // several times a second beats a sharp one every second.
  const FRAME_WIDTHS = [1280, 1024, 800, 640];
  let frameSize = 0, quickFrames = 0;
  async function sendFrame() {
    clearTimeout(sendT);
    if (!device.on) return;
    if (document.hidden) { sendT = setTimeout(sendFrame, 500); return; }
    const v = $("localCam"), started = Date.now();
    if (v.videoWidth) {
      const w = Math.min(FRAME_WIDTHS[frameSize], v.videoWidth), h = Math.round(v.videoHeight * w / v.videoWidth);
      if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
      ctx.drawImage(v, 0, 0, w, h);
      const blob = await new Promise(res => canvas.toBlob(res, "image/jpeg", frameSize ? 0.7 : 0.8));
      if (!device.on) return;
      const sent = Date.now();
      try {
        const r = await fetch("/api/frame", { method: "POST", headers: { "Content-Type": "image/jpeg", ...scannerHeaders() }, body: blob });
        if (r.status === 409) {   // the app restarted, or dropped this page after a long sleep: ask for a scanner again
          try { render(await claimScanner()); }
          catch (e) { stopDeviceCamera(false); toast("Couldn't get the scanner back"); loadCameras(); return; }
        }
        if (r.status === 401) { location.href = "/lock?next=/scan"; return; }
        const took = Date.now() - sent;
        if (took > 450 && frameSize < FRAME_WIDTHS.length - 1) { frameSize++; quickFrames = 0; }
        else if (took < 150 && frameSize > 0 && ++quickFrames >= 24) { frameSize--; quickFrames = 0; }
      } catch (e) {}   // the scanner is restarting or Wi-Fi blinked: keep trying
    }
    sendT = setTimeout(sendFrame, Math.max(40, 125 - (Date.now() - started)));
  }

  function stopDeviceCamera(tellScanner) {
    clearTimeout(sendT);
    const was = device.on;
    device.on = false;
    device.stream?.getTracks().forEach(t => t.stop());
    device.stream = null; $("localCam").srcObject = null;
    document.querySelector(".camera").classList.remove("device");
    $("camDevice").hidden = true;
    fitDeviceBox();
    if (was && tellScanner) api("/api/camera/release", { token: device.token }).then(() => poll()).catch(() => {});
    camShown = null; if (state) showCamera(state.status !== "waiting");
  }
  // Closing the tab: tell the scanner right away, so it goes back to its own camera.
  addEventListener("pagehide", () => {
    if (!device.on) return;
    device.on = false;
    navigator.sendBeacon?.("/api/camera/release", new Blob([JSON.stringify({ token: device.token })], { type: "application/json" }));
  });
  // Back from the background: the scanner may have given up on this camera meanwhile, so ask for it again.
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && device.on) api("/api/camera", { index: "browser", name: device.name, token: device.token, who: device.who }).then(render).catch(() => {});
  });
  $("noCamDevice").hidden = !canUseDevice;
  $("noCamOther").hidden = canUseDevice;
  $("deviceTitle").textContent = `Scan with this ${deviceWord}`;
  $("useDeviceCamText").textContent = `Use this ${deviceWord}'s camera`;
  $("whoInput").value = device.who;
  $("whoInput").onkeydown = e => { if (e.key === "Enter") startDeviceCamera(); };
  $("useDeviceCamBtn").onclick = startDeviceCamera;
  $("usePhotosLink").onclick = () => showTab("photos");

  // Fast while watching the camera, slower on the other tabs or with no camera, and
  // not at all while the page is in the background (it saves the Pi's time).
  let pollT = null, failures = 0;
  function nextPoll() {
    clearTimeout(pollT);
    if (document.hidden) { pollT = null; return; }
    const live = !$("tab-live").hidden && state?.status !== "waiting";
    pollT = setTimeout(poll, failures ? Math.min(5000, 1000 * failures) : live ? 400 : 1500);
  }
  async function poll() {
    try {
      render(await api("/api/state"));
      failures = 0;
      if (!camsLoadedAt) { camsLoadedAt = Date.now(); loadCameras(); }
      else if (state.camera?.index !== camIndex && !$("camPick").classList.contains("busy")) { camsLoadedAt = Date.now(); loadCameras(); }
    }
    catch (e) {
      failures++;
      $("meta").classList.add("down");
      $("metaText").textContent = "Can't reach the scanner. It may be restarting; trying again…";
    }
    nextPoll();
  }
  document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); else nextPoll(); });

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

  // ---------- focus (Pi camera with autofocus): Auto, or locked at a distance ----------
  function renderFocus(f) {
    const pick = $("focusPick"), sel = $("focusSelect");
    pick.hidden = !f;
    if (!f || pick.classList.contains("busy")) return;
    const key = f.choices.join();
    if (sel.dataset.key !== key) {
      sel.innerHTML = '<option value="auto">Auto</option>' + f.choices.map(c => `<option value="${c}">${c} cm</option>`).join("");
      sel.dataset.key = key;
    }
    const want = f.cm == null ? "auto" : String(f.cm);
    if (![...sel.options].some(o => o.value === want)) sel.add(new Option(`${f.cm} cm`, want));
    if (document.activeElement !== sel) sel.value = want;
  }
  $("focusSelect").onchange = async e => {
    const v = e.target.value, pick = $("focusPick");
    pick.classList.add("busy");
    try {
      render(await api("/api/camera/focus", { cm: v === "auto" ? null : +v }));
      toast(v === "auto" ? "Focus: auto" : `Focus locked at ${v} cm`);
    } catch (err) { toast("Couldn't change the focus"); }
    pick.classList.remove("busy");
    if (state) renderFocus(state.camera?.focus);
  };

  // ---------- rotate and crop the machine camera's picture (kept on the scanner) ----------
  function renderView(s) {
    const machineCam = !!s.camera && !s.camera.browser, v = s.view || {};
    if (!machineCam) cropping = false;
    $("rotateBtn").hidden = $("cropBtn").hidden = !machineCam;
    $("uncropBtn").hidden = !machineCam || !v.crop || cropping;
    $("cropBtn").setAttribute("aria-pressed", cropping);
    $("cropBtn").querySelector("span").textContent = cropping ? "Cancel" : "Crop";
    $("cropHint").hidden = !cropping;
    $("straightBtn").hidden = !machineCam || cropping;
    $("straightBtn").textContent = v.straight ? "Straighten again" : "Straighten";
    $("unstraightBtn").hidden = !machineCam || !v.straight || cropping;
    $("autoStraightBtn").hidden = !machineCam || cropping;
    $("autoStraightBtn").setAttribute("aria-pressed", !!v.auto_straight);
    $("autoStraightBtn").textContent = v.auto_straight
      ? (v.straight ? "Auto straighten: on" : `Auto straighten: learning (${v.straight_samples || 0} cards)`)
      : "Auto straighten: off";
    $("wholeCardsBtn").hidden = !machineCam || cropping;
    $("wholeCardsBtn").setAttribute("aria-pressed", v.min_card != null);
    $("wholeCardsBtn").textContent = v.min_card != null ? "Whole cards only: on" : "Whole cards only: off";
    $("emptyBedBtn").hidden = !machineCam || cropping || v.min_card == null;
    $("emptyBedBtn").textContent = v.empty_bed ? "Bed is empty ✓" : "Bed is empty";
  }
  $("wholeCardsBtn").onclick = async () => {
    const on = state?.view?.min_card == null;
    // api() throws on a 400, but "no card in view" is worth showing as it is
    const r = await fetch("/api/settings", { method: "POST",
      headers: { "Content-Type": "application/json", ...scannerHeaders() },
      body: JSON.stringify({ min_card: on ? "bed" : null }) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) return toast(d.error || "Couldn't measure the card on the bed");
    render(d);
    toast(on ? "Only whole cards are read now: parts of a card are ignored" : "Looking for cards of any size again");
  };
  $("emptyBedBtn").onclick = async () => {
    const r = await fetch("/api/settings", { method: "POST",
      headers: { "Content-Type": "application/json", ...scannerHeaders() },
      body: JSON.stringify({ empty_bed: "now" }) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) return toast(d.error || "Couldn't look at the bed");
    render(d);
    toast("Got it: the bare bed won't be read as a card");
  };
  $("autoStraightBtn").onclick = async () => {
    const on = !(state?.view?.auto_straight);
    render(await api("/api/settings", { auto_straight: on }));
    toast(on ? "The picture now straightens itself from the cards it reads" : "Auto straighten off");
  };
  async function straighten(on) {
    // api() throws on a 400, but "no card found" is worth showing as it is
    const r = await fetch("/api/settings", { method: "POST",
      headers: { "Content-Type": "application/json", ...scannerHeaders() },
      // Undo also stops it straightening itself again
      body: JSON.stringify(on ? { straighten: true } : { straighten: false, auto_straight: false }) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) return toast(d.error || "Couldn't straighten the picture");
    render(d);
    toast(on ? "Straightened: the card on the bed now shows square" : "Showing the camera's picture as it is");
  }
  $("straightBtn").onclick = () => straighten(true);
  $("unstraightBtn").onclick = () => straighten(false);
  function setCropping(on) { cropping = on; if (on) editing = false; drag = null; if (state) render(state); }
  $("cropBtn").onclick = () => setCropping(!cropping);
  $("uncropBtn").onclick = async () => { render(await api("/api/settings", { crop: null })); toast("Showing the whole picture"); };
  $("rotateBtn").onclick = async () => {
    const r = ((state?.view?.rotate || 0) + 90) % 360;
    render(await api("/api/settings", { rotate: r }));
    toast(r ? `Turned ${r}°` : "Not turned");
  };

  // ---------- slots: boxes you draw on the picture, one per card position ----------
  function setEditing(on) { editing = on; if (on) cropping = false; drag = null; if (state) render(state); }
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
    if (!(editing || cropping) || !state || e.button) return;
    const del = editing && e.target.closest("[data-del]");
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
    if (cropping) {
      if (slot[2] - slot[0] < 0.05 || slot[3] - slot[1] < 0.05) return drawOutlines(state);   // a click, not a box
      cropping = false;
      render(await api("/api/settings", { crop: slot }));
      return toast("Cropped. Full view brings back the whole picture");
    }
    if (slot[2] - slot[0] < 0.02 || slot[3] - slot[1] < 0.02) return drawOutlines(state);   // a click, not a box
    render(await api("/api/settings", { slots: [...state.slots, slot] }));
  };
  overlay.onpointercancel = () => { drag = null; if (state) drawOutlines(state); };
  const setting = (key) => api("/api/settings", { [key]: !state[key] }).then(render);

  $("saveBtn").onclick = saveCurrent;

  // ---------- Start sorting: the machine on its own (sort_run.py) ----------
  let sortRun = null, sortT = null;
  const cash = v => v == null ? "" : "$" + Number(v).toFixed(2);
  function showSortRun(d) {
    sortRun = d;
    const btn = $("sortBtn"), running = !!d?.running;
    btn.classList.toggle("running", running);
    $("sortBtnText").textContent = running ? "Stop sorting" : "Start sorting";
    if (!d || d.error) { $("sortInfo").textContent = d?.error || ""; return; }
    const cards = d.cards || [], c = d.counts || {};
    if (!cards.length && !running) {
      $("sortInfo").innerHTML = 'Feeds every card, reads it, saves it and drops it into the bin your <a href="/bins">Bins</a> rules give it.';
      return;
    }
    const last = cards[cards.length - 1];
    const tally = (d.tally || []).map(t => `bin ${t.bin}: ${t.cards}`).join(", ");
    const now = running ? (last?.name ? `Last: <b>${last.name}</b> ${cash(last.price)} → bin ${last.bin}${last.wanted ? " (wanted)" : ""}.` : "Working…")
      : `Done: ${d.done || ""}.`;
    $("sortInfo").innerHTML = `${now} <b>${c.saved || 0}</b> saved (${cash(d.value)}), ${c.unsure || 0} unsure, ${c.unknown || 0} unread${tally ? ` · ${tally}` : ""}${d.wanted ? ` · wanted: <b>${d.wanted.found}</b> of ${d.wanted.cards} in bin ${d.wanted.bin}` : ""}${d.warning ? ` · <b>${d.warning}</b>` : ""}`;
    const w = running && d.waiting;
    $("sortWait").hidden = !w;
    if (w) $("sortWaitText").textContent = `Card ${w.n}${w.name ? ` (best guess ${w.name})` : ""}: ${w.message}`;
    if (running && !sortT) sortT = setInterval(pollSortRun, 2000);
    if (!running && sortT) { clearInterval(sortT); sortT = null; }
  }
  for (const b of document.querySelectorAll("[data-decide]")) b.onclick = async () => {
    try {
      const d = await sortApi("/api/machine/sort/decide", { action: b.dataset.decide });
      if (d.error) toast(d.error); else showSortRun(d);
    } catch (e) { toast("Couldn't reach the sorter."); }
  };
  // The run's answers carry their own "error" text (409 when one is already going, 503
  // when the machine can't), which is worth showing: so no throwing on those statuses.
  const sortApi = async (path, body) => (await fetch(path, body === undefined ? { headers: scannerHeaders() }
    : { method: "POST", headers: { "Content-Type": "application/json", ...scannerHeaders() }, body: JSON.stringify(body) })).json();
  async function pollSortRun() {
    try { showSortRun(await sortApi("/api/machine/sort")); } catch (e) { /* no machine here */ }
  }
  $("sortBtn").onclick = async () => {
    $("sortBtn").disabled = true;
    try {
      if (sortRun?.running) showSortRun(await sortApi("/api/machine/sort/stop", {}));
      else {
        const d = await sortApi("/api/machine/sort", {});
        if (d.error) toast(d.error); else { showSortRun(d); toast("Sorting. Keep your hands out of the machine."); }
      }
    } catch (e) { toast("Couldn't reach the sorter."); }
    $("sortBtn").disabled = false;
  };
  let sorterShown = false;
  function showSorter(s) {
    if (!s.sorter || sorterShown) return;
    sorterShown = true;
    $("sorter").hidden = false;
    pollSortRun();
  }
  $("foilBtn").onclick = () => setting("foil");
  $("autoBtn").onclick = () => setting("auto");
  $("collectBtn").onclick = () => setting("collect").then(() => toast(state.collect ? "Collecting scans" : "Stopped collecting"));
  $("collectSwitch").onchange = e => api("/api/settings", { collect: e.target.checked }).then(render);
  $("learnSwitch").onchange = e => api("/api/settings", { learn: e.target.checked }).then(render);
  $("wrongBtn").onclick = markWrong;
  $("printBtn").onclick = otherPrinting;
  $("whichBtn").onclick = () => openPicker({ live: true, track: selected });
  $("undoBtn").onclick = async () => { const name = state.session[0]?.name; render(await api("/api/undo", {})); if (name) toast(`Removed ${name}`); };

  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !$("pick").hidden) return closePicker();
    if (e.key === "Escape" && drawerOpen()) return setDrawer(false);
    if (e.key === "Escape" && editing) return setEditing(false);
    if (e.key === "Escape" && cropping) return setCropping(false);
    if (e.target.matches("input, textarea, select") || e.metaKey || e.ctrlKey || e.altKey || drawerOpen() || !$("pick").hidden || window.MTGMenu?.isOpen()) return;
    if (e.key === "c" || e.key === "C") return setDrawer(true);
    if (e.key === "m" || e.key === "M") return window.MTGMenu?.toggle();
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
    if (!cur) opts.unshift(`<option value="" disabled>${state?.status === "waiting" ? "No camera" : "Demo photos"}</option>`);
    if (!cams.length) opts.push('<option value="" disabled>No cameras found</option>');
    if (navigator.mediaDevices) opts.push(`<option value="browser" ${canUseDevice ? "" : "disabled"}>This ${deviceWord}'s camera${deviceHint ? " · " + deviceHint : ""}</option>`);
    sel.innerHTML = opts.join("");
    sel.value = cur ? (cur.browser ? "browser" : String(cur.index)) : "";
    camIndex = cur?.index;
  }
  $("camSelect").onchange = async e => {
    const sel = e.target, name = sel.selectedOptions[0].textContent;
    const index = /^-?\d+$/.test(sel.value) ? +sel.value : sel.value;   // "pi" is the sorter Pi's camera
    if (sel.value === "browser") {
      $("camPick").classList.add("busy");
      if (!await startDeviceCamera()) sel.value = camIndex ?? "";
      $("camPick").classList.remove("busy");
      return;
    }
    if (device.on) stopDeviceCamera(false);   // the scanner switches straight to the chosen camera
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
  function showTab(name) {
    const b = document.querySelector(`.tabs button[data-tab="${name}"]`); if (!b) return;
    for (const x of document.querySelectorAll(".tabs button")) x.setAttribute("aria-selected", x === b);
    for (const s of document.querySelectorAll(".tab")) s.hidden = s.id !== "tab-" + name;
    moveTabIndicator();
    if (name === "train") loadTraining();
    history.replaceState(null, "", name === "live" ? location.pathname : "#" + name);
    nextPoll();
  }
  for (const b of document.querySelectorAll(".tabs button")) b.onclick = () => showTab(b.dataset.tab);
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
  // Other pages link straight to a tab (/scan#photos) or to the look (/scan?customize).
  if (/^#(photos|train)$/.test(location.hash)) showTab(location.hash.slice(1));
  if (new URLSearchParams(location.search).has("customize")) setDrawer(true);
  poll();
})();
