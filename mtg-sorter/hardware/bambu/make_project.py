#!/usr/bin/env python3
"""Build the Bambu Studio files for the enclosure print.

  python3 make_project.py          (the whole enclosure)
  python3 make_project.py power    (just the two parts with the power jack / button holes)

writes, next to this script:
  MTG_Sorter_Enclosure.3mf   one project, every plate from PRINTING.md laid out on its own
                             plate, the settings from PRINTING.md applied (File > Open Project)
  MTG_Sorter_Power_Parts.3mf with "power": back_l and deck_fr only, for reprinting them
  presets/*.json             the same settings as process presets, for Bambu Studio's
                             "Import Configs" dialog

Run it again after re-exporting STLs (export_enclosure.sh). Needs numpy.
The A1 / PLA defaults come from a1_system_profiles.json (Bambu Studio's own system profiles,
flattened), so the project opens as "0.20mm Standard @BBL A1" with a handful of changes.
"""
import json, os, sys, zipfile
from math import sqrt
from xml.sax.saxutils import escape, quoteattr

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
STL = os.path.join(HERE, "..", "stl")
OUT = os.path.join(HERE, "MTG_Sorter_Enclosure.3mf")
APP = "BambuStudio-02.04.00.70"   # the 3MF generator tag Bambu Studio looks for
VERSION = "02.04.00.70"

BED = 256.0
MARGIN = 6.0          # keep parts this far from the bed edge
GAP = 8.0             # between parts
BRIM_GAP = 16.0       # between parts that get a 5 mm brim
STRIDE = BED * 1.2    # Bambu Studio lays plates out on a grid with this pitch

# ---- settings (PRINTING.md, "Settings") -------------------------------------------------
PROCESS_BASE = "0.20mm Standard @BBL A1"
PRINTER = "Bambu Lab A1 0.4 nozzle"
FILAMENT = "Bambu PLA Basic @BBL A1"

GLOBAL = {   # every part: the flat-panel settings
    "wall_loops": "3",
    "sparse_infill_density": "15%",
    "sparse_infill_pattern": "gyroid",
    "enable_support": "0",
    "brim_type": "no_brim",
    "brim_width": "5",
    "seam_position": "aligned",
    "precise_outer_wall": "1",
    "elefant_foot_compensation": "0.15",
    "ironing_type": "no ironing",
}
STRUCTURAL = {"wall_loops": "4", "sparse_infill_density": "25%"}
TALL = dict(STRUCTURAL, brim_type="outer_only", brim_width="5")
SOLID = {"sparse_infill_density": "100%", "sparse_infill_pattern": "zig-zag"}

PER_PART = {
    "enc_post_front": TALL, "enc_post_back": TALL, "enc_leg": TALL,
    "enc_post_sleeve": TALL, "enc_tower": TALL,
    "enc_divider": STRUCTURAL, "enc_bridge_front": STRUCTURAL, "enc_bridge_back": STRUCTURAL,
    "enc_light_bar": SOLID, "enc_splice": SOLID,
}

PRESETS = {   # presets/<name>.json for the Import Configs dialog
    "MTG Enclosure - 1 Flat panels @BBL A1": {},
    "MTG Enclosure - 2 Structural @BBL A1": STRUCTURAL,
    "MTG Enclosure - 3 Tall parts with brim @BBL A1": TALL,
    "MTG Enclosure - 4 Solid @BBL A1": SOLID,
}

# ---- plates (PRINTING.md, "Plates, in order"; the Card Catalog drawers are not in here) -
PLATES = [
    ("Fit check A - floor_fl, post_front, splices", ["enc_floor_fl", "enc_post_front", "enc_splice", "enc_splice"]),
    ("Fit check C - dividers", ["enc_divider", "enc_divider"]),
    ("bridge_front", ["enc_bridge_front"]),
    ("bridge_back", ["enc_bridge_back"]),
    ("bed walls", ["bed_chute_bed_side_left_enclosure", "bed_chute_bed_side_right_enclosure"]),
    ("feeder_stand_mid", ["feeder_stand_mid"]),
    ("floor_fr, 8 splices", ["enc_floor_fr"] + ["enc_splice"] * 8),
    ("floor_bl, floor_br", ["enc_floor_bl", "enc_floor_br"]),
    ("post_front, post_back, leg", ["enc_post_front", "enc_post_back", "enc_leg"]),
    ("post_back, leg, tower", ["enc_post_back", "enc_leg", "enc_tower"]),
    ("side 1 of 4", ["enc_side"]),
    ("side 2 of 4", ["enc_side"]),
    ("side 3 of 4", ["enc_side"]),
    ("side 4 of 4", ["enc_side"]),
    ("back_l", ["enc_back_l"]),
    ("back_r", ["enc_back_r"]),
    ("fascia l, m, r", ["enc_fascia_l", "enc_fascia_m", "enc_fascia_r"]),
    ("light_bar (white)", ["enc_light_bar"]),
    ("tower_lid, post_sleeve, head_cover (black)", ["enc_tower_lid", "enc_post_sleeve", "enc_head_cover"]),
    ("deck_fl", ["enc_deck_fl"]),
    ("deck_fr", ["enc_deck_fr"]),
    ("deck_bl", ["enc_deck_bl"]),
    ("deck_br", ["enc_deck_br"]),
]

