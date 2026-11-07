// Scan bed + chute: the middle and bottom of the sifter.
//
// Card path:
//   1. Card drops from the feeder onto the BED, which slopes 20 degrees down to the front.
//      It slides until two small PINS near the front edge stop it, under the camera.
//   2. Photo. A servo under the bed swings the pins down and the card slides off.
//   3. It lands in the CHUTE, a level tray above the three bins.
//        bin 2 (middle): two trapdoors in the tray floor open, card drops straight down
//        bin 1 / bin 3:  a servo tilts the tray 25 degrees and the card slides off that end
//
// Coordinates: x = left/right, y = front(-) to back(+), z = up. The table is z = 0.
//
// Printable parts (set `part`, F6, F7). All fit a 256 mm bed, no supports:
//   bed_plate        white, the surface the camera looks at
//   bed_side_left    side wall with the LED groove and the pin servo
//   bed_side_right   side wall with the LED groove and the camera tower socket
//   stop_gate        v2: four stop teeth on a bar across the bed, turned by the pin servo
//   stop_gate3       v3: the same with one flat stop bar instead of the teeth (goes with bed_plate3)
//   gate_bearing     v2: clips on the tilt bracket and holds the stop gate's right end
//   pin_rocker       the older two-pin version, replaced by stop_gate
//   tower_post       camera tower post
//   camera_head      arm + camera plate
//   tilt_bracket     holds the tilt servo, between the two bed side walls
//   chute            the tray
//   trapdoor         x2 (print one, then one mirrored: part = "trapdoor_left")
//   door_carrier     x2 (servo mount + back hinge on one bar) ("door_carrier_left" for the other).
//                    v2: the servo body points in towards the middle, so it stays above the bridge
//                    when the tray tilts (the first one hung out past the door and hit bridge_front)
//   trapdoor_mount, hinge_lug: the older separate versions, replaced by door_carrier
//   frame_side       x2 (identical)
//   front_bar        holds the front of the tray's pivot
//   bin              x3
//   "assembly" shows everything together (preview only)

part = "assembly";

// Preview positions for the moving parts
show_tilt = 0;          // chute tilt in degrees: 0, 25 or -25
show_doors_open = false;
show_pins_down = false;
show_frame = true;      // the open frame, front bar and bins (enclosure.scad turns this off)

// Where the bed side walls start. 0 = they stand on the table (open-frame build).
// enclosure.scad sets this to the top of its bridge plate; the walls then get two screw
// holes in their bottom edge, and the bridge screws up into them from below.
wall_z0 = 0;

// --- Cards ---------------------------------------------------------------------
card_w = 63;
card_l = 88;

// --- Bed -------------------------------------------------------------------------
bed_angle = 20;
bed_len = 100;          // along the slope
bed_t = 3;
bed_y = 54;             // front edge of the bed
bed_z = 170;            // height of the bed surface at its front edge
side_in = 56;           // inner faces of the side walls (x = +-56)
side_t = 6;
wall_h = 32;            // side walls rise this far above the bed
led_w = 10.5;
led_n = 20;             // LED strip centre, above the bed surface
card_s = 47;            // card centre, measured up the slope from the front edge
cam_height = 120;       // camera lens above the card
tower_x = 80;           // tower post, beside the bed
post_s = 20;
socket_d = 18;
boss_s = 32;
fit = 0.3;

// Stop pins
pin_x = 20;             // pins at x = +-20
pin_axis = [75, 165];   // pin servo shaft (y, z), on the left wall
pin_drop = 28;          // degrees the rocker turns to pull the pins down (no more than 31: the bar hits the chute axle)
pin_above = 7;          // how far the pin tops reach above the bed's front edge (was 4: the card side
                        // only stood 2.4 mm proud, and fast cards jumped over it)

// --- Chute -------------------------------------------------------------------------
pivot_z = 145;          // tilt axis height (along y, at x = 0) = top of the tray floor
tilt = 25;
ch_half = 60;           // tray reaches x = +-60
ch_in = 45.5;           // inside of the tray, y = +-45.5 (card is 88 long)
rail_t = 2.5;
floor_t = 2.5;
front_rail_h = 30;      // tall: the falling card hits it
back_rail_h = 6;
door_half = 36;         // trapdoor opening x = +-36
hinge_z = 136;          // trapdoor hinge axes (x = +-36, along y)
axle_d = 8;
front_bar_y = -75;      // inside face of the front bar

// --- Bins and frame -------------------------------------------------------------------
bin_w = 74;
bin_l = 100;
bin_h = 92;             // about 250 cards
bin_pitch = 76;
frame_x = 118;          // inside faces of the frame sides
frame_t = 6;
frame_h = 152;

// --- Servo (SG90 / MG90S, all four are the same size) --------------------------------
sv_len = 22.7;          // body length
sv_w = 12.2;            // body width
sv_shaft_off = 5.9;     // shaft distance from one end of the body
sv_top = 6.6;           // body above the mounting tabs (the part that pokes through)
sv_tab_len = 32.2;
sv_screw = 27.5;        // distance between the two tab screw holes

$fn = 48;

tan_a = tan(bed_angle);
bed_back_y = bed_y + bed_len * cos(bed_angle);
bed_back_z = bed_z + bed_len * sin(bed_angle);
ch_out = ch_in + rail_t;

// Bed coordinates: x across, s up the slope from the front edge, n square to the bed.
module on_bed() { translate([0, bed_y, bed_z]) rotate([bed_angle, 0, 0]) children(); }

// Profile in the (y, z) plane, given as 2D points, extruded along x from x0 to x0 + t.
module yz_plate(x0, t) { translate([x0, 0, 0]) rotate([90, 0, 90]) linear_extrude(t) children(); }

// Rectangle for an SG90 seen from its top, with the shaft at the origin; length along u.
module servo_hole(depth, flip = false) {
    u0 = flip ? -(sv_len - sv_shaft_off) : -sv_shaft_off;
    translate([u0 - 0.3, -sv_w / 2 - 0.3, -1]) cube([sv_len + 0.6, sv_w + 0.6, depth + 2]);
}
module servo_screws(depth, flip = false) {
    c = (flip ? -1 : 1) * (sv_len / 2 - sv_shaft_off);
    for (d = [-1, 1]) translate([c + d * sv_screw / 2, 0, -1]) cylinder(d = 1.8, h = depth + 2);
}

// ============================ BED ============================================

// v2: guide rails 2.5 mm tall, 68 mm apart (a sleeved card is 66), opening out into a funnel
// at the top where the card lands; four slots at the front for the stop gate's teeth.
rail_in = 34;           // inside faces of the rails, x = +-34
rail_h = 2.5;
funnel_s = 72;          // the rails start opening out here ...
funnel_in = 42;         // ... to x = +-42 at the top edge
module bed_plate() {
    difference() {
        union() {
            translate([-side_in - 2 + 0.3, 0, -bed_t]) cube([2 * side_in + 4 - 0.6, bed_len, bed_t]);
            for (m = [0, 1]) mirror([m, 0, 0]) {
                translate([rail_in, 8, 0]) cube([1.5, funnel_s - 8, rail_h]);
                hull() {
                    translate([rail_in, funnel_s, 0]) cube([1.5, 0.01, rail_h]);
                    translate([funnel_in, bed_len - 0.01, 0]) cube([1.5, 0.01, rail_h]);
                }
            }
        }
        // slots the stop teeth come up through (open at the front edge)
        for (x = tooth_x) translate([x - 2.5, -1, -bed_t - 1]) cube([5, 6, bed_t + 2]);
    }
}

