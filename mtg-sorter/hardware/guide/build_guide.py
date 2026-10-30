#!/usr/bin/env python3
"""Build the picture assembly guide from the rendered steps.

    python3 guide/render.py        # first: the pictures, from scenes.scad
    python3 guide/build_guide.py   # then: the guide

writes
    ASSEMBLY_PICTURES.md           for GitHub (pictures from img/assembly/)
    assembly_guide.html            one file with the pictures inside, to open in a browser
    guide/artifact.html            the same page without <html>/<head>, for publishing

The steps follow ASSEMBLY.md (Part 2 stages and Part 3). Change the words here, the
pictures in scenes.scad.
"""
import base64, html, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
IMG = os.path.join(HW, "img", "assembly")

# ---------------------------------------------------------------------------------------
# The guide. Each step: (scene number, title, [lines], [part names], [hardware]).
# In lines, `name` is a printed part (shown in mono), (1) (2) ... refer to the callouts.
SECTIONS = [
    ("The box", "Floor, electronics, walls. Build it on the table where the machine will live.", [
        (1, "Join the floor", [
            "Lay the four floor tiles upside down and push them together.",
            "Put a `splice` in each of the six pockets across the seams and fix it with M2 screws or a drop of CA glue.",
            "Stick a rubber foot in each of the six round recesses.",
            "Turn it over. The grooves on top are where the drawers run.",
        ], ["floor_fl", "floor_fr", "floor_bl", "floor_br", "6 × splice"], ["6 × rubber feet, 8 mm", "M2 × 6 or CA glue"]),
        (2, "Electronics on the floor", [
            "(1) Raspberry Pi 5 on the four standoffs at the back right, ports facing the back.",
            "(2) PCA9685 servo board on the four standoffs at the back left.",
            "(3) DRV8833 motor driver: a zip tie through the slots beside the servo board.",
            "(4) Barrel-jack screw adapter next to the small cut-out at the back left corner. The 5 V adapter cable and the Pi's USB-C cable come in through that cut-out.",
            "Plug the servo and motor wires in later, in step 16.",
        ], [], ["8 × M2.5 × 6 (Pi and PCA9685)", "1 zip tie"]),
        (3, "Corner posts", [
            "Push each post onto its two pegs at a corner of the floor. They go on by hand.",
            "The front posts have one groove that stops 115 mm short of the floor, where the drawers slide past. `post_front` goes front left, `post_front_r` front right: they are mirror images, so two of the same won't do.",
            "A loose post gets a drop of CA glue on its pegs.",
        ], ["post_front (left)", "post_front_r (right)", "2 × post_back"], []),
        (4, "Back panel", [
            "On the bench, glue `back_l` and `back_r` together with four splices in the pockets on the inside face.",
            "Slide it down the grooves of the two back posts until it sits in the floor groove.",
            "The big cut-out lines up with the Pi's USB and network ports, the small one with the power cut-out.",
        ], ["back_l", "back_r", "4 × splice"], ["CA glue"]),
        (5, "Sides", [
            "Each side is two `side` pieces end to end. Flip the second one end for end so both pockets meet at the joint, facing in.",
            "Glue three splices across the joint.",
            "Slide each side down between its front and back post.",
        ], ["4 × side", "6 × splice"], ["CA glue"]),
        (6, "Build the fascia", [
            "Lay the three fascia pieces face down, pockets up. The two end pieces are mirror images, so either goes at either end.",
            "Glue two splices across each seam (four in all).",
            "Glue the white `light_bar` across the top, over the three light slots. It also ties the pieces together.",
        ], ["fascia_l", "fascia_m", "fascia_r", "light_bar", "4 × splice"], ["CA glue"]),
        (7, "Fascia on", [
            "Slide the fascia down the front posts' grooves, light slots at the top and the light bar on the inside.",
            "It stops 114 mm above the floor. The drawers go under it.",
        ], [], []),
        (8, "Dividers and rear legs", [
            "Stand a `divider` in the groove along each middle curb, its top flange reaching out toward the side wall. It stands on its own.",
            "Drop a `leg` onto each of the two round bosses at the back of the floor.",
            "The flanges and the legs carry the bridge in step 16.",
        ], ["2 × divider", "2 × leg"], []),
    ]),
    ("The mechanism, on the bridge", "Build this on the bench and test it before it goes into the box. It's Part 2 of ASSEMBLY.md, standing on the bridge.", [
        (9, "Join the bridge", [
            "Turn `bridge_front` and `bridge_back` upside down, push them together and fix two splices across the seam.",
            "The tall upright at the front, with the hole, holds the chute's front axle.",
        ], ["bridge_front", "bridge_back", "2 × splice"], ["M2 × 6 or CA glue"]),
        (10, "Bed walls and scan bed", [
            "Stand the two `..._enclosure` bed walls on the bridge's side ears and screw each one from below, two M3 per wall.",
            "Slide the white bed plate into the grooves on the inside of the walls: low rails up, pin slots at the low front edge. Use the thin lower groove that runs out through the front edge of each wall, not the wider LED groove above it.",
        ], ["bed_side_left_enclosure", "bed_side_right_enclosure", "bed_plate (white)"], ["4 × M3 × 8"]),
        (11, "Tilt bracket, stop pins", [
            "(1) `tilt_bracket` across between the walls under the bed, two M3 through each wall.",
            "(2) Stop-pin servo into the rectangular hole in the left wall from the outside, shaft pointing in. Use the two screws that came with it.",
            "Centre the servo at 90° before you fit the horn (see the box below).",
            "(3) `pin_rocker`: screw the double-arm horn to its flat plate first (the two horn holes nearest the hub), then push the pair onto the centred servo, pins up, and fit the centre screw through the round hole. Servo at \"up\": both pins poke up through the slots at the front of the bed. 28° the other way: they drop below the surface.",
        ], ["tilt_bracket", "pin_rocker"], ["4 × M3 × 8", "1 MG90S (channel 0)"]),
        (12, "Lights and camera post", [
            "Stick an LED strip in the groove along the inside of each wall, just above the bed (about 9 cm each). Don't cut the wire between the two pieces if you want to skip soldering: loop it under the bed.",
            "Push `tower_post` into the square socket on the right wall. The groove on its back is for the camera cable.",
            "Leave the camera head off for now. The deck can't go on over it (step 18).",
        ], ["tower_post"], ["USB LED strip"]),
        (13, "Build the chute", [
            "(1) A servo into each `trapdoor_mount` (two screws each). Screw the mounts under the front of the chute floor with M2 from above.",
            "(2) `hinge_lug` and `hinge_lug_left` under the back of the chute floor, the same way.",
            "(3) Centre both servos at 90° before fitting horns.",
            "(4) Trapdoors: the back ear goes on an M3 screw through the hinge lug (that's the hinge pin), the front ear screws to the servo horn. Closed, both doors sit flush with the floor.",
        ], ["chute", "trapdoor", "trapdoor_left", "trapdoor_mount", "trapdoor_mount_left", "hinge_lug", "hinge_lug_left"], ["4 × M2 × 6", "2 × M3 × 12 (hinge pins)", "2 MG90S (channels 2, 3)"]),
        (14, "Chute into the bridge", [
            "Push the chute's front axle into the hole in the bridge's front upright.",
            "Push the tilt servo through the tilt bracket from the back and screw it in. Centre it, then screw its horn to the small plate on the chute's back end.",
            "Test by hand: level, 25° left, 25° right. Nothing should touch the walls or the bridge.",
        ], [], ["1 MG90S (channel 1)"]),
        (15, "Feeder on the bridge", [
            "The feeder is the one from Part 1, on the tall `feeder_stand_mid`: (2) N20 motor and roller in the stand, hopper and gate on top.",
            "(1) Set the stand in the low fence on the bridge, behind the bed, with the exit shelf facing the bed.",
            "Cards leave the shelf and drop onto the top of the bed.",
        ], ["feeder_stand_mid", "feeder_hopper", "feeder_gate", "feeder_roller"], ["N20 motor + 2 O-rings"]),
    ]),
    ("Into the box", "The mechanism goes in, gets wired, and the top closes over it.", [
        (16, "Bridge into the box", [
            "Lower the whole bridge in from above. The front edge rests on the dividers' flanges, the two leg pegs go through the holes at the back.",
            "Screw it to the flanges, three M3 per side.",
            "Now wire everything (see Wiring, below). Run the camera cable up the groove in the camera post.",
        ], [], ["6 × M3 × 8"]),
        (17, "Deck", [
            "Slide `post_sleeve` down over the camera post.",
            "Join `deck_fl` and `deck_fr` with two splices across the middle seam. Leave the two pockets on the front/back seam empty, so the back can lift off for the Pi.",
            "Lay the front deck on, then the two back halves. They're separate pieces.",
            "One countersunk M3 into the top of each corner post.",
        ], ["post_sleeve", "deck_fl", "deck_fr", "deck_bl", "deck_br", "2 × splice"], ["4 × M3 × 8, countersunk"]),
        (18, "Camera, covers, hopper tower", [
            "Screw the Camera Module 3 onto the top of `camera_head`, lens down through the window (4 × M2).",
            "Push the head onto the top of the camera post and plug the ribbon in.",
            "`head_cover` over the head and arm.",
            "`tower` down over the hopper into the well in the deck, then `tower_lid` on top.",
        ], ["camera_head", "head_cover", "tower", "tower_lid"], ["4 × M2 × 6", "Camera Module 3"]),
        (19, "Drawers in", [
            "Print three Card Catalog v1.2 drawers and their top bars from the MakerWorld 3MF.",
            "A toploader with a card in each front pocket, top bar clipped on.",
            "Slide them in: left is bin 1, middle bin 2, right bin 3.",
        ], ["3 × Card Catalog drawer + top"], []),
    ]),
]

