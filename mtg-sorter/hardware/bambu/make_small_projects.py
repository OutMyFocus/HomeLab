#!/usr/bin/env python3
"""Build the smaller Bambu Studio projects for the mechanism, with the same settings as the
enclosure project (make_project.py):

  python3 make_small_projects.py

writes, next to this script:
  MTG_Sorter_Feeder_And_Bed_v2.3mf   everything for the new feeder and scan bed
  MTG_Sorter_Chute_v3.3mf            chute v3 (tray, doors, cranks, links, hinge frame) and the
                                     new front bridge with its bearing cap
  MTG_Sorter_Scan_Bed_v3.3mf         scan bed v3 plate (steeper, centring channel, ribs), the
                                     all-plastic hopper weight and the one-bar stop gate
  MTG_Sorter_DC_Jack_Holder.3mf      holder + bezel for the servo-power barrel jack (dc_jack_holder.scad)
  MTG_Sorter_Feeder_Box_v4.3mf       feeder box v4 (feeder4.scad): stand, hopper, separator shoe, roller,
                                     and the scan bed v3.1 plate with the wheel slots

  python3 make_small_projects.py MTG_Sorter_DC_Jack_Holder.3mf   builds just that one

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
    "dc_jack_holder": STRUCTURAL,
    "dc_jack_bezel": STRUCTURAL,
    # scan bed v3.1, slippery smooth: the card's face is flat on this print, so 0.2 mm layers are
    # fine; more top layers and ironing on every top surface (the nozzle passes again, a little flow)
    "bed_chute_bed_plate3": {"wall_loops": "3", "sparse_infill_density": "20%",
                             "top_shell_layers": "7", "top_surface_line_width": "0.4",
                             "ironing_type": "top", "ironing_flow": "15%", "ironing_spacing": "0.1", "ironing_speed": "20"},
    "feeder_weight_solid": SOLID,
    "bed_chute_stop_gate3": STRUCTURAL,
    "feeder4_stand4": TALL,
    "feeder4_hopper4": TALL,
    "feeder4_shoe4": SOLID,       # its weight is what presses the pads on the wheels
    "feeder4_roller4": SOLID,
})

PROJECTS = {
    "MTG_Sorter_Feeder_And_Bed_v2.3mf": [
        ("1 Feeder stand (brim)", ["feeder_stand_mid"]),
        ("2 Feeder hopper (brim)", ["feeder_hopper"]),
        ("3 Feeder arm, roller, gate, weight", ["feeder_arm", "feeder_roller", "feeder_gate", "feeder_weight"]),
        ("4 Scan bed plate (WHITE)", ["bed_chute_bed_plate"]),
        ("5 Stop gate, gate bearing", ["bed_chute_stop_gate", "bed_chute_gate_bearing"]),
    ],
    "MTG_Sorter_Chute_v3.3mf": [
        ("1 Chute tray, hinge frame", ["bed_chute_chute3", "bed_chute_hinge_frame3"]),
        ("2 Front bridge, cap, doors, cranks, links", ["enc_bridge_front", "enc_bridge_cap",
                                                        "bed_chute_door3", "bed_chute_door3_left",
                                                        "bed_chute_door_crank3", "bed_chute_door_crank3_left",
                                                        "bed_chute_servo_crank3", "bed_chute_servo_crank3_left",
                                                        "bed_chute_door_link3", "bed_chute_door_link3"]),
    ],
    "MTG_Sorter_Scan_Bed_v3.3mf": [
        ("1 Scan bed v3 plate (WHITE)", ["bed_chute_bed_plate3"]),
        ("2 Solid hopper weight (any colour, 100% infill)", ["feeder_weight_solid"]),
        ("3 Stop bar, replaces the four-tooth stop gate (black)", ["bed_chute_stop_gate3"]),
    ],
    "MTG_Sorter_Feeder_Box_v4.3mf": [
        ("1 Feeder stand v4 (black, brim)", ["feeder4_stand4"]),
        ("2 Feeder hopper v4 (black, brim)", ["feeder4_hopper4"]),
        ("3 Separator shoe and roller (100% infill)", ["feeder4_shoe4", "feeder4_roller4"]),
        ("4 Scan bed v3.1 plate with wheel slots (WHITE)", ["bed_chute_bed_plate3"]),
        ("5 Stop bar v3.2 (black), if not printed yet", ["bed_chute_stop_gate3"]),
    ],
    "MTG_Sorter_DC_Jack_Holder.3mf": [
        ("1 DC jack holder and bezel (black)", ["dc_jack_holder", "dc_jack_bezel"]),
    ],
}

def write_bed_preset():
    """presets/MTG_Scan_Bed_Slippery_Smooth.json: the bed plate's settings as a process preset,
    for Bambu Studio's File > Import > Import Configs (use it when slicing bed_plate3 on its own)."""
    import json
    name = "MTG Scan Bed - Slippery smooth @BBL A1"
    p = {"type": "process", "name": name, "inherits": mp.PROCESS_BASE, "from": "User",
         "instantiation": "true", "version": mp.VERSION, "print_settings_id": name, "is_custom_defined": "0"}
    p.update(mp.GLOBAL)
    p.update(mp.PER_PART["bed_chute_bed_plate3"])
    with open(os.path.join(mp.HERE, "presets", "MTG_Scan_Bed_Slippery_Smooth.json"), "w") as f:
        json.dump(p, f, indent=4)
    print("wrote presets/MTG_Scan_Bed_Slippery_Smooth.json")


if __name__ == "__main__":
    import sys
    for name, plates in PROJECTS.items():
        if sys.argv[1:] and name not in sys.argv[1:]:
            continue
        mp.PLATES = plates
        mp.OUT = os.path.join(mp.HERE, name)
        mp.main()
    write_bed_preset()
