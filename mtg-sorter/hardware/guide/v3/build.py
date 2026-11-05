#!/usr/bin/env python3
"""Build the chute v3 + front bridge v3 guide.

    python3 guide/v3/render.py    # first: the pictures (img/v3)
    python3 guide/v3/build.py     # then: the guide

writes
    CHUTE_V3.md               for GitHub (pictures from img/v3/)
    chute_v3_guide.html       one file with the pictures inside, to open in a browser
    guide/v3/artifact.html    the same page without <html>/<head>, for publishing
"""
import base64, html, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(os.path.dirname(HERE))
IMG = os.path.join(HW, "img", "v3")
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "v2"))
sys.path.insert(0, os.path.dirname(HERE))
from build import CSS, table_html, md_table   # same look as the v2 guide
from build_guide import inline, callout_md

PROBLEMS = [
    ("The door carrier snapped and a horn came off", "A thin 2.5 mm tab plate held the servo, and each door hung on its servo's shaft",
     "Each door turns on **two round journals** clamped between the tray and a screwed-on **hinge frame**. The servos sit in pockets in an **8 mm front wall** and drive the doors through a crank and a link, so a servo never holds a door up"),
    ("Cards caught on screw heads", "The carriers were screwed down through the tray floor",
     "**No screws in the floor at all.** The card only ever touches the bare, flat print"),
    ("The doors only opened about 67°", "ServoKit's default pulses give an MG90S only about 135° of travel",
     "With **Wider servo travel** on, the link turns each door a full **95°**"),
    ("Hot servos at full tilt", "The old door servos hung under the tray and hit `bridge_front` at 25°",
     "Nothing hangs below the tray. Checked in CAD at ±25° with the doors shut and open, and with the stop gate swinging down"),
    ("The front bridge was flimsy", "A 4 mm ring round a big hole, the tray's axle in a 6 mm plate on two 3 mm gussets",
     "A **10 mm bearing wall** with gussets, a 10 mm shelf behind it (an L beam) and an arched beam at the back. The tray's axle **drops into a slot** and a screw-on cap closes it"),
]
PLATES = [("1", "chute tray, hinge frame", "black", "about 4 h, 60 g"),
          ("2", "front bridge, bearing cap, both doors, both door cranks, both servo cranks, 2 links", "black", "about 6 h, 90 g")]
BITS = [
    "**7 × M3 × 12** self-tapping: hinge frame, from below.",
    "**2 × M3 × 10** with washers: door cranks onto the door journals.",
    "**4 × M3 × 8**: the link pins (two per link).",
    "**2 × M3 × 12**: the bearing cap.",
    "From the servo bags: 4 tab screws, 2 **single-arm** horns and their centre screws.",
    "The 4 divider screws and 2 splices from the old front bridge.",
]
SECTIONS = [
    ("bridge", "The front bridge", "Take the old tray out first: unscrew the tilt servo's horn from its back plate and lift it away.", [
        ("step1_bridge", "Swap the front bridge", [
            "Unscrew the old `bridge_front` from the dividers and the two splices, and lift it out.",
            "Set the new one on the dividers with the **tall wall at the front**, and put the same screws back through it into the divider tops and the splices.",
            "Keep the red **cap** and its 2 screws for step 5.",
        ], ["enc_bridge_front", "enc_bridge_cap"], ["4 divider screws", "2 splices"]),
    ]),
    ("tray", "The tray", "Build it on the bench.", [
        ("step2_servos", "Door servos into the front wall", [
            "From **inside** the tray, push each MG90S into its pocket in the front wall, shaft end first, so the shaft comes out on the front.",
            "The bodies point **in**, towards the middle. Screw each one through its two tabs into the wall.",
            "Run the wires over the top of the wall and out to the side. Leave a loop of slack: the tray tips 25° each way.",
        ], ["bed_chute_chute3"], ["2 × MG90S", "4 tab screws"]),
        ("step3_doors", "Doors and hinge frame", [
            "Turn the tray upside down.",
            "Lay each door in, **smooth face down**, so its round journals sit in the half-round notches at the front and back. The long journal goes out through the front wall. The two doors are mirror images, so each only fits its own side.",
            "Put the hinge frame on top, its half-round notches over the journals, and drive the 7 screws in.",
            "Turn it over and swing each door by hand. It should flop open and shut freely. If one binds, loosen the two screws nearest it a little.",
        ], ["bed_chute_door3", "bed_chute_door3_left", "bed_chute_hinge_frame3"], ["7 × M3 × 12"]),
        ("step4_links", "Cranks and links", [
            "Slide a **door crank** onto the D-shaped end of each door's front journal and screw it on with an M3 × 10 and a washer. Tight.",
            "Press a single-arm horn into the pocket on the back of each **servo crank**, its arm in the slot.",
            "Screw a **link** onto each door crank's pin hole with an M3 × 8. Tighten it until it touches, then back it off a quarter turn so the link turns freely.",
            "Plug the door servos in and press **Closed** for both on the Machine page (with **Wider servo travel** on). Hold each door shut, put the servo crank's pin hole over the link's top hole, and push the crank onto the servo shaft at the nearest spline tooth. Fit the horn's centre screw, then the second M3 × 8 through the link.",
        ], ["bed_chute_door_crank3", "bed_chute_door_crank3_left", "bed_chute_servo_crank3", "bed_chute_servo_crank3_left", "bed_chute_door_link3 ×2"],
         ["2 × M3 × 10 + washers", "4 × M3 × 8", "2 single-arm horns"]),
    ]),
    ("install", "Into the machine", "", [
        ("step5_install", "Drop the tray in", [
            "Set **Chute** to 90 on the Machine page so the tilt servo's horn is level.",
            "Lower the tray in: the back plate goes onto the tilt servo's horn (same screws as before) and the front axle drops down into the **slot** in the bridge wall.",
            "Put the red cap into the slot on top of the axle and screw it down with the 2 × M3 × 12.",
            "The tray should rock left and right freely with the servo let go.",
        ], [], ["2 × M3 × 12", "tilt horn screws"]),
    ]),
]
ANGLES = [("Wider servo travel", "**on**", "The doors need the full 95°. Without it they only open about 70°"),
          ("Chute", "centre 90, left **65**, right **115**", "25° each way. Clear of the bridge and the stop gate at 25° (CAD), touches the bridge at about 28°"),
          ("Right door", "closed **about 40**, open **closed + 95**", "Find closed with the slider (see below), then open is 95 more"),
          ("Left door", "closed **about 140**, open **closed − 95**", "The mirror image: its servo turns the other way"),
          ("Pins", "as you have them", "")]
