#!/usr/bin/env python3
"""Mk2 picture assembly guide: build_guide.py [out.html]

Renders one picture per step from the placed parts in w/at/ (made from ../scene_atoms.scad, see
ATOMS below), then writes a self-contained HTML page (pictures inlined) in the same style as the
Mk1 guide. Run from anywhere; needs what shot.py needs (three.js in node_modules, Playwright, Pillow).
"""
import base64, functools, html, http.server, io, json, math, os, subprocess, sys, threading
import numpy as np
from PIL import Image, ImageChops
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bbox import load

AT = os.path.join(HERE, "w", "at")
SHOTS = os.path.join(HERE, "w", "steps")
GREY, NEW, SERVO, BOARD, METAL, ARROW = "#a3a9b1", "#ff7a1a", "#2e6fd8", "#2d6a4f", "#c8c8c8", 0xd81b60
FRONT, BACK, LEFT = (0.55, -0.8, 0.55), (0.55, 0.8, 0.6), (-0.65, -0.7, 0.45)

_bb = {}
def bb(a):
    if a not in _bb:
        v = load(os.path.join(AT, a + ".stl")).reshape(-1, 3); _bb[a] = (v.min(0), v.max(0))
    return _bb[a]

# ---- the groups the steps are made of ------------------------------------------------------
BASE = ["base_fl", "base_fr", "base_bl", "base_br", "base_keys"]
LV2 = ["lv2_frame", "carriage2", "lever2", "pin2", "psv2"]
LV1 = ["lv1_frame", "carriage1", "lever1", "pin1", "psv1", "doors", "dsv"]
SHAFT = ["col_front", "liner_back"]
SCAN = ["carrier", "bed", "lightbars", "stop_bar", "stop_sv"]
ARCH = ["cam_arch", "cam_hood"]
FEED = ["stand", "n20", "motor_lid", "roller", "hopper", "shoe", "pads"]
TRAY = ["etray", "pi", "pca", "drv", "relay", "wago"]
BACKS = ["back_low", "back_high"]
LIDS = ["lid_front", "lid_back"]
BINS = ["bin0", "bin1", "bin2", "bin3"]

def colour(a, role):
    if a in ("psv1", "psv2", "dsv", "stop_sv"): return SERVO
    if a in ("pi", "pca", "drv", "relay", "wago"): return BOARD
    if a in ("pin1", "pin2", "n20"): return METAL
    return NEW if role == "new" else GREY

def m(atoms, role="old", pos=None, opacity=None):
    return [dict(a=a, role=role, pos=pos, opacity=opacity) for a in atoms]

# ---- the steps -----------------------------------------------------------------------------
# each: part, title, lines, parts (chips), need (chips), meshes, view dir, optional zoom / fov
STEPS = []
def step(**k): STEPS.append(k)

PARTS = [("a", "The box"), ("b", "The levels"), ("c", "The scan module"), ("d", "The feeder"), ("e", "Electronics and cables"), ("f", "Covers and bins")]

step(part="a", title="Join the base",
     lines=["Lay the four base tiles on the table, top up, and push them together.",
            "Press a bowtie key into each of the 5 sockets across the seams.",
            "Push the 3 x 16 mm pins into the seam holes: 3 across the long seam, 2 across the short one.",
            "Press the magnets into their pockets: 1 for the drawer and 2 for each of bins 3 and 4."],
     parts=["base_fl", "base_fr", "base_bl", "base_br", "5 × key"], need=["5 × 3 × 16 mm pin", "5 × magnet"],
     meshes=m(["base_fl"], "new", [-14, -14, 0]) + m(["base_fr"], "new", [14, -14, 0]) + m(["base_bl"], "new", [-14, 14, 0])
            + m(["base_br"], "new", [14, 14, 0]) + m(["base_keys"], "new", [0, 0, 30]),
     arrows="new", dir=(0.45, -0.75, 0.9))
