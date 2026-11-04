#!/usr/bin/env python3
"""Build the mechanism v2 guide (new feeder, scan bed stop gate, door carriers).

    python3 guide/v2/render.py    # first: the pictures, from feeder_scenes.scad and bed_scenes.scad
    python3 guide/v2/build.py     # then: the guide

writes
    MECHANISM_V2.md                 for GitHub (pictures from img/v2/)
    mechanism_v2_guide.html         one file with the pictures inside, to open in a browser
    guide/v2/artifact.html          the same page without <html>/<head>, for publishing

Change the words here, the pictures in the .scad scenes.
"""
import base64, html, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(os.path.dirname(HERE))
IMG = os.path.join(HW, "img", "v2")
sys.path.insert(0, os.path.dirname(HERE))
from build_guide import CSS as BASE_CSS, inline, callout_md   # same look as the enclosure guide

PROBLEMS = [
    ("The roller didn't touch the cards", "It only poked 0.8 mm above the hopper floor, fixed in place",
     "Two O-ring wheels on a **hinged arm**. A rubber band pushes them up into the stack, and a stop keeps them 2.5 mm proud"),
    ("Cards flew past the stop pins", "Two thin pins, only 2.4 mm tall",
     "A **stop gate**: four teeth, 8 mm tall, across the whole card, held at both ends"),
    ("Servos got hot, and the tray couldn't tilt fully", "At 25° the trapdoor servos dipped 4 mm into `bridge_front`",
     "**Door carriers** with the servos turned to point inwards. They clear the bridge at 25° (checked in CAD)"),
]
PLATES = [("1", "feeder stand (with brim)", "black"), ("2", "feeder hopper (with brim)", "black"),
          ("3", "feeder arm, roller (100% infill), gate, weight", "black"), ("4", "scan bed plate", "**white**"),
          ("5", "stop gate, gate bearing, both door carriers", "black")]
BITS = [
    "A small rubber band, about **4 cm long lying flat**. A 40–50 mm O-ring from the kit works too.",
    "Two 3 mm O-rings for the wheels (20 × 3 or 22 × 3), as before.",
    "One **1.9 mm thick O-ring** from the kit (any size), cut open into a strip. This is the gate's rubber pad.",
    "Coins or nuts for the weight plate: two loonies, quarters or M8 nuts per pocket.",
    "Screws: 2 × M3 × 8 (arm hinge), 1 × M3 × 12 (thumb screw), 2 × M3 × 8 (gate lock, as before), 2 × M2 × 6 (motor pinch and gate bearing).",
]

