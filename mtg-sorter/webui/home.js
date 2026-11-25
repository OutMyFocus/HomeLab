// The Home page: one look at the collection, the scanner, the machine and the Pi, with a few
// things worked out from your cards (Insights).
(() => {
  const { $, esc, money, api } = window.MTG;
  const C = window.SortRCharts;
  const signed = v => (v > 0 ? "+" : v < 0 ? "−" : "") + money(Math.abs(v));
  const small = url => url ? url.replace("version=normal", "version=small") : "";
  const plural = (n, word) => `${n.toLocaleString()} ${word}${n === 1 ? "" : "s"}`;
  const day = iso => new Date(iso.length === 10 ? iso + "T12:00:00" : iso);
  const pct = v => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(Math.abs(v) < 10 ? 1 : 0) + "%";
  const axisMoney = v => v >= 10000 ? "$" + (v / 1000).toFixed(0) + "k" : v >= 1000 ? "$" + (v / 1000).toFixed(1) + "k" : "$" + Math.round(v);
  const BINVAR = b => `var(--bin${b}, var(--muted))`;
  const COLORS = { W: "White", U: "Blue", B: "Black", R: "Red", G: "Green", M: "Multicolor", C: "Colorless" };
  const PREF = "sortr-home";
  let prefs = { range: "30", colors: "value" };
  try { prefs = { ...prefs, ...JSON.parse(localStorage.getItem(PREF) || "{}") }; } catch (e) {}
  const save = () => { try { localStorage.setItem(PREF, JSON.stringify(prefs)); } catch (e) {} };
  let data = null, health = window.MTGHealth || null, first = true;

  function greet() {
    const h = new Date().getHours();
    const name = window.MTGMe?.me?.name ? `, ${window.MTGMe.me.name}` : "";
    $("hello").textContent = (h < 5 ? "Up late" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening") + name;
  }

  function setStatus(id, state, text) {
    const el = $(id);
    el.dataset.state = state;
    el.querySelector("small").textContent = text;
  }

  function renderStatus() {
    const s = data.scanner, m = data.machine;
    const cam = s.waiting ? ["bad", "Not connected"] : s.status === "starting" ? ["warn", "Starting…"]
      : ["ok", (s.camera || "Demo photos") + (s.fps ? ` · ${Math.round(s.fps)} fps` : "")];
    setStatus("stCamera", ...cam);
    setStatus("stServos", m.servos ? "ok" : "bad", m.servos ? "Ready" : "Not found");
    setStatus("stFeeder", m.feeder ? (m.feeding ? "warn" : "ok") : "bad", m.feeder ? (m.feeding ? "Feeding…" : "Ready") : "Not available");
    if (health) {
      const p = health.problems || [];
      setStatus("stHealth", health.overall, health.overall === "ok" ? "All good" : p.length === 1 ? p[0].label + ": " + p[0].summary : `${p.length} things to look at`);
    }
    // One line on what's going on, and the main button to match.
    const line = $("heroLine"), btn = $("scanBtn");
    if (s.waiting) {
      line.innerHTML = "No camera is connected, so live scanning is paused. You can still scan photos of your cards, or use this phone's camera on the Scanner.";
      btn.lastChild.textContent = "Open the scanner";
    } else if (s.on_table) {
      line.textContent = `${plural(s.on_table, "card")} on the table right now` + (s.session.count ? `, ${plural(s.session.count, "card")} saved this session.` : ".");
      btn.lastChild.textContent = "Back to scanning";
    } else if (s.session.count) {
      line.textContent = `${plural(s.session.count, "card")} saved this session, worth ${money(s.session.value)}. Ready for more.`;
      btn.lastChild.textContent = "Keep scanning";
    } else {
      line.textContent = `Ready to scan. SortR knows ${s.db_count.toLocaleString()} cards` + (s.learned ? ` and has learned ${plural(s.learned, "scan")} of yours.` : ".");
      btn.lastChild.textContent = "Start scanning";
    }
  }

  // The change over the chosen range of the value history.
  function trend(days) {
    const h = data.collection.history || [];
    if (h.length < 2) return null;
    const lastDay = day(h[h.length - 1].day).getTime();
    const from = days === "all" ? h[0] : (h.find(p => lastDay - day(p.day).getTime() <= days * 864e5) || h[0]);
    const now = h[h.length - 1];
    if (from === now || !from.value) return null;
    const diff = now.value - from.value;
    return { diff, pct: diff / from.value * 100, days: Math.round((lastDay - day(from.day).getTime()) / 864e5) };
  }

  function renderHero() {
    const c = data.collection;
    C.countUp($("kValue"), c.value, v => money(v));
    const vs = $("kValueSub");
    vs.className = "chip-stat " + (c.change > 0 ? "up" : c.change < 0 ? "down" : "");
    vs.innerHTML = c.change ? `<svg><use href="#i-${c.change >= 0 ? "up" : "down"}"/></svg>${esc(signed(c.change))} since scanned` : c.unpriced ? `${plural(c.unpriced, "card")} without a price` : `${plural(c.cards, "card")}`;
    const t = trend(30), tr = $("kTrend");
    tr.hidden = !t;
    if (t) { tr.className = "chip-stat " + (t.diff >= 0 ? "up" : "down"); tr.textContent = `${pct(t.pct)} in ${t.days} day${t.days === 1 ? "" : "s"}`; }
    // The three most valuable cards, fanned out.
    const art = c.top.filter(x => x.image).slice(0, 3);
    const key = art.map(x => x.id).join();
    if ($("heroArt").dataset.key !== key) {
      $("heroArt").dataset.key = key;
      $("heroArt").innerHTML = art.map((x, i) => `<a class="fan f${i}" href="/collection?q=${encodeURIComponent(x.name)}" title="${esc(x.name)} · ${esc(money(x.price))}" tabindex="-1"><img src="${esc(x.image)}" alt=""></a>`).reverse().join("");
    }
  }

  function renderNumbers() {
    const c = data.collection, w = data.sessions.week, s = data.scanner.session;
    C.countUp($("kCards"), c.cards);
    $("kCardsSub").textContent = c.cards ? `${c.unique.toLocaleString()} different` + (c.foils ? ` · ${c.foils} foil` : "") : "Scan some to get started";
    $("kCardsSpark").innerHTML = C.spark((c.history || []).slice(-30).map(p => p.cards));
    C.countUp($("kWeek"), w.cards);
    $("kWeekSub").textContent = w.cards ? `cards · ${money(w.value)}` : "cards";
    $("kWeekSpark").innerHTML = C.spark(data.sessions.days.slice(-7).map(d => d.cards));
    C.countUp($("kSession"), s.count);
    $("kSessionSub").textContent = s.count ? `cards · ${money(s.value)}` : data.scanner.waiting ? "no camera connected" : "since SortR started";
    C.countUp($("kSets"), c.sets);
    const ts = c.top_sets || [];
    $("kSetsSub").textContent = ts.length ? `Most from ${ts[0].name || ts[0].set}` : "None yet";
  }

  function renderValue() {
    const h = data.collection.history || [];
    const lastDay = h.length ? day(h[h.length - 1].day).getTime() : 0;
    const pts = prefs.range === "all" ? h : h.filter(p => lastDay - day(p.day).getTime() <= +prefs.range * 864e5);
    for (const b of $("rangeSeg").children) b.setAttribute("aria-pressed", b.dataset.v === prefs.range);
    C.line($("valueChart"), pts.length >= 2 ? pts : h, {
      fmt: (v, axis) => axis ? axisMoney(v) : money(v),
      tip: p => `${money(p.value)} · ${plural(p.cards, "card")}`,
      empty: `${h.length ? `Today: <b>${money(h[0].value)}</b>. ` : ""}A line appears here once there are two days to compare.`,
    });
  }

  function renderColors() {
    const c = data.collection.colors || {}, m = prefs.colors;
    for (const b of $("colorSeg").children) b.setAttribute("aria-pressed", b.dataset.v === m);
    const segs = Object.keys(COLORS).filter(k => c[k]).map(k => ({ label: COLORS[k], value: c[k][m] || 0, color: `var(--mana-${k})`, href: `/collection?color=${k}` }));
    C.donut($("colorChart"), segs, {
      fmt: v => m === "value" ? money(v) : plural(v, "card"),
      center: m === "value" ? { big: axisMoney(data.collection.value), small: "in value" } : { big: data.collection.cards.toLocaleString(), small: "cards" },
    });
  }

  function renderDays() {
    const days = data.sessions.days;
    C.bars($("dayBars"), days.map(d => ({ value: d.cards, tip: `${day(d.day).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}: ${plural(d.cards, "card")}, ${money(d.value)}` })),
      { axis: [day(days[0].day).toLocaleDateString(undefined, { month: "short", day: "numeric" }), "Today"] });
    if (data.sessions.last) {
      const l = data.sessions.last;
      $("dayBars").insertAdjacentHTML("beforeend", `<p class="sub last">Last session: ${day(l.start).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}, ${plural(l.cards, "card")} worth ${money(l.value)}${l.top ? `. Best find: <b>${esc(l.top.name)}</b> (${money(l.top.price)})` : ""}</p>`);
    }
  }

  // Things worth knowing, worked out from the numbers above. The strongest few are shown.
  function renderInsights() {
    const c = data.collection, s = data.sessions, out = [];
    const add = (weight, icon, tone, html, href) => out.push({ weight, icon, tone, html, href });
    const t = trend(30);
    if (t && Math.abs(t.diff) >= 1) add(9, t.diff >= 0 ? "up" : "down", t.diff >= 0 ? "good" : "bad",
      `Your collection is worth <b>${money(Math.abs(t.diff))}</b> (${pct(t.pct)}) ${t.diff >= 0 ? "more" : "less"} than ${t.days} days ago.`, "/collection");
    const d = s.days, wk = d.slice(-7).reduce((a, x) => a + x.cards, 0), prev = d.slice(0, 7).reduce((a, x) => a + x.cards, 0);
    if (wk || prev) add(7, "clock", "", prev ? `You scanned <b>${plural(wk, "card")}</b> this week, ${Math.round(Math.abs(wk - prev) / prev * 100)}% ${wk >= prev ? "more" : "fewer"} than the week before.`
      : `You scanned <b>${plural(wk, "card")}</b> this week.`, "/history");
    const best = [...d].sort((a, b) => b.cards - a.cards)[0];
    if (best && best.cards) add(4, "spark", "", `Your busiest day lately was <b>${day(best.day).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}</b> with ${plural(best.cards, "card")}.`, "/history");
    const bins = c.bins || [], totalCards = bins.reduce((a, b) => a + b.cards, 0), totalValue = bins.reduce((a, b) => a + (b.value || 0), 0);
    const bulk = bins.find(b => b.bin === 1), top = bins.find(b => b.bin === 3);
    if (bulk && top && totalCards && totalValue) add(8, "bins", "", `<b>${Math.round(top.cards / totalCards * 100)}%</b> of your cards (bin 3) hold <b>${Math.round((top.value || 0) / totalValue * 100)}%</b> of the value. Bulk in bin 1 is ${Math.round(bulk.cards / totalCards * 100)}% of the cards.`, "/bins");
    const colors = Object.entries(c.colors || {}).filter(([k]) => COLORS[k]).sort((a, b) => b[1].value - a[1].value);
    if (colors.length && c.value) add(5, "tag", "", `<b>${COLORS[colors[0][0]]}</b> is your most valuable color: ${money(colors[0][1].value)}, ${Math.round(colors[0][1].value / c.value * 100)}% of the collection.`, `/collection?color=${colors[0][0]}`);
    const up = c.movers.up[0], down = c.movers.down[0];
    if (up) add(6, "up", "good", `<b>${esc(up.name)}</b> went up <b>${signed(up.change)}</b> since you scanned it.`, "/collection?sort=up");
    if (down) add(6, "down", "bad", `<b>${esc(down.name)}</b> dropped <b>${signed(down.change).replace("−", "")}</b> since you scanned it.`, "/collection?sort=down");
    if (c.unpriced) add(10, "tag", "warn", `<b>${plural(c.unpriced, "card")}</b> ${c.unpriced === 1 ? "has" : "have"} no price yet. Refresh prices on the Collection page.`, "/collection");
    if (data.wishlist.owned) add(7, "heart", "", `<b>${plural(data.wishlist.owned, "card")}</b> on your wishlist ${data.wishlist.owned === 1 ? "is" : "are"} already in your collection.`, "/wishlist");
    if (!c.cards) add(10, "spark", "", "Scan your first cards and SortR starts tracking their value, colors and sets here.", "/scan");
    const shown = out.sort((a, b) => b.weight - a.weight).slice(0, 5);
    $("insights").innerHTML = shown.map(i => `<a class="insight ${i.tone}" href="${i.href}"><span class="i-ico"><svg><use href="#i-${i.icon}"/></svg></span><span>${i.html}</span></a>`).join("")
      || '<p class="none">Scan a few cards and SortR will point out what stands out.</p>';
  }

  const tile = c => `<a class="tile${c.foil ? " foil" : ""}" href="/collection?q=${encodeURIComponent(c.name)}" title="${esc(c.name)}">
      <div class="art">${c.image ? `<img src="${esc(small(c.image))}" alt="" loading="lazy">` : `<span class="noimg">${esc(c.name)}</span>`}</div>
      <b>${esc(c.name)}</b><span>${esc(c.set)}${c.foil ? " · foil" : ""}<em>${money(c.price)}</em></span></a>`;

  const row = (c, end, i) => `<a class="rank-row" href="/collection?q=${encodeURIComponent(c.name)}">
      ${i != null ? `<span class="rank-n">${i + 1}</span>` : ""}<span class="thumb">${c.image ? `<img src="${esc(small(c.image))}" alt="" loading="lazy">` : ""}</span>
      <span class="info"><b>${esc(c.name)}</b><small>${esc(c.set)} #${esc(c.number)}${c.foil ? " · foil" : ""}${c.qty > 1 ? ` · ×${c.qty}` : ""}</small></span>${end}</a>`;

  function renderCards() {
    const c = data.collection;
    $("recent").innerHTML = c.recent.length ? c.recent.map(tile).join("")
      : '<p class="none">Nothing yet. Cards you save on the <a href="/scan">Scanner</a> show up here.</p>';
    $("topList").innerHTML = c.top.length ? c.top.map((x, i) => row(x, `<b class="amt">${money(x.price)}</b>`, i)).join("") : '<p class="none">No priced cards yet.</p>';
    const mv = [...c.movers.up, ...c.movers.down];
    $("moverList").innerHTML = mv.length ? mv.map(x => row(x, `<b class="amt ${x.change > 0 ? "up" : "down"}">${signed(x.change)}</b>`)).join("")
      : '<p class="none">No price has moved yet. Refresh prices on the Collection page to check.</p>';
    const total = Math.max(1, c.bins.reduce((a, b) => a + b.cards, 0));
    $("binRows").innerHTML = c.bins.map(b => `<a class="bin-row" href="/collection?bin=${b.bin}"><span class="pill bin-${b.bin}">${b.bin}</span><span class="nm">${esc(b.name)}</span><b>${b.cards.toLocaleString()}</b>
      <span class="track"><i style="width:${(b.cards / total * 100).toFixed(1)}%;background:${BINVAR(b.bin)}"></i></span><small class="bin-val">${money(b.value || 0)}</small></a>`).join("");
    $("scDecks").textContent = data.decks.count ? `${plural(data.decks.count, "saved deck")}. Check what you're missing` : "Check a decklist against your cards";
    $("scWish").textContent = data.wishlist.items ? `${plural(data.wishlist.items, "card")}` + (data.wishlist.owned ? `, ${data.wishlist.owned} already owned` : "") : "Cards you want, and the price you'd pay";
    $("scHistory").textContent = data.sessions.count ? `${plural(data.sessions.count, "session")} so far` : "Past scanning sessions";
  }

  async function load() {
    try {
      data = await api("/api/home");
      renderStatus(); renderHero(); renderNumbers(); renderValue(); renderColors(); renderDays(); renderInsights(); renderCards();
      document.body.classList.remove("offline", "loading");
      first = false;
    } catch (e) {
      if (e.message === "Locked") return;
      document.body.classList.add("offline");
      $("heroLine").textContent = "Can't reach SortR. It may be restarting; trying again…";
    }
  }
  $("rangeSeg").onclick = e => { const b = e.target.closest("button"); if (b && data) { prefs.range = b.dataset.v; save(); renderValue(); } };
  $("colorSeg").onclick = e => { const b = e.target.closest("button"); if (b && data) { prefs.colors = b.dataset.v; save(); renderColors(); } };
  window.addEventListener("mtg-health", e => { health = e.detail; if (data) renderStatus(); });
  // Redraw the line when its box changes size (the window, or the Colors panel next to it growing).
  let rt, lastW = 0, lastH = 0;
  new ResizeObserver(([e]) => {
    const { width, height } = e.contentRect;
    if (Math.abs(width - lastW) < 2 && Math.abs(height - lastH) < 2) return;
    lastW = width; lastH = height;
    clearTimeout(rt); rt = setTimeout(() => { if (data) renderValue(); }, 60);
  }).observe($("valueChart"));

  document.body.classList.add("loading");
  greet();
  setTimeout(greet, 1500);   // the name arrives with the account
  load();
  // Keep it fresh while it's open (the scanner may be saving cards on another device).
  let t = setInterval(load, 10000);
  document.addEventListener("visibilitychange", () => { clearInterval(t); if (!document.hidden) { load(); t = setInterval(load, 10000); } });
})();
