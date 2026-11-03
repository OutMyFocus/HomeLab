// The Settings page: prices and card data, bringing in Commander Vault, scanning alerts and the PIN lock.
(() => {
  const { $, toast, api } = MTG;
  let saveT;

  // ---------- prices and card data (the weekly jobs) ----------
  let pollT;
  const when = iso => { if (!iso) return ""; const d = new Date(iso); return isNaN(d) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }); };
  async function loadVault() {
    clearTimeout(pollT);
    let st; try { st = await api("/api/vault"); } catch (e) { $("vPrices").textContent = e.message; return; }
    const p = st.prices, c = st.carddb;
    $("vPrices").textContent = p.cards ? `${p.cards.toLocaleString()} cards and ${p.printings} exact printings, ${p.checked ? "checked " + when(p.checked) : "from Commander Vault, " + p.date}` : "Not checked yet";
    $("vCards").textContent = c.cards ? `${c.cards.toLocaleString()} cards, updated ${when(c.built)}` : "Not downloaded yet";
    $("vJob").textContent = st.job ? st.message : st.error || (st.offline ? "The app was started with --offline, so it can't reach the stores or Scryfall." : "");
    $("vRunPrices").disabled = $("vRunCards").disabled = !!st.job || st.offline;
    if (st.job) pollT = setTimeout(loadVault, 3000);
  }
  async function run(job) {
    try { await api("/api/vault/run", { job }); toast(job === "prices" ? "Checking prices. It takes a while, and you can leave this page" : "Updating the card database"); }
    catch (e) { toast(e.message); }
    loadVault();
  }
  $("vRunPrices").onclick = () => run("prices");
  $("vRunCards").onclick = () => run("carddb");
  let vaultData = null;
  $("vFile").onchange = async () => {
    vaultData = null; $("vImport").disabled = true; const f = $("vFile").files[0]; if (!f) return;
    try {
      vaultData = JSON.parse(await f.text());
      const n = (vaultData.collection || []).reduce((s, b) => s + (b.cards || []).reduce((t, c) => t + (c.q || 1), 0), 0);
      $("vImported").textContent = `${(vaultData.collection || []).length} sources (${n} cards), ${(vaultData.decks || []).length} decks, ready to import.`;
      $("vImport").disabled = false;
    } catch (e) { $("vImported").textContent = "That file isn't a Commander Vault export."; }
  };
  $("vImport").onclick = async () => {
    if (!vaultData) return;
    $("vImport").disabled = true; $("vImported").textContent = "Importing, and looking each card up on Scryfall. This takes a few seconds…";
    try {
      const { imported: d } = await api("/api/vault/import", vaultData);
      const parts = [d.sources && `${d.sources} sources (${d.cards} cards)`, d.decks && `${d.decks} decks`, d.wishlist && `${d.wishlist} wishlist cards`,
        d.trade && `${d.trade} trade binder cards`, d.games && `${d.games} games`, d.prices && `prices for ${d.prices} cards`].filter(Boolean);
      $("vImported").innerHTML = parts.length ? `Brought in ${parts.join(", ")}. Have a look at your <a href="/collection">Collection</a> and <a href="/decks">Decks</a>.` : "Nothing new: everything in that file is already here.";
      loadVault();
    } catch (e) { $("vImported").textContent = e.message; $("vImport").disabled = false; }
  };
  loadVault();

  async function loadAlerts() {
    const a = await api("/api/alerts");
    $("aBig").value = a.big_card ?? ""; $("aWish").checked = a.wishlist; $("aSound").checked = a.sound;
  }
  function saveAlerts() {
    clearTimeout(saveT);
    saveT = setTimeout(async () => {
      try {
        await api("/api/alerts", { big_card: $("aBig").value, wishlist: $("aWish").checked, sound: $("aSound").checked });
        $("aSaved").textContent = "Saved";
      } catch (e) { $("aSaved").textContent = e.message; }
    }, 400);
  }
  for (const id of ["aBig", "aWish", "aSound"]) $(id).addEventListener("input", saveAlerts);
  $("aTest").onclick = () => {
    if ($("aSound").checked) window.mtgChime?.("big");
    toast($("aBig").value ? `Valuable card! This is how a card over $${$("aBig").value} is announced` : "Set a price first");
  };

  async function loadPin() {
    const s = await api("/api/lock");
    $("pinState").innerHTML = s.enabled ? "<b>The PIN lock is on.</b>" : "The PIN lock is off: anyone who can reach the Pi can use the app.";
    $("pinSet").textContent = s.enabled ? "Change PIN" : "Set PIN";
    $("pinOn").hidden = !s.enabled;
  }
  $("pinSet").onclick = async () => {
    const a = $("pin1").value.trim(), b = $("pin2").value.trim();
    if (!/^\d{4,8}$/.test(a)) return toast("The PIN has to be 4 to 8 digits");
    if (a !== b) return toast("The two PINs don't match");
    try { await api("/api/lock/set", { pin: a }); $("pin1").value = $("pin2").value = ""; toast("PIN set. Other devices will be asked for it"); loadPin(); }
    catch (e) { toast(e.message); }
  };
  $("pinRemove").onclick = async () => {
    if (!confirm("Turn the PIN off? Anyone on your network will be able to use the app.")) return;
    try { await api("/api/lock/remove", {}); toast("PIN turned off"); loadPin(); } catch (e) { toast(e.message); }
  };
  $("pinLock").onclick = async () => { await api("/api/lock/now", {}); location.href = "/lock"; };

  loadAlerts().catch(e => toast(e.message));
  loadPin().catch(e => toast(e.message));
})();
