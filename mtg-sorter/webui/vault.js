// What Commander Vault knew, for the pages that need it (Card lookup, the deck builder):
// every Commander card (downloaded once from the Pi and kept in this browser), the
// Canadian store prices, and which cards you own and which decks they're in.
window.VAULT = (() => {
  const { esc, api } = MTG;
  const norm = s => String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[’']/g, "'").trim();
  const front = k => k.split(" // ")[0];
  const BASICS = new Set(["plains", "island", "swamp", "mountain", "forest", "wastes", "snow-covered plains", "snow-covered island", "snow-covered swamp", "snow-covered mountain", "snow-covered forest"]);
  const STORES = [["f2f", "Face to Face Games"], ["401", "401 Games"], ["myth", "The Mythic Store"], ["hob", "Hobbiesville"], ["cb", "Card Brawlers"], ["udc", "L'Univers de la Carte"]];
  const SHORT = { "Face to Face Games": "", "401 Games": "401", "The Mythic Store": "Mythic", "Hobbiesville": "Hobbiesville", "Card Brawlers": "Card Brawlers", "L'Univers de la Carte": "L'Univers" };
  const S = { cards: null, byName: null, built: "", ca: null, caPr: null, caPrev: null, caDate: "", owned: new Map(), copies: new Map(), items: [], decks: [] };
  const cad = v => v == null || isNaN(v) ? "–" : "$" + (v >= 1000 ? Math.round(v).toLocaleString("en-CA") : Number(v).toFixed(2));

  // ---------- the card database, cached in IndexedDB ----------
  const IDB = {
    open() { return new Promise((res, rej) => { try { const r = indexedDB.open("mtg-sorter", 1); r.onupgradeneeded = () => r.result.createObjectStore("kv"); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); } catch (e) { rej(e); } }); },
    async get(k) { try { const d = await this.open(); return await new Promise(res => { const q = d.transaction("kv").objectStore("kv").get(k); q.onsuccess = () => res(q.result); q.onerror = () => res(null); }); } catch (e) { return null; } },
    async set(k, v) { try { const d = await this.open(); return await new Promise(res => { const t = d.transaction("kv", "readwrite"); t.objectStore("kv").put(v, k); t.oncomplete = () => res(true); t.onerror = () => res(false); t.onabort = () => res(false); }); } catch (e) { return false; } },
    // Delete every key that starts with prefix (older copies of the card database).
    async prune(prefix) { try { const d = await this.open(); await new Promise(res => { const t = d.transaction("kv", "readwrite"), q = t.objectStore("kv").openCursor(); q.onsuccess = () => { const c = q.result; if (!c) return; if (String(c.key).startsWith(prefix)) c.delete(); c.continue(); }; t.oncomplete = res; t.onerror = res; t.onabort = res; }); } catch (e) { } },
  };
  const CARDDB_KEY = "carddb";   // one copy: {built, text}, replaced when the Pi builds a new one
  let cardLoad = null;
  // onStatus(text, percent) while downloading. Resolves to the card list, or null when the Pi has none yet.
  function loadCards(onStatus = () => { }) {
    if (cardLoad) return cardLoad;
    cardLoad = (async () => {
      const st = await api("/api/vault");
      S.status = st;
      if (!st.carddb || !st.carddb.cards) { onStatus(st.job === "carddb" ? "The Pi is building the card database. Try again in a minute." : "The card database isn't on the Pi yet. Settings, Prices and card data, Update now."); return null; }
      const saved = await IDB.get(CARDDB_KEY);
      let data = null;
      if (saved && saved.built === st.carddb.built && typeof saved.text === "string") { try { data = JSON.parse(saved.text); } catch (e) { data = null; } }
      if (!data) {
        onStatus("Downloading the card database", 0);
        const r = await fetch("/api/carddb");
        if (!r.ok) throw new Error("HTTP " + r.status);
        // The browser unpacks the gzip copy as it arrives, so count against the unpacked size.
        const total = st.carddb.raw_bytes || st.carddb.bytes || 0, reader = r.body.getReader(), parts = []; let got = 0;
        for (; ;) { const { done, value } = await reader.read(); if (done) break; parts.push(value); got += value.length; if (total) onStatus("Downloading the card database", Math.min(99, Math.round(got / total * 100))); }
        const text = await new Blob(parts).text();
        data = JSON.parse(text);
        // Saved as text, so the extra field added below isn't stored; then last week's copies go.
        IDB.set(CARDDB_KEY, { built: st.carddb.built, text }).then(ok => { if (ok) IDB.prune("carddb:"); });
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

  // A decklist's text as {commander, partner, list: [[name, qty]], side}. The Commander
  // section holds the commander, and a second one (Partner, a Background) as the partner.
  const SECTIONS = /^(\/\/\s*)?(deck|main|maindeck|mainboard|sideboard|side|sb|commanders?|companion|maybeboard|maybe|considering|tokens)\s*:?$/i;
  const SIDE = /^(sideboard|side|sb|maybeboard|maybe|considering|tokens|companion)$/;
  // The same clean-up, in the same order, as the Pi's parser (mtgscanner/decks.py _TAIL):
  // Moxfield's *F*, #tags, Archidekt's ^tags^ and [categories], "(SET) 123", <labels>.
  const TAIL = [/\s+\*[A-Za-z]+\*/g, /\s+#\S.*$/, /\s+\^[^^]*\^/g, /\s+\[[^\]]*\]/g, /\s+\([A-Za-z0-9]{2,6}\)(\s+\S+)?\s*$/, /\s+<[^>]*>/g];
  // One line of a decklist: null for blank lines and comments, {section} for a section
  // line, else {sec, name, q} (sec "commander", "side" or "list").
  function readLine(raw, section) {
    let line = String(raw || "").trim(); if (!line) return null;
    const sm = line.match(SECTIONS); if (sm) return { section: sm[2].toLowerCase() };
    if (/^(\/\/|#)/.test(line)) return null;
    let sec = section; if (/^sb:/i.test(line)) { line = line.slice(3).trim(); sec = "sideboard"; }
    const m = line.match(/^(\d{1,3})\s*[xX]?\s+(.+)$/); let name = m ? m[2] : line; const q = m ? +m[1] : 1;
    for (const re of TAIL) name = name.replace(re, "");
    name = name.trim(); if (!name || q < 1) return null;
    return { sec: /^commanders?$/.test(sec) ? "commander" : SIDE.test(sec) ? "side" : "list", name, q };
  }
  function parseDeck(text) {
    let section = "deck"; const out = { commander: "", partner: "", list: [], side: [] };
    for (const raw of String(text || "").split(/\r?\n/)) {
      const r = readLine(raw, section); if (!r) continue;
      if (r.section) { section = r.section; continue; }
      const { name, q } = r;
      if (r.sec === "commander") {
        if (!out.commander) { out.commander = name; if (q > 1) out.list.push([name, q - 1]); continue; }
        if (!out.partner && norm(name) !== norm(out.commander)) { out.partner = name; if (q > 1) out.list.push([name, q - 1]); continue; }
      }
      const target = r.sec === "side" ? out.side : out.list;
      const ex = target.find(x => norm(x[0]) === norm(name)); if (ex) ex[1] += q; else target.push([name, q]);
    }
    return out;
  }
  // The deck's commanders (one, or two with a partner) and their colors together.
  const cmds = d => [d.commander, d.partner].filter(Boolean);
  function cmdCI(d) {
    const found = cmds(d).map(lookup).filter(Boolean);
    return found.length ? new Set(found.flatMap(c => [...c.ci])) : null;
  }
  // True when two commanders say they can lead a deck together.
  function canPair(a, b) {
    const partner = c => /\bPartner\b|Friends forever/i.test(c.o);
    const bg = c => /Background/.test(c.t.split(" // ")[0]);
    return (partner(a) && partner(b)) || (/Choose a Background/i.test(a.o) && bg(b)) || (/Choose a Background/i.test(b.o) && bg(a))
      || /Doctor's companion/i.test(a.o + b.o);
  }
  function deckToText(d) {
    const lines = [];
    if (d.commander) lines.push("Commander", ...cmds(d).map(n => `1 ${n}`), "", "Deck");
    for (const [n, q] of d.list) lines.push(`${q} ${n}`);
    if (d.side && d.side.length) { lines.push("", "Sideboard"); for (const [n, q] of d.side) lines.push(`${q} ${n}`); }
    return lines.join("\n");
  }
  // Change a decklist's text one line at a time, leaving everything else as it was typed or
  // pasted (other sections, set codes and foil marks, comments). ops, in order:
  //   {add: name, n}     n more copies in the deck (a new line at the end of the deck part)
  //   {remove: name, n}  n fewer (the line goes at 0)
  //   {commander: name}  make it the commander; the old ones (and a partner) go into the deck
  function editDeckText(text, ops) {
    let lines = String(text || "").split(/\r?\n/);
    const same = (a, b) => { const x = norm(a), y = norm(b); return x === y || front(x) === front(y); };
    const scan = () => { let section = "deck"; return lines.map(raw => { const r = readLine(raw, section); if (r && r.section) section = r.section; return r; }); };
    const setQty = (raw, q) => { const m = raw.match(/^(\s*(?:SB:\s*)?)(\d{1,3})(\s*[xX]?\s+)/i); return m ? m[1] + q + m[3] + raw.slice(m[0].length) : raw.replace(/^(\s*(?:SB:\s*)?)/i, `$1${q} `); };
    function add(name, n) {
      const info = scan(), i = info.findIndex(r => r && r.sec === "list" && same(r.name, name));
      if (i >= 0) { lines[i] = setQty(lines[i], info[i].q + n); return; }
      let at = -1; info.forEach((r, j) => { if (r && r.sec === "list") at = j; });
      if (at >= 0) { lines.splice(at + 1, 0, `${n} ${name}`); return; }
      // No deck cards yet: add after a Deck line, or start a Deck part at the end.
      let end = "deck"; for (const r of info) if (r && r.section) end = r.section;
      while (lines.length && !lines[lines.length - 1].trim()) lines.pop();
      const deckPart = !/^commanders?$/.test(end) && !SIDE.test(end);
      lines.push(...(deckPart ? [] : ["", "Deck"]), `${n} ${name}`);
    }
    function remove(name, n) {
      const info = scan(), i = info.findIndex(r => r && r.sec === "list" && same(r.name, name));
      if (i < 0) return;
      if (info[i].q > n) lines[i] = setQty(lines[i], info[i].q - n); else lines.splice(i, 1);
    }
    function commander(name) {
      let info = scan(); const moved = [];   // (bottom up, so the line numbers stay right)
      for (let i = info.length - 1; i >= 0; i--) {
        const r = info[i];
        if (r && r.sec === "commander") { if (!same(r.name, name)) moved.unshift([r.name, r.q]); lines.splice(i, 1); }
        else if (r && r.sec === "list" && same(r.name, name)) lines.splice(i, 1);
      }
      info = scan();
      const head = lines.findIndex(raw => { const m = raw.trim().match(SECTIONS); return m && /^commanders?$/i.test(m[2]); });
      if (head >= 0) lines.splice(head + 1, 0, `1 ${name}`);
      else {
        const first = info.findIndex(r => r);   // the first card or section line
        const top = ["Commander", `1 ${name}`, ""];
        if (first < 0 || !info[first].section) top.push("Deck");
        lines.splice(0, 0, ...top);
      }
      for (const [n, q] of moved) add(n, q);
    }
    for (const op of ops || []) {
      if (op.add) add(op.add, op.n || 1);
      else if (op.remove) remove(op.remove, op.n || 1);
      else if (op.commander) commander(op.commander);
    }
    return lines.join("\n");
  }
  async function loadDecks() { const js = await api("/api/decks"); S.decks = (js.decks || []).map(d => ({ ...d, ...parseDeck(d.text) })); return S.decks; }
  function deckIndex() {
    const m = new Map();
    for (const d of S.decks) for (const n of [...cmds(d), ...d.list.map(x => x[0])].filter(Boolean)) { const k = norm(n); if (!m.has(k)) m.set(k, new Set()); m.get(k).add(d.name); }
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
    const checks = [], bad = new Set(), names = cmds(d), found = names.map(lookup), ci = cmdCI(d);
    const who = names.join(" and ");
    const count = d.list.reduce((s, x) => s + x[1], 0) + names.length;
    checks.push(count === 100 ? ["ok", `100 cards, ${names.length > 1 ? "commanders" : "commander"} included.`] : ["bad", `${count} cards. A Commander deck is exactly 100 with the commander.`]);
    if (!d.commander) checks.push(["bad", "No commander set. Put it under a Commander line, or press Set commander."]);
    names.forEach((n, i) => {
      const c = found[i];
      if (c && !isCommander(c) && !/Background/.test(c.t)) checks.push(["warn", `${n} isn't a legendary creature. Check that it can be a commander.`]);
      else if (S.cards && !c) checks.push(["warn", `${n} isn't in the card database. Check the spelling.`]);
    });
    if (found.length === 2 && found[0] && found[1] && !canPair(found[0], found[1])) checks.push(["warn", `${who} don't say they can lead a deck together (Partner or Choose a Background). Check that they can.`]);
    const off = [], banned = [], unknown = [], gcs = [], dupes = [], seen = new Map();
    for (const [n, q] of d.list) {
      const c = lookup(n); if (S.cards && !c) unknown.push(n);
      const k = norm(c ? c.n : n); seen.set(k, (seen.get(k) || 0) + q);
      if (c && ci && ![...c.ci].every(x => ci.has(x))) { off.push(c.n); bad.add(norm(n)); }
      if (c && c.b) { banned.push(c.n); bad.add(norm(n)); }
      if (c && c.gc) gcs.push(c.n);
    }
    for (const c of [...found].reverse()) { if (c && c.gc) gcs.unshift(c.n); if (c && c.b) banned.unshift(c.n); }
    for (const [k, q] of seen) { const c = S.byName && S.byName.get(k); if (q > 1 && !BASICS.has(k) && !(c && /any number of cards named/i.test(c.o))) { dupes.push(c ? c.n : k); bad.add(k); } }
    if (S.cards) {
      checks.push(off.length ? ["bad", `Outside ${who || "the commander"}'s colors: ${off.join(", ")}.`] : ["ok", `Every card fits the ${names.length > 1 ? "commanders'" : "commander's"} colors.`]);
      checks.push(dupes.length ? ["bad", `More than one copy: ${dupes.join(", ")}. Only basic lands can repeat.`] : ["ok", "No duplicates."]);
      if (banned.length) checks.push(["bad", `Banned in Commander: ${banned.join(", ")}.`]);
      checks.push(gcs.length === 0 ? ["ok", "No Game Changers, so Bracket 1 or 2 is possible."] : gcs.length <= 3 ? ["warn", `${gcs.length} Game Changer${gcs.length > 1 ? "s" : ""} (${gcs.join(", ")}): Bracket 3 at least.`] : ["warn", `${gcs.length} Game Changers (${gcs.join(", ")}): Bracket 4.`]);
      if (unknown.length) checks.push(["warn", `Not found in the card database: ${unknown.slice(0, 6).join(", ")}${unknown.length > 6 ? "…" : ""}. Check the spelling.`]);
    } else checks.push(["warn", "Color, duplicate and Game Changer checks run once the card database loads."]);
    return { checks, bad, count, gcs, bracket: gcs.length === 0 ? "1 to 2" : gcs.length <= 3 ? "3" : "4+" };
  }
  // Checks for a 60-card (or 40-card Limited) deck with no commander: deck size, the
  // sideboard, at most 4 copies, and the formats every card is legal in.
  const CONSTRUCTED = [["s", "Standard"], ["p", "Pioneer"], ["m", "Modern"], ["l", "Legacy"], ["v", "Vintage"], ["u", "Pauper"]];
  function constructedChecks(d) {
    const checks = [], bad = new Set(), count = d.list.reduce((s, x) => s + x[1], 0), side = (d.side || []).reduce((s, x) => s + x[1], 0);
    checks.push(count >= 60 ? ["ok", `${count} cards in the main deck.`] : count >= 40 ? ["warn", `${count} cards: fine for Limited (40), short of 60 for Constructed.`] : ["bad", `${count} cards. A deck needs at least 60 (40 for Limited).`]);
    if (side) checks.push(side <= 15 ? ["ok", `${side} card sideboard.`] : ["bad", `${side} cards in the sideboard. The most is 15.`]);
    const seen = new Map(), unknown = [];
    for (const [n, q] of [...d.list, ...(d.side || [])]) { const c = lookup(n); if (S.cards && !c) unknown.push(n); const k = norm(c ? c.n : n); seen.set(k, (seen.get(k) || 0) + q); }
    const over = []; let legalIn = [];
    for (const [k, q] of seen) { const c = S.byName && S.byName.get(k); if (q > 4 && !BASICS.has(k) && !(c && /any number of cards named/i.test(c.o))) { over.push(`${c ? c.n : k} (${q})`); bad.add(k); } }
    if (S.cards) {
      checks.push(over.length ? ["bad", `More than 4 copies: ${over.join(", ")}. Only basic lands can go past 4.`] : ["ok", "No more than 4 copies of any card."]);
      const legal = [], notLegal = [];
      for (const [k, f] of CONSTRUCTED) {
        const off = [...seen.keys()].map(n => S.byName.get(n)).filter(c => c && !BASICS.has(norm(c.n)) && !(c.lg || "").includes(k));
        if (!off.length) legal.push(f); else notLegal.push([f, off]);
      }
      legalIn = legal;
      if (legal.length) checks.push(["ok", `Legal in ${legal.join(", ")}.`]);
      for (const [f, off] of notLegal.slice(0, 2)) checks.push(["warn", `Not legal in ${f}: ${off.slice(0, 4).map(c => c.n).join(", ")}${off.length > 4 ? ` and ${off.length - 4} more` : ""}.`]);
      if (unknown.length) checks.push(["warn", `Not found in the card database: ${unknown.slice(0, 6).join(", ")}${unknown.length > 6 ? "…" : ""}. Check the spelling.`]);
    } else checks.push(["warn", "Copy and format checks run once the card database loads."]);
    return { checks, bad, count, legal: legalIn };
  }
  function deckStats(d) {
    const all = [...cmds(d).map(n => [n, 1]), ...d.list];
    let count = 0, own = 0, cost = 0, value = 0; const need = [];
    for (const [n, q] of all) {
      count += q; const have = d.proxied || BASICS.has(norm(n)) ? q : Math.min(q, ownedQty(n)); own += have;   // basics: everyone has a pile
      const p = priceOf(n) || 0; value += p * q;
      if (have < q && !BASICS.has(norm(n))) { cost += p * (q - have); need.push([n, q - have, p]); }
    }
    return { count, own, cost, value, need };
  }

  return { S, norm, BASICS, STORES, cad, loadCards, lookup, loadPrices, caRec, priceInfo, priceOf, money, trend, storeTable, loadOwned, ownedQty, copiesOf, parseDeck, deckToText, editDeckText, cmds, cmdCI, loadDecks, deckIndex, TYPES, typeOf, isCommander, pips, mana, ROLES, ROLEF, deckChecks, constructedChecks, deckStats };
})();