WIRING_STEPS = [
    "(1) **Raspberry Pi 5**: on the floor. Power from the official 27 W USB-C supply, never from the servo supply.",
    "(2) **PCA9685** servo board: I²C to the Pi, servo power from the 5 V adapter.",
    "(3) **DRV8833** motor driver: two Pi pins, motor power from the 5 V adapter.",
    "(4) **Barrel-jack screw adapter**: the 5 V 4 A adapter's plug goes in here.",
    "(5) **Camera Module 3**: on the camera head, ribbon down the post to the Pi's camera port.",
    "(6) **LED strips**: on the bed walls, USB into the Pi.",
    "(7) **N20 feeder motor**: in the feeder stand, to DRV8833 OUT1 / OUT2.",
    "The four **MG90S** servos are in steps 11, 13 and 14: stop pins on the left wall, tilt behind the tilt bracket, trapdoors under the chute.",
]

SERVO_TABLE = [("0", "Stop pins", "up (card stops) / down 28°"),
               ("1", "Chute tilt", "centre / 25° left / 25° right"),
               ("2", "Right trapdoor", "closed / open 90°"),
               ("3", "Left trapdoor", "closed / open 90°")]

RULES = [
    "**The servo supply must be 5 V.** Check the adapter's label. A 12 V adapter burns an MG90S out in seconds: swap it, or put a 12→5 V buck converter in between.",
    "**Never power the servos from the Pi's 5 V pin.** Four servos at once will crash the Pi.",
    "**Join all the grounds**: Pi, PCA9685, DRV8833 and the adapter.",
    "Turn on I²C (`sudo raspi-config nonint do_i2c 0`); `i2cdetect -y 1` should then show `40`.",
]

