#!/usr/bin/env python3
"""Render the feeder box v4 pictures to img/feeder4/*.png.

    cd hardware/guide/feeder4 && npm install --no-save three@0.160.0   # once (three.js, for view.html)
    python3 render.py

Needs OpenSCAD, Node with Playwright and Chromium, and Pillow. Same method as guide/bed3.
"""
import http.server, json, os, subprocess, functools, threading, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "img", "feeder4")
W = os.path.join(HERE, "w")
PIECES = ["bed", "walls", "gate", "stand", "hopper", "shoe", "pads", "roller", "motor", "stack", "card", "weight",
          "fence", "bridge", "p_stand", "p_hopper", "p_shoe", "p_roller", "flatbed", "tower", "deck"]
SLICED = ["bed", "stand", "hopper", "shoe", "pads", "roller", "stack", "card"]
YSLICED = ["stand", "hopper", "fence", "bridge"]
C = dict(bed="#f4f4f4", flatbed="#f4f4f4", walls="#2b2b2b", gate="#e8772e", stand="#3a3f47", hopper="#5a6068",
         shoe="#2b2b2b", pads="#b07a43", roller="#f08c1a", motor="#b8bcc2", stack="#d8c9a3", card="#c9a46a",
         weight="#2b2b2b", fence="#e8772e", bridge="#2c3036", p_stand="#3a3f47", p_hopper="#5a6068",
         p_shoe="#2b2b2b", p_roller="#f08c1a", tower="#2b2b2b", deck="#3a3f47")


def export():
    os.makedirs(W, exist_ok=True)
    jobs = [(p, "") for p in PIECES] + [(p, "_s") for p in SLICED] + [(p, "_y") for p in YSLICED]
    def run(j):
        p, s = j
        subprocess.run(["openscad", "-q", "-o", os.path.join(W, p + s + ".stl"), "-D", f'what="{p}"',
                        "-D", f"slice={'true' if s == '_s' else 'false'}", "-D", f"yslice={'true' if s == '_y' else 'false'}",
                        os.path.join(HERE, "scenes.scad")], check=True)
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(run, jobs))


def m(name, **kw):
    d = {"file": f"w/{name}.stl", "color": C[name[:-2] if name[-2:] in ("_s", "_y") else name]}
    d.update(kw)
    return d


jobs = [
    # the box in the machine, from the front right: card half way out onto the bed
    ({"meshes": [m("bridge"), m("fence"), m("bed"), m("gate"), m("stand"), m("roller"), m("motor"),
                 m("hopper", opacity=0.45), m("stack", opacity=0.7), m("weight", opacity=0.8), m("shoe"), m("pads"), m("card")],
      "eye": [-230, -140, 400], "ctr": [0, 160, 190]}, "feeder4_in_machine.png"),
    # the stand in the bridge's fence, from above
    ({"meshes": [m("bridge"), m("fence"), m("stand")], "eye": [0, 181, 3000], "ctr": [0, 181, 110], "fov": 4.2}, "feeder4_fence_fit.png"),
    # side section through the right wheel
    ({"meshes": [m("bed_s"), m("stand_s", opacity=0.5), m("hopper_s"), m("shoe_s"), m("pads_s"), m("roller_s"),
                 m("stack_s"), m("card_s")],
      "eye": [560, 140, 205], "ctr": [16, 140, 205], "fov": 14}, "feeder4_side_section.png"),
    # the foot and the ridge, cut across the box: the stand's foot closes over the bridge's fence,
    # the hopper's groove sits on the stand's ridge
    ({"meshes": [m("bridge_y"), m("fence_y"), m("stand_y"), m("hopper_y")],
      "eye": [-37, -400, 113], "ctr": [-37, 190, 113], "fov": 1.6, "w": 1200, "h": 900}, "feeder4_foot_lock.png"),
    ({"meshes": [m("stand_y"), m("hopper_y")],
      "eye": [-35, -400, 204], "ctr": [-35, 190, 204], "fov": 1.6, "w": 1200, "h": 900}, "feeder4_ridge_lock.png"),
    # the mouth from the front and below: shoe, pads, wheels in the bed's slots
    ({"meshes": [m("bed"), m("stand"), m("roller"), m("motor"), m("hopper", opacity=0.35), m("shoe"), m("pads")],
      "eye": [90, 30, 250], "ctr": [0, 150, 205], "fov": 26}, "feeder4_mouth.png"),
    # the parts as printed
    ({"meshes": [m("p_stand", pos=[-100, 0, 0]), m("p_hopper", pos=[0, 0, 0]), m("p_shoe", pos=[100, -165, 0]),
                 m("p_roller", pos=[100, 50, 0])],
      "eye": [170, -380, 330], "ctr": [10, -30, 30]}, "feeder4_parts.png"),
    # the hopper tower on the deck, open at the front so it can't press the shoe onto the wheels
    ({"meshes": [m("bed"), m("deck", opacity=0.9), m("stand"), m("roller"), m("motor"), m("hopper"), m("shoe"), m("pads"),
                 m("stack"), m("tower", opacity=0.55)],
      "eye": [-200, -120, 420], "ctr": [0, 180, 235]}, "feeder4_tower_open.png"),
    # the scan bed v3.1 plate with the two wheel slots at its back edge
    ({"meshes": [m("flatbed")], "eye": [120, 230, 150], "ctr": [0, 70, 0], "light": [0.3, 1, 1.6]}, "bed3_wheel_slots.png"),
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
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8766), functools.partial(Quiet, directory=HERE))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    only = [a for a in sys.argv[1:] if a.endswith(".png")]
    full = [(sc, os.path.join(OUT, out)) for sc, out in jobs if not only or out in only]
    json.dump(full, open(os.path.join(W, "jobs.json"), "w"))
    subprocess.run(["node", os.path.join(HERE, "render.js"), os.path.join(W, "jobs.json")], check=True)
    srv.shutdown()
    for _, out in full:
        crop(out)
