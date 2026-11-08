#!/usr/bin/env python3
"""Run the clash checks in check.scad: each must come out empty."""
import os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS = ["wheel_bed", "wheel_stand", "wheel_hopper", "wheel_shoe", "roller_stand", "stand_bed", "hopper_bed",
          "shoe_bed", "shoe_hopper", "motor_bed", "motor_stand", "card_bed", "card_hopper", "card_shoe",
          "stand_fence", "stand_bracket", "stand_hopper"]
def run(w):
    out = os.path.join(tempfile.gettempdir(), "chk_%s.stl" % w)
    r = subprocess.run(["openscad", "-o", out, "-D", 'what="%s"' % w, os.path.join(HERE, "check.scad")], capture_output=True, text=True)
    empty = "empty" in (r.stdout + r.stderr).lower()
    return w, empty, r.stderr[-300:] if not empty else ""
with ThreadPoolExecutor(8) as ex:
    res = list(ex.map(run, sys.argv[1:] or CHECKS))
bad = 0
for w, empty, err in res:
    print("%-14s %s" % (w, "clear" if empty else "CLASH"), "" if empty else err.strip().splitlines()[-1:])
    bad += not empty
sys.exit(1 if bad else 0)
