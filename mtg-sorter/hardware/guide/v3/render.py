#!/usr/bin/env python3
"""Render the chute v3 / front bridge v3 pictures to img/v3/*.png. Then run build.py.

    cd hardware/guide/v3 && npm install three@0.160.0   # once (three.js, for view.html)
    python3 guide/v3/render.py

Needs OpenSCAD (to export the pieces in scenes.scad as STLs), Node with Playwright and Chromium
(to draw them with three.js), and Pillow (to crop). The pictures are drawn in a browser because
headless OpenSCAD can't always get an OpenGL context.
"""
import http.server, json, os, subprocess, sys, threading, functools
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "img", "v3")
W = os.path.join(HERE, "w")    # exported pieces (not committed)
C = dict(tray="#e8772e", frame="#2b2b2b", doors="#d9d9d9", mech="#4a4f57", servos="#3060c0", bridge="#6b7280", cap="#ef4444",
         back="#9ca3af", div="#3a3f47", crank="#4a4f57", scrank="#4a4f57", link="#4a4f57", tiltservo="#3060c0", tiltbr="#2b2b2b")
MOVING = ("tray", "frame", "doors", "mech", "servos")
STATIC = ("crank", "scrank", "link", "bridge", "cap", "back", "div", "tiltbr", "tiltservo")


def export():
    os.makedirs(W, exist_ok=True)
    cmds = [(f"{p}_{t}_{o}", p, t, o) for p in MOVING for t, o in ((0, 0), (0, 1), (25, 0))] + [(p, p, 0, 0) for p in STATIC]
    def run(c):
        name, p, t, o = c
        subprocess.run(["openscad", "-q", "-o", os.path.join(W, name + ".stl"), "-D", f'what="{p}"', "-D", f"tilt={t}",
                        "-D", f"open={o}", os.path.join(HERE, "scenes.scad")], check=True)
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(run, cmds))


def m(name, color=None, **kw):
    d = {"file": f"w/{name}.stl", "color": color or C[name.split("_")[0]]}
    d.update(kw)
    return d


def mech(t, o, parts=MOVING):
    return [m(f"{p}_{t}_{o}") for p in parts]


NEW = "#f5b041"   # highlight colour for the part a step adds
screws = [(-46, -49.5), (-20, -49.5), (20, -49.5), (46, -49.5), (-46, 48.5), (0, 48.5), (46, 48.5)]
jobs = [
    ({"meshes": mech(0, 0) + [m("bridge"), m("cap"), m("div", opacity=0.5)], "eye": [330, -420, 330], "ctr": [0, -10, 130]}, "g/overview.png"),
    ({"meshes": [m("bridge", NEW), m("cap", pos=[0, 0, 28]), m("back", opacity=0.35), m("div", opacity=0.6)],
      "arrows": [[[0, -72, 205], [0, -72, 180]]], "eye": [300, -420, 330], "ctr": [0, 0, 120]}, "g/step1_bridge.png"),
    ({"meshes": [m("tray_0_0"), m("servos_0_0", NEW)], "eye": [-170, 260, 330], "ctr": [0, -30, 170]}, "g/step2_servos.png"),
    ({"meshes": [m("tray_0_0"), m("servos_0_0"), m("doors_0_0", NEW), m("frame_0_0", NEW, pos=[0, 0, -30])],
      "arrows": [[[x, y, 92], [x, y, 118]] for x, y in screws], "eye": [260, -330, -120], "ctr": [0, 0, 130]}, "g/step3_doors.png"),
    ({"meshes": [m("tray_0_0"), m("servos_0_0"), m("doors_0_0"), m("frame_0_0"), m("crank", NEW), m("scrank", NEW), m("link", NEW, pos=[0, -12, 0])],
      "arrows": [[[x, -95, z], [x, -78, z]] for x, z in [(26.8, 148.9), (18.2, 186.9), (-26.8, 148.9), (-18.2, 186.9)]],
      "eye": [140, -330, 230], "ctr": [0, -55, 165]}, "g/step4_links.png"),
    ({"meshes": [m("bridge"), m("cap", pos=[0, 0, 45]), m("tiltbr"), m("tiltservo"), m("div", opacity=0.5)]
                + [m(f"{p}_0_0", pos=[0, 0, 30]) for p in ("tray", "frame", "doors", "mech", "servos")],
      "arrows": [[[0, -90, 200], [0, -90, 175]], [[0, 75, 205], [0, 75, 180]]], "eye": [360, -380, 360], "ctr": [0, 0, 150]}, "g/step5_install.png"),
    ({"meshes": mech(0, 0) + [m("bridge"), m("cap"), m("div")], "eye": [0, -560, 150], "ctr": [0, 0, 135], "w": 1200, "h": 1200}, "g/state_shut.png"),
    ({"meshes": mech(0, 1) + [m("bridge"), m("cap"), m("div")], "eye": [0, -560, 150], "ctr": [0, 0, 135], "w": 1200, "h": 1200}, "g/state_open.png"),
    ({"meshes": mech(25, 0) + [m("bridge"), m("cap"), m("div")], "eye": [0, -560, 150], "ctr": [0, 0, 135], "w": 1200, "h": 1200}, "g/state_tilt.png"),
]


def crop(path, margin=30):
    from PIL import Image, ImageChops
    im = Image.open(path).convert("RGB")
    box = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).convert("L").point(lambda v: 255 if v > 12 else 0).getbbox()
    if box:
        l, t, r, b = box
        im = im.crop((max(0, l - margin), max(0, t - margin), min(im.width, r + margin), min(im.height, b + margin)))
    im.save(path, optimize=True)


if __name__ == "__main__":
    if "--no-export" not in sys.argv:
        export()
    os.makedirs(OUT, exist_ok=True)
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    handler = functools.partial(Quiet, directory=HERE)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    full = [(sc, os.path.join(OUT, out.split("/")[-1])) for sc, out in jobs]
    json.dump(full, open(os.path.join(W, "jobs.json"), "w"))
    subprocess.run(["node", os.path.join(HERE, "render.js"), os.path.join(W, "jobs.json")], check=True)
    srv.shutdown()
    for _, out in full:
        crop(out)
