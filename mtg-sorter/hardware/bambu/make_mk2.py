#!/usr/bin/env python3
"""Build the Bambu Studio project for the Sorter Mk2: every printed part, on numbered plates in
the order to print them, with the settings applied (same base profile as make_project.py).

  python3 ../mk2/export.py     # first: writes mk2/stl/mk2_<part>.stl, turned the way each prints
  python3 make_mk2.py          # writes MTG_Sorter_Mk2.3mf next to this script

One filament (black). Plates marked WHITE are the parts the light has to come through or that
show inside the machine: swap to white PLA for those plates. Open it with File > Open Project and
answer No to "load as a single object".
"""
import json, os, re, sys, zipfile
import make_project as mp

mp.STL = os.path.join(mp.HERE, "..", "mk2", "stl")
mp.OUT = os.path.join(mp.HERE, "MTG_Sorter_Mk2.3mf")
mp.MARGIN = 2.0      # the A1 prints its full 256 x 256 (no prime tower with one colour); the wall tiles need 250
mp.GAP = 6.0
mp.BRIM_GAP = 14.0

# Mk2 prints sturdier than the enclosure did: one more wall and denser infill everywhere.
mp.GLOBAL = dict(mp.GLOBAL, wall_loops="4", sparse_infill_density="20%")
SOLID = mp.SOLID
STRUCTURAL = {"wall_loops": "5", "sparse_infill_density": "30%"}
BRIM = {"brim_type": "outer_only", "brim_width": "5"}
TALL = dict(STRUCTURAL, **BRIM)
SOLID_BRIM = dict(SOLID, **BRIM)
TREE = {"enable_support": "1", "support_type": "tree(auto)", "support_style": "default",
        "support_threshold_angle": "35", "support_top_z_distance": "0.2"}
TALL_TREE = dict(TALL, **TREE)
STRUCT_TREE = dict(STRUCTURAL, **TREE)
SMOOTH = {"wall_loops": "4", "sparse_infill_density": "25%", "top_shell_layers": "7",
          "top_surface_line_width": "0.4", "ironing_type": "top", "ironing_flow": "15%",
          "ironing_spacing": "0.1", "ironing_speed": "20"}   # the scan bed: the card slides on it

# Pack each plate as before, then move the whole layout to the middle of the bed, so the brims and
# tree supports round the big parts have room and stay inside the printable area.
_pack = mp.pack
def pack_centred(sizes, gaps):
    spots = _pack(sizes, gaps)
    if spots is None:
        return None
    boxes = [(x, y, x + (d if r else w), y + (w if r else d)) for (x, y, r), (w, d) in zip(spots, sizes)]
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    dx, dy = (mp.BED - (x1 - x0)) / 2 - x0, (mp.BED - (y1 - y0)) / 2 - y0
    out = [(x + dx, y + dy, r) for x, y, r in spots]
    for (x, y, r), (w, d), g in zip(out, sizes, gaps):     # a part with a brim keeps the brim and a bit more on the bed
        need = 7.0 if g == mp.BRIM_GAP else 2.0      # 5 mm brim + 2
        ww, dd = (d, w) if r else (w, d)
        if min(x, y, mp.BED - x - ww, mp.BED - y - dd) < need - 1e-6:
            sys.exit("a part with a brim sits too near the bed's edge (%.1f mm)" % min(x, y, mp.BED - x - ww, mp.BED - y - dd))
    return out
mp.pack = pack_centred

N = lambda p: "mk2_" + p
mp.PER_PART.update({N(k): v for k, v in {
    **{"wall_%s%d%d" % (s, y, z): STRUCTURAL for s in "rl" for y in (0, 1) for z in (0, 1, 2)},
    **{"base_" + n: STRUCTURAL for n in ("fl", "fr", "bl", "br")},
    "bin": TALL, "drawer": TALL,
    "lv1_frame": TALL_TREE, "lv2_frame": TALL_TREE,
    "carriage1": STRUCT_TREE, "carriage2": STRUCT_TREE, "lever": SOLID,
    "door": TALL, "col_front": TALL, "liner_back": STRUCTURAL, "ir_holder": STRUCTURAL,
    "scan_carrier": TALL_TREE, "scan_bed": SMOOTH, "stop_bar": STRUCTURAL,
    "cam_arch": TALL_TREE, "cam_hood": SOLID, "lightbar": SOLID_BRIM,
    "fd_stand": STRUCT_TREE, "fd_hopper": TALL, "fd_shoe": SOLID_BRIM,
    "fd_roller": SOLID, "fd_motor_lid": STRUCTURAL,
    "etray": STRUCT_TREE, "pca_comb": STRUCTURAL,
    "key": SOLID, "trunk_lid": {}, "branch_lid": {},
    "front_cover": {}, "lid_front": {}, "lid_back": {}, "back_low": {}, "back_high": {},
    "coupon_plate": {}, "coupon_pieces": {},
}.items()})

