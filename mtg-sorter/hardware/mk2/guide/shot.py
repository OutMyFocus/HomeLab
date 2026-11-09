#!/usr/bin/env python3
"""One picture of Mk2 parts: shot.py out.png --eye x,y,z --ctr x,y,z [--fov 30] part.stl:#color[:opacity] ...

STL paths are relative to this folder (../stl/... for exported parts, w/... for scene pieces).
Needs `npm install --no-save three@0.160.0` here once, Node with Playwright, and Pillow.
"""
import argparse, functools, http.server, json, os, subprocess, threading
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("--eye", required=True); ap.add_argument("--ctr", required=True)
ap.add_argument("--fov", type=float, default=30); ap.add_argument("--w", type=int, default=1600); ap.add_argument("--h", type=int, default=1200)
ap.add_argument("meshes", nargs="+")
a = ap.parse_args()
vec = lambda s: [float(v) for v in s.split(",")]
meshes = []
for m in a.meshes:
    p = m.split(":")
    d = {"file": os.path.relpath(os.path.abspath(p[0]), HERE), "color": p[1] if len(p) > 1 else "#3a3f47"}
    if len(p) > 2: d["opacity"] = float(p[2])
    meshes.append(d)
sc = {"meshes": meshes, "eye": vec(a.eye), "ctr": vec(a.ctr), "fov": a.fov, "w": a.w, "h": a.h}
out = os.path.abspath(a.out)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *x): pass
# serve the hardware/mk2 folder so ../stl is reachable; view.html lives in guide/
root = os.path.dirname(HERE)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8766), functools.partial(Q, directory=root))
threading.Thread(target=srv.serve_forever, daemon=True).start()
for d in meshes: d["file"] = "../" + os.path.relpath(os.path.join(HERE, d["file"]), root)
os.makedirs(os.path.join(HERE, "w"), exist_ok=True)
json.dump([[sc, out]], open(os.path.join(HERE, "w", "jobs.json"), "w"))
subprocess.run(["node", os.path.join(HERE, "render.js"), os.path.join(HERE, "w", "jobs.json")], check=True)
srv.shutdown()
from PIL import Image, ImageChops
im = Image.open(out).convert("RGB")
box = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).convert("L").point(lambda v: 255 if v > 12 else 0).getbbox()
if box:
    l, t, r, b = box; im = im.crop((max(0, l - 30), max(0, t - 30), min(im.width, r + 30), min(im.height, b + 30)))
im.save(out, optimize=True)
