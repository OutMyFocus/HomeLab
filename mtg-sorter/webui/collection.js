// The Collection page: every card you've saved, with stats, filters, edits and exports.
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = v => v == null ? "No price" : "$" + Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const signed = v => (v > 0 ? "+" : v < 0 ? "−" : "") + money(Math.abs(v));
  const small = url => url ? url.replace("version=normal", "version=small") : "";
  // The small picture where it's enough, the sharp one on a phone's screen or a big tile:
  // the browser picks from the two by how wide the picture is shown.
  const picture = (c, sizes) => c.image
    ? `<img src="${esc(small(c.image))}" srcset="${esc(small(c.image))} 146w, ${esc(c.image)} 488w" sizes="${sizes}" alt="" loading="lazy" decoding="async">`
    : `<span class="noimg">${esc(c.name)}</span>`;
  const COLORS = { W: "White", U: "Blue", B: "Black", R: "Red", G: "Green", M: "Multicolor", C: "Colorless", "": "Unknown" };
  const RARITIES = ["mythic", "rare", "uncommon", "common", "special", "bonus"];
  const PAGE = 120;
  const PREFS_KEY = "mtg-collection-prefs";
  let data = null, shown = [], limit = PAGE, detailKey = null, toastT;
  let selecting = false, binderFirst = 0;
  const picked = new Set();   // the keys of the cards picked with Select
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
    // [code, name] pairs from the server, in their order (best condition first)
    data.condOrder = js.conditions || []; data.conditions = Object.fromEntries(data.condOrder);
    data.langOrder = js.languages || []; data.languages = Object.fromEntries(data.langOrder);
    document.querySelector(".meta").classList.remove("down");
    $("metaText").textContent = js.prices;
    $("refreshBtn").hidden = !js.live;
    fillFilters();
    for (const k of [...picked]) if (!byKeyIn(js, k)) picked.delete(k);   // deleted elsewhere
    renderTiles(); renderLine(); renderBars(); renderTop(); renderResults();
    if (detailKey) renderDetail();
    if (js.refresh?.running) watchRefresh();
  }

  const byKey = key => data.cards.find(c => c.key === key);
  const byKeyIn = (js, key) => js.cards.some(c => c.key === key);

  // ---------- headline numbers ----------
  function renderTiles() {
    const s = data.summary;
    $("tCards").textContent = s.cards.toLocaleString();
    $("tCardsSub").textContent = `${s.names.toLocaleString()} different cards · ${s.foils.toLocaleString()} foil${s.proxies ? ` · ${s.proxies.toLocaleString()} prox${s.proxies === 1 ? "y" : "ies"}` : ""}`;
    $("tCardsSub").title = s.proxies ? `Proxies aren't counted in the value (the real cards would be ${money(s.proxy_value)})` : "";
    $("tValue").textContent = money(s.value);
    const ch = $("tValueSub");
    ch.className = "sub " + (s.change > 0 ? "up" : s.change < 0 ? "down" : "");
    ch.textContent = s.change ? `${signed(s.change)} since they were scanned` : s.unpriced ? `${s.unpriced} cards have no price` : "";
    if (s.paid_cards) {   // what you paid, where you entered it, beats "since scanned"
      ch.className = "sub " + (s.gain > 0 ? "up" : s.gain < 0 ? "down" : "");
      ch.textContent = `${signed(s.gain)} on the ${money(s.paid)} you paid`;
      ch.title = `For the ${s.paid_cards.toLocaleString()} cards you entered a price paid for`;
    }
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
      box.innerHTML = `<div class="empty"><p>${pts.length ? `Today: <b>${money(pts[0].value)}</b>. ` : ""}The chart fills in as the days go by: the total is noted once a day whenever this page or Home is opened.</p></div>`;
      return;
    }
    if (window.SortRCharts) {   // the same smooth line, hover readout and colors as Home
      SortRCharts.line(box, pts, { fmt: (v, isAxis, step) => isAxis ? SortRCharts.axisMoney(v, step) : money(v), tip: p => `${money(p.value)}${p.cards ? ` · ${p.cards.toLocaleString()} cards` : ""}` });
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
    if (prefs.breakdown === "tag") return (s.tags || []).map(t => ({ label: t.tag, swatch: "var(--accent)", n: t[m], filter: ["fTag", t.tag] }));
    if (prefs.breakdown === "condition") {
      const byCond = {};
      for (const c of data.cards) { const x = byCond[c.condition] ||= { cards: 0, value: 0 }; x.cards += c.qty; x.value += c.value || 0; }
      return data.condOrder.map(([k]) => k).filter(k => byCond[k]).map(k => ({ label: `${k} · ${data.conditions[k]}`, swatch: "var(--accent)", n: byCond[k][m], filter: ["fCond", k] }));
    }
    return s.sets.map(v => ({ label: v.name || v.set, swatch: "var(--accent)", n: v[m], filter: ["fSet", v.set] }));
  }
  function renderBars() {
    for (const b of $("breakSeg").children) b.setAttribute("aria-pressed", b.dataset.v === prefs.breakdown);
    for (const b of $("measureSeg").children) b.setAttribute("aria-pressed", b.dataset.v === prefs.measure);
    const rows = breakdownRows().filter(r => r.n > 0), max = Math.max(1, ...rows.map(r => r.n));
    const fmt = n => prefs.measure === "value" ? money(n) : n.toLocaleString();
    const none = prefs.breakdown === "tag" ? "No tags yet. Open a card and add one, or tag many with Select." : "Nothing to show yet";
    $("bars").innerHTML = rows.length ? rows.map((r, i) => `<div class="bar-row" data-i="${i}" title="Show only ${esc(r.label)}">
        <span class="name"><i style="background:${r.swatch}"></i>${esc(r.label)}</span>
        <span class="track"><span class="fill" style="width:${(100 * r.n / max).toFixed(1)}%;background:${r.swatch}"></span></span>
        <span class="n">${fmt(r.n)}</span></div>`).join("") : `<p class="none">${none}</p>`;
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
  // Condition (when not near mint) and language (when not English), on the card's corner.
  const badges = c => {
    const b = [c.condition && c.condition !== "NM" ? (c.mixed ? c.condition + "+" : c.condition) : "", c.language && c.language !== "EN" ? c.language : ""].filter(Boolean);
    return b.length ? `<span class="cond-badge" title="${esc([data?.conditions?.[c.condition], data?.languages?.[c.language]].filter(Boolean).join(", "))}">${b.map(esc).join(" · ")}</span>` : "";
  };
  // A proxy: kept, but worth nothing to the collection (its price is the real card's)
  const proxyBadge = c => c.proxy ? '<span class="proxy-badge" title="Proxy: not counted in the value">PROXY</span>' : "";
  const proxyKey = (key, on) => key.replace(/#proxy$/, "") + (on ? "#proxy" : "");
  const PICK_MARK = '<i class="pick-mark" aria-hidden="true"><svg><use href="#i-check"/></svg></i>';
  function tile(c, extra = "", sizes = "(max-width: 600px) 46vw, 170px") {
    const on = selecting && picked.has(c.key);
    return `<button class="tile${c.foil ? " foil" : ""}${c.proxy ? " proxy" : ""}${on ? " picked" : ""}${extra}" data-key="${esc(c.key)}" title="${esc(c.name)}"${selecting && !extra ? ` aria-pressed="${on}"` : ""}>
      <span class="art">${picture(c, sizes)}${c.qty > 1 ? `<span class="qty">×${c.qty}</span>` : ""}${c.foil ? '<span class="foil-badge">FOIL</span>' : ""}${badges(c)}${proxyBadge(c)}${selecting && !extra ? PICK_MARK : ""}</span>
      <b>${esc(c.name)}</b><span>${esc(c.set)} #${esc(c.number)}<em>${money(c.price)}</em></span></button>`;
  }
  function renderTop() {
    const top = data.summary.top.map(byKey).filter(Boolean);
    $("topStrip").innerHTML = top.length ? top.map(c => tile(c, " in-strip", "130px")).join("") : '<p class="none">Scan some cards and they show up here.</p>';
  }
  $("topStrip").onclick = e => { const t = e.target.closest(".tile"); if (t) openDetail(t.dataset.key); };

  // ---------- filters and sorting ----------
  const FILTER_IDS = ["q", "fColor", "fRarity", "fSet", "fBin", "fTag", "fCond", "fLang", "fFoil", "fProxy", "fMin", "fMax"];
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
    const tags = data.summary.tags || [];
    fillSelect("fTag", tags.map(t => [t.tag, `${t.tag} (${t.cards})`]), tags.length ? "All tags" : "No tags yet");
    $("fTag").hidden = !tags.length && !$("fTag").value;
    $("tagList").innerHTML = tags.map(t => `<option value="${esc(t.tag)}">`).join("");
    const conds = data.condOrder.map(([k]) => k).filter(k => cards.some(c => c.condition === k));
    fillSelect("fCond", conds.map(k => [k, `${k} · ${data.conditions[k]}`]), "Any condition");
    $("fCond").hidden = conds.length < 2 && !$("fCond").value;
    const langs = data.langOrder.map(([k]) => k).filter(k => cards.some(c => c.language === k));
    fillSelect("fLang", langs.map(k => [k, data.languages[k]]), "Any language");
    $("fLang").hidden = langs.length < 2 && !$("fLang").value;
    $("fProxy").hidden = !cards.some(c => c.proxy) && !$("fProxy").value;
    $("sort").value = prefs.sort;
  }
  const SORTS = {
    value: (a, b) => (b.value ?? -1) - (a.value ?? -1),
    price: (a, b) => (b.price ?? -1) - (a.price ?? -1),
    cheap: (a, b) => (a.price ?? 1e9) - (b.price ?? 1e9),
    mtl: (a, b) => (b.mtl?.price ?? -1) - (a.mtl?.price ?? -1),
    name: (a, b) => a.name.localeCompare(b.name),
    set: (a, b) => a.set.localeCompare(b.set) || a.number.localeCompare(b.number, undefined, { numeric: true }),
    new: (a, b) => b.last.localeCompare(a.last),
    old: (a, b) => a.first.localeCompare(b.first),
    qty: (a, b) => b.qty - a.qty,
    up: (a, b) => (b.change ?? -1e9) - (a.change ?? -1e9),
    down: (a, b) => (a.change ?? 1e9) - (b.change ?? 1e9),
    rise: (a, b) => (b.trend?.change ?? -1e9) - (a.trend?.change ?? -1e9),
    fall: (a, b) => (a.trend?.change ?? 1e9) - (b.trend?.change ?? 1e9),
    gain: (a, b) => (b.gain ?? -1e9) - (a.gain ?? -1e9),
    loss: (a, b) => (a.gain ?? 1e9) - (b.gain ?? 1e9),
  };
  function filtered() {
    const q = $("q").value.trim().toLowerCase(), f = id => $(id).value;
    const min = parseFloat(f("fMin")), max = parseFloat(f("fMax"));
    return data.cards.filter(c =>
      (!q || `${c.name} ${c.set} ${c.set_name} #${c.number} ${c.number}`.toLowerCase().includes(q)) &&
      (!f("fColor") || c.color === f("fColor")) && (!f("fRarity") || c.rarity === f("fRarity")) &&
      (!f("fSet") || c.set === f("fSet")) && (!f("fBin") || String(c.bin) === f("fBin")) &&
      (!f("fTag") || (c.tags || []).includes(f("fTag"))) && (!f("fCond") || c.condition === f("fCond")) &&
      (!f("fLang") || c.language === f("fLang")) &&
      (!f("fFoil") || c.foil === (f("fFoil") === "foil")) &&
      (!f("fProxy") || !!c.proxy === (f("fProxy") === "proxy")) &&
      (isNaN(min) || (c.price ?? -1) >= min) && (isNaN(max) || (c.price != null && c.price <= max))
    ).sort((a, b) => SORTS[prefs.sort](a, b) || a.name.localeCompare(b.name));
  }
  function applyFilters() { limit = PAGE; binderFirst = 0; renderResults(); syncUrl(); }
  function clearFilters(render = true) { for (const id of FILTER_IDS) $(id).value = ""; if (render) applyFilters(); }
  for (const id of FILTER_IDS) $(id).addEventListener("input", applyFilters);
  $("sort").onchange = () => { prefs.sort = $("sort").value; savePrefs(); applyFilters(); };

  // The filters live in the address too, so Back, a refresh or a bookmark keeps them
  // (/collection?color=U&rarity=mythic&min=5).
  const URL_KEYS = { q: "q", color: "fColor", rarity: "fRarity", set: "fSet", bin: "fBin", tag: "fTag", cond: "fCond", lang: "fLang", foil: "fFoil", proxy: "fProxy", min: "fMin", max: "fMax" };
  function syncUrl() {
    const ps = new URLSearchParams();
    for (const [k, id] of Object.entries(URL_KEYS)) if ($(id).value.trim()) ps.set(k, $(id).value.trim());
    if (prefs.sort !== "value") ps.set("sort", prefs.sort);
    const qs = ps.toString();
    history.replaceState(null, "", location.pathname + (qs ? "?" + qs : ""));
  }

  // What's filtered, as chips you can take off one at a time.
  function activeChips() {
    const f = id => $(id).value.trim(), out = [];
    const label = id => $(id).selectedOptions[0]?.textContent || f(id);
    if (f("q")) out.push(["q", `“${f("q")}”`]);
    if (f("fColor")) out.push(["fColor", COLORS[f("fColor")] ?? f("fColor")]);
    if (f("fRarity")) out.push(["fRarity", label("fRarity")]);
    if (f("fSet")) out.push(["fSet", label("fSet")]);
    if (f("fBin")) out.push(["fBin", label("fBin")]);
    if (f("fTag")) out.push(["fTag", "Tag: " + f("fTag")]);
    if (f("fCond")) out.push(["fCond", label("fCond")]);
    if (f("fLang")) out.push(["fLang", label("fLang")]);
    if (f("fFoil")) out.push(["fFoil", label("fFoil")]);
    if (f("fProxy")) out.push(["fProxy", label("fProxy")]);
    const lo = f("fMin"), hi = f("fMax");
    if (lo || hi) out.push(["price", lo && hi ? `$${lo} to $${hi}` : lo ? `$${lo} and up` : `Up to $${hi}`]);
    return out;
  }
  function renderChips() {
    const chips = activeChips(), box = $("chips");
    const n = chips.filter(([id]) => id !== "q").length;
    $("filterCount").hidden = !n; $("filterCount").textContent = n;
    box.hidden = !chips.length;
    box.innerHTML = chips.map(([id, text]) => `<button class="chip" data-clear="${id}" aria-label="Take off ${esc(text)}">${esc(text)}<svg><use href="#i-close"/></svg></button>`).join("")
      + (chips.length > 1 ? '<button class="link-btn" data-clear="all">Clear all</button>' : "");
  }
  $("chips").onclick = e => {
    const b = e.target.closest("[data-clear]"); if (!b) return;
    const id = b.dataset.clear;
    if (id === "all") return clearFilters();
    if (id === "price") { $("fMin").value = ""; $("fMax").value = ""; } else $(id).value = "";
    applyFilters();
  };
  $("filterBtn").onclick = () => {
    const open = document.querySelector(".find-bar").classList.toggle("open");
    $("filterBtn").setAttribute("aria-expanded", open);
  };

  function renderResults() {
    shown = filtered();
    const active = FILTER_IDS.some(id => $(id).value);
    renderChips();
    const cards = shown.reduce((n, c) => n + c.qty, 0), value = shown.reduce((v, c) => v + (c.value || 0), 0);
    $("showing").textContent = data.cards.length ? (active ? `Showing ${cards.toLocaleString()} of ${data.summary.cards.toLocaleString()} cards · ${money(value)}` : `${cards.toLocaleString()} cards · ${money(value)}`) : "";
    for (const b of $("viewSeg").children) b.setAttribute("aria-pressed", b.dataset.v === prefs.view);
    const page = shown.slice(0, limit);
    $("results").classList.toggle("is-binder", prefs.view === "binder" && shown.length > 0);
    if (!data.cards.length) $("results").innerHTML = `<p class="results-empty">No cards saved yet. Scan some on the <a href="/scan">Scanner</a>, or press <b>Add a card</b>.</p>`;
    else if (!shown.length) $("results").innerHTML = '<p class="results-empty">No cards match these filters.</p>';
    else if (prefs.view === "grid") $("results").innerHTML = `<div class="results-grid">${page.map(c => tile(c)).join("")}</div>`;
    else if (prefs.view === "binder") renderBinder();
    else $("results").innerHTML = `<div class="table-wrap"><table class="list"><thead><tr>
        <th>Card</th><th class="hide-sm">Set</th><th class="hide-sm">Rarity</th><th>Copies</th><th class="num">Price</th><th class="num" title="Face to Face Games, or the next Montreal store">Montreal</th><th class="num hide-sm">Value</th><th class="num hide-sm">Since scanned</th><th class="num hide-sm" title="What you paid for each, and the gain since">Paid</th><th class="hide-sm">Bin</th></tr></thead><tbody>
      ${page.map(c => `<tr data-key="${esc(c.key)}"${selecting && picked.has(c.key) ? ' class="picked"' : ""}>
        <td class="card-cell">${c.image ? `<img class="thumb" src="${esc(small(c.image))}" alt="" loading="lazy">` : '<span class="thumb"></span>'}<span><span class="dotc" style="background:var(--mana-${esc(c.color)})" title="${esc(COLORS[c.color] ?? "")}"></span><span class="nm">${esc(c.name)}</span>${c.foil ? '<span class="foil-tag">foil</span>' : ""}${c.proxy ? '<span class="proxy-tag" title="Proxy: not counted in the value">proxy</span>' : ""}${c.condition !== "NM" || c.language !== "EN" ? `<span class="foil-tag cond-tag">${esc([c.condition !== "NM" ? c.condition : "", c.language !== "EN" ? c.language : ""].filter(Boolean).join(" · "))}</span>` : ""}${(c.tags || []).map(t => `<span class="tag-pill">${esc(t)}</span>`).join("")}<small class="sub show-sm">${esc(c.set)} #${esc(c.number)}</small></span></td>
        <td class="hide-sm">${esc(c.set)} #${esc(c.number)}</td>
        <td class="rar hide-sm">${esc(c.rarity)}</td>
        <td class="qty-cell"><button data-step="-1" aria-label="One fewer"><svg><use href="#i-minus"/></svg></button><b>${c.qty}</b><button data-step="1" aria-label="One more"><svg><use href="#i-plus"/></svg></button></td>
        <td class="num">${money(c.price)}</td>
        <td class="num mtl-cell">${window.Montreal ? Montreal.cell(c) : ""}</td>
        <td class="num hide-sm">${c.value == null ? "" : money(c.value)}</td>
        <td class="num chg hide-sm ${c.change > 0 ? "up" : c.change < 0 ? "down" : ""}">${c.change ? signed(c.change) : ""}</td>
        <td class="num hide-sm paid-cell">${c.paid == null ? "" : `${money(c.paid)}${c.gain ? `<small class="${c.gain > 0 ? "up" : "down"}">${signed(c.gain)}</small>` : ""}`}</td>
        <td class="hide-sm"><span class="pill bin-${c.bin}">${c.bin}</span></td></tr>`).join("")}</tbody></table></div>`;
    $("moreBtn").hidden = shown.length <= limit || prefs.view === "binder";
    $("moreBtn").textContent = `Show more (${(shown.length - limit).toLocaleString()} left)`;
  }
  $("moreBtn").onclick = () => { limit += PAGE * 2; renderResults(); };
  $("viewSeg").onclick = e => { const b = e.target.closest("button"); if (b) setView(b.dataset.v); };
  function setView(v) {
    if (v === "binder" && prefs.view !== "binder") binderFirst = 0;
    prefs.view = v; savePrefs(); renderResults();
  }

  // ---------- binder: the cards in 9-pocket pages, two side by side on a computer ----------
  const POCKETS = 9;
  const binderSpread = () => matchMedia("(min-width: 900px)").matches ? 2 : 1;
  function renderBinder(turn = "") {
    const pps = binderSpread(), per = POCKETS * pps;
    const pages = Math.max(1, Math.ceil(shown.length / POCKETS));
    const spreads = Math.max(1, Math.ceil(shown.length / per));
    const at = Math.min(Math.floor(binderFirst / per), spreads - 1);
    binderFirst = at * per;
    const sheet = p => {
      const cards = shown.slice(p * POCKETS, (p + 1) * POCKETS);
      if (p >= pages) return '<div class="binder-page blank" aria-hidden="true"></div>';
      return `<div class="binder-page" aria-label="Page ${p + 1}">${cards.map(c => {
        const on = selecting && picked.has(c.key);
        return `<button class="pocket${c.foil ? " foil" : ""}${c.proxy ? " proxy" : ""}${on ? " picked" : ""}" data-key="${esc(c.key)}" title="${esc(c.name)} · ${esc(c.set)} #${esc(c.number)} · ${esc(money(c.price))}"${selecting ? ` aria-pressed="${on}"` : ""}>
          ${picture(c, "(max-width: 900px) 30vw, 180px")}${c.qty > 1 ? `<span class="qty">×${c.qty}</span>` : ""}${c.foil ? '<span class="foil-badge">FOIL</span>' : ""}${badges(c)}${proxyBadge(c)}${selecting ? PICK_MARK : ""}
          <span class="pocket-price">${esc(money(c.price))}</span></button>`;
      }).join("")}${'<span class="pocket empty" aria-hidden="true"></span>'.repeat(POCKETS - cards.length)}<small class="page-no">${p + 1}</small></div>`;
    };
    const first = at * pps, last = Math.min(pages, first + pps);
    const label = last - first > 1 ? `Pages ${first + 1}–${last} of ${pages}` : `Page ${first + 1} of ${pages}`;
    const value = shown.slice(first * POCKETS, last * POCKETS).reduce((v, c) => v + (c.value || 0), 0);
    $("results").innerHTML = `<div class="binder-wrap">
        <button class="binder-turn" data-turn="-1" aria-label="Page before" ${at ? "" : "disabled"}><svg><use href="#i-left"/></svg></button>
        <div class="binder${turn ? " turn-" + turn : ""}" style="--pps:${pps}">${Array.from({ length: pps }, (_, i) => sheet(first + i)).join("")}</div>
        <button class="binder-turn" data-turn="1" aria-label="Next page" ${at < spreads - 1 ? "" : "disabled"}><svg><use href="#i-right"/></svg></button>
      </div>
      <div class="binder-foot"><span><b>${label}</b> · ${money(value)} on ${last - first > 1 ? "these pages" : "this page"}</span>
        ${spreads > 1 ? `<input type="range" id="binderRange" min="1" max="${spreads}" value="${at + 1}" aria-label="Jump to a page">` : ""}</div>`;
  }
  function turnBinder(d) {
    const per = POCKETS * binderSpread(), spreads = Math.ceil(shown.length / per);
    const at = Math.floor(binderFirst / per) + d;
    if (at < 0 || at >= spreads) return;
    binderFirst = at * per; renderBinder(d > 0 ? "next" : "prev");
  }
  $("results").addEventListener("input", e => {
    if (e.target.id !== "binderRange") return;
    binderFirst = (+e.target.value - 1) * POCKETS * binderSpread(); renderBinder();
    $("binderRange")?.focus();
  });
  // A swipe turns the page on a phone.
  let swipeX = null, swipeY = 0;
  $("results").addEventListener("touchstart", e => { if (prefs.view === "binder" && e.touches.length === 1) { swipeX = e.touches[0].clientX; swipeY = e.touches[0].clientY; } }, { passive: true });
  $("results").addEventListener("touchend", e => {
    if (swipeX == null) return;
    const dx = e.changedTouches[0].clientX - swipeX, dy = e.changedTouches[0].clientY - swipeY; swipeX = null;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5 && e.target.closest(".binder")) turnBinder(dx < 0 ? 1 : -1);
  }, { passive: true });
  let spreadWas = binderSpread();
  addEventListener("resize", () => { if (data && prefs.view === "binder" && binderSpread() !== spreadWas) { spreadWas = binderSpread(); renderBinder(); } });

  // ---------- select: pick several cards, then trade, export or delete them together ----------
  function setSelecting(on) {
    selecting = on;
    if (!on) picked.clear();
    $("selectBtn").setAttribute("aria-pressed", on);
    document.querySelector(".browse").classList.toggle("selecting", on);
    renderResults(); renderSelectBar();
  }
  function pickedCards() { return data.cards.filter(c => picked.has(c.key)); }
  function renderSelectBar() {
    $("selectBar").hidden = !selecting;
    document.documentElement.classList.toggle("has-select-bar", selecting);
    if (!selecting) return;
    const cards = pickedCards(), n = cards.reduce((t, c) => t + c.qty, 0);
    $("selCount").textContent = cards.length ? `${n.toLocaleString()} card${n === 1 ? "" : "s"} picked` : "Tap cards to pick them";
    $("selValue").textContent = cards.length ? `${cards.length.toLocaleString()} printing${cards.length === 1 ? "" : "s"} · ${money(cards.reduce((v, c) => v + (c.value || 0), 0))}` : "";
    const all = shown.length && shown.every(c => picked.has(c.key));
    $("selAll").textContent = all ? "Unpick all" : `Pick all ${shown.length.toLocaleString()} showing`;
    for (const id of ["selEdit", "selTrade", "selExport", "selDelete"]) $(id).disabled = !cards.length;
  }
  function togglePick(el) {
    const key = el.dataset.key;
    if (picked.has(key)) picked.delete(key); else picked.add(key);
    const on = picked.has(key);
    el.classList.toggle("picked", on);
    if (el.hasAttribute("aria-pressed")) el.setAttribute("aria-pressed", on);
    renderSelectBar();
  }
  $("selectBtn").onclick = () => setSelecting(!selecting);
  $("selDone").onclick = () => setSelecting(false);
  $("selAll").onclick = () => {
    const all = shown.every(c => picked.has(c.key));
    for (const c of shown) all ? picked.delete(c.key) : picked.add(c.key);
    renderResults(); renderSelectBar();
  };
  $("selTrade").onclick = async () => {
    const cards = pickedCards();
    try {
      setTrades(await api("/api/trades/add", { cards: cards.map(c => ({ name: c.name, set: c.set, number: c.number, foil: c.foil, qty: c.qty, card_id: c.id })) }));
      toast(`${cards.length.toLocaleString()} in the trade binder (Wishlist page)`);
    } catch (e) { toast(e.message); }
  };
  $("selExport").onclick = () => openExport(true);
  $("selDelete").onclick = async () => {
    const cards = pickedCards(), n = cards.reduce((t, c) => t + c.qty, 0);
    if (!cards.length || !confirm(`Delete ${n.toLocaleString()} card${n === 1 ? "" : "s"} (${cards.length.toLocaleString()} printing${cards.length === 1 ? "" : "s"}, ${money(cards.reduce((v, c) => v + (c.value || 0), 0))}) from the collection?\n\nA backup on the Maintenance page is the only way back.`)) return;
    try {
      setData(await api("/api/collection/delete", { cards: Object.fromEntries(cards.map(c => [c.key, c.qty])) }));
      picked.clear(); renderResults(); renderSelectBar();
      toast(`Deleted ${n.toLocaleString()} card${n === 1 ? "" : "s"}`);
    } catch (e) { toast(e.message); load(); }
  };
  $("results").onclick = async e => {
    const turn = e.target.closest("[data-turn]");
    if (turn) return turnBinder(+turn.dataset.turn);
    const step = e.target.closest("[data-step]"), row = e.target.closest("[data-key]");
    if (!row) return;
    if (selecting && !step) return togglePick(row);
    if (step) {
      // Sends one more or one fewer, not a count: the server counts what's there now, so
      // copies saved since the page loaded are kept.
      const c = byKey(row.dataset.key), s = +step.dataset.step;
      if (c.qty + s < 1 && !confirm(`Delete ${c.name} (${c.set}) from the collection?`)) return;
      return edit({ key: c.key, step: s }, s < 0 ? js => gone(js, c) : null);
    }
    openDetail(row.dataset.key);
  };

  // message: the toast text, or a function of the answer that returns it.
  async function edit(change, message) {
    try {
      const js = await api("/api/collection/edit", change);
      setData(js);
      const text = typeof message === "function" ? message(js) : message;
      if (text) toast(text);
    }
    catch (e) { toast(e.message); load(); }
  }
  // After one fewer: say "Deleted" only if the card really is gone.
  function gone(js, c) {
    const now = js.cards.find(x => x.key === c.key);
    if (!now) return `Deleted ${c.name}`;
    return now.qty >= c.qty ? `More were saved since. You have ${now.qty} now.` : null;
  }

  // ---------- one card ----------
  function openModal(id) { $(id).hidden = false; }
  function closeModal(id) {
    $(id).hidden = true;
    if (id !== "detail") return;
    // In the binder, land on the page of the last card looked at.
    const i = shown.findIndex(c => c.key === detailKey);
    if (prefs.view === "binder" && i >= 0) {
      const per = POCKETS * binderSpread();
      if (Math.floor(i / per) !== Math.floor(binderFirst / per)) { binderFirst = Math.floor(i / per) * per; renderBinder(); }
    }
    detailKey = null;
  }
  for (const m of document.querySelectorAll(".modal")) {
    m.addEventListener("click", e => { if (e.target === m || e.target.closest("[data-close]")) closeModal(m.id); });
  }
  function openDetail(key) {
    detailKey = key; $("dPrintList").hidden = true; $("dImg").removeAttribute("src");
    renderDetail(); openModal("detail");
  }
  // Card to card with the arrows, the ← → keys or a swipe on the picture, in the order showing.
  function stepDetail(d) {
    const i = shown.findIndex(c => c.key === detailKey), next = shown[i + d];
    if (i < 0 || !next) return;
    detailKey = next.key; $("dPrintList").hidden = true;
    renderDetail();
  }
  $("dPrev").onclick = () => stepDetail(-1);
  $("dNext").onclick = () => stepDetail(1);
  let artX = null;
  $("dArt").addEventListener("touchstart", e => { artX = e.touches[0].clientX; }, { passive: true });
  $("dArt").addEventListener("touchend", e => {
    if (artX == null) return;
    const dx = e.changedTouches[0].clientX - artX; artX = null;
    if (Math.abs(dx) > 40) stepDetail(dx < 0 ? 1 : -1);
  }, { passive: true });
  function renderDetail() {
    const c = byKey(detailKey);
    if (!c) return closeModal("detail");
    const i = shown.findIndex(x => x.key === c.key);
    $("dNav").hidden = i < 0 || shown.length < 2;
    $("dPos").textContent = i < 0 ? "" : `${(i + 1).toLocaleString()} of ${shown.length.toLocaleString()}`;
    $("dPrev").disabled = i <= 0; $("dNext").disabled = i < 0 || i >= shown.length - 1;
    if (shown[i + 1]?.image) new Image().src = shown[i + 1].image;   // ready before it's asked for
    $("dName").textContent = c.name;
    if (c.image && $("dImg").getAttribute("src") !== c.image) $("dImg").src = c.image;
    $("dImg").alt = c.name;
    $("dArt").classList.toggle("foil", c.foil);
    $("dSet").textContent = `${c.set_name || c.set} · ${c.set} #${c.number}${c.rarity ? " · " + c.rarity : ""}`;
    $("dPrice").textContent = money(c.price) + (!c.proxy && c.qty > 1 && c.value != null ? `  ×${c.qty} = ${money(c.value)}` : "");
    $("dSource").textContent = c.proxy ? "Proxy: that's the real card's price, not counted in your collection's value" : "";
    if (!c.proxy) $("dSource").textContent = c.price_source || "";
    renderSpark(c);
    window.Montreal?.show($("dMontreal"), c);
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
    $("dProxy").setAttribute("aria-pressed", !!c.proxy);
    $("dScryfall").hidden = !c.scryfall; $("dScryfall").href = c.scryfall || "#";
    $("dLookup").href = "/cards?card=" + encodeURIComponent(c.name);
    $("dTrade").setAttribute("aria-pressed", tradeKeys.has(tradeKey(c)));
    renderCopyDetails(c);
  }

  // ---------- its price over time ----------
  // The prices SortR noted for this printing, one a day, as a small line, with how much it
  // moved this week. Fetched once per card while the page is open.
  const sparks = new Map();
  const shortDay = d => new Date(d + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
  function trendText(t) {
    if (!t) return "";
    const pct = t.pct != null ? ` (${t.pct > 0 ? "+" : t.pct < 0 ? "−" : ""}${Math.abs(t.pct)}%)` : "";
    return `${t.change ? signed(t.change) + pct : "No change"} since ${shortDay(t.since)}`;
  }
  async function renderSpark(c) {
    const box = $("dSpark");
    if (!c.trend) { box.hidden = true; return; }
    $("dTrend").textContent = trendText(c.trend);
    $("dTrend").className = "spark-note " + (c.trend.change > 0 ? "up" : c.trend.change < 0 ? "down" : "");
    box.hidden = false;
    let pts = sparks.get(c.key);
    if (!pts) {
      $("dSparkSvg").innerHTML = ""; $("dSparkRange").textContent = "";
      try { pts = (await api("/api/collection/price-history?key=" + encodeURIComponent(c.key))).points; sparks.set(c.key, pts); }
      catch (e) { return; }
      if (detailKey !== c.key) return;
    }
    if (pts.length < 2) { $("dSparkSvg").innerHTML = ""; $("dSparkRange").textContent = ""; return; }
    const W = 240, H = 56, pad = 4, ps = pts.map(p => p.price), lo = Math.min(...ps), hi = Math.max(...ps), span = hi - lo || 1;
    const t0 = Date.parse(pts[0].day), t1 = Date.parse(pts[pts.length - 1].day), tw = t1 - t0 || 1;
    const xy = pts.map(p => [pad + (Date.parse(p.day) - t0) / tw * (W - 2 * pad), H - pad - (p.price - lo) / span * (H - 2 * pad)]);
    const daysNoted = Math.round(tw / 864e5) + 1;
    $("dSparkRange").textContent = `Last ${daysNoted} days · low ${money(lo)} · high ${money(hi)}`;
    const line = xy.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join("");
    const cls = ps[ps.length - 1] > ps[0] ? "up" : ps[ps.length - 1] < ps[0] ? "down" : "";
    $("dSparkSvg").innerHTML = `<path class="area ${cls}" d="${line}L${xy[xy.length - 1][0].toFixed(1)},${H}L${xy[0][0].toFixed(1)},${H}Z"/><path class="line ${cls}" d="${line}"/>
      <title>${esc(shortDay(pts[0].day))} ${esc(money(ps[0]))} to ${esc(shortDay(pts[pts.length - 1].day))} ${esc(money(ps[ps.length - 1]))}, low ${esc(money(lo))}, high ${esc(money(hi))}</title>`;
  }

  // ---------- condition, language, what you paid, tags ----------
  const condButtons = (pressed, mixed) => data.condOrder.map(([k, name]) =>
    `<button data-cond="${k}" title="${esc(name)}" aria-pressed="${k === pressed && !mixed}">${k}</button>`).join("");
  const langOptions = (sel, first = "") => (first ? `<option value="">${first}</option>` : "") +
    data.langOrder.map(([k, name]) => `<option value="${k}"${k === sel ? " selected" : ""}>${esc(name)}</option>`).join("");
  function renderCopyDetails(c) {
    $("dCond").innerHTML = condButtons(c.condition, false);
    $("dCond").title = c.mixed ? "These copies aren't all in the same condition: this is the most common one. Pick one to set them all." : "";
    $("dLang").innerHTML = langOptions(c.language);
    if (document.activeElement !== $("dPaid")) $("dPaid").value = c.paid ?? "";
    $("dGain").className = c.gain > 0 ? "up" : c.gain < 0 ? "down" : "";
    $("dGain").textContent = c.paid == null ? "Add it to see what it gained" : c.gain == null ? "" :
      `${signed(c.gain)}${c.paid_qty !== c.qty ? ` on ${c.paid_qty} of ${c.qty}` : c.qty > 1 ? ` on all ${c.qty}` : ""}`;
    $("dTags").innerHTML = (c.tags || []).map(t => `<button class="chip" data-untag="${esc(t)}" aria-label="Take off ${esc(t)}">${esc(t)}<svg><use href="#i-close"/></svg></button>`).join("");
  }
  async function details(keys, change, message) {
    try {
      setData(await api("/api/collection/details", { keys, ...change }));
      if (message) toast(message);
    } catch (e) { toast(e.message); }
  }
  $("dCond").onclick = e => {
    const b = e.target.closest("[data-cond]"), c = byKey(detailKey); if (!b || !c) return;
    details([c.key], { condition: b.dataset.cond }, `Condition: ${data.conditions[b.dataset.cond]}`);
  };
  $("dLang").onchange = () => { const c = byKey(detailKey); if (c) details([c.key], { language: $("dLang").value }, `Language: ${data.languages[$("dLang").value]}`); };
  const savePaid = () => {
    const c = byKey(detailKey); if (!c) return;
    const raw = $("dPaid").value.trim(), v = raw === "" ? null : Math.round(parseFloat(raw) * 100) / 100;
    if (raw !== "" && (isNaN(v) || v < 0)) return toast("The price paid is a number, like 4.50");
    if (v === (c.paid ?? null)) return;
    details([c.key], { paid: v }, v == null ? "Price paid cleared" : `Paid ${money(v)} each`);
  };
  $("dPaid").onchange = savePaid;
  $("dPaid").onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); $("dPaid").blur(); } };
  const addTag = () => {
    const c = byKey(detailKey), t = $("dTagInput").value.replace(/,/g, " ").trim(); if (!c || !t) return;
    $("dTagInput").value = "";
    details([c.key], { add_tag: t }, `Tagged ${t}`);
  };
  $("dTagInput").onkeydown = e => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addTag(); } };
  $("dTagInput").onchange = () => { if ($("dTagInput").value && [...$("tagList").options].some(o => o.value === $("dTagInput").value)) addTag(); };
  $("dTags").onclick = e => {
    const b = e.target.closest("[data-untag]"), c = byKey(detailKey); if (!b || !c) return;
    details([c.key], { remove_tag: b.dataset.untag }, `Took off ${b.dataset.untag}`);
  };

  // Select's "Tag, condition…": the same for every picked card at once.
  function openBulk() {
    const cards = pickedCards(); if (!cards.length) return;
    const n = cards.length;
    $("bulkTitle").textContent = `Change the ${n.toLocaleString()} picked printing${n === 1 ? "" : "s"}`;
    renderBulk();
    $("bLang").innerHTML = langOptions("", "Leave as they are");
    $("bPaid").value = "";
    openModal("bulk"); $("bTagInput").focus();
  }
  function renderBulk() {
    const cards = pickedCards(), tags = [...new Set(cards.flatMap(c => c.tags || []))].sort((a, b) => a.localeCompare(b));
    $("bTags").innerHTML = tags.map(t => `<button class="chip" data-untag="${esc(t)}">${esc(t)}<svg><use href="#i-close"/></svg></button>`).join("");
    $("bTags").hidden = $("bTagsLabel").hidden = !tags.length;
    const conds = new Set(cards.map(c => c.condition));
    $("bCond").innerHTML = condButtons(conds.size === 1 ? [...conds][0] : "", cards.some(c => c.mixed));
    $("bNote").textContent = `${cards.reduce((t, c) => t + c.qty, 0).toLocaleString()} cards. Each change is saved straight away.`;
  }
  const bulk = (change, message) => details([...picked], change, message).then(() => { if (!$("bulk").hidden) renderBulk(); });
  $("selEdit").onclick = openBulk;
  $("bTagAdd").onclick = () => {
    const t = $("bTagInput").value.replace(/,/g, " ").trim(); if (!t) return $("bTagInput").focus();
    $("bTagInput").value = "";
    bulk({ add_tag: t }, `Tagged ${picked.size.toLocaleString()} with ${t}`);
  };
  $("bTagInput").onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); $("bTagAdd").click(); } };
  $("bTags").onclick = e => { const b = e.target.closest("[data-untag]"); if (b) bulk({ remove_tag: b.dataset.untag }, `Took off ${b.dataset.untag}`); };
  $("bCond").onclick = e => { const b = e.target.closest("[data-cond]"); if (b) bulk({ condition: b.dataset.cond }, `All ${data.conditions[b.dataset.cond]}`); };
  $("bLang").onchange = () => { if ($("bLang").value) bulk({ language: $("bLang").value }, `All ${data.languages[$("bLang").value]}`); };
  $("bPaidSet").onclick = () => {
    const v = Math.round(parseFloat($("bPaid").value) * 100) / 100;
    if (isNaN(v) || v < 0) return toast("Type what you paid for each, like 4.50");
    bulk({ paid: v }, `Paid ${money(v)} each`);
  };
  $("bProxyOn").onclick = () => markProxy([...picked], true, `${picked.size.toLocaleString()} marked as proxies`);
  $("bProxyOff").onclick = () => markProxy([...picked], false, `${picked.size.toLocaleString()} marked as real cards`);
  $("bPaidClear").onclick = () => bulk({ paid: null }, "Price paid cleared");
  // The trade binder (shown on the Wishlist page).
  let tradeKeys = new Set(), tradeIds = new Map();
  const tradeKey = c => `${c.name}|${c.set}|${c.number}|${c.foil ? 1 : 0}`;
  function setTrades(js) { tradeKeys = new Set(js.cards.map(x => x.key)); tradeIds = new Map(js.cards.map(x => [x.key, x.id])); }
  api("/api/trades").then(setTrades).catch(() => { });
  $("dTrade").onclick = async () => {
    const c = byKey(detailKey); if (!c) return;
    const k = tradeKey(c), on = tradeKeys.has(k);
    try {
      setTrades(on ? await api("/api/trades/remove", { id: tradeIds.get(k) })
        : await api("/api/trades/add", { name: c.name, set: c.set, number: c.number, foil: c.foil, qty: c.qty, card_id: c.id }));
      toast(on ? "Taken out of the trade binder" : "In the trade binder (Wishlist page)"); renderDetail();
    } catch (e) { toast(e.message); }
  };
  window.COLLECTION = { reload: () => load() };
  $("dPlus").onclick = () => { const c = byKey(detailKey); edit({ key: c.key, step: 1 }); };
  $("dMinus").onclick = () => {
    const c = byKey(detailKey);
    if (c.qty <= 1) return $("dDelete").click();
    edit({ key: c.key, step: -1 });
  };
  $("dFoil").onclick = () => {
    const c = byKey(detailKey);
    detailKey = c.key.replace(/#(foil|normal)(#proxy)?$/, (_, f, p) => (c.foil ? "#normal" : "#foil") + (p || ""));   // joins any copies already there
    edit({ key: c.key, foil: !c.foil }, c.foil ? "Marked as normal" : "Marked as foil");
  };
  // Proxy or real: the copies move to a key of their own (id#normal#proxy), joining any there
  async function markProxy(keys, on, message) {
    try {
      const js = await api("/api/collection/details", { keys, proxy: on });
      for (const k of keys) if (picked.delete(k)) picked.add(proxyKey(k, on));
      if (detailKey && keys.includes(detailKey)) detailKey = proxyKey(detailKey, on);
      setData(js); toast(message);
      if (!$("bulk").hidden) renderBulk();
    } catch (e) { toast(e.message); }
  }
  $("dProxy").onclick = () => {
    const c = byKey(detailKey); if (!c) return;
    markProxy([c.key], !c.proxy, c.proxy ? "Marked as the real card" : "Marked as a proxy: not counted in the value");
  };
  $("dDelete").onclick = () => {
    const c = byKey(detailKey);
    if (!confirm(`Delete all ${c.qty} of ${c.name} (${c.set}${c.foil ? " foil" : ""}) from the collection?`)) return;
    // seen: the server refuses if more were saved since, so none are deleted unseen.
    closeModal("detail"); edit({ key: c.key, delete: true, seen: c.qty }, `Deleted ${c.name}`);
  };
  $("dPrintings").onclick = async () => {
    const c = byKey(detailKey), list = $("dPrintList");
    list.hidden = false; list.innerHTML = '<p class="sub">Looking up every printing…</p>';
    try {
      const prints = await api(`/api/printings?name=${encodeURIComponent(c.name)}&foil=${c.foil ? 1 : 0}`);
      list.innerHTML = `<p class="sub">Pick the printing you really have:</p><div class="print-grid">` + prints.map(p => tile({ ...p, key: p.id, qty: 1, foil: c.foil }, p.id === c.id ? " is-current in-print" : " in-print", "110px")).join("") + "</div>";
    } catch (e) { list.innerHTML = `<p class="sub">${esc(e.message)}</p>`; }
  };
  $("dPrintList").onclick = e => {
    const t = e.target.closest(".tile"), c = byKey(detailKey);
    if (!t || t.dataset.key === c.id) return;
    detailKey = `${t.dataset.key}#${c.foil ? "foil" : "normal"}${c.proxy ? "#proxy" : ""}`;
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
      setData(await api("/api/collection/add", { id: b.dataset.id, qty, foil: $("addFoil").checked, proxy: $("addProxy").checked }));
      toast(`Added ${qty > 1 ? qty + " × " : ""}${b.dataset.name}${$("addProxy").checked ? " (proxy)" : ""}`);
      $("addInput").select();
    } catch (err) { toast(err.message); }
  };

  // ---------- export ----------
  let exportPicked = false;   // Select's Export: only the picked cards
  function openExport(onlyPicked = false) {
    exportPicked = onlyPicked && picked.size > 0;
    $("formats").innerHTML = data.exports.map(f => `<button class="format" data-id="${f.id}" aria-pressed="${f.id === prefs.format}"><b>${esc(f.label)}</b><small>${esc(f.hint)}</small></button>`).join("");
    const active = exportPicked || shown.length !== data.cards.length;
    const count = (exportPicked ? pickedCards() : shown).reduce((n, c) => n + c.qty, 0).toLocaleString();
    $("exOnly").checked = active; $("exOnly").disabled = !active;
    $("exOnlyText").textContent = exportPicked ? `Only the ${count} cards you picked` : active ? `Only the ${count} cards showing` : "Only the cards showing (set filters first)";
    openModal("export");
  }
  $("exportBtn").onclick = () => openExport(false);
  $("formats").onclick = e => {
    const b = e.target.closest(".format"); if (!b) return;
    prefs.format = b.dataset.id; savePrefs();
    for (const x of $("formats").children) x.setAttribute("aria-pressed", x === b);
  };
  async function exportFile() {
    const body = { format: prefs.format };
    if ($("exOnly").checked) body.keys = exportPicked ? [...picked] : shown.map(c => c.key);
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
    if (open?.id === "detail" && (e.key === "ArrowLeft" || e.key === "ArrowRight") && !e.target.matches("input, textarea, select")) {
      e.preventDefault(); return stepDetail(e.key === "ArrowLeft" ? -1 : 1);
    }
    if (open || e.target.matches("input, textarea, select") || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "Escape" && selecting) return setSelecting(false);
    if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && prefs.view === "binder" && data) { e.preventDefault(); return turnBinder(e.key === "ArrowLeft" ? -1 : 1); }
    if (e.key === "/") { e.preventDefault(); $("q").focus(); }
    else if (e.key === "g" || e.key === "G") setView("grid");
    else if (e.key === "l" || e.key === "L") setView("list");
    else if (e.key === "b" || e.key === "B") setView("binder");
    else if ((e.key === "s" || e.key === "S") && data) setSelecting(!selecting);
    else if (e.key === "n" || e.key === "N") { e.preventDefault(); openAdd(); }
    else if ((e.key === "e" || e.key === "E") && data) openExport();
  });

  // On a phone the long hint is cut off beside the Filters button.
  if (matchMedia("(max-width: 600px)").matches) $("q").placeholder = "Search your cards";
  // Other pages link here with a search filled in (/collection?q=Sol Ring).
  { const ps = new URLSearchParams(location.search), q = ps.get("q"), sort = ps.get("sort");
    if (q) $("q").value = q;
    for (const [k, id] of [["min", "fMin"], ["max", "fMax"]]) if (ps.get(k) && !isNaN(parseFloat(ps.get(k)))) $(id).value = parseFloat(ps.get(k));
    if (sort && [...$("sort").options].some(o => o.value === sort)) { prefs.sort = sort; $("sort").value = sort; }
    // Home links here with one filter set (/collection?color=U, ?bin=3); applied once the lists are filled.
    var linked = { fColor: ps.get("color"), fBin: ps.get("bin"), fRarity: ps.get("rarity"), fSet: ps.get("set"), fFoil: ps.get("foil"),
      fTag: ps.get("tag"), fCond: ps.get("cond"), fLang: ps.get("lang"), fProxy: ps.get("proxy") }; }
  // The search palette's "Export the collection" and "Add a card" land here as #export / #add.
  load().then(() => {
    let changed = false;
    for (const [id, v] of Object.entries(linked)) if (v != null && [...$(id).options].some(o => o.value === v)) { $(id).value = v; changed = true; }
    if (changed) { fillFilters(); applyFilters(); }   // (fillFilters again: a linked tag's list shows)
    else renderChips();
    if (location.hash === "#export" && data) openExport();
    else if (location.hash === "#add") openAdd();
    if (location.hash) history.replaceState(null, "", location.pathname + location.search);
    syncUrl();   // drops any filter that didn't match (a set no longer in the collection)
  });
})();
