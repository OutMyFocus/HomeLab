// Clash checks for the feeder box v4 against the scan bed v3.1 and the bridge (check.py renders each
// `what`; an empty result means no clash).
include <../../bed_chute.scad>
use <../../feeder4.scad>
part = "none";
what = "wheel_bed";
module F() translate([0, 150, 111]) children();
module bed3() on_bed() bed_plate3();
grow = 0;
module motor() F() translate([22.6 - grow, 1.0 - 6.1 - grow, 82.7 - 5.1 - grow]) cube([25.8 + 2 * grow, 12.2 + 2 * grow, 10.2 + 2 * grow]);
// a card sliding out along the exit line, 0.3 thick (n = 3.6 .. 3.9 over the bed's base)
module card_path() on_bed() translate([-31.5, 0, 3.6 + 0.02]) cube([63, 120, 0.28]);
// the bridge's fence (2 mm wall, 2 mm tall, 73.6 x 128.6 inside) and the bridge plate under it
module fence_ring() translate([0, 181, 111 - 0.01]) linear_extrude(2) difference() { square([77.6, 132.6], center = true); square([73.6, 128.6], center = true); }
module bridge_plate() translate([-52, 90, 107]) cube([104, 175, 3.99]);
if (what == "wheel_bed") intersection() { F() wheel_sweep(0.3); bed3(); }
if (what == "wheel_stand") intersection() { F() wheel_sweep(0.3); F() stand4(); }
if (what == "wheel_hopper") intersection() { F() wheel_sweep(0.3); F() hopper4(); }
if (what == "wheel_shoe") intersection() { F() wheel_sweep(0.05); F() shoe4(); }
if (what == "roller_stand") intersection() { F() roller4(); F() stand4(); }
if (what == "stand_bed") intersection() { F() stand4(); union() { bed3(); bed_side(false); mirror([1, 0, 0]) bed_side(true); } }
if (what == "hopper_bed") intersection() { F() hopper4(); union() { bed3(); bed_side(false); mirror([1, 0, 0]) bed_side(true); } }
if (what == "shoe_bed") intersection() { F() shoe4(); bed3(); }
if (what == "shoe_hopper") intersection() { F() shoe4(); F() hopper4(); }
if (what == "motor_bed") intersection() { motor(); bed3(); }
if (what == "motor_stand") intersection() { motor(); F() stand4(); }
if (what == "card_bed") intersection() { card_path(); bed3(); }
if (what == "card_hopper") intersection() { card_path(); F() hopper4(); }
if (what == "card_shoe") intersection() { card_path(); F() shoe4(); }
if (what == "stand_fence") intersection() { F() stand4(); fence_ring(); }
if (what == "stand_bridge") intersection() { F() stand4(); bridge_plate(); }
// sanity: moved 1 mm forward the stand must hit the fence (it can't slide)
if (what == "stand_slid") intersection() { F() translate([0, -1, 0]) stand4(); fence_ring(); }
if (what == "stand_bracket") intersection() { F() stand4(); union() { tilt_bracket(); gate_bearing(); stop_gate(true); } }
if (what == "stand_hopper") intersection() { F() stand4(); F() translate([0, 0, 0.01]) hopper4(); }
if (what == "shoe_low_bed") intersection() { F() translate([0, 0, -1.6]) shoe4(); bed3(); }
if (what == "pads_wheel") intersection() { F() pads(); F() wheel_sweep(0.2); }