step(part="a", title="Join each wall",
     lines=["Each wall is six tiles: two across and three up.",
            "Lay the tiles inside face up and push them together. Press a key into each of the 9 sockets across the seams.",
            "Push the 3 x 16 mm pins into the seam holes.",
            "Build the left wall the same way. Its tiles are mirror images, so keep the L and R tiles apart."],
     parts=["wall_r00 to r12", "wall_l00 to l12", "18 × key"], need=["3 × 16 mm pins"],
     meshes=sum([m([f"wall_r{iy}{iz}"], "new", [0, iy * 24, iz * 24]) for iy in (0, 1) for iz in (0, 1, 2)], [])
     ,
     arrows=None, dir=(-1, -0.25, 0.3))
step(part="a", title="Slide the walls onto the base",
     lines=["Stand each wall at the front corner of the base, its bottom groove on the dovetail along the base's edge.",
            "Slide it back with a firm push until it's flush with the base's back edge. The dovetail locks the wall down, so the machine can be lifted by its walls.",
            "Press the magnets into the rails (near the closed back end of each rail) and into the top ledge for the lid."],
     parts=["left wall", "right wall"], need=["rail and lid magnets"],
     meshes=m(BASE) + m(["wall_r"], "new", [0, -200, 0]) + m(["wall_l"], "new", [0, -200, 0]),
     arrows=[[[s * 126, 40, 12], [s * 126, 170, 12]] for s in (-1, 1)], dir=(0.6, -0.75, 0.5))

step(part="b", title="Level 2's pusher, on the bench",
     lines=["Press the servo horn into the lever's pocket and push a 3 x 16 mm pin through the lever's end, so 5 mm stands out of its flat face.",
            "Lay the carriage on the frame's guide and slide it to the middle.",
            "Lower the lever in from above so its pin drops into the fork at the top of the crossbar.",
            "Slide the servo in from the back of its box, shaft first into the lever's horn, until the latch clicks over its back. To take it out, lift the latch with a fingernail and pull."],
     parts=["lv2_frame", "carriage2", "lever"], need=["MG90S servo (centred to 90°)", "3 × 16 mm pin"],
     meshes=m(["lv2_frame"]) + m(["carriage2"], "new", [0, 0, 50]) + m(["lever2", "pin2"], "new", [0, 0, 110]) + m(["psv2"], "new", [0, 70, 0]),
     arrows="new", dir=(0.5, 0.85, 0.85), zoom=1.05)
step(part="b", title="Level 2 into the box",
     lines=["Lay a hall sensor flat in each shelf's pocket, legs back along the groove. It reads the bin's magnet through the bin's floor.",
            "Slide level 2 in from the front on the lowest rail, until its magnet clicks.",
            "Its servo wire goes straight back to the trunk in the wall (see the cables step)."],
     parts=["level 2 (from the last step)"], need=["2 × hall sensor (A3144 or similar)"],
     meshes=m(BASE + ["wall_l"]) + m(LV2, "new", [0, -300, 0]),
     arrows="new", dir=FRONT)
step(part="b", title="Shaft liners",
     lines=["The column front and the back liner line the shaft that cards fall down from level 1 to level 2.",
            "Stand each one in level 2's floor groove. The column front's panel sits flush with the machine's face, between bins 1 and 2.",
            "Their top tabs click under level 1's front hinge bar when level 1 goes in, in step 09."],
     parts=["col_front", "liner_back"], need=[],
     meshes=m(BASE + ["wall_l"] + LV2) + m(SHAFT, "new", [0, 0, 90]),
     arrows="new", dir=FRONT, zoom=1.0)
step(part="b", title="Level 1's pusher, on the bench",
     lines=["Same as level 2: horn and pin in the lever, carriage on the guide, lever into the fork, servo in from the back until it clicks."],
     parts=["lv1_frame", "carriage1", "lever"], need=["MG90S servo (centred)", "3 × 16 mm pin"],
     meshes=m(["lv1_frame"]) + m(["carriage1"], "new", [0, 0, 50]) + m(["lever1", "pin1"], "new", [0, 0, 110]) + m(["psv1"], "new", [0, 70, 0]),
     arrows="new", dir=(0.5, 0.85, 0.85), zoom=1.05)
