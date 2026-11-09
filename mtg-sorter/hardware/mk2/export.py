#!/usr/bin/env python3
"""Export every Mk2 printed part, turned the way it prints, to stl/mk2_<part>.stl (binary).

  python3 export.py            all parts
  python3 export.py etray bin  just those

Then build the Bambu Studio project: python3 ../bambu/make_mk2.py
"""
import os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
STL = os.path.join(HERE, "stl")
SRC = os.path.join(HERE, "export.scad")
BIN = os.path.join(HERE, "..", "guide", "feeder4", "stl2bin.py")

def parts():
    s = open(SRC).read()
    out = re.findall(r'part == "([a-z0-9_]+)"', s)
    for side in "rl":
        for iy in (0, 1):
            for iz in (0, 1, 2):
                out.append("wall_%s%d%d" % (side, iy, iz))
    out += ["base_" + n for n in ("fl", "fr", "bl", "br")]
    out += ["coupon_plate", "coupon_pieces"]         # from coupon.scad
    return sorted(set(out))

def run(p):
    out = os.path.join(STL, "mk2_%s.stl" % p)
    src, q = (os.path.join(HERE, "coupon.scad"), p[7:]) if p.startswith("coupon_") else (SRC, p)
    r = subprocess.run(["openscad", "-o", out, "-D", 'part="%s"' % q, src], capture_output=True, text=True)
    txt = r.stdout + r.stderr
    if r.returncode or "WARNING" in txt and "empty" in txt.lower() or not os.path.exists(out):
        return p, False, txt[-600:]
    subprocess.run([sys.executable, BIN, out], capture_output=True)
    return p, True, ""

if __name__ == "__main__":
    os.makedirs(STL, exist_ok=True)
    want = sys.argv[1:] or parts()
    bad = 0
    with ThreadPoolExecutor(os.cpu_count() or 4) as ex:
        for p, ok, err in ex.map(run, want):
            print("%-14s %s" % (p, "ok" if ok else "FAILED\n" + err), flush=True)
            bad += not ok
    sys.exit(1 if bad else 0)
