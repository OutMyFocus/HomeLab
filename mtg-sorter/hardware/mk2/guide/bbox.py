#!/usr/bin/env python3
"""bbox.py a.stl ...: bounding box and volume of each (ASCII or binary STL), to find where a clash is."""
import sys, struct, numpy as np
def load(p):
    d = open(p, "rb").read()
    if d[:5] == b"solid" and b"facet" in d[:300]:
        v = np.array([list(map(float, l.split()[1:])) for l in d.decode().splitlines() if l.strip().startswith("vertex")])
        return v.reshape(-1, 3, 3)
    n = struct.unpack("<I", d[80:84])[0]
    a = np.frombuffer(d, dtype=np.uint8, offset=84, count=n * 50).reshape(n, 50)
    return a[:, 12:48].copy().view("<f4").reshape(n, 3, 3).astype(float)
if __name__ == "__main__":
  for p in sys.argv[1:]:
    t = load(p)
    if len(t) == 0: print(p, "empty"); continue
    v = t.reshape(-1, 3)
    vol = np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])).sum() / 6
    print(p.split("/")[-1], "min", v.min(0).round(1), "max", v.max(0).round(1), "vol %.1f mm3" % vol)
