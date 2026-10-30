// Card feeder test rig: the first piece of the sifter to build and test.
//
// A hopper holds a stack of cards face up. A rubber-ringed roller under the stack
// pushes the bottom card forward through a gap only one card thick (the gate).
// Getting exactly ONE card out every time is the hardest part of any card sorter,
// so this gets tested on its own before the rest is built around it.
//
// Parts (print each separately, no supports needed):
//   stand   - box the hopper sits on, with a cradle for the motor
//   hopper  - floor + walls that hold the stack
//   gate    - plate on the front wall; slide it up or down to set the gap
//   roller  - hub that goes on the motor shaft; two O-rings stretch over it
//
// Open in OpenSCAD, set `part`, press F6 then F7 to save an STL.

part = "assembly"; // "stand", "hopper", "gate", "roller" or "assembly" (preview only)

// --- Cards -------------------------------------------------------------------
card_w = 63;
card_l = 88;
hopper_gap = 2;     // room around the stack (sleeved cards: try 4)
hopper_h = 60;      // stack height: about 190 unsleeved cards

// --- Roller and motor ----------------------------------------------------------
// N20 gear motor (12 x 10 mm gearbox, 3 mm D-shaft) and two O-rings,
// 20 mm inside diameter x 3 mm thick (sold as "20x3 O-ring", nitrile).
oring_id = 20;
oring_cs = 3;
groove_root = oring_id + 0.5;           // slightly bigger than the O-ring, so it grips
hub_d = groove_root + 2.5;
roller_d = groove_root + 2 * oring_cs;  // across the O-rings: about 26.5
roller_w = 14;
roller_y = 20;      // roller centre, measured back from the hopper's front wall
roller_poke = 0.8;  // how far the roller sticks up through the floor
n20_w = 12.2;       // gearbox, with a little clearance
n20_h = 10.2;
n20_len = 26;       // gearbox + motor body
shaft_len = 9;

// --- Frame ---------------------------------------------------------------------
wall = 3;
floor_t = 3;
stand_h = 40;
exit_shelf = 30;    // flat area in front of the gate where cards come out
// Enclosure build: the stand's front reaches in under the back of the sloped scan bed.
// bed_cut = true cuts it away under the bed (2 mm clear). bed_low is the height of the bed
// plate's underside straight below the hopper's front wall, above the stand's bottom.
bed_cut = false;
bed_low = 89.1;     // enclosure: 167 + (150 - 54) * tan(20) - 111 - 2 (clearance), at y = 0

$fn = 64;

in_w = card_w + 2 * hopper_gap;          // inside of the hopper
in_l = card_l + 2 * hopper_gap;
out_w = in_w + 2 * wall;
floor_l = exit_shelf + wall + in_l + wall;
floor_y0 = -exit_shelf - wall;           // y = 0 is the inside of the front wall
floor_top = stand_h + floor_t;
roller_z = floor_top + roller_poke - roller_d / 2;  // roller axis height
gate_slot = 4;                           // opening under the front wall that the gate covers

module stand() {
    difference() {
        union() {
            // four walls, open top and bottom
            difference() {
                translate([-out_w / 2, floor_y0, 0]) cube([out_w, floor_l, stand_h]);
                translate([-out_w / 2 + wall, floor_y0 + wall, -1]) cube([out_w - 2 * wall, floor_l - 2 * wall, stand_h + 2]);
            }
            // motor cradle: the gearbox lies on top of this block
            translate([roller_w / 2 + 1, roller_y - 9, 0]) cube([out_w / 2 - wall - roller_w / 2 - 1, 18, roller_z - n20_h / 2]);
            // locating pegs for the hopper
            for (x = [-1, 1], y = [floor_y0 + 8, floor_y0 + floor_l - 8])
                translate([x * (out_w / 2 - wall / 2), y, stand_h]) cylinder(d = 2, h = 2.5);
        }
        // zip-tie slots through the cradle to strap the motor down
        for (x = [roller_w / 2 + 6, roller_w / 2 + n20_len - 4])
            translate([x, roller_y - 10, roller_z - n20_h / 2 - 6]) cube([3.5, 20, 2]);
        // enclosure: clear the underside of the scan bed (slopes 20 degrees down to the front)
        if (bed_cut) translate([-out_w, 0.5, bed_low]) rotate([20, 0, 0]) translate([0, -200, 0]) cube([2 * out_w, 200, 200]);
        // the back of the motor (and its wires) pokes out through the side wall
        translate([out_w / 2 - wall - 1, roller_y - n20_w / 2 - 0.5, roller_z - n20_h / 2 - 0.5]) cube([wall + 2, n20_w + 1, n20_h + 1]);
    }
}

