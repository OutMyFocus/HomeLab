// The Decks page: paste a decklist, see what you own, what's missing and what it costs.
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = v => v == null ? "–" : "$" + Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const DRAFT_KEY = "mtg-deck-draft";
  let decks = [], currentId = null, result = null, show = "all", toastT;

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
        <b>${esc(d.name)}</b><small>${d.text.split("\n").filter(l => l.trim()).length} lines · saved ${esc(d.updated)}</small></button>`).join("")
      : '<p class="none">Decks you save show up here.</p>';
    $("deleteDeck").hidden = !currentId;
  }
  $("savedDecks").onclick = e => {
    const b = e.target.closest(".deck-item"); if (!b) return;
    const d = decks.find(x => x.id === b.dataset.id);
    currentId = d.id; $("deckName").value = d.name; $("deckText").value = d.text;
    renderDecks(); countLines(); checkDeck();
  };
  $("newDeck").onclick = () => {
    currentId = null; $("deckName").value = ""; $("deckText").value = ""; $("result").hidden = true;
    renderDecks(); countLines(); $("deckText").focus();
  };
  $("saveDeck").onclick = async () => {
    if (!$("deckText").value.trim()) return toast("Paste a decklist first");
    try {
      const js = await api("/api/decks/save", { id: currentId, name: $("deckName").value, text: $("deckText").value });
      decks = js.decks; currentId = js.deck.id; $("deckName").value = js.deck.name; renderDecks();
      toast(`Saved ${js.deck.name}`);
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
    const rows = r.lines.filter(x => show === "all" || (show === "missing" ? x.missing : x.have));
    $("rRows").innerHTML = rows.length ? rows.map(x => {
      const cls = !x.found ? "unknown" : x.missing ? "short" : "ok";
      const where = x.where.map(w => `<span class="pill bin-${w.bin}" title="${esc(w.sorted_into || "")}">${esc(w.set)} #${esc(w.number)}${w.foil ? " foil" : ""} ×${w.qty}</span>`).join("");
      const img = x.image ? `<img class="thumb" src="${esc(x.image.replace("version=normal", "version=small"))}" alt="" loading="lazy">` : '<span class="thumb"></span>';
      return `<tr class="${cls}"><td class="card-cell">${img}<span><span class="nm">${esc(x.name)}</span><span class="sec">${esc(x.section)}</span></span></td>
        <td class="num">${x.need}</td><td class="num">${x.have}</td>
        <td class="hide-sm"><span class="where">${where || '<span class="sub">Not in your collection</span>'}</span></td>
        <td class="num">${x.missing ? money(x.price) : ""}</td>
        <td class="num miss">${x.missing ? `${x.missing}${x.cost != null ? " · " + money(x.cost) : ""}` : ""}</td></tr>`;
    }).join("") : `<tr class="empty-row"><td colspan="6">${show === "missing" ? "Nothing missing" : "Nothing here"}</td></tr>`;
  }
  $("showSeg").onclick = e => { const b = e.target.closest("button"); if (b && result) { show = b.dataset.v; renderResult(); } };

  function missingList() {
    const rows = (result?.lines || []).filter(x => x.missing && x.found);
    return rows.map(x => `${x.missing} ${x.name}`).join("\n") + (rows.length ? "\n" : "");
  }
  $("copyMissing").onclick = () => {
    const t = missingList(); if (!t) return toast("Nothing missing");
    copy(t).then(() => toast("Copied. Paste it into a shop's mass entry box"), () => toast("Couldn't copy"));
  };

  $("wishMissing").onclick = async () => {
    const cards = (result?.lines || []).filter(x => x.missing && x.found).map(x => ({ name: x.name }));
    if (!cards.length) return toast("Nothing missing");
    try { await api("/api/wishlist/add", { cards }); toast(`Added ${cards.length} cards to your wishlist`); }
    catch (e) { toast(e.message); }
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
