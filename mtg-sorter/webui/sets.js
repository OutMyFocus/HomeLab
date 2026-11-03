// The Sets page: how complete each set is, and the spare copies you could trade.
(() => {
  const { $, esc, money, api, toast, copy } = window.MTG;
  const small = url => url ? url.replace("version=normal", "version=small") : "";
  const plural = (n, w) => `${n.toLocaleString()} ${w}${n === 1 ? "" : "s"}`;
  const RARITIES = ["mythic", "rare", "uncommon", "common", "special", "bonus", "unknown"];
  let sets = [], detail = null, show = "missing", spareData = null;

  // ---------- which view ----------
  function setView(v) {
    for (const b of $("viewSeg").children) b.setAttribute("aria-pressed", b.dataset.v === v);
    $("viewSets").hidden = v !== "sets"; $("viewSpares").hidden = v !== "spares";
    $("barNote").hidden = v !== "sets";
    if (v === "spares" && !spareData) loadSpares();
    updateHash();
  }
  $("viewSeg").onclick = e => { const b = e.target.closest("button"); if (b) setView(b.dataset.v); };
  function updateHash() {
    const h = !$("viewSpares").hidden ? "#spares" : detail ? "#" + detail.set : "";
    history.replaceState(null, "", location.pathname + h);
  }

  // ---------- all sets ----------
  const ring = (pct, size = 54) => {
    const r = size / 2 - 5, c = 2 * Math.PI * r;
    return `<svg viewBox="0 0 ${size} ${size}" style="width:${size}px;height:${size}px" aria-hidden="true"><circle cx="${size / 2}" cy="${size / 2}" r="${r}" class="ring-bg"/>
      <circle cx="${size / 2}" cy="${size / 2}" r="${r}" class="ring-fg" stroke-dasharray="${(c * pct / 100).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 ${size / 2} ${size / 2})"/>
      <text x="50%" y="50%" text-anchor="middle" dominant-baseline="central">${Math.floor(pct)}%</text></svg>`;
  };
  function renderSets() {
    const q = $("setQ").value.trim().toLowerCase(), started = $("startedOnly").checked;
    const list = sets.filter(s => (!started || s.owned) && (!q || `${s.name} ${s.set}`.toLowerCase().includes(q)));
    const begun = sets.filter(s => s.owned).length;
    $("barNote").textContent = sets.length ? `${plural(begun, "set")} started of ${sets.length.toLocaleString()} in the card database` : "";
    $("setGrid").innerHTML = list.length ? list.map(s => `<button class="panel set-card${s.percent >= 100 ? " done" : ""}" data-set="${esc(s.set)}">
        ${ring(s.percent)}<span class="info"><b>${esc(s.name)}</b><small>${esc(s.set)} · ${s.owned} of ${s.total}${s.copies > s.owned ? ` · ${s.copies} copies` : ""}</small>
        <span class="bar"><i style="width:${s.percent}%"></i></span></span></button>`).join("")
      : `<p class="results-empty">${sets.length ? (started && !q ? "No set started yet. Scan some cards, or turn off <b>Only sets I've started</b>." : "No set matches that.") : "The card database is empty."}</p>`;
  }
  $("setQ").oninput = renderSets;
  $("startedOnly").onchange = renderSets;
  $("setGrid").onclick = e => { const b = e.target.closest("[data-set]"); if (b) openSet(b.dataset.set); };

  // ---------- one set ----------
  async function openSet(code) {
    try { detail = await api("/api/sets/" + encodeURIComponent(code)); }
    catch (e) { toast(e.message); return; }
    $("setGrid").hidden = true; document.querySelector(".sets-tools").hidden = true; $("setDetail").hidden = false;
    renderDetail(); updateHash(); scrollTo({ top: 0 });
  }
  function closeSet() {
    detail = null; $("setDetail").hidden = true; $("setGrid").hidden = false; document.querySelector(".sets-tools").hidden = false;
    updateHash();
  }
  $("backBtn").onclick = closeSet;
  function renderDetail() {
    const d = detail, pct = d.total ? 100 * d.owned / d.total : 0, missing = d.total - d.owned;
    $("dName").textContent = d.name;
    $("dSub").textContent = `${d.set} · you have ${d.owned} of ${d.total}` + (missing ? `. The ${plural(missing, "missing card")} cost about ${money(d.missing_value)} today.` : ". Complete!");
    $("dRing").innerHTML = ring(pct, 76);
    $("dRarity").innerHTML = RARITIES.filter(r => d.by_rarity[r]).map(r => {
      const x = d.by_rarity[r];
      return `<span class="rar r-${r}"><b>${r[0].toUpperCase() + r.slice(1)}</b> ${x.owned}/${x.total}</span>`;
    }).join("");
    for (const b of $("showSeg").children) b.setAttribute("aria-pressed", b.dataset.v === show);
    const cards = d.cards.filter(c => show === "all" || (show === "owned" ? c.qty : !c.qty));
    $("wishBtn").disabled = $("copyBtn").disabled = !missing;
    $("dCards").innerHTML = cards.length ? cards.map(c => `<a class="tile${c.qty ? "" : " missing"}" href="https://scryfall.com/card/${esc(d.set.toLowerCase())}/${esc(c.number)}" target="_blank" rel="noopener" title="${esc(c.name)} on Scryfall">
        <div class="art"><img src="${esc(small(c.image))}" alt="" loading="lazy">${c.qty ? `<span class="qty">×${c.qty}</span>` : ""}${c.foil ? '<span class="foil-badge">FOIL</span>' : ""}</div>
        <b>${esc(c.name)}</b><span>#${esc(c.number)} · ${esc(c.rarity)}<em>${money(c.price)}</em></span></a>`).join("")
      : `<p class="results-empty">${show === "missing" ? "Nothing missing. This set is complete!" : "You don't have any of this set yet."}</p>`;
  }
  $("showSeg").onclick = e => { const b = e.target.closest("button"); if (b) { show = b.dataset.v; renderDetail(); } };
  const missingCards = () => detail.cards.filter(c => !c.qty);
  $("copyBtn").onclick = async () => {
    const lines = missingCards().map(c => `1 ${c.name} (${detail.set}) ${c.number}`);
    await copy(lines.join("\n")); toast(`Copied ${plural(lines.length, "card")}`);
  };
  $("wishBtn").onclick = async () => {
    const names = [...new Set(missingCards().map(c => c.name))];
    if (names.length > 40 && !confirm(`Add ${names.length} cards to your wishlist?`)) return;
    try { await api("/api/wishlist/add", { cards: names.map(name => ({ name })) }); toast(`Added ${plural(names.length, "card")} to your wishlist`); }
    catch (e) { toast(e.message); }
  };

  // ---------- spare copies ----------
  let keep = 4;
  try { keep = +(localStorage.getItem("mtg-sets-keep") ?? 4); } catch (e) {}
  $("keepN").value = keep;
  async function loadSpares() {
    try { spareData = await api(`/api/spares?keep=${keep}&lands=${$("lands").checked ? 1 : 0}`); }
    catch (e) { toast(e.message); return; }
    renderSpares();
  }
  function renderSpares() {
    const s = spareData;
    for (const b of document.querySelectorAll("[data-keep]")) b.setAttribute("aria-pressed", +b.dataset.keep === keep);
    $("sCards").textContent = s.cards.toLocaleString();
    $("sCardsSub").textContent = s.spares.length ? `of ${plural(s.spares.length, "different card")}` : "";
    $("sValue").textContent = money(s.value);
    $("copySpares").disabled = !s.spares.length;
    $("spareList").innerHTML = s.spares.length ? s.spares.map(x => `<div class="spare">
        <span class="thumb">${x.printings[0]?.image ? `<img src="${esc(small(x.printings[0].image))}" alt="" loading="lazy">` : ""}</span>
        <span class="info"><b>${esc(x.name)}</b><small>You have ${x.have}. Spare: ${x.printings.map(p => `${p.spare}× ${esc(p.set)} #${esc(p.number)}${p.foil ? " foil" : ""}`).join(", ")}</small></span>
        <span class="n">${x.spare}</span><b class="amt">${money(x.value)}</b></div>`).join("")
      : `<p class="results-empty">No spares: you have ${keep ? `${keep} or fewer` : "none"} of every card${$("lands").checked ? "" : " (basic lands aside)"}.</p>`;
  }
  function setKeep(n) {
    keep = Math.max(0, Math.min(99, n | 0)); $("keepN").value = keep;
    try { localStorage.setItem("mtg-sets-keep", keep); } catch (e) {}
    loadSpares();
  }
  document.querySelectorAll("[data-keep]").forEach(b => b.onclick = () => setKeep(+b.dataset.keep));
  $("keepN").onchange = () => setKeep(+$("keepN").value);
  $("lands").onchange = loadSpares;
  $("copySpares").onclick = async () => {
    const lines = spareData.spares.flatMap(x => x.printings.map(p => `${p.spare} ${x.name} (${p.set}) ${p.number}${p.foil ? " *F*" : ""}`));
    await copy(lines.join("\n")); toast(`Copied ${plural(lines.length, "line")}`);
  };

  // ---------- start ----------
  (async () => {
    try { sets = (await api("/api/sets")).sets; } catch (e) { if (e.message !== "Locked") toast(e.message); return; }
    if (!sets.some(s => s.owned)) $("startedOnly").checked = false;
    renderSets();
    fromHash();
    addEventListener("hashchange", fromHash);
  })();
  // /sets#spares opens the spares, /sets#DMU opens that set.
  function fromHash() {
    const h = location.hash.slice(1);
    if (h === "spares") return setView("spares");
    setView("sets");
    if (h && sets.some(s => s.set === h.toUpperCase())) { if (detail?.set !== h.toUpperCase()) openSet(h); }
    else if (detail) closeSet();
  }
})();
