#!/usr/bin/env python3
"""Render the scan bed v3 and solid weight pictures to img/bed3/*.png.

    cd hardware/guide/bed3 && npm install --no-save three@0.160.0   # once (three.js, for view.html)
    python3 render.py

Needs OpenSCAD (exports the pieces in scenes.scad as STLs), Node with Playwright and Chromium
(draws them with three.js) and Pillow (crops). Same method as guide/v3.
"""
import http.server, json, os, subprocess, functools, threading, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "img", "bed3")
W = os.path.join(HERE, "w")
PIECES = ["flat", "plate3", "plate2", "card", "card2", "walls", "gate", "hopper", "fgate", "stand", "stack", "tray", "weight"]
C = dict(flat="#f4f4f4", plate3="#f4f4f4", plate2="#b9c3cf", card="#c9a46a", card2="#c9a46a", walls="#2b2b2b", gate="#e8772e",
         hopper="#5a6068", fgate="#3a3f47", stand="#3a3f47", stack="#d8c9a3", tray="#4a4f57", weight="#2b2b2b")


def export():
    os.makedirs(W, exist_ok=True)
    jobs = [(p, False) for p in PIECES] + [(p, True) for p in ("plate3", "plate2", "card", "card2", "hopper", "fgate", "stand", "stack", "gate")]
    def run(j):
        p, s = j
        subprocess.run(["openscad", "-q", "-o", os.path.join(W, p + ("_s" if s else "") + ".stl"), "-D", f'what="{p}"',
                        "-D", f"slice={'true' if s else 'false'}", os.path.join(HERE, "scenes.scad")], check=True)
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(run, jobs))


def m(name, **kw):
    d = {"file": f"w/{name}.stl", "color": C[name.split("_")[0]]}
    d.update(kw)
    return d


jobs = [
    # the bed in the machine: card at the stop teeth, hopper behind, tray with the trapdoors below
    ({"meshes": [m("plate3"), m("card"), m("walls", opacity=0.25), m("gate"), m("hopper", opacity=0.35), m("fgate", opacity=0.5),
                 m("stack", opacity=0.6), m("tray", opacity=0.55)],
      "eye": [260, -260, 420], "ctr": [0, 90, 175]}, "bed3_in_machine.png"),
    # the plate on its own, from the front and above
    ({"meshes": [m("flat")], "eye": [130, -120, 170], "ctr": [0, 50, 0], "light": [0.3, -1, 1.6]}, "bed3_plate.png"),
    ({"meshes": [m("plate3"), m("card", opacity=0.8)], "eye": [0, -40, 420], "ctr": [0, 95, 180]}, "bed3_top_with_card.png"),
    # side section at x = 18: old plate (grey) and new, with the hopper floor the card comes off
    ({"meshes": [m("plate2_s", opacity=0.6), m("plate3_s"), m("card_s"), m("hopper_s"), m("fgate_s"),
                 m("stand_s", opacity=0.4), m("stack_s"), m("gate_s")],
      "eye": [600, 100, 190], "ctr": [18, 100, 190], "fov": 22}, "bed3_side_section.png"),
    ({"meshes": [m("weight")], "eye": [140, -160, 170], "ctr": [0, 0, 8], "light": [0.3, -1, 1.6]}, "weight_solid.png"),
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
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), functools.partial(Quiet, directory=HERE))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    full = [(sc, os.path.join(OUT, out)) for sc, out in jobs]
    json.dump(full, open(os.path.join(W, "jobs.json"), "w"))
    subprocess.run(["node", os.path.join(HERE, "render.js"), os.path.join(W, "jobs.json")], check=True)
    srv.shutdown()
    for _, out in full:
        crop(out)