# Each step: (picture, title, [lines], [parts], [hardware]). (1) (2) ... are the numbered circles.
SECTIONS = [
    ("feeder", "The feeder", "Build it on the bench. It sits on the bridge in the same spot as the old one, same footprint.", [
        ("feeder_01", "Wheels", [
            "(1) Stretch a 3 mm O-ring into each groove on the roller.",
            "(2) is the stub axle, (3) the D-shaped hole for the motor shaft.",
        ], ["feeder_roller"], ["2 × 3 mm O-ring"]),
        ("feeder_02", "Motor into the arm", [
            "Slide the N20 into the square tunnel from the outside, shaft first, until the gearbox stops against the end wall (1).",
            "(2) Snug the M2 screw in the side of the tunnel to pinch the gearbox. Don't overtighten it.",
            "(3) The slot in the left plate is for the roller's stub.",
        ], ["feeder_arm"], ["N20 motor", "1 × M2 × 6"]),
        ("feeder_03", "Roller onto the motor", [
            "(1) Line up the flat in the roller's hole with the flat on the shaft and press it on.",
            "(2) The stub at the other end drops into the slot in the arm's left plate.",
            "Spin it by hand: it should turn with the motor and not rub.",
        ], [], []),
        ("feeder_04", "Arm into the stand", [
            "With the hopper off, lower the arm in from the top.",
            "(1) The motor slides down the open slot in the right wall.",
            "(2) Put an M3 × 8 through each side wall into the arm's hinge. The arm should swing up and down freely.",
        ], ["feeder_stand_mid"], ["2 × M3 × 8"]),
        ("feeder_05", "Rubber band", [
            "This picture is cut open down the middle so you can see inside.",
            "Loop the band under the bar at the bottom back of the stand (2), through the notch, and over the arm's tail tongue (1). The bump at the end of the tongue keeps it on.",
            "The band pulls the tail down, so the arm turns on its hinge (3) and the wheels push up. Press the wheels down: they should push back firmly.",
        ], [], ["rubber band, ~4 cm"]),
        ("feeder_06", "Hopper on", [
            "Set the hopper on the four pegs at the top of the stand.",
            "(1) The O-rings now stand about 2.5 mm above the floor. Press them down with a finger and they should spring back.",
        ], ["feeder_hopper"], []),
        ("feeder_07", "Gate", [
            "(1) Press the cut 1.9 mm O-ring into the groove under the gate's bottom edge. A dab of glue helps.",
            "Hang the gate on the front wall with the two lock screws (3) loose.",
            "(2) Drive the M3 × 12 down through the tab until its tip rests on the little shelf (4) that pokes out through the gate's window.",
            "Slip one card under the gate and turn the thumb screw until the card just drags when you pull it. Tighten the lock screws and take the card out.",
        ], ["feeder_gate"], ["1 × M3 × 12", "2 × M3 × 8", "1.9 mm O-ring, cut"]),
        ("feeder_08", "Cards and weight", [
            "(1) Load the cards face up.",
            "(2) Put the weight plate on top with coins in its pockets. Lift it out by the handle.",
        ], ["feeder_weight"], ["8 coins or M8 nuts"]),
        ("feeder_09", "How it works", [
            "(1) The wheels push up into the stack and roll the bottom card forward, out under the gate and down onto the bed.",
            "(2) The rubber pad under the gate holds the next card back, so only one comes out.",
            "(3) The rubber band keeps the wheels pressed up as the stack gets lower.",
            "Wiring is the same as before. If the wheels push cards **backwards**, swap the motor's two wires.",
        ], [], []),
    ]),
    ("bed", "The scan bed stop gate", "The stop gate replaces the two stop pins. It uses the same pin servo, still on the left wall. "
     "Take out the old pin rocker and slide the old bed plate out of its grooves first. Leave the pin servo where it is. "
     "The right bed wall is left out of these pictures so you can see in.", [
        ("bed_01", "Gate bearing", [
            "(1) Push the gate bearing down over the **right** end of the tilt bracket (3), between the bracket and the right bed wall, with its pin pointing to the middle.",
            "(2) Put an M2 × 6 through its back jaw into the bracket.",
        ], ["bed_chute_gate_bearing"], ["1 × M2 × 6"]),
        ("bed_02", "Horn on the stop gate", [
            "(1) Screw the double-arm horn to the stop gate's left plate (2), using the two horn holes nearest the hub, as with the old rocker.",
            "(3) are the four teeth that stop the card.",
        ], ["bed_chute_stop_gate"], ["servo horn and its 2 small screws"]),
        ("bed_03", "Fit the stop gate", [
            "Centre the pin servo at 90 first (Machine page, Pins).",
            "(1) Hook the right plate's hole over the bearing pin.",
            "(2) Then push the horn onto the servo shaft, with the teeth (3) pointing up. Fit the horn's centre screw.",
        ], [], ["horn centre screw"]),
        ("bed_04", "New bed plate in", [
            "On the Machine page, move **Pins** to about 50 so the teeth (1) swing down.",
            "Slide the new white bed plate down its grooves from the top, rails up.",
        ], ["bed_chute_bed_plate (white)"], []),
        ("bed_05", "Teeth up", [
            "Move **Pins** back to 90.",
            "(1) The four teeth come up through the slots at the bed's front edge, about 8 mm tall. A card coming down the bed stops on them.",
            "At 50 they drop below the bed and the card slides off into the chute.",
        ], [], []),
    ]),
    ("doors", "Door carriers", "The chute itself doesn't change. Only the two carriers under it do.", [
        ("bed_06", "Swap the door carriers", [
            "Unscrew the chute and swap each door carrier for the new one, with the same screws.",
            "(1) The servo goes in the same way, except its body now points **in** towards the middle of the tray instead of out past the door. That is what keeps it off `bridge_front` when the tray tilts.",
            "(2) The hinge lug at the back is the same. The horn still slides up into the door's fork.",
        ], ["bed_chute_door_carrier", "bed_chute_door_carrier_left"], []),
    ]),
]
ANGLES = [("Pins (the stop gate)", "up **90**, down **50**", "40° drops the teeth well clear. CAD shows no contact from 6° past up to 44° down"),
          ("Chute", "centre 90, left **68**, right **112**", "22° each way. The servos now clear the bridge even at 25°, but 22° leaves about 2.5 mm"),
          ("Doors", "unchanged", "")]
