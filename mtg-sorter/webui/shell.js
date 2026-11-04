// The same page menu on every page: links across the header on a computer, a tab bar
// along the bottom on a phone, and a "More" list for the rest. Also puts a dot on
// Maintenance when the Pi's check-up finds a problem. Load it right after the header.
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
    more: '<circle cx="6" cy="12" r="1.6" fill="currentColor"/><circle cx="12" cy="12" r="1.6" fill="currentColor"/><circle cx="18" cy="12" r="1.6" fill="currentColor"/>',
  };
  // main: always in the header and the phone's bottom bar. The rest fold into More
  // when the window is narrow.
  const PAGES = [
    { key: "home", href: "/", label: "Home", desc: "Everything at a glance", main: true },
    { key: "scan", href: "/scan", label: "Scanner", desc: "Scan cards with the camera or photos", main: true },
    { key: "collection", href: "/collection", label: "Collection", desc: "Every card you've saved, stats and exports", main: true },
    { key: "machine", href: "/machine", label: "Machine", desc: "Test the servos and feeder", main: true },
    { key: "sets", href: "/sets", label: "Sets", desc: "How complete each set is, and spare copies to trade" },
    { key: "decks", href: "/decks", label: "Decks", desc: "Build Commander decks and check them against your cards" },
    { key: "cards", href: "/cards", label: "Card lookup", desc: "Every Commander card, with Canadian prices" },
    { key: "play", href: "/play", label: "Play", desc: "Life counter and the games log" },
    { key: "wishlist", href: "/wishlist", label: "Wishlist", desc: "Cards you want, and your trade binder" },
    { key: "history", href: "/history", label: "History", desc: "Past scanning sessions" },
    { key: "bins", href: "/bins", label: "Bins", desc: "What goes in each bin" },
    { key: "lights", href: "/lights", label: "Lights", desc: "Color of the RGB light bars" },
    { key: "maintenance", href: "/maintenance", label: "Maintenance", desc: "Health, updates, backups" },
    { key: "settings", href: "/settings", label: "Settings", desc: "Alerts, PIN lock and the look" },
  ];
  const here = location.pathname.replace(/\/+$/, "") || "/";
  const current = PAGES.find(p => p.href === here)?.key || (here === "/" ? "home" : "");
  const icon = k => `<svg class="nav-ico" viewBox="0 0 24 24" aria-hidden="true">${ICONS[k]}</svg>`;
  const cur = p => p.key === current ? ' aria-current="page"' : "";

  const header = document.querySelector("header.top");
  if (!header) return;
  // The logo goes home.
  const brand = header.querySelector(".brand");
  if (brand && brand.tagName !== "A") {
    const a = document.createElement("a");
    a.className = brand.className; a.href = "/"; a.innerHTML = brand.innerHTML; a.setAttribute("aria-label", "MTG Sorter home");
    brand.replaceWith(a);
  }

  const nav = document.createElement("nav");
  nav.className = "site-nav"; nav.setAttribute("aria-label", "Pages");
  nav.innerHTML = PAGES.map(p => `<a href="${p.href}" data-key="${p.key}" class="${p.main ? "main" : "extra"}"${cur(p)}>${p.label}</a>`).join("")
    + `<div class="more-wrap"><button class="more-btn" type="button" aria-haspopup="true" aria-expanded="false">More${icon("more")}</button></div>`;
  const anchor = header.querySelector(".brand");
  anchor.after(nav);

  // Phone: a bar along the bottom with the main pages and More.
  const bar = document.createElement("nav");
  bar.className = "tab-bar"; bar.setAttribute("aria-label", "Pages");
  bar.innerHTML = PAGES.filter(p => p.main).map(p => `<a href="${p.href}" data-key="${p.key}"${cur(p)}>${icon(p.key)}<span>${p.label}</span></a>`).join("")
    + `<button type="button" class="more-btn" aria-haspopup="true" aria-expanded="false"${PAGES.some(p => !p.main && p.key === current) ? ' aria-current="page"' : ""}>${icon("more")}<span>More</span></button>`;
  document.body.append(bar);
  document.documentElement.classList.add("has-tab-bar");

  // The More list: every page, with a line on what it's for.
  const sheet = document.createElement("div");
  sheet.className = "more-sheet"; sheet.hidden = true;
  sheet.innerHTML = `<div class="more-scrim"></div><nav class="more-list panel" aria-label="All pages">
    ${PAGES.map(p => `<a href="${p.href}" data-key="${p.key}"${cur(p)}>${icon(p.key)}<span><b>${p.label}</b><small>${p.desc}</small></span></a>`).join("")}</nav>`;
  document.body.append(sheet);
  const moreBtns = [...document.querySelectorAll(".more-btn")];
  let opener = null;
  function setMore(open, btn) {
    sheet.hidden = !open;
    moreBtns.forEach(b => b.setAttribute("aria-expanded", open && b === btn));
    if (open) {
      opener = btn;
      // On a computer it drops down under the More button; on a phone it rises from the bottom.
      const r = btn.getBoundingClientRect(), list = sheet.querySelector(".more-list");
      const fromBar = !!btn.closest(".tab-bar");
      sheet.classList.toggle("from-bar", fromBar);
      if (!fromBar) { list.style.top = r.bottom + 8 + "px"; list.style.right = Math.max(12, innerWidth - r.right) + "px"; }
      else list.style.top = list.style.right = "";
      (list.querySelector('[aria-current="page"]') || list.querySelector("a")).focus({ preventScroll: true });
    } else if (opener) { opener.focus({ preventScroll: true }); opener = null; }
  }
  moreBtns.forEach(b => b.addEventListener("click", e => { e.stopPropagation(); setMore(sheet.hidden, b); }));
  sheet.querySelector(".more-scrim").addEventListener("click", () => setMore(false));
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !sheet.hidden) { e.stopImmediatePropagation(); setMore(false); }
  }, true);
  addEventListener("resize", () => { if (!sheet.hidden) setMore(false); });
  // Pages can open it from a shortcut (the scanner uses M).
  window.MTGMenu = { toggle: () => setMore(sheet.hidden, moreBtns.find(b => b.offsetParent) || moreBtns[0]), isOpen: () => !sheet.hidden };

  // A dot on Maintenance when the check-up finds something wrong.
  async function checkHealth() {
    if (window.MTGMe && !window.MTGMe.perms.admin) return;   // Maintenance is for admins
    try {
      const r = await fetch("/api/health");
      if (!r.ok) return;
      const h = await r.json();
      const state = h.overall === "ok" ? "" : h.overall;
      const tip = state ? "Maintenance: " + h.problems.map(p => p.label + ": " + p.summary).join(" · ") : "";
      for (const a of document.querySelectorAll('[data-key="maintenance"]')) {
        if (state) { a.dataset.state = state; a.title = tip; } else { delete a.dataset.state; a.removeAttribute("title"); }
      }
      for (const b of moreBtns) if (state) b.dataset.state = state; else delete b.dataset.state;
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

  // With accounts on (Settings): who's logged in, at the right of the header, and only the
  // pages this account may open.
  const NEEDS = { machine: "machine", lights: "machine", maintenance: "admin" };
  fetch("/api/me").then(r => r.ok ? r.json() : null).then(s => {
    if (!s || !s.accounts) return;
    for (const [key, perm] of Object.entries(NEEDS))
      if (!s.perms[perm]) document.querySelectorAll(`[data-key="${key}"]`).forEach(a => a.hidden = true);
    window.MTGMe = s;
    if (!s.perms.admin) for (const b of moreBtns) delete b.dataset.state;
    if (!s.me) return;
    const style = document.createElement("style");
    style.textContent = `.who-chip{display:inline-flex;align-items:center;gap:7px;padding:4px 10px 4px 4px;border-radius:999px;
      background:var(--raised);color:var(--text);text-decoration:none;font-size:.85rem;font-weight:600;white-space:nowrap;flex:none}
      .who-chip:hover{background:var(--hover)}.who-chip i{display:grid;place-items:center;width:24px;height:24px;border-radius:50%;
      background:var(--accent);color:var(--on-accent);font-style:normal;font-size:.75rem}
      @media (max-width:700px){.who-chip b{display:none}.who-chip{padding:4px}}
      .site-nav [hidden],.tab-bar [hidden],.more-list [hidden]{display:none!important}`;
    document.head.append(style);
    const chip = document.createElement("a");
    chip.className = "who-chip"; chip.href = "/settings"; chip.title = `Logged in as ${s.me.name}: your account`;
    const initial = document.createElement("i"), name = document.createElement("b");
    initial.textContent = (s.me.name || s.me.username).slice(0, 1).toUpperCase(); name.textContent = s.me.name;
    chip.append(initial, name);
    header.append(chip);
  }).catch(() => {});
})();