// v3.1 bed plate (2026-11-07): drops into the same wall grooves. Nic asked for a bed that sets every
// card in the middle, square, over the trapdoors, and never stops it.
//   - Flat-printed card surface. v3 tilted the surface 4° against the plate (24° bed), so every print
//     layer left a fine step across the slide direction, and cards stopped on it (live test). The
//     card's surface is now parallel to the plate's underside, so it prints dead flat: 20°, as the
//     walls. It stands 2 mm higher than the old plate's face, so the card drops 5.4 mm off the hopper
//     floor instead of 8, and everything in front of the floor's edge only goes down (v3's crest sat
//     in front of the edge, with a hollow under it, and cards stuck there).
//   - A 65 mm channel (an unsleeved card is 63: 1 mm each side) with 4 mm walls from the stop to the
//     card's middle, then a funnel out to 76 mm at the top, 6 mm tall. The walls' top inside edge
//     is chamfered, so a corner that lands on one slides back in.
//   - Four lengthwise lands, 6.5 mm wide and 0.8 mm tall, carry the card. Each takes a strip of
//     1/4" (6.35 mm) PTFE tape: PLA is too grippy for a card to start sliding at 20° by itself.
//     They ramp in at the top so a card's edge can't catch on their ends.
//   - Four pockets for camera marker stickers beside the walls (positions below).
//   - One opening, chamfered at the top, for stop_gate3: one flat stop bar across the card.
// Built in bed coordinates like bed_plate (x across, y up the slope from the front edge, z square
// to the side walls' 20° plane).
bp3_extra = 0;                                  // the card's surface is parallel to the plate (prints flat)
bp3_lift = 2;                                   // ... and this much higher than the old plate's face
bp3_crest = 95;                                 // the raised face ends here, under the hopper floor's front edge (y 142.6)
bp3_rise = bp3_lift;                            // then a 45° bevel down (it clears the floor's underside by 2.4 mm)
bp3_half = (card_w + 2) / 2;                    // channel half width: 32.5
bp3_pocket = 55;                                // the channel is straight up to here ...
bp3_funnel_s = 88;                              // ... and opens out to bp3_top_half by here
bp3_top_half = 38;                              // (the hopper is 67 inside; its floor is 73 wide)
bp3_wall_t = 2;
bp3_wall_lo = 4;  bp3_wall_hi = 6;              // wall height over the surface: channel / funnel top
bp3_rib_x = [-24.5, -9, 9, 24.5];               // the PTFE tape lands
bp3_rib_h = 0.8;  bp3_rib_w = 7.5;  bp3_rib_top = 6.5;
bp3_wedge_half = bp3_top_half + bp3_wall_t + 0.5;
// Camera markers: four 5 mm square pockets, 0.4 mm deep, for printed ArUco stickers (OpenCV
// DICT_4X4_50, ids 0-3), so the app can straighten the picture. Centres, measured on the surface
// from the bed's front edge (u) and across (x):
//   id 0 (-37.75, 10)   id 1 (37.75, 10)   id 2 (37.75, 50)   id 3 (-37.75, 50)
// x is seen from the camera with the bed's front edge (the stop) at the bottom, right = +x (the
// camera tower side). A 75.5 x 40 mm rectangle, 0.8 mm under the card's face (the lands).
bp3_mk_x = 37.75;  bp3_mk_u = [10, 50];  bp3_mk_w = 5;  bp3_mk_d = 0.4;

function bp3_n(s) = s <= bp3_crest ? bp3_lift + s * tan(bp3_extra) : max(0, bp3_rise - (s - bp3_crest));
function bp3_wx(s) = s <= bp3_pocket ? bp3_half
                   : s >= bp3_funnel_s ? bp3_top_half
                   : bp3_half + (bp3_top_half - bp3_half) * (s - bp3_pocket) / (bp3_funnel_s - bp3_pocket);
function bp3_wh(s) = s <= bp3_pocket ? bp3_wall_lo
                   : s >= bp3_funnel_s ? bp3_wall_hi
                   : bp3_wall_lo + (bp3_wall_hi - bp3_wall_lo) * (s - bp3_pocket) / (bp3_funnel_s - bp3_pocket);

// one cross-section of the right-hand wall at s (inner face vertical, 1 mm chamfer on top inside)
module bp3_wall_slab(s) {
    x = bp3_wx(s);  top = bp3_n(s) + bp3_wh(s);
    translate([0, s, 0]) rotate([90, 0, 0]) linear_extrude(0.01, center = true)
        polygon([[x, 0], [x, top - 1], [x + 1, top], [x + bp3_wall_t, top], [x + bp3_wall_t, 0]]);
}
module bp3_rib_slab(x, s, h) {
    n = bp3_n(s);
    translate([0, s, 0]) rotate([90, 0, 0]) linear_extrude(0.01, center = true)
        polygon([[x - bp3_rib_w / 2, 0], [x - bp3_rib_top / 2, n + h], [x + bp3_rib_top / 2, n + h], [x + bp3_rib_w / 2, 0]]);
}
module bed_plate3() {
    wall_s = [0, bp3_pocket, bp3_funnel_s, bp3_crest, bp3_crest + bp3_rise, bed_len - 0.5];
    rib_s = [[0, bp3_crest - 8, bp3_rib_h, bp3_rib_h], [bp3_crest - 8, bp3_crest, bp3_rib_h, 0.01]];
    difference() {
        union() {
            translate([-side_in - 2 + 0.3, 0, -bed_t]) cube([2 * side_in + 4 - 0.6, bed_len, bed_t]);
            // the wedge: 0 at the front edge, bp3_rise at the crest, then a 45° bevel down
            yz_plate(-bp3_wedge_half, 2 * bp3_wedge_half)
                polygon([[0, -0.01], [0, bp3_lift], [bp3_crest, bp3_rise], [bp3_crest + bp3_rise, 0], [bp3_crest + bp3_rise, -0.01]]);
            for (m = [0, 1]) mirror([m, 0, 0]) {
                for (i = [0 : len(wall_s) - 2]) hull() { bp3_wall_slab(wall_s[i]); bp3_wall_slab(wall_s[i + 1]); }
                for (x = [for (r = bp3_rib_x) if (r > 0) r], r = rib_s) hull() { bp3_rib_slab(x, r[0], r[2]); bp3_rib_slab(x, r[1], r[3]); }
            }
        }
        // camera marker pockets (for 5 mm printed ArUco stickers), in the wedge's own surface so they
        // lie in the card's plane, beside the channel walls
        for (x = [-bp3_mk_x, bp3_mk_x], u = bp3_mk_u) rotate([bp3_extra, 0, 0])
            translate([x - bp3_mk_w / 2 - 0.2, u - bp3_mk_w / 2 - 0.2, bp3_lift - bp3_mk_d]) cube([bp3_mk_w + 0.4, bp3_mk_w + 0.4, 2]);
        // one opening for all four teeth (Nic: "one smooth area"), open at the front edge, its back
        // and side edges chamfered 1 mm at the top so nothing can catch on them
        bp3_gap = blade_half + 0.7;   // +-26.5: room for the v3 stop bar (or the old four teeth)
        translate([-bp3_gap, -1, -bed_t - 1]) cube([2 * bp3_gap, 6, bed_t + 2 + 2]);
        hull() {
            translate([-bp3_gap, -1, -0.6]) cube([2 * bp3_gap, 6, 0.01]);
            translate([-bp3_gap - 1.1, -1, bp3_n(6) + 0.5]) cube([2 * bp3_gap + 2.2, 7.1, 0.01]);
        }
    }
}