TROUBLE = [("Two cards come out", "Lower the gate a quarter turn of the thumb screw"),
           ("Nothing comes out, wheels spin", "Add a second wrap of the rubber band, or more coins on the weight"),
           ("Card lands crooked on the bed", "The funnel at the top of the bed should straighten it. If not, check that both wheels touch the card"),
           ("The pin servo buzzes with the teeth up", "The bar is pressing on the bed's underside: save \"up\" a few degrees lower (towards 50)")]
OLD = "You can stop using these old parts: `pin_rocker`, the old roller, hopper, gate and stand, and the old door carriers."


def md_table(head, rows):
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(r) + " |" for r in rows]


def build_md():
    out = ["# Mechanism v2: new feeder, scan bed stop and door carriers", "",
           "This replaces the parts that went wrong on the first test run:", ""]
    out += md_table(["Problem", "Cause", "v2 fix"], PROBLEMS)
    out += ["", "Everything else stays as it is: the enclosure, bridge, bed walls, chute tray, trapdoors, tilt bracket and wiring.", "",
            "A single-file version with the pictures inside: [`mechanism_v2_guide.html`](mechanism_v2_guide.html) "
            "(download it and open it in a browser). In the pictures **grey** is already fitted, **orange** is what the step adds, "
            "**pink arrows** show where it goes, and numbered circles match the numbers in the text.", "",
            "![Side cut-away: hopper and wheel on the right, card resting on the stop teeth at the front of the bed](img/v2/mechanism_v2_side.png)", "",
            "## Print", "", "Open **`bambu/MTG_Sorter_Feeder_And_Bed_v2.3mf`** with **File > Open Project** (not Import). "
            "The settings are already applied. There are five plates:", ""]
    out += md_table(["Plate", "Parts", "Filament"], PLATES)
    out += ["", "No supports anywhere. " + OLD, "", "## Bits you need", ""] + ["- " + b for b in BITS] + [""]
    n = 0
    for key, title, intro, steps in SECTIONS:
        out += [f"## {title}", "", intro, ""]
        for pic, t, lines, parts, hw in steps:
            n += 1
            out += [f"### {n}. {t}", "", f"![Step {n}](img/v2/{pic}.png)", ""] + ["- " + callout_md(l) for l in lines]
            meta = []
            if parts: meta.append("**Parts:** " + ", ".join(f"`{p}`" for p in parts))
            if hw: meta.append("**You need:** " + ", ".join(hw))
            if meta: out += [""] + ["  \n".join(meta)]
            out.append("")
    out += ["![Stop gate turned down: the teeth swing forward under the bed's front edge and the card slides into the chute](img/v2/stop_gate_down.png)", "",
            "## Servo angles to save on the Machine page", ""]
    out += md_table(["Part", "Positions", "Why"], ANGLES)
    out += ["", "Press **Save** after each one. If cards stick in the tray at 22°, try 24°.", "", "## If something's off", ""]
    out += md_table(["What you see", "Try"], TROUBLE)
    out += ["", "---", "", "Pictures: `python3 guide/v2/render.py` (needs OpenSCAD), then `python3 guide/v2/build.py`."]
    return "\n".join(out) + "\n"


