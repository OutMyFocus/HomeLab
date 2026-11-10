// The Play page: a life counter for the table, and the games log with win rates.
(() => {
  const { $, esc, toast, api } = MTG;
  const KEY = "mtg-life";
  let LC = null, games = [], draft = null, decks = [];
  const rnd = n => 1 + Math.floor(Math.random() * n);

  // ---------- life counter (this device only) ----------
  function save() { try { localStorage.setItem(KEY, JSON.stringify(LC)); } catch (e) { } }
  function load() { try { LC = JSON.parse(localStorage.getItem(KEY) || "null"); } catch (e) { LC = null; } if (!LC || !Array.isArray(LC.players)) fresh(4, 40); }
  function fresh(n, start) {
    const old = LC && LC.players || [];
    LC = { start, players: Array.from({ length: n }, (_, i) => ({ name: old[i] ? old[i].name : "Player " + (i + 1), life: start, poison: 0, cmd: Array(n).fill(0) })) };
    save();
  }
  const isOut = p => p.life <= 0 || p.poison >= 10 || p.cmd.some(x => x >= 21);
  function renderLife() {
    $("lcN").value = LC.players.length; $("lcStart").value = LC.start;
    $("lcGrid").innerHTML = LC.players.map((p, i) => `<div class="panel life${isOut(p) ? " out" : ""}">
      <input class="nm" data-lcn="${i}" value="${esc(p.name)}" aria-label="Player name">
      <div class="big"><button data-lc="${i}" data-d="-1" aria-label="Lose 1 life">−</button><div class="total" aria-live="polite">${p.life}</div><button data-lc="${i}" data-d="1" aria-label="Gain 1 life">+</button></div>
      <div class="row5"><button class="btn ghost" data-lc="${i}" data-d="-5">−5</button><button class="btn ghost" data-lc="${i}" data-d="-10">−10</button><button class="btn ghost" data-lc="${i}" data-d="5">+5</button><button class="btn ghost" data-lc="${i}" data-d="10">+10</button></div>
      <details class="cd-more" data-lcm="${i}"${extrasOpen(i) ? " open" : ""}><summary>${extrasLabel(p)}</summary>
      <div class="cd"><span>Poison</span><button class="btn ghost" data-lp="${i}" data-d="-1">−</button><b>${p.poison}</b><button class="btn ghost" data-lp="${i}" data-d="1">+</button></div>
      ${LC.players.map((q, j) => j === i ? "" : `<div class="cd"><span>From ${esc(q.name)}</span><button class="btn ghost" data-lcd="${i}" data-from="${j}" data-d="-1">−</button><b>${p.cmd[j] || 0}</b><button class="btn ghost" data-lcd="${i}" data-from="${j}" data-d="1">+</button></div>`).join("")}
      </details>
      ${isOut(p) ? '<span class="badge bad">Out</span>' : ""}</div>`).join("");
  }
  // Poison and commander damage fold away on a phone so four players fit on the screen.
  // Each one stays open or shut as you left it, and opens by itself once it has damage on it.
  const shut = new Set(), opened = new Set();
  const phone = () => matchMedia("(max-width: 700px)").matches;
  const extrasOpen = i => {
    const p = LC.players[i];
    if (opened.has(i)) return true;
    if (shut.has(i)) return false;
    return !phone() || p.poison > 0 || p.cmd.some(x => x > 0);
  };
  function extrasLabel(p) {
    const cmd = Math.max(0, ...p.cmd), bits = [];
    if (p.poison) bits.push(`${p.poison} poison`);
    if (cmd) bits.push(`${cmd} commander`);
    return bits.length ? bits.join(" · ") : "Poison · commander";
  }
  $("lcGrid").addEventListener("toggle", e => {
    const d = e.target.closest("[data-lcm]"); if (!d) return; const i = +d.dataset.lcm;
    if (d.open) { opened.add(i); shut.delete(i); } else { shut.add(i); opened.delete(i); }
  }, true);
  $("lcGrid").onclick = e => {
    const b = e.target.closest("button"); if (!b) return; const d = +b.dataset.d || 0;
    if (b.dataset.lc != null) LC.players[+b.dataset.lc].life += d;
    else if (b.dataset.lp != null) { const p = LC.players[+b.dataset.lp]; p.poison = Math.max(0, p.poison + d); }
    else if (b.dataset.lcd != null) { const p = LC.players[+b.dataset.lcd], j = +b.dataset.from, was = p.cmd[j] || 0, now = Math.max(0, was + d); p.life -= now - was; p.cmd[j] = now; }
    else return;
    save(); renderLife();
  };
  $("lcGrid").onchange = e => { const t = e.target.closest("[data-lcn]"); if (!t) return; LC.players[+t.dataset.lcn].name = t.value.trim() || "Player"; save(); renderLife(); };
  $("lcReset").onclick = () => { fresh(+$("lcN").value, +$("lcStart").value); shut.clear(); opened.clear(); renderLife(); $("lcRoll").textContent = ""; };
  $("lcN").onchange = $("lcStart").onchange = $("lcReset").onclick;
  $("lcFirst").onclick = () => $("lcRoll").textContent = `${LC.players[rnd(LC.players.length) - 1].name} goes first`;
  $("lcD6").onclick = () => $("lcRoll").textContent = `d6: ${rnd(6)}`;
  $("lcD20").onclick = () => $("lcRoll").textContent = `d20: ${rnd(20)}`;
  $("lcCoin").onclick = () => $("lcRoll").textContent = rnd(2) === 1 ? "Heads" : "Tails";
  // Start the log form with the players at the table, and whoever is still in as the winner.
  $("lcLog").onclick = () => {
    const alive = LC.players.findIndex(p => !isOut(p));
    draft = { players: LC.players.map(p => ({ name: p.name, deck: "" })), winner: Math.max(0, alive) };
    renderForm(); $("gPlayers").scrollIntoView({ behavior: "smooth", block: "center" });
  };

  // ---------- games log ----------
  function blank() { return { players: [{ name: "", deck: "" }, { name: "", deck: "" }], winner: 0 }; }
  function renderForm() {
    if (!draft) draft = blank();
    if (!$("gDate").value) $("gDate").value = new Date().toLocaleDateString("en-CA");
    $("gPlayers").innerHTML = draft.players.map((p, i) => `<div class="prow">
      <label class="sub" title="Winner"><input type="radio" name="gWin" value="${i}" ${draft.winner === i ? "checked" : ""}> Won</label>
      <input type="text" class="field" data-gn="${i}" placeholder="Player ${i + 1}" value="${esc(p.name)}" list="gNames" aria-label="Player ${i + 1}">
      <input type="text" class="field grow" data-gd="${i}" placeholder="Deck or commander" value="${esc(p.deck)}" list="gDecks" aria-label="Deck">
      ${draft.players.length > 2 ? `<button class="link-btn" data-grm="${i}" title="Remove player">×</button>` : "<span></span>"}</div>`).join("")
      + `<datalist id="gNames">${[...new Set(games.flatMap(g => g.players.map(p => p.name)))].map(n => `<option value="${esc(n)}">`).join("")}</datalist>`;
  }
  $("gPlayers").oninput = e => {
    const t = e.target;
    if (t.name === "gWin") draft.winner = +t.value;
    if (t.dataset.gn != null) draft.players[+t.dataset.gn].name = t.value;
    if (t.dataset.gd != null) draft.players[+t.dataset.gd].deck = t.value;
  };
  $("gPlayers").onclick = e => { const b = e.target.closest("[data-grm]"); if (!b) return; draft.players.splice(+b.dataset.grm, 1); if (draft.winner >= draft.players.length) draft.winner = 0; renderForm(); };
  $("gAddP").onclick = () => { if (draft.players.length < 8) { draft.players.push({ name: "", deck: "" }); renderForm(); } };
  $("gSave").onclick = async () => {
    const players = draft.players.map((p, i) => ({ name: p.name.trim() || `Player ${i + 1}`, deck: p.deck.trim() }));
    try {
      show(await api("/api/games/add", { date: $("gDate").value, turns: $("gTurns").value, notes: $("gNotes").value, winner: draft.winner, players }));
      toast("Game saved"); draft = null; $("gTurns").value = ""; $("gNotes").value = ""; renderForm();
    } catch (e) { toast(e.message); }
  };
  const bars = rows => rows.length ? rows.slice(0, 12).map(r => `<div class="r"><span>${esc(r.label)}</span><span class="tr"><i style="width:${Math.round(r.wins / r.games * 100)}%"></i></span><span class="v">${r.wins}/${r.games} · ${Math.round(r.wins / r.games * 100)}%</span></div>`).join("") : '<p class="sub">No games yet.</p>';
  function show(js) {
    games = js.games || [];
    $("gCount").textContent = games.length ? `${games.length} game${games.length === 1 ? "" : "s"}` : "";
    $("gByPlayer").innerHTML = bars(js.stats.players); $("gByDeck").innerHTML = bars(js.stats.decks);
    $("gList").innerHTML = games.length ? games.map(g => `<div class="game">
        <div>${g.players.map((p, i) => `<span class="${g.winner === i ? "win" : ""}">${esc(p.name)}${p.deck ? ` <span class="sub">(${esc(p.deck)})</span>` : ""}${g.winner === i ? " 🏆" : ""}</span>`).join(" · ")}</div>
        <div class="meta"><span>${esc(g.date)}</span>${g.turns ? `<span>${g.turns} turns</span>` : ""}${g.notes ? `<span>${esc(g.notes)}</span>` : ""}<button class="link-btn" data-gdel="${esc(g.id)}">Delete</button></div></div>`).join("")
      : '<p class="results-empty">No games logged yet. Log one after your next pod.</p>';
  }
  $("gList").onclick = async e => {
    const b = e.target.closest("[data-gdel]"); if (!b) return;
    if (b.dataset.sure !== "1") { b.dataset.sure = "1"; b.textContent = "Delete for good?"; return; }
    try { show(await api("/api/games/delete", { id: b.dataset.gdel })); toast("Game deleted"); } catch (err) { toast(err.message); }
  };

  load(); renderLife(); renderForm();
  api("/api/games").then(js => { show(js); renderForm(); }).catch(e => toast(e.message));
  api("/api/decks").then(js => { decks = js.decks || []; $("gDecks").innerHTML = decks.map(d => `<option value="${esc(d.name)}">`).join(""); }).catch(() => { });
})();
