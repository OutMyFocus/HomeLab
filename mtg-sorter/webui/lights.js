// The Lights page: color, brightness and effect of the RGB light bars, and the flashes while scanning.
(() => {
  const { $, esc, toast, api } = MTG;
  const SWATCHES = [
    ["#ff7a1a", "Orange"], ["#ffffff", "White (scan light)"], ["#ffd8a8", "Warm white"], ["#ff1a1a", "Red"],
    ["#1fd65f", "Green"], ["#1a6dff", "Blue"], ["#9b3dff", "Purple"], ["#ff3da5", "Pink"],
  ];
  let state = null, saveT, pending = {};

  function save(change, now = false) {
    for (const [k, v] of Object.entries(change))   // card and events are merged one level deep
      pending[k] = v && typeof v === "object" && pending[k] ? { ...pending[k], ...v } : v;
    clearTimeout(saveT);
    saveT = setTimeout(async () => {
      const body = pending; pending = {};
      try { show(await api("/api/lights", body)); } catch (e) { toast(e.message); }
    }, now ? 0 : 150);
  }

  function build(s) {
    $("swatches").innerHTML = SWATCHES.map(([c, name]) =>
      `<button class="swatch" style="--c:${c}" data-c="${c}" title="${name}" aria-label="${name}"></button>`).join("");
    $("swatches").onclick = (e) => { const b = e.target.closest("[data-c]"); if (b) save({ color: b.dataset.c, on: true }, true); };
    $("color").oninput = () => save({ color: $("color").value });
    $("effects").innerHTML = s.effects.map(([k, name]) => `<button data-e="${k}">${esc(name)}</button>`).join("");
    $("effects").onclick = (e) => { const b = e.target.closest("[data-e]"); if (b) save({ effect: b.dataset.e }, true); };
    $("brightness").oninput = () => { $("bOut").value = $("brightness").value + "%"; save({ brightness: +$("brightness").value }); };
    $("speed").oninput = () => { $("sOut").value = $("speed").value + "%"; save({ speed: +$("speed").value }); };
    $("on").onchange = () => save({ on: $("on").checked }, true);
    $("flashes").onchange = () => save({ flashes: $("flashes").checked }, true);
    $("count").max = s.max_count;
    $("count").onchange = () => save({ count: +$("count").value }, true);
    $("cardCount").max = s.max_count;
    $("cardCount").onchange = () => save({ card: { count: +$("cardCount").value } }, true);
    $("cardOn").onchange = () => save({ card: { on: $("cardOn").checked } }, true);
    $("cardColor").oninput = () => save({ card: { color: $("cardColor").value } });
    document.querySelectorAll("[data-cc]").forEach((b) => { b.onclick = () => save({ card: { color: b.dataset.cc, on: true } }, true); });
    $("cardBrightness").oninput = () => {
      $("cbOut").value = $("cardBrightness").value + "%"; save({ card: { brightness: +$("cardBrightness").value } });
    };
    $("events").innerHTML = s.events.map(([k, label]) => `
      <div class="event">
        <label class="switch"><input type="checkbox" data-ev="${k}"><span></span></label>
        <input type="color" data-evc="${k}" aria-label="${esc(label)} color">
        <span>${esc(label)}</span>
        <button class="btn ghost" data-try="${k}">Try it</button>
      </div>`).join("");
    $("events").addEventListener("change", (e) => {
      const k = e.target.dataset.ev; if (k) save({ events: { [k]: { on: e.target.checked } } }, true);
    });
    $("events").addEventListener("input", (e) => {
      const k = e.target.dataset.evc; if (k) save({ events: { [k]: { color: e.target.value } } });
    });
    $("events").addEventListener("click", async (e) => {
      const b = e.target.closest("[data-try]");
      if (b) try { await api("/api/lights/flash", { event: b.dataset.try }); } catch (err) { toast(err.message); }
    });
    $("spiOn").onclick = async () => {
      try {
        const r = await api("/api/lights/spi-on", {});
        toast(r.message); $("reboot").hidden = false; show(r);
      } catch (e) { toast(e.message); }
    };
    $("reboot").onclick = async () => {
      if (!confirm("Reboot the Pi now? Scanning stops for about a minute.")) return;
      try { toast((await api("/api/system/reboot", {})).message); } catch (e) { toast(e.message); }
    };
    $("reset").onclick = async () => {
      if (!confirm("Go back to the starting color, brightness and flashes?")) return;
      try { show(await api("/api/lights/reset", {})); toast("Back to the starting settings."); } catch (e) { toast(e.message); }
    };
  }

  function show(s) {
    if (!state) build(s);
    state = s;
    const set = s.settings;
    $("dot").className = "dot " + (s.ok ? "ok" : "off");
    $("status").textContent = s.ok
      ? `Ready: sending to the bars on ${s.pin}. (The Pi can't tell whether they're plugged in.)`
      : s.error || "Not available.";
    $("spiRow").hidden = s.ok || !/SPI/.test(s.error || "");
    $("on").checked = set.on;
    $("flashes").checked = set.flashes;
    if (document.activeElement !== $("color")) $("color").value = set.color;
    for (const b of $("swatches").children) b.setAttribute("aria-pressed", b.dataset.c === set.color);
    for (const b of $("effects").children) b.setAttribute("aria-pressed", b.dataset.e === set.effect);
    if (document.activeElement !== $("brightness")) $("brightness").value = set.brightness;
    if (document.activeElement !== $("speed")) $("speed").value = set.speed;
    $("bOut").value = set.brightness + "%"; $("sOut").value = set.speed + "%";
    $("speed").closest(".slide").hidden = set.effect === "solid";
    if (document.activeElement !== $("count")) $("count").value = set.count;
    const card = set.card;
    $("cardOn").checked = card.on;
    if (document.activeElement !== $("cardCount")) $("cardCount").value = card.count;
    if (document.activeElement !== $("cardColor")) $("cardColor").value = card.color;
    if (document.activeElement !== $("cardBrightness")) $("cardBrightness").value = card.brightness;
    $("cbOut").value = card.brightness + "%";
    for (const [k, ev] of Object.entries(set.events)) {
      document.querySelector(`[data-ev="${k}"]`).checked = ev.on;
      const c = document.querySelector(`[data-evc="${k}"]`);
      if (document.activeElement !== c) c.value = ev.color;
    }
    $("maxAmps").textContent = s.max_amps + " A";
    $("power").textContent = `Drawing about ${s.amps} A right now. The app keeps it under ${s.max_amps} A ` +
      `(${set.count + set.card.count} LEDs at full white would be about ${s.full_white_amps} A).`;
  }

  // The preview follows exactly what's sent to the bars, a few times a second.
  async function preview() {
    try {
      const { colors } = await api("/api/lights/preview");
      const strip = $("strip");
      if (strip.children.length !== colors.length)
        strip.innerHTML = colors.map(() => "<i></i>").join("");
      colors.forEach((c, i) => { const el = strip.children[i]; el.style.background = c; el.style.setProperty("--c", c); });
      strip.classList.toggle("lit", colors.some((c) => c !== "#000000"));
    } catch (e) { /* keep the last picture */ }
    setTimeout(preview, document.hidden ? 2000 : 120);
  }

  async function refresh() {
    if (Object.keys(pending).length) return;   // a change is about to be saved
    try { show(await api("/api/lights")); } catch (e) { toast(e.message); }
  }
  refresh();
  preview();
  setInterval(refresh, 5000);   // status and the power estimate
})();
