// The Bins page: rules for which bin each card goes into, with a live preview.
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

  // ---------- the four bins ----------
  function renderBins() {
    const p = info.preview, total = Math.max(1, Object.values(p).reduce((n, b) => n + b.cards, 0));
    const box = $("binCards");
    if (box.children.length) {   // update in place, so typing a bin's name isn't interrupted
      for (const b of info.bins) {
        const card = box.querySelector(`[data-name="${b}"]`).closest(".bin-card"), v = p[b];
        card.querySelector(".count").innerHTML = `${v.cards.toLocaleString()} <span class="sub">cards · ${money(v.value)}</span>`;
        card.querySelector(".share span").style.width = (100 * v.cards / total).toFixed(1) + "%";
        card.querySelector(".ex").textContent = v.examples.length ? "Like " + v.examples.join(", ") : "Nothing from your collection";
        const input = card.querySelector("input");
        if (input !== document.activeElement) input.value = draft.names[b];
      }
      return;
    }
    box.innerHTML =info.bins.map(b => {
      const v = p[b] || { cards: 0, value: 0, examples: [] };
      return `<div class="panel bin-card" style="--c: var(--bin${b})">
        <div class="head"><span class="pill bin-${b}">Bin ${b}</span><input class="field" data-name="${b}" value="${esc(draft.names[b])}" maxlength="40" aria-label="Name of bin ${b}"></div>
        <div class="count">${v.cards.toLocaleString()} <span class="sub">cards · ${money(v.value)}</span></div>
        <div class="share"><span style="width:${(100 * v.cards / total).toFixed(1)}%"></span></div>
        <div class="ex">${v.examples.length ? "Like " + v.examples.map(esc).join(", ") : "Nothing from your collection"}</div>
      </div>`;
    }).join("");
  }
  $("binCards").oninput = e => { const i = e.target.closest("[data-name]"); if (i) { draft.names[i.dataset.name] = i.value; changed(false); } };

  // ---------- rules ----------
  const binOptions = sel => info.bins.map(b => `<option value="${b}"${b === sel ? " selected" : ""}>Bin ${b} · ${esc(draft.names[b])}</option>`).join("");
  function renderRules() {
    $("rules").innerHTML = draft.rules.length ? draft.rules.map((r, i) => `<div class="rule" data-i="${i}">
      <span class="no">${i + 1}</span>
      <div class="conds">
        <span class="cond"><span>Price</span> $<input class="field price" data-k="min_price" type="number" min="0" step="0.5" placeholder="any" value="${r.min_price ?? ""}" aria-label="At least">
          <span>up to</span> $<input class="field price" data-k="max_price" type="number" min="0" step="0.5" placeholder="any" value="${r.max_price ?? ""}" aria-label="Under"></span>
        <span class="cond"><span>Color</span>${info.colors.map(c => `<button class="chip" data-list="colors" data-v="${c}" aria-pressed="${r.colors.includes(c)}" title="${COLOR_NAMES[c]}"><i style="background:var(--mana-${c})"></i>${COLOR_NAMES[c]}</button>`).join("")}</span>
        <span class="cond"><span>Rarity</span>${info.rarities.map(x => `<button class="chip" data-list="rarities" data-v="${x}" aria-pressed="${r.rarities.includes(x)}">${x[0].toUpperCase() + x.slice(1)}</button>`).join("")}</span>
        <span class="cond"><span>Sets</span><input class="field sets" data-k="sets" placeholder="any set" title="Set codes, like DMU, ONE" value="${esc(r.sets.join(", "))}" aria-label="Set codes"></span>
        <span class="cond"><span>Foil</span><select class="field" data-k="foil">
          <option value="any"${r.foil === "any" ? " selected" : ""}>Foil or not</option><option value="foil"${r.foil === "foil" ? " selected" : ""}>Foil only</option><option value="normal"${r.foil === "normal" ? " selected" : ""}>Not foil</option></select></span>
      </div>
      <div class="goto">→ <select class="field" data-k="bin">${binOptions(r.bin)}</select>
        <span class="tools">
          <button class="icon-btn" data-move="-1" aria-label="Move up"${i ? "" : " disabled"}><svg><use href="#i-up"/></svg></button>
          <button class="icon-btn" data-move="1" aria-label="Move down"${i < draft.rules.length - 1 ? "" : " disabled"}><svg><use href="#i-down"/></svg></button>
          <button class="icon-btn" data-del aria-label="Delete rule"><svg><use href="#i-trash"/></svg></button>
        </span></div>
    </div>`).join("") : '<p class="sub">No rules: every card goes to the "anything else" bin.</p>';
    $("fallback").innerHTML = binOptions(draft.fallback);
  }
  const ruleOf = el => draft.rules[+el.closest(".rule").dataset.i];
  $("rules").oninput = e => {
    const k = e.target.dataset.k; if (!k) return;
    const r = ruleOf(e.target);
    if (k === "sets") r.sets = e.target.value.split(/[\s,]+/).map(s => s.trim().toUpperCase()).filter(Boolean);
    else if (k === "bin") r.bin = +e.target.value;
    else if (k === "foil") r.foil = e.target.value;
    else r[k] = e.target.value === "" ? null : +e.target.value;
    changed(false);
  };
  $("rules").onclick = e => {
    const chip = e.target.closest(".chip"), move = e.target.closest("[data-move]"), del = e.target.closest("[data-del]");
    if (!chip && !move && !del) return;
    const i = +e.target.closest(".rule").dataset.i, r = draft.rules[i];
    if (chip) {
      const list = r[chip.dataset.list], v = chip.dataset.v;
      r[chip.dataset.list] = list.includes(v) ? list.filter(x => x !== v) : [...list, v];
    } else if (move) {
      const j = i + +move.dataset.move;
      [draft.rules[i], draft.rules[j]] = [draft.rules[j], draft.rules[i]];
    } else draft.rules.splice(i, 1);
    changed(true);
  };
  $("addRule").onclick = () => {
    draft.rules.push({ bin: 1, min_price: null, max_price: null, colors: [], rarities: [], sets: [], foil: "any" });
    changed(true);
  };
  $("fallback").onchange = () => { draft.fallback = +$("fallback").value; changed(false); };

  // ---------- wanted cards (checked before the rules) ----------
  const realBins = () => info.bins.filter(b => b !== 0);
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
    $("resetBtn").hidden = !info.custom;
    $("saveNote").className = "sub";
    $("saveNote").textContent = d ? "Not saved yet. The counts above show what would happen." : info.custom ? "These are your saved rules." : "Using the original price bins from config.py.";
  }
  function render() {
    renderPresets(); renderBins(); renderWanted();
    // Don't rebuild the rule rows while someone is typing in them (it would lose the cursor).
    if (!$("rules").contains(document.activeElement)) renderRules();
    else $("fallback").innerHTML = binOptions(draft.fallback);
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