// ============================ STOP GATE (v2) ==================================
// Four teeth across the front of the bed, 8 mm tall and square to it, so a fast card can't jump
// them or twist past. They stand on a bar that spans the bed: the left end screws to the pin
// servo's horn (same place as the old rocker), the right end turns on a pin in gate_bearing.
// The card leans on the teeth; they turn down and forward out of its way. Built in bed
// coordinates (x, s up the slope, n square to the bed), with the teeth up.
tooth_x = [-24, -8, 8, 24];
tooth_w = 3.6;
tooth_top = 8;          // teeth stand this far above the bed
blade_half = 25.8;      // v3 stop: 10 mm tall (bed_plate3's face is 2 mm higher), one flat bar as wide as the four teeth were (x = +-25.8; the card is
                        // +-31.5). Any wider and its ends hit the tray when it tilts with the stop down
gate_drop = 40;         // degrees the servo turns to drop the teeth. Checked in CAD: nothing touches
                        // from 6° past up (the bar meets the bed: the up stop) to 44° down (the bar
                        // meets the chute's back axle), with the tray level or tilted 22° either way
gb_s0 = -1;  gb_s1 = 9;  // the bar, front to back
gb_n0 = -9;  gb_n1 = -5; // ... and its depth under the bed (2 mm gap: the up stop, about 6° past up)
gate_axis_s = (pin_axis[0] - bed_y) * cos(bed_angle) + (pin_axis[1] - bed_z) * sin(bed_angle);
gate_axis_n = -(pin_axis[0] - bed_y) * sin(bed_angle) + (pin_axis[1] - bed_z) * cos(bed_angle);
gate_left = -side_in + sv_top - 1;   // outer face of the horn plate (as the old rocker)
gate_right = 49;                     // outer face of the right plate
module stop_gate_bed(blade = false) {
    hub_r = 5.5;
    difference() {
        union() {
            // the bar
            translate([gate_left, gb_s0, gb_n0]) cube([gate_right - gate_left, gb_s1 - gb_s0, gb_n1 - gb_n0]);
            // teeth
            if (blade) // v3: one flat stop across the card instead of four teeth (same profile)
                translate([-blade_half, gb_s0, gb_n0]) cube([2 * blade_half, 3 - gb_s0, tooth_top + bp3_lift - gb_n0]);
            else for (x = tooth_x) translate([x - tooth_w / 2, gb_s0, gb_n0]) cube([tooth_w, 3 - gb_s0, tooth_top - gb_n0]);
            // end plates out to the axis
            for (x = [gate_left, gate_right - 3]) hull() {
                translate([x, gb_s0, gb_n0]) cube([3, gb_s1 - gb_s0, gb_n1 - gb_n0]);
                translate([x, gate_axis_s, gate_axis_n]) rotate([0, 90, 0]) cylinder(r = hub_r, h = 3);
            }
        }
        // left: hole for the horn's hub and two horn screw holes (as the old rocker)
        translate([gate_left - 1, gate_axis_s, gate_axis_n]) rotate([0, 90, 0]) cylinder(d = 7.2, h = 5);
        // right: hole for the bearing's pin
        translate([gate_right - 4, gate_axis_s, gate_axis_n]) rotate([0, 90, 0]) cylinder(d = 5.5, h = 5);
    }
}
// The horn screw holes are given in the machine's own coordinates, like the old rocker's.
module stop_gate(blade = false) {
    difference() {
        on_bed() stop_gate_bed(blade);
        for (d = [-1, 1]) translate([gate_left - 1, pin_axis[0] + d * 5.5, pin_axis[1] - 1]) rotate([0, 90, 0]) cylinder(d = 1.5, h = 5);
    }
}

module stop_gate_print(blade = false) {
    translate([0, 0, -gb_s0]) rotate([90, 0, 0]) rotate([-bed_angle, 0, 0]) translate([0, -bed_y, -bed_z]) stop_gate(blade);
}

// Clips down over the right end of the tilt bracket (between the bed walls) and carries the
// pin the stop gate's right end turns on. One M2 x 6 through the back jaw into the bracket.
module gate_bearing() {
    x0 = gate_right + 0.5;  x1 = side_in - 0.3;
    top = pivot_z - 20 + 32;          // tilt bracket top (157)
    difference() {
        union() {
            translate([x0, 70, top - 7]) cube([x1 - x0, tilt_bracket_y + 6 + 2.5 - 70, pin_axis[1] + 5 - top + 7]);
            translate([gate_right - 4, pin_axis[0], pin_axis[1]]) rotate([0, 90, 0]) cylinder(d = 5, h = x0 - gate_right + 4 + 0.01);
        }
        // the slot the bracket goes into
        translate([x0 - 1, tilt_bracket_y - 0.2, top - 8]) cube([x1 - x0 + 2, 6.4, 8]);
        // M2 screw through the back jaw
        translate([(x0 + x1) / 2, tilt_bracket_y + 10, top - 3.5]) rotate([90, 0, 0]) cylinder(d = 1.8, h = 12);
        translate([(x0 + x1) / 2, tilt_bracket_y + 6.2 + 3, top - 3.5]) rotate([90, 0, 0]) cylinder(d = 2.2, h = 3.2);
    }
}

module bed_side(left) {
    difference() {
        union() {
            yz_plate(side_in, side_t) polygon([
                [bed_y, wall_z0], [bed_back_y, wall_z0], [bed_back_y, bed_back_z + wall_h], [bed_y, bed_z + wall_h]]);
            // camera tower socket block, square to the bed (right wall only)
            if (!left) on_bed() translate([side_in + side_t - 2, card_s - boss_s / 2, -10])
                cube([tower_x + boss_s / 2 - side_in - side_t + 2, boss_s, 24]);
        }
        on_bed() {
            // groove the bed plate slides into
            translate([side_in - 0.01, -1, -bed_t - 0.15]) cube([2.01, bed_len + 2, bed_t + 0.3]);   // 2 mm into the wall
            // LED strip groove
            translate([side_in - 0.01, 5, led_n - led_w / 2]) cube([1.6, bed_len - 10, led_w]);
            // tower socket
            if (!left) translate([tower_x - (post_s + fit) / 2, card_s - (post_s + fit) / 2, -4]) cube([post_s + fit, post_s + fit, 30]);
        }
        if (left) {
            // pin servo: pokes in through the wall, shaft along x
            translate([side_in - 1, pin_axis[0], pin_axis[1]]) rotate([0, 90, 0]) rotate([0, 0, 90]) {
                servo_hole(side_t + 2);
                servo_screws(side_t + 2);
            }
        }
        // screw holes for the tilt bracket
        for (z = [pivot_z - 8, pivot_z + 2]) translate([side_in - 1, tilt_bracket_y + 3, z]) rotate([0, 90, 0]) cylinder(d = 3.2, h = side_t + 2);
        // enclosure build: M3 screws come up through the bridge plate into the bottom edge
        if (wall_z0 > 0) for (y = [bed_y + 12, bed_back_y - 12]) translate([side_in + side_t / 2, y, wall_z0 - 1]) cylinder(d = 2.6, h = 11);
    }
}