TROUBLE = [("A door's servo buzzes or gets warm when shut", "Closed is pushing the door against its stop. Move closed 2–3 towards open and Save. The doors now **keep holding** after a move (they'd sag open if let go), so they must not push"),
           ("A door opens the wrong way", "Swap that door's closed and open numbers round the other side of closed (closed − 95 instead of + 95)"),
           ("A door doesn't open fully", "Check Wider servo travel is on, then add a few degrees to open"),
           ("The tray rubs the bridge at full tilt", "Bring left/right 2–3 back towards 90 and Save"),
           ("A link is stiff", "Back its screws off another quarter turn")]
CLOSED = ("**Finding closed:** with the door shut, nudge the door's slider a degree at a time until the door is held flat against its stop "
          "with no buzz, then back off one degree and press **Save closed**. Then set open (95 further) and **Save open**. "
          "Press Closed / Open a few times to check.")
OLD = ("You can stop using: the old `chute`, both `trapdoor`s, both `door_carrier`s, the `hinge_pin`s and the old `bridge_front`. "
       "Everything else (bridge_back, bed walls, tilt bracket, tilt servo, feeder, wiring) stays as it is.")


def src(name, embed):
    if not embed: return f"img/v3/{name}.png"
    with open(os.path.join(IMG, name + ".png"), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def build_md():
    out = ["# Chute v3 and front bridge v3", "",
           "A new tray, trapdoors and front bridge, built so they can't break the way the v2 ones did.", ""]
    out += md_table(["Problem", "Cause", "v3 fix"], PROBLEMS)
    out += ["", f"![The new tray in the new front bridge](img/v3/overview.png)", "",
            "| Waiting | Bin 2: doors open | Bin 3: tipped right |", "|---|---|---|",
            "| ![](img/v3/state_shut.png) | ![](img/v3/state_open.png) | ![](img/v3/state_tilt.png) |", "",
            "A single-file version with the pictures inside: [`chute_v3_guide.html`](chute_v3_guide.html).", "",
            "## Print", "", "Open **`bambu/MTG_Sorter_Chute_v3.3mf`** with **File > Open Project** (not Import). "
            "The settings are already applied. All black, no supports. Times and weights are estimates until it's sliced.", ""]
    out += md_table(["Plate", "Parts", "Filament", "Roughly"], PLATES)
    out += ["", OLD, "", "## Bits you need", ""] + ["- " + b for b in BITS] + [""]
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
    out += ["## Servo angles (Machine page)", ""] + md_table(["Setting", "Value", "Why"], ANGLES) + ["", CLOSED, "",
            "## If something's off", ""] + md_table(["What you see", "Try"], TROUBLE)
    out += ["", "---", "", "CAD: `bed_chute.scad` (CHUTE v3 section) and `enclosure.scad` (`bridge_front3`, `bridge_cap3`). "
            "Pictures: `python3 guide/v3/render.py`, then `python3 guide/v3/build.py`."]
    return "\n".join(out) + "\n"


def step_html(n, pic, t, lines, parts, hw, embed):
    lis = "".join(f"<li>{inline(l)}</li>" for l in lines)
    meta = ""
    if parts or hw:
        meta = '<div class="meta">'
        if parts: meta += '<div class="chips"><b>Parts</b>' + "".join(f'<span class="chip">{html.escape(p)}</span>' for p in parts) + "</div>"
        if hw: meta += '<div class="chips"><b>You need</b>' + "".join(f'<span class="chip">{html.escape(h)}</span>' for h in hw) + "</div>"
        meta += "</div>"
    return (f'<article class="step" id="step-{n}"><div class="pic"><img src="{src(pic, embed)}" alt="Step {n}: {html.escape(t)}" loading="lazy"></div>'
            f'<div class="txt"><div class="num">{n:02d}</div><h3>{html.escape(t)}</h3><ul>{lis}</ul>{meta}</div></article>')


def build_html(embed=True):
    body, toc, n = [], [], 0
    for key, title, intro, steps in SECTIONS:
        toc.append(f'<a href="#{key}">{html.escape(title)}</a>')
        arts = []
        for s in steps:
            n += 1
            arts.append(step_html(n, *s, embed))
        first = n - len(steps) + 1
        rng = f"step {n}" if first == n else f"steps {first}–{n}"
        body.append(f'<section class="part" id="{key}"><h2>{html.escape(title)} <small>{rng}</small></h2>'
                    + (f'<p>{inline(intro)}</p>' if intro else "") + f'{"".join(arts)}</section>')
    toc += ['<a href="#print">Print</a>', '<a href="#angles">Servo angles</a>', '<a href="#trouble">Problems</a>']
    states = "".join(f'<figure><img src="{src(p, embed)}" alt="{c}"><figcaption>{c}</figcaption></figure>' for p, c in
                     [("state_shut", "Waiting: tray level, doors shut"), ("state_open", "Bin 2: both doors swing down 95°"),
                      ("state_tilt", "Bin 3: the tray tips 25° (bin 1 is the mirror image)")])
    return f"""<title>Chute v3 Guide</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header><h1>Chute v3 and front bridge</h1>
<p>A new tray, trapdoors and front bridge, one picture per step, drawn from the same CAD the print file comes from.
Nothing screws through the tray floor, no servo holds a door up, and the tray drops into the bridge from above.</p></header>
<div class="hero"><img src="{src('overview', embed)}" alt="The new tray sitting in the new front bridge"></div>
<div class="figs">{states}</div>
<div class="key"><span><i class="sw" style="background:#f5b041"></i>this step</span>
<span><i class="sw" style="background:#d62828"></i>where it goes</span>
<span><i class="sw" style="background:#e8772e"></i>tray</span>
<span><i class="sw" style="background:#3060c0"></i>servo</span></div>
<nav class="toc">{"".join(toc)}</nav>
<section class="part" id="print"><h2>Before you start</h2>
<p>{inline("Open `bambu/MTG_Sorter_Chute_v3.3mf` with **File > Open Project** (not Import). The settings are already applied. All black, no supports. Times and weights are estimates until it's sliced.")}</p>
{table_html(["Plate", "Parts", "Filament", "Roughly"], PLATES)}
<div class="card"><h3>Bits you need</h3><ul>{"".join(f"<li>{inline(b)}</li>" for b in BITS)}</ul></div>
<p>{inline(OLD)}</p>
</section>
{"".join(body)}
<section class="part" id="angles"><h2>Servo angles</h2>
<p>On the Machine page. Press <strong>Save</strong> after each one.</p>
{table_html(["Setting", "Value", "Why"], ANGLES)}<p>{inline(CLOSED)}</p></section>
<section class="part" id="trouble"><h2>If something's off</h2>
{table_html(["What you see", "Try"], TROUBLE)}</section>
<section class="part"><h2>What changed</h2>{table_html(["Problem", "Cause", "v3 fix"], PROBLEMS)}</section>
<footer>CAD: <code>hardware/bed_chute.scad</code> (CHUTE v3) and <code>enclosure.scad</code> (<code>bridge_front3</code>).
Pictures: <code>python3 guide/v3/render.py</code> then <code>python3 guide/v3/build.py</code>.</footer>
</div>
"""


if __name__ == "__main__":
    with open(os.path.join(HW, "CHUTE_V3.md"), "w") as f:
        f.write(build_md())
    page = build_html(embed=True)
    with open(os.path.join(HERE, "artifact.html"), "w") as f:
        f.write(page)
    with open(os.path.join(HW, "chute_v3_guide.html"), "w") as f:
        f.write('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
                + "</head><body>" + page + "</body></html>\n")
    print("wrote CHUTE_V3.md, chute_v3_guide.html, guide/v3/artifact.html")
