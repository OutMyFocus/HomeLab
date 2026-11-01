// The Home page: one look at the scanner, the machine, the collection and the Pi.
(() => {
  const { $, esc, money, api } = window.MTG;
  const signed = v => (v > 0 ? "+" : v < 0 ? "−" : "") + money(Math.abs(v));
  const small = url => url ? url.replace("version=normal", "version=small") : "";
  const plural = (n, word) => `${n.toLocaleString()} ${word}${n === 1 ? "" : "s"}`;
  const day = iso => new Date(iso.length === 10 ? iso + "T12:00:00" : iso);
  const BINVAR = b => `var(--bin${b}, var(--muted))`;
  let data = null, health = window.MTGHealth || null;

  function greet() {
    const h = new Date().getHours();
    $("hello").textContent = h < 5 ? "Up late?" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
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
      line.innerHTML = "No camera is connected, so live scanning is paused. You can still scan photos of your cards, " +
        'and <a href="/maintenance">the check-up</a> says what to look at.';
      btn.lastChild.textContent = "Open the scanner";
    } else if (s.on_table) {
      line.textContent = `${plural(s.on_table, "card")} on the table right now` + (s.session.count ? `, ${plural(s.session.count, "card")} saved this session.` : ".");
      btn.lastChild.textContent = "Back to scanning";
    } else if (s.session.count) {
      line.textContent = `${plural(s.session.count, "card")} saved this session, worth ${money(s.session.value)}. Ready for more.`;
      btn.lastChild.textContent = "Keep scanning";
    } else {
      line.textContent = `Ready to scan. The scanner knows ${s.db_count.toLocaleString()} cards` + (s.learned ? ` and has learned ${plural(s.learned, "scan")} of yours.` : ".");
      btn.lastChild.textContent = "Start scanning";
    }
  }

  function renderNumbers() {
    const c = data.collection, w = data.sessions.week, s = data.scanner.session;
    $("kValue").textContent = money(c.value);
    const vs = $("kValueSub");
    vs.className = "sub " + (c.change > 0 ? "up" : c.change < 0 ? "down" : "");
    vs.textContent = c.change ? `${signed(c.change)} since scanned` : c.unpriced ? `${plural(c.unpriced, "card")} without a price` : "";
    $("kCards").textContent = c.cards.toLocaleString();
    $("kCardsSub").textContent = c.cards ? `${c.unique.toLocaleString()} different · ${plural(c.sets, "set")}` + (c.foils ? ` · ${c.foils} foil` : "") : "Scan some to get started";
    $("kWeek").textContent = w.cards.toLocaleString();
    $("kWeekSub").textContent = w.cards ? `cards · ${money(w.value)}` : "cards";
    $("kSession").textContent = s.count.toLocaleString();
    $("kSessionSub").textContent = s.count ? `cards · ${money(s.value)}` : data.scanner.waiting ? "no camera" : "since the app started";
  }

  // Value over time: one point a day, noted whenever Home or Collection is opened.
  function renderValue() {
    const box = $("valueChart"), pts = data.collection.history || [];
    if (pts.length < 2) {
      box.innerHTML = `<div class="empty"><p>${pts.length ? `Today: <b>${money(pts[0].value)}</b>. ` : ""}A line appears here once there are two days to compare.</p></div>`;
      return;
    }
    const W = box.clientWidth || 600, H = box.clientHeight || 200, L = 54, R = 10, T = 10, B = 24;
    const vals = pts.map(p => p.value), lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * .12 || Math.max(1, hi * .05), y0 = Math.max(0, lo - pad), y1 = hi + pad;
    const t = pts.map(p => day(p.day).getTime()), t0 = t[0], t1 = t[t.length - 1];
    const x = v => L + (v - t0) / (t1 - t0 || 1) * (W - L - R), y = v => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
    const fmt = d => day(d).toLocaleDateString(undefined, { month: "short", day: "numeric" });
    const line = pts.map((p, i) => `${i ? "L" : "M"}${x(t[i]).toFixed(1)},${y(p.value).toFixed(1)}`).join("");
    const ticks = [0, 1, 2].map(i => y0 + (y1 - y0) * i / 2);
    box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Collection value over time, now ${money(vals[vals.length - 1])}">
      ${ticks.map(v => `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/><text class="axis" x="${L - 8}" y="${y(v).toFixed(1)}" text-anchor="end" dominant-baseline="middle">$${Math.round(v).toLocaleString()}</text>`).join("")}
      <text class="axis" x="${L}" y="${H - 5}">${fmt(pts[0].day)}</text><text class="axis" x="${W - R}" y="${H - 5}" text-anchor="end">${fmt(pts[pts.length - 1].day)}</text>
      <path class="area" d="${line}L${x(t1).toFixed(1)},${H - B}L${L},${H - B}Z"/><path class="line" d="${line}"/>
      <circle class="dot" r="4" cx="${x(t1).toFixed(1)}" cy="${y(vals[vals.length - 1]).toFixed(1)}"/></svg>`;
  }

  function renderDays() {
    const days = data.sessions.days, max = Math.max(1, ...days.map(d => d.cards));
    $("dayBars").innerHTML = `<div class="bars14">${days.map(d => {
      const label = day(d.day).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
      return `<div class="b" title="${esc(label)}: ${plural(d.cards, "card")}, ${money(d.value)}"><span style="height:${(d.cards / max * 100).toFixed(1)}%"${d.cards ? "" : ' class="zero"'}></span></div>`;
    }).join("")}</div><div class="bars14-axis"><span>${day(days[0].day).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span><span>Today</span></div>`
      + (data.sessions.last ? `<p class="sub last">Last session: ${day(data.sessions.last.start).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}, ${plural(data.sessions.last.cards, "card")} worth ${money(data.sessions.last.value)}</p>` : "");
  }

  const tile = c => `<a class="tile${c.foil ? " foil" : ""}" href="/collection?q=${encodeURIComponent(c.name)}" title="${esc(c.name)}">
      <div class="art">${c.image ? `<img src="${esc(small(c.image))}" alt="" loading="lazy">` : `<span class="noimg">${esc(c.name)}</span>`}</div>
      <b>${esc(c.name)}</b><span>${esc(c.set)}${c.foil ? " · foil" : ""}<em>${money(c.price)}</em></span></a>`;

  const row = (c, end) => `<a class="rank-row" href="/collection?q=${encodeURIComponent(c.name)}">
      <span class="thumb">${c.image ? `<img src="${esc(small(c.image))}" alt="" loading="lazy">` : ""}</span>
      <span class="info"><b>${esc(c.name)}</b><small>${esc(c.set)} #${esc(c.number)}${c.foil ? " · foil" : ""}${c.qty > 1 ? ` · ×${c.qty}` : ""}</small></span>${end}</a>`;

  function renderCards() {
    const c = data.collection;
    $("recent").innerHTML = c.recent.length ? c.recent.map(tile).join("")
      : '<p class="none">Nothing yet. Cards you save on the <a href="/scan">Scanner</a> show up here.</p>';
    $("topList").innerHTML = c.top.length ? c.top.map(x => row(x, `<b class="amt">${money(x.price)}</b>`)).join("") : '<p class="none">No priced cards yet.</p>';
    const mv = [...c.movers.up, ...c.movers.down];
    $("moverList").innerHTML = mv.length ? mv.map(x => row(x, `<b class="amt ${x.change > 0 ? "up" : "down"}">${signed(x.change)}</b>`)).join("")
      : '<p class="none">No price has moved yet. Refresh prices on the Collection page to check.</p>';
    const total = Math.max(1, c.bins.reduce((a, b) => a + b.cards, 0));
    $("binRows").innerHTML = c.bins.map(b => `<div class="bin-row"><span class="pill bin-${b.bin}">${b.bin}</span><span class="nm">${esc(b.name)}</span><b>${b.cards.toLocaleString()}</b>
      <span class="track"><i style="width:${(b.cards / total * 100).toFixed(1)}%;background:${BINVAR(b.bin)}"></i></span></div>`).join("");
    $("scDecks").textContent = data.decks.count ? `${plural(data.decks.count, "saved deck")}. Check what you're missing` : "Check a decklist against your cards";
    $("scWish").textContent = data.wishlist.items ? `${plural(data.wishlist.items, "card")}` + (data.wishlist.owned ? `, ${data.wishlist.owned} already owned` : "") : "Cards you want, and the price you'd pay";
    $("scHistory").textContent = data.sessions.count ? `${plural(data.sessions.count, "session")} so far` : "Past scanning sessions";
  }

  async function load() {
    try {
      data = await api("/api/home");
      renderStatus(); renderNumbers(); renderValue(); renderDays(); renderCards();
      document.body.classList.remove("offline");
    } catch (e) {
      if (e.message === "Locked") return;
      document.body.classList.add("offline");
      $("heroLine").textContent = "Can't reach the sorter. It may be restarting; trying again…";
    }
  }
  window.addEventListener("mtg-health", e => { health = e.detail; if (data) renderStatus(); });
  addEventListener("resize", () => { if (data) renderValue(); });

  greet();
  load();
  // Keep it fresh while it's open (the scanner may be saving cards on another device).
  let t = setInterval(load, 10000);
  document.addEventListener("visibilitychange", () => { clearInterval(t); if (!document.hidden) { load(); t = setInterval(load, 10000); } });
})();
