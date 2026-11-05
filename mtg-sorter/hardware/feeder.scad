// Feeder v3: the hopper and card picker that stands on the enclosure's bridge, behind the scan bed.
//
// v3 (2026-11-05, from watching v2 feed on camera): the wheels move from 20 mm behind the gate
// to 8 mm. With them at 20 mm they touched the NEXT card as soon as the fed card's tail passed
// them, and drove it 20-35 mm out of the slot behind the first, where it lay on the landed card
// and pinned it on the bed. At 8 mm the next card only moves a few mm before the app stops the
// motor (and backs it off, feed_watch.py). The arm's hinge moves forward too, so the rubber
// band presses the wheels into the stack about twice as hard. The wheels now reach over the
// back edge of the scan bed, which gets two notches (bed_chute.scad: wheel_notch). Changed
// parts: stand, arm, hopper, bed plate. The roller, gate and weight are the v2 ones.
//
// How it picks ONE card:
//   - Two O-ring wheels, 30 mm apart, poke up through the hopper floor under the stack and push
//     the bottom card forward. Two wheels keep it straight; one narrow roller let it twist.
//   - The wheels and their motor ride on a hinged ARM. A rubber band pulls the arm's tail down,
//     so the wheels always press up into the stack, however the parts print. A hard stop (the arm
//     touching the underside of the floor) keeps them from poking more than 2.5 mm.
//   - At the front, the card goes out through a gap under the GATE, set to about one card thick
//     with a thumb screw. A strip of rubber in the gate's bottom edge holds the second card back.
//   - A WEIGHT plate sits on top of the stack (put coins or nuts in it), so the last few cards
//     still press down on the wheels. Real feeders struggle with the last cards for this reason.
//
// Parts (set `part`, F6, F7). No supports. The STLs in stl/ are already turned to print:
//   stand    box on the bridge, holds the arm (replaces feeder_stand_mid)
//   arm      carries the motor and the roller, hinged on two M3 screws
//   roller   two O-ring wheels on one shaft (100% infill)
//   hopper   floor and walls for the stack (replaces feeder_hopper)
//   gate     hangs on the hopper's front wall (replaces feeder_gate)
//   weight   sits on the stack
//   "assembly" shows it all together (preview only)
//
// Coordinates: x across, y = 0 at the inside of the hopper's front wall (+y towards the back),
// z = 0 at the bottom of the stand (the top of the bridge). enclosure.scad puts y = 0 at its
// feeder_front_y (150) and z = 0 at bridge_top (111).

part = "assembly";

// --- Cards (63 x 88 x 0.3 mm; sleeved about 66 x 91) ------------------------------------
card_w = 63;  card_l = 88;
hopper_gap = 2;          // room around an unsleeved card, each side
hopper_h = 60;           // stack height: about 180 cards (less the weight plate)

// --- Frame (same outside as the first feeder, so the bridge fence and tower still fit) ---
wall = 3;
floor_t = 3;
stand_h = 96;            // stand height: the hopper floor ends up 4 mm above the back of the bed
in_w = card_w + 2 * hopper_gap;      // 67
in_l = card_l + 2 * hopper_gap;      // 92
out_w = in_w + 2 * wall;             // 73
stand_y0 = -33;                      // front of the stand (it reaches in under the bed)
stand_y1 = in_l + wall;              // 95: back of the stand and hopper
floor_y0 = -8;                       // front edge of the hopper floor (under the gate)
floor_top = stand_h + floor_t;       // 99
gate_slot = 4;                       // opening under the front wall, covered by the gate
gate_gap = 0.4;                      // gate above the floor (set for real with the thumb screw)

// The scan bed below: top surface at z = bed_z0 + y * tan(20) here. The stand is cut 2 mm
// under it (bed plate 3 mm thick).
bed_z0 = 93.94;          // 170 + (150 - 54) * tan(20) - 111
bed_cut_z0 = bed_z0 - 3 / cos(20) - 2;

// --- Roller: two wheels with 3 mm O-rings (20x3 or 22x3, stretched over a 23 mm groove) ---
oring_cs = 3;
groove_root = 23;
wheel_d = groove_root + 2;           // 25: the flanks either side of the groove
roller_r = groove_root / 2 + oring_cs;   // 14.5 over the O-rings
core_d = 16;
wheel_x = 15;                        // wheels at x = +-15
wheel_w = 7;
roller_x0 = -20;  roller_x1 = 20.5;  // ends of the roller body (+x end goes on the motor shaft, 7 mm on)
stub_d = 5;                          // stub axle at the -x end, turns in the arm
shaft_len = 9;                       // N20 D-shaft, 3 mm
poke = 2.5;                          // how far the O-rings stand above the floor at the stop