def src(name, embed):
    if not embed: return f"img/v2/{name}.png"
    with open(os.path.join(IMG, name + ".png"), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


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


def table_html(head, rows):
    return ("<div class=\"tbl\"><table><thead><tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div>")


CSS = BASE_CSS + """
.tbl { background: var(--sheet); border-radius: 12px; padding: 6px 12px; overflow-x: auto }
.tbl td:first-child { font-family: var(--body) }
.card { background: var(--sheet); border-radius: 12px; padding: 16px 20px; display: grid; gap: 10px }
.card h3 { font: 700 1.3rem/1.1 var(--display); text-transform: uppercase; letter-spacing: .02em; margin: 0 }
.card ul { margin: 0; padding-left: 18px; display: grid; gap: 6px }
.figs { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr)); gap: 12px }
.figs figure { margin: 0; background: var(--plate); border-radius: 12px; padding: 10px; display: grid; gap: 6px; align-content: start }
.figs figcaption { font-size: 13px; color: var(--muted) }
.hero img { border-radius: 12px; background: var(--plate) }
"""


def build_html(embed=True):
    body, toc, n = [], [], 0
    for key, title, intro, steps in SECTIONS:
        toc.append(f'<a href="#{key}">{html.escape(title)}</a>')
        arts = []
        for s in steps:
            n += 1
            arts.append(step_html(n, *s, embed))
        body.append(f'<section class="part" id="{key}"><h2>{html.escape(title)} <small>steps {n - len(steps) + 1}–{n}</small></h2>'
                    f'<p>{inline(intro)}</p>{"".join(arts)}</section>')
    toc += ['<a href="#print">Print</a>', '<a href="#angles">Servo angles</a>', '<a href="#trouble">Problems</a>']
    return f"""<title>Sorter Mechanism v2</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header><h1>Mechanism v2 assembly</h1>
<p>The new feeder, the scan bed stop gate and the door carriers, one picture per step. The pictures are drawn from the
same CAD the STLs come from. Everything else in the sorter stays as it is.</p></header>
<div class="figs">
<figure><img src="{src('mechanism_v2_side', embed)}" alt="Side cut-away of the feeder and scan bed"><figcaption>Side cut-away: the hopper and wheels on the right, a card resting on the stop teeth at the front of the bed.</figcaption></figure>
<figure><img src="{src('stop_gate_down', embed)}" alt="Stop gate turned down"><figcaption>Stop gate turned down: the teeth swing under the bed's front edge and the card slides into the chute.</figcaption></figure>
</div>
<div class="key"><span><i class="sw" style="background:#a3a9b1"></i>already fitted</span>
<span><i class="sw" style="background:#ff7a1a"></i>this step</span>
<span><i class="sw" style="background:var(--arrow)"></i>where it goes</span>
<span><span class="co">1</span>matches the text</span>
<span><i class="sw" style="background:#2e6fd8"></i>servo</span></div>
<nav class="toc">{"".join(toc)}</nav>
<section class="part" id="print"><h2>Before you start</h2>
<p>{inline("Open `bambu/MTG_Sorter_Feeder_And_Bed_v2.3mf` with **File > Open Project** (not Import). The settings are already applied. No supports anywhere.")}</p>
{table_html(["Plate", "Parts", "Filament"], PLATES)}
<div class="card"><h3>Bits you need</h3><ul>{"".join(f"<li>{inline(b)}</li>" for b in BITS)}</ul></div>
<p>{inline(OLD)}</p>
</section>
{"".join(body)}
<section class="part" id="angles"><h2>Servo angles</h2>
<p>Set these on the Machine page and press <strong>Save</strong> after each one. If cards stick in the tray at 22°, try 24°.</p>
{table_html(["Part", "Positions", "Why"], ANGLES)}</section>
<section class="part" id="trouble"><h2>If something's off</h2>
{table_html(["What you see", "Try"], TROUBLE)}</section>
<section class="part"><h2>What changed</h2>{table_html(["Problem", "Cause", "v2 fix"], PROBLEMS)}</section>
<footer>Pictures come from <code>hardware/guide/v2/feeder_scenes.scad</code> and <code>bed_scenes.scad</code>; rebuild with
<code>python3 guide/v2/render.py</code> then <code>python3 guide/v2/build.py</code>.</footer>
</div>
"""


if __name__ == "__main__":
    with open(os.path.join(HW, "MECHANISM_V2.md"), "w") as f:
        f.write(build_md())
    page = build_html(embed=True)
    with open(os.path.join(HERE, "artifact.html"), "w") as f:
        f.write(page)
    with open(os.path.join(HW, "mechanism_v2_guide.html"), "w") as f:
        f.write('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
                + "</head><body>" + page + "</body></html>\n")
    print("wrote MECHANISM_V2.md, mechanism_v2_guide.html, guide/v2/artifact.html")
