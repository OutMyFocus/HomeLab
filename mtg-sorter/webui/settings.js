// The Settings page: scanning alerts and the PIN lock.
(() => {
  const { $, toast, api } = MTG;
  let saveT;

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