roller_y = 8;                        // v3: wheels 8 mm behind the front wall (v2: 20). Any closer
                                     // and the wheel hits the gate's foot; any further back and
                                     // it drives the next card out behind the first.
roller_z = floor_top + poke - roller_r;  // 87: roller axis with the arm against its stop

// --- N20 gear motor (12 x 10 mm, about 26 mm long with the motor) ----------------------
n20_w = 12.4;  n20_h = 10.4;  n20_len = 26;
gear_face_x = 22.5;                  // the gearbox's front face (shaft side)

// --- Arm ---------------------------------------------------------------------------
pivot = [44, 76];                    // hinge (y, z): two M3 screws through the stand walls. v3: 44
                                     // (v2: 62), so the band's pull at the tail (y 91) reaches the
                                     // wheels at y 8 through a 47:36 lever instead of 29:42.
arm_z0 = 66;                         // underside of the arm's base plate
arm_t = 3;
stop_z = stand_h;                    // the arm's stop pads touch the floor's underside here
arm_half = in_w / 2 - 0.2;           // the arm just fits between the stand walls
tail_y = 91;                         // band tongue tip

$fn = 64;

module rbox(p, s) { translate(p) cube(s); }

// ============================ STAND ==========================================
module stand() {
    difference() {
        union() {
            difference() {
                rbox([-out_w / 2, stand_y0, 0], [out_w, stand_y1 - stand_y0, stand_h]);
                rbox([-out_w / 2 + wall, stand_y0 + wall, -1], [out_w - 2 * wall, stand_y1 - stand_y0 - 2 * wall, stand_h + 2]);
            }
            // bar along the bottom at the back: the rubber band hooks under it
            rbox([-in_w / 2, 85, 0], [in_w, 4, 6]);
            // locating pegs for the hopper
            for (x = [-1, 1], y = [6, 86]) translate([x * (out_w / 2 - wall / 2), y, stand_h]) cylinder(d = 2, h = 2.5);
        }
        // the notch under the band bar (bridges 10 mm when printing)
        rbox([-5, 84, -1], [10, 6, 4]);
        // under the scan bed: cut away 2 mm below the bed plate
        translate([-out_w, 0.5, bed_cut_z0 + 0.5 * tan(20)]) rotate([20, 0, 0]) translate([0, -200, 0]) cube([2 * out_w, 200, 200]);
        // the motor sticks out through the right wall; the slot is open at the top so the arm
        // drops in from above, and leaves 6 mm of travel below the stop
        rbox([out_w / 2 - wall - 1, roller_y - n20_w / 2 - 1.5, roller_z - n20_h / 2 - 6], [wall + 2, n20_w + 3, 40]);
        // hinge screws (M3) through both side walls
        translate([-out_w, pivot[0], pivot[1]]) rotate([0, 90, 0]) cylinder(d = 3.2, h = 2 * out_w);
    }
}

// ============================ ARM ============================================
// Built where it sits with the wheels at their stop. Prints the right way up (as exported):
// base plate on the bed.
module arm() {
    difference() {
        union() {
            // base plate under the roller, out to the hinge cheeks and the tail
            rbox([-24, roller_y - 12, arm_z0], [24 + 33, pivot[0] - 4 - (roller_y - 12), arm_t]);
            rbox([-arm_half, pivot[0] - 8, arm_z0], [2 * arm_half, 80 - (pivot[0] - 8), arm_t]);
            // tail tongue for the rubber band, with a bump so the band can't slip off
            rbox([-4, 78, arm_z0], [8, tail_y - 78, arm_t]);
            rbox([-4, tail_y - 2, arm_z0], [8, 2, arm_t + 2]);
            // hinge cheeks, against the stand walls
            for (x = [-arm_half, arm_half - 4]) hull() {
                rbox([x, pivot[0] - 8, arm_z0], [4, 16, arm_t]);
                translate([x, pivot[0], pivot[1]]) rotate([0, 90, 0]) cylinder(r = 5, h = 4);
            }
            // left bearing plate: the roller's stub axle drops into a slot open at the top
            rbox([-24, roller_y - 8, arm_z0], [3.5, 16, stop_z - arm_z0]);
            // motor block around the gearbox, from the base plate up to the stop
            rbox([gear_face_x - 1.5, roller_y - n20_w / 2 - 2.5, arm_z0], [arm_half - gear_face_x + 1.5, n20_w + 5, stop_z - arm_z0]);
        }
        // stub axle slot (open at the top)
        translate([-25, roller_y, roller_z]) rotate([0, 90, 0]) cylinder(d = stub_d + 0.6, h = 6);
        rbox([-25, roller_y - (stub_d + 0.6) / 2, roller_z], [6, stub_d + 0.6, 20]);
        // gearbox tunnel, open at the outer end: the motor slides in shaft first
        rbox([gear_face_x, roller_y - n20_w / 2, roller_z - n20_h / 2], [20, n20_w, n20_h]);
        // hole in the end wall for the gearbox boss and shaft
        translate([gear_face_x - 3, roller_y, roller_z]) rotate([0, 90, 0]) cylinder(d = 5, h = 4);
        // M2 screw from the back pinches the gearbox
        translate([28.5, roller_y + n20_w / 2 - 1, roller_z]) rotate([-90, 0, 0]) cylinder(d = 1.8, h = 6);
        // the wheels' floor slots reach over the inner end of the motor block, so keep it low there
        rbox([gear_face_x - 2, roller_y - 10, roller_z + n20_h / 2 + 1], [25 - gear_face_x + 2, 20, 20]);
        // hinge screw holes (M3 self-tapping)
        translate([-arm_half - 1, pivot[0], pivot[1]]) rotate([0, 90, 0]) cylinder(d = 2.6, h = 2 * arm_half + 2);
    }
}

