// "Upgrade this deck" on the Decks page. For the deck's commander it gets the cards other
// players run with it (EDHREC, through /api/decks/upgrades), then pairs each strong card
// the deck doesn't have with the deck's weakest card of the same kind (land for land,
// spell for spell). The swaps come in steps, from the fewest changes to the most: a quick
// fix of 3, a tune-up, a big upgrade, then the fully optimized deck. Cards you own are
// marked free. Each step's button makes the swaps in the decklist.
(() => {
  const { $, esc, toast, api } = MTG;
  const V = VAULT, { norm, cad } = V;
  const STEPS = [
    [3, "Quick fix", "The few swaps that help the most"],
    [8, "Tune-up", "Five more solid swaps"],
    [15, "Big upgrade", "The deck gets close to what most players run"],
    [30, "Fully optimized", "Every swap EDHREC's players agree on"],
  ];
  const MIN_GAIN = 0.1;   // an add must be in at least 10% more decks than the card it replaces
  const recs = new Map(); // commander -> EDHREC answer (or {error})
  let shown = "", swaps = [];

  const score = c => c ? c.inc + 0.5 * Math.max(0, c.syn) : 0;
  const pct = c => c ? Math.round(c.inc * 100) + "%" : "0%";
  const landish = (name, rec) => V.lookup(name) ? window.DECKBUILDER.isLand(name) : /land/i.test(rec?.list || "");

  async function load(cmd) {
    if (recs.has(cmd)) return recs.get(cmd);
    const p = api("/api/decks/upgrades?commander=" + encodeURIComponent(cmd)).catch(e => ({ error: e.message }));
    recs.set(cmd, p);
    const r = await p;
    if (r.error) setTimeout(() => recs.delete(cmd), 60000);   // try again later
    return r;
  }

  function plan(deck, rec) {
    const by = new Map(rec.cards.map(c => [norm(c.n), c]));
    const inDeck = new Set([norm(deck.commander), ...deck.list.map(([n]) => norm(n))]);
    const budget = +$("uBudget").value || 0, ownedOnly = $("uOwned").checked;
    // The deck's cards, weakest first. Cards EDHREC doesn't list for this commander count as 0,
    // and among those the less popular card overall goes first.
    const cuts = deck.list.filter(([n, q]) => q === 1 && !V.BASICS.has(norm(n)))
      .map(([n]) => { const r = by.get(norm(n)); return { n, s: score(r), r, land: landish(n, r), rank: V.lookup(n)?.e || 1e6 }; })
      .sort((a, b) => a.s - b.s || b.rank - a.rank);
    const adds = rec.cards.filter(c => !inDeck.has(norm(c.n)) && !V.BASICS.has(norm(c.n)) && !V.lookup(c.n)?.b)
      .map(c => {
        const own = V.ownedQty(c.n) > 0, price = own ? 0 : (V.priceOf(c.n) ?? c.p);
        return { n: c.n, s: score(c), r: c, land: landish(c.n, c), own, price };
      })
      .filter(a => a.own || (!ownedOnly && (!budget || (a.price != null && a.price <= budget))))
      .sort((a, b) => (b.s + (b.own ? .05 : 0)) - (a.s + (a.own ? .05 : 0)));
    const out = [], used = new Set();
    // A deck short of 100 cards gets the best cards for its empty slots first.
    let empty = Math.max(0, 99 - deck.list.reduce((s, [, q]) => s + q, 0));
    for (const a of adds) {
      if (out.length >= STEPS.at(-1)[0]) break;
      if (empty > 0) { out.push({ add: a, cut: null, gain: a.s }); empty--; continue; }
      const cut = cuts.find(c => c.land === a.land && !used.has(c.n));
      if (!cut || a.s - cut.s < MIN_GAIN) continue;
      used.add(cut.n);
      out.push({ add: a, cut, gain: a.s - cut.s });
    }
    return out.sort((x, y) => (y.gain + (y.add.own ? .05 : 0)) - (x.gain + (x.add.own ? .05 : 0)));
  }

  function row(sw, i) {
    const a = sw.add, c = sw.cut;
    const link = n => `<a class="cardlink" href="/cards?card=${encodeURIComponent(n)}">${esc(n)}</a>`;
    return `<li>
      <span class="swap-out">${c ? `<b>Cut</b> ${link(c.n)} <small>in ${pct(c.r)} of decks</small>` : `<b>Empty slot</b>`}</span>
      <span class="swap-in"><b>Add</b> ${link(a.n)} <small>in ${pct(a.r)} of decks</small></span>
      <span class="swap-cost">${a.own ? '<span class="badge good">You own it</span>' : a.price != null ? cad(a.price) : '<span class="sub">no price</span>'}</span>
      <button class="btn ghost small-btn" data-swap="${i}">Swap</button>
    </li>`;
  }

  function draw(deck, rec) {
    swaps = plan(deck, rec);
    $("uSub").innerHTML = `From ${rec.decks.toLocaleString()} decks on <a href="${esc(rec.url)}" target="_blank" rel="noopener">EDHREC</a>${rec.stale ? " (saved copy)" : ""}`;
    $("uTools").hidden = false;
    if (!swaps.length) {
      $("uNote").textContent = $("uOwned").checked || $("uBudget").value
        ? "Nothing to swap at this price. Try a higher price or turn off Only cards I own."
        : "This deck already runs what most players run with this commander. Nice.";
      $("uSteps").innerHTML = ""; return;
    }
    $("uNote").textContent = "Each swap cuts the card players run least with this commander for one they run a lot more. Start at step 1; each step adds more changes.";
    let from = 0, total = 0, html = "";
    STEPS.forEach(([upTo, title, line], k) => {
      const part = swaps.slice(from, upTo);
      if (!part.length) return;
      const cost = part.reduce((s, x) => s + (x.add.price || 0), 0), own = part.filter(x => x.add.own).length;
      total += cost;
      const end = from + part.length;
      html += `<details class="step"${k === 0 ? " open" : ""}>
        <summary><span class="step-n">${k + 1}</span><span class="step-t"><b>${title}</b><small>${line}</small></span>
          <span class="step-m"><b>${part.length} swap${part.length > 1 ? "s" : ""}</b><small>${cost ? cad(cost) + " to buy" : "Free"}${own ? ` · ${own} you own` : ""}</small></span></summary>
        <ul class="swaps">${part.map((sw, j) => row(sw, from + j)).join("")}</ul>
        <div class="step-foot"><span class="sub">${k ? `Steps 1 to ${k + 1}: ${end} swaps, ${total ? cad(total) : "free"}` : ""}</span>
          <button class="btn primary" data-upto="${end}">${k ? `Make steps 1 to ${k + 1}` : `Make these ${part.length} swaps`}</button></div>
      </details>`;
      from = end;
    });
    $("uSteps").innerHTML = html;
  }

  async function render() {
    if ($("builder").hidden || !window.DECKBUILDER) return;
    const deck = window.DECKBUILDER.read(), cmd = deck.commander;
    if (!cmd) { shown = ""; $("uSub").textContent = ""; $("uTools").hidden = true; $("uSteps").innerHTML = ""; $("uNote").textContent = "Set a commander to see upgrades."; return; }
    if (shown !== cmd) { $("uNote").textContent = `Looking up what players run with ${cmd}…`; $("uSteps").innerHTML = ""; }
    shown = cmd;
    const rec = await load(cmd);
    if (shown !== cmd) return;   // the deck changed while it loaded
    if (rec.error) { $("uTools").hidden = true; $("uSub").textContent = ""; $("uSteps").innerHTML = ""; $("uNote").textContent = rec.error; return; }
    draw(window.DECKBUILDER.read(), rec);
  }

  function make(list, msg) {
    const deck = window.DECKBUILDER.read();
    for (const { add, cut } of list) {
      if (cut) {
        const i = deck.list.findIndex(([n]) => norm(n) === norm(cut.n));
        if (i >= 0) { if (deck.list[i][1] > 1) deck.list[i][1]--; else deck.list.splice(i, 1); }
      }
      if (!deck.list.some(([n]) => norm(n) === norm(add.n))) deck.list.push([add.n, 1]);
    }
    window.DECKBUILDER.write(msg);
  }
  $("uSteps").addEventListener("click", e => {
    const one = e.target.closest("[data-swap]"), upto = e.target.closest("[data-upto]");
    if (one) { const sw = swaps[+one.dataset.swap]; if (sw) make([sw], sw.cut ? `Swapped ${sw.cut.n} for ${sw.add.n}` : `Added ${sw.add.n}`); }
    if (upto) { const n = +upto.dataset.upto; make(swaps.slice(0, n), `Made ${n} swap${n > 1 ? "s" : ""}`); }
  });
  $("uBudget").onchange = $("uOwned").onchange = render;
  document.addEventListener("deck-rendered", () => render().catch(e => toast(e.message)));
})();
