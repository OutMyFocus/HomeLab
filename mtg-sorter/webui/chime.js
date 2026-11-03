// A short chime for alerts, made in the browser (no sound file to download).
window.mtgChime = (kind = "big") => {
  try {
    const ctx = window._mtgAudio || (window._mtgAudio = new (window.AudioContext || window.webkitAudioContext)());
    if (ctx.state === "suspended") ctx.resume();
    const notes = kind === "wish" ? [659.25, 880, 1174.66] : [523.25, 659.25, 783.99, 1046.5];
    notes.forEach((f, i) => {
      const o = ctx.createOscillator(), g = ctx.createGain(), t = ctx.currentTime + i * 0.11;
      o.type = "sine"; o.frequency.value = f;
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.18, t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.35);
      o.connect(g).connect(ctx.destination); o.start(t); o.stop(t + 0.4);
    });
  } catch (e) {}
};