step(part="b", title="Trapdoors and their servos (seen from below)",
     lines=["Hold each door in place under the floor's opening, its left knuckle against the servo pocket.",
            "Slide the two door servos in from the left until their latches click, each horn in its door's pocket.",
            "Push a 3 x 10 mm pin through each door's right knuckle.",
            "Check both doors swing down freely by hand."],
     parts=["2 × door (white)"], need=["2 × MG90S servo (centred)", "2 × 3 × 10 mm pin"],
     meshes=m(["lv1_frame", "carriage1", "lever1", "pin1", "psv1"]) + m(["doors"], "new", [0, 0, -40]) + m(["dsv"], "new", [-80, 0, 0]),
     arrows="new", dir=(-0.7, -0.55, -0.45), zoom=1.05)
step(part="b", title="Level 1 into the box",
     lines=["Slide level 1 in from the front on its rail, until its magnet clicks.",
            "On the way in its front hinge bar rides over the liners' tabs and clicks them home."],
     parts=["level 1 (from the last two steps)"], need=[],
     meshes=m(BASE + ["wall_l"] + LV2 + SHAFT) + m(LV1, "new", [0, -300, 0]),
     arrows="new", dir=FRONT)
step(part="b", title="Bin-full sensors",
     lines=["Slide a TCRT5000 module into each of the four holders: sensor end first, sensor facing out of the open side.",
            "Slide each holder's tongue back into the groove in the frame's stiffener behind its bin. The left holders are the same part turned upside down.",
            "The sensor looks through the slot in the bin's back wall, and the bin in front keeps the holder in its groove."],
     parts=["4 × ir_holder"], need=["4 × TCRT5000 module"],
     meshes=m(BASE + ["wall_l"] + LV2 + SHAFT + LV1) + m(["ir"], "new", [0, -70, 0]),
     arrows="new", dir=(0.25, -1, 0.3), focus=["ir"], zoom=0.9)

step(part="c", title="Stop bar and its servo",
     lines=["Centre the servo first. Push a 3 x 10 mm pin through the stop bar's left arm into the carrier, and press the servo's horn into the right arm.",
            "Click the servo into its box under the carrier until the latch closes.",
            "Swing the bar by hand: it should move freely between up and down."],
     parts=["scan_carrier", "stop_bar"], need=["MG90S servo (centred)", "3 × 10 mm pin"],
     meshes=m(["carrier"]) + m(["stop_bar"], "new", [0, 0, 40]) + m(["stop_sv"], "new", [60, 0, 0]),
     arrows="new", dir=(0.6, -0.7, 0.6), zoom=1.1)
step(part="c", title="Lights and the scan bed",
     lines=["Stick the LED strip pieces into the light box under the bed and into the two light bars.",
            "Drop the light bars into their slots, with the polarizer strips in front of them.",
            "Press the white bed into the carrier's rim until it clicks under the four lips.",
            "Stick the four half-width PTFE strips on the bed's lands."],
     parts=["scan_bed (white)", "2 × lightbar (white)"], need=["LED strip pieces", "polarizer film", "PTFE tape, cut in half"],
     meshes=m(["carrier", "stop_bar", "stop_sv"]) + m(["lightbars"], "new", [0, 0, 60]) + m(["bed"], "new", [0, 0, 110]),
     arrows="new", dir=(0.6, -0.7, 0.6), zoom=1.1)
step(part="c", title="Scan module into the box",
     lines=["Slide the carrier in from the front on the scan rail, above level 1, until its magnet clicks.",
            "The stop bar must be up whenever level 1's pusher moves. The app does that for you."],
     parts=["scan module (from the last two steps)"], need=[],
     meshes=m(BASE + ["wall_l"] + LV2 + SHAFT + LV1) + m(SCAN, "new", [0, -300, 0]),
     arrows="new", dir=FRONT)
step(part="c", title="Camera arch",
     lines=["Slide the camera arch in on the same rail after the carrier.",
            "A key joins each of its feet to the carrier's skids, so the camera can't move relative to the card.",
            "Clip the camera onto its two pegs under the arch's plate, put the polarizer disc in the hood and twist the hood on."],
     parts=["cam_arch", "cam_hood", "2 × key"], need=["Camera Module 3", "polarizer disc"],
     meshes=m(BASE + ["wall_l"] + LV2 + SHAFT + LV1 + SCAN) + m(["cam_arch"], "new", [0, -300, 0]) + m(["cam_hood"], "new", [0, -300, -40]),
     arrows="new", dir=FRONT)