// Rocker: a flat plate the servo horn screws onto, a cross bar, and the two pins.
// Modelled where it sits with the pins up. Everything starts at the same height
// underneath, so it prints flat with no supports.
rocker_bottom = 159;
module pin_rocker() {
    hub_x = -side_in + sv_top - 1;   // just inside the left wall, where the servo shaft ends
    bar_y = bed_y + 1.5;
    difference() {
        union() {
            // plate in the y-z plane: the horn screws to its outer (left) face
            yz_plate(hub_x, 3) polygon([[bar_y, rocker_bottom], [pin_axis[0] + 6, rocker_bottom],
                [pin_axis[0] + 6, pin_axis[1] + 4], [pin_axis[0] - 2, pin_axis[1] + 6], [bar_y, rocker_bottom + 5]]);
            // cross bar
            translate([hub_x, bar_y, rocker_bottom]) cube([pin_x + 4 - hub_x, 4, 5]);
            // pins, up through the bed slots: the card side stands about 5 mm proud of the bed
            for (x = [-pin_x, pin_x]) translate([x - 1.5, bar_y + 0.5, rocker_bottom])
                cube([3, 3, bed_z + 1 * tan_a + pin_above - rocker_bottom]);
        }
        // hole for the horn's hub, and two horn screw holes
        translate([hub_x - 1, pin_axis[0], pin_axis[1]]) rotate([0, 90, 0]) cylinder(d = 7.2, h = 5);
        for (d = [-1, 1]) translate([hub_x - 1, pin_axis[0] + d * 5.5, pin_axis[1] - 1]) rotate([0, 90, 0]) cylinder(d = 1.5, h = 5);
    }
}

module tower_post() {
    len = cam_height + socket_d - 1 + 4;
    difference() {
        translate([-post_s / 2, -post_s / 2, 0]) cube([post_s, post_s, len]);
        translate([-8.5, post_s / 2 - 1.5, -1]) cube([17, 2, len + 2]);   // camera cable groove
    }
}

// Same camera plate as the scan station, with the arm reaching across (x) to the tower.
cam_holes = [[-10.5, -10], [10.5, -10], [-10.5, 2.5], [10.5, 2.5]];
module camera_head() {
    difference() {
        union() {
            translate([tower_x - boss_s / 2, -boss_s / 2, 0]) cube([boss_s, boss_s, socket_d + 6]);
            translate([0, -10, 0]) cube([tower_x, 20, 6]);
            translate([-17, -17, 0]) cube([34, 34, 3]);
            for (h = cam_holes) translate([h[0], h[1], 0]) cylinder(d = 5, h = 6);
        }
        translate([tower_x - (post_s + fit) / 2, -(post_s + fit) / 2, -1]) cube([post_s + fit, post_s + fit, socket_d + 1]);
        translate([-7, -9, -1]) cube([14, 18, 10]);                             // lens window
        for (h = cam_holes) translate([h[0], h[1], -1]) cylinder(d = 1.8, h = 10);
        translate([tower_x - boss_s / 2 - 1, -8.5, 6.5]) cube([3, 17, 2]);      // cable slot
    }
}

// ============================ CHUTE ==========================================

tilt_bracket_y = 78;      // front face of the tilt bracket
back_axle_end = 70;       // where the back axle meets the horn plate

// ---- OLD CHUTE (v1/v2: chute, trapdoor, hinge_pin, trapdoor_mount, hinge_lug, door_carrier).
// Retired 2026-11-04 by CHUTE v3 below; no longer exported. Kept only because the older picture
// guides (guide/scenes.scad, guide/v2/bed_scenes.scad) still draw them.

module chute() {
    difference() {
        union() {
            // floor
            translate([-ch_half, -ch_in, pivot_z - floor_t]) cube([2 * ch_half, 2 * ch_in, floor_t]);
            // front and back rails
            translate([-ch_half, -ch_out, pivot_z - floor_t]) cube([2 * ch_half, rail_t, front_rail_h + floor_t]);
            translate([-ch_half, ch_in, pivot_z - floor_t]) cube([2 * ch_half, rail_t, back_rail_h + floor_t]);
            // axles along y (flat underneath so they print without supports)
            for (y = [[front_bar_y - 8, -ch_out], [ch_out, back_axle_end]])
                translate([0, y[0], pivot_z]) intersection() {
                    rotate([-90, 0, 0]) cylinder(d = axle_d, h = y[1] - y[0]);
                    translate([-axle_d, 0, -floor_t]) cube([2 * axle_d, y[1] - y[0], axle_d]);
                }
            // plate the tilt servo's horn screws onto
            translate([-12, back_axle_end, pivot_z - floor_t]) cube([24, 2.5, 14]);
        }
        // trapdoor opening
        translate([-door_half, -ch_in - 0.01, pivot_z - floor_t - 1]) cube([2 * door_half, 2 * ch_in + 0.02, floor_t + 2]);
        // horn screw holes and hub clearance
        translate([0, back_axle_end - 1, pivot_z]) rotate([-90, 0, 0]) cylinder(d = 7.2, h = 5);
        for (d = [-1, 1]) translate([d * 7, back_axle_end - 1, pivot_z]) rotate([-90, 0, 0]) cylinder(d = 1.5, h = 5);
        // screw holes for the trapdoor mounts and hinge lugs (from above, M2 self-tapping)
        for (m = [0, 1]) mirror([m, 0, 0]) for (y = [-ch_in + 5, ch_in - 5]) translate([door_half + 8, y, pivot_z - floor_t - 1]) cylinder(d = 2.4, h = floor_t + 2);
        // ... and for the door carriers that replace them
        for (m = [0, 1]) mirror([m, 0, 0]) for (y = carrier_screws_y) translate([carrier_x + 3, y, pivot_z - floor_t - 1]) cylinder(d = 2.4, h = floor_t + 2);
    }
}

// Right trapdoor, closed: fills x = 0.5 .. 35.5 of the opening, hinged at x = 36.
// Front ear: a fork below the hinge axis. The servo's single-arm horn, arm pointing
// straight down, slides up into the slot between the prongs, so the door turns with the
// servo without screws. The slot goes right through, so however tall the horn is, it can't
// push the door out of line. Back ear: turns on a printed hinge_pin through the lug.
// The panel stops 2 mm short of the front rail so it swings past the servo's top.
horn_hub = 7.6;           // slot width: the horn's hub, with clearance (the arm is narrower)
ear_face = -ch_out + 7;   // y of the front ear's servo-side face (clear of the servo's gear boss)
module trapdoor() {
    ear_t = -ch_in + 10 - ear_face;
    difference() {
        union() {
            translate([0.5, -ch_in + 2.1, pivot_z - floor_t]) cube([door_half - 1, 2 * ch_in - 2.6, floor_t]);
            // back ear down to the hinge axis
            hull() {
                translate([door_half - 10, ch_in - 10, pivot_z - floor_t]) cube([10, 4, 0.1]);
                translate([door_half, ch_in - 10, hinge_z]) rotate([-90, 0, 0]) cylinder(r = 4, h = 4);
            }
            // front ear: from the floor down past the axis to a fork 14 mm below it
            hull() {
                translate([door_half - 10, ear_face, pivot_z - floor_t]) cube([10, ear_t, 0.1]);
                translate([door_half - 4, ear_face, hinge_z]) cube([8, ear_t, 4]);
                translate([door_half - 8, ear_face, hinge_z - 2]) cube([14, ear_t, 0.1]);
            }
            // (no further than 6 mm past the axis on the outer side, or it hits the tray floor at 90°)
            translate([door_half - 8, ear_face, hinge_z - 14]) cube([14, ear_t, 12]);
        }
        // hinge pin hole (back ear)
        translate([door_half, ch_in - 11, hinge_z]) rotate([-90, 0, 0]) cylinder(d = 3.2, h = 6);
        // the slot for the horn, open at the bottom, right through the ear
        translate([door_half - horn_hub / 2, ear_face - 1, hinge_z - 20]) cube([horn_hub, ear_t + 2, 20]);
        translate([door_half, ear_face - 1, hinge_z]) rotate([-90, 0, 0]) cylinder(d = horn_hub, h = ear_t + 2);
    }
}

