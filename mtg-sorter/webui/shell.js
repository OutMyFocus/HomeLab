// SortR's frame, the same on every page. On a computer: a sidebar with every page in its
// group, and a bar along the top with the page's name, search (Ctrl K), the light/dark
// switch and who's logged in. On a phone: the page's name at the top and a tab bar along the
// bottom (Home, Scanner, Cards, Decks, More), the groups rising as a sheet.
// Also: a dot on Maintenance when the Pi's check-up finds a problem, and the search palette
// that jumps to any page, any card you own or an action. Load it right after the header.
(() => {
  const ICONS = {
    home: '<path d="M4 11.5 12 5l8 6.5V19a1.5 1.5 0 0 1-1.5 1.5H15v-5.5H9v5.5H5.5A1.5 1.5 0 0 1 4 19v-7.5Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>',
    scan: '<path d="M4 8a2 2 0 0 1 2-2h2l1.5-2h5L16 6h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><circle cx="12" cy="12.5" r="3.5" fill="none" stroke="currentColor" stroke-width="1.7"/>',
    collection: '<rect x="7" y="3.5" width="12" height="15" rx="2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M5 7v11.5A2.5 2.5 0 0 0 7.5 21H15" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>',
    decks: '<rect x="9" y="4" width="10" height="14" rx="1.8" transform="rotate(12 14 11)" fill="none" stroke="currentColor" stroke-width="1.6"/><rect x="5" y="5" width="10" height="14" rx="1.8" transform="rotate(-8 10 12)" fill="none" stroke="currentColor" stroke-width="1.6"/>',
    wishlist: '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>',
    history: '<circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M12 8v4.5l3 2" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>',
    bins: '<path d="M3.5 9h17l-1.5 10.5h-14L3.5 9ZM8 9V5.5h8V9" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M12 12v4.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>',
    machine: '<path d="M13 3 5 13.5h6L10 21l8-10.5h-6L13 3Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>',
    cards: '<circle cx="10.5" cy="10.5" r="6" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="m15 15 5 5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>',
    play: '<rect x="4" y="4" width="16" height="16" rx="3" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="9" cy="9" r="1.4" fill="currentColor"/><circle cx="15" cy="15" r="1.4" fill="currentColor"/><circle cx="12" cy="12" r="1.4" fill="currentColor"/>',
    lights: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.7.6 1.1 1.3 1.1 2.2h5c0-.9.4-1.6 1.1-2.2A6 6 0 0 0 12 3Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
    maintenance: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
    settings: '<circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M5.6 18.4l1.8-1.8M16.6 7.4l1.8-1.8" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>',
    sets: '<rect x="4" y="4" width="7" height="7" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.7"/><rect x="13" y="4" width="7" height="7" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.7"/><rect x="4" y="13" width="7" height="7" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M13 16.5h7M16.5 13v7" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>',
    news: '<path d="M5 5.5h11.5V18a2 2 0 0 0 2 2H6.5A1.5 1.5 0 0 1 5 18.5v-13Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M16.5 9H19v9a2 2 0 0 1-2.5 2M8 9h5.5M8 12.5h5.5M8 16h3.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
    more: '<circle cx="6" cy="12" r="1.6" fill="currentColor"/><circle cx="12" cy="12" r="1.6" fill="currentColor"/><circle cx="18" cy="12" r="1.6" fill="currentColor"/>',
    search: '<circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="m16 16 4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    sun: '<circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>',
    moon: '<path d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>',
    auto: '<circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M12 4a8 8 0 0 1 0 16Z" fill="currentColor"/>',
    bolt: '<path d="M13 3 5 13.5h6L10 21l8-10.5h-6L13 3Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>',
    photos: '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="9" cy="10" r="1.8" fill="currentColor"/><path d="m4 17 5-4.5 4 3.5 3-2.5 4.5 4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>',
    enter: '<path d="M19 6v5a3 3 0 0 1-3 3H6m0 0 4-4m-4 4 4 4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    side: '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M9.5 4.5v15" stroke="currentColor" stroke-width="1.7"/>',
  };
  // Every page, then the few groups the menu shows them in. Home and Scanner are links of
  // their own; the rest sit under Cards, Decks, Machine and the gear (Settings).
  const PAGES = [
    { key: "home", href: "/", label: "Home", desc: "Everything at a glance" },
    { key: "scan", href: "/scan", label: "Scanner", desc: "Scan cards with the camera or photos" },
    { key: "collection", href: "/collection", label: "Collection", desc: "Every card you've saved, stats and exports" },
    { key: "sets", href: "/sets", label: "Sets", desc: "How complete each set is, and spares to trade" },
    { key: "wishlist", href: "/wishlist", label: "Wishlist", desc: "Cards you want, and your trade binder" },
    { key: "news", href: "/news", label: "News", desc: "New sets, previews and ban announcements" },
    { key: "cards", href: "/cards", label: "Card lookup", desc: "Any Commander card, with Canadian prices" },
    { key: "history", href: "/history", label: "Scan history", desc: "Past scanning sessions" },
    { key: "decks", href: "/decks", label: "Decks", desc: "Build decks, check them and find upgrades" },
    { key: "play", href: "/play", label: "Play", desc: "Life counter and the games log" },
    { key: "machine", href: "/machine", label: "Machine", desc: "Test the servos and feeder" },
    { key: "bins", href: "/bins", label: "Bins", desc: "What goes in each bin" },
    { key: "lights", href: "/lights", label: "Lights", desc: "Color of the light strip" },
    { key: "settings", href: "/settings", label: "Settings", desc: "Accounts, alerts, PIN lock and the look" },
    { key: "maintenance", href: "/maintenance", label: "Maintenance", desc: "Health, updates, backups" },
  ];
  const LINKS = ["home", "scan"];
  const GROUPS = [
    { key: "g-cards", label: "Cards", icon: "collection", pages: ["collection", "sets", "wishlist", "news", "cards", "history"] },
    { key: "g-decks", label: "Decks", icon: "decks", pages: ["decks", "play"] },
    { key: "g-machine", label: "Machine", icon: "machine", pages: ["machine", "bins", "lights"] },
    { key: "g-system", label: "Settings", icon: "settings", pages: ["settings", "maintenance"] },
  ];
  const LOOK_KEY = "mtg-scanner-look";
  const page = k => PAGES.find(p => p.key === k);
  const here = location.pathname.replace(/\/+$/, "") || "/";
  const current = PAGES.find(p => p.href === here)?.key || (here === "/" || here === "/home" ? "home" : "");
  const herePage = page(current);
  const icon = (k, cls = "nav-ico") => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[k] || ""}</svg>`;
  const cur = p => p.key === current ? ' aria-current="page"' : "";
  const inGroup = g => g.pages.includes(current);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  const root = document.documentElement;

  const header = document.querySelector("header.top");
  if (!header) return;
  root.classList.add("has-shell");
  // The logo goes home, and the brand gets its colored tile.
  let brand = header.querySelector(".brand");
  if (brand && brand.tagName !== "A") {
    const a = document.createElement("a");
    a.className = brand.className; a.href = "/"; a.innerHTML = brand.innerHTML; a.setAttribute("aria-label", "SortR home");
    brand.replaceWith(a); brand = a;
  }
  if (brand) brand.innerHTML = `<span class="logo-tile"><svg class="logo" viewBox="0 0 24 24"><use href="#i-logo"/></svg></span><span class="wordmark">Sort<b>R</b></span>`;

  // ---------- the sidebar (a computer) ----------
  const side = document.createElement("aside");
  side.className = "side"; side.setAttribute("aria-label", "SortR");
  const link = p => `<a href="${p.href}" data-key="${p.key}"${cur(p)} title="${esc(p.label)}">${icon(p.key)}<span>${esc(p.label)}</span></a>`;
  side.innerHTML = `
    <a class="side-brand" href="/" aria-label="SortR home"><span class="logo-tile"><svg class="logo" viewBox="0 0 24 24"><use href="#i-logo"/></svg></span><span class="wordmark">Sort<b>R</b></span></a>
    <button type="button" class="side-search" data-palette title="Search (${isMac ? "⌘" : "Ctrl"} K)">${icon("search")}<span>Search</span><kbd>${isMac ? "⌘" : "Ctrl"} K</kbd></button>
    <nav class="side-nav" aria-label="Pages">
      <div class="side-sec">${LINKS.map(k => link(page(k))).join("")}</div>
      ${GROUPS.map(g => `<div class="side-sec" data-group="${g.key}"><h4>${esc(g.label)}</h4>${g.pages.map(k => link(page(k))).join("")}</div>`).join("")}
    </nav>
    <div class="side-foot">
      <div class="side-who" hidden></div>
      <div class="side-row"><a class="side-health" href="/maintenance" data-key="maintenance-status" hidden><i class="dot"></i><span><b>Checking…</b><small>SortR health</small></span></a><button type="button" class="side-btn" data-theme-toggle aria-label="Light or dark">${icon("auto")}</button><button type="button" class="side-btn" data-collapse aria-label="Smaller sidebar" title="Smaller sidebar">${icon("side")}</button></div>
    </div>`;
  document.body.prepend(side);
  try { if (localStorage.getItem("sortr-side") === "mini") root.classList.add("side-mini"); } catch (e) {}
  side.querySelector("[data-collapse]").onclick = () => {
    const mini = root.classList.toggle("side-mini");
    try { localStorage.setItem("sortr-side", mini ? "mini" : ""); } catch (e) {}
  };

  // ---------- the top bar: the page's name and the tools ----------
  if (herePage) {
    const head = document.createElement("div");
    head.className = "page-head";
    head.innerHTML = `<span class="page-ico">${icon(herePage.key)}</span><span class="page-txt"><h1 class="page-title">${esc(herePage.label)}</h1><small class="page-desc">${esc(herePage.desc)}</small></span>`;
    (brand || header.firstChild)?.after(head);
    document.title = herePage.key === "home" ? "SortR" : `${herePage.label} · SortR`;
  }
  const tools = document.createElement("div");
  tools.className = "top-tools";
  tools.innerHTML = `<button type="button" class="tool-btn search-btn" data-palette aria-label="Search">${icon("search")}<span>Search cards, pages…</span><kbd>${isMac ? "⌘" : "Ctrl"} K</kbd></button>
    <button type="button" class="tool-btn" data-theme-toggle aria-label="Light or dark">${icon("auto")}</button>`;
  header.append(tools);

  // ---------- the tab bar (a phone) ----------
  const BAR = [...LINKS.map(k => ({ ...page(k), link: true })), GROUPS[0], GROUPS[1],
    { key: "g-more", label: "More", icon: "more", pages: [...GROUPS[2].pages, ...GROUPS[3].pages], sections: [GROUPS[2], GROUPS[3]] }];
  const bar = document.createElement("nav");
  bar.className = "tab-bar"; bar.setAttribute("aria-label", "Pages");
  bar.innerHTML = BAR.map(b => b.link
    ? `<a href="${b.href}" data-key="${b.key}"${cur(b)}>${icon(b.key)}<span>${b.label}</span></a>`
    : `<button type="button" class="menu-btn" data-group="${b.key}" aria-haspopup="true" aria-expanded="false"${inGroup(b) ? ' aria-current="page"' : ""}>${icon(b.icon)}<span>${b.label}</span></button>`).join("");
  document.body.append(bar);
  root.classList.add("has-tab-bar");

  // The sheet that rises from the tab bar with a group's pages.
  const groupOf = k => GROUPS.find(g => g.key === k) || BAR.find(b => b.key === k) || { sections: [{ label: "Start", pages: LINKS }, ...GROUPS] };
  const item = p => `<a href="${p.href}" data-key="${p.key}"${cur(p)}>${icon(p.key)}<span><b>${p.label}</b><small>${p.desc}</small></span></a>`;
  const sheet = document.createElement("div");
  sheet.className = "more-sheet"; sheet.hidden = true;
  sheet.innerHTML = `<div class="more-scrim"></div><nav class="more-list" aria-label="Pages"><i class="grab"></i><div class="more-body"></div></nav>`;
  document.body.append(sheet);
  const list = sheet.querySelector(".more-body");
  const menuBtns = () => [...document.querySelectorAll(".menu-btn")];
  let opener = null, openKey = null;
  function fill(g) {
    const secs = g.sections || [g];
    list.innerHTML = secs.map(s => `<div class="menu-sec"><h4>${s.label}</h4>${s.pages.map(k => item(page(k))).join("")}</div>`).join("");
    hideBlocked(list);
    if (window.MTGHealth) markHealth(window.MTGHealth);
  }
  function setMenu(key, btn) {
    const open = !!key && !(key === openKey && !sheet.hidden);
    sheet.hidden = !open;
    menuBtns().forEach(b => b.setAttribute("aria-expanded", open && b === btn));
    if (open) {
      openKey = key; opener = btn || null;
      fill(groupOf(key));
      (list.querySelector('[aria-current="page"]') || list.querySelector("a:not([hidden])"))?.focus({ preventScroll: true });
    } else {
      openKey = null;
      if (opener) { opener.focus({ preventScroll: true }); opener = null; }
    }
  }
  document.addEventListener("click", e => {
    const b = e.target.closest(".menu-btn");
    if (b) { setMenu(b.dataset.group, b); return; }
    if (e.target.closest("[data-palette]")) { palette.open(); return; }
    if (e.target.closest("[data-theme-toggle]")) { cycleTheme(); return; }
    if (!sheet.hidden && !e.target.closest(".more-list")) setMenu(null);
  });
  document.addEventListener("keydown", e => {
    if (sheet.hidden) return;
    if (e.key === "Escape") { e.stopImmediatePropagation(); setMenu(null); return; }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      const links = [...list.querySelectorAll("a:not([hidden])")], i = links.indexOf(document.activeElement);
      if (!links.length) return;
      e.preventDefault();
      links[(i + (e.key === "ArrowDown" ? 1 : -1) + links.length) % links.length].focus();
    }
  }, true);
  addEventListener("resize", () => { if (!sheet.hidden && innerWidth > 700) setMenu(null); });

  // ---------- light / dark ----------
  // The same saved look the scanner's Customize panel writes; this only changes its theme.
  const THEMES = ["system", "dark", "light"];
  const THEME_ICON = { system: "auto", dark: "moon", oled: "moon", light: "sun" };
  const THEME_NAME = { system: "Matches this device", dark: "Dark", oled: "Black (OLED)", light: "Light" };
  function readLook() { try { return JSON.parse(localStorage.getItem(LOOK_KEY) || "{}") || {}; } catch (e) { return {}; } }
  function showTheme() {
    const t = root.dataset.theme || "system";
    for (const b of document.querySelectorAll("[data-theme-toggle]")) {
      b.innerHTML = icon(THEME_ICON[t] || "auto");
      b.title = `Theme: ${THEME_NAME[t] || t}. Click to switch`;
    }
    const dark = t === "dark" || t === "oled" || (t === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? (t === "oled" ? "#000000" : "#0b0c12") : "#f4f5f9");
  }
  function cycleTheme() {
    const t = root.dataset.theme || "system";
    const next = THEMES[(THEMES.indexOf(t === "oled" ? "dark" : t) + 1) % THEMES.length];
    const look = readLook(); look.theme = next;
    try { localStorage.setItem(LOOK_KEY, JSON.stringify(look)); } catch (e) {}
    root.classList.add("theme-swap");
    root.dataset.theme = next;
    setTimeout(() => root.classList.remove("theme-swap"), 400);
    showTheme();
    window.dispatchEvent(new CustomEvent("mtg-look", { detail: { theme: next } }));
    window.MTG?.toast?.(`Theme: ${THEME_NAME[next]}`);
  }
  showTheme();
  matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", showTheme);
  new MutationObserver(showTheme).observe(root, { attributes: true, attributeFilter: ["data-theme"] });

  // ---------- the search palette ----------
  // Pages, actions and the cards you own (loaded the first time it opens), all from one box.
  const ACTIONS = [
    { label: "Start scanning", desc: "Open the live scanner", to: "/scan", icon: "scan", words: "camera live scan" },
    { label: "Scan photos", desc: "Pictures you already took", to: "/scan#photos", icon: "photos", words: "upload pictures images" },
    { label: "Look up any card", desc: "Rules text and Canadian prices", to: "/cards", icon: "cards", words: "search find oracle", q: "/cards?q=" },
    { label: "Customize the look", desc: "Theme, accent color, font, corners", to: "/scan?customize", icon: "settings", words: "theme color accent font dark light" },
    { label: "Switch light or dark", desc: "System, dark or light", run: () => cycleTheme(), icon: "auto", words: "theme dark light mode night" },
    { label: "Add a card by hand", desc: "One you didn't scan", to: "/collection#add", icon: "collection", words: "add manual type new" },
    { label: "Export the collection", desc: "CSV for ManaBox, Moxfield and more", to: "/collection#export", icon: "collection", words: "download csv moxfield manabox" },
    { label: "New deck", desc: "Paste a decklist and check it", to: "/decks", icon: "decks", words: "decklist build commander" },
    { label: "Life counter", desc: "Start a game", to: "/play", icon: "play", words: "life game commander damage" },
  ];
  const palette = (() => {
    const el = document.createElement("div");
    el.className = "cmdk"; el.hidden = true;
    el.innerHTML = `<div class="cmdk-scrim"></div><div class="cmdk-box" role="dialog" aria-modal="true" aria-label="Search SortR">
      <label class="cmdk-input">${icon("search")}<input type="search" placeholder="Search your cards, pages and actions" autocomplete="off" spellcheck="false" aria-label="Search"><kbd>Esc</kbd></label>
      <div class="cmdk-list" role="listbox"></div>
      <div class="cmdk-foot"><span><kbd>↑</kbd><kbd>↓</kbd> to move</span><span><kbd>Enter</kbd> to open</span><span class="cmdk-note"></span></div></div>`;
    document.body.append(el);
    const input = el.querySelector("input"), listEl = el.querySelector(".cmdk-list"), note = el.querySelector(".cmdk-note");
    let cards = null, loading = null, items = [], sel = 0, last = null;
    const money = v => v == null ? "" : "$" + Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const small = url => url ? url.replace("version=normal", "version=small") : "";
    function loadCards() {
      if (cards || loading) return loading;
      loading = fetch("/api/collection").then(r => r.ok ? r.json() : null).then(js => {
        const by = new Map();
        for (const c of js?.cards || []) {
          const k = c.name.toLowerCase(), o = by.get(k);
          if (!o) by.set(k, { name: c.name, set: c.set, image: c.image, qty: c.qty || 1, price: c.price, sets: new Set([c.set]) });
          else { o.qty += c.qty || 1; o.sets.add(c.set); if ((c.price || 0) > (o.price || 0)) { o.price = c.price; o.image = c.image || o.image; } }
        }
        cards = [...by.values()];
        note.textContent = `${cards.length.toLocaleString()} cards you own`;
        render();
      }).catch(() => { cards = []; });
      return loading;
    }
    const norm = s => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
    function score(text, q) {
      const t = norm(text);
      if (t.startsWith(q)) return 3;
      if (t.split(/[\s,'-]+/).some(w => w.startsWith(q))) return 2;
      return t.includes(q) ? 1 : 0;
    }
    function render() {
      const q = norm(input.value.trim());
      const pages = PAGES.filter(p => !blocked.has(p.key)).map(p => ({ kind: "Pages", label: p.label, desc: p.desc, href: p.href, icon: p.key, s: q ? Math.max(score(p.label, q), score(p.desc, q) && .5) : 1 }));
      const acts = ACTIONS.map(a => ({ kind: "Actions", ...a, href: a.to, s: q ? Math.max(score(a.label, q), score(a.words, q) && .8) : (a.to === "/scan" || a.run ? 1 : 0) }));
      let own = [];
      if (q.length >= 2 && cards) {
        own = cards.map(c => ({ c, s: score(c.name, q) })).filter(x => x.s).sort((a, b) => b.s - a.s || (b.c.price || 0) - (a.c.price || 0)).slice(0, 8)
          .map(({ c, s }) => ({ kind: "Your cards", label: c.name, desc: `${[...c.sets].join(", ")}${c.qty > 1 ? ` · ×${c.qty}` : ""}`, end: money(c.price), image: small(c.image), href: "/collection?q=" + encodeURIComponent(c.name), s: s + 1 }));
      }
      const extra = q.length >= 2 ? [{ kind: "Everything else", label: `Look up “${input.value.trim()}”`, desc: "Every Commander card, with Canadian prices", href: "/cards?q=" + encodeURIComponent(input.value.trim()), icon: "cards", s: .1 }] : [];
      items = [...own, ...pages.filter(p => p.s), ...acts.filter(a => a.s), ...extra];
      if (!q) items = [...acts.filter(a => a.s), ...pages];
      sel = Math.min(sel, Math.max(0, items.length - 1));
      let kind = null;
      listEl.innerHTML = items.length ? items.map((it, i) => {
        const h = it.kind !== kind ? `<h4>${it.kind}</h4>` : ""; kind = it.kind;
        const pic = it.image !== undefined ? `<span class="cmdk-thumb">${it.image ? `<img src="${esc(it.image)}" alt="" loading="lazy">` : ""}</span>` : `<span class="cmdk-ico">${icon(it.icon)}</span>`;
        return `${h}<a class="cmdk-item" role="option" data-i="${i}" href="${esc(it.href || "#")}"${i === sel ? ' aria-selected="true"' : ""}>${pic}<span class="cmdk-txt"><b>${esc(it.label)}</b><small>${esc(it.desc || "")}</small></span>${it.end ? `<em>${esc(it.end)}</em>` : `<i class="cmdk-go">${icon("enter")}</i>`}</a>`;
      }).join("") : `<p class="cmdk-empty">Nothing matches “${esc(input.value)}”.</p>`;
      listEl.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
    }
    function go(i) {
      const it = items[i]; if (!it) return;
      close();
      if (it.run) it.run();
      else if (it.href) { location.href = it.href; if (it.href.startsWith(here + "#") || it.href === here + location.search) location.reload(); }
    }
    function open() {
      if (!el.hidden) return;
      last = document.activeElement;
      el.hidden = false; input.value = ""; sel = 0; render(); loadCards();
      requestAnimationFrame(() => input.focus());
    }
    function close() { el.hidden = true; last?.focus?.({ preventScroll: true }); }
    input.addEventListener("input", () => { sel = 0; render(); });
    input.addEventListener("keydown", e => {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        sel = (sel + (e.key === "ArrowDown" ? 1 : -1) + items.length) % Math.max(1, items.length);
        for (const a of listEl.querySelectorAll(".cmdk-item")) a.toggleAttribute("aria-selected", +a.dataset.i === sel);
        listEl.querySelector('[aria-selected]')?.scrollIntoView({ block: "nearest" });
      } else if (e.key === "Enter") { e.preventDefault(); go(sel); }
    });
    listEl.addEventListener("click", e => { const a = e.target.closest(".cmdk-item"); if (a) { e.preventDefault(); go(+a.dataset.i); } });
    listEl.addEventListener("mousemove", e => {
      const a = e.target.closest(".cmdk-item"); if (!a || +a.dataset.i === sel) return;
      sel = +a.dataset.i; for (const x of listEl.querySelectorAll(".cmdk-item")) x.toggleAttribute("aria-selected", x === a);
    });
    el.querySelector(".cmdk-scrim").onclick = close;
    document.addEventListener("keydown", e => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); el.hidden ? open() : close(); return; }
      if (!el.hidden && e.key === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); close(); }
    }, true);
    return { open, close, isOpen: () => !el.hidden };
  })();
  // Pages can open the search from a shortcut (the scanner uses M).
  window.MTGMenu = { toggle: () => palette.isOpen() ? palette.close() : palette.open(), isOpen: () => palette.isOpen() };

  // ---------- accounts hide pages; the check-up marks Maintenance ----------
  let blocked = new Set();
  function hideBlocked(scope = document) {
    for (const k of blocked) scope.querySelectorAll(`[data-key="${k}"]`).forEach(a => a.hidden = true);
    if (scope !== document) return;
    for (const b of menuBtns()) b.hidden = groupOf(b.dataset.group).pages.every(k => blocked.has(k));
    for (const s of side.querySelectorAll(".side-sec[data-group]")) s.hidden = [...s.querySelectorAll("a")].every(a => a.hidden);
  }
  const healthCard = side.querySelector(".side-health");
  function markHealth(h) {
    const state = h.overall === "ok" || blocked.has("maintenance") ? "" : h.overall;
    const tip = state ? "Maintenance: " + h.problems.map(p => p.label + ": " + p.summary).join(" · ") : "";
    for (const a of document.querySelectorAll('[data-key="maintenance"]')) {
      if (state) { a.dataset.state = state; a.title = tip; } else { delete a.dataset.state; a.title = "Maintenance"; }
    }
    for (const b of menuBtns()) {
      if (state && groupOf(b.dataset.group).pages.includes("maintenance")) b.dataset.state = state; else delete b.dataset.state;
    }
    if (!blocked.has("maintenance")) {
      const p = h.problems || [];
      healthCard.hidden = false;
      healthCard.dataset.state = h.overall;
      healthCard.title = tip || "Everything checks out";
      healthCard.querySelector("b").textContent = h.overall === "ok" ? "All systems good" : p.length === 1 ? p[0].label : `${p.length} things to check`;
      healthCard.querySelector("small").textContent = h.overall === "ok" ? "SortR health" : (p.length === 1 ? p[0].summary : "Open Maintenance");
    }
  }

  async function checkHealth() {
    if (window.MTGMe && !window.MTGMe.perms.admin) return;   // Maintenance is for admins
    try {
      const r = await fetch("/api/health");
      if (!r.ok) return;
      const h = await r.json();
      markHealth(h);
      window.MTGHealth = h;
      window.dispatchEvent(new CustomEvent("mtg-health", { detail: h }));
    } catch (e) {}
  }
  if (here !== "/lock") {
    checkHealth();
    let t = setInterval(checkHealth, 60000);
    document.addEventListener("visibilitychange", () => {
      clearInterval(t);
      if (!document.hidden) { checkHealth(); t = setInterval(checkHealth, 60000); }
    });
  }

  // ---------- lost the connection ----------
  // A thin bar at the top while the sorter can't be reached (it may be restarting).
  const net = document.createElement("div");
  net.className = "net-bar"; net.hidden = true; net.setAttribute("role", "status");
  net.innerHTML = `<i></i><span>Can't reach SortR. It may be restarting, trying again…</span>`;
  document.body.append(net);
  const realFetch = window.fetch.bind(window);
  let fails = 0;
  window.fetch = async (...a) => {
    try {
      const r = await realFetch(...a);
      if (r.status === 502 || r.status === 503 || r.status === 504) { if (++fails >= 2) net.hidden = false; } else { fails = 0; net.hidden = true; }
      return r;
    } catch (e) {
      if (++fails >= 2 && !(e && e.name === "AbortError")) net.hidden = false;
      throw e;
    }
  };
  addEventListener("offline", () => { net.hidden = false; });
  addEventListener("online", () => { fails = 0; net.hidden = true; });

  // ---------- who's logged in ----------
  const NEEDS = { machine: "machine", lights: "machine", maintenance: "admin" };
  fetch("/api/me").then(r => r.ok ? r.json() : null).then(s => {
    if (!s || !s.accounts) return;
    blocked = new Set(Object.entries(NEEDS).filter(([, perm]) => !s.perms[perm]).map(([key]) => key));
    hideBlocked();
    window.MTGMe = s;
    if (window.MTGHealth) markHealth(window.MTGHealth);
    if (blocked.has("maintenance")) healthCard.hidden = true;
    if (!s.me) return;
    const chip = document.createElement("a");
    chip.className = "who-chip"; chip.href = "/settings"; chip.title = `Logged in as ${s.me.name}: your account`;
    const initial = document.createElement("i"), name = document.createElement("b");
    initial.textContent = (s.me.name || s.me.username).slice(0, 1).toUpperCase(); name.textContent = s.me.name;
    chip.append(initial, name);
    header.append(chip);
    const who = side.querySelector(".side-who");
    who.hidden = false; who.append(chip.cloneNode(true));
  }).catch(() => {});
})();