step(part="d", title="Feeder cartridge, on the bench",
     lines=["Lay the N20 motor in its pod and snap the motor lid over it. Fit the roller on the shaft.",
            "Drop the magazine onto the stand's ridge.",
            "Stick the two PTFE strips in the magazine floor's tracks and the cork pads under the shoe. The shoe rests on the wheels by its own weight."],
     parts=["fd_stand", "fd_motor_lid", "fd_roller", "fd_hopper", "fd_shoe"], need=["N20 motor, 60 RPM", "2 × cork pad", "PTFE tape"],
     meshes=m(["stand"]) + m(["n20"], "new", [0, 0, 30]) + m(["motor_lid"], "new", [0, 0, 70]) + m(["roller"], "new", [0, -40, 0])
            + m(["hopper"], "new", [0, 0, 90]) + m(["shoe", "pads"], "new", [0, 0, 430]),
     arrows=None, dir=(0.6, -0.75, 0.55), zoom=1.0)
step(part="d", title="Feeder into the box",
     lines=["Leave the upper back panel off for now.",
            "Slide the cartridge in from the back on the top rail, until its magnets click.",
            "Its motor wire runs down the wall's feeder branch to the trunk."],
     parts=["feeder cartridge (from the last step)"], need=[],
     meshes=m(BASE + ["wall_l"] + LV2 + SHAFT + LV1 + SCAN + ARCH) + m(FEED, "new", [0, 300, 0]),
     arrows="new", dir=BACK)

step(part="e", title="Fill the electronics tray",
     lines=["Press the Pi 5 and the PCA9685 onto their pegs, ports to the back.",
            "Push the relay and the DRV8833 into their cradles until the hooks click, and the Wago blocks into their holder.",
            "Snap the comb over the PCA9685's servo plugs so none can work loose.",
            "Fit the DC jack in the back plate's 11 mm hole with its nut."],
     parts=["etray", "pca_comb"], need=["Pi 5", "PCA9685", "DRV8833", "5 V relay", "2 × Wago 221-415", "panel DC jack"],
     meshes=m(["etray"]) + m(["pi", "pca", "drv", "relay", "wago"], "new", [0, 0, 40]),
     arrows=None, dir=(0.45, 0.8, 0.9), zoom=1.1)
step(part="e", title="Tray into the box",
     lines=["Slide the tray in from the back on the base's two rails, until it clicks.",
            "Plug each module's labelled JST-XH plug into the patch bar along the tray's front."],
     parts=["electronics tray (from the last step)"], need=[],
     meshes=m(BASE + ["wall_l"] + LV2 + SHAFT + LV1 + SCAN + ARCH + FEED) + m(TRAY, "new", [0, 300, 0]),
     arrows="new", dir=BACK)
step(part="e", title="Cables in the trunks",
     lines=["Each wall has a cable trunk at y 76 with three click-in lids. Fit the lids with their notches to the back, and a wire drops into the trunk wherever it meets it.",
            "Wires cross to the trunk only where nothing moves: behind the bins and under the back beams.",
            "Red: servo wires. Yellow: bin sensors. Orange: the trunk down to the tray."],
     parts=["6 × trunk_lid", "branch_lid"], need=["JST-XH plugs", "labels"],
     cables=True, dir=(0.76, -0.56, 0.7), eye=[760, -560, 700], ctr=[0, 80, 280], fov=34)

step(part="f", title="Back panels",
     lines=["Drop the two back panels into the back grooves from the top, the low one first.",
            "Their louvres slope down to the outside, so warm air gets out and room light can't reach the scan bed."],
     parts=["back_low", "back_high"], need=[],
     meshes=m(BASE + ["wall_l", "wall_r"] + LV2 + SHAFT + LV1 + SCAN + ARCH + FEED + TRAY) + m(["back_low"], "new", [0, 0, 330]) + m(["back_high"], "new", [0, 0, 380]),
     arrows=None, dir=(-0.55, 0.85, 0.55))
