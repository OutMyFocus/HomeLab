// SortR's charts: a value line with a hover readout, a donut with its legend, day bars and
// tiny sparklines. Plain SVG drawn from data, in the page's colors (CSS variables), so they
// follow the theme and the accent. Used by Home; any page can use window.SortRCharts.
window.SortRCharts = (() => {
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  let uid = 0;
  const day = iso => new Date(iso.length === 10 ? iso + "T12:00:00" : iso);
  const short = d => day(d).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const long = d => day(d).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });

  // A smooth path through the points (monotone, so it never overshoots between days).
  function smooth(P) {
    if (P.length < 3) return P.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("");
    const n = P.length, d = [], m = [];
    for (let i = 0; i < n - 1; i++) d.push((P[i + 1][1] - P[i][1]) / (P[i + 1][0] - P[i][0] || 1));
    m[0] = d[0]; m[n - 1] = d[n - 2];
    for (let i = 1; i < n - 1; i++) m[i] = d[i - 1] * d[i] <= 0 ? 0 : (d[i - 1] + d[i]) / 2;
    let s = `M${P[0][0].toFixed(1)},${P[0][1].toFixed(1)}`;
    for (let i = 0; i < n - 1; i++) {
      const h = (P[i + 1][0] - P[i][0]) / 3;
      s += `C${(P[i][0] + h).toFixed(1)},${(P[i][1] + m[i] * h).toFixed(1)} ${(P[i + 1][0] - h).toFixed(1)},${(P[i + 1][1] - m[i + 1] * h).toFixed(1)} ${P[i + 1][0].toFixed(1)},${P[i + 1][1].toFixed(1)}`;
    }
    return s;
  }

  // pts: [{day, value, ...}], fmt: value → text. Hovering (or dragging a finger) shows the day.
  function line(box, pts, { fmt = v => v, tip = p => fmt(p.value), empty = "" } = {}) {
    if (pts.length < 2) { box.innerHTML = `<div class="empty"><p>${empty}</p></div>`; return; }
    const id = "g" + (++uid);
    const W = box.clientWidth || 600, H = box.clientHeight || 220, L = 56, R = 12, T = 14, B = 26;
    const vals = pts.map(p => p.value), lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * .15 || Math.max(1, hi * .05), y0 = Math.max(0, lo - pad), y1 = hi + pad;
    const t = pts.map(p => day(p.day).getTime()), t0 = t[0], t1 = t[t.length - 1];
    const x = v => L + (v - t0) / (t1 - t0 || 1) * (W - L - R), y = v => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
    const P = pts.map((p, i) => [x(t[i]), y(p.value)]);
    const path = smooth(P);
    const ticks = [0, 1, 2, 3].map(i => y0 + (y1 - y0) * i / 3);
    const last = P[P.length - 1];
    box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Over time, now ${esc(fmt(vals[vals.length - 1]))}">
      <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--accent)" stop-opacity=".32"/><stop offset="1" stop-color="var(--accent)" stop-opacity="0"/></linearGradient>
      <linearGradient id="${id}s" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="var(--accent)"/><stop offset="1" stop-color="var(--accent-2)"/></linearGradient></defs>
      ${ticks.map(v => `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/><text class="axis" x="${L - 10}" y="${y(v).toFixed(1)}" text-anchor="end" dominant-baseline="middle">${esc(fmt(v, true))}</text>`).join("")}
      <text class="axis" x="${L}" y="${H - 6}">${short(pts[0].day)}</text><text class="axis" x="${W - R}" y="${H - 6}" text-anchor="end">${short(pts[pts.length - 1].day)}</text>
      <path d="${path}L${last[0].toFixed(1)},${H - B}L${L},${H - B}Z" fill="url(#${id})"/>
      <path class="line" d="${path}" stroke="url(#${id}s)"/>
      <circle class="halo" r="9" cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}"/><circle class="dot" r="4.5" cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}"/>
      <g class="hover" visibility="hidden"><line class="cross" y1="${T}" y2="${H - B}"/><circle class="dot" r="4.5"/></g>
      <rect class="hit" x="${L}" y="0" width="${W - L - R}" height="${H}" fill="transparent"/></svg><div class="chart-tip" hidden></div>`;
    const svg = box.querySelector("svg"), g = svg.querySelector(".hover"), tipEl = box.querySelector(".chart-tip");
    function show(ev) {
      const r = svg.getBoundingClientRect(), px = (ev.clientX - r.left) * W / r.width;
      let i = 0; for (let k = 1; k < P.length; k++) if (Math.abs(P[k][0] - px) < Math.abs(P[i][0] - px)) i = k;
      g.setAttribute("visibility", "visible");
      g.querySelector("line").setAttribute("x1", P[i][0]); g.querySelector("line").setAttribute("x2", P[i][0]);
      g.querySelector("circle").setAttribute("cx", P[i][0]); g.querySelector("circle").setAttribute("cy", P[i][1]);
      tipEl.hidden = false;
      tipEl.innerHTML = `<small>${long(pts[i].day)}</small><b>${esc(tip(pts[i]))}</b>`;
      const left = P[i][0] * r.width / W, w = tipEl.offsetWidth;
      tipEl.style.left = Math.max(0, Math.min(r.width - w, left - w / 2)) + "px";
      tipEl.style.top = Math.max(0, P[i][1] * r.height / H - tipEl.offsetHeight - 14) + "px";
    }
    const hide = () => { g.setAttribute("visibility", "hidden"); tipEl.hidden = true; };
    svg.addEventListener("pointermove", show); svg.addEventListener("pointerdown", show); svg.addEventListener("pointerleave", hide);
  }

  // segs: [{label, value, color, href?}]; center: {big, small}. The legend lists each with its share.
  function donut(box, segs, { center = {}, fmt = v => v } = {}) {
    const total = segs.reduce((a, s) => a + s.value, 0);
    if (!total) { box.innerHTML = `<div class="empty"><p>Nothing to show yet.</p></div>`; return; }
    const R = 52, C = 2 * Math.PI * R, gap = segs.filter(s => s.value).length > 1 ? 2.2 : 0;
    let at = 0;
    const arcs = segs.filter(s => s.value).map(s => {
      const len = s.value / total * C, a = `<circle class="arc" r="${R}" cx="70" cy="70" stroke="${s.color}" stroke-dasharray="${Math.max(0, len - gap).toFixed(2)} ${C.toFixed(2)}" stroke-dashoffset="${(-at).toFixed(2)}"><title>${esc(s.label)}: ${esc(fmt(s.value))}</title></circle>`;
      at += len; return a;
    }).join("");
    box.innerHTML = `<div class="donut"><svg viewBox="0 0 140 140" role="img" aria-label="${esc(center.small || "")}"><circle class="track" r="${R}" cx="70" cy="70"/><g transform="rotate(-90 70 70)">${arcs}</g></svg>
      <div class="donut-mid"><b>${esc(center.big ?? "")}</b><small>${esc(center.small ?? "")}</small></div></div>
      <ul class="legend">${segs.filter(s => s.value).sort((a, b) => b.value - a.value).map(s => `<li>${s.href ? `<a href="${esc(s.href)}">` : "<span>"}<i style="background:${s.color}"></i><span class="nm">${esc(s.label)}</span><b>${Math.round(s.value / total * 100)}%</b><small>${esc(fmt(s.value))}</small>${s.href ? "</a>" : "</span>"}</li>`).join("")}</ul>`;
  }

  // items: [{label, value, tip}]; the last one (today) is lit.
  function bars(box, items, { axis = [] } = {}) {
    const max = Math.max(1, ...items.map(d => d.value));
    box.innerHTML = `<div class="bars-n" style="grid-template-columns:repeat(${items.length},1fr)">${items.map((d, i) =>
      `<div class="b${i === items.length - 1 ? " now" : ""}" title="${esc(d.tip || "")}" style="--h:${(d.value / max * 100).toFixed(1)}%"><span class="${d.value ? "" : "zero"}"></span>${d.value ? `<em>${d.value.toLocaleString()}</em>` : ""}</div>`).join("")}</div>
      <div class="bars-axis">${axis.map(a => `<span>${esc(a)}</span>`).join("")}</div>`;
  }

  // A tiny line for a stat tile.
  function spark(values, { w = 96, h = 30 } = {}) {
    if (!values || values.length < 2) return "";
    const lo = Math.min(...values), hi = Math.max(...values), id = "s" + (++uid);
    const P = values.map((v, i) => [i / (values.length - 1) * w, h - 3 - (hi === lo ? .5 : (v - lo) / (hi - lo)) * (h - 6)]);
    const d = smooth(P);
    return `<svg class="sparkline" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--accent)" stop-opacity=".3"/><stop offset="1" stop-color="var(--accent)" stop-opacity="0"/></linearGradient></defs>
      <path d="${d}L${w},${h}L0,${h}Z" fill="url(#${id})"/><path d="${d}" fill="none" stroke="var(--accent)" stroke-width="1.8" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>`;
  }

  // Counts a number up from where it was to its new value (only the first time, or when it changes).
  function countUp(el, to, fmt = v => Math.round(v).toLocaleString()) {
    const from = +el.dataset.n || 0;
    el.dataset.n = to;
    if (from === to || matchMedia("(prefers-reduced-motion: reduce)").matches || document.documentElement.classList.contains("no-motion")) { el.textContent = fmt(to); return; }
    const t0 = performance.now(), dur = 700;
    const step = now => {
      const k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      el.textContent = fmt(from + (to - from) * e);
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  return { line, donut, bars, spark, countUp };
})();