# the two parts that changed for the power jack and button (POWER.md), to reprint on their own
POWER_PLATES = [p for p in PLATES if p[0] in ("back_l", "deck_fr")]


def read_stl(name):
    b = open(os.path.join(STL, name + ".stl"), "rb").read()
    n = int.from_bytes(b[80:84], "little")
    if 84 + 50 * n != len(b):
        sys.exit(name + ".stl is not a binary STL")
    a = np.frombuffer(b, dtype=np.uint8, offset=84, count=n * 50).reshape(n, 50)
    return a[:, 12:48].copy().view("<f4").reshape(n, 3, 3).astype(np.float64)


def pack(sizes, gaps):
    """First-fit on a 1 mm grid, lowest row first. Returns [(x0, y0, rotated)] or None."""
    placed = []   # (x0, y0, x1, y1, gap)
    out = []
    lo, hi = MARGIN, BED - MARGIN
    for (w, d), g in zip(sizes, gaps):
        spot = None
        for rot in (False, True):
            ww, dd = (d, w) if rot else (w, d)
            if ww > hi - lo or dd > hi - lo:
                continue
            for y in np.arange(lo, hi - dd + 1e-9, 1.0):
                for x in np.arange(lo, hi - ww + 1e-9, 1.0):
                    if all(x + ww + max(g, pg) <= px0 or px1 + max(g, pg) <= x or
                           y + dd + max(g, pg) <= py0 or py1 + max(g, pg) <= y
                           for px0, py0, px1, py1, pg in placed):
                        spot = (x, y, rot, ww, dd)
                        break
                if spot:
                    break
            if spot:
                break
        if not spot:
            return None
        x, y, rot, ww, dd = spot
        placed.append((x, y, x + ww, y + dd, g))
        out.append((x, y, rot))
    return out


def mesh_xml(oid, tris):
    v, idx = np.unique(np.round(tris.reshape(-1, 3), 5), axis=0, return_inverse=True)
    f = idx.reshape(-1, 3)
    f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])]
    s = ['  <object id="%d" type="model">\n   <mesh>\n    <vertices>\n' % oid]
    s += ['     <vertex x="%.5f" y="%.5f" z="%.5f" />\n' % tuple(p) for p in v]
    s.append('    </vertices>\n    <triangles>\n')
    s += ['     <triangle v1="%d" v2="%d" v3="%d" />\n' % tuple(t) for t in f]
    s.append('    </triangles>\n   </mesh>\n  </object>\n')
    return "".join(s), len(f)


def project_settings(profiles):
    cfg = {}
    cfg.update(profiles["machine"])
    cfg.update(profiles["filament"])
    cfg.update(profiles["process"])
    cfg.update(GLOBAL)
    cfg.update({
        "name": "project_settings",
        "from": "project",
        "version": VERSION,
        "print_settings_id": PROCESS_BASE,
        "printer_settings_id": PRINTER,
        "filament_settings_id": [FILAMENT],
        "filament_ids": [profiles["filament_id"]],
        "filament_colour": ["#161616"],
        "curr_bed_type": "Textured PEI Plate",
        "different_settings_to_system": [";".join(sorted(GLOBAL)), "", ""],
        "print_compatible_printers": profiles["process"].get("compatible_printers", [PRINTER]),
    })
    cfg.pop("compatible_printers", None)
    cfg.pop("compatible_printers_condition", None)
    return cfg


def write_presets():
    d = os.path.join(HERE, "presets")
    os.makedirs(d, exist_ok=True)
    for name, extra in PRESETS.items():
        p = {"type": "process", "name": name, "inherits": PROCESS_BASE, "from": "User",
             "instantiation": "true", "version": VERSION, "print_settings_id": name,
             "is_custom_defined": "0"}
        p.update(GLOBAL)
        p.update(extra)
        fn = name.split(" @")[0].replace("MTG Enclosure - ", "MTG_Enclosure_").replace(" ", "_") + ".json"
        with open(os.path.join(d, fn), "w") as f:
            json.dump(p, f, indent=4)
        print("wrote presets/" + fn)