// Hinge pin: pushes through the hinge lug into the door's back ear. Prints standing on its head.
module hinge_pin() {
    cylinder(d = 6, h = 1.2);
    cylinder(d = 2.75, h = 12.2);
    translate([0, 0, 12.2]) cylinder(d1 = 2.75, d2 = 2, h = 0.6);
}

// Servo mount under the front of the tray, right side. The servo's shaft lines up with the hinge.
module trapdoor_mount() {
    difference() {
        union() {
            translate([door_half - 12, -ch_out - 2.5, hinge_z - 10]) cube([sv_len + 12, 2.5, pivot_z - floor_t - hinge_z + 10]);
            // flange screwed under the tray floor, outside the trapdoor opening
            translate([door_half + 1, -ch_out - 2.5, pivot_z - floor_t - 3]) cube([sv_len - 1, 12, 3]);
        }
        translate([door_half, -ch_out - 2.5 - 1, hinge_z]) rotate([-90, 0, 0]) rotate([0, 0, 0]) {
            translate([-sv_shaft_off - 0.3, -sv_w / 2 - 0.3, 0]) cube([sv_len + 0.6, sv_w + 0.6, 6]);
        }
        for (d = [-1, 1]) translate([door_half + sv_len / 2 - sv_shaft_off + d * sv_screw / 2, -ch_out - 4, hinge_z]) rotate([-90, 0, 0]) cylinder(d = 1.8, h = 5);
        translate([door_half + 8, -ch_in + 5, pivot_z - floor_t - 4]) cylinder(d = 2.4, h = 5);
    }
}

// Back hinge lug, right side: screwed under the tray floor, holds the hinge pin.
module hinge_lug() {
    difference() {
        hull() {
            translate([door_half + 2, ch_in - 6, pivot_z - floor_t - 3]) cube([10, 6, 3]);
            translate([door_half, ch_in - 6, hinge_z]) rotate([-90, 0, 0]) cylinder(r = 4, h = 6);
        }
        translate([door_half, ch_in - 7, hinge_z]) rotate([-90, 0, 0]) cylinder(d = 2.9, h = 8);  // pin: 3 mm screw or filament
        translate([door_half + 8, ch_in - 5, pivot_z - floor_t - 4]) cylinder(d = 2.4, h = 5);
    }
}

// Door carrier, right side: the servo mount and the hinge lug joined by a bar, so the
// servo shaft and the hinge pin can't end up out of line. Three M2 screws from above, along
// the outer edge of the tray floor (clear of the servo body). Replaces trapdoor_mount +
// hinge_lug. Prints upside down, bar on the bed.
carrier_x = door_half + 17.5;    // bar x = carrier_x .. carrier_x + 6, screws on its centre line
module door_carrier() {
    top = pivot_z - floor_t;
    sv_c = door_half - (sv_len / 2 - sv_shaft_off);   // middle of the servo body (it points inward)
    plate_x0 = sv_c - sv_tab_len / 2 - 1.5;
    plate_x1 = door_half + 11;
    plate_z0 = hinge_z - 7;
    difference() {
        union() {
            // servo plate, with its outer bottom corner cut away (that corner swings lowest)
            translate([0, -ch_out, 0]) rotate([90, 0, 0]) linear_extrude(2.5) polygon([
                [plate_x0, plate_z0], [plate_x1 - 4, plate_z0], [plate_x1, plate_z0 + 5],
                [plate_x1, top], [plate_x0, top]]);
            // strip out to the bar
            translate([plate_x1 - 1, -ch_out - 2.5, top - 3]) cube([carrier_x + 6 - plate_x1 + 1, 2.5, 3]);
            // bar along the outer edge, front to back
            translate([carrier_x, -ch_out - 2.5, top - 3]) cube([6, ch_in + ch_out + 2.5, 3]);
            // stiffening rib under the bar
            translate([carrier_x + 4, -ch_out, top - 5]) cube([2, ch_in + ch_out - 6, 5]);
            // hinge lug (as hinge_lug), tied across to the bar behind the door's back ear
            hull() {
                translate([door_half + 2, ch_in - 6, top - 3]) cube([10, 6, 3]);
                translate([door_half, ch_in - 6, hinge_z]) rotate([-90, 0, 0]) cylinder(r = 4, h = 6);
            }
            translate([door_half + 2, ch_in - 6, top - 3]) cube([carrier_x + 6 - door_half - 2, 6, 3]);
        }
        // servo hole, body towards the middle, and its two tab screws
        translate([door_half, -ch_out - 2.5 - 1, hinge_z]) rotate([-90, 0, 0])
            translate([-(sv_len - sv_shaft_off) - 0.3, -sv_w / 2 - 0.3, 0]) cube([sv_len + 0.6, sv_w + 0.6, 6]);
        for (d = [-1, 1]) translate([sv_c + d * sv_screw / 2, -ch_out - 4, hinge_z]) rotate([-90, 0, 0]) cylinder(d = 1.8, h = 5);
        // hinge pin
        translate([door_half, ch_in - 7, hinge_z]) rotate([-90, 0, 0]) cylinder(d = 2.9, h = 8);
        // screws up into the tray floor
        for (y = carrier_screws_y) translate([carrier_x + 3, y, top - 9]) cylinder(d = 2.4, h = 10);
    }
}
carrier_screws_y = [-ch_in + 6, 0, ch_in - 3];


// ============================ CHUTE v3: SOLID BOMB BAY ========================
// Replaces chute, trapdoor, door_carrier and hinge_pin (and goes with bridge_front3 in
// enclosure.scad). What it fixes:
//   - no screws through the tray floor: the card's surface is the bare print
//   - each door turns on two round journals (front and back) clamped between the tray and
//     one hinge_frame underneath, so a servo never holds a door up
//   - the door servos sit in pockets in an 8 mm thick front wall, high above the card,
//     and turn the doors through a crank and a link (a parallelogram: door and servo turn
//     the same amount), so a spline tooth off just shifts the slider angle
//   - nothing hangs low enough to touch the bridge when the tray tips 25 degrees
// Parts: chute3, door3 + door3_left, door_crank3 + door_crank3_left, hinge_frame3,
// servo_crank3 + servo_crank3_left, door_link3 x2. All print flat with no supports.
v3_hx = 36.6;            // door hinge axes x = +-36.6, along y ...
v3_hz = pivot_z - floor_t - 0.5;   // ... at z = 142, the underside of the floor
v3_edge = 36;            // door's outer top edge (the wing starts at 36.25)
v3_gap = 0.25;
v3_door_y = ch_in - 0.25;          // doors run y = +-45.25
hub3_r = 4;              // door journals
hub3_flat = pivot_z - v3_hz;       // the journals are flat on top (3 mm up), so the door prints top down
bore3_r = hub3_r + 0.25;
wall3_y0 = -ch_in - 8;   // front wall y = -53.5 .. -45.5 (8 thick)
back3_y1 = ch_in + 6;    // back rail y = 45.5 .. 51.5
back3_h = 10;            // back rail stands 10 above the floor
front3_h = front_rail_h; // front rail height above the floor (30) ...
mount3_top = 190;        // ... and up to z = 190 where the servos sit (x = +-41)
mount3_x = 41;
// door servo shafts (right one; the left is mirrored), and the crank sweep
sv3_x = 28;  sv3_z = 180;
crank3_r = 12;
crank3_shut = 145;       // crank angle with the door shut (degrees, 0 = +x, 90 = up) ...
crank3_open = 95;        // ... and how far it turns to open the door
// along y, in front of the tray's front wall (servo tab face is the wall's back face, y = -45.5):
crank3_y0 = wall3_y0 - 0.5;        // door crank: y -54 .. -60.5
crank3_y1 = crank3_y0 - 6.5;
scrank3_y0 = -ch_in - 11;          // servo crank: -56.5 .. -60.5 (stock horn sits in a pocket on its back)
scrank3_y1 = scrank3_y0 - 4;
link3_y0 = crank3_y1 - 0.5;        // link: -61 .. -64
link3_y1 = link3_y0 - 3;
link3_len = norm([sv3_x - v3_hx, sv3_z - v3_hz]);
frame3_z0 = 135;         // hinge frame: beams z 135..142 under the front wall and back rail
gate3_cut_x = 31.5;      // back rail stays full depth only outside x = +-31.5
// hinge frame screws (x, y): either side of the front journals; outside the back ones and one
// in the middle, under the back axle
frame3_screws = [for (x = [-46, -20, 20, 46]) [x, wall3_y0 + 4], for (x = [-46, 0, 46]) [x, (ch_in + back3_y1) / 2]];

