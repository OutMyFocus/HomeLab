#!/usr/bin/env python3
"""Build the Bambu Studio project for the Sorter Mk2: every printed part, on numbered plates in
the order to print them, with the settings applied (same base profile as make_project.py).

  python3 ../mk2/export.py     # first: writes mk2/stl/mk2_<part>.stl, turned the way each prints
  python3 make_mk2.py          # writes MTG_Sorter_Mk2.3mf next to this script

One filament (black). Plates marked WHITE are the parts the light has to come through or that
show inside the machine: swap to white PLA for those plates. Open it with File > Open Project and
answer No to "load as a single object".
"""
import os
import make_project as mp

mp.STL = os.path.join(mp.HERE, "..", "mk2", "stl")
mp.OUT = os.path.join(mp.HERE, "MTG_Sorter_Mk2.3mf")
mp.MARGIN = 2.0      # the A1 prints its full 256 x 256 (no prime tower with one colour); the wall tiles need 250
mp.GAP = 6.0
mp.BRIM_GAP = 14.0

SOLID, STRUCTURAL, TALL = mp.SOLID, mp.STRUCTURAL, mp.TALL
TREE = {"enable_support": "1", "support_type": "tree(auto)", "support_style": "default",
        "support_threshold_angle": "35", "support_top_z_distance": "0.2"}
TALL_TREE = dict(TALL, **TREE)
STRUCT_TREE = dict(STRUCTURAL, **TREE)
SMOOTH = {"wall_loops": "3", "sparse_infill_density": "20%", "top_shell_layers": "7",
          "top_surface_line_width": "0.4", "ironing_type": "top", "ironing_flow": "15%",
          "ironing_spacing": "0.1", "ironing_speed": "20"}   # the scan bed: the card slides on it

N = lambda p: "mk2_" + p
mp.PER_PART.update({N(k): v for k, v in {
    **{"wall_%s%d%d" % (s, y, z): STRUCTURAL for s in "rl" for y in (0, 1) for z in (0, 1, 2)},
    **{"base_" + n: STRUCTURAL for n in ("fl", "fr", "bl", "br")},
    "bin": TALL, "drawer": TALL,
    "lv1_frame": TALL_TREE, "lv2_frame": TALL_TREE,
    "carriage1": STRUCT_TREE, "carriage2": STRUCT_TREE, "lever": SOLID,
    "door": TALL, "col_front": TALL, "liner_back": STRUCTURAL,
    "scan_carrier": TALL_TREE, "scan_bed": SMOOTH, "stop_bar": STRUCTURAL,
    "cam_arch": TALL_TREE, "cam_hood": SOLID, "lightbar": dict(SOLID, brim_type="outer_only", brim_width="5"),
    "fd_stand": STRUCT_TREE, "fd_hopper": TALL, "fd_shoe": dict(SOLID, brim_type="outer_only", brim_width="5"),
    "fd_roller": SOLID, "fd_motor_lid": STRUCTURAL,
    "etray": STRUCT_TREE, "pca_comb": STRUCTURAL,
    "key": SOLID, "trunk_lid": {}, "branch_lid": {},
}.items()})

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
    ("19 Pushers, levers, liners, stop bar", P("carriage1", "carriage2", "lever*2", "col_front", "liner_back", "stop_bar")),
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

if __name__ == "__main__":
    mp.PRESETS = {}     # the enclosure's presets stay as they are
    mp.main()