# The print config: the same settings as process presets for Bambu Studio's Import Configs dialog
# (presets/mk2/*.json), for slicing a part on its own. The 3MF already carries them per part.
PRESETS = [
    ("1 Panels and covers", {}),
    ("2 Frame", STRUCTURAL),
    ("3 Frame, brim", TALL),
    ("4 Frame, tree supports", STRUCT_TREE),
    ("5 Frame, brim, tree supports", TALL_TREE),
    ("6 Solid", SOLID),
    ("7 Solid, brim", SOLID_BRIM),
    ("8 Scan bed, ironed", SMOOTH),
]
WHITE = ("bin", "door", "drawer", "scan_bed", "lightbar")

def P(*names):
    out = []
    for n in names:
        k, _, q = n.partition("*")
        out += [N(k)] * int(q or 1)
    return out

mp.PLATES = [
    ("01 Fit coupon - print first, set fit.scad", P("coupon_plate", "coupon_pieces")),
    ("02 Base front-left, front-right", P("base_fl", "base_fr")),
    ("03 Base back-left, back-right", P("base_bl", "base_br")),
    ("04 Right wall, front bottom + 10 keys", P("wall_r00", "key*10")),
    ("05 Right wall, back bottom + 10 keys", P("wall_r10", "key*10")),
    ("06 Right wall, front middle + 2 trunk lids", P("wall_r01", "trunk_lid*2")),
    ("07 Right wall, back middle + 2 trunk lids", P("wall_r11", "trunk_lid*2")),
    ("08 Right wall, front top", P("wall_r02")),
    ("09 Right wall, back top", P("wall_r12")),
    ("10 Left wall, front bottom + 8 keys", P("wall_l00", "key*8")),
    ("11 Left wall, back bottom + 2 feed lids", P("wall_l10", "branch_lid*2")),
    ("12 Left wall, front middle + 2 trunk lids", P("wall_l01", "trunk_lid*2")),
    ("13 Left wall, back middle", P("wall_l11")),
    ("14 Left wall, front top", P("wall_l02")),
    ("15 Left wall, back top", P("wall_l12")),
    ("16 Bins x4 (WHITE, brim)", P("bin*4")),
    ("17 Level 2 frame (tree supports)", P("lv2_frame")),
    ("18 Level 1 frame (tree supports)", P("lv1_frame")),
    ("19 Pushers, levers, liners, stop bar, sensor holders", P("carriage1", "carriage2", "lever*2", "col_front", "liner_back", "stop_bar", "ir_holder*4")),
    ("20 Trapdoors x2, drawer (WHITE)", P("door*2", "drawer")),
    ("21 Scan carrier (tree supports)", P("scan_carrier")),
    ("22 Scan bed, light bars (WHITE)", P("scan_bed", "lightbar*2")),
    ("23 Camera arch and hood (tree supports)", P("cam_arch", "cam_hood")),
    ("24 Feeder stand (tree supports), motor lid", P("fd_stand", "fd_motor_lid")),
    ("25 Feeder magazine, shoe, roller", P("fd_hopper", "fd_shoe", "fd_roller")),
    ("26 Electronics tray (tree supports), comb", P("etray", "pca_comb")),
    ("27 Front cover", P("front_cover")),
    ("28 Lid, front half", P("lid_front")),
    ("29 Lid, back half", P("lid_back")),
    ("30 Back panel, lower", P("back_low")),
    ("31 Back panel, upper", P("back_high")),
]

def preset_of(part):
    return next(n for n, v in PRESETS if v == mp.PER_PART[N(part)])