// The D-shaped journal profile, in the (x, z) plane about the axis.
module hub3_2d(r = hub3_r, flat = hub3_flat) { intersection() { circle(r = r); translate([-r - 1, -r - 1]) square([2 * r + 2, flat + r + 1]); } }
// A 2D shape in the (x, z) plane, extruded along y between a and b (either order).
module along_y(a, b) { translate([0, min(a, b), 0]) rotate([-90, 0, 0]) linear_extrude(abs(b - a)) mirror([0, 1, 0]) children(); }

// ---- tray
module chute3() {
    top = pivot_z;  bot = pivot_z - floor_t;
    difference() {
        union() {
            // floor wings, outside the door opening
            for (m = [0, 1]) mirror([m, 0, 0]) translate([v3_edge + v3_gap, -ch_in, bot]) cube([ch_half - v3_edge - v3_gap, 2 * ch_in, floor_t]);
            // front wall: 8 thick, rail height at the ends, up to z 190 across the servo mounts
            translate([-ch_half, wall3_y0, bot]) cube([2 * ch_half, 8, front3_h + floor_t]);
            translate([-mount3_x, wall3_y0, bot]) cube([2 * mount3_x, 8, mount3_top - bot]);
            // back rail, 6 thick
            translate([-ch_half, ch_in, bot]) cube([2 * ch_half, back3_y1 - ch_in, back3_h + floor_t]);
            // axles along y, flat underneath (as before)
            for (y = [[front_bar_y - 8, wall3_y0], [back3_y1, back_axle_end]])
                translate([0, y[0], pivot_z]) intersection() {
                    rotate([-90, 0, 0]) cylinder(d = axle_d, h = y[1] - y[0]);
                    translate([-axle_d, 0, -floor_t]) cube([2 * axle_d, y[1] - y[0], axle_d]);
                }
            // plate the tilt servo's horn screws onto
            translate([-12, back_axle_end, bot]) cube([24, 2.5, 14]);
        }
        // round off the outer exit edges a little (cards slide off here)
        for (m = [0, 1]) mirror([m, 0, 0]) translate([ch_half, -ch_in - 1, top]) rotate([-90, 0, 0]) difference() {
            translate([-1.5, -1.5, 0]) cube([3, 3, 2 * ch_in + 2]); translate([-1.5, 1.5, -1]) cylinder(r = 1.5, h = 2 * ch_in + 4); }
        // upper halves of the door journal bores, in the underside of the front wall and back rail
        for (m = [0, 1]) mirror([m, 0, 0]) for (y = [[wall3_y0 - 1, -ch_in + 0.01], [ch_in - 0.01, back3_y1 + 1]])
            translate([v3_hx, 0, v3_hz]) along_y(y[1], y[0]) circle(r = bore3_r);
        // the journals turn in a small notch at each inner corner of the wings
        for (m = [0, 1]) mirror([m, 0, 0]) for (y = [-ch_in - 1, ch_in - 1]) translate([v3_hx - 5, y, v3_hz - 5]) cube([bore3_r + 5.25, 2, 10]);
        // servo pockets: the servo's top goes through the front wall from behind, shaft forward
        for (m = [0, 1]) mirror([m, 0, 0]) {
            translate([sv3_x, -ch_in + 1, sv3_z]) rotate([90, 0, 0]) rotate([0, 0, 180]) { servo_hole(10); servo_screws(9); }
            // and a clear path for the horn and servo crank in front of it
        }
        // horn screw holes and hub clearance (tilt servo)
        translate([0, back_axle_end - 1, pivot_z]) rotate([-90, 0, 0]) cylinder(d = 7.2, h = 5);
        for (d = [-1, 1]) translate([d * 7, back_axle_end - 1, pivot_z]) rotate([-90, 0, 0]) cylinder(d = 1.5, h = 5);
        // the stop gate's teeth swing through here if they drop while the tray is tipped, so between
        // the hinges the back rail is only a 2 mm lip (kept full in the middle, where the back axle
        // joins it; the hinge frame's back beam stiffens it from below)
        for (m = [0, 1]) mirror([m, 0, 0]) translate([6, ch_in - 0.01, top - 1]) cube([gate3_cut_x - 6, back3_y1 - ch_in + 0.02, 20]);
        for (m = [0, 1]) mirror([m, 0, 0]) translate([6, ch_in - 0.01, top + 5]) cube([gate3_cut_x - 3, back3_y1 - ch_in + 0.02, 20]);
        // screw holes for the hinge frame (M3 self-tapping, up from below)
        for (xy = frame3_screws) translate([xy[0], xy[1], bot - 1]) cylinder(d = 2.6, h = 13);
    }
}

// ---- door (right; door3_left is its mirror image)
module door3() {
    top = pivot_z;
    difference() {
        union() {
            // the slab
            translate([v3_gap, -v3_door_y, top - floor_t]) cube([v3_edge - v3_gap, 2 * v3_door_y, floor_t]);
            // spine under its outer edge, full length (stiffens it; stays inboard of the axis so it
            // can't swing up into the wing)
            translate([v3_hx - 8, -v3_door_y, v3_hz - 4]) cube([7, 2 * v3_door_y, 4.01]);
            // journals at both ends, and the D-shaped end the crank slides onto
            translate([v3_hx, 0, v3_hz]) along_y(crank3_y1 + 0.01, -ch_in + 0.75) hub3_2d();
            translate([v3_hx, 0, v3_hz]) along_y(back3_y1 - 0.25, ch_in - 0.75) hub3_2d();
            // fill between slab and spine at the ends, where the journals join (all inboard of x = 36,
            // so nothing swings up into the wing as the door opens)
            for (y = [-v3_door_y, v3_door_y - 6]) translate([v3_hx - 8, y, v3_hz - 4]) cube([v3_edge - v3_hx + 8, 6, 4 + floor_t]);
        }
        // axial screw hole for the crank (M3 self-tapping, from the front)
        translate([v3_hx, crank3_y1 - 1, v3_hz]) rotate([-90, 0, 0]) cylinder(d = 2.6, h = 12);
    }
}

