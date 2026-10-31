// The History page: scanning sessions and cards per day.
(() => {
  const { $, esc, money, toast, api, download } = MTG;
  let data = null, shown = 20, open = new Set();
  const day = iso => new Date(iso).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", year: "numeric" });
  const clock = iso => new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });

  async function load() {
    try { data = await api("/api/history"); render(); } catch (e) { toast(e.message); }
  }

  function render() {
    const s = data.sessions;
    $("tSessions").textContent = data.total_sessions.toLocaleString();
    $("tSessionsSub").textContent = s[0] ? `Last one ${day(s[0].start)}` : "Scan some cards to start";
    const week = data.days.slice(-7), wc = week.reduce((n, d) => n + d.cards, 0), wv = week.reduce((v, d) => v + d.value, 0);
    $("tWeek").textContent = wc.toLocaleString();
    $("tWeekSub").textContent = `cards · ${money(wv)}`;
    const best = s.reduce((b, x) => !b || x.cards > b.cards ? x : b, null);
    $("tBest").textContent = best ? best.cards.toLocaleString() : "0";
    $("tBestSub").textContent = best ? `cards on ${day(best.start)}` : "";
    const find = s.reduce((b, x) => x.top.price && (!b || x.top.price > b.price) ? x.top : b, null);
    $("tFind").textContent = find ? find.name : "None yet";
    $("tFindSub").textContent = find ? `${money(find.price)} · ${find.set}` : "";
    renderDays(); renderSessions();
  }

  // Cards per day: one bar per day, hover for the number.
  function renderDays() {
    const d = data.days, max = Math.max(1, ...d.map(x => x.cards)), box = $("dayChart");
    const W = box.clientWidth || 700, H = 170, B = 22, gap = 2, bw = (W - gap * (d.length - 1)) / d.length;
    const total = d.reduce((n, x) => n + x.cards, 0);
    $("dayNote").textContent = `${total.toLocaleString()} cards`;
    const fmt = iso => new Date(iso + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
    box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Cards scanned each day">
      <line class="grid" x1="0" x2="${W}" y1="${H - B}" y2="${H - B}"/>
      ${d.map((x, i) => {
        const h = x.cards ? Math.max(3, (H - B - 8) * x.cards / max) : 0, xx = i * (bw + gap);
        return `<rect class="hit" data-i="${i}" x="${xx.toFixed(1)}" y="0" width="${bw.toFixed(1)}" height="${H - B}" fill="transparent"/>
          ${h ? `<rect class="bar" x="${xx.toFixed(1)}" y="${(H - B - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="${Math.min(4, bw / 2).toFixed(1)}"/>` : ""}`;
      }).join("")}
      <text class="axis" x="0" y="${H - 5}">${fmt(d[0].day)}</text>
      <text class="axis" x="${W}" y="${H - 5}" text-anchor="end">Today</text>
    </svg><div class="tip" id="tip" hidden></div>`;
    box.onpointermove = e => {
      const r = e.target.closest(".hit"), tip = $("tip");
      if (!r) return tip.hidden = true;
      const x = d[+r.dataset.i], br = box.getBoundingClientRect(), rr = r.getBoundingClientRect();
      tip.hidden = false; tip.style.left = (rr.left - br.left + rr.width / 2) + "px"; tip.style.top = "40px";
      tip.innerHTML = `<b>${x.cards.toLocaleString()} cards</b>${fmt(x.day)} · ${money(x.value)}`;
    };
    box.onpointerleave = () => $("tip").hidden = true;
  }

  function renderSessions() {
    const s = data.sessions.slice(0, shown);
    $("sessions").innerHTML = s.length ? s.map(x => `<div class="session-row${open.has(x.start) ? " open" : ""}" data-start="${esc(x.start)}">
      <button class="session-sum" aria-expanded="${open.has(x.start)}">
        <span class="when"><b>${esc(day(x.start))}</b><small>${esc(clock(x.start))} to ${esc(clock(x.end))}${x.minutes ? ` · ${x.minutes} min` : ""}</small></span>
        <span class="nums"><b>${x.cards.toLocaleString()}</b><small>cards</small></span>
        <span class="nums"><b>${money(x.value)}</b><small>when scanned</small></span>
        <span class="topcard hide-sm">${x.top.price ? `Best: <b>${esc(x.top.name)}</b> ${money(x.top.price)}` : ""}</span>
      </button>
      ${open.has(x.start) ? `<div class="session-body">
        <div class="session-acts">
          ${Object.entries(x.bins).map(([b, n]) => `<span class="pill bin-chip">${esc(b)} · ${n}</span>`).join("")}
          <span class="grow"></span>
          <button class="btn ghost" data-export="manabox"><svg><use href="#i-download"/></svg>CSV for Commander Vault</button>
          <button class="btn ghost" data-export="moxfield"><svg><use href="#i-download"/></svg>Moxfield</button>
          <button class="btn ghost danger" data-delete><svg><use href="#i-trash"/></svg>Remove these cards</button>
        </div>
        <div class="table-wrap"><table class="list"><thead><tr><th>Card</th><th class="hide-sm">Set</th><th class="num">Price</th><th class="hide-sm">Bin</th><th class="num">Time</th></tr></thead><tbody>
        ${x.rows.map(r => `<tr><td class="card-cell">${r.id ? `<img class="thumb" src="https://api.scryfall.com/cards/${esc(r.id)}?format=image&version=small" alt="" loading="lazy">` : '<span class="thumb"></span>'}<span><span class="nm">${esc(r.name)}</span>${r.foil ? '<span class="foil-tag">foil</span>' : ""}${r.qty > 1 ? ` ×${r.qty}` : ""}</span></td>
          <td class="hide-sm">${esc(r.set)} #${esc(r.number)}</td><td class="num">${money(r.price)}</td><td class="hide-sm">${esc(r.bin)}</td><td class="num">${esc(r.time)}</td></tr>`).join("")}
        </tbody></table></div></div>` : ""}
    </div>`).join("") : '<p class="results-empty">No scans yet. Cards you save on the <a href="/">Scanner</a> show up here.</p>';
    $("moreBtn").hidden = data.sessions.length <= shown;
  }

  $("sessions").onclick = async e => {
    const row = e.target.closest(".session-row"); if (!row) return;
    const x = data.sessions.find(s => s.start === row.dataset.start);
    if (e.target.closest(".session-sum")) {
      open.has(x.start) ? open.delete(x.start) : open.add(x.start);
      return renderSessions();
    }
    const ex = e.target.closest("[data-export]");
    if (ex) {
      try { toast(`Downloaded ${await download("/api/history/export", { start: x.start, end: x.end, format: ex.dataset.export })}`); }
      catch (err) { toast(err.message); }
      return;
    }
    if (e.target.closest("[data-delete]")) {
      if (!confirm(`Remove all ${x.cards} cards scanned on ${day(x.start)} between ${clock(x.start)} and ${clock(x.end)} from your collection? This can't be undone.`)) return;
      try { data = await api("/api/history/delete", { start: x.start, end: x.end }); render(); toast(`Removed ${x.cards} cards`); }
      catch (err) { toast(err.message); }
    }
  };
  $("moreBtn").onclick = () => { shown += 40; renderSessions(); };
  let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => data && renderDays(), 150); });
  load();
})();
