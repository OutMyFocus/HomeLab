// Build a deck (Decks page): Commander decks your own cards can make, best first. The Pi
// works out each idea (mtgscanner/deck_ideas.py); this shows them, previews one, and makes
// it a saved deck in the editor below, where the deck builder takes over.
(() => {
  const { $, esc, toast, api } = MTG;
  const V = VAULT;
  const FOLD_KEY = "mtg-ideas-folded", FIRST = 8;
  const JOBS = [["ramp", "Ramp"], ["draw", "Card draw"], ["removal", "Removal"], ["wipe", "Board wipes"]];
  const TARGETS = { ramp: 10, draw: 9, removal: 8, wipe: 2 };
  const TYPE_NAMES = { Creature: "Creatures", Planeswalker: "Planeswalkers", Battle: "Battles", Instant: "Instants", Sorcery: "Sorceries", Artifact: "Artifacts", Enchantment: "Enchantments", Other: "Other" };
  const opts = { style: "", colors: new Set(), owned: false, spare: false };
  let ideas = [], styles = {}, shown = FIRST, loadT = null, seq = 0;
  let preview = null, fill = "buy", previewFor = "", previewSeq = 0;

  const art = n => `https://api.scryfall.com/cards/named?exact=${encodeURIComponent(n)}&format=image&version=art_crop`;
  const frontName = n => String(n).split(" // ")[0];
  const fitWord = f => f >= 85 ? "Ready to play" : f >= 70 ? "Nearly there" : f >= 50 ? "Good start" : "Needs cards";
  const fitCls = f => f >= 85 ? "good" : f >= 70 ? "ok" : f >= 50 ? "warn" : "low";

  // ---------- folding the panel away ----------
  function setFold(folded) {
    $("ideas").classList.toggle("folded", folded);
    $("ideasFold").setAttribute("aria-expanded", String(!folded));
    $("ideasBody").hidden = folded;
    try { localStorage.setItem(FOLD_KEY, folded ? "1" : ""); } catch (e) { }
    if (!folded && !ideas.length) load();
  }
  $("ideasFold").onclick = () => setFold(!$("ideas").classList.contains("folded"));

  // ---------- the ideas ----------
  function query() {
    const p = new URLSearchParams();
    if (opts.style) p.set("style", opts.style);
    if (opts.colors.size) p.set("colors", [...opts.colors].join(""));
    if (opts.owned) p.set("owned", "1");
    if (opts.spare) p.set("spare", "1");
    return p.toString();
  }
  async function load() {
    const mine = ++seq;
    $("iGrid").classList.add("loading");
    if (!ideas.length) $("iGrid").innerHTML = Array(4).fill('<div class="idea-tile skel"></div>').join("");
    try {
      const js = await api("/api/decks/ideas?" + query());
      if (mine !== seq) return;
      ideas = js.ideas || []; styles = js.styles || styles; shown = FIRST;
      $("ideasSub").textContent = js.error ? js.error : js.cards
        ? `Commander decks your ${js.cards.toLocaleString()} different cards can make, best first.`
        : "Scan or import some cards first, and ideas for decks show up here.";
      renderStyles(); render();
    } catch (e) {
      if (mine !== seq) return;
      $("iGrid").innerHTML = `<p class="none">${esc(e.message)}</p>`;
    } finally { if (mine === seq) $("iGrid").classList.remove("loading"); }
  }
  const reload = () => { clearTimeout(loadT); loadT = setTimeout(load, 120); };

  function renderStyles() {
    $("iStyles").innerHTML = `<button class="chip" data-s="" aria-pressed="${!opts.style}">Any style</button>`
      + Object.entries(styles).map(([k, label]) => `<button class="chip" data-s="${esc(k)}" aria-pressed="${opts.style === k}">${esc(label)}</button>`).join("");
  }
  $("iStyles").onclick = e => { const b = e.target.closest("[data-s]"); if (!b) return; opts.style = b.dataset.s; renderStyles(); reload(); };
  $("iColors").onclick = e => {
    const b = e.target.closest("[data-c]"); if (!b) return;
    const c = b.dataset.c; opts.colors.has(c) ? opts.colors.delete(c) : opts.colors.add(c);
    b.setAttribute("aria-pressed", opts.colors.has(c)); reload();
  };
  $("iColors").title = "Exactly these colors (pick none for any)";
  $("iOwned").onchange = () => { opts.owned = $("iOwned").checked; reload(); };
  $("iSpare").onchange = () => { opts.spare = $("iSpare").checked; reload(); };

  function tile(d, i) {
    const owned = 99 - d.open;
    const tags = (d.tags || []).slice(0, 3).map(t => `<span class="idea-tag">${esc(t)}</span>`).join("");
    return `<button class="idea-tile" data-i="${i}" style="--art: url('${esc(art(d.commander))}')">
      <span class="idea-art" aria-hidden="true"></span>
      <span class="idea-fit ${fitCls(d.fit)}" title="How ready it is from your cards"><b>${d.fit}</b><small>%</small></span>
      <span class="idea-info">
        <span class="idea-pips">${V.pips(d.ci)}${d.owned_leader ? "" : '<span class="badge warn">Get the commander</span>'}</span>
        <b class="idea-name">${esc(frontName(d.commander))}</b>
        <span class="idea-tags">${tags || '<span class="idea-tag plain">Good cards in its colors</span>'}</span>
        <span class="idea-meter" aria-hidden="true"><span style="width:${Math.round(owned / 99 * 100)}%"></span></span>
        <span class="idea-line"><span>${fitWord(d.fit)}</span><span>${d.open ? `${owned} of 99 · ${d.open} to fill` : "All 99 from your cards"}</span></span>
      </span></button>`;
  }
  function render() {
    if (!ideas.length) {
      $("iGrid").innerHTML = `<p class="none">${opts.style || opts.colors.size || opts.owned ? "No ideas match these choices. Try fewer." : "No ideas yet."}</p>`;
      $("iMore").hidden = true; return;
    }
    $("iGrid").innerHTML = ideas.slice(0, shown).map(tile).join("");
    $("iMore").hidden = ideas.length <= shown;
    $("iNote").textContent = ideas.length > shown ? `${ideas.length - shown} more` : "";
  }
  $("iMore").onclick = () => { shown += 12; render(); };
  $("iGrid").onclick = e => { const b = e.target.closest(".idea-tile[data-i]"); if (b) open(ideas[+b.dataset.i].commander); };

  // ---------- start from any commander ----------
  let sug = [], sugIdx = -1;
  function suggest() {
    const q = V.norm($("iCmd").value), ul = $("iSug");
    if (!q || !V.S.cards) { ul.hidden = true; return; }
    const starts = [], has = [];
    for (const c of V.S.cards) {
      if (!V.isCommander(c) || c.b) continue;
      if (c._k.startsWith(q)) starts.push(c); else if (c._k.includes(q)) has.push(c);
      if (starts.length > 30) break;
    }
    const rank = (a, b) => (a.e || 1e6) - (b.e || 1e6);
    sug = [...starts.sort(rank), ...has.sort(rank)].slice(0, 10); sugIdx = sug.length ? 0 : -1;
    ul.innerHTML = sug.map((c, i) => `<li role="option" data-i="${i}" aria-selected="${i === sugIdx}"><span>${esc(c.n)}${V.ownedQty(c.n) ? ' <span class="badge good">Own</span>' : ""}</span><span>${V.pips(c.ci)}</span></li>`).join("");
    ul.hidden = !sug.length;
  }
  function pickSug(i) { const c = sug[i]; if (!c) return; $("iCmd").value = ""; $("iSug").hidden = true; open(c.n); }
  $("iCmd").oninput = suggest;
  $("iCmd").onfocus = () => { if (!V.S.cards) $("iCmd").placeholder = "Loading the card list…"; };
  $("iCmd").onkeydown = e => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { if (!sug.length) return; e.preventDefault(); sugIdx = (sugIdx + (e.key === "ArrowDown" ? 1 : -1) + sug.length) % sug.length; for (const li of $("iSug").children) li.setAttribute("aria-selected", +li.dataset.i === sugIdx); }
    else if (e.key === "Enter") { e.preventDefault(); if (sugIdx >= 0) pickSug(sugIdx); else if ($("iCmd").value.trim()) open($("iCmd").value.trim()); }
    else if (e.key === "Escape") $("iSug").hidden = true;
  };
  $("iSug").onmousedown = e => { const li = e.target.closest("li[data-i]"); if (li) { e.preventDefault(); pickSug(+li.dataset.i); } };
  $("iCmd").onblur = () => setTimeout(() => $("iSug").hidden = true, 150);

  // ---------- preview one idea ----------
  function open(commander) {
    previewFor = commander; preview = null;
    $("ipName").textContent = frontName(commander);
    $("ipHero").style.setProperty("--art", `url('${art(commander)}')`);
    $("ipPips").innerHTML = ""; $("ipTags").innerHTML = ""; $("ipStats").innerHTML = ""; $("ipJobs").innerHTML = "";
    $("ipList").innerHTML = '<p class="sub idea-wait">Picking the best of your cards…</p>';
    $("ipBuild").disabled = true; $("ipNote").textContent = "";
    $("idea").hidden = false; document.body.classList.add("modal-open");
    $("ipBuild").focus({ preventScroll: true });
    build();
  }
  function close() { $("idea").hidden = true; document.body.classList.remove("modal-open"); previewSeq++; }
  $("idea").onclick = e => { if (e.target === $("idea") || e.target.closest("[data-close]")) close(); };
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !$("idea").hidden) close(); });

  async function build() {
    const mine = ++previewSeq;
    $("ipList").classList.add("loading");
    try {
      const d = await api("/api/decks/ideas/build", { commander: previewFor, fill, spare: opts.spare });
      if (mine !== previewSeq) return;
      preview = d; renderPreview();
    } catch (e) {
      if (mine !== previewSeq) return;
      $("ipList").innerHTML = `<p class="none">${esc(e.message)}</p>`;
    } finally { if (mine === previewSeq) $("ipList").classList.remove("loading"); }
  }
  function renderPreview() {
    const d = preview, own = d.cards.filter(c => !c.buy), buy = d.cards.filter(c => c.buy);
    const basics = Object.values(d.basics).reduce((a, b) => a + b, 0), lands = d.lands.length + basics;
    $("ipName").textContent = frontName(d.commander);
    $("ipPips").innerHTML = V.pips(d.ci) + (d.owned_leader ? "" : ' <span class="badge warn">You don\'t have this commander yet</span>');
    $("ipTags").innerHTML = (d.tags || []).map(t => `<span class="idea-tag">${esc(t)}</span>`).join("") || '<span class="idea-tag plain">Good cards in its colors</span>';
    $("ipStats").innerHTML = [
      [`${d.fit}%`, fitWord(d.fit), fitCls(d.fit)],
      [`${99 - buy.length - d.open}/99`, "from your cards"],
      [lands, `lands, ${basics} of them basic`],
      buy.length ? [buy.length, buy.length === 1 ? "card to get" : "cards to get", "warn"] : d.open ? [d.open, "slots left open", "warn"] : ["✓", "Nothing to buy", "good"],
    ].map(([v, l, c]) => `<div class="idea-stat ${c || ""}"><b>${esc(v)}</b><small>${esc(l)}</small></div>`).join("");
    $("ipJobs").innerHTML = JOBS.map(([k, label]) => {
      const got = d.roles[k] || 0, t = TARGETS[k], pct = Math.min(100, Math.round(got / t * 100));
      return `<div class="idea-job ${got >= t ? "full" : ""}"><span>${label}</span><span class="idea-meter"><span style="width:${pct}%"></span></span><b>${got}<small>/${t}</small></b></div>`;
    }).join("") + `<div class="idea-job theme"><span>On theme</span><span class="idea-meter"><span style="width:${Math.min(100, Math.round(d.on_theme / 35 * 100))}%"></span></span><b>${d.on_theme}</b></div>`;
    $("ipFillRow").hidden = !d.open && !buy.length && fill === "buy";
    for (const b of $("ipFill").children) b.setAttribute("aria-pressed", b.dataset.v === fill);
    const groups = new Map();
    for (const c of d.cards) { if (!groups.has(c.type)) groups.set(c.type, []); groups.get(c.type).push(c); }
    const order = ["Creature", "Planeswalker", "Battle", "Instant", "Sorcery", "Artifact", "Enchantment", "Other"];
    const li = c => `<li class="${c.buy ? "buy" : ""}"><span class="dot${c.on && !c.buy ? "" : " off"}" title="${c.on && !c.buy ? "On theme" : ""}"></span><a class="cardlink" href="/cards?card=${encodeURIComponent(c.n)}" target="_blank" rel="noopener">${esc(c.n)}</a>${c.buy ? '<span class="own n" title="Not in your collection">BUY</span>' : ""}<span class="cost">${c.m ? V.mana(c.m.split(" // ")[0]) : ""}</span></li>`;
    let html = order.filter(k => groups.has(k)).map(k => `<section><h4>${TYPE_NAMES[k]} <span class="sub">${groups.get(k).length}</span></h4><ul>${groups.get(k).map(li).join("")}</ul></section>`).join("");
    html += `<section><h4>Lands <span class="sub">${lands}</span></h4><ul>${d.lands.map(n => li({ n })).join("")}${Object.entries(d.basics).map(([n, q]) => `<li class="basic"><span class="dot off"></span><span>${q} ${esc(n)}</span></li>`).join("")}</ul></section>`;
    $("ipList").innerHTML = html;
    $("ipNote").textContent = d.edhrec ? "Picks use what other decks with this commander play (EDHREC)." : "";
    $("ipBuild").disabled = false;
  }
  $("ipFill").onclick = e => {
    const b = e.target.closest("button[data-v]"); if (!b || b.dataset.v === fill) return;
    fill = b.dataset.v; for (const x of $("ipFill").children) x.setAttribute("aria-pressed", x === b); build();
  };
  $("ipBuild").onclick = async () => {
    if (!preview) return;
    if (window.DECKS?.unsaved?.() && !confirm("Discard your unsaved changes to the list in the box?")) return;
    $("ipBuild").disabled = true;
    try {
      const deck = await window.DECKS.create(`${frontName(preview.commander)} from my cards`, preview.text);
      close();
      toast(`Saved ${deck.name}. Change anything below`);
      document.querySelector(".deck-edit")?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) { toast(e.message); $("ipBuild").disabled = false; }
  };

  // ---------- start ----------
  let folded = false;
  try { folded = localStorage.getItem(FOLD_KEY) === "1"; } catch (e) { }
  setFold(folded);
  V.loadCards().then(() => { $("iCmd").placeholder = "Or start from any commander: type a name"; if (document.activeElement === $("iCmd")) suggest(); });
})();
