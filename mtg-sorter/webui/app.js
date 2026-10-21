// MTG Scanner page: polls the scanner's state and renders it.
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = v => v == null ? "No price" : "$" + v.toFixed(2);
  const BIN_NAMES = { 0: "Unknown", 1: "Bulk", 2: "$1–10", 3: "$10+" };
  let state = null, shownId = null, toastT;

  function toast(msg) {
    const t = $("toast"); t.textContent = msg; t.hidden = false;
    clearTimeout(toastT); toastT = setTimeout(() => t.hidden = true, 2200);
  }

  async function api(path, body) {
    const r = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }

  // ---------- live ----------
  const STATUS = { starting: "Starting camera…", looking: "Looking for a card", recognizing: "Recognizing…", locked: "Card recognized", unknown: "Not recognized. Try straightening the card" };

  function render(s) {
    state = s;
    $("meta").textContent = `${s.db_count.toLocaleString()} cards in database · ${s.prices}`;
    const st = $("camStatus"); st.textContent = STATUS[s.status] || s.status; st.className = "camera-status " + s.status;

    const c = s.card;
    $("emptyCard").hidden = !!c; $("cardView").hidden = !c;
    if (c) {
      if (shownId !== c.id) { $("cardImg").src = c.image; $("cardImg").alt = c.name; shownId = c.id; }
      $("cardName").textContent = c.name;
      $("cardSet").textContent = `${c.set_name} · ${c.set} #${c.number} · ${c.rarity}${c.foil ? " · foil" : ""}`;
      $("cardPrice").textContent = money(c.price);
      $("cardSource").textContent = c.price_source ? c.price_source : "";
      const b = $("cardBin"); b.textContent = `Bin ${c.bin} · ${c.bin_label}`; b.className = "bin bin-" + c.bin;
      const m = $("cardMatch"); m.textContent = c.match === "good" ? "Good match" : "Fair match: check the set"; m.className = "match " + c.match;
    } else shownId = null;

    const save = $("saveBtn");
    save.disabled = !c || s.saved;
    save.classList.toggle("saved", !!(c && s.saved));
    save.innerHTML = c && s.saved ? "Saved ✓" : "Save card <kbd>Space</kbd>";
    $("foilBtn").setAttribute("aria-pressed", s.foil);
    $("autoBtn").setAttribute("aria-pressed", s.auto);

    const t = s.totals;
    const chips = [`<span class="chip"><b>${t.count}</b> cards</span>`, `<span class="chip"><b>${money(t.value)}</b></span>`];
    for (const [bin, n] of Object.entries(t.bins).sort((a, b) => b[0] - a[0])) chips.push(`<span class="chip">Bin ${bin}: <b>${n}</b></span>`);
    $("totals").innerHTML = chips.join("");
    $("sessionRows").innerHTML = s.session.length ? s.session.map(r => `<tr>
        <td>${esc(r.name)}${r.foil ? '<span class="foil-tag">foil</span>' : ""}</td>
        <td>${esc(r.set)} #${esc(r.number)}</td>
        <td class="num">${money(r.price)}</td>
        <td><span class="pill bin-${r.bin}">${r.bin} · ${esc(BIN_NAMES[r.bin] || r.bin_label)}</span></td>
        <td class="num">${esc(r.time)}</td></tr>`).join("")
      : '<tr class="empty-row"><td colspan="5">No cards saved yet</td></tr>';
    $("undoBtn").disabled = !s.session.length;
  }

  async function poll() {
    try { render(await api("/api/state")); }
    catch (e) { $("meta").textContent = "Can't reach the scanner. Is app.py still running?"; }
    setTimeout(poll, 400);
  }

  async function saveCurrent() {
    if (!state || !state.card || state.saved) return;
    render(await api("/api/add", { id: state.card.id, foil: state.foil }));
    toast(`Saved ${state.session[0].name}`);
  }
  const setting = (key) => api("/api/settings", { [key]: !state[key] }).then(render);

  $("saveBtn").onclick = saveCurrent;
  $("foilBtn").onclick = () => setting("foil");
  $("autoBtn").onclick = () => setting("auto");
  $("undoBtn").onclick = async () => { const name = state.session[0]?.name; render(await api("/api/undo", {})); if (name) toast(`Removed ${name}`); };
  $("stream").onerror = () => { $("camStatus").textContent = "Camera stream lost. Reload the page"; };

  document.addEventListener("keydown", e => {
    if (e.target.matches("input, textarea") || e.metaKey || e.ctrlKey || $("tab-live").hidden) return;
    if (e.code === "Space") { e.preventDefault(); saveCurrent(); }
    else if (e.key === "f" || e.key === "F") setting("foil");
    else if (e.key === "a" || e.key === "A") setting("auto");
  });

  // ---------- tabs ----------
  for (const b of document.querySelectorAll(".tabs button")) b.onclick = () => {
    for (const x of document.querySelectorAll(".tabs button")) x.setAttribute("aria-selected", x === b);
    for (const s of document.querySelectorAll(".tab")) s.hidden = s.id !== "tab-" + b.dataset.tab;
  };

  // ---------- photos ----------
  let photoResults = [];
  async function scanPhotos(files) {
    if (!files.length) return;
    $("photoBar").hidden = false; $("photoSummary").textContent = `Scanning ${files.length} photo${files.length > 1 ? "s" : ""}…`;
    $("addAllBtn").disabled = true;
    const fd = new FormData(); for (const f of files) fd.append("photos", f);
    const urls = new Map([...files].map(f => [f.name, URL.createObjectURL(f)]));
    const r = await fetch("/api/photos", { method: "POST", body: fd });
    const results = (await r.json()).map(x => ({ ...x, preview: urls.get(x.file), added: false, foil: false }));
    photoResults = [...results, ...photoResults];
    renderPhotos();
  }

  function renderPhotos() {
    const found = photoResults.filter(p => p.card);
    const waiting = found.filter(p => !p.added);
    $("photoSummary").textContent = `${found.length} of ${photoResults.length} recognized` + (waiting.length < found.length ? ` · ${found.length - waiting.length} added` : "");
    $("addAllBtn").disabled = !waiting.length;
    $("photoGrid").innerHTML = photoResults.map((p, i) => p.card ? `<div class="panel photo">
        <img src="${esc(p.card.image)}" alt="${esc(p.card.name)}" loading="lazy">
        <div class="name">${esc(p.card.name)}</div>
        <div class="sub">${esc(p.card.set)} #${esc(p.card.number)}${p.card.match === "fair" ? " · check the set" : ""}</div>
        <div class="row"><b>${money(p.card.price)}</b><span class="pill bin-${p.card.bin}">Bin ${p.card.bin}</span></div>
        <div class="row"><label><input type="checkbox" data-foil="${i}" ${p.foil ? "checked" : ""} ${p.added ? "disabled" : ""}> Foil</label>
          <button class="btn ${p.added ? "saved" : ""}" data-add="${i}" ${p.added ? "disabled" : ""}>${p.added ? "Added ✓" : "Add"}</button></div>
      </div>` : `<div class="panel photo">
        <img src="${esc(p.preview || "")}" alt="">
        <div class="name">${esc(p.file)}</div><div class="err">${esc(p.error)}</div>
      </div>`).join("");
  }

  async function addPhoto(i) {
    const p = photoResults[i]; if (!p || p.added) return;
    render(await api("/api/add", { id: p.card.id, foil: p.foil }));
    p.added = true;
  }

  $("photoGrid").addEventListener("click", async e => {
    const b = e.target.closest("[data-add]"); if (!b) return;
    await addPhoto(+b.dataset.add); renderPhotos(); toast("Added to collection");
  });
  $("photoGrid").addEventListener("change", e => {
    const c = e.target.closest("[data-foil]"); if (c) photoResults[+c.dataset.foil].foil = c.checked;
  });
  $("addAllBtn").onclick = async () => {
    let n = 0; for (let i = 0; i < photoResults.length; i++) if (photoResults[i].card && !photoResults[i].added) { await addPhoto(i); n++; }
    renderPhotos(); toast(`Added ${n} card${n === 1 ? "" : "s"}`);
  };
  $("photoInput").onchange = e => { scanPhotos(e.target.files); e.target.value = ""; };
  const drop = $("drop");
  drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", e => { e.preventDefault(); drop.classList.remove("over"); scanPhotos(e.dataTransfer.files); });

  poll();
})();