CENTRE = ("Centre every servo before its horn goes on",
          "Plug it into the PCA9685, set it to 90° with the snippet below, then press the horn on. "
          "Otherwise the part it moves ends up at the wrong angle.")
SNIPPET = "from adafruit_servokit import ServoKit\nkit = ServoKit(channels=16)\nkit.servo[0].angle = 90   # channel, angle"

# ---------------------------------------------------------------------------------------
WIRING_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 560" font-family="IBM Plex Sans, Segoe UI, Arial, sans-serif" font-size="12" role="img" aria-label="Wiring diagram">
<rect width="920" height="560" fill="#f8f8f8"/>
<defs><marker id="dot" viewBox="0 0 8 8" refX="4" refY="4" markerWidth="5" markerHeight="5"><circle cx="4" cy="4" r="3.2" fill="#1d2733"/></marker></defs>
<g fill="none" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" marker-start="url(#dot)" marker-end="url(#dot)">
  <path d="M250 104 H340 V182 H380" stroke="#d62828"/>
  <path d="M250 128 H320 V200 H380" stroke="#222"/>
  <path d="M340 182 V392 H380" stroke="#d62828" marker-start="none"/>
  <path d="M320 200 V410 H380" stroke="#222" marker-start="none"/>
  <path d="M200 254 H380" stroke="#f08c00"/>
  <path d="M200 276 H290 V218 H380" stroke="#1971c2"/>
  <path d="M200 298 H300 V236 H380" stroke="#e0b000"/>
  <path d="M200 320 H310 V272 H380" stroke="#222"/>
  <path d="M200 362 H300 V428 H380" stroke="#2b8a3e"/>
  <path d="M200 384 H290 V446 H380" stroke="#2b8a3e"/>
  <path d="M200 406 H270 V464 H380" stroke="#222"/>
  <path d="M560 192 H680" stroke="#555"/><path d="M560 232 H680" stroke="#555"/>
  <path d="M560 272 H680" stroke="#555"/><path d="M560 312 H680" stroke="#555"/>
  <path d="M560 420 H680" stroke="#555"/>
  <path d="M200 500 H680" stroke="#888" stroke-dasharray="2 7"/>
</g>
<g stroke="#1d2733" stroke-width="2">
  <rect x="40" y="76" width="210" height="72" rx="8" fill="#fff"/>
  <rect x="40" y="232" width="160" height="196" rx="8" fill="#dff0e5"/>
  <rect x="380" y="164" width="180" height="168" rx="8" fill="#dbe6fb"/>
  <rect x="380" y="374" width="180" height="104" rx="8" fill="#ece0f8"/>
  <rect x="680" y="172" width="200" height="160" rx="8" fill="#fff"/>
  <rect x="680" y="400" width="200" height="40" rx="8" fill="#fff"/>
  <rect x="40" y="470" width="160" height="60" rx="8" fill="#fff"/>
  <rect x="680" y="470" width="200" height="60" rx="8" fill="#fff"/>
  <rect x="40" y="16" width="210" height="40" rx="8" fill="#fff"/>
</g>
<g fill="#1d2733">
  <text x="52" y="98" font-size="14" font-weight="700">5 V 4 A adapter</text>
  <text x="52" y="118">via the barrel-jack</text><text x="52" y="134">screw adapter</text>
  <text x="240" y="100" text-anchor="end">+5 V</text><text x="240" y="132" text-anchor="end">GND</text>
  <text x="52" y="224" font-size="14" font-weight="700">Raspberry Pi 5</text>
  <text x="190" y="258" text-anchor="end">pin 1 · 3.3 V</text>
  <text x="190" y="280" text-anchor="end">pin 3 · SDA</text>
  <text x="190" y="302" text-anchor="end">pin 5 · SCL</text>
  <text x="190" y="324" text-anchor="end">pin 6 · GND</text>
  <text x="190" y="366" text-anchor="end">pin 11 · GPIO17</text>
  <text x="190" y="388" text-anchor="end">pin 13 · GPIO27</text>
  <text x="190" y="410" text-anchor="end">pin 14 · GND</text>
  <text x="392" y="156" font-size="14" font-weight="700">PCA9685</text>
  <text x="392" y="186">V+</text><text x="392" y="204">GND</text><text x="392" y="222">SDA</text>
  <text x="392" y="240">SCL</text><text x="392" y="258">VCC</text><text x="392" y="276">GND</text>
  <text x="548" y="196" text-anchor="end">ch 0</text><text x="548" y="236" text-anchor="end">ch 1</text>
  <text x="548" y="276" text-anchor="end">ch 2</text><text x="548" y="316" text-anchor="end">ch 3</text>
  <text x="392" y="366" font-size="14" font-weight="700">DRV8833</text>
  <text x="392" y="396">VM</text><text x="392" y="414">GND</text><text x="392" y="432">IN1</text>
  <text x="392" y="450">IN2</text><text x="392" y="468">GND</text>
  <text x="548" y="424" text-anchor="end">OUT1 / OUT2</text>
  <text x="692" y="196" font-size="13">Stop-pin servo</text><text x="692" y="236" font-size="13">Chute tilt servo</text>
  <text x="692" y="276" font-size="13">Right trapdoor servo</text><text x="692" y="316" font-size="13">Left trapdoor servo</text>
  <text x="692" y="425" font-size="13">N20 feeder motor</text>
  <text x="52" y="494" font-size="14" font-weight="700">27 W USB-C supply</text><text x="52" y="514">into the Pi's USB-C</text>
  <text x="692" y="494" font-size="14" font-weight="700">Camera Module 3</text><text x="692" y="514">ribbon to a Pi camera port</text>
  <text x="440" y="494" text-anchor="middle" fill="#555">Pi only, not the servo supply</text>
  <text x="52" y="40" font-size="13">LED strips: a Pi USB port</text>
  <text x="680" y="150" fill="#555">MG90S, signal / + / GND on each channel</text>
</g>
</svg>"""


def img_b64(n):
    with open(os.path.join(IMG, f"step_{n:02d}.png"), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def callout_md(s):
    return re.sub(r"\((\d+)\)", lambda m: "**(" + m.group(1) + ")**", s)


def build_md():
    out = ["# Picture assembly guide", "",
           "How the enclosure build goes together, one picture per step. Every picture is drawn from the "
           "same CAD the STLs come from (`guide/scenes.scad`), so it shows the real parts in their real places. "
           "**Grey** is already fitted, **orange** is what the step adds, **pink arrows** show where it goes, "
           "and numbered circles match the numbers in the text. The longer text version, with the Pi setup and "
           "the feeder test, is [`ASSEMBLY.md`](ASSEMBLY.md); print order and settings are in [`PRINTING.md`](PRINTING.md).",
           "", "A single-file version with the pictures inside: [`assembly_guide.html`](assembly_guide.html) "
           "(download it and open it in a browser).", "",
           "![The finished sorter](img/assembly/step_00.png)", "",
           "> **" + CENTRE[0] + ".** " + CENTRE[1], ">", "> ```python", *["> " + l for l in SNIPPET.splitlines()], "> ```", ""]
    for title, intro, steps in SECTIONS:
        out += [f"## {title}", "", intro, ""]
        for n, t, lines, parts, hw in steps:
            out += [f"### {n}. {t}", "", f"![Step {n}](img/assembly/step_{n:02d}.png)", ""]
            out += ["- " + callout_md(l) for l in lines]
            meta = []
            if parts: meta.append("**Parts:** " + ", ".join(f"`{p}`" for p in parts))
            if hw: meta.append("**You need:** " + ", ".join(hw))
            if meta: out += [""] + ["  \n".join(meta)]
            out.append("")
            if n == 16:
                out += wiring_md()
    out += ["---", "", "Pictures: `python3 guide/render.py` (needs OpenSCAD), then `python3 guide/build_guide.py`."]
    return "\n".join(out) + "\n"


def wiring_md():
    out = ["### Wiring", "", "![Where the electronics go](img/assembly/step_20.png)", ""]
    out += ["- " + callout_md(l) for l in WIRING_STEPS]
    out += ["", "![Wiring diagram](img/assembly/wiring.svg)", "",
            "| PCA9685 channel | Servo | Moves |", "|---|---|---|"]
    out += [f"| {a} | {b} | {c} |" for a, b, c in SERVO_TABLE]
    out += [""] + ["- " + r for r in RULES] + [""]
    return out


# ---- HTML ----------------------------------------------------------------------------------
def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"\((\d+)\)", r'<span class="co">\1</span>', s)
    return s


CSS = """
/* Build-booklet layout: one column of numbered steps, picture first, short lines under it. */
:root {
  --paper: #eef0f2; --sheet: #ffffff; --plate: #f8f8f8; --ink: #1d2733; --muted: #5b6673;
  --rule: #d5dae0; --accent: #e8650f; --accent-ink: #b74c06; --arrow: #d81b60; --chip: #e6e9ed;
  --display: "Barlow Condensed", "Arial Narrow", "Roboto Condensed", sans-serif;
  --body: "IBM Plex Sans", "Segoe UI", Roboto, Arial, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "Cascadia Mono", Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --paper: #14181d; --sheet: #1c2229; --ink: #e7ebef; --muted: #9aa5b1; --rule: #2e3742;
  --accent: #ff8a3d; --accent-ink: #ff9d5c; --arrow: #ff5c8a; --chip: #28313b; color-scheme: dark } }
:root[data-theme="dark"] {
  --paper: #14181d; --sheet: #1c2229; --ink: #e7ebef; --muted: #9aa5b1; --rule: #2e3742;
  --accent: #ff8a3d; --accent-ink: #ff9d5c; --arrow: #ff5c8a; --chip: #28313b; color-scheme: dark }
* { box-sizing: border-box }
img { max-width: 100%; height: auto; display: block }
body { background: var(--paper); color: var(--ink); font: 16px/1.55 var(--body); margin: 0;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
.wrap { max-width: 900px; margin: 0 auto; padding-block: 32px 64px; display: grid; grid-template-columns: minmax(0, 1fr); gap: 28px }
header h1 { font: 700 clamp(2.4rem, 6vw, 3.6rem)/1 var(--display); letter-spacing: .01em; margin: 0 0 10px; text-wrap: balance; text-transform: uppercase }
header p { margin: 0; color: var(--muted); max-width: 62ch }
.hero { background: var(--plate); border-radius: 14px; padding: 12px; display: grid; place-items: center }
.hero img { max-height: 520px; width: auto }
.key { display: flex; flex-wrap: wrap; gap: 8px 18px; font-size: 14px; color: var(--muted) }
.key span { display: inline-flex; align-items: center; gap: 7px }
.sw { width: 14px; height: 14px; border-radius: 3px; display: inline-block }
nav.toc { display: flex; flex-wrap: wrap; gap: 8px }
nav.toc a { font: 600 15px/1 var(--display); letter-spacing: .06em; text-transform: uppercase; color: var(--ink);
  text-decoration: none; padding: 9px 12px; border: 1px solid var(--rule); border-radius: 999px; background: var(--sheet) }
nav.toc a:hover, nav.toc a:focus-visible { border-color: var(--accent); outline: none }
.note { background: var(--sheet); border-left: 4px solid var(--accent); border-radius: 6px; padding: 14px 16px; display: grid; gap: 8px }
.note strong { font-weight: 600 }
pre { margin: 0; background: var(--chip); border-radius: 6px; padding: 10px 12px; overflow-x: auto; font: 13px/1.5 var(--mono) }
section.part { display: grid; grid-template-columns: minmax(0, 1fr); gap: 20px; scroll-margin-top: 16px }
section.part > h2 { font: 700 2rem/1 var(--display); text-transform: uppercase; letter-spacing: .02em; margin: 24px 0 0;
  display: flex; align-items: baseline; gap: 12px; border-bottom: 2px solid var(--ink); padding-bottom: 8px }
section.part > h2 small { font: 600 1rem/1 var(--mono); color: var(--accent-ink) }
section.part > p { margin: -8px 0 0; color: var(--muted) }
article.step { background: var(--sheet); border-radius: 12px; overflow: hidden; display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr) }
article.step .pic { background: var(--plate); display: grid; place-items: center; padding: 10px }
article.step .pic img { max-height: 440px; width: auto }
article.step .txt { padding: 18px 20px 20px; display: grid; gap: 12px; align-content: start; min-width: 0 }
.num { font: 700 3.4rem/.85 var(--display); color: var(--accent) ; font-variant-numeric: tabular-nums }
.txt h3 { font: 700 1.5rem/1.1 var(--display); text-transform: uppercase; letter-spacing: .02em; margin: 0; text-wrap: balance }
.txt ul { margin: 0; padding-left: 18px; display: grid; gap: 6px }
.txt li { padding-left: 2px }
.meta { display: grid; gap: 6px; font-size: 13px; color: var(--muted); border-top: 1px solid var(--rule); padding-top: 10px }
.chips { display: flex; flex-wrap: wrap; gap: 5px }
.chips b { font-weight: 600; color: var(--ink); margin-right: 2px }
.chip { background: var(--chip); border-radius: 4px; padding: 1px 6px; font: 12px/1.6 var(--mono); color: var(--ink) }
code { font: .88em var(--mono); background: var(--chip); border-radius: 3px; padding: 0 4px; overflow-wrap: anywhere }
.co { display: inline-grid; place-items: center; width: 1.45em; height: 1.45em; border-radius: 50%; border: 1.5px solid var(--ink);
  font: 700 .78em/1 var(--body); vertical-align: .08em; margin-right: 2px }
article.wide { grid-template-columns: minmax(0, 1fr) }
article.wide .txt { padding-top: 6px }
.diagram { background: #f8f8f8; padding: 10px; overflow-x: auto }
.diagram svg { display: block; min-width: 640px; width: 100%; height: auto }
table { border-collapse: collapse; width: 100%; font-size: 14px }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--rule) }
th { font: 600 13px/1.2 var(--display); text-transform: uppercase; letter-spacing: .06em; color: var(--muted) }
td:first-child { font-variant-numeric: tabular-nums; font-family: var(--mono) }
footer { color: var(--muted); font-size: 13px; border-top: 1px solid var(--rule); padding-top: 14px }
a { color: var(--accent-ink) }
@media (max-width: 720px) {
  article.step { grid-template-columns: minmax(0, 1fr) }
  article.step .pic img { max-height: 360px }
  .num { font-size: 2.6rem }
}
"""


def step_html(n, t, lines, parts, hw, embed):
    src = img_b64(n) if embed else f"img/assembly/step_{n:02d}.png"
    lis = "".join(f"<li>{inline(l)}</li>" for l in lines)
    meta = ""
    if parts or hw:
        meta = '<div class="meta">'
        if parts: meta += '<div class="chips"><b>Parts</b>' + "".join(f'<span class="chip">{html.escape(p)}</span>' for p in parts) + "</div>"
        if hw: meta += '<div class="chips"><b>You need</b>' + "".join(f'<span class="chip">{html.escape(h)}</span>' for h in hw) + "</div>"
        meta += "</div>"
    return (f'<article class="step" id="step-{n}"><div class="pic"><img src="{src}" alt="Step {n}: {html.escape(t)}" loading="lazy"></div>'
            f'<div class="txt"><div class="num">{n:02d}</div><h3>{html.escape(t)}</h3><ul>{lis}</ul>{meta}</div></article>')


def wiring_html(embed):
    src = img_b64(20) if embed else "img/assembly/step_20.png"
    lis = "".join(f"<li>{inline(l)}</li>" for l in WIRING_STEPS)
    rows = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in SERVO_TABLE)
    rules = "".join(f"<li>{inline(r)}</li>" for r in RULES)
    return (f'<article class="step" id="wiring"><div class="pic"><img src="{src}" alt="Where the electronics go" loading="lazy"></div>'
            f'<div class="txt"><div class="num">16+</div><h3>Wiring: where it all goes</h3><ul>{lis}</ul></div></article>'
            f'<article class="step wide"><div class="diagram">{WIRING_SVG}</div>'
            f'<div class="txt"><table><thead><tr><th>PCA9685 ch</th><th>Servo</th><th>Moves</th></tr></thead><tbody>{rows}</tbody></table>'
            f'<ul>{rules}</ul></div></article>')


def build_html(embed=True):
    hero = img_b64(0) if embed else "img/assembly/step_00.png"
    parts = []
    toc = []
    for i, (title, intro, steps) in enumerate(SECTIONS):
        sid = "part-" + "abc"[i]
        toc.append(f'<a href="#{sid}">{html.escape(title)}</a>')
        body = []
        for s in steps:
            body.append(step_html(*s, embed))
            if s[0] == 16:
                body.append(wiring_html(embed))
        rng = f"steps {steps[0][0]}–{steps[-1][0]}"
        parts.append(f'<section class="part" id="{sid}"><h2>{html.escape(title)} <small>{rng}</small></h2>'
                     f'<p>{inline(intro)}</p>{"".join(body)}</section>')
    toc.append('<a href="#wiring">Wiring</a>')
    return f"""<title>MTG Sorter Assembly</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header><h1>MTG Sorter assembly</h1>
<p>The enclosure build, one picture per step, drawn from the same CAD the STLs come from. Print everything first
(PRINTING.md, or the Bambu Studio project), and have the feeder from Part 1 of ASSEMBLY.md working.</p></header>
<div class="hero"><img src="{hero}" alt="The finished sorter, middle drawer pulled out"></div>
<div class="key"><span><i class="sw" style="background:#a3a9b1"></i>already fitted</span>
<span><i class="sw" style="background:#ff7a1a"></i>this step</span>
<span><i class="sw" style="background:var(--arrow)"></i>where it goes</span>
<span><span class="co">1</span>matches the text</span>
<span><i class="sw" style="background:#2e6fd8"></i>servo</span></div>
<nav class="toc">{"".join(toc)}</nav>
<div class="note"><div><strong>{html.escape(CENTRE[0])}.</strong> {html.escape(CENTRE[1])}</div><pre>{html.escape(SNIPPET)}</pre></div>
{"".join(parts)}
<footer>Screws are self-tapping: about 20 M3 × 8, 30 M2 × 6 and 8 M2.5 × 6. CA glue for the splices in the thin panels (fascia, back, sides).
The build uses 24 splices; print 26 for two spares. Pictures come from <code>hardware/guide/scenes.scad</code>; rebuild with
<code>python3 guide/render.py</code> then <code>python3 guide/build_guide.py</code>.</footer>
</div>
"""


if __name__ == "__main__":
    with open(os.path.join(IMG, "wiring.svg"), "w") as f:
        f.write(WIRING_SVG)
    with open(os.path.join(HW, "ASSEMBLY_PICTURES.md"), "w") as f:
        f.write(build_md())
    page = build_html(embed=True)
    with open(os.path.join(HERE, "artifact.html"), "w") as f:
        f.write(page)
    with open(os.path.join(HW, "assembly_guide.html"), "w") as f:
        f.write('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"></head><body>\n'
                + page + "</body></html>\n")
    print("wrote ASSEMBLY_PICTURES.md, assembly_guide.html, guide/artifact.html")
