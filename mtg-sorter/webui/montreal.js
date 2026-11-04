// Montreal store prices for one card: Face to Face Games first, then Card Brawlers and
// L'Univers de la Carte (see mtgscanner/montreal.py). Used by the scanner's card panel
// and the Collection's card details:  Montreal.show(element, card)
window.Montreal = (() => {
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = v => "$" + Number(v).toFixed(2);
  const answers = new Map();   // the same card again (rescans, reopening details) answers at once

  const style = document.createElement("style");
  style.textContent = `
    .mtl { margin-top: 12px; padding: 10px 12px; border: 1px solid var(--line); border-radius: calc(var(--radius, 12px) * .7); background: var(--raised); font-size: .9rem; }
    .mtl-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 8px; margin-bottom: 6px; font-weight: 650; }
    .mtl-head small, .mtl .note { color: var(--muted); font-weight: 400; font-size: .8rem; }
    .mtl ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
    .mtl li { display: grid; grid-template-columns: minmax(0, 1fr) auto; column-gap: 10px; align-items: baseline; }
    .mtl li > a, .mtl li > span:first-child { grid-column: 1; grid-row: 1; }
    .mtl li a { color: inherit; text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .mtl li a:hover { text-decoration: underline; }
    .mtl li .tag { grid-column: 1; grid-row: 2; color: var(--muted); font-size: .76rem; }
    .mtl li .tag.exact { color: var(--accent); }
    .mtl li b { grid-column: 2; grid-row: 1; font-variant-numeric: tabular-nums; }
    .mtl li.out b { color: var(--muted); font-weight: 500; }
    .mtl li.first a { font-weight: 600; }
    .mtl-links { margin-top: 8px; color: var(--muted); font-size: .8rem; }
    .mtl-links a { color: var(--accent); }
    td .mtl-store { display: block; color: var(--muted); font-size: .72rem; }`;
  document.head.appendChild(style);

  function params(c) {
    return new URLSearchParams({ name: c.name || "", set: c.set || "", set_name: c.set_name || "", number: c.number || "", foil: c.foil ? "1" : "0" });
  }

  function render(el, d) {
    const when = d.checked === "today" ? "today" : d.date ? `price check of ${d.date}` : "";
    const rows = (d.stores || []).map((s, i) => `<li class="${i === 0 ? "first" : ""} ${s.in_stock === false ? "out" : ""}">
        ${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener" title="${esc(s.title || s.store)}">${esc(s.store)}</a>` : `<span>${esc(s.store)}</span>`}
        <span class="tag ${s.exact ? "exact" : ""}">${s.exact ? "this printing" : d.checked === "today" ? "cheapest" : ""}${s.in_stock === false ? " · out of stock" : ""}</span>
        <b>${money(s.price)}</b></li>`).join("");
    const links = (d.links || []).map(l => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.store)}</a>`).join(" · ");
    el.innerHTML = `<div class="mtl-head">Montreal stores <small>${esc(when)}${d.foil ? " · foil" : ""} · Near Mint</small></div>
      ${rows ? `<ul>${rows}</ul>` : `<div class="note">No Montreal store lists this card right now.</div>`}
      ${links ? `<div class="mtl-links">Also check: ${links}</div>` : ""}`;
  }

  async function show(el, c) {
    if (!el) return;
    if (!c || !c.name) { el.hidden = true; el.dataset.key = ""; return; }
    const key = params(c).toString();
    if (el.dataset.key === key) return;   // already showing (or fetching) this card
    el.dataset.key = key; el.hidden = false;
    if (answers.has(key)) return render(el, answers.get(key));
    el.innerHTML = `<div class="mtl-head">Montreal stores <small>checking Face to Face Games and others…</small></div>`;
    try {
      const r = await fetch("/api/montreal?" + key);
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || r.statusText);
      answers.set(key, d);
      if (el.dataset.key === key) render(el, d);
    } catch (e) {
      if (el.dataset.key === key) { el.innerHTML = `<div class="mtl-head">Montreal stores <small>couldn't reach the stores</small></div>`; el.dataset.key = ""; }
    }
  }

  // The Collection table's Montreal cell: Face to Face Games' price, else the next store's.
  function cell(c) {
    if (!c.mtl) return "";
    const f2f = c.mtl.store === "Face to Face Games";
    return `${money(c.mtl.price)}${f2f ? "" : `<small class="mtl-store">${esc(c.mtl.store)}</small>`}`;
  }

  return { show, cell };
})();
