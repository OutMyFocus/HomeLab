// The Bins page: rules for which bin each card goes into (any mix of conditions), with a live preview.
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = v => "$" + Number(v || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const COLOR_NAMES = { W: "White", U: "Blue", B: "Black", R: "Red", G: "Green", M: "Multicolor", C: "Colorless" };
  let info = null, draft = null, saved = null, previewT, toastT;

  function toast(msg) {
    const t = $("toast"); $("toastText").textContent = msg;
    t.hidden = true; void t.offsetWidth; t.hidden = false;
    clearTimeout(toastT); toastT = setTimeout(() => t.hidden = true, 2400);
  }
  async function api(path, body) {
    const r = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const js = await r.json().catch(() => ({}));
    if (r.status === 401 && js.locked) { location.href = "/lock?next=" + encodeURIComponent(location.pathname); throw new Error("Locked"); }
    if (!r.ok) throw new Error(js.error || `Error ${r.status}`);
    return js;
  }
  const clone = o => JSON.parse(JSON.stringify(o));
  // key order can change while editing (the wanted list's text becomes cards), so compare sorted
  const stable = o => JSON.stringify(o, (k, v) => v && typeof v === "object" && !Array.isArray(v)
    ? Object.fromEntries(Object.keys(v).sort().map(x => [x, v[x]])) : v);
  const dirty = () => stable(draft) !== stable(saved);

  function take(js, { keepDraft = false, isSaved = false } = {}) {
    info = js;
    if (!keepDraft) draft = clone(js.rules);
    else if (draft.wanted && draft.wanted.text !== undefined && $("wText").value === draft.wanted.text) {
      // the server read the pasted list: keep its cards, so Save and Undo compare like with like
      draft.wanted.cards = clone(js.rules.wanted.cards);
      delete draft.wanted.text;
    }
    if (isSaved || !saved) saved = clone(js.rules);
    render();
  }

  // ---------- presets ----------
  function renderPresets() {
    $("presets").innerHTML = info.presets.map(p => `<button class="preset" data-id="${p.id}"><b>${esc(p.label)}</b><small>${esc(p.hint)}</small></button>`).join("");
  }
  $("presets").onclick = async e => {
    const b = e.target.closest(".preset"); if (!b) return;
    try {
      const wanted = draft.wanted;      // a preset is only the rules: keep the wanted list
      take(await api("/api/bins/preview", { preset: b.dataset.id, wanted }));
      toast("Loaded. Press Save to use it");
    }
    catch (err) { toast(err.message); }
  };

  // ---------- the bins ----------
  const trays = () => info.trays || info.bins;
  // Bin 0 (the original price bins' "Unknown price") has no tray: shown only while it's used.
  const used = b => draft.fallback === b || draft.rules.some(r => r.bin === b) || (draft.wanted.on && draft.wanted.bin === b);
  const shownBins = () => info.bins.filter(b => trays().includes(b) || used(b));
  // A bin with no tray on this sorter: say where its cards really drop.
  const noTray = b => trays().includes(b) ? ""
    : `No tray on this sorter: these cards drop into bin ${info.fallback_tray} (${draft.names[info.fallback_tray] || ""}).`;
  function trayIntro() {
    const t = trays(), list = t.length > 1 ? `${t.slice(0, -1).join(", ")} and ${t[t.length - 1]}` : `${t[0]}`;
    $("trayNote").textContent = `The sorter has ${t.length} bin${t.length === 1 ? "" : "s"}: ${list}. `;
  }
  function renderBins() {
    const p = info.preview, total = Math.max(1, Object.values(p).reduce((n, b) => n + b.cards, 0));
    const box = $("binCards"), want = shownBins();
    trayIntro();
    const have = [...box.querySelectorAll("[data-name]")].map(i => +i.dataset.name);
    if (have.length && have.join() === want.join()) {   // update in place, so typing a bin's name isn't interrupted
      for (const b of want) {
        const card = box.querySelector(`[data-name="${b}"]`).closest(".bin-card"), v = p[b];
        const note = card.querySelector(".no-tray");
        note.textContent = noTray(b); note.hidden = !note.textContent;
        card.querySelector(".count").innerHTML = `${v.cards.toLocaleString()} <span class="sub">cards · ${money(v.value)}</span>`;
        card.querySelector(".share span").style.width = (100 * v.cards / total).toFixed(1) + "%";
        card.querySelector(".ex").textContent = v.examples.length ? "Like " + v.examples.join(", ") : "Nothing from your collection";
        card.querySelector(".catch").hidden = draft.fallback !== b;
        const input = card.querySelector("input");
        if (input !== document.activeElement) input.value = draft.names[b];
      }
      return;
    }
    box.innerHTML = want.map(b => {
      const v = p[b] || { cards: 0, value: 0, examples: [] };
      return `<div class="panel bin-card" style="--c: var(--bin${b})">
        <div class="head"><span class="pill bin-${b}">Bin ${b}</span><input class="field" data-name="${b}" value="${esc(draft.names[b])}" maxlength="40" aria-label="Name of bin ${b}"></div>
        <div class="count">${v.cards.toLocaleString()} <span class="sub">cards · ${money(v.value)}</span></div>
        <div class="share"><span style="width:${(100 * v.cards / total).toFixed(1)}%"></span></div>
        <div class="ex">${v.examples.length ? "Like " + v.examples.map(esc).join(", ") : "Nothing from your collection"}</div>
        <div class="sub catch"${draft.fallback === b ? "" : " hidden"}>Catch-all: gets anything no rule takes</div>
        <div class="sub no-tray"${noTray(b) ? "" : " hidden"}>${esc(noTray(b))}</div>
      </div>`;
    }).join("");
  }
  $("binCards").oninput = e => { const i = e.target.closest("[data-name]"); if (i) { draft.names[i.dataset.name] = i.value; changed(false); } };

  // ---------- rules ----------
  // Every kind of condition: its label, a new one's starting values, and its group in the menu.
  const FIELDS = {
    price: ["Price", { min: null, max: null }, "Price"], noprice: ["Has no price", {}, "Price"],
    foil: ["Foil", {}, "Price"], copies: ["Extra copies", { over: 4 }, "Price"],
    type: ["Card type", { types: ["Land"], mode: "any" }, "Card"], typeline: ["Type line has", { text: "" }, "Card"],
    color: ["Color", { mode: "any", colors: [] }, "Card"], identity: ["Color identity", { mode: "within", colors: [] }, "Card"],
    ncolors: ["Number of colors", { min: 2, max: null }, "Card"], mv: ["Mana value", { min: null, max: null }, "Card"],
    rarity: ["Rarity", { values: [] }, "Card"], set: ["Set", { values: [] }, "Card"],
    name: ["Name", { mode: "contains", text: "" }, "Card"], text: ["Rules text has", { text: "" }, "Card"],
    format: ["Format", { format: "commander", status: "legal" }, "Play"], deck: ["My decks", { deck: "", how: "list" }, "Play"],
    wishlist: ["On my wishlist", {}, "Play"], edhrec: ["EDHREC rank", { max: 1000 }, "Play"], gc: ["Game Changer", {}, "Play"],
  };
  const NEEDS_LIST = new Set(["identity", "type", "typeline", "mv", "format", "text", "edhrec", "gc"]);
  const COLOR_MODES = { any: "has any of", all: "has all of", exact: "is exactly", within: "fits inside", group: "main color is" };
  const FORMAT_NAMES = { standard: "Standard", pioneer: "Pioneer", modern: "Modern", legacy: "Legacy", vintage: "Vintage", pauper: "Pauper",
    commander: "Commander", brawl: "Brawl", historic: "Historic", premodern: "Premodern", oathbreaker: "Oathbreaker" };
  const RARE = x => x[0].toUpperCase() + x.slice(1);
  const opt = (v, label, sel) => `<option value="${esc(v)}"${String(v) === String(sel) ? " selected" : ""}>${esc(label)}</option>`;
  const binOptions = sel => shownBins().map(b => opt(b, `Bin ${b} · ${draft.names[b]}`, sel)).join("");
  const num = (k, v, ph, step = 1) => `<input class="field" type="number" min="0" step="${step}" data-c="${k}" placeholder="${ph}" value="${v ?? ""}">`;
  const chips = (k, list, have, label = x => x, dot) => `<span class="chips">${list.map(x => `<button type="button" class="chip" data-chip="${k}" data-v="${esc(x)}" aria-pressed="${have.includes(x)}">${dot ? `<i style="background:var(--mana-${x})"></i>` : ""}${esc(label(x))}</button>`).join("")}</span>`;
  const colorChips = c => chips("colors", ["W", "U", "B", "R", "G", "C"].concat(c.mode === "group" || c.mode === "any" ? ["M"] : []), c.colors, x => COLOR_NAMES[x], true);
  const deckName = id => (info.decks.find(d => d.id === id) || {}).name || "a deck that's gone";

  function editor(c) {
    switch (c.f) {
      case "price": return `<span class="muted">$</span>${num("min", c.min, "any", .5)}<span class="muted">up to (not incl.) $</span>${num("max", c.max, "any", .5)}`;
      case "mv": return `${num("min", c.min, "any")}<span class="muted">to</span>${num("max", c.max, "any")}`;
      case "ncolors": return `${num("min", c.min, "any")}<span class="muted">to</span>${num("max", c.max, "any")}<span class="muted">colors</span>`;
      case "color": case "identity":
        return `<select class="field" data-c="mode">${Object.entries(COLOR_MODES).map(([k, l]) => opt(k, l, c.mode)).join("")}</select>${colorChips(c)}`;
      case "type": return `<select class="field" data-c="mode">${opt("any", "any of", c.mode)}${opt("all", "all of", c.mode)}</select>${chips("types", info.types, c.types)}`;
      case "typeline": return `<input class="field wide" data-c="text" placeholder="Elf, Goblin, Equipment" value="${esc(c.text)}">`;
      case "text": return `<input class="field wide" data-c="text" placeholder="draw a card" value="${esc(c.text)}">`;
      case "rarity": return chips("values", info.rarities, c.values, RARE);
      case "set": return `<input class="field wide" data-c="sets" placeholder="Set codes, like MH3, DMU" value="${esc(c.values.join(", "))}">`;
      case "name": return `<select class="field" data-c="mode">${opt("contains", "contains", c.mode)}${opt("starts", "starts with", c.mode)}${opt("list", "is one of (one per line)", c.mode)}</select>` +
        (c.mode === "list" ? `<textarea class="field" data-c="text" placeholder="Sol Ring&#10;Lightning Bolt">${esc(c.text)}</textarea>` : `<input class="field wide" data-c="text" value="${esc(c.text)}">`);
      case "format": return `<select class="field" data-c="status">${opt("legal", "legal in", c.status)}${opt("banned", "banned in", c.status)}${opt("not_legal", "not legal in", c.status)}</select>` +
        `<select class="field" data-c="format">${info.formats.map(f => opt(f, FORMAT_NAMES[f] || f, c.format)).join("")}</select>`;
      case "deck": return `<select class="field" data-c="how">${opt("list", "the card is in", c.how)}${opt("colors", "the card fits the colors of", c.how)}</select>` +
        `<select class="field" data-c="deck">${opt("", "any of my decks", c.deck)}${info.decks.map(d => opt(d.id, d.name + (c.how === "colors" && d.ci ? ` (${d.ci})` : ""), c.deck)).join("")}${c.deck && !info.decks.some(d => d.id === c.deck) ? opt(c.deck, "A deck that's gone", c.deck) : ""}</select>` +
        (info.decks.length ? "" : `<span class="muted">No decks saved yet: add them on the Decks page.</span>`);
      case "copies": return `<span class="muted">more than</span>${num("over", c.over, "4")}<span class="muted">of the same card: copy ${(c.over ?? 4) + 1} and up</span>`;
      case "edhrec": return `<span class="muted">in the top</span>${num("max", c.max, "1000")}`;
      case "noprice": return `<span class="muted">tokens, very old or odd printings</span>`;
      case "foil": return `<span class="muted">the Foil switch was on when it was scanned</span>`;
      case "wishlist": return `<span class="muted">${info.wishlist ? info.wishlist + " cards on it" : "your wishlist is empty"}</span>`;
      case "gc": return `<span class="muted">on Commander's Game Changers list</span>`;
    }
    return "";
  }

  // Plain words for a condition: "a Land", "not foil", "$10 and up".
  const list = (xs, join = "or") => xs.length <= 1 ? xs.join("") : `${xs.slice(0, -1).join(", ")} ${join} ${xs[xs.length - 1]}`;
  const range = (lo, hi, unit = "", top = "to") => lo != null && hi != null ? `${unit}${lo} ${top} ${unit}${hi}` : lo != null ? `${unit}${lo} and up` : hi != null ? `under ${unit}${hi}` : "any";
  function say(c) {
    const n = c.not ? "not " : "";
    switch (c.f) {
      case "price": return `price ${n}${range(c.min, c.max, "$", "to under")}`;
      case "noprice": return c.not ? "has a price" : "has no price";
      case "foil": return c.not ? "not foil" : "foil";
      case "copies": return `${n}copy ${(c.over ?? 4) + 1} or later`;
      case "type": return c.types.length ? `${n}${list(c.types, c.mode === "all" ? "and" : "or")}` : "any type";
      case "typeline": return `type line ${c.not ? "without" : "with"} “${c.text}”`;
      case "color": case "identity": return `${c.f === "color" ? "color" : "identity"} ${n}${COLOR_MODES[c.mode]} ${list(c.colors.map(x => COLOR_NAMES[x]), c.mode === "all" ? "and" : "or") || "(pick colors)"}`;
      case "ncolors": return `${n}${range(c.min, c.max, "", "to")} colors`;
      case "mv": return `mana value ${n}${range(c.min, c.max)}`;
      case "rarity": return `${n}${list(c.values.map(RARE)) || "any rarity"}`;
      case "set": return `${c.not ? "not from" : "from"} ${list(c.values) || "any set"}`;
      case "name": return `name ${n}${c.mode === "list" ? "on your list" : (c.mode === "starts" ? "starting with" : "with") + ` “${c.text}”`}`;
      case "text": return `rules text ${c.not ? "without" : "with"} “${c.text}”`;
      case "format": return `${n}${{ legal: "legal", banned: "banned", not_legal: "not legal" }[c.status]} in ${FORMAT_NAMES[c.format] || c.format}`;
      case "deck": return `${n}${c.how === "colors" ? "fits the colors of" : "in"} ${c.deck ? deckName(c.deck) : "one of my decks"}`;
      case "wishlist": return `${n}on my wishlist`;
      case "edhrec": return `${n}top ${c.max} on EDHREC`;
      case "gc": return `${n}a Game Changer`;
    }
    return c.f;
  }
  const sayRule = r => r.conds.length ? r.conds.map(c => `<b>${esc(say(c))}</b>`).join(r.match === "any" ? " or " : " and ") : "<b>every card</b>";
  const groups = () => ["Price", "Card", "Play"].map(g => `<optgroup label="${{ Price: "Price and copies", Card: "The card", Play: "Decks and formats" }[g]}">${Object.entries(FIELDS).filter(([, v]) => v[2] === g).map(([k, v]) => opt(k, v[0])).join("")}</optgroup>`).join("");

  function renderRules() {
    const hits = info.rule_hits || [];
    $("rules").innerHTML = draft.rules.length ? draft.rules.map((r, i) => `<div class="rule2${r.on ? "" : " off"}" data-i="${i}" style="--c: var(--bin${r.bin})">
      <div class="r-head">
        <span class="no">${i + 1}</span>
        <label class="switch" title="Turn this rule on or off"><input type="checkbox" data-on${r.on ? " checked" : ""}><span></span></label>
        <span class="r-goto">→ <select class="field" data-k="bin" aria-label="Bin">${binOptions(r.bin)}</select></span>
        <span class="hits">${r.on ? `${(hits[i] || 0).toLocaleString()} of your cards` : "Off"}</span>
        <span class="tools">
          <button class="icon-btn" data-move="-1" aria-label="Move up"${i ? "" : " disabled"}><svg><use href="#i-up"/></svg></button>
          <button class="icon-btn" data-move="1" aria-label="Move down"${i < draft.rules.length - 1 ? "" : " disabled"}><svg><use href="#i-down"/></svg></button>
          <button class="icon-btn" data-dup aria-label="Copy rule"><svg><use href="#i-copy"/></svg></button>
          <button class="icon-btn" data-del aria-label="Delete rule"><svg><use href="#i-trash"/></svg></button>
        </span>
      </div>
      <div class="r-say">${sayRule(r)} <span>→ bin ${r.bin}</span></div>
      ${r.conds.length > 1 ? `<div class="r-match">Cards that match
        <span class="seg"><button type="button" data-match="all" aria-pressed="${r.match !== "any"}">all</button><button type="button" data-match="any" aria-pressed="${r.match === "any"}">any</button></span>
        of these</div>` : ""}
      <div class="conds2">${r.conds.length ? r.conds.map((c, j) => `<div class="cond2${c.not ? " is-not" : ""}" data-j="${j}">
          <button type="button" class="not-btn" data-not aria-pressed="${!!c.not}" title="Turn this condition around">NOT</button>
          <span class="what">${esc(FIELDS[c.f][0])}</span>${editor(c)}
          <button class="icon-btn del" data-cdel aria-label="Remove condition"><svg><use href="#i-x"/></svg></button></div>`).join("")
        : `<div class="every">No conditions: every card that gets this far goes here.</div>`}</div>
      <div class="add-cond"><select class="field" data-add aria-label="Add a condition"><option value="">+ Add a condition…</option>${groups()}</select></div>
    </div>`).join("") : '<p class="sub">No rules: every card goes to the catch-all bin.</p>';
    $("fallback").innerHTML = binOptions(draft.fallback);
    renderFactsNote();
  }
  function renderFactsNote() {
    const need = draft.rules.some(r => r.on && r.conds.some(c => NEEDS_LIST.has(c.f)));
    const fmt = draft.rules.some(r => r.on && r.conds.some(c => c.f === "format" && c.format !== "commander"));
    const f = info.facts || {}, n = $("factsNote");
    let msg = "";
    if (need && !f.have) msg = "Card types, mana value, rules text and formats come from the card list, which isn't downloaded yet. Until it is, those conditions match nothing.";
    else if (fmt && !f.formats) msg = "Your card list was downloaded before formats were added, so only Commander can be checked. Update it to check the other formats.";
    n.hidden = !msg;
    n.innerHTML = msg ? `<span>${esc(msg)}</span><button class="btn ghost" id="getList" type="button">${f.have ? "Update the card list" : "Download the card list"}</button>` : "";
    if (msg) $("getList").onclick = async () => {
      try { await api("/api/vault/run", { job: "carddb" }); toast("Downloading the card list. Counts update in a minute or two"); setTimeout(() => changed(false), 60000); }
      catch (e) { toast(e.message); }
    };
  }
  const ruleAt = el => draft.rules[+el.closest(".rule2").dataset.i];
  const condAt = el => ruleAt(el).conds[+el.closest(".cond2").dataset.j];
  $("rules").oninput = e => {
    const t = e.target;
    if (t.dataset.c && t.tagName !== "SELECT") {
      const c = condAt(t), k = t.dataset.c;
      if (k === "sets") c.values = t.value.split(/[\s,]+/).map(x => x.trim().toUpperCase()).filter(Boolean);
      else if (t.type === "number") c[k] = t.value === "" ? null : +t.value;
      else c[k] = t.value;
      sayAgain(t); changed(false);
    }
  };
  // Update the rule's plain-words line while typing, without rebuilding the row.
  const sayAgain = t => { const row = t.closest(".rule2"), r = ruleAt(t); row.querySelector(".r-say").innerHTML = `${sayRule(r)} <span>→ bin ${r.bin}</span>`; };
  $("rules").onchange = e => {
    const t = e.target;
    if (t.dataset.k === "bin") { ruleAt(t).bin = +t.value; changed(true); return; }
    if (t.hasAttribute("data-on")) { ruleAt(t).on = t.checked; changed(true); return; }
    if (t.hasAttribute("data-add")) {
      const f = t.value; if (!f) return;
      ruleAt(t).conds.push({ f, not: false, ...clone(FIELDS[f][1]) });
      changed(true); return;
    }
    if (t.dataset.c && t.tagName === "SELECT") {
      const c = condAt(t); c[t.dataset.c] = t.value;
      if (t.dataset.c === "mode" && c.colors) c.colors = c.colors.filter(x => x !== "M" || t.value === "group" || t.value === "any");
      changed(true);
    }
  };
  $("rules").onclick = e => {
    const t = e.target, row = t.closest(".rule2"); if (!row) return;
    const i = +row.dataset.i, r = draft.rules[i];
    const chip = t.closest("[data-chip]"), not = t.closest("[data-not]"), match = t.closest("[data-match]");
    const move = t.closest("[data-move]"), del = t.closest("[data-del]"), dup = t.closest("[data-dup]"), cdel = t.closest("[data-cdel]");
    if (chip) {
      const c = condAt(chip), k = chip.dataset.chip, v = chip.dataset.v;
      c[k] = c[k].includes(v) ? c[k].filter(x => x !== v) : [...c[k], v];
    } else if (not) { const c = condAt(not); c.not = !c.not; }
    else if (match) r.match = match.dataset.match;
    else if (cdel) r.conds.splice(+cdel.closest(".cond2").dataset.j, 1);
    else if (move) { const j = i + +move.dataset.move; [draft.rules[i], draft.rules[j]] = [draft.rules[j], draft.rules[i]]; }
    else if (dup) draft.rules.splice(i + 1, 0, clone(r));
    else if (del) draft.rules.splice(i, 1);
    else return;
    changed(true);
  };
  $("addRule").onclick = () => {
    const free = trays().find(b => !draft.rules.some(r => r.bin === b)) ?? trays()[0];
    draft.rules.push({ bin: free, match: "all", on: true, conds: [{ f: "type", not: false, ...clone(FIELDS.type[1]) }] });
    changed(true);
    setTimeout(() => { const all = $("rules").querySelectorAll(".rule2"); all[all.length - 1]?.scrollIntoView({ behavior: "smooth", block: "center" }); }, 50);
  };
  $("fallback").onchange = () => { draft.fallback = +$("fallback").value; changed(true); };

  // ---------- wanted cards (checked before the rules) ----------
  const realBins = () => trays();
  const listText = w => (w.cards || []).map(c => `${c.qty} ${c.name}`).join("\n");
  function renderWanted(full) {
    const w = draft.wanted, sum = info.wanted || {};
    $("wantedPanel").classList.toggle("off", !w.on);
    $("wOn").checked = w.on; $("wOnly").checked = w.only; $("wLimit").checked = w.limit; $("wBasics").checked = w.skip_basics;
    const opts = sel => realBins().map(b => `<option value="${b}"${b === sel ? " selected" : ""}>Bin ${b} · ${esc(draft.names[b])}</option>`).join("");
    if (document.activeElement !== $("wBin")) $("wBin").innerHTML = opts(w.bin);
    if (document.activeElement !== $("wOthers")) $("wOthers").innerHTML = opts(w.others);
    $("wOthersRow").hidden = !w.only;
    if (full || (document.activeElement !== $("wText") && w.text === undefined)) $("wText").value = w.text ?? listText(w);
    $("wSource").textContent = w.source ? `From ${w.source}` : "";
    const decks = info.decks || [];
    if ($("wDeck").options.length !== decks.length + 1)
      $("wDeck").innerHTML = '<option value="">Fill from a deck…</option>' + decks.map(d => `<option value="${esc(d.id)}">${esc(d.name)}</option>`).join("");
    $("wDeck").hidden = !decks.length;
    $("wWish").hidden = !info.wishlist;
    const f = $("wFound");
    if (!sum.cards) { f.innerHTML = w.on ? "The list is empty: add some cards." : ""; return; }
    const miss = (sum.missing || []).slice(0, 12).map(m => esc(m.qty > 1 ? `${m.qty} ${m.name}` : m.name));
    f.innerHTML = `<b>${sum.cards.toLocaleString()}</b> card${sum.cards === 1 ? "" : "s"} on the list (${sum.different} different).
      Your collection already has <b>${sum.found.toLocaleString()}</b> of them.` +
      (miss.length ? ` Not scanned yet: ${miss.join(", ")}${sum.missing.length > miss.length ? ` and ${sum.missing.length - miss.length} more` : ""}.` : "") +
      (w.on ? "" : " <b>Turn on Pull wanted cards to use the list.</b>");
  }
  const setWanted = (k, v) => { draft.wanted[k] = v; renderWanted(); changed(false); };
  $("wOn").onchange = () => setWanted("on", $("wOn").checked);
  $("wOnly").onchange = () => setWanted("only", $("wOnly").checked);
  $("wLimit").onchange = () => setWanted("limit", $("wLimit").checked);
  $("wBasics").onchange = () => setWanted("skip_basics", $("wBasics").checked);
  $("wBin").onchange = () => {
    const b = +$("wBin").value;
    if (draft.wanted.others === b) draft.wanted.others = realBins().find(x => x !== b);   // can't be the same bin
    $("wOthers").innerHTML = ""; setWanted("bin", b);
  };
  $("wOthers").onchange = () => setWanted("others", +$("wOthers").value);
  $("wText").oninput = () => { draft.wanted.text = $("wText").value; changed(false); };
  function fill(text, source) {
    Object.assign(draft.wanted, { text, source, on: true });
    renderWanted(true); changed(false);
    toast(`Filled from ${source}. Press Save to use it`);
  }
  $("wDeck").onchange = async () => {
    const id = $("wDeck").value; if (!id) return;
    try { const js = await api("/api/bins/wanted/list", { deck: id }); fill(js.text, js.source); }
    catch (e) { toast(e.message); }
    $("wDeck").value = "";
  };
  $("wWish").onclick = async () => {
    try { const js = await api("/api/bins/wanted/list", { wishlist: true }); fill(js.text, js.source); }
    catch (e) { toast(e.message); }
  };
  $("wClear").onclick = () => { Object.assign(draft.wanted, { text: "", source: "" }); renderWanted(true); changed(false); };

  // ---------- preview and save ----------
  function changed(rerender) {
    if (rerender) renderRules();
    updateBar();
    clearTimeout(previewT);
    previewT = setTimeout(async () => {
      try { take(await api("/api/bins/preview", draft), { keepDraft: true }); $("saveNote").className = "sub"; updateBar(); }
      catch (err) { $("saveNote").className = "err"; $("saveNote").textContent = err.message; $("saveBtn").disabled = true; }
    }, 350);
  }
  function updateBar() {
    const d = dirty();
    $("saveBtn").disabled = !d; $("undoBtn").disabled = !d;
    document.querySelector(".save-bar").classList.toggle("dirty", d);
    $("resetBtn").hidden = !info.custom;
    $("saveNote").className = "sub";
    $("saveNote").textContent = d ? "Not saved yet. The counts above show what would happen." : info.custom ? "These are your saved rules." : "Using the original price bins from config.py.";
  }
  function render() {
    renderPresets(); renderBins(); renderWanted();
    // Don't rebuild the rule rows while someone is typing in them (it would lose the cursor):
    // only the counts change.
    const typing = $("rules").contains(document.activeElement) && /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName);
    if (!typing) renderRules();
    else {
      const hits = info.rule_hits || [];
      $("rules").querySelectorAll(".rule2").forEach((row, i) => { const r = draft.rules[i]; row.querySelector(".hits").textContent = r && r.on ? `${(hits[i] || 0).toLocaleString()} of your cards` : "Off"; });
      renderFactsNote();
    }
    updateBar();
  }
  $("saveBtn").onclick = async () => {
    try { take(await api("/api/bins", draft), { isSaved: true }); toast("Saved. New scans use these bins"); }
    catch (e) { toast(e.message); }
  };
  $("undoBtn").onclick = () => { draft = clone(saved); renderRules(); renderWanted(true); changed(false); };
  $("resetBtn").onclick = async () => {
    if (!confirm("Go back to the original price bins? Your rules here are deleted.")) return;
    try { take(await api("/api/bins/reset", {}), { isSaved: true }); toast("Back to the price bins"); }
    catch (e) { toast(e.message); }
  };
  addEventListener("beforeunload", e => { if (draft && dirty()) { e.preventDefault(); e.returnValue = ""; } });

  api("/api/bins").then(js => take(js, { isSaved: true })).catch(e => { $("saveNote").textContent = "Can't reach the scanner: " + e.message; });
})();
