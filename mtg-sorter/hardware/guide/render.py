#!/usr/bin/env python3
"""Render the picture-guide scenes in scenes.scad to img/assembly/step_NN.png.
Needs OpenSCAD (2021.01 or newer) and, on a headless machine, xvfb-run.
    python3 guide/render.py            # all steps
    python3 guide/render.py 3 7        # just these
"""
import os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "img", "assembly")

# step: (eye, centre). Each picture is rendered large, then cropped to what is in it.
ZOOM = 1.8   # how far the eye sits back from the views below
FRONT = ((520, -760, 560), (0, 90, 110))
VIEWS = {
    0: ((560, -820, 520), (0, 90, 130)),
    1: ((420, -620, -520), (0, 90, 0)),
    2: ((380, -360, 520), (0, 150, 0)),
    3: FRONT,
    4: ((520, 1000, 560), (0, 90, 110)),
    5: FRONT,
    6: ((260, -620, 160), (0, 0, 50)),
    7: FRONT,
    8: ((440, -560, 640), (0, 90, 80)),
    9: ((380, -520, -300), (0, 90, 100)),
    10: ((520, -620, 560), (0, 80, 160)),
    11: ((-640, -420, 380), (0, 80, 160)),
    12: ((560, -560, 520), (0, 80, 170)),
    13: ((420, -560, -160), (0, 0, 110)),
    14: ((560, 600, 520), (0, 40, 150)),
    15: ((560, -560, 520), (0, 100, 180)),
    16: ((620, -820, 560), (0, 90, 180)),
    17: FRONT,
    18: ((560, -760, 640), (0, 90, 200)),
    19: ((560, -820, 520), (0, 40, 130)),
    20: ((600, 760, 640), (0, 110, 120)),
}

def crop(path, margin=40, width=1400):
    from PIL import Image, ImageChops
    im = Image.open(path).convert("RGB")
    bg = Image.new("RGB", im.size, im.getpixel((0, 0)))
    box = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > 12 else 0).getbbox()
    if box:
        l, t, r, b = box
        im = im.crop((max(0, l - margin), max(0, t - margin), min(im.width, r + margin), min(im.height, b + margin)))
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(path, optimize=True)

def render(step):
    os.makedirs(OUT, exist_ok=True)
    eye, ctr = VIEWS[step]
    eye = tuple(c + ZOOM * (e - c) for e, c in zip(eye, ctr))
    out = os.path.join(OUT, f"step_{step:02d}.png")
    cmd = ["openscad", "-o", out, "-D", f"step={step}", "-D", f"eye=[{','.join(map(str, eye))}]", "-D", f"ctr=[{','.join(map(str, ctr))}]", "--imgsize=2400,1800",
           "--camera=" + ",".join(str(v) for v in eye + ctr),
           "--projection=p", "--colorscheme=Tomorrow", os.path.join(HERE, "scenes.scad")]
    if not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
        cmd = ["xvfb-run", "-a"] + cmd
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0:
        crop(out)
    warn = [l for l in r.stderr.splitlines() if "WARNING" in l or "ERROR" in l]
    print(f"step {step:2d}: {'ok' if r.returncode == 0 else 'FAILED'} {' | '.join(sorted(set(warn)))[:400]}")

if __name__ == "__main__":
    for s in ([int(a) for a in sys.argv[1:]] or sorted(VIEWS)):
        render(s)