step(part="f", title="Front cover and lid",
     lines=["Drop the front cover in from the top.",
            "Lay the two lid halves on the ledge between the walls, where the magnets hold them."],
     parts=["front_cover", "lid_front", "lid_back"], need=[],
     meshes=m(BASE + ["wall_l", "wall_r"] + LV2 + SHAFT + LV1 + SCAN + ARCH + FEED + TRAY + BACKS) + m(["front_cover"], "new", [0, 0, 300])
            + m(LIDS, "new", [0, 0, 120]),
     arrows=None, dir=FRONT)
step(part="f", title="Drawer and bins",
     lines=["Slide the drawer in under the bins until its magnet clicks.",
            "Slide the four bins in on their runners. Any bin goes in any slot.",
            "Plug in the 5 V brick (never 12 V) and press the button."],
     parts=["drawer", "4 × bin"], need=["5 V 10 A brick"],
     meshes=m(BASE + ["wall_l", "wall_r"] + LV2 + SHAFT + LV1 + SCAN + ARCH + FEED + TRAY + BACKS + LIDS + ["front_cover"])
            + m(["drawer"], "new", [0, -150, 0]) + m(BINS, "new", [0, -180, 0]),
     arrows=None, dir=FRONT)

# ---- scenes --------------------------------------------------------------------------------
def scene(s):
    if s.get("cables"):
        W = os.path.join(HERE, "w")
        ms = [dict(file="w/g_wall_r.stl", color="#2b2b2b", opacity=0.18), dict(file="w/g_wall_l.stl", color=GREY),
              dict(file="w/g_lids.stl", color=NEW), dict(file="w/g_base.stl", color=GREY),
              dict(file="w/g_lvframes.stl", color=GREY, opacity=0.55), dict(file="w/g_servos.stl", color=SERVO),
              dict(file="w/g_ir.stl", color=GREY), dict(file="w/g_etray.stl", color=BOARD),
              dict(file="w/g_w_servo.stl", color="#e63946"), dict(file="w/g_w_sense.stl", color="#f4c430"), dict(file="w/g_w_trunk.stl", color="#ff8c00")]
        lo, hi = np.array([-125., -66, 0]), np.array([125., 242, 420])
        return ms, [], lo, hi
    ms, arrows, lo, hi = [], [], np.full(3, 1e9), np.full(3, -1e9)
    for d in s["meshes"]:
        p = np.array(d["pos"] or [0, 0, 0], float)
        a, b = bb(d["a"]); lo = np.minimum(lo, a + p); hi = np.maximum(hi, b + p)
        e = dict(file="w/at/%s.stl" % d["a"], color=colour(d["a"], d["role"]))
        if d["pos"]: e["pos"] = list(p)
        if d["opacity"]: e["opacity"] = d["opacity"]
        ms.append(e)
    if isinstance(s.get("arrows"), list):
        size = float(np.linalg.norm(hi - lo))
        for f, t in s["arrows"]: arrows.append([f, t, ARROW, max(3.0, size * 0.007)])
    if s.get("arrows") == "new":
        moved = {}
        for d in s["meshes"]:
            if d["role"] == "new" and d["pos"]: moved.setdefault(tuple(d["pos"]), []).append(d["a"])
        size = float(np.linalg.norm(hi - lo))
        for pos, atoms in moved.items():
            p = np.array(pos, float); L = np.linalg.norm(p); u = -p / L
            a = np.min([bb(x)[0] for x in atoms], 0); b = np.max([bb(x)[1] for x in atoms], 0)
            c = (a + b) / 2; h = abs(np.dot((b - a) / 2, u))
            st = c + p + u * (h + 6); ln = max(min(L * 0.6, L - 6), 30)
            arrows.append([list(st), list(st + u * ln), ARROW, max(3.0, size * 0.007)])
    return ms, arrows, lo, hi

