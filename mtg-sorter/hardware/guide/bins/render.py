#!/usr/bin/env python3
"""Pictures of the sorter bins and the organizer: img/bins/*.png.

    cd hardware/guide/v3 && npm install three@0.160.0   # once
    python3 guide/bins/render.py

Same renderer as the chute v3 guide (guide/v3/view.html + render.js, three.js in Chromium).
"""
import json, os, subprocess, sys, threading, functools, http.server
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.join(HERE, "..", "v3")
W = os.path.join(V3, "w", "bins")
OUT = os.path.join(HERE, "..", "..", "img", "bins")
PIECES = {"org22": {}, "org12": {}, "bin_l": {}, "bin_r": {}, "bin_m_top": {}, "bin_m": {"out": 0},
          "bin_m_out": {"what": "bin_m", "out": 130}, "cards_out": {"what": "cards", "out": 130},
          "dividers_out": {"what": "dividers", "out": 130}, "bin": {}, "org22_alone": {}, "keys": {}}
# the bins in the sorter's dock (sorter_scene.scad)
SORTER = {"s_floor": {"what": "floor"}, "s_dividers": {"what": "dividers"}, "s_posts": {"what": "posts"},
          "s_fascia": {"what": "fascia"}, "s_bridge": {"what": "bridge"}, "s_chute": {"what": "chute"},
          "s_bin_l": {"what": "bin_l"}, "s_bin_r": {"what": "bin_r"}, "s_bin_m": {"what": "bin_m", "out": 110}}
ORG, BLUE, CREAM, RED, CARD, WHITE = "#2a2d33", "#2d63b8", "#e5e2d6", "#d8262a", "#c9a46a", "#f4f4f4"


def export():
    os.makedirs(W, exist_ok=True)
    def run(item):
        name, d = item
        src = "sorter_scene.scad" if name.startswith("s_") else "scenes.scad"
        args = ["openscad", "-q", "--export-format", "binstl", "-o", os.path.join(W, name + ".stl"),
                "-D", 'what="%s"' % d.get("what", name)]
        if "out" in d:
            args += ["-D", "out=%d" % d["out"]]
        subprocess.run(args + [os.path.join(HERE, src)], check=True)
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(run, list(PIECES.items()) + list(SORTER.items())))


def m(name, color, **kw):
    d = {"file": "w/bins/%s.stl" % name, "color": color}
    d.update(kw)
    return d


cabinet = [m("org22", ORG), m("org12", ORG)]
jobs = [
    ({"meshes": cabinet + [m("bin_l", BLUE), m("bin_r", RED), m("bin_m_top", CREAM), m("bin_m_out", CREAM),
                           m("cards_out", CARD, edgeOpacity=0.15), m("dividers_out", WHITE)],
      "eye": [520, -760, 520], "ctr": [10, -40, 110]}, "organizer_full.png"),
    ({"meshes": [m("s_floor", "#3a3f47"), m("s_dividers", "#3a3f47"), m("s_posts", "#1b1d21"), m("s_fascia", "#2c3036", opacity=0.35),
                 m("s_bridge", "#555b63"), m("s_chute", "#e8772e"), m("s_bin_l", BLUE), m("s_bin_r", RED), m("s_bin_m", CREAM)],
      "eye": [430, -720, 420], "ctr": [0, -40, 80]}, "bins_in_sorter.png"),
    ({"meshes": [m("org22_alone", ORG)], "eye": [420, -620, 380], "ctr": [0, 110, 110]}, "organizer_2x2.png"),
    ({"meshes": [m("org22_alone", ORG)], "eye": [-380, 760, 300], "ctr": [0, 110, 110]}, "organizer_back.png"),
    ({"meshes": [m("bin", CREAM)], "eye": [260, -380, 260], "ctr": [0, 100, 45]}, "bin.png"),
    ({"meshes": [m("bin", CREAM)], "eye": [90, -260, 150], "ctr": [0, 0, 70], "fov": 26}, "bin_front.png"),
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
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), functools.partial(Quiet, directory=V3))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    full = [(sc, os.path.abspath(os.path.join(OUT, out))) for sc, out in jobs]
    json.dump(full, open(os.path.join(W, "jobs.json"), "w"))
    subprocess.run(["node", os.path.join(V3, "render.js"), os.path.join(W, "jobs.json")], check=True)
    srv.shutdown()
    for _, out in full:
        crop(out)
