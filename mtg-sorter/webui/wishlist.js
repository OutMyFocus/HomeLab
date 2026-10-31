// The Wishlist page: cards you want, with the price you'd pay.
(() => {
  const { $, esc, money, toast, api, copy } = MTG;
  let data = null, show = "all", nameT;

  async function load() { try { data = await api("/api/wishlist"); render(); } catch (e) { toast(e.message); } }

  function render() {
    const items = data.items, need = items.filter(i => !i.owned);
    $("tCount").textContent = items.length;
    $("tCountSub").textContent = items.length ? `${need.length} you don't have yet` : "Add cards you're looking for";
    $("tDeals").textContent = data.deals;
    $("tOwned").textContent = data.owned;
    $("tCost").textContent = money(need.reduce((v, i) => v + (i.price || 0), 0));
    for (const b of $("showSeg").children) b.setAttribute("aria-pressed", b.dataset.v === show);
    const list = items.filter(i => show === "all" || (show === "deal" ? i.deal : show === "owned" ? i.owned : !i.owned))
      .sort((a, b) => (b.deal - a.deal) || (b.owned > 0) - (a.owned > 0) || a.display.localeCompare(b.display));
    $("wish").innerHTML = list.length ? list.map(i => `<div class="wish-card${i.deal ? " deal" : ""}" data-id="${esc(i.id)}">
        <span class="art">${i.image ? `<img src="${esc(i.image.replace("version=normal", "version=small"))}" alt="" loading="lazy">` : `<span class="noimg">${esc(i.name)}</span>`}</span>
        <div class="wish-info">
          <b>${esc(i.display)}${i.foil ? '<span class="foil-tag">foil</span>' : ""}</b>
          <span class="sub">${i.found ? `${money(i.price)} today${i.set ? " · " + esc(i.set) : ""}` : "Couldn't find this card. Check the spelling"}</span>
          ${i.deal ? '<span class="badge good">At your price!</span>' : ""}${i.owned ? `<span class="badge">You have ${i.owned}</span>` : ""}
          <label class="target">Up to $<input class="field price" type="number" min="0" step="0.5" value="${i.target ?? ""}" placeholder="any" data-target></label>
          <button class="link-btn" data-remove>Remove</button>
        </div>
      </div>`).join("") : `<p class="results-empty">${data.items.length ? "Nothing here" : "Your wishlist is empty. Add a card above, or press Add the missing cards to my wishlist on the Decks page."}</p>`;
  }

  async function addCard() {
    const name = $("wName").value.trim();
    if (!name) return $("wName").focus();
    try {
      data = await api("/api/wishlist/add", { name, target: $("wTarget").value, foil: $("wFoil").checked });
      render(); toast(`Added ${name}`); $("wName").value = ""; $("wTarget").value = ""; $("wName").focus();
    } catch (e) { toast(e.message); }
  }
  $("wAdd").onclick = addCard;
  $("wName").onkeydown = e => { if (e.key === "Enter") addCard(); };
  $("wTarget").onkeydown = e => { if (e.key === "Enter") addCard(); };
  // Suggest names from the card database while typing.
  $("wName").oninput = () => {
    clearTimeout(nameT);
    nameT = setTimeout(async () => {
      const q = $("wName").value.trim(); if (q.length < 2) return;
      const cards = await api("/api/search?q=" + encodeURIComponent(q)).catch(() => []);
      $("wNames").innerHTML = [...new Set(cards.map(c => c.name))].map(n => `<option value="${esc(n)}">`).join("");
    }, 200);
  };
  $("wish").onchange = async e => {
    if (!e.target.matches("[data-target]")) return;
    const id = e.target.closest(".wish-card").dataset.id;
    try { data = await api("/api/wishlist/update", { id, target: e.target.value }); render(); toast("Price saved"); }
    catch (err) { toast(err.message); }
  };
  $("wish").onclick = async e => {
    if (!e.target.closest("[data-remove]")) return;
    const id = e.target.closest(".wish-card").dataset.id;
    try { data = await api("/api/wishlist/remove", { id }); render(); toast("Removed"); } catch (err) { toast(err.message); }
  };
  $("showSeg").onclick = e => { const b = e.target.closest("button"); if (b && data) { show = b.dataset.v; render(); } };
  $("copyBtn").onclick = () => {
    const lines = (data?.items || []).filter(i => !i.owned && i.found).map(i => `1 ${i.display}`).join("\n");
    if (!lines) return toast("Nothing to copy");
    copy(lines + "\n").then(() => toast("Copied. Paste it into a shop's mass entry box"), () => toast("Couldn't copy"));
  };
  load();
})();
