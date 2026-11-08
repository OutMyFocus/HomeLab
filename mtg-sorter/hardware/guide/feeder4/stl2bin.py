#!/usr/bin/env python3
"""Turn OpenSCAD 2021's ASCII STLs into binary ones (make_project.py reads binary): stl2bin.py a.stl ..."""
import struct, sys, numpy as np
for p in sys.argv[1:]:
    d = open(p, "rb").read()
    if not d[:5] == b"solid":
        continue
    v = np.array([list(map(float, l.split()[1:])) for l in d.decode().splitlines() if l.strip().startswith("vertex")]).reshape(-1, 3, 3)
    n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]); n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    rec = np.zeros(len(v), dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))
    rec["n"] = n; rec["v"] = v.reshape(-1, 9)
    open(p, "wb").write(b"binary STL".ljust(80, b" ") + struct.pack("<I", len(v)) + rec.tobytes())
    print("binary", p, len(v))
