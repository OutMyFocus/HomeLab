#!/usr/bin/env python3
"""Build the smaller Bambu Studio projects for the mechanism, with the same settings as the
enclosure project (make_project.py):

  python3 make_small_projects.py

writes, next to this script:
  MTG_Sorter_Feeder_And_Bed_v2.3mf   everything for the new feeder, scan bed and door carriers
  MTG_Sorter_Chute.3mf               chute, trapdoors, door carriers (one plate)
  MTG_Sorter_Trapdoor_Parts.3mf      trapdoors, door carriers, hinge pins (one plate)

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
    "bed_chute_door_carrier": STRUCTURAL,
    "bed_chute_door_carrier_left": STRUCTURAL,
})

PROJECTS = {
    "MTG_Sorter_Feeder_And_Bed_v2.3mf": [
        ("1 Feeder stand (brim)", ["feeder_stand_mid"]),
        ("2 Feeder hopper (brim)", ["feeder_hopper"]),
        ("3 Feeder arm, roller, gate, weight", ["feeder_arm", "feeder_roller", "feeder_gate", "feeder_weight"]),
        ("4 Scan bed plate (WHITE)", ["bed_chute_bed_plate"]),
        ("5 Stop gate, bearing, door carriers", ["bed_chute_stop_gate", "bed_chute_gate_bearing",
                                                  "bed_chute_door_carrier", "bed_chute_door_carrier_left"]),
    ],
    "MTG_Sorter_Chute.3mf": [
        ("chute, trapdoors, door carriers", ["bed_chute_chute", "bed_chute_trapdoor", "bed_chute_trapdoor_left",
                                             "bed_chute_door_carrier", "bed_chute_door_carrier_left"]),
    ],
    "MTG_Sorter_Trapdoor_Parts.3mf": [
        ("trapdoors, door carriers, hinge pins", ["bed_chute_trapdoor", "bed_chute_trapdoor_left",
                                                  "bed_chute_door_carrier", "bed_chute_door_carrier_left"]
         + ["bed_chute_hinge_pin"] * 4),
    ],
}

if __name__ == "__main__":
    for name, plates in PROJECTS.items():
        mp.PLATES = plates
        mp.OUT = os.path.join(mp.HERE, name)
        mp.main()
