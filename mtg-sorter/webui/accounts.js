// The Settings page's accounts: turning them on, your own account, and (for admins) the
// people who can log in and what each may do. See mtgscanner/accounts.py.
(() => {
  const { $, esc, toast, api } = MTG;
  const PERM_LABELS = { scan: "Scan", edit: "Edit", machine: "Machine", admin: "Admin" };
  const ROLE_OF = perms => {
    const p = [...perms].sort().join(",");
    return p === "admin,edit,machine,scan" ? "admin" : p === "edit,scan" ? "member" : p === "" ? "viewer" : "custom";
  };
  let me = null;

  async function load() {
    const s = await api("/api/me");
    me = s;
    $("acctSetup").hidden = s.accounts || !s.perms.admin;
    $("acctMe").hidden = !s.accounts;
    $("acctPeople").hidden = !(s.accounts && s.perms.admin);
    // With accounts on, the login does the PIN's job, and some panels are for some people only.
    if (s.accounts) $("pinPanel").hidden = true;
    $("pricesPanel").hidden = !s.perms.admin;
    $("vaultPanel").hidden = !s.perms.edit;
    if (s.accounts && s.me) {
      const role = ROLE_OF(s.me.perms);
      $("meLine").innerHTML = `Logged in as <b>${esc(s.me.name)}</b> (${esc(s.me.username)})` +
        (s.me.owner ? ", the owner, with every permission." : role === "custom" ? `, allowed to: ${s.me.perms.map(p => PERM_LABELS[p]).join(", ") || "look only"}.` : `, ${role}.`);
    } else if (s.accounts && s.local) {
      $("meLine").textContent = "Opened on the sorter itself, which counts as the owner. Log in from another device to use your own account.";
      for (const id of ["pwGo", "outHere", "outAll"]) $(id).disabled = true;
    }
    if (s.accounts && s.perms.admin) loadPeople();
  }

  // ---------- turning accounts on ----------
  $("suGo").onclick = async () => {
    const user = $("suUser").value.trim().toLowerCase(), pass = $("suPass").value;
    if (!user) return toast("Pick a username");
    if (pass !== $("suPass2").value) return toast("The two passwords don't match");
    if (!confirm(`Turn on accounts? From now on everyone logs in. You'll be "${user}", the owner, and every card here stays yours.`)) return;
    $("suGo").disabled = true; $("suMsg").textContent = "Saving a backup first…";
    try {
      const r = await api("/api/accounts/setup", { username: user, password: pass, name: $("suName").value.trim() });
      toast("Accounts are on. You're the owner");
      $("suMsg").textContent = r.backup ? `Backup saved as ${r.backup}.` : "";
      load();
    } catch (e) { $("suMsg").textContent = e.message; $("suGo").disabled = false; }
  };

  // ---------- your own account ----------
  $("pwGo").onclick = async () => {
    if ($("pwNew").value !== $("pwNew2").value) return toast("The two new passwords don't match");
    try {
      await api("/api/password", { old: $("pwOld").value, new: $("pwNew").value });
      for (const id of ["pwOld", "pwNew", "pwNew2"]) $(id).value = "";
      toast("Password changed. Your other devices have to log in again");
    } catch (e) { toast(e.message); }
  };
  $("outHere").onclick = async () => { await api("/api/logout", {}); location.href = "/login"; };
  $("outAll").onclick = async () => {
    try { await api("/api/logout/everywhere", {}); toast("Logged out everywhere else"); } catch (e) { toast(e.message); }
  };

  // ---------- people and permissions (admins) ----------
  async function loadPeople() {
    const s = await api("/api/accounts");
    $("people").innerHTML = s.users.map(u => {
      const role = ROLE_OF(u.perms), mine = u.username === s.me;
      const tags = [u.owner && "Owner", mine && "You"].filter(Boolean).map(t => `<span class="pill acct-tag">${t}</span>`).join("");
      const perms = s.perms.map(p => `<label class="perm"><input type="checkbox" data-perm="${p}" ${u.perms.includes(p) ? "checked" : ""}
          ${u.owner || (p !== "admin" && u.perms.includes("admin")) ? "disabled" : ""}><span>${PERM_LABELS[p]}</span></label>`).join("");
      return `<div class="person" data-user="${esc(u.username)}">
        <div class="person-head"><b>${esc(u.name)}</b><span class="sub">${esc(u.username)}</span>${tags}</div>
        <div class="person-perms">
          <select class="field role" aria-label="Role for ${esc(u.name)}" ${u.owner ? "disabled" : ""}>
            ${["admin", "member", "viewer"].map(r => `<option value="${r}" ${role === r ? "selected" : ""}>${r[0].toUpperCase() + r.slice(1)}</option>`).join("")}
            ${role === "custom" ? '<option value="custom" selected>Custom</option>' : ""}
          </select>
          ${perms}
        </div>
        <div class="person-actions">
          <button class="btn ghost" data-act="password">New password</button>
          ${u.owner || mine ? "" : '<button class="btn ghost danger" data-act="remove">Remove</button>'}
        </div>
      </div>`;
    }).join("");
    renderInvites(s.invites || []);
  }

  // ---------- invite links ----------
  const until = t => new Date(t * 1000).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  function renderInvites(list) {
    $("invites").innerHTML = list.length ? `<b class="sub">Open invites</b>` + list.map(i => `<div class="invite" data-id="${esc(i.id)}">
        <span><b>${esc(i.note || (i.role === "member" ? "Member invite" : "Viewer invite"))}</b>
        <small class="sub">${i.role} · ${i.used.length} of ${i.uses} used${i.used.length ? " (" + i.used.map(esc).join(", ") + ")" : ""} · runs out ${until(i.expires)}</small></span>
        <button class="btn ghost danger" data-cancel>Cancel</button></div>`).join("") : "";
  }
  $("invGo").onclick = async () => {
    try {
      const r = await api("/api/accounts/invite", { role: $("invRole").value, uses: +$("invUses").value, days: +$("invDays").value, note: $("invNote").value.trim() });
      $("invLink").value = location.origin + r.path;
      $("invMade").hidden = false; $("invNote").value = "";
      $("invShare").hidden = !navigator.share;
      $("invLink").select();
      renderInvites(r.invites);
    } catch (e) { toast(e.message); }
  };
  $("invCopy").onclick = async () => { await MTG.copy($("invLink").value); toast("Invite link copied"); };
  $("invShare").onclick = () => navigator.share?.({ title: "Join my SortR", text: "Here's your invite to my MTG card sorter:", url: $("invLink").value }).catch(() => {});
  $("invites").addEventListener("click", async e => {
    const b = e.target.closest("[data-cancel]"); if (!b) return;
    if (!confirm("Cancel this invite? Nobody else can join with it.")) return;
    try { renderInvites((await api("/api/accounts/invite/cancel", { id: b.closest(".invite").dataset.id })).invites); toast("Invite cancelled"); }
    catch (err) { toast(err.message); }
  });

  async function change(username, body, done) {
    try { await api("/api/accounts/update", { username, ...body }); toast(done); }
    catch (e) { toast(e.message); }
    loadPeople();
  }
  $("people").addEventListener("change", e => {
    const row = e.target.closest(".person"); if (!row) return;
    const user = row.dataset.user;
    if (e.target.matches(".role")) {
      if (e.target.value !== "custom") change(user, { role: e.target.value }, "Role changed");
    } else if (e.target.dataset.perm) {
      const perms = [...row.querySelectorAll("[data-perm]")].filter(c => c.checked).map(c => c.dataset.perm);
      change(user, { perms }, "Permissions changed");
    }
  });
  $("people").addEventListener("click", async e => {
    const b = e.target.closest("[data-act]"); if (!b) return;
    const user = b.closest(".person").dataset.user;
    if (b.dataset.act === "password") {
      const pw = prompt(`New password for ${user} (at least 6 characters). They'll be logged out on their devices.`);
      if (pw) change(user, { password: pw }, `Password changed for ${user}`);
    } else if (b.dataset.act === "remove") {
      if (!confirm(`Remove ${user}? They won't be able to log in. Their cards stay on the server, and adding "${user}" again brings them back.`)) return;
      try { await api("/api/accounts/remove", { username: user }); toast(`${user} removed`); } catch (err) { toast(err.message); }
      loadPeople();
    }
  });
  $("addGo").onclick = async () => {
    try {
      const r = await api("/api/accounts/add", { name: $("addName").value.trim(), username: $("addUser").value.trim().toLowerCase(),
        password: $("addPass").value, role: $("addRole").value });
      for (const id of ["addName", "addUser", "addPass"]) $(id).value = "";
      toast(`Added ${r.added}`);
      loadPeople();
    } catch (e) { toast(e.message); }
  };

  load().catch(e => toast(e.message));
})();
