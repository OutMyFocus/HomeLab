// "Cards go into": whose account the machine scans into (mtgscanner/machine_account.py).
// Used by the Machine page (Start sorting) and the Scan page (on the machine's camera).
// scanFor(row, select, {note, toast, changed}) fills the picker and keeps it in step; it stays hidden while
// accounts are off. Only an admin can change it; others see whose account it is.
window.scanFor = function (row, select, opts = {}) {
  const note = opts.note, say = opts.toast || window.toast || (() => {});
  let last = null;
  const nameOf = (c) => c.name && c.name !== c.username ? `${c.name} (${c.username})` : c.username;
  const label = (c) => !c.owner ? nameOf(c) : c.name && c.name !== c.username ? `${c.name} (${c.username}, owner)` : `${c.username} (owner)`;
  function show(s) {
    last = s;
    row.hidden = !s || !s.accounts;
    if (row.hidden) return;
    select.innerHTML = "";
    for (const c of s.choices || []) {
      const o = document.createElement("option");
      o.value = c.username; o.textContent = label(c);
      select.appendChild(o);
    }
    select.value = s.user || "";
    select.disabled = !s.can_pick;
    select.title = s.can_pick ? "Whose collection the cards the machine scans and sorts are saved into"
      : "Only an admin can change whose account the machine scans into";
    if (note) {
      const who = (s.choices || []).find((c) => c.username === s.user);
      note.textContent = who && !who.owner ? `Sort runs and the machine's scanner save into ${nameOf(who)}'s cards.` : "";
    }
  }
  async function load() {
    try {
      const res = await fetch("/api/machine/account");
      if (res.ok) show(await res.json());
    } catch (e) { /* the page carries on without it */ }
  }
  select.addEventListener("change", async () => {
    const want = select.value;
    select.disabled = true;
    let data = null;
    try {
      const res = await fetch("/api/machine/account", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user: want }) });
      data = await res.json();
    } catch (e) { data = { error: "Couldn't save that." }; }
    if (data.error) {
      say(data.error);
      show(last);
      return;
    }
    show(data);
    const who = (data.choices || []).find((c) => c.username === data.user);
    say(`Saved: the machine's cards now go into ${who ? nameOf(who) : data.user}'s collection.`);
    if (opts.changed) opts.changed(data);
  });
  load();
  return { load, get: () => last };
};
