// Applies the look picked in the scanner's Customize panel (theme, accent, bin colors,
// font, corners, spacing) to the other pages. Saved in this browser only, by app.js.
(() => {
  const FONTS = {
    sans: '"Inter", "Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, "Helvetica Neue", Arial, sans-serif',
    rounded: 'ui-rounded, "SF Pro Rounded", "Nunito", "Quicksand", "Varela Round", "Segoe UI Variable Text", "Segoe UI", sans-serif',
    serif: '"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif',
    mono: 'ui-monospace, "Cascadia Code", "SF Mono", Menlo, Consolas, monospace',
  };
  function onColor(hex) {
    const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(c => c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4);
    return .2126 * r + .7152 * g + .0722 * b > .42 ? "#121417" : "#ffffff";
  }
  let look = {};
  try { look = JSON.parse(localStorage.getItem("mtg-scanner-look") || "{}") || {}; } catch (e) {}
  const root = document.documentElement, css = root.style;
  if (look.theme) root.dataset.theme = look.theme;
  if (look.density) root.dataset.density = look.density;
  if (/^#[0-9a-f]{6}$/i.test(look.accent || "")) { css.setProperty("--accent", look.accent); css.setProperty("--on-accent", onColor(look.accent)); }
  (look.bins || []).forEach((c, i) => { if (/^#[0-9a-f]{6}$/i.test(c)) { css.setProperty(`--bin${i}`, c); css.setProperty(`--on-bin${i}`, onColor(c)); } });
  if (FONTS[look.font]) css.setProperty("--font", FONTS[look.font]);
  if (look.radius != null) css.setProperty("--radius", look.radius + "px");
  if (look.size) css.fontSize = look.size + "px";
  for (const k of ["glow", "motion", "keys"]) if (look[k] === false) root.classList.add("no-" + k);
})();