// ---- door crank (right): slides on the D end of the front journal, held by one M3 from the front
module door_crank3() {
    a = crank3_shut;
    difference() {
        hull() {
            translate([v3_hx, 0, v3_hz]) along_y(crank3_y0, crank3_y1) circle(r = 6);
            translate([v3_hx + crank3_r * cos(a), 0, v3_hz + crank3_r * sin(a)]) along_y(crank3_y0, crank3_y1) circle(r = 4.5);
        }
        translate([v3_hx, 0, v3_hz]) along_y(crank3_y0 + 1, crank3_y1 - 1) offset(delta = 0.15) hub3_2d();
        translate([v3_hx, crank3_y1 - 1, v3_hz]) rotate([-90, 0, 0]) cylinder(d = 3.4, h = 10);
        // link pin: M3 self-tapping into the crank
        translate([v3_hx + crank3_r * cos(a), crank3_y1 - 1, v3_hz + crank3_r * sin(a)]) rotate([-90, 0, 0]) cylinder(d = 2.6, h = 10);
    }
}

// ---- servo crank: the servo's own single-arm horn presses into a pocket on its back. The
// horn's arm points a quarter turn from the link pin (so the pin screw can't hit it, and it
// stays pointing down-ish, clear of the deck, whatever the doors and tilt do); the pocket runs
// out through the end, so any length of horn fits.
horn3_len = 22;  horn3_w = 6.6;  horn3_hub = 7.8;
horn3_turn = 90;  horn3_reach = 17;
module servo_crank3() {
    a = crank3_shut;
    difference() {
        hull() {
            translate([sv3_x, 0, sv3_z]) along_y(scrank3_y0, scrank3_y1) circle(r = 7);
            translate([sv3_x + crank3_r * cos(a), 0, sv3_z + crank3_r * sin(a)]) along_y(scrank3_y0, scrank3_y1) circle(r = 4.5);
            translate([sv3_x + horn3_reach * cos(a + horn3_turn), 0, sv3_z + horn3_reach * sin(a + horn3_turn)]) along_y(scrank3_y0, scrank3_y1) circle(r = 4.5);
        }
        // horn pocket, 2 deep, the arm a quarter turn from the link pin
        translate([sv3_x, 0, sv3_z]) along_y(scrank3_y0 + 1, scrank3_y0 - 2) rotate(a + horn3_turn) {
            circle(d = horn3_hub);
            translate([0, -horn3_w / 2]) square([horn3_len + 5, horn3_w]);
        }
        // the horn's own screw goes through the middle, head on the front
        translate([sv3_x, scrank3_y1 - 1, sv3_z]) rotate([-90, 0, 0]) cylinder(d = 2.4, h = 10);
        // link pin, M3 self-tapping (comes in from the front, through the link)
        translate([sv3_x + crank3_r * cos(a), scrank3_y1 - 1, sv3_z + crank3_r * sin(a)]) rotate([-90, 0, 0]) cylinder(d = 2.6, h = 10);
    }
}

// ---- link: two M3 screws, one at each end
module door_link3() {
    a = crank3_shut;
    p0 = [v3_hx + crank3_r * cos(a), v3_hz + crank3_r * sin(a)];
    p1 = [sv3_x + crank3_r * cos(a), sv3_z + crank3_r * sin(a)];
    difference() {
        hull() for (p = [p0, p1]) translate([p[0], 0, p[1]]) along_y(link3_y0, link3_y1) circle(r = 4);
        for (p = [p0, p1]) translate([p[0], link3_y1 - 1, p[1]]) rotate([-90, 0, 0]) cylinder(d = 3.4, h = 6);
    }
}

// ---- hinge frame: lower halves of the four journal bores, screwed up into the tray
module hinge_frame3() {
    bot = pivot_z - floor_t;
    difference() {
        union() {
            for (y = [[wall3_y0, -ch_in], [ch_in, back3_y1]]) {
                // beam: deep under the bores, shallower out at the ends (tilt clearance)
                translate([0, y[0], 0]) rotate([90, 0, 0]) mirror([0, 0, 1]) linear_extrude(y[1] - y[0]) polygon([
                    [-ch_half + 2, bot], [-ch_half + 2, bot - 4], [-47, frame3_z0 + 1], [47, frame3_z0 + 1], [ch_half - 2, bot - 4], [ch_half - 2, bot]]);
                for (m = [0, 1]) mirror([m, 0, 0]) translate([v3_hx, 0, v3_hz]) along_y(y[1], y[0]) circle(r = bore3_r + 2.6);
            }
            // side bars under the wings
            for (m = [0, 1]) mirror([m, 0, 0]) translate([48, wall3_y0, bot - 4]) cube([ch_half - 2 - 48, back3_y1 - wall3_y0, 4]);
        }
        // nothing above the underside of the tray
        translate([-100, -100, bot]) cube([200, 200, 50]);
        for (m = [0, 1]) mirror([m, 0, 0]) for (y = [[wall3_y0 - 1, -ch_in + 0.01], [ch_in - 0.01, back3_y1 + 1]])
            translate([v3_hx, 0, v3_hz]) along_y(y[1], y[0]) circle(r = bore3_r);
        // keep clear of the door spines and slabs between the beams
        translate([-v3_hx - 5, -ch_in, frame3_z0 - 1]) cube([2 * v3_hx + 10, 2 * ch_in, 10]);
        // M3 screws up into the tray
        for (xy = frame3_screws) {
            translate([xy[0], xy[1], frame3_z0 - 5]) cylinder(d = 3.4, h = 20);
            translate([xy[0], xy[1], frame3_z0 - 5]) cylinder(d = 6, h = 5 + 2.5);   // head sits in a counterbore
        }
    }
}

// Moving parts in place: tilt (degrees, + = right side down) and doors (0 = shut, 1 = open).
module door3_moving(open = 0) {
    a = open * crank3_open;
    translate([v3_hx, 0, v3_hz]) rotate([0, -a, 0]) translate([-v3_hx, 0, -v3_hz]) { door3(); door_crank3(); }
    // the parallelogram: the servo crank turns by the same angle, the link slides without turning
    translate([sv3_x, 0, sv3_z]) rotate([0, -a, 0]) translate([-sv3_x, 0, -sv3_z]) servo_crank3();
    translate([crank3_r * (cos(crank3_shut + a) - cos(crank3_shut)), 0, crank3_r * (sin(crank3_shut + a) - sin(crank3_shut))]) door_link3();
}
module chute3_moving(tilt = 0, open = 0, servos = true) {
    translate([0, 0, pivot_z]) rotate([0, tilt, 0]) translate([0, 0, -pivot_z]) {
        color("#e8772e") chute3();
        color("#2b2b2b") hinge_frame3();
        for (m = [0, 1]) mirror([m, 0, 0]) {
            color("#d0d0d0") door3_moving(open);
            if (servos) color("#3060c0") translate([sv3_x, -ch_in, sv3_z]) servo_body3();
        }
    }
}
// MG90S stand-in for the clearance checks: body behind the tabs, inward; shaft at the origin.
module servo_body3() {
    rotate([90, 0, 0]) rotate([0, 0, 180]) {
        translate([-sv_shaft_off - 0.0, -sv_w / 2, -16.5 - 2.5]) cube([sv_len, sv_w, 16.5]);       // body (behind the tabs)
        translate([-sv_shaft_off - (sv_tab_len - sv_len) / 2, -sv_w / 2, -2.5]) cube([sv_tab_len, sv_w, 2.5]);   // tabs
        translate([-sv_shaft_off, -sv_w / 2, 0]) cube([sv_len, sv_w, sv_top]);                     // top, through the wall
        cylinder(d = 11.8, h = 10);
    }
}

