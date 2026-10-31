// Small helpers shared by the newer pages (History, Wishlist, Settings, lock screen).
window.MTG = (() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = v => v == null ? "No price" : "$" + Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  let toastT;
  function toast(msg) {
    const t = $("toast"); if (!t) return;
    $("toastText").textContent = msg;
    t.hidden = true; void t.offsetWidth; t.hidden = false;
    clearTimeout(toastT); toastT = setTimeout(() => t.hidden = true, 2600);
  }
  // A locked app answers 401: go to the PIN screen, then come back here.
  function toLock() { location.href = "/lock?next=" + encodeURIComponent(location.pathname + location.search); }
  async function api(path, body) {
    const r = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const js = await r.json().catch(() => ({}));
    if (r.status === 401 && js.locked) { toLock(); throw new Error("Locked"); }
    if (!r.ok) throw new Error(js.error || `Error ${r.status}`);
    return js;
  }
  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    const t = document.createElement("textarea"); t.value = text; t.style.position = "fixed"; t.style.opacity = "0";
    document.body.append(t); t.select(); document.execCommand("copy"); t.remove();
    return Promise.resolve();
  }
  async function download(path, body) {
    const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error("Download failed");
    const name = (r.headers.get("Content-Disposition") || "").match(/filename="([^"]+)"/)?.[1] || "cards.csv";
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await r.blob()); a.download = name;
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    return name;
  }
  return { $, esc, money, toast, api, copy, download, toLock };
})();