def camera(s, lo, hi):
    if "eye" in s: return s["eye"], s["ctr"], s["fov"]
    if "focus" in s:
        lo = np.min([bb(a)[0] for a in s["focus"]], 0); hi = np.max([bb(a)[1] for a in s["focus"]], 0)
        p = next(np.array(d["pos"] or [0, 0, 0], float) for d in s["meshes"] if d["a"] == s["focus"][0])
        lo = np.minimum(lo, lo + p); hi = np.maximum(hi, hi + p)
        r = max(np.linalg.norm(hi - lo) / 2, 200)
    else: r = np.linalg.norm(hi - lo) / 2
    d = np.array(s["dir"], float); d /= np.linalg.norm(d)
    c = (lo + hi) / 2
    fov = s.get("fov", 28)
    dist = r / math.sin(math.radians(fov / 2)) * s.get("zoom", 1.0) * 0.98
    return list(c + d * dist), list(c), fov

def render():
    os.makedirs(SHOTS, exist_ok=True)
    jobs = []
    for i, s in enumerate(STEPS, 1):
        ms, arrows, lo, hi = scene(s)
        eye, ctr, fov = camera(s, lo, hi)
        for e in ms: e["file"] = "../guide/" + e["file"]
        out = os.path.join(SHOTS, "step%02d.png" % i)
        jobs.append([dict(meshes=ms, arrows=arrows, eye=eye, ctr=ctr, fov=fov, w=1800, h=1400), out])
    json.dump(jobs, open(os.path.join(HERE, "w", "jobs_guide.json"), "w"))
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *x): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8766), functools.partial(Q, directory=os.path.dirname(HERE)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    subprocess.run(["node", os.path.join(HERE, "render.js"), os.path.join(HERE, "w", "jobs_guide.json")], check=True)
    srv.shutdown()
    for _, out in jobs:
        im = Image.open(out).convert("RGB")
        box = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).convert("L").point(lambda v: 255 if v > 12 else 0).getbbox()
        if box:
            l, t, r, b = box; im = im.crop((max(0, l - 24), max(0, t - 24), min(im.width, r + 24), min(im.height, b + 24)))
        im.save(out)

def data_uri(path, maxw=1000):
    im = Image.open(path).convert("RGB")
    if im.width > maxw: im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=84, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

CSS = open(os.path.join(HERE, "guide.css")).read()
def page(out):
    E = html.escape
    hero = data_uri(os.path.join(HERE, "w", "hero.png"), 900)
    toc = "".join('<a href="#part-%s">%s</a>' % (k, E(t)) for k, t in PARTS)
    body = []
    n = 0
    for k, t in PARTS:
        body.append('<section class="part" id="part-%s"><h2><small>PART %s</small>%s</h2>' % (k, k.upper(), E(t)))
        for s in STEPS:
            if s["part"] != k: continue
            n += 1
            lis = "".join("<li>%s</li>" % E(l) for l in s["lines"])
            chips = ""
            if s["parts"]: chips += '<div class="chips"><b>Parts</b>' + "".join('<span class="chip">%s</span>' % E(p) for p in s["parts"]) + "</div>"
            if s["need"]: chips += '<div class="chips"><b>You need</b>' + "".join('<span class="chip">%s</span>' % E(p) for p in s["need"]) + "</div>"
            body.append('<article class="step" id="step-%d"><div class="pic"><img src="%s" alt="Step %d: %s" loading="lazy"></div>'
                        '<div class="txt"><div class="num">%02d</div><h3>%s</h3><ul>%s</ul><div class="meta">%s</div></div></article>'
                        % (n, data_uri(os.path.join(SHOTS, "step%02d.png" % n)), n, E(s["title"]), n, E(s["title"]), lis, chips))
        body.append("</section>")
    doc = TEMPLATE.replace("{{CSS}}", CSS).replace("{{HERO}}", hero).replace("{{TOC}}", toc).replace("{{BODY}}", "\n".join(body))
    open(out, "w").write(doc)   # the page as the Artifact tool publishes it (it adds the skeleton)
    print("wrote", out, os.path.getsize(out) // 1024, "KB")
    full = out[:-5] + "_standalone.html"   # the same page with its own skeleton, to open from a folder
    open(full, "w").write('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
                          'content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>\n' + doc + "\n</body></html>")

TEMPLATE = open(os.path.join(HERE, "guide_template.html")).read()

if __name__ == "__main__":
    if "--no-render" not in sys.argv: render()
    page(next((a for a in sys.argv[1:] if a.endswith(".html")), os.path.join(HERE, "MTG_Sorter_Mk2_Picture_Assembly.html")))