// Tilt servo bracket: a plate across between the bed side walls, with the servo through it.
module tilt_bracket() {
    difference() {
        translate([-side_in + 0.3, tilt_bracket_y, pivot_z - 20]) cube([2 * side_in - 0.6, 6, 32]);
        // servo pokes through from the back; shaft lines up with the tilt axis
        translate([0, tilt_bracket_y + 6 + 1, pivot_z]) rotate([90, 0, 0]) {
            servo_hole(8);
            servo_screws(8);
        }
        // screws into the side walls
        for (m = [0, 1]) mirror([m, 0, 0]) for (z = [pivot_z - 8, pivot_z + 2])
            translate([side_in - 12, tilt_bracket_y + 3, z]) rotate([0, 90, 0]) cylinder(d = 2.6, h = 14);
    }
}

// ============================ FRAME AND BINS ===================================

module frame_side() {
    difference() {
        yz_plate(frame_x, frame_t) polygon([[front_bar_y - 6, 0], [ch_out + 4, 0], [ch_out + 4, frame_h], [front_bar_y - 6, frame_h]]);
        // big window so you can see into the bins (and save filament)
        yz_plate(frame_x - 1, frame_t + 2) offset(r = 8) offset(delta = -8)
            polygon([[front_bar_y + 14, 14], [ch_out - 10, 14], [ch_out - 10, frame_h - 40], [front_bar_y + 14, frame_h - 40]]);
        // screw holes for the front bar
        for (z = [frame_h - 22, frame_h - 8]) translate([frame_x - 1, front_bar_y - 3, z]) rotate([0, 90, 0]) cylinder(d = 3.2, h = frame_t + 2);
    }
}

module front_bar() {
    difference() {
        translate([-frame_x + 0.3, front_bar_y - 6, frame_h - 30]) cube([2 * frame_x - 0.6, 6, 30]);
        translate([0, front_bar_y - 7, pivot_z]) rotate([-90, 0, 0]) cylinder(d = axle_d + 0.5, h = 8);
        for (m = [0, 1]) mirror([m, 0, 0]) for (z = [frame_h - 22, frame_h - 8])
            translate([frame_x - 12, front_bar_y - 3, z]) rotate([0, 90, 0]) cylinder(d = 2.6, h = 14);
    }
}

module bin() {
    difference() {
        translate([-bin_w / 2, -bin_l / 2, 0]) cube([bin_w, bin_l, bin_h]);
        translate([-bin_w / 2 + 2, -bin_l / 2 + 2, 2]) cube([bin_w - 4, bin_l - 4, bin_h]);
        // finger pull in the front
        translate([0, -bin_l / 2 - 1, bin_h]) rotate([-90, 0, 0]) cylinder(r = 14, h = 4);
    }
}

// ============================ OUTPUT ==========================================

// Each printable part is turned and moved so it sits flat on the print bed.
if (part == "bed_plate") translate([0, 0, bed_t]) bed_plate();
else if (part == "bed_plate3") translate([0, 0, bed_t]) bed_plate3();
else if (part == "bed_side_left") translate([0, 0, -side_in]) rotate([0, 90, 0]) mirror([1, 0, 0]) bed_side(true);
else if (part == "bed_side_right") translate([0, 0, -side_in]) rotate([0, -90, 0]) bed_side(false);
else if (part == "pin_rocker") translate([0, 0, -rocker_bottom]) pin_rocker();
// stop gate: printed standing on the front faces of its bar and teeth (s up), no supports
else if (part == "stop_gate") stop_gate_print();
else if (part == "stop_gate3") stop_gate_print(true);
else if (part == "gate_bearing") translate([-160, -78, side_in - 0.3]) rotate([0, 90, 0]) gate_bearing();   // on its outer face, pin up
else if (part == "tower_post") translate([0, 0, post_s / 2]) rotate([0, 90, 0]) tower_post();
else if (part == "camera_head") camera_head();
else if (part == "tilt_bracket") translate([0, 0, -tilt_bracket_y]) rotate([90, 0, 0]) tilt_bracket();
// chute v3 (solid bomb bay)
else if (part == "chute3") translate([0, 0, -(pivot_z - floor_t)]) chute3();                       // floor down
else if (part == "door3") mirror([0, 0, 1]) translate([0, 0, -pivot_z]) door3();                   // top face down
else if (part == "door3_left") mirror([1, 0, 0]) mirror([0, 0, 1]) translate([0, 0, -pivot_z]) door3();
else if (part == "door_crank3") translate([0, 0, -crank3_y1]) rotate([90, 0, 0]) door_crank3();  // front face down
else if (part == "door_crank3_left") mirror([1, 0, 0]) translate([0, 0, -crank3_y1]) rotate([90, 0, 0]) door_crank3();
else if (part == "servo_crank3") translate([0, 0, -scrank3_y1]) rotate([90, 0, 0]) servo_crank3(); // front face down, horn pocket up
else if (part == "servo_crank3_left") mirror([1, 0, 0]) translate([0, 0, -scrank3_y1]) rotate([90, 0, 0]) servo_crank3();
else if (part == "door_link3") translate([0, 0, -link3_y1]) rotate([90, 0, 0]) door_link3();
else if (part == "hinge_frame3") mirror([0, 0, 1]) translate([0, 0, -(pivot_z - floor_t)]) hinge_frame3();   // top face down
else if (part == "frame_side") translate([0, 0, -frame_x]) rotate([0, -90, 0]) frame_side();
else if (part == "front_bar") translate([0, 0, -(front_bar_y - 6)]) rotate([90, 0, 0]) front_bar();
else if (part == "bin") bin();
else if (part == "none") { }
else assembly();

module assembly() {
    color("white") on_bed() bed_plate3();
    color("#2b2b2b") bed_side(false);
    color("#2b2b2b") mirror([1, 0, 0]) bed_side(true);
    // LED strips
    for (m = [0, 1]) mirror([m, 0, 0]) color("#fff2b0") on_bed() translate([side_in - 0.5, 6, led_n - led_w / 2]) cube([0.5, bed_len - 12, led_w]);
    // card resting against the stop teeth
    color("#c9a46a") on_bed() rotate([bp3_extra, 0, 0]) translate([-card_w / 2, 3, bp3_lift + bp3_rib_h + 0.05]) cube([card_w, card_l, 0.3]);
    // pins + rocker (rotates about the pin servo shaft)
    color("orange") translate([0, pin_axis[0], pin_axis[1]]) rotate([show_pins_down ? gate_drop : 0, 0, 0]) translate([0, -pin_axis[0], -pin_axis[1]]) stop_gate(true);
    color("#2b2b2b") gate_bearing();
    // camera tower
    color("#3a3f47") on_bed() translate([tower_x, card_s, -4]) tower_post();
    color("#3a3f47") on_bed() translate([0, card_s, cam_height]) rotate([0, 0, 0]) camera_head();
    // chute (v3), tilting about the y axis through (x = 0, z = pivot_z)
    chute3_moving(show_tilt, show_doors_open ? 1 : 0);
    color("#2b2b2b") tilt_bracket();
    if (show_frame) {
        for (m = [0, 1]) mirror([m, 0, 0]) color("#2b2b2b", 0.9) frame_side();
        color("#2b2b2b") front_bar();
        for (i = [-1, 0, 1]) color("#3a3f47") translate([i * bin_pitch, 0, 0]) bin();
    }
}