module hopper() {
    difference() {
        union() {
            // floor
            translate([-out_w / 2, floor_y0, 0]) cube([out_w, floor_l, floor_t]);
            // side walls and back wall
            for (x = [-out_w / 2, in_w / 2]) translate([x, -wall, 0]) cube([wall, in_l + 2 * wall, floor_t + hopper_h]);
            translate([-out_w / 2, in_l, 0]) cube([out_w, wall, floor_t + hopper_h]);
            // front wall, starting above the gate slot
            translate([-out_w / 2, -wall, floor_t + gate_slot]) cube([out_w, wall, hopper_h - gate_slot]);
            // low guide rails along the exit shelf
            for (x = [-out_w / 2, in_w / 2]) translate([x, floor_y0, 0]) cube([wall, exit_shelf + 1, floor_t + 4]);
        }
        // hole for the roller to poke through
        translate([-roller_w / 2 - 2, roller_y - roller_d / 2 + 1, -1]) cube([roller_w + 4, roller_d - 2, floor_t + 2]);
        // holes for the stand's locating pegs
        for (x = [-1, 1], y = [floor_y0 + 8, floor_y0 + floor_l - 8])
            translate([x * (out_w / 2 - wall / 2), y, -1]) cylinder(d = 2.4, h = 3);
        // screw holes for the gate (M3 self-tapping)
        for (x = [-20, 20]) translate([x, 1, floor_t + 20]) rotate([90, 0, 0]) cylinder(d = 2.6, h = wall + 2);
        // thumb notch in the back wall to push the stack down
        translate([0, in_l - 1, floor_t + hopper_h]) rotate([-90, 0, 0]) cylinder(r = 15, h = wall + 2);
    }
}

// The gate hangs on the front of the hopper. Its slotted holes let it slide up and
// down: set the gap under it to about 1.5 card thicknesses (start with 0.45 mm by
// slipping one card underneath, tightening, then pulling the card out).
module gate() {
    gate_h = 30;
    difference() {
        translate([-in_w / 2, 0, 0]) cube([in_w, 2.5, gate_h]);
        for (x = [-20, 20]) hull() for (z = [gate_h - 18, gate_h - 9]) translate([x, -1, z]) rotate([-90, 0, 0]) cylinder(d = 3.3, h = 5);
        // bevel the bottom edge on the hopper side so cards don't snag
        translate([-in_w / 2 - 1, 2.5, 0]) rotate([45, 0, 0]) cube([in_w + 2, 2, 2]);
    }
}

module roller() {
    difference() {
        rotate([0, 90, 0]) cylinder(d = hub_d, h = roller_w, center = true);
        // O-ring grooves
        for (x = [-3.5, 3.5]) translate([x, 0, 0]) rotate([0, 90, 0]) difference() {
            cylinder(d = hub_d + 1, h = oring_cs + 0.2, center = true);
            cylinder(d = groove_root, h = oring_cs + 1, center = true);
        }
        // D-shaped hole for the motor shaft, from the motor side (+x)
        translate([roller_w / 2 - shaft_len, 0, 0]) rotate([0, 90, 0]) intersection() {
            cylinder(d = 3.15, h = shaft_len + 1);
            translate([-2, -1.65, 0]) cube([4, 3.3, shaft_len + 1]);  // flat side
        }
    }
}

module print_roller() {  // stood on its end for printing
    rotate([0, -90, 0]) roller();
}

if (part == "stand") stand();
else if (part == "hopper") hopper();
else if (part == "gate") rotate([90, 0, 0]) gate();
else if (part == "roller") print_roller();
else {
    color("dimgray") stand();
    color("white") translate([0, 0, stand_h]) hopper();
    color("orange") translate([0, -wall - 2.5, floor_top + 0.45]) gate();
    color("black") translate([0, roller_y, roller_z]) roller();
    color("gold") translate([roller_w / 2 + 0.5, roller_y - n20_w / 2, roller_z - n20_h / 2]) cube([n20_len, n20_w, n20_h]);
    // a stack of cards
    color("tan") translate([-card_w / 2, hopper_gap, floor_top]) cube([card_w, card_l, 25]);
}
