// The Machine health page: everything the sorter reports (GET /api/machine/health), every 3 s while Live is on.
(() => {
  const { $, esc, toast, api } = MTG;
  const STATE_WORD = { ok: "fine", warn: "check", bad: "problem", off: "off" };
  const RESULT = { landed: "landed", none: "nothing came out", over: "went over the stop", stuck: "stuck in the slot", crowded: "two cards / a hand" };
  let timer = null, last = null, saving = false;

  const ago = (t) => {
    if (!t) return "never";
    const s = Math.max(0, Date.now() / 1000 - t);
    if (s < 60) return `${Math.round(s)} s ago`;
    if (s < 3600) return `${Math.round(s / 60)} min ago`;
    if (s < 86400) return `${Math.floor(s / 3600)} h ${Math.round((s % 3600) / 60)} min ago`;
    return `${Math.round(s / 86400)} days ago`;
  };
  const clock = (t) => new Date(t * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
  const span = (s) => {
    if (s == null) return "–";
    if (s < 3600) return `${Math.round(s / 60)} min`;
    if (s < 86400) return `${Math.floor(s / 3600)} h ${Math.round((s % 3600) / 60)} m`;
    return `${Math.floor(s / 86400)} d ${Math.round((s % 86400) / 3600)} h`;
  };
  const dot = (id, state) => { const el = $(id); el.className = "dot " + (state || ""); };
  const worst = (...states) => states.includes("bad") ? "bad" : states.includes("warn") ? "warn" : states.includes("ok") ? "ok" : "";
  const areaState = (r, area) => worst(...(r.problems || []).filter((p) => p.area === area).map((p) => p.state)) || "ok";

  function hero(r) {
    const n = (r.problems || []).length;
    dot("heroDot", r.overall);
    if (r.reachable === false) {
      $("heroTitle").textContent = "Can't reach the sorter's Pi";
    } else {
      $("heroTitle").textContent = n ? `${n} thing${n === 1 ? "" : "s"} to look at` : "Everything looks fine";
    }
    const where = r.server ? ` · through the server, from ${r.server.pi_url}` : "";
    $("heroSub").textContent = `Updated ${clock(r.generated_at)}${where}` + (r.since ? ` · record kept since ${clock(r.since)}` : "");
    $("problems").innerHTML = (r.problems || []).map((p) => `<li><span class="dot ${p.state}"></span><span>${esc(p.text)}</span>${p.fix ? `<span class="fix">${esc(p.fix)}</span>` : ""}</li>`).join("");
  }

  function pi(r) {
    const p = r.pi || {};
    const st = areaState(r, "pi");
    dot("piDot", st);
    $("piTag").textContent = p.model ? p.model.replace("Raspberry Pi", "Pi").replace(/ Model B.*$/, "") : (p.on_pi ? "Pi" : "not a Pi");
    $("piTag").className = "tag";
    const t = p.temperature_c;
    $("temp").textContent = t == null ? "–" : `${Math.round(t)} °C`;
    $("tempStat").className = "stat " + (t == null ? "" : t >= 80 ? "bad" : t >= 70 ? "warn" : "ok");
    $("thermMark").style.left = t == null ? "0" : `${Math.min(100, Math.max(0, (t - 30) / 60 * 100))}%`;
    $("volts").textContent = p.supply_volts == null ? "–" : `${p.supply_volts.toFixed(2)} V`;
    $("voltStat").className = "stat " + (p.supply_volts == null ? "" : p.supply_volts < 4.8 ? "bad" : p.supply_volts < 4.95 ? "warn" : "ok");
    $("uptime").textContent = span(p.uptime_s);
    $("throttle").innerHTML = (p.throttled || []).length
      ? p.throttled.map((x) => `<span class="tag ${/now/.test(x) ? "bad" : "warn"}">${esc(x)}</span>`).join("")
      : (p.throttled_raw != null ? `<span class="tag ok">never slowed down</span>` : "");
    const mem = p.memory ? `${(p.memory.free_mb / 1024).toFixed(1)} of ${(p.memory.total_mb / 1024).toFixed(1)} GB free` : "–";
    const disk = p.disk ? `${p.disk.free_gb} of ${p.disk.total_gb} GB free` : "–";
    $("piFacts").innerHTML = `<dt>Name</dt><dd>${esc(p.hostname || "–")}</dd><dt>Memory</dt><dd>${esc(mem)}</dd>
      <dt>Storage</dt><dd>${esc(disk)}</dd><dt>Version</dt><dd>${esc(p.version || "–")}</dd>`;
  }

  function camera(r) {
    const c = r.camera || {};
    dot("camDot", c.state === "off" ? "" : c.state);
    $("camSummary").textContent = c.summary || "–";
    $("camFps").textContent = c.fps == null ? "–" : c.fps.toFixed(0);
    $("camAge").textContent = c.frame_age_ms == null ? "–" : c.frame_age_ms < 1000 ? `${c.frame_age_ms} ms` : `${(c.frame_age_ms / 1000).toFixed(1)} s`;
    $("camAgeStat").className = "stat " + (c.frame_age_ms == null ? "" : c.frame_age_ms > 3000 ? "bad" : "ok");
    $("camSize").textContent = Array.isArray(c.size) ? `${c.size[0]}×${c.size[1]}` : "–";
    $("camFix").textContent = c.state !== "ok" && c.fix ? c.fix : "";
  }

  function servos(r) {
    const list = r.servos || [];
    const [lo, hi] = (r.machine || {}).safe_range || [10, 170];
    $("safeRange").textContent = `${lo}-${hi}°`;
    const board = (r.machine || {}).servo_board || {};
    const st = board.ok === false ? "bad" : areaState(r, "servos");
    dot("servoDot", st);
    $("servoTag").textContent = board.ok === false ? "board not found" : board.ok ? "board found" : "";
    $("servoTag").className = "tag " + (board.ok === false ? "bad" : board.ok ? "ok" : "");
    const pct = (a) => `${Math.min(100, Math.max(0, a / 180 * 100))}%`;
    $("servos").innerHTML = list.length ? list.map((s) => {
      const marks = Object.entries(s.positions || {}).map(([pos, a]) =>
        `<span class="mark ${a < lo || a > hi ? "out" : ""}" style="left:${pct(a)}" title="${esc(pos)} ${a}°"><i></i><span>${esc(pos)} ${Math.round(a)}°</span></span>`).join("");
      const at = s.angle != null ? s.angle : s.last_move_angle != null ? s.last_move_angle : s.last_sent;
      const now = at == null ? "" : `<span class="now ${s.angle == null ? "relaxed" : ""}" style="left:${pct(at)}" title="${s.angle == null ? "let go, last sent" : "now"} ${Math.round(at)}°"></span>`;
      const where = s.angle != null ? `holding at <b>${Math.round(s.angle)}°</b>` : at != null ? `let go (last sent ${Math.round(at)}°)` : "not moved yet";
      return `<div class="servo">
        <span><span class="name">${esc(s.name)}</span> <span class="sub">channel ${s.channel}</span><br><span class="sub">${where}</span></span>
        <span class="when">last move<br>${esc(ago(s.last_move_at))}</span>
        <div class="track"><div class="rail"></div>${marks}${now}</div>
        ${s.warnings.length ? `<p class="warns">${s.warnings.map(esc).join(" · ")}</p>` : ""}
      </div>`;
    }).join("") : `<p class="empty">No servos reported.</p>`;
  }

  function feeder(r) {
    const f = r.feeder || {};
    const st = f.ok === false ? "bad" : areaState(r, "feeder");
    dot("feedDot", st);
    $("feedTag").textContent = f.running ? "turning now" : f.ok ? `ready, GPIO ${(f.pins || []).join(" + ")}` : (f.error ? "not available" : "");
    $("feedTag").className = "tag " + (f.running ? "warn" : f.ok ? "ok" : f.ok === false ? "bad" : "");
    const feeds = f.feeds || [];
    $("landed").textContent = f.landed_share == null ? "–" : `${Math.round(f.landed_share * 100)}%`;
    $("landStat").className = "stat " + (f.landed_share == null ? "" : f.landed_share >= 0.9 ? "ok" : f.landed_share >= 0.6 ? "warn" : "bad");
    $("pulseCount").textContent = (r.counts || {}).pulses ?? "–";
    const jams = (r.counts || {}).jams ?? 0;
    $("jams").textContent = jams;
    $("jamStat").className = "stat " + (jams ? "bad" : "ok");
    $("feeds").innerHTML = feeds.length
      ? feeds.map((x) => `<i class="${esc(x.result)}" title="${esc(clock(x.at))}: ${esc(RESULT[x.result] || x.result)}${x.landed_ms != null ? `, in ${(x.landed_ms / 1000).toFixed(2)} s` : ""}"></i>`).join("")
      : `<span class="empty">No cards fed since the app started.</span>`;
    const pulses = (f.pulses || []).slice(0, 6);
    $("pulses").innerHTML = pulses.length ? pulses.map((p) => `<li><span class="t">${esc(clock(p.at))}</span>
      <span>Motor ${p.direction === "back" ? "backwards" : "forwards"}, ${p.seconds} s at ${Math.round(p.speed * 100)}%</span><span class="r">${esc(ago(p.at))}</span></li>`).join("")
      : `<li><span></span><span class="empty">No motor pulses yet.</span><span></span></li>`;
    const s = f.settings || {};
    $("feedSettings").textContent = f.error && f.ok === false ? f.error
      : `Saved: speed ${Math.round((s.speed || 0) * 100)}%, push ${s.push ?? "–"} s after landing, back-off ${s.backoff ?? "–"} s, reverse ${s.reverse ? "on" : "off"}.`;
  }

  function bins(r) {
    const b = r.bins || {};
    const fitted = b.fitted || {};
    if (!saving) { $("fitFull").checked = !!fitted.full; $("fitSeated").checked = !!fitted.seated; }
    const any = fitted.full || fitted.seated;
    dot("binDot", !any ? "" : areaState(r, "bins"));
    $("bins").innerHTML = (b.bins || []).map((x) => {
      const full = x.full == null ? null : x.full, seated = x.seated == null ? null : x.seated;
      const known = full != null || seated != null;
      const state = !known ? "off" : (full || seated === false) ? "warn" : "ok";
      const line1 = full == null ? (fitted.full ? "full sensor: no reading" : "full sensor: not connected") : full ? "FULL" : "room left";
      const line2 = seated == null ? (fitted.seated ? "no reading" : "in place: not connected") : seated ? "in place" : "PULLED OUT";
      return `<div class="bin ${state}"><b>Bin ${x.bin}</b><small>${esc(line1)}</small><small>${esc(line2)}</small>
        <small>GPIO${x.full_pin ?? "–"} · GPIO${x.seated_pin ?? "–"}</small></div>`;
    }).join("");
  }

  function scans(r) {
    const s = r.scans || {};
    const run = s.run || {};
    const c = run.counts || {};
    const st = areaState(r, "scans") === "ok" ? areaState(r, "run") : areaState(r, "scans");
    dot("scanDot", st);
    $("scanTag").textContent = run.running ? "sort run going" : `${s.saved_this_session ?? 0} saved since start`;
    $("scanTag").className = "tag " + (run.running ? "ok" : "");
    const read = (c.saved || 0), unsure = (c.unsure || 0) + (c.unknown || 0);
    $("runStats").innerHTML = run.cards ? `
      <div class="stat ok"><b>${read}</b><small>read and saved</small></div>
      <div class="stat ${unsure ? "warn" : ""}"><b>${unsure}</b><small>not sure / unknown</small></div>
      <div class="stat ${(c.stuck || 0) + (c.crowded || 0) + (c.double || 0) ? "bad" : ""}"><b>${(c.stuck || 0) + (c.crowded || 0) + (c.double || 0) + (c.over || 0)}</b><small>jams, doubles, overs</small></div>` : "";
    $("runLine").textContent = run.running ? `Sort run going: ${run.cards} cards so far.`
      : run.done ? `Last sort run: ${run.cards} cards, ended: ${run.done}.` : "No sort run since the app started.";
    const mis = s.misreads || [];
    $("misreads").innerHTML = mis.length ? mis.map((m) => `<li><span class="dot ${/stuck|crowded|double/.test(m.status) ? "bad" : "warn"}"></span>
      <span>Card ${m.n}: ${esc(m.status)}${m.name ? ` (${esc(m.name)})` : ""}</span><span class="r">${m.bin != null ? "bin " + m.bin : "not dropped"}</span></li>`).join("")
      : `<li><span></span><span class="empty">None in the last run.</span><span></span></li>`;
    const rec = (s.recent || []).slice(0, 8);
    $("recent").innerHTML = rec.length ? rec.map((x) => `<li><span class="t">${esc(x.time || "")}</span>
      <span>${esc(x.name)} <span class="sub">${esc(x.set || "")} ${esc(x.number || "")}${x.foil ? " · foil" : ""}</span></span>
      <span class="r">${x.price != null ? "$" + Number(x.price).toFixed(2) : ""}${x.bin != null ? ` · bin ${x.bin}` : ""}</span></li>`).join("")
      : `<li><span></span><span class="empty">No cards saved since the app started.</span><span></span></li>`;
  }

  function lights(r) {
    const l = r.lights, m = r.machine || {};
    dot("lightDot", l && l.ok ? "ok" : "");
    const relay = m.relay ? (m.relay.on ? "on (servos, feeder and lights have 5 V)" : m.relay.error ? "error: " + m.relay.error : "off / not wired") : "–";
    $("lightFacts").innerHTML = l ? `
      <dt>Light bars</dt><dd>${l.ok ? "SPI on, sending on " + esc(l.pin) : esc(l.error || "not available")}</dd>
      <dt>Status lights</dt><dd>${l.on && l.count ? `<span class="swatch-dot" style="background:${esc(l.color)}"></span>${esc(l.effect)}, ${l.brightness}%, ${l.count} LEDs` : "off"}</dd>
      <dt>Card light</dt><dd>${l.card_on && l.card_count ? `<span class="swatch-dot" style="background:${esc(l.card_color)}"></span>on, ${l.card_count} LEDs` : "off"}</dd>
      <dt>Drawing</dt><dd>about ${l.amps ?? "–"} A${l.dimmed != null ? `, dimmed to ${l.dimmed}% for a run` : ""}</dd>
      <dt>Power relay</dt><dd>${esc(relay)}</dd>
      <dt>Machine</dt><dd>${esc((m.model || "").toUpperCase() || "–")}${m.busy ? ` · busy: ${esc(m.busy)}` : ""}</dd>` : `<dt>Light bars</dt><dd>not reported</dd>`;
  }

  function events(r) {
    const ev = r.events || [];
    const bad = ev.filter((e) => e.level === "bad").length;
    $("eventTag").textContent = bad ? `${bad} error${bad === 1 ? "" : "s"}` : `${ev.length} events`;
    $("eventTag").className = "tag " + (bad ? "bad" : "");
    $("events").innerHTML = ev.length ? ev.slice(0, 40).map((e) => `<li><span class="dot ${e.level === "info" ? "" : e.level}"></span>
      <span>${esc(e.text)}</span><span class="r">${esc(clock(e.at))}</span></li>`).join("")
      : `<li><span></span><span class="empty">Nothing since the app started: no jams, no errors.</span><span></span></li>`;
  }

  function show(r) {
    last = r;
    hero(r);
    if (r.reachable === false) { $("json").textContent = JSON.stringify(r, null, 1); return; }
    for (const f of [pi, camera, servos, feeder, bins, scans, lights, events]) {
      try { f(r); } catch (e) { console.error(e); }
    }
    if ($("json").closest("details").open) $("json").textContent = JSON.stringify(r, null, 1);
  }

  async function refresh() {
    clearTimeout(timer);
    try { show(await api("/api/machine/health")); } catch (e) { $("heroTitle").textContent = e.message; dot("heroDot", "bad"); }
    if ($("live").checked) timer = setTimeout(refresh, document.hidden ? 15000 : 3000);
  }

  async function fit(kind, on) {
    saving = true;
    try {
      show(await api("/api/machine/health/sensors", { kind, fitted: on }));
      toast(on ? "Saved: the sensors will be read" : "Saved: shown as not connected");
    } catch (e) { toast(e.message); } finally { saving = false; }
  }
  $("fitFull").onchange = () => fit("full", $("fitFull").checked);
  $("fitSeated").onchange = () => fit("seated", $("fitSeated").checked);
  $("live").onchange = () => { if ($("live").checked) refresh(); else clearTimeout(timer); };
  $("json").closest("details").ontoggle = () => { if (last) $("json").textContent = JSON.stringify(last, null, 1); };
  document.addEventListener("visibilitychange", () => { if (!document.hidden && $("live").checked) refresh(); });
  refresh();
})();