// ============================ ROLLER =========================================
// Turned shape: profile of (x, radius). Prints standing on its +x end (the motor end).
module roller_body() {
    function wheel(c) = [[c - wheel_w / 2, core_d / 2], [c - wheel_w / 2, wheel_d / 2],
                         [c - 1.6, wheel_d / 2], [c - 1.6, groove_root / 2], [c + 1.6, groove_root / 2],
                         [c + 1.6, wheel_d / 2], [c + wheel_w / 2, wheel_d / 2],
                         [c + wheel_w / 2 + (wheel_d - core_d) / 2, core_d / 2]];   // 45° on the +x side
    rc = wheel_x + wheel_w / 2;      // where the right wheel's 45° side would end
    pts = concat([[roller_x0 - 4, 0], [roller_x0 - 4, stub_d / 2], [roller_x0, stub_d / 2], [roller_x0, core_d / 2]],
                 wheel(-wheel_x),
                 // the right wheel's 45° side is cut off by the roller's end (at 21.5)
                 [[wheel_x - wheel_w / 2, core_d / 2], [wheel_x - wheel_w / 2, wheel_d / 2],
                  [wheel_x - 1.6, wheel_d / 2], [wheel_x - 1.6, groove_root / 2], [wheel_x + 1.6, groove_root / 2],
                  [wheel_x + 1.6, wheel_d / 2], [rc, wheel_d / 2],
                  [roller_x1, wheel_d / 2 - (roller_x1 - rc)]],
                 [[roller_x1, 0]]);
    difference() {
        rotate([0, 90, 0]) rotate_extrude() polygon([for (p = pts) [p[1], p[0]]]);
        // D-shaped hole for the motor shaft, from the +x end
        translate([roller_x1 - shaft_len + 1, 0, 0]) rotate([0, 90, 0]) intersection() {
            cylinder(d = 3.15, h = shaft_len + 1, $fn = 32);
            translate([-2, -1.65, 0]) cube([4, 3.3, shaft_len + 1]);
        }
    }
}
module roller() { translate([0, roller_y, roller_z]) roller_body(); }

