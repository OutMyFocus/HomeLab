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
module fence_out() difference() { translate([-60, 80, 100]) cube([120, 200, 13]); translate([-36.8, 116.7, 99]) cube([73.6, 128.6, 15]); }
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
if (what == "stand_fence") intersection() { F() stand4(); fence_out(); }
if (what == "stand_bracket") intersection() { F() stand4(); union() { tilt_bracket(); gate_bearing(); stop_gate(true); } }
if (what == "stand_hopper") intersection() { F() stand4(); F() translate([0, 0, 0.01]) hopper4(); }
if (what == "shoe_low_bed") intersection() { F() translate([0, 0, -1.6]) shoe4(); bed3(); }
if (what == "pads_wheel") intersection() { F() pads(); F() wheel_sweep(0.2); }
