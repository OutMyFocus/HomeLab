#!/usr/bin/env python3
"""Run the Mk2 clash checks in check.scad: each must come out empty.  python3 check.py [name ...]
A check whose name ends in _latch is the other way round: it pulls a servo back 2 mm and must
CLASH (the latch is what it runs into), so the servo can't back out of its pocket."""
import os, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "check.scad")).read()
CHECKS = re.findall(r'what == "([a-z0-9_]+)"', src)
def run(w):
    out = os.path.join(tempfile.gettempdir(), "mk2chk_%s.stl" % w)
    r = subprocess.run(["openscad", "-o", out, "-D", 'what="%s"' % w, os.path.join(HERE, "check.scad")], capture_output=True, text=True)
    txt = (r.stdout + r.stderr).lower()
    if "empty" in txt:
        return w, True, ""
    # parts that only rest on each other (shared faces) give a zero-volume result: that's fine
    sys.path.insert(0, os.path.join(HERE, "guide")); import bbox
    t = bbox.load(out); import numpy as np
    vol = abs(np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])).sum() / 6) if len(t) else 0
    v = t.reshape(-1, 3)
    return w, vol < 0.5, "%.1f mm3 between %s and %s" % (vol, v.min(0).round(1), v.max(0).round(1))
with ThreadPoolExecutor(8) as ex:
    res = list(ex.map(run, sys.argv[1:] or CHECKS))
bad = 0
for w, empty, err in res:
    want = not w.endswith("_latch")
    ok = empty == want
    print("%-14s %s" % (w, "clear" if empty else "CLASH"), ("" if empty else err) + ("" if ok else "   <-- FAIL"))
    bad += not ok
sys.exit(1 if bad else 0)
