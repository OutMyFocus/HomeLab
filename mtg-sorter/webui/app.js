// MTG Scanner page: polls the scanner's state and renders it.
(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = v => v == null ? "No price" : "$" + v.toFixed(2);
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
    $("emptyText").textContent = s.status === "unknown" ? "Not recognized. Straighten the card, or look it up:" : "Put a card under the camera";
    if (c) {
      if (shownId !== c.id) { $("cardImg").src = c.image; $("cardImg").alt = c.name; shownId = c.id; }
      $("cardName").textContent = c.name;
      $("cardSet").textContent = `${c.set_name} · ${c.set} #${c.number} · ${c.rarity}${c.foil ? " · foil" : ""}`;
      $("cardPrice").textContent = money(c.price);
      $("cardSource").textContent = c.price_source ? c.price_source : "";
      const b = $("cardBin"); b.textContent = `Bin ${c.bin} · ${c.bin_label}`; b.className = "bin bin-" + c.bin;
      const m = $("cardMatch");
      if (s.picked) { m.textContent = "Printing picked by you"; m.className = "match good"; }
      else { m.textContent = c.match === "good" ? "Good match" : "Fair match: check the set"; m.className = "match " + c.match; }
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
        <td><span class="pill bin-${r.bin}">${r.bin} · ${esc(r.bin_label)}</span></td>
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
  $("printBtn").onclick = () => state.card && openPicker(state.card.name, state.card.id, state.foil,
    id => api("/api/choose", { id }).then(s => { render(s); toast(s.saved ? "Saved row switched to this printing" : "Printing changed"); }));
  $("findBtn").onclick = () => openPicker("", null, state?.foil, id => api("/api/choose", { id }).then(render));
  $("stream").onerror = () => { $("camStatus").textContent = "Camera stream lost. Reload the page"; };

  document.addEventListener("keydown", e => {
    if (e.target.matches("input, textarea") || e.metaKey || e.ctrlKey || $("tab-live").hidden || $("picker").open) return;
    if (e.code === "Space") { e.preventDefault(); saveCurrent(); }
    else if (e.key === "f" || e.key === "F") setting("foil");
    else if (e.key === "a" || e.key === "A") setting("auto");
  });

  // ---------- printing picker ----------
  // Lists every printing of a card name so you can pick the one in your hand (reprints
  // often share the same art, so the camera can't always tell them apart).
  let pick = null, searchT;
  function openPicker(name, currentId, foil, onPick) {
    pick = { currentId, foil: !!foil, onPick };
    $("pickerName").value = name; $("printings").innerHTML = "";
    $("picker").showModal();
    if (name) loadPrintings(name); else $("pickerName").focus();
  }

  async function loadPrintings(name) {
    $("printings").innerHTML = '<li class="empty">Looking up printings…</li>';
    const list = await api(`/api/printings?name=${encodeURIComponent(name)}&foil=${pick.foil ? 1 : 0}`);
    $("printings").innerHTML = list.length ? list.map(c => `<li><button data-id="${esc(c.id)}" class="${c.id === pick.currentId ? "current" : ""}">
        <span class="p-set">${esc(c.set_name)}</span><span class="p-price">${money(c.price)}</span>
        <span class="p-num">${esc(c.set)} #${esc(c.number)} · ${esc(c.rarity)}${c.id === pick.currentId ? " · current" : ""}</span>
        <span class="pill bin-${c.bin}">Bin ${c.bin}</span></button></li>`).join("")
      : '<li class="empty">No printings found. Check the spelling.</li>';
  }

  $("pickerName").addEventListener("input", e => {
    clearTimeout(searchT);
    const q = e.target.value.trim();
    searchT = setTimeout(async () => {
      const names = q.length < 2 ? [] : await api(`/api/search?q=${encodeURIComponent(q)}`);
      $("pickerNames").innerHTML = names.map(n => `<option value="${esc(n)}">`).join("");
    }, 250);
  });
  $("pickerName").addEventListener("change", e => e.target.value.trim() && loadPrintings(e.target.value.trim()));
  $("printings").addEventListener("click", async e => {
    const b = e.target.closest("[data-id]"); if (!b || !pick) return;
    $("picker").close();
    await pick.onPick(b.dataset.id);
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
        ${p.added ? "" : `<button class="link" data-print="${i}">Wrong printing?</button>`}
        <div class="row"><b>${money(p.card.price)}</b><span class="pill bin-${p.card.bin}">Bin ${p.card.bin}</span></div>
        <div class="row"><label><input type="checkbox" data-foil="${i}" ${p.foil ? "checked" : ""} ${p.added ? "disabled" : ""}> Foil</label>
          <button class="btn ${p.added ? "saved" : ""}" data-add="${i}" ${p.added ? "disabled" : ""}>${p.added ? "Added ✓" : "Add"}</button></div>
      </div>` : `<div class="panel photo">
        <img src="${esc(p.preview || "")}" alt="">
        <div class="name">${esc(p.file)}</div><div class="err">${esc(p.error)}</div>
        ${p.error === "Card not recognized" ? `<button class="link" data-print="${i}">Find it by name</button>` : ""}
      </div>`).join("");
  }

  async function addPhoto(i) {
    const p = photoResults[i]; if (!p || p.added) return;
    render(await api("/api/add", { id: p.card.id, foil: p.foil }));
    p.added = true;
  }

  // Re-price a photo's card after changing its foil box or printing.
  async function setPhotoCard(i, id) {
    const p = photoResults[i];
    p.card = await api(`/api/card?id=${encodeURIComponent(id)}&foil=${p.foil ? 1 : 0}`);
    delete p.error;
    renderPhotos();
  }

  $("photoGrid").addEventListener("click", async e => {
    const pb = e.target.closest("[data-print]");
    if (pb) {
      const i = +pb.dataset.print, p = photoResults[i];
      openPicker(p.card?.name || "", p.card?.id, p.foil, id => setPhotoCard(i, id));
      return;
    }
    const b = e.target.closest("[data-add]"); if (!b) return;
    await addPhoto(+b.dataset.add); renderPhotos(); toast("Added to collection");
  });
  $("photoGrid").addEventListener("change", e => {
    const c = e.target.closest("[data-foil]"); if (!c) return;
    const i = +c.dataset.foil; photoResults[i].foil = c.checked;
    setPhotoCard(i, photoResults[i].card.id);
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
