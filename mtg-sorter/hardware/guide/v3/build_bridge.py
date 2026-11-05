#!/usr/bin/env python3
"""Build the front bridge swap guide: BRIDGE_V3.md and bridge_v3_guide.html (pictures from
bridge_render.py)."""
import html, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
import importlib.util
_spec = importlib.util.spec_from_file_location("chute_v3_build", os.path.join(HERE, "build.py"))
g = importlib.util.module_from_spec(_spec)   # same look and helpers as the chute v3 guide
_spec.loader.exec_module(g)

BITS = [
    "The new `enc_bridge_front` and the red `enc_bridge_cap` (plate 2 of `MTG_Sorter_Chute_v3.3mf`).",
    "The 4 screws and 2 splices from the old front bridge, with their 8 small screws. Two spare splices are on plate 2 too, in case yours were glued.",
    "2 × M3 × 12 for the cap.",
    "A **stubby screwdriver** (under about 9 cm) that fits the splice screws, for working under the bridge through the middle drawer's opening.",
]
SECTIONS = [
    ("out", "Old front bridge out", "You don't need to take the whole mechanism out of the box. The back half of the bridge, the bed walls, "
     "the feeder and the tilt servo all stay where they are.", [
        ("bridge_1_compare", "What's changing", [
            "Left: the old front bridge, a thin frame with the tray's axle in a 6 mm plate.",
            "Right: the new one. The 10 mm front wall has a **slot** the axle drops into, and the red **cap** screws on top to close it.",
            "The new one has the same footprint and screw holes, so it fits exactly where the old one was.",
        ], [], []),
        ("bridge_2_screws", "Make room, then take out 4 screws", [
            "Lift off the two **front deck tiles**, and pull out **all three drawers**.",
            "Unscrew the tilt servo's horn from the tray's back plate and lift the old tray out (if it isn't out already).",
            "Take out the **4 screws** that hold the front bridge down onto the tops of the two dividers, two per side (the arrows).",
            "Leave the two screws further back alone. They hold the back half.",
        ], [], ["screwdriver"]),
        ("bridge_3_splices", "Splice screws, from underneath", [
            "This picture looks **up** at the underside. Two small plates (splices) join the front and back halves under the seam, 4 small screws each.",
            "Reach in through the empty **middle drawer opening** with the stubby screwdriver. The splices are about 13 cm in, either side of the middle.",
            "Take out all 8 screws and keep the splices.",
            "Glued instead of screwed? Pry the front half off and use the two spare splices from plate 2 later.",
        ], [], ["stubby screwdriver"]),
        ("bridge_4_slide_off", "Slide it forward and lift it out", [
            "The bed walls sit about 2 mm over the front bridge's back corners. So slide the front bridge **forward** about 3 mm first, then lift it straight up and out.",
            "If a wire runs through the old opening, unhook it so it doesn't snag.",
        ], [], []),
    ]),
    ("in", "New front bridge in", "", [
        ("bridge_5_slide_on", "Lower it in and slide it back", [
            "Hold the new bridge with its **tall wall at the front** (towards the drawers) and the slot at the top.",
            "Lower it onto the divider tops about 3 mm in front of where it goes, then slide it **back** until it meets the back half. Its back corners go under the bed walls.",
            "The 4 screw holes in its sides should now sit over the holes in the divider tops.",
        ], ["enc_bridge_front"], []),
        ("bridge_6_splices_on", "Splices back on, from underneath", [
            "Looking up again. Hold each splice up into its shallow pocket across the seam and drive its 4 small screws in.",
            "Snug, not tight: they go into plastic.",
        ], ["2 × splice"], ["8 splice screws", "stubby screwdriver"]),
        ("bridge_7_screws", "Screw it to the dividers", [
            "Put the 4 screws back down through the side strips into the divider tops.",
            "Push the drawers back in. They should slide all the way home without touching anything.",
            "Press on the top of the front wall: it shouldn't move at all.",
        ], [], ["4 screws from the old bridge"]),
        ("bridge_8_cap", "Tray in, cap on", [
            "Do this when the new tray is built (steps 2 to 4 of the chute guide).",
            "Centre the tilt servo (**Chute** 90 on the Machine page). Lower the tray in: its back plate goes onto the tilt servo's horn, and its front axle drops down into the slot.",
            "Push the red cap down into the slot on top of the axle and screw it on with 2 × M3 × 12.",
            "With the servo let go, the tray should rock left and right freely. If it's stiff, loosen the cap screws half a turn.",
            "Put the front deck tiles back on.",
        ], ["enc_bridge_cap"], ["2 × M3 × 12"]),
    ]),
]


def build_md():
    out = ["# Front bridge v3: swap guide", "", "Swapping the old front bridge for the new one, in the box. "
           "A single-file version with the pictures inside: [`bridge_v3_guide.html`](bridge_v3_guide.html). "
           "The rest of the chute is in [CHUTE_V3.md](CHUTE_V3.md).", "", "## You need", ""] + ["- " + b for b in BITS] + [""]
    n = 0
    for key, title, intro, steps in SECTIONS:
        out += [f"## {title}", ""] + ([intro, ""] if intro else [])
        for pic, t, lines, parts, hw in steps:
            n += 1
            out += [f"### {n}. {t}", "", f"![Step {n}](img/v3/{pic}.png)", ""] + ["- " + l for l in lines]
            meta = []
            if parts: meta.append("**Parts:** " + ", ".join(f"`{p}`" for p in parts))
            if hw: meta.append("**You need:** " + ", ".join(hw))
            if meta: out += [""] + ["  \n".join(meta)]
            out.append("")
    return "\n".join(out) + "\n"


def build_html():
    body, toc, n = [], [], 0
    for key, title, intro, steps in SECTIONS:
        toc.append(f'<a href="#{key}">{html.escape(title)}</a>')
        arts = []
        for s in steps:
            n += 1
            arts.append(g.step_html(n, *s, True))
        first = n - len(steps) + 1
        body.append(f'<section class="part" id="{key}"><h2>{html.escape(title)} <small>steps {first}–{n}</small></h2>'
                    + (f'<p>{g.inline(intro)}</p>' if intro else "") + "".join(arts) + "</section>")
    return f"""<title>Front Bridge Swap</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>{g.CSS}</style>
<div class="wrap">
<header><h1>Front bridge swap</h1>
<p>Old front bridge out, new one in, without taking the rest of the mechanism out of the box. One picture per step.</p></header>
<div class="key"><span><i class="sw" style="background:#f5b041"></i>new part</span>
<span><i class="sw" style="background:#a3a9b1"></i>old front bridge</span>
<span><i class="sw" style="background:#d62828"></i>screw or move</span></div>
<nav class="toc">{"".join(toc)}</nav>
<section class="part"><h2>You need</h2><div class="card"><ul>{"".join(f"<li>{g.inline(b)}</li>" for b in BITS)}</ul></div></section>
{"".join(body)}
<footer>Pictures: <code>guide/v3/bridge_render.py</code>, page: <code>guide/v3/build_bridge.py</code>.</footer>
</div>
"""


if __name__ == "__main__":
    open(os.path.join(g.HW, "BRIDGE_V3.md"), "w").write(build_md())
    page = build_html()
    open(os.path.join(HERE, "bridge_artifact.html"), "w").write(page)
    open(os.path.join(g.HW, "bridge_v3_guide.html"), "w").write(
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"></head><body>' + page + "</body></html>\n")
    print("wrote BRIDGE_V3.md, bridge_v3_guide.html")
