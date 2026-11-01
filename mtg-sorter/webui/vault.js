// What Commander Vault knew, for the pages that need it (Card lookup, the deck builder):
// every Commander card (downloaded once from the Pi and kept in this browser), the
// Canadian store prices, and which cards you own and which decks they're in.
window.VAULT = (() => {
  const { esc, api } = MTG;
  const norm = s => String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[’']/g, "'").trim();
  const front = k => k.split(" // ")[0];
  const BASICS = new Set(["plains", "island", "swamp", "mountain", "forest", "wastes", "snow-covered plains", "snow-covered island", "snow-covered swamp", "snow-covered mountain", "snow-covered forest"]);
  const STORES = [["f2f", "Face to Face Games"], ["401", "401 Games"], ["myth", "The Mythic Store"], ["hob", "Hobbiesville"]];
  const SHORT = { "Face to Face Games": "", "401 Games": "401", "The Mythic Store": "Mythic", "Hobbiesville": "Hobbiesville" };
  const S = { cards: null, byName: null, built: "", ca: null, caPr: null, caPrev: null, caDate: "", owned: new Map(), copies: new Map(), items: [], decks: [] };
  const cad = v => v == null || isNaN(v) ? "–" : "$" + (v >= 1000 ? Math.round(v).toLocaleString("en-CA") : Number(v).toFixed(2));

  // ---------- the card database, cached in IndexedDB ----------
  const IDB = {
    open() { return new Promise((res, rej) => { try { const r = indexedDB.open("mtg-sorter", 1); r.onupgradeneeded = () => r.result.createObjectStore("kv"); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); } catch (e) { rej(e); } }); },
    async get(k) { try { const d = await this.open(); return await new Promise(res => { const q = d.transaction("kv").objectStore("kv").get(k); q.onsuccess = () => res(q.result); q.onerror = () => res(null); }); } catch (e) { return null; } },
    async set(k, v) { try { const d = await this.open(); await new Promise(res => { const t = d.transaction("kv", "readwrite"); t.objectStore("kv").put(v, k); t.oncomplete = res; t.onerror = res; }); } catch (e) { } },
  };
  let cardLoad = null;
  // onStatus(text, percent) while downloading. Resolves to the card list, or null when the Pi has none yet.
  function loadCards(onStatus = () => { }) {
    if (cardLoad) return cardLoad;
    cardLoad = (async () => {
      const st = await api("/api/vault");
      S.status = st;
      if (!st.carddb || !st.carddb.cards) { onStatus(st.job === "carddb" ? "The Pi is building the card database. Try again in a minute." : "The card database isn't on the Pi yet. Settings, Prices and card data, Update now."); return null; }
      const key = "carddb:" + st.carddb.built;
      let data = await IDB.get(key);
      if (!data) {
        onStatus("Downloading the card database", 0);
        const r = await fetch("/api/carddb");
        if (!r.ok) throw new Error("HTTP " + r.status);
        const total = st.carddb.bytes || 0, reader = r.body.getReader(), parts = []; let got = 0;
        for (; ;) { const { done, value } = await reader.read(); if (done) break; parts.push(value); got += value.length; if (total) onStatus("Downloading the card database", Math.min(99, Math.round(got / total * 100))); }
        data = JSON.parse(await new Blob(parts).text());
        IDB.set(key, data);
      }
      S.cards = data.cards; S.built = st.carddb.built; S.byName = new Map();
      for (const c of S.cards) { const k = norm(c.n); c._k = k; S.byName.set(k, c); if (k.includes(" // ") && !S.byName.has(front(k))) S.byName.set(front(k), c); }
      onStatus(`${S.cards.length.toLocaleString()} cards`);
      return S.cards;
    })().catch(e => { cardLoad = null; onStatus("The card database didn't load. Reload the page to try again."); console.error(e); return null; });
    return cardLoad;
  }
  function lookup(name) { if (!S.byName) return null; const k = norm(name); return S.byName.get(k) || S.byName.get(front(k)) || null; }

  // ---------- Canadian prices ----------
  async function loadPrices() {
    const x = await api("/api/vault/prices").catch(() => ({}));
    S.ca = new Map(Object.entries(x.prices || {}).map(([k, v]) => [norm(k), v]));
    S.caPr = new Map(Object.entries(x.printings || {}));
    S.caPrev = new Map(Object.entries(x.prev || {}).map(([k, v]) => [norm(k), v]));
    S.caDate = x.date || "";
    return S.ca;
  }
  function caRec(name) { if (!S.ca) return null; const k = norm(name); return S.ca.get(k) || S.ca.get(front(k)) || null; }
  // Face to Face Games is the main price. The other stores fill in when it doesn't list the card.
  function caBest(name, foil) {
    const r = caRec(name); if (!r) return null; const opts = [];
    for (const [k, store] of STORES) { const x = r[k]; if (!x) continue; const v = foil ? (x[2] ?? null) : x[0]; if (v != null && v > 0) opts.push({ p: v, store, inStock: foil ? true : !!x[1] }); }
    if (!opts.length) return foil ? caBest(name, false) : null;
    const f2f = opts.find(o => o.store === "Face to Face Games"); if (f2f) return f2f;
    const inS = opts.filter(o => o.inStock); const pool = inS.length ? inS : opts;
    return pool.reduce((a, b) => b.p < a.p ? b : a);
  }
  const priceInfo = (name, foil) => caBest(name, foil);
  const priceOf = (name, foil) => { const i = caBest(name, foil); return i ? i.p : null; };
  function money(info) {
    if (!info) return '<span class="muted" title="No Canadian store price yet. The weekly price check looks it up.">–</span>';
    const st = info.store && SHORT[info.store];
    return cad(info.p) + (st ? ` <span class="muted small" title="Face to Face Games doesn't list this card, so this is ${esc(info.store)}'s price">${st}</span>` : "")
      + (info.inStock === false ? ` <span class="badge" title="Out of stock at ${esc(info.store || "the store")}">Out</span>` : "");
  }
  function trend(name) {
    const prev = S.caPrev && S.caPrev.get(norm(name)); const now = priceOf(name);
    if (prev == null || now == null) return "";
    const d = now - prev; if (Math.abs(d) < 0.01) return "";
    return d < 0 ? `<span class="down">▼ ${cad(-d)}</span>` : `<span class="up">▲ ${cad(d)}</span>`;
  }
  function storeTable(name) {
    const r = caRec(name);
    if (!r) return '<p class="sub">No Canadian store price yet. Add it to a deck, your collection or your wishlist and the weekly price check looks it up.</p>';
    return `<table class="list stores"><thead><tr><th>Store</th><th class="num">Near Mint</th><th class="num">Foil NM</th></tr></thead><tbody>` + STORES.map(([k, store]) => {
      const x = r[k];
      return `<tr><td>${store}${k === "f2f" ? ' <span class="badge good">Main</span>' : ""}</td>${!x ? '<td class="num muted" colspan="2">Not listed</td>' :
        `<td class="num">${x[0] > 0 ? cad(x[0]) + (x[1] ? ' <span class="badge good">In stock</span>' : ' <span class="badge">Out</span>') : "–"}</td><td class="num">${x[2] > 0 ? cad(x[2]) : "–"}</td>`}</tr>`;
    }).join("") + `</tbody></table><p class="sub">Cheapest Near Mint copy of any printing, checked ${esc(S.caDate)}.</p>`;
  }

  // ---------- your cards and decks ----------
  async function loadOwned() {
    const js = await api("/api/collection");
    S.items = js.cards || []; S.owned = new Map(); S.copies = new Map();
    for (const it of S.items) {
      for (const k of new Set([norm(it.name), front(norm(it.name))])) { S.owned.set(k, (S.owned.get(k) || 0) + it.qty); if (!S.copies.has(k)) S.copies.set(k, []); S.copies.get(k).push(it); }
    }
    return S.items;
  }
  const ownedQty = name => { const k = norm(name); return S.owned.get(k) || S.owned.get(front(k)) || 0; };
  const copiesOf = name => { const k = norm(name); return S.copies.get(k) || S.copies.get(front(k)) || []; };

  // A decklist's text as {commander, list: [[name, qty]]}. The Commander section holds the commander.
  const SECTIONS = /^(\/\/\s*)?(deck|main|maindeck|mainboard|sideboard|side|sb|commanders?|companion|maybeboard|maybe|considering|tokens)\s*:?$/i;
  function parseDeck(text) {
    let section = "deck"; const out = { commander: "", list: [], side: [] };
    for (let line of String(text || "").split(/\r?\n/)) {
      line = line.trim(); if (!line) continue;
      const sm = line.match(SECTIONS); if (sm) { section = sm[2].toLowerCase(); continue; }
      if (/^(\/\/|#)/.test(line)) continue;
      let sec = section; if (/^sb:/i.test(line)) { line = line.slice(3).trim(); sec = "sideboard"; }
      line = line.replace(/\s+\*[A-Za-z]+\*/g, "").replace(/\s+\([A-Za-z0-9]{2,6}\)(\s+\S+)?\s*$/, "").replace(/\s+\[[^\]]*\]/g, "").replace(/\s+#\S.*$/, "").trim();
      const m = line.match(/^(\d{1,3})\s*[xX]?\s+(.+)$/); const name = (m ? m[2] : line).trim(); const q = m ? +m[1] : 1;
      if (!name) continue;
      if (/^commanders?$/.test(sec) && !out.commander) { out.commander = name; if (q > 1) out.list.push([name, q - 1]); continue; }
      const target = /^(sideboard|side|sb|maybeboard|maybe|considering|tokens|companion)$/.test(sec) ? out.side : out.list;
      const ex = target.find(x => norm(x[0]) === norm(name)); if (ex) ex[1] += q; else target.push([name, q]);
    }
    return out;
  }
  function deckToText(d) {
    const lines = [];
    if (d.commander) lines.push("Commander", `1 ${d.commander}`, "", "Deck");
    for (const [n, q] of d.list) lines.push(`${q} ${n}`);
    if (d.side && d.side.length) { lines.push("", "Sideboard"); for (const [n, q] of d.side) lines.push(`${q} ${n}`); }
    return lines.join("\n");
  }
  async function loadDecks() { const js = await api("/api/decks"); S.decks = (js.decks || []).map(d => ({ ...d, ...parseDeck(d.text) })); return S.decks; }
  function deckIndex() {
    const m = new Map();
    for (const d of S.decks) for (const n of [d.commander, ...d.list.map(x => x[0])].filter(Boolean)) { const k = norm(n); if (!m.has(k)) m.set(k, new Set()); m.get(k).add(d.name); }
    return m;
  }

  // ---------- card helpers ----------
  const TYPES = ["Creature", "Planeswalker", "Battle", "Instant", "Sorcery", "Artifact", "Enchantment", "Land"];
  function typeOf(c) { if (!c) return "Unknown"; const f = c.t.split(" // ")[0]; for (const t of TYPES) if (f.includes(t)) return t; return "Other"; }
  const isCommander = c => (/Legendary/.test(c.t) && /Creature/.test(c.t.split(" // ")[0])) || /can be your commander/i.test(c.o);
  function pips(ci) { return ci ? [...ci].map(c => `<span class="pip ${c}">${c}</span>`).join("") : '<span class="pip C">C</span>'; }
  function mana(m) { return esc(m || "").replace(/\{([^}]+)\}/g, (_, s) => { const cls = /^[WUBRG]$/.test(s) ? s : (/^[WUBRG]\/P$/.test(s) ? s[0] : "C"); return `<span class="pip ${cls}" title="${esc(s)}">${esc(s.length > 2 ? s.replace("/", "")[0] : s)}</span>`; }); }
  // Card jobs, matched on rules text. Rough on purpose: good for browsing, not a rules engine.
  const ROLES = [
    ["ramp", "Ramp", c => !/Land/.test(c.t.split(" // ")[0]) && /(\{T\}: add \{|add one mana|add \{[wubrgc]\}|search your library for (a|up to \w+) (basic )?lands? card|put (a|up to \w+) lands? cards? .*onto the battlefield|create (a|two|\w+) treasure)/i.test(c.o)],
    ["draw", "Card draw", c => /\bdraws? (a|two|three|four|x|that many|\w+) cards?\b|\bdraw cards?\b/i.test(c.o)],
    ["removal", "Removal", c => /(destroy|exile) target (creature|permanent|nonland|artifact|enchantment|planeswalker|attacking)|deals? (\d+|x) damage to (any target|target creature)|target creature gets -\d+\/-\d+|target (player|opponent) sacrifices/i.test(c.o)],
    ["wipe", "Board wipes", c => /(destroy|exile) all (creatures|nonland|permanents|other creatures)|all creatures get -|deals? (\d+|x) damage to each creature|each player sacrifices all|return all (nonland|creatures)/i.test(c.o)],
    ["counter", "Counterspells", c => /counter target/i.test(c.o)],
    ["tutor", "Tutors", c => /search your library for (a|an|up to \w+) (?!basic)(?!.*lands? card)/i.test(c.o)],
    ["recursion", "Recursion", c => /return (target|up to|a|all|it|that card)[^.]*from (your|a) graveyard to (your hand|the battlefield)/i.test(c.o)],
    ["protect", "Protection", c => /(gains?|have|has) (hexproof|indestructible|shroud|protection)|phase(s)? out/i.test(c.o)],
    ["tokens", "Token makers", c => /create (a|an|two|three|x|\w+)[^.]*token/i.test(c.o)],
    ["lifegain", "Lifegain", c => /\bgain (\d+|x|that much) life|\blifelink\b/i.test(c.o)],
    ["drain", "Drain", c => /each opponent loses (\d+|x) life|target (opponent|player) loses (\d+|x) life/i.test(c.o)],
    ["sac", "Sacrifice outlets", c => /sacrifice (a|another) (creature|permanent|artifact)[^:]*:/i.test(c.o)],
    ["evasion", "Evasion", c => /\b(flying|menace|trample|can't be blocked|unblockable|shadow|fear|intimidate)\b/i.test(c.o)],
  ];
  const ROLEF = Object.fromEntries(ROLES.map(([k, , f]) => [k, f]));

  // The Commander checks for a deck: count, commander, colors, duplicates, banned, Game Changers.
  function deckChecks(d) {
    const checks = [], bad = new Set(), cmd = lookup(d.commander), ci = cmd ? new Set(cmd.ci) : null;
    const count = d.list.reduce((s, x) => s + x[1], 0) + (d.commander ? 1 : 0);
    checks.push(count === 100 ? ["ok", "100 cards, commander included."] : ["bad", `${count} cards. A Commander deck is exactly 100 with the commander.`]);
    if (!d.commander) checks.push(["bad", "No commander set. Put it under a Commander line, or press Set commander."]);
    else if (cmd && !isCommander(cmd)) checks.push(["warn", `${d.commander} isn't a legendary creature. Check that it can be a commander.`]);
    else if (S.cards && !cmd) checks.push(["warn", `${d.commander} isn't in the card database. Check the spelling.`]);
    const off = [], banned = [], unknown = [], gcs = [], dupes = [], seen = new Map();
    for (const [n, q] of d.list) {
      const c = lookup(n); if (S.cards && !c) unknown.push(n);
      const k = norm(c ? c.n : n); seen.set(k, (seen.get(k) || 0) + q);
      if (c && ci && ![...c.ci].every(x => ci.has(x))) { off.push(c.n); bad.add(norm(n)); }
      if (c && c.b) { banned.push(c.n); bad.add(norm(n)); }
      if (c && c.gc) gcs.push(c.n);
    }
    if (cmd && cmd.gc) gcs.unshift(cmd.n);
    if (cmd && cmd.b) banned.unshift(cmd.n);
    for (const [k, q] of seen) { const c = S.byName && S.byName.get(k); if (q > 1 && !BASICS.has(k) && !(c && /any number of cards named/i.test(c.o))) { dupes.push(c ? c.n : k); bad.add(k); } }
    if (S.cards) {
      checks.push(off.length ? ["bad", `Outside ${d.commander || "the commander"}'s colors: ${off.join(", ")}.`] : ["ok", "Every card fits the commander's colors."]);
      checks.push(dupes.length ? ["bad", `More than one copy: ${dupes.join(", ")}. Only basic lands can repeat.`] : ["ok", "No duplicates."]);
      if (banned.length) checks.push(["bad", `Banned in Commander: ${banned.join(", ")}.`]);
      checks.push(gcs.length === 0 ? ["ok", "No Game Changers, so Bracket 1 or 2 is possible."] : gcs.length <= 3 ? ["warn", `${gcs.length} Game Changer${gcs.length > 1 ? "s" : ""} (${gcs.join(", ")}): Bracket 3 at least.`] : ["warn", `${gcs.length} Game Changers (${gcs.join(", ")}): Bracket 4.`]);
      if (unknown.length) checks.push(["warn", `Not found in the card database: ${unknown.slice(0, 6).join(", ")}${unknown.length > 6 ? "…" : ""}. Check the spelling.`]);
    } else checks.push(["warn", "Color, duplicate and Game Changer checks run once the card database loads."]);
    return { checks, bad, count, gcs, bracket: gcs.length === 0 ? "1 to 2" : gcs.length <= 3 ? "3" : "4+" };
  }
  function deckStats(d) {
    const all = [...(d.commander ? [[d.commander, 1]] : []), ...d.list];
    let count = 0, own = 0, cost = 0, value = 0; const need = [];
    for (const [n, q] of all) {
      count += q; const have = d.proxied ? q : Math.min(q, ownedQty(n)); own += have;
      const p = priceOf(n) || 0; value += p * q;
      if (have < q && !BASICS.has(norm(n))) { cost += p * (q - have); need.push([n, q - have, p]); }
    }
    return { count, own, cost, value, need };
  }

  return { S, norm, BASICS, STORES, cad, loadCards, lookup, loadPrices, caRec, priceInfo, priceOf, money, trend, storeTable, loadOwned, ownedQty, copiesOf, parseDeck, deckToText, loadDecks, deckIndex, TYPES, typeOf, isCommander, pips, mana, ROLES, ROLEF, deckChecks, deckStats };
})();
