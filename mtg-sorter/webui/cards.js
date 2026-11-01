// Card lookup: every Commander card, with Canadian prices, what you own and which decks it fits.
(() => {
  const { $, esc, toast, api } = MTG;
  const V = VAULT, { S, norm, cad } = V;
  const k = { colors: new Set(), gc: false, noGc: false, noBan: true, cmd: false, role: "", limit: 80, sel: null };
  let last = [], numberHits = null, numberQ = "";

  // ---------- search ----------
  function parseQuery(raw) {
    const terms = [], words = []; const re = /(-?)(\w+)(:|<=|>=|<|>|=)("[^"]*"|\S+)|("[^"]*")|(\S+)/g; let m;
    while ((m = re.exec(raw))) {
      if (m[2]) terms.push({ neg: m[1] === "-", key: m[2].toLowerCase(), op: m[3], val: m[4].replace(/^"|"$/g, "").toLowerCase() });
      else words.push((m[5] || m[6]).replace(/^"|"$/g, ""));
    }
    return { terms, name: norm(words.join(" ")) };
  }
  // "FRA 419", "#419", "cn:419", "s:fra", "fra#419": a printing search, answered by Scryfall.
  function numberQuery(raw) {
    const t = raw.trim(); let m;
    if ((m = t.match(/^(?:s|set|e):([a-z0-9]{2,6})(?:\s+(?:cn:|#)?([0-9]+[a-z★]?))?$/i))) return { set: m[1], cn: m[2] || "" };
    if ((m = t.match(/^(?:cn:|#)([0-9]+[a-z★]?)(?:\s+(?:s|set):([a-z0-9]{2,6}))?$/i))) return { set: m[2] || "", cn: m[1] };
    if ((m = t.match(/^([a-z0-9]{2,6})\s*[ #-]\s*([0-9]+[a-z★]?)$/i)) && /[a-z]/i.test(m[1])) return { set: m[1], cn: m[2] };
    return null;
  }
  const RAR = { c: "c", common: "c", u: "u", uncommon: "u", r: "r", rare: "r", m: "m", mythic: "m" };
  const cmp = (a, op, b) => op === "<" ? a < b : op === "<=" ? a <= b : op === ">" ? a > b : op === ">=" ? a >= b : a === b;
  function termOk(c, t) {
    const v = t.val; let ok;
    switch (t.key) {
      case "t": case "type": ok = norm(c.t).includes(v); break;
      case "o": case "oracle": case "text": ok = norm(c.o).includes(v); break;
      case "c": case "id": case "ci": case "color": { const allow = new Set(v.toUpperCase().replace(/[^WUBRGC]/g, "")); ok = allow.has("C") && allow.size === 1 ? c.ci === "" : [...c.ci].every(x => allow.has(x)); break; }
      case "mv": case "cmc": ok = cmp(c.v, t.op === ":" ? "=" : t.op, +v); break;
      case "pow": case "power": { const n = parseInt((c.pt || "").split("/")[0], 10); ok = !isNaN(n) && cmp(n, t.op === ":" ? "=" : t.op, +v); break; }
      case "tou": case "toughness": { const n = parseInt((c.pt || "").split("/")[1], 10); ok = !isNaN(n) && cmp(n, t.op === ":" ? "=" : t.op, +v); break; }
      case "r": case "rarity": ok = c.r === RAR[v]; break;
      case "price": case "p": { const p = V.priceOf(c.n); ok = p != null && cmp(p, t.op === ":" ? "<=" : t.op, +v); break; }
      case "is": ok = v === "commander" ? V.isCommander(c) : v === "gc" ? !!c.gc : v === "banned" ? !!c.b : V.ROLEF[v] ? V.ROLEF[v](c) : true; break;
      case "own": ok = (V.ownedQty(c.n) > 0) === ["yes", "y", "true"].includes(v); break;
      default: ok = c._k.includes(norm(t.key + t.op + t.val));
    }
    return t.neg ? !ok : ok;
  }
  const num = id => $(id).value === "" ? null : +$(id).value;
  function matches() {
    if (!S.cards) return [];
    const pq = parseQuery($("kQ").value), q = pq.name;
    const tx = norm($("kText").value), ty = norm($("kType").value), mv = num("kMv"), mvMin = num("kMvMin"), pmax = num("kPmax"), pow = num("kPow");
    const own = $("kOwn").value, kind = $("kKind").value, rar = $("kRar").value, stock = $("kStock").value;
    let allow = null; const fd = $("kFor").value;
    if (fd) { const d = S.decks.find(x => x.id === fd); const c = d && V.lookup(d.commander); if (c) allow = new Set(c.ci); }
    else if (k.colors.size) allow = new Set([...k.colors].filter(x => x !== "C"));
    const role = k.role && V.ROLEF[k.role]; const out = [];
    for (const c of S.cards) {
      if (q && !c._k.includes(q)) continue;
      if (pq.terms.length && !pq.terms.every(t => termOk(c, t))) continue;
      if (role && !role(c)) continue;
      if (tx && !norm(c.o).includes(tx)) continue;
      if (ty && !norm(c.t).includes(ty)) continue;
      if (mv != null && c.v > mv) continue;
      if (mvMin != null && c.v < mvMin) continue;
      if (allow && ![...c.ci].every(x => allow.has(x))) continue;
      if (k.gc && !c.gc) continue;
      if (k.noGc && c.gc) continue;
      if (k.noBan && c.b) continue;
      if (kind && !c.t.split(" // ")[0].includes(kind)) continue;
      if (rar && c.r !== rar) continue;
      if (pow != null) { const pw = parseInt((c.pt || "").split("/")[0], 10); if (isNaN(pw) || pw < pow) continue; }
      if (k.cmd && !V.isCommander(c)) continue;
      if (pmax != null || stock) { const pi = V.priceInfo(c.n); if (pmax != null && (!pi || pi.p > pmax)) continue; if (stock && !(pi && pi.inStock)) continue; }
      if (own) { const h = V.ownedQty(c.n) > 0; if (own === "y" && !h) continue; if (own === "n" && h) continue; }
      out.push(c);
    }
    const s = $("kSort").value, rank = c => c.e || 1e6;
    if (q && s === "pop") out.sort((a, b) => ((b._k === q) - (a._k === q)) || (b._k.startsWith(q) - a._k.startsWith(q)) || rank(a) - rank(b));
    else if (s === "pop") out.sort((a, b) => rank(a) - rank(b));
    else if (s === "name") out.sort((a, b) => a.n.localeCompare(b.n));
    else if (s === "price") out.sort((a, b) => (V.priceOf(a.n) ?? 1e9) - (V.priceOf(b.n) ?? 1e9));
    else if (s === "priced") out.sort((a, b) => (V.priceOf(b.n) ?? -1) - (V.priceOf(a.n) ?? -1));
    else out.sort((a, b) => a.v - b.v || a.n.localeCompare(b.n));
    return out;
  }
  function filterCount() {
    let n = ["kText", "kType", "kRar", "kMvMin", "kMv", "kPmax", "kPow", "kStock"].filter(id => $(id).value).length;
    for (const key of ["cmd", "gc", "noGc"]) if (k[key]) n++;
    return n + (k.noBan ? 0 : 1);
  }

  // ---------- results ----------
  function row(c, extra = "") {
    const h = V.ownedQty(c.n);
    return `<button class="result" data-card="${esc(c.n)}" aria-current="${k.sel === c.n}">
      <span class="nm">${esc(c.n)}${c.gc ? ' <span class="badge warn">Game Changer</span>' : ""}${c.b ? ' <span class="badge bad">Banned</span>' : ""}${h ? ` <span class="badge good">Own ${h}</span>` : ""}</span>
      <span class="pr">${V.mana(c.m)}</span>
      <span class="tl">${esc(c.t)}${c.pt ? " · " + esc(c.pt) : ""} · ${extra || V.money(V.priceInfo(c.n))}</span></button>`;
  }
  async function render() {
    if (!$("kRoles").innerHTML) $("kRoles").innerHTML = '<span class="sub">Find by job:</span>' + V.ROLES.map(([key, label]) => `<button class="chip" data-role="${key}" aria-pressed="false">${label}</button>`).join("");
    for (const b of document.querySelectorAll("[data-role]")) b.setAttribute("aria-pressed", k.role === b.dataset.role);
    const fc = filterCount(); $("kMoreCount").textContent = fc ? `(${fc} on)` : "";
    renderRecent();
    if (!S.cards) return;
    const nq = numberQuery($("kQ").value);
    if (nq) return renderNumber(nq);
    const list = matches(); last = list;
    const shown = Math.min(list.length, k.limit);
    $("kSummary").innerHTML = `<b>${list.length.toLocaleString()}</b> ${list.length === 1 ? "card matches" : "cards match"}${list.length > shown ? ` · showing ${shown}` : ""}`;
    $("kResults").innerHTML = list.length ? list.slice(0, shown).map(c => row(c)).join("") : '<p class="results-empty">No cards match. Loosen a filter, or press Clear filters.</p>';
    $("kMoreRes").hidden = list.length <= shown;
  }
  async function renderNumber(nq) {
    const key = `${nq.set}|${nq.cn}`;
    if (numberQ !== key) {
      numberQ = key; numberHits = null;
      $("kSummary").textContent = "Looking up that number…";
      try { numberHits = await api(`/api/cards/number?set=${encodeURIComponent(nq.set)}&cn=${encodeURIComponent(nq.cn)}`); }
      catch (e) { numberHits = { cards: [], error: e.message }; }
      if (numberQ !== key) return;
    }
    if (!numberHits) return;
    const hits = numberHits.cards || [];
    last = hits.map(h => V.lookup(h.name)).filter(Boolean);
    $("kSummary").innerHTML = numberHits.error ? esc(numberHits.error) : `<b>${hits.length}</b> ${hits.length === 1 ? "printing matches" : "printings match"} ${esc((nq.set || "").toUpperCase())} ${nq.cn ? "#" + esc(nq.cn) : ""}`;
    $("kResults").innerHTML = hits.length ? hits.slice(0, 200).map(h => {
      const c = V.lookup(h.name);
      const exact = S.caPr && (S.caPr.get(`${h.name}|${h.set}|${h.number}|0`) || S.caPr.get(`${h.name}|${h.set}|${h.number}|1`));
      const mine = V.copiesOf(h.name).some(x => x.set === h.set && String(x.number) === String(h.number));
      const extra = `${esc(h.set)} #${esc(h.number)} · ${esc(h.set_name)}${mine ? ' · <span class="badge good">You own this one</span>' : ""} · ${exact ? cad(exact[0]) + " at " + esc(exact[2]) : V.money(V.priceInfo(h.name))}`;
      return c ? row(c, extra) : `<div class="result"><span class="nm">${esc(h.name)}</span><span class="tl">${extra} · not a Commander card</span></div>`;
    }).join("") : '<p class="results-empty">No printing has that number. Try the set code too, like FRA 419.</p>';
    $("kMoreRes").hidden = true;
  }
  function recent() { try { return JSON.parse(localStorage.getItem("mtg-cards-recent") || "[]"); } catch (e) { return []; } }
  function renderRecent() { const r = recent(); $("kRecent").innerHTML = r.length ? '<span class="sub">Recently viewed</span>' + r.map(n => `<button class="mini" data-card="${esc(n)}">${esc(n)}</button>`).join("") : ""; }
  function pushRecent(n) { try { localStorage.setItem("mtg-cards-recent", JSON.stringify([n, ...recent().filter(x => x !== n)].slice(0, 8))); } catch (e) { } }

  // ---------- one card ----------
  function similar(c) {
    const roles = V.ROLES.filter(([, , f]) => f(c)).map(r => r[2]), kind = V.typeOf(c);
    const sub = (c.t.split(" — ")[1] || "").split(" // ")[0].split(" ").filter(Boolean); const out = [];
    for (const x of S.cards) {
      if (x === c || x.b || V.typeOf(x) !== kind) continue;
      if (c.ci && ![...x.ci].every(y => c.ci.includes(y))) continue;
      if (!roles.some(f => f(x)) && !(sub.length && sub.some(w => x.t.includes(w)))) continue;
      if (Math.abs(x.v - c.v) > 2) continue;
      out.push(x);
    }
    return out.sort((a, b) => (a.e || 1e6) - (b.e || 1e6)).slice(0, 8);
  }
  function fits(c) {
    return S.decks.filter(d => { const cm = V.lookup(d.commander); return cm && [...c.ci].every(x => cm.ci.includes(x)) && !d.list.some(x => norm(x[0]) === c._k) && norm(d.commander) !== c._k; });
  }
  function show(name) {
    const c = V.lookup(name); const el = $("kDetail");
    if (!c) { el.innerHTML = `<p class="results-empty">${esc(name)} isn't in the card database. It may be too new, or not a Commander card.</p>`; return; }
    k.sel = c.n; pushRecent(c.n); renderRecent();
    const h = V.ownedQty(c.n), ds = V.deckIndex().get(c._k), copies = V.copiesOf(c.n), fit = fits(c);
    el.innerHTML = `<div class="detail-top">
        <img class="card-img" src="https://api.scryfall.com/cards/named?exact=${encodeURIComponent(c.n)}&format=image&version=normal" alt="" loading="lazy">
        <div class="detail-main">
          <h2>${esc(c.n)}</h2>
          <p class="type">${V.mana(c.m)} ${esc(c.t)}${c.pt ? " · " + esc(c.pt) : ""}${c.l ? " · Loyalty " + esc(c.l) : ""}</p>
          <div class="badges">${c.gc ? '<span class="badge warn">Game Changer</span>' : ""}${c.b ? '<span class="badge bad">Banned in Commander</span>' : ""}<span class="badge">Colors ${V.pips(c.ci)}</span>${c.e ? `<span class="badge">EDHREC rank ${c.e.toLocaleString()}</span>` : ""}</div>
          <p class="oracle">${esc(c.o)}</p>
        </div></div>
      ${V.storeTable(c.n)}
      <p class="facts-line">${h ? `<b>You own ${h}</b>` : "You don't own this"}${V.trend(c.n) ? " · this week " + V.trend(c.n) : ""}${ds ? ` · In ${[...ds].map(x => `<span class="badge">${esc(x)}</span>`).join(" ")}` : ""}</p>
      ${copies.length ? `<h4>Your copies</h4><div class="minis">${copies.map(x => `<span class="mini">${x.qty}x ${esc(x.set)} ${esc(x.number)}${x.foil ? " foil" : ""} · ${cad(x.price)}${x.bin != null && x.sorted_into ? " · bin " + esc(x.sorted_into) : ""}</span>`).join("")}</div>` : ""}
      <h4>Printings</h4><div class="minis" id="kPrints"><button class="mini" id="kPrintsBtn">Show every printing</button></div>
      ${fit.length ? `<h4>Fits these decks</h4><div class="minis">${fit.map(d => `<button class="mini" data-addto="${esc(d.id)}">+ Add to ${esc(d.name)}</button>`).join("")}</div>` : ""}
      <h4>Jobs</h4><div class="minis">${V.ROLES.filter(([, , f]) => f(c)).map(([key, label]) => `<button class="mini" data-role-go="${key}">${label}</button>`).join("") || '<span class="sub">No common job found in its text.</span>'}</div>
      <h4>Similar cards</h4><div class="minis">${similar(c).map(x => `<button class="mini" data-card="${esc(x.n)}">${esc(x.n)} <span class="sub">${V.money(V.priceInfo(x.n))}</span></button>`).join("") || '<span class="sub">None close enough.</span>'}</div>
      <div class="add-row">
        ${S.decks.length ? `<select id="kAddDeck" aria-label="Deck">${S.decks.map(d => `<option value="${esc(d.id)}">${esc(d.name)}</option>`).join("")}</select><button class="btn ghost" id="kAddBtn">Add to deck</button>` : ""}
        <label class="price-range">Up to $<input id="kWishMax" type="number" step="0.5" min="0" placeholder="any"></label><button class="btn ghost" id="kWishBtn">Add to wishlist</button>
      </div>
      <p class="sub"><a href="https://scryfall.com/search?q=${encodeURIComponent('!"' + c.n + '"')}" target="_blank" rel="noopener">See it on Scryfall</a> · <a href="https://edhrec.com/cards/${encodeURIComponent(c.n.split(" // ")[0].toLowerCase().replace(/[^a-z0-9 -]/g, "").replace(/\s+/g, "-"))}" target="_blank" rel="noopener">EDHREC</a></p>`;
    for (const b of document.querySelectorAll(".result")) b.setAttribute("aria-current", b.dataset.card === c.n);
    if ($("kAddBtn")) $("kAddBtn").onclick = () => addToDeck($("kAddDeck").value, c.n);
    $("kWishBtn").onclick = () => api("/api/wishlist/add", { name: c.n, target: $("kWishMax").value }).then(() => toast(`Added ${c.n} to your wishlist`), e => toast(e.message));
    $("kPrintsBtn").onclick = async () => {
      $("kPrints").innerHTML = '<span class="sub">Asking Scryfall…</span>';
      const list = await api("/api/printings?name=" + encodeURIComponent(c.n)).catch(() => []);
      const mine = new Set(copies.map(x => `${x.set}|${x.number}`));
      $("kPrints").innerHTML = list.length ? list.slice(0, 80).map(p => `<a class="mini${mine.has(`${p.set}|${p.number}`) ? " on" : ""}" href="${esc(p.image || "#")}" target="_blank" rel="noopener" title="${esc(p.set_name)}">${esc(p.set)} #${esc(p.number)} · ${cad(p.price)}</a>`).join("") + (list.length > 80 ? `<span class="sub">and ${list.length - 80} more</span>` : "") + '<span class="sub">Highlighted: ones you own. Prices are Canadian when the store check has them.</span>'
        : '<span class="sub">Couldn\'t reach Scryfall.</span>';
    };
  }
  async function addToDeck(id, name) {
    const d = S.decks.find(x => x.id === id); if (!d) return;
    const c = V.lookup(name), nm = c ? c.n : name;
    const ex = d.list.find(x => norm(x[0]) === norm(nm));
    if (ex && !V.BASICS.has(norm(nm)) && !(c && /any number of cards named/i.test(c.o))) return toast(`${nm} is already in ${d.name}`);
    if (ex) ex[1]++; else d.list.push([nm, 1]);
    try { await api("/api/decks/save", { id: d.id, name: d.name, text: V.deckToText(d) }); toast(`Added ${nm} to ${d.name}`); if (k.sel) show(k.sel); }
    catch (e) { toast(e.message); }
  }

  // ---------- events ----------
  document.addEventListener("click", e => {
    const card = e.target.closest("[data-card]"); if (card) { show(card.dataset.card); if (matchMedia("(max-width: 860px)").matches) $("kDetail").scrollIntoView({ behavior: "smooth", block: "start" }); return; }
    const ro = e.target.closest("[data-role]"); if (ro) { k.role = k.role === ro.dataset.role ? "" : ro.dataset.role; k.limit = 80; render(); return; }
    const rg = e.target.closest("[data-role-go]"); if (rg) { k.role = rg.dataset.roleGo; k.limit = 80; render(); $("kResults").scrollIntoView({ block: "nearest" }); return; }
    const at = e.target.closest("[data-addto]"); if (at && k.sel) { addToDeck(at.dataset.addto, k.sel); return; }
  });
  let t; for (const id of ["kQ", "kText", "kType", "kMv", "kMvMin", "kOwn", "kSort", "kFor", "kKind", "kRar", "kPmax", "kPow", "kStock"]) $(id).addEventListener("input", () => { clearTimeout(t); k.limit = 80; t = setTimeout(render, 150); });
  for (const [id, key] of [["kCmd", "cmd"], ["kGc", "gc"], ["kNoGc", "noGc"], ["kNoBan", "noBan"]]) $(id).onclick = () => { k[key] = !k[key]; $(id).setAttribute("aria-pressed", k[key]); render(); };
  $("kColors").innerHTML = ["W", "U", "B", "R", "G", "C"].map(c => `<button class="chip" data-c="${c}" aria-pressed="false" title="${{ W: "White", U: "Blue", B: "Black", R: "Red", G: "Green", C: "Colorless" }[c]}"><span class="pip ${c}">${c}</span></button>`).join("");
  $("kColors").onclick = e => { const b = e.target.closest("[data-c]"); if (!b) return; const c = b.dataset.c; k.colors.has(c) ? k.colors.delete(c) : k.colors.add(c); b.setAttribute("aria-pressed", k.colors.has(c)); render(); };
  $("kMoreRes").onclick = () => { k.limit += 80; render(); };
  $("kHelpBtn").onclick = () => { $("kHelp").hidden = !$("kHelp").hidden; $("kHelpBtn").setAttribute("aria-expanded", !$("kHelp").hidden); };
  $("kRandom").onclick = () => { const pool = last.length ? last : S.cards || []; const c = pool[Math.floor(Math.random() * pool.length)]; if (c) show(c.n); };
  $("kQ").onkeydown = e => { if (e.key === "Enter" && last[0]) show(last[0].n); };
  $("kReset").onclick = () => {
    k.role = ""; k.limit = 80; k.colors.clear();
    for (const id of ["kQ", "kText", "kType", "kMv", "kMvMin", "kPmax", "kPow", "kOwn", "kKind", "kRar", "kStock", "kFor"]) $(id).value = "";
    for (const b of $("kColors").children) b.setAttribute("aria-pressed", "false");
    for (const [id, key, v] of [["kGc", "gc", false], ["kCmd", "cmd", false], ["kNoGc", "noGc", false], ["kNoBan", "noBan", true]]) { k[key] = v; $(id).setAttribute("aria-pressed", v); }
    render();
  };

  // ---------- start ----------
  (async () => {
    const params = new URLSearchParams(location.search);
    if (params.get("q")) $("kQ").value = params.get("q");
    await Promise.all([V.loadPrices(), V.loadOwned().catch(() => []), V.loadDecks().catch(() => [])]);
    $("kFor").innerHTML = '<option value="">Fits any deck</option>' + S.decks.filter(d => d.commander).map(d => `<option value="${esc(d.id)}">Fits ${esc(d.name)}</option>`).join("");
    await V.loadCards((text, pct) => { $("kSummary").textContent = pct != null ? `${text}, ${pct}%` : text; });
    $("kStatus").textContent = S.cards ? `${S.cards.length.toLocaleString()} Commander cards${S.caDate ? ` · Canadian Near Mint prices from ${S.caDate} (Face to Face Games first, then 401 Games, The Mythic Store and Hobbiesville)` : ""}` : "";
    render();
    if (params.get("card")) show(params.get("card"));
  })().catch(e => toast(e.message));
})();