def write_config():
    """presets/mk2/: one process preset per group of settings, a README that says which preset and
    colour each part takes, and the same files zipped for download."""
    d = os.path.join(mp.HERE, "presets", "mk2")
    os.makedirs(d, exist_ok=True)
    files = []
    for name, extra in PRESETS:
        full = "MTG Mk2 - %s @BBL A1" % name
        p = {"type": "process", "name": full, "inherits": mp.PROCESS_BASE, "from": "User",
             "instantiation": "true", "version": mp.VERSION, "print_settings_id": full, "is_custom_defined": "0"}
        p.update(mp.GLOBAL)
        p.update(extra)
        fn = "MTG_Mk2_" + re.sub(r"[^A-Za-z0-9]+", "_", name) + ".json"
        with open(os.path.join(d, fn), "w") as f:
            json.dump(p, f, indent=4)
        files.append(fn)
    show = {"wall_loops": "walls", "sparse_infill_density": "infill", "brim_type": "brim", "enable_support": "supports",
            "ironing_type": "ironing", "top_shell_layers": "top layers"}
    def say(v):
        c = dict(mp.GLOBAL, **v)
        out = ["%s walls" % c["wall_loops"], "%s %s infill" % (c["sparse_infill_density"], c["sparse_infill_pattern"])]
        if c["brim_type"] != "no_brim": out.append("%s mm outer brim" % c["brim_width"])
        if c["enable_support"] == "1": out.append("tree supports (auto, %s degrees)" % c["support_threshold_angle"])
        if c["ironing_type"] != "no ironing": out.append("%s top layers, top surface ironed" % c["top_shell_layers"])
        return ", ".join(out)
    L = ["# Sorter Mk2 print config", "",
         "Process presets for Bambu Studio, for the Bambu Lab A1 with the 0.4 mm nozzle. Written by `make_mk2.py`, so they always match the settings inside `MTG_Sorter_Mk2.3mf`.", "",
         "The 3MF already has these settings on every part. You only need the presets to slice a part on its own, or to check a plate against them.", "",
         "## Import", "",
         "1. In Bambu Studio: **File → Import → Import Configs...**",
         "2. Pick all eight `.json` files in this folder and press Open.",
         "3. They show up in the **Process** list under User presets, named `MTG Mk2 - ...`.", "",
         "## Printer, plate and filament", "",
         "| Setting | Value |", "|---|---|",
         "| Printer | %s |" % mp.PRINTER,
         "| Plate | Textured PEI |",
         "| Filament | %s, black; white for the parts marked below |" % mp.FILAMENT,
         "| Layer height | 0.20 mm (every preset inherits `%s`) |" % mp.PROCESS_BASE,
         "| On every preset | seam aligned, precise outer wall on, elephant foot compensation %s mm |" % mp.GLOBAL["elefant_foot_compensation"], "",
         "## The presets", "", "| Preset | Settings | Parts |", "|---|---|---|"]
    parts = sorted({q for _, ps in mp.PLATES for q in ps})
    for name, extra in PRESETS:
        mine = [q[4:] for q in parts if mp.PER_PART.get(q, {}) == extra]
        L.append("| `MTG Mk2 - %s` | %s | %s |" % (name, say(extra), ", ".join(mine) or "none"))
    L += ["", "## Plate by plate", "", "| Plate | Colour | Presets on it |", "|---|---|---|"]
    for pname, ps in mp.PLATES:
        used = sorted({next(n for n, v in PRESETS if v == mp.PER_PART.get(q, {})) for q in ps})
        white = all(q[4:] in WHITE for q in ps)
        L.append("| %s | %s | %s |" % (pname, "white" if white else "black", "; ".join(used)))
    L += ["", "Supports are only on where the table says so. Every other part prints without them.", ""]
    with open(os.path.join(d, "README.md"), "w") as f:
        f.write("\n".join(L))
    z = os.path.join(mp.HERE, "MTG_Sorter_Mk2_Print_Config.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in files + ["README.md"]:
            zi = zipfile.ZipInfo(fn, (2026, 11, 9, 0, 0, 0)); zi.compress_type = zipfile.ZIP_DEFLATED; zi.external_attr = 0o644 << 16
            zf.writestr(zi, open(os.path.join(d, fn), "rb").read())
    print("wrote presets/mk2/ (%d presets, README.md) and %s" % (len(files), os.path.basename(z)))


if __name__ == "__main__":
    mp.PRESETS = {}     # the enclosure's presets stay as they are
    if "--config" not in sys.argv:
        mp.main()
    write_config()
