#!/usr/bin/env python3
"""Render the mechanism v2 picture scenes to img/v2/feeder_NN.png and img/v2/bed_NN.png.
Needs OpenSCAD and, on a headless machine, xvfb-run. Then run build.py.
    python3 guide/v2/render.py              # all
    python3 guide/v2/render.py feeder 3     # one
"""
import os, shutil, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from render import crop

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "img", "v2")

ZOOM = 1.35   # eye further back than the views below, so nothing is cut off
FR = ((260, -300, 230), (0, 40, 80))      # front right, above
VIEWS = {
    "feeder": {
        1: ((90, -110, 70), (0, 20, 95)),
        2: ((120, -130, 110), (20, 20, 85)),
        3: ((90, -130, 100), (0, 20, 95)),
        4: ((260, -320, 200), (0, 40, 110)),
        5: ((380, 30, 90), (0, 45, 55)),
        6: ((300, -340, 300), (0, 40, 110)),
        7: ((240, -300, 170), (0, 20, 110)),
        8: ((260, -300, 260), (0, 40, 110)),
        9: ((380, -20, 120), (0, 20, 95)),
    },
    "bed": {
        1: ((300, -220, 330), (20, 80, 165)),
        2: ((-260, -300, 340), (-10, 60, 175)),
        3: ((-330, -220, 300), (-10, 70, 175)),
        4: ((220, -300, 380), (0, 40, 180)),
        5: ((200, -300, 360), (0, 70, 175)),
        6: ((260, -260, -120), (0, 0, 125)),
    },
}

def render(kind, step):
    os.makedirs(OUT, exist_ok=True)
    eye, ctr = VIEWS[kind][step]
    eye = tuple(c + ZOOM * (e - c) for e, c in zip(eye, ctr))
    out = os.path.join(OUT, f"{kind}_{step:02d}.png")
    cmd = ["openscad", "-o", out, "-D", f"step={step}", "-D", f"eye=[{','.join(map(str, eye))}]",
           "-D", f"ctr=[{','.join(map(str, ctr))}]", "--imgsize=2400,1800",
           "--camera=" + ",".join(str(v) for v in eye + ctr),
           "--projection=p", "--colorscheme=Tomorrow", os.path.join(HERE, f"{kind}_scenes.scad")]
    if not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
        cmd = ["xvfb-run", "-a"] + cmd
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not os.path.exists(out):
        print(r.stderr[-2000:]); raise SystemExit(f"{kind} {step} failed")
    warn = [l for l in r.stderr.splitlines() if "WARNING" in l or "ERROR" in l]
    if warn: print(kind, step, *warn[:5], sep="\n  ")
    crop(out, width=1200)
    print("wrote", os.path.relpath(out))

if __name__ == "__main__":
    kinds = [sys.argv[1]] if len(sys.argv) > 1 else list(VIEWS)
    for k in kinds:
        steps = [int(a) for a in sys.argv[2:]] or sorted(VIEWS[k])
        for s in steps:
            render(k, s)
