// The Collection page: every card you've saved, with stats, filters, edits and exports.
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = v => v == null ? "No price" : "$" + Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const signed = v => (v > 0 ? "+" : v < 0 ? "−" : "") + money(Math.abs(v));
  const small = url => url ? url.replace("version=normal", "version=small") : "";
  const COLORS = { W: "White", U: "Blue", B: "Black", R: "Red", G: "Green", M: "Multicolor", C: "Colorless", "": "Unknown" };
  const RARITIES = ["mythic", "rare", "uncommon", "common", "special", "bonus"];
  const PAGE = 120;
  const PREFS_KEY = "mtg-collection-prefs";
  let data = null, shown = [], limit = PAGE, detailKey = null, toastT;
  let prefs = { view: "grid", sort: "value", breakdown: "color", measure: "cards", format: "moxfield" };
  try { prefs = { ...prefs, ...JSON.parse(localStorage.getItem(PREFS_KEY) || "{}") }; } catch (e) {}
  const savePrefs = () => { try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); } catch (e) {} };

  function toast(msg) {
    const t = $("toast"); $("toastText").textContent = msg;
    t.hidden = true; void t.offsetWidth; t.hidden = false;
    clearTimeout(toastT); toastT = setTimeout(() => t.hidden = true, 2400);
  }

  async function api(path, body) {
    const r = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const js = await r.json().catch(() => ({}));
    if (r.status === 401 && js.locked) { location.href = "/lock?next=" + encodeURIComponent(location.pathname); throw new Error("Locked"); }
    if (!r.ok) throw new Error(js.error || `Error ${r.status}`);
    return js;
  }

  async function load() {
    try { setData(await api("/api/collection")); }
    catch (e) { $("metaText").textContent = "Can't reach the scanner. Is the app running?"; document.querySelector(".meta").classList.add("down"); }
  }

  function setData(js) {
    data = js;
    document.querySelector(".meta").classList.remove("down");
    $("metaText").textContent = js.prices;
    $("refreshBtn").hidden = !js.live;
    fillFilters();
    renderTiles(); renderLine(); renderBars(); renderTop(); renderResults();
    if (detailKey) renderDetail();
    if (js.refresh?.running) watchRefresh();
  }

  const byKey = key => data.cards.find(c => c.key === key);

  // ---------- headline numbers ----------
  function renderTiles() {
    const s = data.summary;
    $("tCards").textContent = s.cards.toLocaleString();
    $("tCardsSub").textContent = `${s.names.toLocaleString()} different cards · ${s.foils.toLocaleString()} foil`;
    $("tValue").textContent = money(s.value);
    const ch = $("tValueSub");
    ch.className = "sub " + (s.change > 0 ? "up" : s.change < 0 ? "down" : "");
    ch.textContent = s.change ? `${signed(s.change)} since they were scanned` : s.unpriced ? `${s.unpriced} cards have no price` : "";
    const top = s.top.length ? byKey(s.top[0]) : null;
    $("tTop").textContent = top ? top.name : "None yet";
    $("tTopSub").textContent = top ? `${money(top.price)} · ${top.set}${top.foil ? " foil" : ""}` : "";
    $("tSets").textContent = s.set_count.toLocaleString();
    $("tSetsSub").textContent = s.sets[0] ? `Most from ${s.sets[0].name || s.sets[0].set} (${s.sets[0].cards})` : "";
  }

  // ---------- value over time (one point per day) ----------
  function renderLine() {
    const box = $("lineChart"), pts = data.history || [];
    $("histNote").textContent = pts.length ? `${pts.length} day${pts.length === 1 ? "" : "s"} noted` : "";
    if (pts.length < 2) {
      box.innerHTML = `<div class="empty">${pts.length ? `Today: <b>&nbsp;${money(pts[0].value)}&nbsp;</b>.` : ""} The chart fills in as the days go by: the total is noted once a day whenever this page is opened.</div>`;
      return;
    }
    const W = box.clientWidth || 600, H = box.clientHeight || 220, L = 56, R = 12, T = 12, B = 26;
    const vals = pts.map(p => p.value), lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * .12 || Math.max(1, hi * .05);
    const y0 = Math.max(0, lo - pad), y1 = hi + pad;
    const t = pts.map(p => new Date(p.day + "T12:00:00").getTime()), t0 = t[0], t1 = t[t.length - 1];
    const x = v => L + (t1 === t0 ? .5 : (v - t0) / (t1 - t0)) * (W - L - R);
    const y = v => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
    const ticks = [0, 1, 2, 3].map(i => y0 + (y1 - y0) * i / 3);
    const fmtDay = d => new Date(d + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
    const line = pts.map((p, i) => `${i ? "L" : "M"}${x(t[i]).toFixed(1)},${y(p.value).toFixed(1)}`).join("");
    const area = `${line}L${x(t1).toFixed(1)},${H - B}L${x(t0).toFixed(1)},${H - B}Z`;
    box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Collection value over time">
      ${ticks.map(v => `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/><text class="axis" x="${L - 8}" y="${y(v).toFixed(1)}" text-anchor="end" dominant-baseline="middle">$${Math.round(v).toLocaleString()}</text>`).join("")}
      <text class="axis" x="${L}" y="${H - 6}">${fmtDay(pts[0].day)}</text>
      <text class="axis" x="${W - R}" y="${H - 6}" text-anchor="end">${fmtDay(pts[pts.length - 1].day)}</text>
      <path class="area" d="${area}"/><path class="line" d="${line}"/>
      <line class="cross" id="cross" y1="${T}" y2="${H - B}" visibility="hidden"/>
      <circle class="dot" id="hoverDot" r="5" visibility="hidden"/>
      <circle class="dot" r="4" cx="${x(t1).toFixed(1)}" cy="${y(vals[vals.length - 1]).toFixed(1)}"/>
      <rect x="${L}" y="0" width="${W - L - R}" height="${H}" fill="transparent" id="hit"/>
    </svg><div class="tip" id="tip" hidden></div>`;
    const hit = $("hit"), tip = $("tip"), cross = $("cross"), dot = $("hoverDot");
    hit.onpointermove = e => {
      const r = box.getBoundingClientRect(), mx = (e.clientX - r.left) * W / r.width;
      let i = 0; t.forEach((v, j) => { if (Math.abs(x(v) - mx) < Math.abs(x(t[i]) - mx)) i = j; });
      const px = x(t[i]), py = y(pts[i].value);
      cross.setAttribute("x1", px); cross.setAttribute("x2", px); cross.setAttribute("visibility", "visible");
      dot.setAttribute("cx", px); dot.setAttribute("cy", py); dot.setAttribute("visibility", "visible");
      tip.hidden = false; tip.style.left = (px * r.width / W) + "px"; tip.style.top = (py * r.height / H - 8) + "px";
      tip.innerHTML = `<b>${money(pts[i].value)}</b>${fmtDay(pts[i].day)} · ${pts[i].cards.toLocaleString()} cards`;
    };
    hit.onpointerleave = () => { tip.hidden = true; cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); };
  }
  let resizeT; addEventListener("resize", () => { clearTimeout(resizeT); resizeT = setTimeout(() => data && renderLine(), 150); });

  // ---------- breakdown ----------
  function breakdownRows() {
    const s = data.summary, m = prefs.measure;
    const binLabel = b => (data.bins.find(x => String(x.bin) === String(b)) || {}).label || `Bin ${b}`;
    // (The server's JSON comes with its keys in A-Z order, so put them back in card order.)
    const inOrder = (obj, order) => Object.entries(obj).sort((x, y) => (order.indexOf(x[0]) + 99) % 99 - (order.indexOf(y[0]) + 99) % 99);
    if (prefs.breakdown === "color") return inOrder(s.by_color, Object.keys(COLORS)).map(([k, v]) => ({ label: COLORS[k] ?? k, swatch: `var(--mana-${k})`, n: v[m], filter: ["fColor", k] }));
    if (prefs.breakdown === "rarity") return inOrder(s.by_rarity, RARITIES).map(([k, v]) => ({ label: k ? k[0].toUpperCase() + k.slice(1) : "Unknown", swatch: "var(--accent)", n: v[m], filter: ["fRarity", k] }));
    if (prefs.breakdown === "bin") return Object.entries(s.by_bin).sort((a, b) => b[0] - a[0]).map(([k, v]) => ({ label: `${k} · ${binLabel(k)}`, swatch: `var(--bin${k})`, n: v[m], filter: ["fBin", k] }));
    return s.sets.map(v => ({ label: v.name || v.set, swatch: "var(--accent)", n: v[m], filter: ["fSet", v.set] }));
  }
  function renderBars() {
    for (const b of $("breakSeg").children) b.setAttribute("aria-pressed", b.dataset.v === prefs.breakdown);
    for (const b of $("measureSeg").children) b.setAttribute("aria-pressed", b.dataset.v === prefs.measure);
    const rows = breakdownRows().filter(r => r.n > 0), max = Math.max(1, ...rows.map(r => r.n));
    const fmt = n => prefs.measure === "value" ? money(n) : n.toLocaleString();
    $("bars").innerHTML = rows.length ? rows.map((r, i) => `<div class="bar-row" data-i="${i}" title="Show only ${esc(r.label)}">
        <span class="name"><i style="background:${r.swatch}"></i>${esc(r.label)}</span>
        <span class="track"><span class="fill" style="width:${(100 * r.n / max).toFixed(1)}%;background:${r.swatch}"></span></span>
        <span class="n">${fmt(r.n)}</span></div>`).join("") : '<p class="none">Nothing to show yet</p>';
    $("bars").onclick = e => {
      const row = e.target.closest(".bar-row"); if (!row) return;
      const [id, v] = rows[+row.dataset.i].filter;
      clearFilters(false); $(id).value = v; applyFilters();
      document.querySelector(".browse").scrollIntoView({ behavior: "smooth", block: "start" });
    };
  }
  $("breakSeg").onclick = e => { const b = e.target.closest("button"); if (b) { prefs.breakdown = b.dataset.v; savePrefs(); renderBars(); } };
  $("measureSeg").onclick = e => { const b = e.target.closest("button"); if (b) { prefs.measure = b.dataset.v; savePrefs(); renderBars(); } };

  // ---------- card tiles ----------
  function tile(c, extra = "") {
    const img = c.image ? `<img src="${esc(small(c.image))}" alt="" loading="lazy">` : `<span class="noimg">${esc(c.name)}</span>`;
    return `<button class="tile${c.foil ? " foil" : ""}${extra}" data-key="${esc(c.key)}" title="${esc(c.name)}">
      <span class="art">${img}${c.qty > 1 ? `<span class="qty">×${c.qty}</span>` : ""}${c.foil ? '<span class="foil-badge">FOIL</span>' : ""}</span>
      <b>${esc(c.name)}</b><span>${esc(c.set)} #${esc(c.number)}<em>${money(c.price)}</em></span></button>`;
  }
  function renderTop() {
    const top = data.summary.top.map(byKey).filter(Boolean);
    $("topStrip").innerHTML = top.length ? top.map(c => tile(c)).join("") : '<p class="none">Scan some cards and they show up here.</p>';
  }
  $("topStrip").onclick = e => { const t = e.target.closest(".tile"); if (t) openDetail(t.dataset.key); };

  // ---------- filters and sorting ----------
  const FILTER_IDS = ["q", "fColor", "fRarity", "fSet", "fBin", "fFoil", "fMin", "fMax"];
  function fillSelect(id, options, first) {
    const sel = $(id), keep = sel.value;
    sel.innerHTML = `<option value="">${first}</option>` + options.map(([v, label]) => `<option value="${esc(v)}">${esc(label)}</option>`).join("");
    sel.value = options.some(([v]) => String(v) === keep) ? keep : "";
  }
  function fillFilters() {
    const cards = data.cards;
    const colors = Object.keys(COLORS).filter(k => cards.some(c => c.color === k));
    fillSelect("fColor", colors.map(k => [k, COLORS[k]]), "All colors");
    const rar = [...new Set(cards.map(c => c.rarity))].sort((a, b) => (RARITIES.indexOf(a) + 99) % 99 - (RARITIES.indexOf(b) + 99) % 99);
    fillSelect("fRarity", rar.map(r => [r, r ? r[0].toUpperCase() + r.slice(1) : "Unknown"]), "All rarities");
    const sets = {}; for (const c of cards) sets[c.set] = c.set_name || c.set;
    fillSelect("fSet", Object.entries(sets).sort((a, b) => a[1].localeCompare(b[1])).map(([k, n]) => [k, `${n} (${k})`]), "All sets");
    fillSelect("fBin", data.bins.map(b => [b.bin, `Bin ${b.bin} · ${b.label}`]), "All bins");
    $("sort").value = prefs.sort;
  }
  const SORTS = {
    value: (a, b) => (b.value ?? -1) - (a.value ?? -1),
    price: (a, b) => (b.price ?? -1) - (a.price ?? -1),
    cheap: (a, b) => (a.price ?? 1e9) - (b.price ?? 1e9),
    name: (a, b) => a.name.localeCompare(b.name),
    set: (a, b) => a.set.localeCompare(b.set) || a.number.localeCompare(b.number, undefined, { numeric: true }),
    new: (a, b) => b.last.localeCompare(a.last),
    old: (a, b) => a.first.localeCompare(b.first),
    qty: (a, b) => b.qty - a.qty,
    up: (a, b) => (b.change ?? -1e9) - (a.change ?? -1e9),
    down: (a, b) => (a.change ?? 1e9) - (b.change ?? 1e9),
  };
  function filtered() {
    const q = $("q").value.trim().toLowerCase(), f = id => $(id).value;
    const min = parseFloat(f("fMin")), max = parseFloat(f("fMax"));
    return data.cards.filter(c =>
      (!q || `${c.name} ${c.set} ${c.set_name} #${c.number} ${c.number}`.toLowerCase().includes(q)) &&
      (!f("fColor") || c.color === f("fColor")) && (!f("fRarity") || c.rarity === f("fRarity")) &&
      (!f("fSet") || c.set === f("fSet")) && (!f("fBin") || String(c.bin) === f("fBin")) &&
      (!f("fFoil") || c.foil === (f("fFoil") === "foil")) &&
      (isNaN(min) || (c.price ?? -1) >= min) && (isNaN(max) || (c.price != null && c.price <= max))
    ).sort((a, b) => SORTS[prefs.sort](a, b) || a.name.localeCompare(b.name));
  }
  function applyFilters() { limit = PAGE; renderResults(); }
  function clearFilters(render = true) { for (const id of FILTER_IDS) $(id).value = ""; if (render) applyFilters(); }
  for (const id of FILTER_IDS) $(id).addEventListener("input", applyFilters);
  $("sort").onchange = () => { prefs.sort = $("sort").value; savePrefs(); applyFilters(); };
  $("clearFilters").onclick = () => clearFilters();

  function renderResults() {
    shown = filtered();
    const active = FILTER_IDS.some(id => $(id).value);
    $("clearFilters").hidden = !active;
    const cards = shown.reduce((n, c) => n + c.qty, 0), value = shown.reduce((v, c) => v + (c.value || 0), 0);
    $("showing").textContent = data.cards.length ? (active ? `Showing ${cards.toLocaleString()} of ${data.summary.cards.toLocaleString()} cards · ${money(value)}` : `${cards.toLocaleString()} cards · ${money(value)}`) : "";
    for (const b of $("viewSeg").children) b.setAttribute("aria-pressed", b.dataset.v === prefs.view);
    const page = shown.slice(0, limit);
    if (!data.cards.length) $("results").innerHTML = `<p class="results-empty">No cards saved yet. Scan some on the <a href="/">Scanner</a>, or press <b>Add a card</b>.</p>`;
    else if (!shown.length) $("results").innerHTML = '<p class="results-empty">No cards match these filters.</p>';
    else if (prefs.view === "grid") $("results").innerHTML = `<div class="results-grid">${page.map(c => tile(c)).join("")}</div>`;
    else $("results").innerHTML = `<div class="table-wrap"><table class="list"><thead><tr>
        <th>Card</th><th class="hide-sm">Set</th><th class="hide-sm">Rarity</th><th>Copies</th><th class="num">Price</th><th class="num hide-sm">Value</th><th class="num hide-sm">Since scanned</th><th class="hide-sm">Bin</th></tr></thead><tbody>
      ${page.map(c => `<tr data-key="${esc(c.key)}">
        <td class="card-cell">${c.image ? `<img class="thumb" src="${esc(small(c.image))}" alt="" loading="lazy">` : '<span class="thumb"></span>'}<span><span class="dotc" style="background:var(--mana-${esc(c.color)})" title="${esc(COLORS[c.color] ?? "")}"></span><span class="nm">${esc(c.name)}</span>${c.foil ? '<span class="foil-tag">foil</span>' : ""}<small class="sub show-sm">${esc(c.set)} #${esc(c.number)}</small></span></td>
        <td class="hide-sm">${esc(c.set)} #${esc(c.number)}</td>
        <td class="rar hide-sm">${esc(c.rarity)}</td>
        <td class="qty-cell"><button data-step="-1" aria-label="One fewer"><svg><use href="#i-minus"/></svg></button><b>${c.qty}</b><button data-step="1" aria-label="One more"><svg><use href="#i-plus"/></svg></button></td>
        <td class="num">${money(c.price)}</td>
        <td class="num hide-sm">${c.value == null ? "" : money(c.value)}</td>
        <td class="num chg hide-sm ${c.change > 0 ? "up" : c.change < 0 ? "down" : ""}">${c.change ? signed(c.change) : ""}</td>
        <td class="hide-sm"><span class="pill bin-${c.bin}">${c.bin}</span></td></tr>`).join("")}</tbody></table></div>`;
    $("moreBtn").hidden = shown.length <= limit;
    $("moreBtn").textContent = `Show more (${(shown.length - limit).toLocaleString()} left)`;
  }
  $("moreBtn").onclick = () => { limit += PAGE * 2; renderResults(); };
  $("viewSeg").onclick = e => { const b = e.target.closest("button"); if (b) setView(b.dataset.v); };
  function setView(v) { prefs.view = v; savePrefs(); renderResults(); }
  $("results").onclick = async e => {
    const step = e.target.closest("[data-step]"), row = e.target.closest("[data-key]");
    if (!row) return;
    if (step) {
      const c = byKey(row.dataset.key), n = c.qty + +step.dataset.step;
      if (n < 1 && !confirm(`Delete ${c.name} (${c.set}) from the collection?`)) return;
      return edit({ key: c.key, qty: Math.max(0, n) }, n < 1 ? `Deleted ${c.name}` : null);
    }
    openDetail(row.dataset.key);
  };

  async function edit(change, message) {
    try { setData(await api("/api/collection/edit", change)); if (message) toast(message); }
    catch (e) { toast(e.message); load(); }
  }

  // ---------- one card ----------
  function openModal(id) { $(id).hidden = false; }
  function closeModal(id) { $(id).hidden = true; if (id === "detail") detailKey = null; }
  for (const m of document.querySelectorAll(".modal")) {
    m.addEventListener("click", e => { if (e.target === m || e.target.closest("[data-close]")) closeModal(m.id); });
  }
  function openDetail(key) {
    detailKey = key; $("dPrintList").hidden = true; $("dImg").removeAttribute("src");
    renderDetail(); openModal("detail");
  }
  function renderDetail() {
    const c = byKey(detailKey);
    if (!c) return closeModal("detail");
    $("dName").textContent = c.name;
    if (c.image && $("dImg").getAttribute("src") !== c.image) $("dImg").src = c.image;
    $("dImg").alt = c.name;
    $("dArt").classList.toggle("foil", c.foil);
    $("dSet").textContent = `${c.set_name || c.set} · ${c.set} #${c.number}${c.rarity ? " · " + c.rarity : ""}`;
    $("dPrice").textContent = money(c.price) + (c.qty > 1 && c.value != null ? `  ×${c.qty} = ${money(c.value)}` : "");
    $("dSource").textContent = c.price_source || "";
    const facts = [
      ["Color", COLORS[c.color] ?? "Unknown"],
      ["Bin now", `${c.bin} · ${c.bin_label}`],
      c.sorted_into && c.sorted_into !== c.bin_label ? ["Sorted into", c.sorted_into] : null,
      c.scanned_price != null ? ["When scanned", money(c.scanned_price) + (c.change ? ` (${signed(c.change)} since)` : "")] : null,
      c.first ? ["First scanned", new Date(c.first).toLocaleString()] : null,
      c.last && c.last !== c.first ? ["Last scanned", new Date(c.last).toLocaleString()] : null,
    ].filter(Boolean);
    $("dFacts").innerHTML = facts.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("");
    $("dQty").textContent = c.qty;
    $("dFoil").setAttribute("aria-pressed", c.foil);
    $("dScryfall").hidden = !c.scryfall; $("dScryfall").href = c.scryfall || "#";
  }
  $("dPlus").onclick = () => { const c = byKey(detailKey); edit({ key: c.key, qty: c.qty + 1 }); };
  $("dMinus").onclick = () => {
    const c = byKey(detailKey);
    if (c.qty <= 1) return $("dDelete").click();
    edit({ key: c.key, qty: c.qty - 1 });
  };
  $("dFoil").onclick = () => {
    const c = byKey(detailKey);
    detailKey = c.key.replace(/#(foil|normal)$/, c.foil ? "#normal" : "#foil");   // joins any copies already there
    edit({ key: c.key, foil: !c.foil }, c.foil ? "Marked as normal" : "Marked as foil");
  };
  $("dDelete").onclick = () => {
    const c = byKey(detailKey);
    if (!confirm(`Delete all ${c.qty} of ${c.name} (${c.set}${c.foil ? " foil" : ""}) from the collection?`)) return;
    closeModal("detail"); edit({ key: c.key, delete: true }, `Deleted ${c.name}`);
  };
  $("dPrintings").onclick = async () => {
    const c = byKey(detailKey), list = $("dPrintList");
    list.hidden = false; list.innerHTML = '<p class="sub">Looking up every printing…</p>';
    try {
      const prints = await api(`/api/printings?name=${encodeURIComponent(c.name)}&foil=${c.foil ? 1 : 0}`);
      list.innerHTML = `<p class="sub">Pick the printing you really have:</p><div class="print-grid">` + prints.map(p => tile({ ...p, key: p.id, qty: 1, foil: c.foil }, p.id === c.id ? " is-current" : "")).join("") + "</div>";
    } catch (e) { list.innerHTML = `<p class="sub">${esc(e.message)}</p>`; }
  };
  $("dPrintList").onclick = e => {
    const t = e.target.closest(".tile"), c = byKey(detailKey);
    if (!t || t.dataset.key === c.id) return;
    detailKey = `${t.dataset.key}#${c.foil ? "foil" : "normal"}`;
    $("dPrintList").hidden = true;
    edit({ key: c.key, printing: t.dataset.key }, "Printing changed");
  };

  // ---------- add a card by hand ----------
  let addT, addN = 0, addName = "";
  function openAdd() { openModal("add"); $("addInput").value = ""; $("addAllPrints").hidden = true; $("addResults").innerHTML = '<p class="pick-hint">Type at least 2 letters of the card\'s name</p>'; $("addInput").focus(); }
  function showPicks(cards, hint) {
    $("addResults").innerHTML = cards.length ? cards.map(c => `<button class="pick-card" data-id="${esc(c.id)}" data-name="${esc(c.name)}">
        <img src="${esc(small(c.image))}" alt="" loading="lazy"><b>${esc(c.name)}</b><span>${esc(c.set)} #${esc(c.number)} · ${money(c.price)}</span></button>`).join("")
      : `<p class="pick-hint">${hint}</p>`;
  }
  $("addBtn").onclick = openAdd;
  $("addInput").oninput = () => {
    clearTimeout(addT);
    addT = setTimeout(async () => {
      const q = $("addInput").value.trim(), n = ++addN;
      if (q.length < 2) return showPicks([], "Type at least 2 letters of the card's name");
      const cards = await api("/api/search?q=" + encodeURIComponent(q)).catch(() => []);
      if (n !== addN) return;
      addName = cards[0]?.name || "";
      $("addAllPrints").hidden = !addName || !data.live;
      $("addAllPrints").textContent = `Show every printing of ${addName}`;
      showPicks(cards, "No card by that name in the scanner's database");
    }, 180);
  };
  $("addInput").onkeydown = e => { if (e.key === "Enter") $("addResults").querySelector(".pick-card")?.click(); };
  $("addAllPrints").onclick = async () => {
    $("addResults").innerHTML = '<p class="pick-hint">Looking up every printing…</p>';
    showPicks(await api(`/api/printings?name=${encodeURIComponent(addName)}`).catch(() => []), "Couldn't look up the printings");
  };
  $("addResults").onclick = async e => {
    const b = e.target.closest(".pick-card"); if (!b) return;
    const qty = Math.max(1, Math.min(100, parseInt($("addQty").value) || 1));
    try {
      setData(await api("/api/collection/add", { id: b.dataset.id, qty, foil: $("addFoil").checked }));
      toast(`Added ${qty > 1 ? qty + " × " : ""}${b.dataset.name}`);
      $("addInput").select();
    } catch (err) { toast(err.message); }
  };

  // ---------- export ----------
  function openExport() {
    $("formats").innerHTML = data.exports.map(f => `<button class="format" data-id="${f.id}" aria-pressed="${f.id === prefs.format}"><b>${esc(f.label)}</b><small>${esc(f.hint)}</small></button>`).join("");
    const active = shown.length !== data.cards.length;
    $("exOnly").checked = active; $("exOnly").disabled = !active;
    $("exOnlyText").textContent = active ? `Only the ${shown.reduce((n, c) => n + c.qty, 0).toLocaleString()} cards showing` : "Only the cards showing (set filters first)";
    openModal("export");
  }
  $("exportBtn").onclick = openExport;
  $("formats").onclick = e => {
    const b = e.target.closest(".format"); if (!b) return;
    prefs.format = b.dataset.id; savePrefs();
    for (const x of $("formats").children) x.setAttribute("aria-pressed", x === b);
  };
  async function exportFile() {
    const body = { format: prefs.format };
    if ($("exOnly").checked) body.keys = shown.map(c => c.key);
    const r = await fetch("/api/collection/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error("Export failed");
    const name = (r.headers.get("Content-Disposition") || "").match(/filename="([^"]+)"/)?.[1] || "collection.csv";
    return { name, text: await r.text() };
  }
  $("exGo").onclick = async () => {
    try {
      const { name, text } = await exportFile();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([text], { type: name.endsWith(".csv") ? "text/csv" : "text/plain" }));
      a.download = name; document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
      toast(`Downloaded ${name}`);
    } catch (e) { toast(e.message); }
  };
  $("exCopy").onclick = async () => {
    try {
      const { text } = await exportFile();
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
      else {   // the Pi's page is plain http, where the clipboard API isn't allowed
        const t = document.createElement("textarea"); t.value = text; t.style.position = "fixed"; t.style.opacity = "0";
        document.body.append(t); t.select(); document.execCommand("copy"); t.remove();
      }
      toast("Copied. Paste it into the other site");
    } catch (e) { toast("Couldn't copy: " + e.message); }
  };

  // ---------- refresh prices ----------
  let refreshing = false;
  async function watchRefresh() {
    if (refreshing) return;
    refreshing = true; $("refreshBtn").disabled = true;
    try {
      for (;;) {
        const { refresh: r } = await api("/api/collection/refresh");
        $("refreshText").textContent = r.running ? `Prices ${r.done}/${r.total}…` : "Refresh prices";
        if (!r.running) {
          refreshing = false; $("refreshBtn").disabled = false;
          toast(r.error || `Updated ${r.updated.toLocaleString()} prices`);
          return load();
        }
        await new Promise(res => setTimeout(res, 800));
      }
    } catch (e) { refreshing = false; $("refreshBtn").disabled = false; $("refreshText").textContent = "Refresh prices"; }
  }
  $("refreshBtn").onclick = async () => {
    try { await api("/api/collection/refresh", {}); watchRefresh(); } catch (e) { toast(e.message); }
  };

  // ---------- keyboard ----------
  document.addEventListener("keydown", e => {
    const open = [...document.querySelectorAll(".modal")].find(m => !m.hidden);
    if (e.key === "Escape" && open) return closeModal(open.id);
    if (open || e.target.matches("input, textarea, select") || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "/") { e.preventDefault(); $("q").focus(); }
    else if (e.key === "g" || e.key === "G") setView("grid");
    else if (e.key === "l" || e.key === "L") setView("list");
    else if (e.key === "n" || e.key === "N") { e.preventDefault(); openAdd(); }
    else if ((e.key === "e" || e.key === "E") && data) openExport();
  });

  load();
})();
