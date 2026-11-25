// The Decks page: paste a decklist, see what you own, what's missing and what it costs.
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = v => v == null ? "–" : "$" + Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const DRAFT_KEY = "mtg-deck-draft", VIEW_KEY = "mtg-deck-view";
  let decks = [], currentId = null, result = null, show = "all", toastT, view = "list";
  try { if (localStorage.getItem(VIEW_KEY) === "pics") view = "pics"; } catch (e) {}

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
  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    const t = document.createElement("textarea"); t.value = text; t.style.position = "fixed"; t.style.opacity = "0";
    document.body.append(t); t.select(); document.execCommand("copy"); t.remove();
    return Promise.resolve();
  }

  // ---------- saved decks ----------
  function renderDecks() {
    $("savedDecks").innerHTML = decks.length ? decks.slice().reverse().map(d => `<button class="deck-item" data-id="${esc(d.id)}" aria-current="${d.id === currentId}">
        <b>${esc(d.name)}</b><small>${d.text.split("\n").filter(l => l.trim()).length} lines · saved ${esc(d.updated)}${d.proxied ? " · proxies" : ""}</small></button>`).join("")
      : '<p class="none">Decks you save show up here.</p>';
    $("deleteDeck").hidden = !currentId;
  }
  // True when the list in the box has changes that aren't saved (a saved deck that was
  // edited, or a new list typed or pasted in).
  function unsaved() {
    const d = decks.find(x => x.id === currentId), t = $("deckText").value;
    if (!d) return !!t.trim();
    const name = ($("deckName").value.trim() || "Untitled deck").slice(0, 80);   // as the Pi saves it
    return t !== d.text || name !== d.name;
  }
  const discardOk = () => !unsaved() || confirm("Discard your unsaved changes to this list?");
  $("savedDecks").onclick = e => {
    const b = e.target.closest(".deck-item"); if (!b) return;
    const d = decks.find(x => x.id === b.dataset.id); if (!d) return;
    if (d.id !== currentId && !discardOk()) return;
    currentId = d.id; $("deckName").value = d.name; $("deckText").value = d.text;
    renderDecks(); countLines(); checkDeck();
    document.dispatchEvent(new CustomEvent("deck-opened"));
  };
  $("newDeck").onclick = () => {
    if (!discardOk()) return;
    currentId = null; $("deckName").value = ""; $("deckText").value = ""; $("result").hidden = true;
    renderDecks(); countLines(); $("deckText").focus();
    document.dispatchEvent(new CustomEvent("deck-opened"));
  };
  // One save at a time, each sending the list as it is when its turn comes, so an older
  // save can never land after a newer one (the builder saves after every change).
  let saving = Promise.resolve();
  function queueSave(extra = {}) {
    const run = saving.then(() => api("/api/decks/save", { id: currentId, name: $("deckName").value, text: $("deckText").value, ...extra }));
    saving = run.catch(() => { });
    return run;
  }
  $("saveDeck").onclick = async () => {
    if (!$("deckText").value.trim()) return toast("Paste a decklist first");
    try {
      const js = await queueSave();
      decks = js.decks; currentId = js.deck.id; $("deckName").value = js.deck.name; renderDecks(); countLines();
      toast(`Saved ${js.deck.name}`);
    } catch (e) { toast(e.message); }
  };
  // The sorter pulls this deck's cards into the Bins page's wanted bin while it sorts.
  $("pullDeck").onclick = async () => {
    if (!$("deckText").value.trim()) return toast("Paste a decklist first");
    const name = $("deckName").value.trim() || "a pasted deck";
    try {
      const js = await api("/api/bins/wanted", { on: true, text: $("deckText").value, source: name });
      const w = js.rules.wanted;
      toast(`The sorter now pulls ${w.cards.length} card${w.cards.length === 1 ? "" : "s"} into bin ${w.bin} · Bins page to change it`);
    } catch (e) { toast(e.message); }
  };
  $("deleteDeck").onclick = async () => {
    const d = decks.find(x => x.id === currentId);
    if (!d || !confirm(`Delete the saved deck "${d.name}"? Your cards aren't touched.`)) return;
    try { decks = (await api("/api/decks/delete", { id: d.id })).decks; currentId = null; renderDecks(); toast(`Deleted ${d.name}`); }
    catch (e) { toast(e.message); }
  };

  // ---------- the decklist ----------
  function countLines() {
    const n = $("deckText").value.split("\n").filter(l => l.trim() && !/^(\/\/|#)/.test(l.trim())).length;
    $("lineCount").textContent = n ? `${n} line${n === 1 ? "" : "s"}` : "";
    try { localStorage.setItem(DRAFT_KEY, JSON.stringify({ id: currentId, name: $("deckName").value, text: $("deckText").value })); } catch (e) {}
  }
  $("deckText").oninput = countLines;
  $("deckName").oninput = countLines;
  $("deckText").onkeydown = e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); checkDeck(); } };

  async function checkDeck() {
    const btn = $("checkDeck"); btn.disabled = true; btn.firstChild.textContent = "Checking… ";
    try { result = await api("/api/decks/check", { text: $("deckText").value }); renderResult(); }
    catch (e) { toast(e.message); }
    finally { btn.disabled = false; btn.firstChild.textContent = "Check my collection "; }
  }
  $("checkDeck").onclick = checkDeck;

  function renderResult() {
    const r = result;
    $("result").hidden = false;
    $("rPercent").textContent = r.percent + "%";
    $("rBar").style.width = r.percent + "%";
    $("rHave").textContent = `${r.have} of ${r.need}`;
    $("rHaveSub").textContent = r.missing ? "" : "You own every card!";
    $("rMissing").textContent = r.missing;
    $("rMissingSub").textContent = `${r.lines.filter(x => x.missing).length} different cards`;
    $("rCost").textContent = money(r.cost);
    $("rCostSub").textContent = r.unpriced ? `${r.unpriced} cards have no price` : r.missing ? "At today's prices" : "";
    $("rUnknown").hidden = !r.unknown.length;
    $("rUnknown").textContent = r.unknown.length ? `Couldn't find ${r.unknown.length === 1 ? "this card" : "these cards"}: ${r.unknown.join(", ")}. Check the spelling.` : "";
    for (const b of $("showSeg").children) b.setAttribute("aria-pressed", b.dataset.v === show);
    for (const b of $("viewSeg").children) b.setAttribute("aria-pressed", b.dataset.v === view);
    const rows = r.lines.filter(x => show === "all" || (show === "missing" ? x.missing : x.have));
    $("rPics").hidden = view !== "pics"; $("rTable").hidden = view === "pics";
    if (view === "pics") return renderPics(rows);
    $("rRows").innerHTML = rows.length ? rows.map(x => {
      const cls = x.extra ? "" : !x.found ? "unknown" : x.missing ? "short" : "ok";
      const where = x.where.map(w => `<span class="pill bin-${w.bin}" title="${esc(w.sorted_into || "")}">${esc(w.set)} #${esc(w.number)}${w.foil ? " foil" : ""} ×${w.qty}</span>`).join("");
      const img = x.image ? `<img class="thumb" src="${esc(x.image.replace("version=normal", "version=small"))}" alt="" loading="lazy">` : '<span class="thumb"></span>';
      return `<tr class="${cls}"><td class="card-cell">${img}<span><span class="nm">${esc(x.name)}</span><span class="sec">${esc(x.section)}${x.extra ? " · not counted" : x.basic ? " · basic land" : ""}</span></span></td>
        <td class="num">${x.need}</td><td class="num">${x.have}<span class="of">/${x.need}</span></td>
        <td class="hide-sm"><span class="where">${where || '<span class="sub">Not in your collection</span>'}</span></td>
        <td class="num hide-sm">${x.missing ? money(x.price) : ""}</td>
        <td class="num miss">${x.missing ? `${x.missing}${x.cost != null ? " · " + money(x.cost) : ""}` : ""}</td></tr>`;
    }).join("") : `<tr class="empty-row"><td colspan="6">${show === "missing" ? "Nothing missing" : "Nothing here"}</td></tr>`;
  }
  // Pictures: the deck as card pictures, a section at a time. Cards you're short of are
  // dimmed, with how many to get on the corner.
  function renderPics(rows) {
    if (!rows.length) { $("rPics").innerHTML = `<p class="none">${show === "missing" ? "Nothing missing" : "Nothing here"}</p>`; return; }
    const sections = [];
    for (const x of rows) { let g = sections.find(s => s.name === x.section); if (!g) sections.push(g = { name: x.section, items: [] }); g.items.push(x); }
    $("rPics").innerHTML = sections.map(g => `<section><h4>${esc(g.name)} <span class="sub">${g.items.reduce((n, x) => n + x.need, 0)}</span></h4><div class="pic-grid">${g.items.map(x => {
      const small = x.image ? x.image.replace("version=normal", "version=small") : "";
      const state = x.extra ? "extra" : !x.found ? "unknown" : x.missing ? "short" : "ok";
      const tag = x.extra ? "" : x.missing ? `<span class="pic-tag short">Need ${x.missing}${x.cost != null ? " · " + money(x.cost) : ""}</span>` : `<span class="pic-tag ok">✓ ${x.have}</span>`;
      return `<a class="pic ${state}" href="/cards?card=${encodeURIComponent(x.name)}" title="${esc(x.name)}: need ${x.need}, have ${x.have}">
        ${small ? `<img src="${esc(small)}" srcset="${esc(small)} 146w, ${esc(x.image)} 488w" sizes="(max-width: 600px) 30vw, 150px" alt="${esc(x.name)}" loading="lazy">` : `<span class="pic-blank">${esc(x.name)}</span>`}
        ${x.need > 1 ? `<span class="pic-qty">${x.need}×</span>` : ""}${tag}</a>`;
    }).join("")}</div></section>`).join("");
  }
  $("viewSeg").onclick = e => {
    const b = e.target.closest("button"); if (!b || !result) return;
    view = b.dataset.v; try { localStorage.setItem(VIEW_KEY, view); } catch (err) {}
    renderResult();
  };
  $("showSeg").onclick = e => { const b = e.target.closest("button"); if (b && result) { show = b.dataset.v; renderResult(); } };

  function missingList() {
    const rows = (result?.lines || []).filter(x => x.missing && x.found && !x.extra);
    return rows.map(x => `${x.missing} ${x.name}`).join("\n") + (rows.length ? "\n" : "");
  }
  $("copyMissing").onclick = () => {
    const t = missingList(); if (!t) return toast("Nothing missing");
    copy(t).then(() => toast("Copied. Paste it into a shop's mass entry box"), () => toast("Couldn't copy"));
  };

  $("wishMissing").onclick = async () => {
    const cards = (result?.lines || []).filter(x => x.missing && x.found && !x.extra).map(x => ({ name: x.name }));
    if (!cards.length) return toast("Nothing missing");
    try { await api("/api/wishlist/add", { cards }); toast(`Added ${cards.length} cards to your wishlist`); }
    catch (e) { toast(e.message); }
  };

  // For the deck builder (builder.js): the saved deck being edited, and a quiet save.
  window.DECKS = {
    current: () => decks.find(x => x.id === currentId) || null,
    async save(extra = {}) {
      if (!currentId) return null;
      const js = await queueSave(extra);
      decks = js.decks; renderDecks(); return js.deck;
    },
    changed() { countLines(); },
  };

  async function start() {
    try { decks = (await api("/api/decks")).decks; } catch (e) { decks = []; }
    try {
      const d = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null");
      if (d && d.text) { currentId = decks.some(x => x.id === d.id) ? d.id : null; $("deckName").value = d.name || ""; $("deckText").value = d.text; }
    } catch (e) {}
    renderDecks(); countLines();
  }
  start();
})();
