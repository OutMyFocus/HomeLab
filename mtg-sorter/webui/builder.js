// The Commander deck builder on the Decks page (Commander Vault's Deck builder). It reads
// the decklist box, so typing and pasting still work: it checks the deck as you go (100
// cards, colors, duplicates, banned cards, Game Changers), draws the mana curve, prices
// it in Canadian dollars, groups the cards by type, and deals test hands. Its buttons
// change the list in the box, and save the deck if it's already saved.
(() => {
  const { $, esc, toast, copy } = MTG;
  const V = VAULT, { S, norm, cad } = V;
  let deck = null, pt = null, sug = [], sugIdx = -1, t;

  const text = () => $("deckText").value;
  function read() { deck = V.parseDeck(text()); const saved = window.DECKS?.current(); deck.proxied = !!saved?.proxied; deck.guide = saved?.guide || ""; return deck; }
  async function write(msg) {
    const saved = window.DECKS?.current();
    const side = deck.side;
    $("deckText").value = V.deckToText({ ...deck, side });
    window.DECKS?.changed();
    if (saved) { try { await window.DECKS.save(); } catch (e) { toast(e.message); return; } }
    if (msg) toast(msg + (saved ? "" : ". Press Save deck to keep it"));
    render();
  }

  function render() {
    read();
    const looksCommander = !!deck.commander || deck.list.reduce((s, x) => s + x[1], 0) >= 90;
    $("builder").hidden = !looksCommander;
    if (!looksCommander) return;
    const cmd = V.lookup(deck.commander), ch = V.deckChecks(deck), st = V.deckStats(deck);
    $("bTitle").textContent = "Commander checks";
    $("bCmd").innerHTML = deck.commander ? `${cmd ? V.pips(cmd.ci) : ""} ${esc(deck.commander)}` : "";
    $("bChecks").innerHTML = ch.checks.map(([c, msg]) => `<div class="check-row ${c}"><span class="ic">${c === "ok" ? "✓" : c === "bad" ? "✕" : "!"}</span><span>${esc(msg)}</span></div>`).join("")
      + `<div class="check-row ok"><span class="ic">✓</span><span>${deck.proxied ? "Complete. Cards you don't own are covered by proxies." : `You own ${st.own} of ${st.count}.`}</span></div>`;
    $("bBracket").textContent = S.cards ? `Bracket estimate ${ch.bracket}` : "";
    const unpriced = [deck.commander, ...deck.list.map(x => x[0])].filter(n => n && !V.BASICS.has(norm(n)) && V.priceOf(n) == null).length;
    $("bMoney").innerHTML = `<span>Deck value <b>${cad(st.value)}</b></span>${deck.proxied ? "<span>Complete with proxies</span>" : `<span>To finish <b>${cad(st.cost)}</b> for ${st.need.length} cards</span>`}${unpriced ? `<span>${unpriced} not priced in Canada yet</span>` : ""}`;
    $("bProxy").checked = deck.proxied; $("bProxy").disabled = !window.DECKS?.current();
    $("bProxy").parentElement.title = window.DECKS?.current() ? "Counts every card as owned, so nothing shows as missing or to buy" : "Save the deck first";
    $("bGuide").hidden = !deck.guide; if (deck.guide) $("bGuide").href = deck.guide;
    $("bNote").textContent = S.cards ? "" : "Checks, the curve and card types need the card database. It downloads once, then stays in this browser.";
    groups(ch.bad); curve(); renderPt();
  }

  function groups(bad) {
    const by = new Map();
    for (const [n, q] of deck.list) { const c = V.lookup(n), k = V.typeOf(c); if (!by.has(k)) by.set(k, []); by.get(k).push([n, q, c]); }
    $("bGroups").innerHTML = [...V.TYPES, "Other", "Unknown"].filter(k => by.has(k)).map(k => {
      const items = by.get(k).sort((a, b) => ((a[2]?.v ?? 0) - (b[2]?.v ?? 0)) || a[0].localeCompare(b[0]));
      const n = items.reduce((s, x) => s + x[1], 0);
      const title = k === "Unknown" ? (S.cards ? "Not found" : "Cards") : k + (k === "Sorcery" ? " cards" : k === "Other" ? "" : "s");
      return `<div class="panel group"><header><h3>${title}</h3><span class="sub">${n}</span></header><ul>${items.map(([nm, q, c]) => {
        const have = V.ownedQty(nm), proxy = deck.proxied && have < q, ok = deck.proxied || have >= q;
        return `<li class="${bad.has(norm(c ? c.n : nm)) || bad.has(norm(nm)) ? "bad" : ""}"><span class="own ${proxy ? "p" : ok ? "y" : "n"}" title="${proxy ? "Proxy" : ok ? "Owned" : "Not owned"}">${proxy ? "PRX" : ok ? "OWN" : "BUY"}</span>
          <span>${q > 1 ? `${q}x ` : ""}<a class="cardlink" href="/cards?card=${encodeURIComponent(nm)}">${esc(nm)}</a>${c && c.gc ? ' <span class="badge warn">GC</span>' : ""}</span>
          <span class="right">${c ? V.mana(c.m) : ""}<span>${V.money(V.priceInfo(nm))}</span>${V.BASICS.has(norm(nm)) ? `<button class="x" data-inc="${esc(nm)}" title="One more">+</button>` : ""}<button class="x" data-rm="${esc(nm)}" title="Remove one">×</button></span></li>`;
      }).join("")}</ul></div>`;
    }).join("");
  }

  function curve() {
    const svg = $("bCurve"), counts = Array(8).fill(0); let sum = 0, n = 0;
    for (const [nm, q] of deck.list) { const c = V.lookup(nm); if (!c || /Land/.test(c.t.split(" // ")[0])) continue; counts[Math.min(7, Math.floor(c.v))] += q; sum += c.v * q; n += q; }
    const W = 420, H = 170, pl = 28, pr = 8, ptop = 16, pb = 34, iw = W - pl - pr, ih = H - ptop - pb, bw = iw / 8;
    const max = Math.ceil(Math.max(4, ...counts) / 4) * 4; let s = "";
    for (let g = 0; g <= max; g += max / 4) { const y = ptop + ih - g / max * ih; s += `<line x1="${pl}" x2="${W - pr}" y1="${y}" y2="${y}"/><text x="${pl - 6}" y="${y + 4}" text-anchor="end">${g}</text>`; }
    counts.forEach((v, i) => { const h = v / max * ih, x = pl + i * bw + bw * .2, w = bw * .6, y = ptop + ih - h; if (v) s += `<rect class="bar" x="${x}" y="${y}" width="${w}" height="${h}" rx="2"/><text x="${x + w / 2}" y="${y - 4}" text-anchor="middle">${v}</text>`; s += `<text x="${x + w / 2}" y="${H - pb + 15}" text-anchor="middle">${i === 7 ? "7+" : i}</text>`; });
    s += `<text x="${pl + iw / 2}" y="${H - 4}" text-anchor="middle">MANA VALUE${n ? " · AVERAGE " + (sum / n).toFixed(2) : ""}</text>`;
    svg.innerHTML = s;
  }

  // ---------- editing ----------
  function add(name) {
    const c = V.lookup(name), nm = c ? c.n : name.trim(); if (!nm) return;
    const ex = deck.list.find(x => norm(x[0]) === norm(nm));
    if (ex && !V.BASICS.has(norm(nm)) && !(c && /any number of cards named/i.test(c.o))) return toast(`${nm} is already in the deck`);
    if (ex) ex[1]++; else deck.list.push([nm, 1]);
    write(`Added ${nm}`);
  }
  $("bGroups").onclick = e => {
    const rm = e.target.closest("[data-rm]"), inc = e.target.closest("[data-inc]");
    if (rm) { read(); const i = deck.list.findIndex(x => x[0] === rm.dataset.rm); if (i >= 0) { if (deck.list[i][1] > 1) deck.list[i][1]--; else deck.list.splice(i, 1); write(); } }
    if (inc) { read(); const x = deck.list.find(y => y[0] === inc.dataset.inc); if (x) { x[1]++; write(); } }
  };
  $("bSetCmd").onclick = () => {
    read(); const n = $("bAdd").value.trim(), c = n ? V.lookup(n) : null;
    if (!c) { toast("Type the commander's name in the Add a card box first"); return $("bAdd").focus(); }
    if (deck.commander && !deck.list.some(x => norm(x[0]) === norm(deck.commander))) deck.list.push([deck.commander, 1]);
    deck.list = deck.list.filter(x => norm(x[0]) !== norm(c.n)); deck.commander = c.n;
    $("bAdd").value = ""; $("bSug").hidden = true; write(`${c.n} is now the commander`);
  };
  $("bCopy").onclick = () => { read(); copy(V.deckToText(deck)).then(() => toast("Decklist copied"), () => toast("Couldn't copy")); };
  $("bShop").onclick = () => {
    read(); const st = V.deckStats(deck);
    if (!st.need.length) return toast("Nothing to buy");
    copy(st.need.map(([n, q, p]) => `${q} ${n}${p ? ` ($${p.toFixed(2)} CAD)` : ""}`).join("\n") + `\n\nTotal about ${cad(st.cost)} CAD`)
      .then(() => toast(`Shopping list copied (${st.need.length} cards)`), () => toast("Couldn't copy"));
  };
  $("bProxy").onchange = async () => {
    try { await window.DECKS.save({ proxied: $("bProxy").checked }); toast($("bProxy").checked ? "Marked complete with proxies" : "Shows missing cards again"); render(); }
    catch (e) { toast(e.message); }
  };

  // ---------- suggestions while typing ----------
  function suggest() {
    const q = norm($("bAdd").value), ul = $("bSug");
    if (!q || !S.cards) { ul.hidden = true; return; }
    const cmd = V.lookup(deck?.commander), ci = cmd ? new Set(cmd.ci) : null, starts = [], has = [];
    for (const c of S.cards) { if (c._k.startsWith(q)) starts.push(c); else if (c._k.includes(q)) has.push(c); if (starts.length > 40) break; }
    const rank = (a, b) => (a.e || 1e6) - (b.e || 1e6);
    sug = [...starts.sort(rank), ...has.sort(rank)].slice(0, 12); sugIdx = sug.length ? 0 : -1;
    ul.innerHTML = sug.map((c, i) => `<li role="option" data-i="${i}" aria-selected="${i === sugIdx}"><span>${esc(c.n)}${!ci || [...c.ci].every(x => ci.has(x)) ? "" : ' <span class="badge bad">Off color</span>'}${V.ownedQty(c.n) ? ' <span class="badge good">Own</span>' : ""}</span><span class="sub">${V.money(V.priceInfo(c.n))}</span></li>`).join("");
    ul.hidden = !sug.length;
  }
  function pick(i) { const c = sug[i]; if (!c) return; read(); add(c.n); $("bAdd").value = ""; $("bSug").hidden = true; $("bAdd").focus(); }
  $("bAdd").oninput = suggest;
  $("bAdd").onkeydown = e => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { if (!sug.length) return; e.preventDefault(); sugIdx = (sugIdx + (e.key === "ArrowDown" ? 1 : -1) + sug.length) % sug.length; for (const li of $("bSug").children) li.setAttribute("aria-selected", +li.dataset.i === sugIdx); }
    else if (e.key === "Enter") { e.preventDefault(); if (sugIdx >= 0) pick(sugIdx); else if ($("bAdd").value.trim()) { read(); add($("bAdd").value); $("bAdd").value = ""; } }
    else if (e.key === "Escape") $("bSug").hidden = true;
  };
  $("bSug").onmousedown = e => { const li = e.target.closest("li[data-i]"); if (li) { e.preventDefault(); pick(+li.dataset.i); } };
  $("bAdd").onblur = () => setTimeout(() => $("bSug").hidden = true, 150);

  // ---------- playtest ----------
  const shuffle = a => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
  const comb = (n, k) => { if (k < 0 || k > n) return 0; let r = 1; for (let i = 1; i <= k; i++) r = r * (n - k + i) / i; return r; };
  const library = () => deck.list.flatMap(([n, q]) => Array(q).fill(n));
  const isLand = n => { const c = V.lookup(n); return c ? /Land/.test(c.t.split(" // ")[0]) : V.BASICS.has(norm(n)); };
  function ptStart(mulls) { read(); const lib = shuffle(library()); pt = { lib, hand: lib.splice(0, 7), mulls, drawn: 0, bottom: new Set() }; renderPt(); }
  function renderPt() {
    const lib = library(), N = lib.length, L = lib.filter(isLand).length; let p = 0;
    for (const k of [2, 3, 4, 5]) p += comb(L, k) * comb(N - L, 7 - k) / comb(N, 7);
    $("ptOdds").textContent = N >= 7 ? `${L} lands in ${N} cards. A 7-card opener has 2 to 5 lands ${Math.round(p * 100)}% of the time.` : "";
    if (!pt) { $("ptHand").innerHTML = ""; $("ptInfo").textContent = ""; $("ptBottom").textContent = ""; $("ptMull").disabled = $("ptDraw").disabled = true; return; }
    $("ptMull").disabled = false; $("ptDraw").disabled = !pt.lib.length;
    const lands = pt.hand.filter(isLand).length;
    $("ptInfo").textContent = `${pt.hand.length} cards · ${lands} lands${pt.mulls ? ` · mulligan ${pt.mulls}: put ${pt.mulls} on the bottom` : ""}${pt.drawn ? ` · turn ${pt.drawn + 1}` : ""}`;
    $("ptHand").innerHTML = pt.hand.map((n, i) => { const c = V.lookup(n); return `<button class="hcard${isLand(n) ? " land" : ""}" data-pti="${i}" aria-pressed="${pt.bottom.has(i)}" title="${pt.mulls ? "Tap to put it on the bottom" : esc(c ? c.o : "")}"><b>${esc(n)}</b><span class="t">${c ? V.mana(c.m) + " " + esc(c.t.split(" // ")[0]) : ""}</span></button>`; }).join("");
    $("ptBottom").textContent = pt.mulls ? (pt.bottom.size === pt.mulls ? "Ready. Those go to the bottom when you draw." : `Choose ${pt.mulls - pt.bottom.size} more to put on the bottom.`) : "";
  }
  $("ptNew").onclick = () => ptStart(0);
  $("ptMull").onclick = () => ptStart((pt ? pt.mulls : 0) + 1);
  $("ptDraw").onclick = () => {
    if (!pt) return;
    if (pt.mulls && pt.bottom.size) { pt.lib.push(...pt.hand.filter((_, i) => pt.bottom.has(i))); pt.hand = pt.hand.filter((_, i) => !pt.bottom.has(i)); pt.mulls = 0; pt.bottom = new Set(); }
    if (pt.lib.length) { pt.hand.push(pt.lib.shift()); pt.drawn++; }
    renderPt();
  };
  $("ptHand").onclick = e => { const b = e.target.closest("[data-pti]"); if (!b || !pt || !pt.mulls) return; const i = +b.dataset.pti; if (pt.bottom.has(i)) pt.bottom.delete(i); else if (pt.bottom.size < pt.mulls) pt.bottom.add(i); renderPt(); };

  // ---------- start ----------
  $("deckText").addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => { pt = null; render(); }, 300); });
  document.addEventListener("deck-opened", () => { pt = null; render(); });
  (async () => {
    await Promise.all([V.loadPrices().catch(() => null), V.loadOwned().catch(() => null)]);
    render();
    await V.loadCards(msg => { $("bNote").textContent = msg; });
    render();
  })();
})();
