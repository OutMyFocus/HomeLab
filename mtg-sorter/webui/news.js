// The News page: Magic news from Wizards and community sites, sets coming out,
// the newest previewed cards and ban list changes. The server does the fetching.
(() => {
  const { $, esc, api, toast } = window.MTG;
  const PAGE = 30;
  let data = null, tag = "all", shown = PAGE, setView = "upcoming", previewSet = "";

  // Articles newer than your last visit get a "New" tag (remembered in this browser).
  const VISIT = "mtg-news-last-visit";
  let lastVisit = 0;
  try { lastVisit = Number(localStorage.getItem(VISIT)) || 0; } catch (e) {}
  const markVisit = () => { try { localStorage.setItem(VISIT, String(Date.now() / 1000)); } catch (e) {} };
  addEventListener("pagehide", markVisit);
  document.addEventListener("visibilitychange", () => { if (document.hidden) markVisit(); });

  // ---------- dates ----------
  const when = a => a.published || a.seen || 0;
  function ago(ts) {
    if (!ts) return "";
    const s = Date.now() / 1000 - ts;
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.floor(s / 60)} min ago`;
    if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
    if (s < 2 * 86400) return "yesterday";
    if (s < 7 * 86400) return `${Math.floor(s / 86400)} days ago`;
    const d = new Date(ts * 1000);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: d.getFullYear() === new Date().getFullYear() ? undefined : "numeric" });
  }
  const day = iso => new Date(iso + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  function countdown(days) {
    if (days === 0) return "Out today";
    if (days > 0) return days === 1 ? "Tomorrow" : days < 60 ? `In ${days} days` : `In ${Math.round(days / 30)} months`;
    const d = -days;
    return d === 1 ? "Out yesterday" : `Out ${d} days ago`;
  }
  const TYPES = { expansion: "Expansion", core: "Core set", masters: "Masters", draft_innovation: "Draft set", commander: "Commander", funny: "Un-set",
    starter: "Starter", duel_deck: "Duel decks", from_the_vault: "From the Vault", spellbook: "Spellbook", premium_deck: "Premium deck",
    arsenal: "Arsenal", planechase: "Planechase", archenemy: "Archenemy", eternal: "Eternal" };

  // ---------- load ----------
  async function load(refresh) {
    $("refreshBtn").classList.add("spin"); $("refreshBtn").disabled = true;
    try {
      data = await api("/api/news" + (refresh ? "?refresh=1" : ""));
      render();
      if (refresh) {
        const bad = data.sources.filter(s => s.on && s.error);
        toast(bad.length ? `Updated. ${bad.map(s => s.name).join(", ")} didn't answer` : "News updated");
      }
      // The server fetches old sources in the background: look again shortly.
      if (data.refreshing && !refresh) setTimeout(() => quiet(), 6000);
    } catch (e) {
      $("updated").textContent = "Couldn't load the news: " + e.message;
    } finally {
      $("refreshBtn").classList.remove("spin"); $("refreshBtn").disabled = false;
    }
  }
  async function quiet() {
    try { data = await api("/api/news"); render(); } catch (e) {}
  }
  $("refreshBtn").onclick = () => load(true);

  function render() {
    const d = data;
    const parts = [];
    if (d.updated) parts.push(`Updated ${ago(d.updated)}`);
    if (!d.online) parts.push("the sorter is running offline, so this is the last news it saved");
    const down = d.sources.filter(s => s.on && s.error && !s.count);
    if (down.length) parts.push(`couldn't reach ${down.map(s => s.name).join(", ")}`);
    $("updated").textContent = parts.length ? parts.join(" · ").replace(/^./, c => c.toUpperCase()) : "No news yet";
    renderSources(); renderBans(); renderSets(); renderPreviews(); renderArticles();
  }

  // ---------- sources ----------
  $("sourcesBtn").onclick = () => {
    const open = $("sourcesPanel").hidden;
    $("sourcesPanel").hidden = !open; $("sourcesBtn").setAttribute("aria-expanded", open);
  };
  function renderSources() {
    $("sourceList").innerHTML = data.sources.map(s => `<label class="source">
        <span class="switch"><input type="checkbox" data-src="${esc(s.key)}"${s.on ? " checked" : ""}><span></span></span>
        <span class="info"><b>${esc(s.name)}</b><small>${esc(s.desc)}</small>
        <small class="${s.on && s.error ? "err" : ""}">${!s.on ? "Off" : s.error ? esc(s.error) + (s.count ? ", showing what was saved" : "") : s.updated ? `${s.count} articles · ${ago(s.updated)}` : "Not fetched yet"}
          · <a href="${esc(s.site)}" target="_blank" rel="noopener noreferrer">Open the site</a></small></span></label>`).join("");
  }
  $("sourceList").onchange = async e => {
    const box = e.target.closest("[data-src]"); if (!box) return;
    box.disabled = true;
    try { data = await api("/api/news/sources", { [box.dataset.src]: box.checked }); render(); toast(box.checked ? "Source turned on" : "Source turned off"); }
    catch (err) { toast(err.message); box.checked = !box.checked; box.disabled = false; }
  };

  // ---------- ban list changes ----------
  function renderBans() {
    $("banBox").innerHTML = (data.bans || []).map(a => `<a class="ban-box" href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">
      <svg><use href="#i-ban" /></svg><span><small>Ban list news · ${esc(srcName(a.source))} · ${esc(ago(when(a)))}</small><b>${esc(a.title)}</b></span></a>`).join("");
  }

  // ---------- sets ----------
  $("setSeg").onclick = e => {
    const b = e.target.closest("button"); if (!b) return;
    setView = b.dataset.v;
    for (const x of $("setSeg").children) x.setAttribute("aria-pressed", x === b);
    renderSets();
  };
  function renderSets() {
    const s = data.sets || {};
    const list = s[setView] || [];
    $("setsBox").hidden = !(s.upcoming?.length || s.recent?.length);
    $("setStrip").innerHTML = list.length ? list.map(x => `<a class="new-set${x.days >= 0 && x.days <= 14 ? " soon" : ""}" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">
        <span class="icon">${x.icon ? `<img src="${esc(x.icon)}" alt="" loading="lazy">` : ""}</span>
        <b title="${esc(x.name)}">${esc(x.name)}</b>
        <small>${esc(TYPES[x.type] || x.type)} · ${esc(x.code)}</small>
        <span class="when"><em>${esc(countdown(x.days))}</em><span class="sub">${esc(day(x.released))} · ${x.cards ? `${x.cards} cards` : "no cards shown yet"}</span></span></a>`).join("")
      : `<p class="news-empty">${setView === "upcoming" ? "No new sets announced on Scryfall yet." : "No set came out in the last few weeks."}</p>`;
  }

  // ---------- previews ----------
  function renderPreviews() {
    const cards = data.previews || [];
    $("previewsBox").hidden = !cards.length;
    $("previewsAll").href = data.previews_url;
    const sets = [...new Map(cards.map(c => [c.set, c.set_name])).entries()];
    if (previewSet && !sets.some(([k]) => k === previewSet)) previewSet = "";
    $("previewSets").innerHTML = sets.length > 1 ? [["", "All sets"], ...sets].map(([k, n]) =>
      `<button class="chip" data-set="${esc(k)}" aria-pressed="${k === previewSet}">${esc(n)}</button>`).join("") : "";
    $("previewStrip").innerHTML = cards.filter(c => !previewSet || c.set === previewSet).map(c => `<a class="tile" href="${esc(c.url)}" target="_blank" rel="noopener noreferrer" title="${esc(c.name)}">
        <div class="art">${c.image ? `<img src="${esc(c.image)}" alt="${esc(c.name)}" loading="lazy">` : `<div class="noimg">${esc(c.name)}</div>`}</div>
        <b>${esc(c.name)}</b><small>${esc(c.set_name)}${c.by ? ` · by ${esc(c.by)}` : ""}</small></a>`).join("");
  }
  $("previewSets").onclick = e => {
    const b = e.target.closest("[data-set]"); if (!b) return;
    previewSet = b.dataset.set; renderPreviews();
  };

  // ---------- articles ----------
  const srcName = key => data.sources.find(s => s.key === key)?.name || key;
  $("tagSeg").onclick = e => {
    const b = e.target.closest("button"); if (!b) return;
    tag = b.dataset.v; shown = PAGE;
    for (const x of $("tagSeg").children) x.setAttribute("aria-pressed", x === b);
    renderArticles();
  };
  // A picture that doesn't load (moved, blocked) just goes away.
  $("articles").addEventListener("error", e => { if (e.target.matches?.("img.pic")) e.target.remove(); }, true);
  $("newsQ").oninput = () => { shown = PAGE; renderArticles(); };
  $("moreBtn").onclick = () => { shown += PAGE; renderArticles(); };

  function renderArticles() {
    const q = $("newsQ").value.trim().toLowerCase();
    const list = data.articles.filter(a => (tag === "all" || (tag === "wizards" ? a.source === "wizards" : a.tags.includes(tag)))
      && (!q || `${a.title} ${a.summary} ${a.section} ${a.author}`.toLowerCase().includes(q)));
    const on = data.sources.filter(s => s.on).length;
    $("articles").innerHTML = list.length ? list.slice(0, shown).map(a => {
      const t = when(a), fresh = lastVisit && t > lastVisit;
      return `<a class="article panel" href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">
        ${a.image ? `<img class="pic" src="${esc(a.image)}" alt="" loading="lazy">` : ""}
        <div class="body">
          <div class="meta-row"><span class="src ${esc(a.source)}">${esc(srcName(a.source))}</span>${a.section ? `<span>${esc(a.section)}</span>` : ""}
            ${t ? `<span>${esc(ago(t))}</span>` : ""}${fresh ? `<span class="tag new">New</span>` : ""}
            ${a.tags.includes("bans") ? `<span class="tag bans">Bans</span>` : ""}${a.tags.includes("previews") ? `<span class="tag previews">Preview</span>` : ""}</div>
          <h4>${esc(a.title)}</h4>
          ${a.summary ? `<p>${esc(a.summary)}</p>` : ""}
          ${a.author ? `<div class="meta-row"><span>by ${esc(a.author)}</span></div>` : ""}
        </div></a>`;
    }).join("") : `<p class="news-empty">${!on ? "Every source is turned off. Turn one on under <b>Sources</b>." : data.articles.length ? "Nothing matches that." : data.online ? "No news yet. Press <b>Refresh</b> to try again." : "No saved news, and the sorter is running offline."}</p>`;
    $("moreBtn").hidden = list.length <= shown;
  }

  load(false);
})();
