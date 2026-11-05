#!/usr/bin/env python3
"""Pictures for the front bridge swap (img/v3/bridge_*.png). Run render.py once first (it exports
the pieces in scenes.scad to w/), then this. Then build_bridge.py."""
import functools, http.server, json, os, subprocess, sys, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import HERE, OUT, W, C, m, crop

C.update(old="#a3a9b1", splices="#f5b041", walls="#2b2b2b", legs="#3a3f47", floor="#d6d3cc", feeder="#555b63", new="#f5b041")
NEW = "#f5b041"
GHOST = dict(opacity=0.35, edgeOpacity=0.15)
flange = [(x, y) for x in (-48, 48) for y in (-57.3, 33.75)]   # the four in the front half
splice = [(x + dx, 56 + dy) for x in (-26, 26) for dx in (-4, 4) for dy in (-12, 12)]
legs = [(-45, 253.5), (45, 253.5)]
TOP = ["back", "walls", "feeder"]
def up(pts, z0, z1): return [[[x, y, z0], [x, y, z1]] for x, y in pts]
def lift(names, dz=0, dy=0, **kw): return [m(n, pos=[0, dy, dz], **kw) for n in names]
CAP_TRAY = [m(f"{p}_0_0") for p in ("tray", "frame", "doors", "mech", "servos")]
jobs = [
    ({"meshes": [m("old_front", C["old"], pos=[-80, 0, 0]), m("bridge", NEW, pos=[80, 0, 0]), m("cap", pos=[80, 0, 0])],
      "eye": [260, -520, 360], "ctr": [0, -10, 120]}, "bridge_1_compare.png"),
    ({"meshes": [m("floor", **GHOST), m("div"), m("legs"), m("old_front", C["old"])] + [m(n) for n in TOP],
      "arrows": up(flange, 116, 160), "eye": [380, -460, 400], "ctr": [0, 40, 110]}, "bridge_2_screws.png"),
    ({"meshes": [m("old_front", C["old"])] + [m(n) for n in TOP] + [m("splices", pos=[0, 0, -22])],
      "arrows": [[[x, y, 104], [x, y, 70]] for x, y in splice], "eye": [260, -200, -330], "ctr": [0, 60, 105]}, "bridge_3_splices.png"),
    ({"meshes": [m("old_front", C["old"], pos=[0, -35, 0])] + [m(n) for n in TOP],
      "arrows": [[[0, -40, 125], [0, -95, 125]]], "eye": [330, -330, 330], "ctr": [0, 20, 120]}, "bridge_4_slide_off.png"),
    ({"meshes": [m("bridge", NEW, pos=[0, -35, 0])] + [m(n) for n in TOP],
      "arrows": [[[0, -125, 130], [0, -80, 130]]], "eye": [330, -330, 330], "ctr": [0, 20, 120]}, "bridge_5_slide_on.png"),
    ({"meshes": [m("bridge", NEW)] + [m(n) for n in TOP] + [m("splices", pos=[0, 0, -22])],
      "arrows": [[[x, y, 70], [x, y, 104]] for x, y in splice], "eye": [260, -200, -330], "ctr": [0, 60, 105]}, "bridge_6_splices_on.png"),
    ({"meshes": [m("floor", **GHOST), m("div"), m("legs"), m("bridge", NEW)] + [m(n) for n in TOP],
      "arrows": up(flange, 160, 116), "eye": [380, -460, 400], "ctr": [0, 40, 110]}, "bridge_7_screws.png"),
    ({"meshes": [m("bridge"), m("div")] + CAP_TRAY + [m("cap", pos=[0, 0, 30])],
      "arrows": [[[x, -72, 215], [x, -72, 195]] for x in (-10, 10)], "eye": [170, -330, 260], "ctr": [0, -60, 150]}, "bridge_8_cap.png"),
]
if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), functools.partial(Quiet, directory=HERE))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    full = [(sc, os.path.join(OUT, out)) for sc, out in jobs]
    json.dump(full, open(os.path.join(W, "jobs.json"), "w"))
    subprocess.run(["node", os.path.join(HERE, "render.js"), os.path.join(W, "jobs.json")], check=True)
    srv.shutdown()
    for _, out in full: crop(out)
