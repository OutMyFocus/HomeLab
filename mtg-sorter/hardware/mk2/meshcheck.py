#!/usr/bin/env python3
"""Check printed parts before they go into the 3MF: python3 meshcheck.py [stl ...]  (default: stl/mk2_*.stl)

For every STL it reports
  - shells: separate closed surfaces. A printed part must be ONE solid shell. A second shell with
    positive volume is a loose piece (it would fall off the plate); one with negative volume is a
    closed hollow inside the part (harmless, but usually a modelling slip).
  - open or shared edges: every edge must belong to exactly two triangles (watertight).
  - size: must fit the A1's 256 x 256 x 256.
  - how much of the first layer touches the plate, and how much surface overhangs past 45 degrees
    more than 0.3 mm above the plate (that area needs supports or is a bridge).
Exit code 1 if any part has a loose piece, isn't watertight or doesn't fit.
"""
import glob, os, struct, sys
import numpy as np

BED = (256.0, 256.0, 256.0)
SETS = ("mk2_coupon_pieces",)   # several separate pieces on purpose: each must stand on the plate

def load(fn):
    b = open(fn, "rb").read()
    if b[:5] == b"solid" and b"facet" in b[:400]:
        v = [l.split()[1:4] for l in b.decode("ascii", "replace").splitlines() if l.lstrip().startswith("vertex")]
        return np.array(v, dtype=np.float64).reshape(-1, 3, 3)
    n = struct.unpack("<I", b[80:84])[0]
    a = np.frombuffer(b, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), count=n, offset=84)
    return a["v"].astype(np.float64)

def check(fn):
    t = load(fn)
    q = np.round(t.reshape(-1, 3), 3)
    uniq, idx = np.unique(q, axis=0, return_inverse=True)
    f = idx.reshape(-1, 3)
    # watertight: every undirected edge used exactly twice
    e = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    _, cnt = np.unique(e, axis=0, return_counts=True)
    bad_edges = int((cnt != 2).sum())
    # shells: union-find over vertices
    par = np.arange(len(uniq))
    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]; x = par[x]
        return x
    for a, b_, c in f:
        ra, rb, rc = find(a), find(b_), find(c)
        par[rb] = ra; par[find(rc)] = ra
    root = np.array([find(x) for x in f[:, 0]])
    vol6 = np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2]))
    shells = []
    for r in np.unique(root):
        m = root == r
        p = t[m].reshape(-1, 3)
        shells.append((vol6[m].sum() / 6.0, p.min(0), p.max(0)))
    shells.sort(key=lambda s: -abs(s[0]))
    lo, hi = t.reshape(-1, 3).min(0), t.reshape(-1, 3).max(0)
    size = hi - lo
    nrm = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    area = np.linalg.norm(nrm, axis=1) / 2
    nz = np.divide(nrm[:, 2], 2 * area, out=np.zeros(len(area)), where=area > 0)
    zmin = t[:, :, 2].min(1) - lo[2]
    on_plate = area[(nz < -0.99) & (zmin < 0.05)].sum()
    over = area[(nz < -0.7071) & (zmin > 0.3)].sum()
    return dict(shells=shells, bad_edges=bad_edges, size=size, on_plate=on_plate, over=over, vol=vol6.sum() / 6)

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    files = sys.argv[1:] or sorted(glob.glob(os.path.join(here, "stl", "mk2_*.stl")))
    fail = 0
    for fn in files:
        r = check(fn)
        loose = [s for s in r["shells"][1:] if s[0] > 0.01]
        if os.path.basename(fn)[:-4] in SETS:
            lo = min(sh[1][2] for sh in r["shells"])
            loose = [sh for sh in loose if sh[1][2] > lo + 0.05]      # a piece that doesn't reach the plate
        voids = [s for s in r["shells"][1:] if s[0] <= 0.01]
        fits = all(r["size"][i] <= BED[i] + 1e-6 for i in range(3)) or (r["size"][1] <= BED[0] and r["size"][0] <= BED[1] and r["size"][2] <= BED[2])
        ok = not loose and not r["bad_edges"] and fits
        fail += not ok
        print("%-4s %-26s %6.1f x %6.1f x %6.1f  %8.0f mm3  plate %6.0f mm2  overhang %6.0f mm2%s%s%s%s" % (
            "ok" if ok else "FAIL", os.path.basename(fn)[:-4], *r["size"], r["vol"], r["on_plate"], r["over"],
            "" if fits else "  TOO BIG", "  %d open/shared edges" % r["bad_edges"] if r["bad_edges"] else "",
            "  %d LOOSE" % len(loose) if loose else "", "  %d hollow" % len(voids) if voids else ""))
        for v, a, b in loose + voids:
            print("       %s %9.1f mm3 at [%s] .. [%s]" % ("loose " if v > 0.01 else "hollow", v, " ".join("%.1f" % x for x in a), " ".join("%.1f" % x for x in b)))
    sys.exit(1 if fail else 0)