// ============================ HOPPER =========================================
module hopper() {
    z0 = stand_h;
    difference() {
        union() {
            rbox([-out_w / 2, floor_y0, z0], [out_w, stand_y1 - floor_y0, floor_t]);
            for (x = [-out_w / 2, in_w / 2]) rbox([x, -wall, z0], [wall, in_l + 2 * wall, floor_t + hopper_h]);
            rbox([-out_w / 2, in_l, z0], [out_w, wall, floor_t + hopper_h]);
            // front wall, above the gate slot
            rbox([-out_w / 2, -wall, z0 + floor_t + gate_slot], [out_w, wall, hopper_h - gate_slot]);
            // the thumb screw's anvil, out through the gate's window (45° underneath)
            translate([-3.5, -wall, z0]) rotate([90, 0, 90]) linear_extrude(7)
                polygon([[0, 11.5], [0, 24], [-7.5, 24], [-7.5, 19]]);
        }
        // slots the wheels poke up through (the core between them stays under the floor). They
        // stop 2 mm short of the floor's front edge, so the edge the card slides over is whole.
        for (x = [-wheel_x - 5, wheel_x - 5]) rbox([x, max(roller_y - 14, floor_y0 + 2), z0 - 1], [14, 28, floor_t + 2]);
        // round off the floor's front edge so the card bends down onto the bed
        translate([0, floor_y0, z0 + floor_t]) rotate([45, 0, 0]) cube([2 * out_w, 2.5, 2.5], center = true);
        // pegs from the stand
        for (x = [-1, 1], y = [6, 86]) translate([x * (out_w / 2 - wall / 2), y, z0 - 1]) cylinder(d = 2.4, h = 4);
        // gate lock screws (M3 self-tapping)
        for (x = [-22, 22]) translate([x, 1, z0 + 23]) rotate([90, 0, 0]) cylinder(d = 2.6, h = wall + 2);
        // thumb notch in the back wall, to lift the weight out
        translate([0, in_l - 1, z0 + floor_t + hopper_h]) rotate([-90, 0, 0]) cylinder(r = 15, h = wall + 2);
    }
}

// ============================ GATE ===========================================
// Hangs on the hopper's front wall. Its weight rests on the thumb screw (M3 x 12), whose tip
// sits on the anvil that pokes out through the window: screw in = gate up. Two M3 screws in
// the slots lock it. A 1.9 mm O-ring, cut open, lies in the groove under the bottom edge and
// stands 0.6 mm proud: that's the rubber pad that holds the second card back.
gate_h = 30;
module gate() {
    gz = stand_h + floor_t + gate_gap;   // bottom edge
    difference() {
        union() {
            rbox([-in_w / 2, -wall - 2.5, gz], [in_w, 2.5, gate_h]);
            rbox([-in_w / 2, -wall - 5, gz], [in_w, 5, 4]);                 // foot along the bottom
            rbox([-6, -wall - 10, gz + gate_h - 3], [12, 10, 3]);           // tab for the thumb screw
        }
        // window for the anvil
        rbox([-4.5, -20, stand_h + 10], [9, 30, 18]);
        // lock screw slots
        for (x = [-22, 22]) hull() for (z = [stand_h + 19, stand_h + 27]) translate([x, -wall - 6, z]) rotate([-90, 0, 0]) cylinder(d = 3.3, h = 7);
        // thumb screw hole (self-tapping)
        translate([0, -wall - 5.5, gz + gate_h - 4]) cylinder(d = 2.6, h = 5);
        // rubber pad groove under the foot
        rbox([-in_w / 2 - 1, -wall - 4.3, gz - 1], [in_w + 2, 2, 2.3]);
    }
}

// ============================ WEIGHT =========================================
// 64 x 89 plate with four pockets: two loonies, quarters or M8 nuts in each.
module weight() {
    difference() {
        union() {
            translate([0, 0, 0]) linear_extrude(7) offset(r = 3) offset(delta = -3) square([in_w - 3, in_l - 3], center = true);
            translate([-1.5, -8, 0]) cube([3, 16, 18]);   // handle
        }
        for (x = [-15.5, 15.5], y = [-22, 22]) translate([x, y, 2.5]) cylinder(d = 27.5, h = 10);
    }
}

// ============================ OUTPUT =========================================
if (part == "stand") stand();
else if (part == "arm") translate([0, 0, -arm_z0]) arm();
else if (part == "roller") translate([0, 0, roller_x1]) rotate([0, 90, 0]) roller_body();
else if (part == "hopper") translate([0, 0, -stand_h]) hopper();
else if (part == "gate") translate([0, 0, -wall]) rotate([-90, 0, 0]) translate([0, 0, -(stand_h + floor_t + gate_gap)]) gate();
else if (part == "weight") weight();
else if (part == "none") { }
else assembly();

module assembly() {
    color("#3a3f47") stand();
    color("#2b2b2b") arm();
    color("orange") roller();
    color("#3a3f47", 0.6) hopper();
    color("#5a6068") gate();
    color("#c9a46a") for (i = [0:14]) translate([-card_w / 2, 2, floor_top + 0.32 * i]) cube([card_w, card_l, 0.3]);
    color("#e2701f") translate([0, in_l / 2, floor_top + 15 * 0.32]) weight();
    // motor
    color("silver") translate([gear_face_x, roller_y - n20_w / 2 + 0.2, roller_z - n20_h / 2 + 0.2]) cube([n20_len, n20_w - 0.4, n20_h - 0.4]);
}
