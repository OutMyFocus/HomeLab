#!/usr/bin/env python3
"""Build the smaller Bambu Studio projects for the mechanism, with the same settings as the
enclosure project (make_project.py):

  python3 make_small_projects.py

writes, next to this script:
  MTG_Sorter_Feeder_And_Bed_v2.3mf   everything for the v2 feeder and scan bed (kept as built)
  MTG_Sorter_Feeder_v3.3mf           feeder v3: wheels at the gate (stand, hopper, arm, notched bed
                                     plate), plus the unchanged parts for a fresh build
  MTG_Sorter_Chute_v3.3mf            chute v3 (tray, doors, cranks, links, hinge frame) and the
                                     new front bridge with its bearing cap

Run it again after re-exporting STLs (export_enclosure.sh). Needs numpy.
"""
import os
import make_project as mp

SOLID = mp.SOLID
STRUCTURAL = mp.STRUCTURAL
TALL = mp.TALL
mp.PER_PART.update({
    "feeder_stand_mid": TALL,
    "feeder_hopper": TALL,
    "feeder_arm": STRUCTURAL,
    "feeder_roller": SOLID,
    "feeder_gate": STRUCTURAL,
    "bed_chute_stop_gate": STRUCTURAL,
    "bed_chute_gate_bearing": SOLID,
    "bed_chute_chute3": STRUCTURAL,
    "bed_chute_hinge_frame3": STRUCTURAL,
    "bed_chute_door3": STRUCTURAL,
    "bed_chute_door3_left": STRUCTURAL,
    "bed_chute_door_crank3": SOLID,
    "bed_chute_door_crank3_left": SOLID,
    "bed_chute_servo_crank3": SOLID,
    "bed_chute_servo_crank3_left": SOLID,
    "bed_chute_door_link3": SOLID,
    "enc_bridge_cap": SOLID,
})

PROJECTS = {
    "MTG_Sorter_Feeder_And_Bed_v2.3mf": [
        ("1 Feeder stand (brim)", ["feeder_stand_mid"]),
        ("2 Feeder hopper (brim)", ["feeder_hopper"]),
        ("3 Feeder arm, roller, gate, weight", ["feeder_arm", "feeder_roller", "feeder_gate", "feeder_weight"]),
        ("4 Scan bed plate (WHITE)", ["bed_chute_bed_plate"]),
        ("5 Stop gate, gate bearing", ["bed_chute_stop_gate", "bed_chute_gate_bearing"]),
    ],
    "MTG_Sorter_Feeder_v3.3mf": [
        ("1 Feeder stand v3 (brim)", ["feeder_stand_mid"]),
        ("2 Feeder hopper v3 (brim)", ["feeder_hopper"]),
        ("3 Feeder arm v3", ["feeder_arm"]),
        ("4 Scan bed plate v3, notched (WHITE)", ["bed_chute_bed_plate"]),
        ("5 Unchanged: roller, gate, weight, stop gate, bearing (fresh build only)",
         ["feeder_roller", "feeder_gate", "feeder_weight", "bed_chute_stop_gate", "bed_chute_gate_bearing"]),
    ],
    "MTG_Sorter_Chute_v3.3mf": [
        ("1 Chute tray, hinge frame", ["bed_chute_chute3", "bed_chute_hinge_frame3"]),
        ("2 Front bridge, cap, doors, cranks, links", ["enc_bridge_front", "enc_bridge_cap",
                                                        "bed_chute_door3", "bed_chute_door3_left",
                                                        "bed_chute_door_crank3", "bed_chute_door_crank3_left",
                                                        "bed_chute_servo_crank3", "bed_chute_servo_crank3_left",
                                                        "bed_chute_door_link3", "bed_chute_door_link3"]),
    ],
}

if __name__ == "__main__":
    import sys
    wanted = sys.argv[1:]   # e.g. python3 make_small_projects.py MTG_Sorter_Feeder_v3.3mf; none = all
    for name, plates in PROJECTS.items():
        if wanted and name not in wanted:
            continue
        mp.PLATES = plates
        mp.OUT = os.path.join(mp.HERE, name)
        mp.main()
