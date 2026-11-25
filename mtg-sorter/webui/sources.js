// The Collection page's Sources panel: import a ManaBox CSV as its own source, see every
// source, and remove one (with its cards) in one go. Came from Commander Vault.
(() => {
  const { $, esc, toast, api } = MTG;
  let csv = "";

  function list(sources) {
    $("sourceList").innerHTML = sources.length ? sources.map(s => `<div class="source-row">
        <span><b>${esc(s.name)}</b><small class="sub" style="display:block">${s.cards} card${s.cards === 1 ? "" : "s"}${s.added ? " · " + esc(s.added.slice(0, 10)) : ""}${s.scanned ? " · remove scans on the History page" : ""}</small></span>
        ${s.scanned ? "" : `<button class="btn ghost danger" data-src="${esc(s.name)}">Remove</button>`}</div>`).join("")
      : '<p class="sub">No cards yet.</p>';
  }
  const load = () => api("/api/sources").then(js => list(js.sources)).catch(() => { });

  $("mbFile").onchange = async () => {
    const f = $("mbFile").files[0]; csv = ""; $("mbImport").disabled = true;
    if (!f) return;
    try {
      csv = await f.text();
      const p = await api("/api/sources/manabox", { csv, preview: true });
      $("mbPreview").innerHTML = `${p.cards} cards in ${p.rows} rows, ready to import.` + (p.repeats.length ? ` <span class="warn">Check these quantities first, they may be scanner repeats: ${esc(p.repeats.join(", "))}.</span>` : "");
      if (!$("mbName").value) $("mbName").value = f.name.replace(/\.csv$/i, "");
      $("mbImport").disabled = false;
    } catch (e) { $("mbPreview").textContent = e.message; }
  };
  $("mbImport").onclick = async () => {
    if (!csv) return;
    $("mbImport").disabled = true; $("mbPreview").textContent = "Importing, and looking each card up on Scryfall…";
    try {
      const js = await api("/api/sources/manabox", { csv, name: $("mbName").value });
      toast(`Imported ${js.cards} cards as "${js.source}"`); list(js.sources);
      $("mbFile").value = ""; $("mbName").value = ""; csv = "";
      $("mbPreview").textContent = "Done. Each import is its own source, so a bad one can be removed in one step.";
      window.COLLECTION?.reload();
    } catch (e) { toast(e.message); $("mbImport").disabled = false; $("mbPreview").textContent = e.message; }
  };
  $("sourceList").onclick = async e => {
    const b = e.target.closest("[data-src]"); if (!b) return;
    if (b.dataset.sure !== "1") { b.dataset.sure = "1"; b.textContent = "Remove it and its cards?"; return; }
    try {
      const js = await api("/api/sources/remove", { name: b.dataset.src });
      toast(`Removed ${js.removed} row${js.removed === 1 ? "" : "s"}`); list(js.sources); window.COLLECTION?.reload();
    } catch (err) { toast(err.message); }
  };
  load();
})();