def main(PLATES=PLATES, OUT=OUT):
    profiles = json.load(open(os.path.join(HERE, "a1_system_profiles.json")))
    r = round(sqrt(len(PLATES)))            # Bambu Studio's compute_colum_count()
    cols = r + 1 if sqrt(len(PLATES)) > r else r
    meshes = {}
    resources, build, objects_cfg, plates_cfg, assemble = [], [], [], [], []
    oid = 0
    ident = 100
    for pi, (pname, parts) in enumerate(PLATES):
        row, col = divmod(pi, cols)
        ox, oy = col * STRIDE, -row * STRIDE
        tris = [meshes.setdefault(p, read_stl(p)) for p in parts]
        sizes = []
        for t in tris:
            mn, mx = t.reshape(-1, 3).min(0), t.reshape(-1, 3).max(0)
            sizes.append((mx[0] - mn[0], mx[1] - mn[1]))
        gaps = [BRIM_GAP if PER_PART.get(p, {}).get("brim_type") == "outer_only" else GAP for p in parts]
        spots = pack(sizes, gaps)
        if spots is None:
            sys.exit("plate %r does not fit the bed" % pname)
        inst = []
        for k, (part, t, (x, y, rot)) in enumerate(zip(parts, tris, spots)):
            t = t.copy()
            if rot:
                t = t[:, :, [1, 0, 2]] * np.array([-1.0, 1.0, 1.0])   # turn 90 degrees about Z
            mn, mx = t.reshape(-1, 3).min(0), t.reshape(-1, 3).max(0)
            c = (mn + mx) / 2
            t -= c
            mesh_id, comp_id = oid + 1, oid + 2
            oid += 2
            xml, nf = mesh_xml(mesh_id, t)
            resources.append(xml)
            resources.append('  <object id="%d" type="model">\n   <components>\n    <component objectid="%d" transform="1 0 0 0 1 0 0 0 1 0 0 0" />\n   </components>\n  </object>\n' % (comp_id, mesh_id))
            w, d, h = mx - mn
            tx, ty, tz = ox + x + w / 2, oy + y + d / 2, h / 2
            build.append('  <item objectid="%d" transform="1 0 0 0 1 0 0 0 1 %.4f %.4f %.4f" printable="1" />\n' % (comp_id, tx, ty, tz))
            label = part if parts.count(part) == 1 else "%s (%d)" % (part, parts[:k + 1].count(part))
            meta = ['    <metadata key="name" value=%s/>\n' % quoteattr(label), '    <metadata key="extruder" value="1"/>\n']
            meta += ['    <metadata key="%s" value=%s/>\n' % (k, quoteattr(v)) for k, v in PER_PART.get(part, {}).items()]
            objects_cfg.append(
                '  <object id="%d">\n%s    <part id="%d" subtype="normal_part">\n'
                '      <metadata key="name" value=%s/>\n'
                '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
                '      <mesh_stat face_count="%d" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>\n'
                '    </part>\n  </object>\n' % (comp_id, "".join(meta), mesh_id, quoteattr(part + ".stl"), nf))
            assemble.append('   <assemble_item object_id="%d" instance_id="0" transform="1 0 0 0 1 0 0 0 1 %.4f %.4f %.4f" offset="0 0 0" />\n' % (comp_id, tx, ty, tz))
            ident += 1
            inst.append('    <model_instance>\n      <metadata key="object_id" value="%d"/>\n      <metadata key="instance_id" value="0"/>\n      <metadata key="identify_id" value="%d"/>\n    </model_instance>\n' % (comp_id, ident))
        plates_cfg.append('  <plate>\n    <metadata key="plater_id" value="%d"/>\n    <metadata key="plater_name" value=%s/>\n    <metadata key="locked" value="false"/>\n%s  </plate>\n' % (pi + 1, quoteattr(pname), "".join(inst)))
        print("plate %2d  %-52s %s" % (pi + 1, pname, " ".join("%s%s" % (p, "*" if r else "") for p, (_, _, r) in zip(parts, spots))))

    model = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
             'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">\n'
             ' <metadata name="Application">%s</metadata>\n'
             ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
             ' <metadata name="Title">MTG Sorter enclosure</metadata>\n'
             ' <metadata name="Designer">OutMyFocus/HomeLab mtg-sorter</metadata>\n'
             ' <resources>\n%s </resources>\n <build>\n%s </build>\n</model>\n') % (APP, "".join(resources), "".join(build))
    model_cfg = ('<?xml version="1.0" encoding="UTF-8"?>\n<config>\n%s%s  <assemble>\n%s  </assemble>\n</config>\n'
                 % ("".join(objects_cfg), "".join(plates_cfg), "".join(assemble)))
    content_types = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
                     ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
                     ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
                     ' <Default Extension="png" ContentType="image/png"/>\n'
                     ' <Default Extension="gcode" ContentType="text/x.gcode"/>\n</Types>\n')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
            '</Relationships>\n')
    seq = json.dumps({"plate_%d" % (i + 1): {"sequence": []} for i in range(len(PLATES))})
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)
        z.writestr("Metadata/model_settings.config", model_cfg)
        z.writestr("Metadata/project_settings.config", json.dumps(project_settings(profiles), indent=4, sort_keys=True))
        z.writestr("Metadata/filament_sequence.json", seq)
    print("wrote", os.path.relpath(OUT, HERE), "%d plates, %d objects" % (len(PLATES), oid // 2))


if __name__ == "__main__":
    if sys.argv[1:] == ["power"]:
        main(POWER_PLATES, os.path.join(HERE, "MTG_Sorter_Power_Parts.3mf"))
    else:
        main()
        write_presets()
