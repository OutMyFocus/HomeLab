// The Upgrade path panel in the deck builder (Decks page). For a Commander deck it asks
// the Pi for what EDHREC's decks with the same commander play (/api/decks/upgrades),
// pairs the deck's weakest cards with better ones, and splits the swaps into steps:
// a few quick wins first, then more and more until it's the best version of the deck.
// Cards you already own come first, because they're free. Each swap, or a whole step,
// can be made with one press (builder.js changes the list and saves it).
window.UPGRADES = (() => {
  const { $, esc, toast, copy, api } = MTG;
  const V = VAULT, { S, norm, cad } = V;
  const STEPS = [[3, "Quick wins", "The few changes that help the most"], [7, "Tune-up", "Tightens the deck up"],
    [10, "Big upgrade", "Most of the way there"], [20, "Best version", "Everything EDHREC's best decks would change"]];
  const MAX_SWAPS = STEPS.reduce((s, x) => s + x[0], 0);
  const TARGET = { ramp: [10, "ramp"], draw: [10, "card draw"], removal: [8, "removal"], wipe: [2, "board wipes"] };
  const MIN_GAIN = 0.08, OWN_BONUS = 0.25, KEEP_BASICS = 5;
  const recs = new Map();  // commander -> Promise of the Pi's answer
  let last = null, swaps = [], deck = null, steps = [];

  const pop = e => e ? Math.max(0, 1 - Math.log10(e) / 4.6) : 0;  // EDHREC rank 1 -> 1, about 40,000 -> 0
  const isLand = c => /Land/.test(c.t.split(" // ")[0]);
  const roles = c => Object.keys(TARGET).filter(k => V.ROLEF[k](c));
  const short = n => String(n || "").split(",")[0].split(" // ")[0];
  const pct = x => Math.round(x * 100) + "%";

  function fetchRecs(commander) {
    const k = norm(commander);
    if (!recs.has(k)) recs.set(k, api("/api/decks/upgrades?commander=" + encodeURIComponent(commander))
      .catch(e => ({ source: "none", error: e.message || "Couldn't get suggestions" })));
    return recs.get(k);
  }

  // Every card that could go in, with a score: how many decks play it (and how much more
  // than usual), or, with no EDHREC list, how popular it is in Commander overall.
  function pool(info, cmd, inDeck) {
    const ci = new Set(cmd.ci), out = [];
    const ok = c => c && !c.b && [...c.ci].every(x => ci.has(x)) && !inDeck.has(norm(c.n)) && norm(c.n) !== norm(cmd.n) && !V.BASICS.has(norm(c.n));
    if (info.source === "edhrec") {
      for (const r of info.cards || []) { const c = V.lookup(r.n); if (ok(c)) out.push({ c, score: r.inc + 0.8 * Math.max(0, r.syn), inc: r.inc, syn: r.syn, p: r.p }); }
    } else {
      // No lands here: without EDHREC there's no telling which lands suit the deck (Command Tower in mono black).
      for (const c of S.cards) if (c.e && c.e < 3000 && ok(c) && !isLand(c) && !/can be your commander|Background/.test(c.o + c.t)) out.push({ c, score: 0.5 * pop(c.e) });
      out.sort((a, b) => b.score - a.score); out.length = Math.min(out.length, 250);
    }
    return out;
  }

  function deckScore(c, name, info, byName, ci) {
    if (!c) return { score: 0.05, why: "Not in the card database" };
    if (c.b) return { score: -1, why: "Banned in Commander" };
    if (![...c.ci].every(x => ci.has(x))) return { score: -1, why: "Outside the commander's colors" };
    const r = byName.get(norm(c.n));
    if (r) return { score: r.inc + 0.8 * Math.max(0, r.syn), why: `In ${pct(r.inc)} of decks` };
    if (info.source === "edhrec") return { score: 0.02 + 0.12 * pop(c.e), why: "Few decks with this commander play it" };
    return { score: 0.5 * pop(c.e), why: c.e ? "Rarely played in Commander" : "Hardly anyone plays it" };
  }

  // Pair the best cards to add with the weakest cards to cut. Lands swap with lands, so
  // the land count stays the same; everything else swaps with a nonland card.
  function plan(d, info, opts) {
    const cmd = V.lookup(d.commander); if (!cmd) return null;
    const ci = new Set(cmd.ci), byName = new Map((info.cards || []).map(r => [norm(r.n), r]));
    const inDeck = new Set(d.list.map(([n]) => norm(V.lookup(n)?.n || n)));
    const counts = Object.fromEntries(Object.keys(TARGET).map(k => [k, 0]));
    const cutsN = [], cutsL = []; const basics = new Map(); let lands = 0;
    for (const [n, q] of d.list) {
      const c = V.lookup(n);
      if (V.BASICS.has(norm(n))) { basics.set(n, q); lands += q; continue; }
      if (c && isLand(c)) lands += q;
      if (c && !isLand(c)) for (const r of roles(c)) counts[r] += q;
      const s = deckScore(c, n, info, byName, ci);
      (c && isLand(c) ? cutsL : cutsN).push({ n, c, ...s, roles: c && !isLand(c) ? roles(c) : [] });
    }
    const base = cutsN.concat(cutsL).reduce((s, x) => s + Math.max(0, x.score), 0);
    const gcs = d.list.some(([n]) => V.lookup(n)?.gc) || cmd.gc;
    const adds = pool(info, cmd, inDeck).filter(a => {
      if (opts.noGc && a.c.gc) return false;
      a.own = V.ownedQty(a.c.n) > 0;
      a.price = a.own ? 0 : (V.priceOf(a.c.n) ?? a.p ?? null);
      return a.own || !opts.budget || (a.price != null && a.price <= opts.budget);
    }).sort((a, b) => b.score - a.score);
    const idealN = cutsN.length + cutsL.length;
    const ideal = [...adds.map(a => a.score), ...cutsN.concat(cutsL).map(x => x.score)].sort((a, b) => b - a).slice(0, idealN).reduce((s, x) => s + Math.max(0, x), 0);
    cutsN.sort((a, b) => a.score - b.score); cutsL.sort((a, b) => a.score - b.score);
    const out = []; let basicLeft = [...basics.values()].reduce((s, q) => s + q, 0);
    for (const a of adds) {
      if (out.length >= MAX_SWAPS * 2) break;
      const aRoles = isLand(a.c) ? [] : roles(a.c);
      const bonus = aRoles.filter(r => counts[r] < TARGET[r][0]).length * 0.06;
      let cut = null, eff = 0;
      if (isLand(a.c)) {
        const nb = cutsL[0];
        const top = [...basics.entries()].filter(([, q]) => q > 0).sort((x, y) => y[1] - x[1])[0];
        const basic = top && basicLeft > KEEP_BASICS ? { n: top[0], score: 0.2, why: "A basic land" } : null;
        cut = nb && (!basic || nb.score < basic.score) ? nb : basic; eff = cut ? cut.score : 0;
        if (!cut || a.score - eff < MIN_GAIN) continue;
        if (cut === nb) cutsL.shift(); else { basics.set(top[0], top[1] - 1); basicLeft--; }
      } else {
        for (const x of cutsN.slice(0, 15)) {
          const e = x.score + x.roles.filter(r => counts[r] <= TARGET[r][0] && !aRoles.includes(r)).length * 0.1;
          if (!cut || e < eff) { cut = x; eff = e; }
        }
        if (!cut || a.score + bonus - eff < MIN_GAIN) continue;
        cutsN.splice(cutsN.indexOf(cut), 1);
        for (const r of cut.roles) counts[r]--;
        for (const r of aRoles) counts[r]++;
      }
      const fills = aRoles.filter(r => counts[r] - 1 < TARGET[r][0]);
      out.push({ add: a, cut, gain: Math.max(0, a.score) - Math.max(0, cut.score), rank: a.score + bonus - eff + (a.own ? OWN_BONUS : 0), fills, counts: { ...counts } });
    }
    out.sort((a, b) => b.rank - a.rank); out.length = Math.min(out.length, MAX_SWAPS);
    return { cmd, swaps: out, base, ideal, lands, gcs };
  }

  function addWhy(s, info, cmd) {
    const a = s.add, bits = [];
    if (info.source === "edhrec") {
      bits.push(`In ${pct(a.inc)} of ${esc(short(cmd.n))} decks`);
      if (a.syn >= 0.25) bits.push("a signature card for this commander");
      else if (a.syn >= 0.1) bits.push("fits this commander well");
    } else bits.push(a.c.e ? `One of the most played Commander cards (#${a.c.e.toLocaleString()})` : "A popular Commander card");
    for (const r of s.fills) bits.push(`adds ${TARGET[r][1]}`);
    return bits.join(" · ");
  }

  function render(d) {
    deck = d; const box = $("upg"); if (!box) return;
    const cmdName = d.commander;
    if (!cmdName) { box.hidden = true; return; }
    box.hidden = false;
    if (!S.cards) { $("uSteps").innerHTML = '<p class="sub">The upgrade path needs the card database. It loads above.</p>'; $("uFit").innerHTML = ""; $("uSrc").textContent = ""; return; }
    $("uSteps").innerHTML = last && norm(last.cmd) === norm(cmdName) ? $("uSteps").innerHTML : '<p class="sub">Looking at what other decks with this commander play…</p>';
    fetchRecs(cmdName).then(info => { if (deck === d) draw(d, info); });
  }

  function draw(d, info) {
    const opts = { budget: +$("uBudget").value || 0, noGc: $("uNoGc").checked };
    const p = plan(d, info, opts);
    last = { cmd: d.commander };
    if (!p) { $("uSteps").innerHTML = `<p class="sub">${esc(d.commander)} isn't in the card database, so there's nothing to compare with. Check the spelling.</p>`; $("uFit").innerHTML = ""; return; }
    swaps = p.swaps;
    $("uSrc").innerHTML = info.source === "edhrec"
      ? `From <a href="${esc(info.url)}" target="_blank" rel="noopener">${(info.decks || 0).toLocaleString()} decks on EDHREC</a>${info.fetched ? `, ${esc(info.fetched)}` : ""}`
      : "From the most played Commander cards";
    const notes = [];
    if (info.source !== "edhrec" && info.error) notes.push(esc(info.error) + ".");
    if (info.source === "edhrec" && info.lands && p.lands < info.lands - 2) notes.push(`Your deck has ${p.lands} lands. Most ${esc(short(p.cmd.n))} decks run about ${Math.round(info.lands)}, so think about cutting a spell or two for lands.`);
    if (opts.noGc && !p.gcs) notes.push("No Game Changers are suggested, so the deck stays in Bracket 1 or 2.");
    else if (opts.noGc) notes.push("No new Game Changers are suggested, so the bracket stays where it is.");
    const fit = v => Math.max(0, Math.min(100, Math.round(100 * v / (p.ideal || 1))));
    steps = []; let at = 0, sum = p.base, total = 0;
    for (const [n, title, sub] of STEPS) {
      const part = swaps.slice(at, at + n); if (!part.length) break;
      const cost = part.reduce((s, x) => s + (x.add.price || 0), 0), unpriced = part.filter(x => x.add.price == null).length;
      sum += part.reduce((s, x) => s + x.gain, 0); total += cost;
      steps.push({ from: at, part, title, sub, cost, total, unpriced, own: part.filter(x => x.add.own).length, fit: fit(sum) });
      at += n;
    }
    const now = fit(p.base);
    $("uFit").innerHTML = steps.length ? `<div class="fit-row" title="How close the deck is to what EDHREC's decks with this commander play. 100 means every card is one most of them run.">
      <span class="fit-now"><small>Now</small><b>${now}</b></span>${steps.map((s, i) => `<span class="fit-arrow">→</span><span class="fit-step"><small>Step ${i + 1}</small><b>${s.fit}</b></span>`).join("")}<span class="sub">deck fit out of 100</span></div>
      <div class="fit-bar"><span style="width:${now}%"></span>${steps.map((s, i) => `<span class="gain s${i}" style="width:${Math.max(0, s.fit - (i ? steps[i - 1].fit : now))}%"></span>`).join("")}</div>` : "";
    $("uNotes").innerHTML = notes.map(n => `<p class="sub">${n}</p>`).join("");
    if (!steps.length) {
      $("uSteps").innerHTML = `<p class="good-line">✓ Nothing to change: this deck already plays the cards most ${esc(short(p.cmd.n))} decks do${opts.budget ? " at this budget" : ""}.</p>`;
      return;
    }
    $("uSteps").innerHTML = steps.map((s, i) => `<details class="upg-step"${i === 0 ? " open" : ""}>
      <summary><span class="step-n">${i + 1}</span><span class="step-t"><b>${s.title}</b><small>${s.sub}</small></span>
        <span class="step-m"><b>${s.part.length} swap${s.part.length > 1 ? "s" : ""}</b><small>${s.cost ? cad(s.cost) : "Free"}${s.unpriced ? ` + ${s.unpriced} unpriced` : ""}${i ? ` · ${cad(s.total)} total` : ""}${s.own ? ` · ${s.own} you own` : ""}</small></span></summary>
      <ul class="swaps">${s.part.map((x, j) => {
        const k = s.from + j, a = x.add;
        return `<li><div class="sw-cut"><span class="sign">−</span><a class="cardlink" href="/cards?card=${encodeURIComponent(x.cut.n)}">${esc(x.cut.n)}</a><small>${esc(x.cut.why)}</small></div>
          <div class="sw-add"><span class="sign">+</span><a class="cardlink" href="/cards?card=${encodeURIComponent(a.c.n)}">${esc(a.c.n)}</a>${a.c.gc ? ' <span class="badge warn" title="Game Changer: Bracket 3 or higher">GC</span>' : ""}<small>${addWhy(x, info, p.cmd)}</small></div>
          <div class="sw-price">${a.own ? '<span class="badge good" title="It\'s in your collection">You own it</span>' : a.price != null ? cad(a.price) : '<span class="muted" title="No price yet">–</span>'}</div>
          <button class="btn ghost small-btn" data-swap="${k}" title="Cut ${esc(x.cut.n)}, add ${esc(a.c.n)}">Swap</button></li>`;
      }).join("")}</ul>
      <div class="step-acts"><button class="btn primary small-btn" data-step="${i}">Make these ${s.part.length} swaps</button>
        <button class="btn ghost small-btn" data-shop="${i}">Copy shopping list</button><button class="btn ghost small-btn" data-wish="${i}">Add to wishlist</button></div>
    </details>`).join("");
  }

  const toBuy = s => s.part.filter(x => !x.add.own);
  $("uSteps").addEventListener("click", async e => {
    const sw = e.target.closest("[data-swap]"), st = e.target.closest("[data-step]"), sh = e.target.closest("[data-shop]"), wi = e.target.closest("[data-wish]");
    if (sw) { const x = swaps[+sw.dataset.swap]; window.BUILDER.apply([[x.cut.n, x.add.c.n]], `Swapped ${x.cut.n} for ${x.add.c.n}`); }
    if (st) { const s = steps[+st.dataset.step]; window.BUILDER.apply(s.part.map(x => [x.cut.n, x.add.c.n]), `Made ${s.part.length} swaps`); }
    if (sh) {
      const b = toBuy(steps[+sh.dataset.shop]); if (!b.length) return toast("Nothing to buy: you own all of these");
      copy(b.map(x => `1 ${x.add.c.n}${x.add.price != null ? ` ($${x.add.price.toFixed(2)} CAD)` : ""}`).join("\n")).then(() => toast(`Shopping list copied (${b.length} cards)`), () => toast("Couldn't copy"));
    }
    if (wi) {
      const b = toBuy(steps[+wi.dataset.wish]); if (!b.length) return toast("Nothing to buy: you own all of these");
      try { await api("/api/wishlist/add", { cards: b.map(x => ({ name: x.add.c.n })) }); toast(`Added ${b.length} cards to your wishlist`); } catch (err) { toast(err.message); }
    }
  });
  const redraw = () => { if (deck) render(deck); };
  $("uBudget").onchange = redraw; $("uNoGc").onchange = redraw;

  return { render, plan };
})();
