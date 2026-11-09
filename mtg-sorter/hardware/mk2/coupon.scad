// Sorter Mk2 fit coupon: print this first (about 40 minutes, black PLA, no supports).
//
// It holds every screwless joint the Mk2 uses at a few sizes. Try each by hand and write the
// size that feels right into fit.scad; every other Mk2 part reads its sizes from there.
//
//   A  pin holes, 3 mm steel dowel pin: upright (in the raised bar) and sideways (in the back rib)
//      2.8 to 3.3 mm. Pick the smallest that takes a pin with a firm push (pin_press) and the
//      smallest that lets a pin spin freely (pin_free).
//   B  dovetail slots at 0.1, 0.2 and 0.3 mm per flank. Slide the loose tongue in upside down;
//      pick the one that slides with a light push and doesn't wobble (fit_dove).
//   C  snap hooks 1.2, 1.6 and 2.0 mm thick, each with its own catch block. Push in until it
//      clicks, pull it out, ten times. Pick the thinnest that still holds hard and never
//      cracks (hook_t). PLA cracking? Try PETG for hooks.
//   D  magnet pockets 6.0, 6.1, 6.2 mm. Pick the one a 6 x 3 mm magnet presses into and stays
//      without glue (mag_pocket_d).
//   E  cable channel with its flush lid: the lid should click in level with the top.
//   F  board pegs: the test board's 2.7 mm hole (like the Pi 5) clicks onto the 2.5 peg, its
//      2.2 mm hole (like Camera Module 3) onto the 2.0 peg; the board slides into the grooves.
//
// part = "plate" (the main plate), "pieces" (the loose pieces), "all" (both, as in the 3MF).
include <joints.scad>
part = "all";

pins  = [2.8, 2.9, 3.0, 3.1, 3.2, 3.3];
doves = [0.1, 0.2, 0.3];
hooks = [1.2, 1.6, 2.0];
mags  = [6.0, 6.1, 6.2];
base_t = 4;
W = 150;  D = 104;

module label(t, p, s = 3.2) { translate([p[0], p[1], p[2] - 0.5]) linear_extrude(0.51) text(t, size = s, halign = "center", valign = "center", font = "Liberation Sans:style=Bold"); }
fmt = function(v) str(floor(v * 10 + 0.5) / 10);

module plate() {
    difference() {
        union() {
            ccube([W, D, base_t]);
            translate([4, 84, 0]) ccube([82, 16, 12]);                 // A: upright pin bar
            translate([90, 88, 0]) ccube([56, 12, 14]);                // A: sideways pin rib
            for (i = [0 : 2]) translate([6 + i * 33, 46, 0]) ccube([28, 26, 10]);   // B: dovetail blocks
            translate([108, 8, 0]) ccube([24, 40, 12]);                // E: channel block
            translate([62, 8, base_t - 0.01]) card_guides(30, 25);                 // F: grooves for the test board
            translate([14, 20, base_t - 0.01]) board_peg(peg_pi);      // F: Pi peg
            translate([30, 20, base_t - 0.01]) board_peg(peg_cam);     // F: camera peg
        }
        // A upright: through the bar
        for (i = [0 : 5]) { translate([11 + i * 13.5, 92, -1]) pin_hole(pins[i], 14); label(fmt(pins[i]), [11 + i * 13.5, 79, base_t]); }
        // A sideways: through the rib along y, 8 mm up
        for (i = [0 : 5]) translate([95 + i * 9.2, 87, 8]) rotate([-90, 0, 0]) pin_hole(pins[i], 14);
        label("A  pins: upright / sideways", [118, 80, base_t], 2.6);
        // B: slots open at the top face, along y, narrow at the top and wider below
        for (i = [0 : 2]) {
            translate([20 + i * 33, 46, 10]) mirror([0, 0, 1]) dove_slot_cut(26, g = doves[i]);
            label(fmt(doves[i]), [20 + i * 33, 40, base_t]);
        }
        // D: magnet pockets
        for (i = [0 : 2]) { translate([112 + i * 12, 70, base_t - mag_pocket_h]) cylinder(d = mags[i], h = mag_pocket_h + 0.01, $fn = 40);
                            label(fmt(mags[i]), [112 + i * 12, 62, base_t], 2.4); }
        label("D", [145, 70, base_t]);
        // E: channel along y in the block's top
        translate([120, 8, 12]) chan_cut(40);
        label("E", [138, 28, base_t]);
        label("F", [8, 34, base_t]);
        label("F", [62, 42, base_t]);
        label("B", [104, 59, base_t]);
        label("C: hooks are loose pieces", [80, 4, base_t], 2.4);
    }
}
module pin_hole(d, h) cylinder(d = d, h = h, $fn = 40);

// ---- loose pieces --------------------------------------------------------------------------
// Dovetail tongue: a strip with the rail on it; flip it over into a slot.
module tongue() { ccube([16, 26, 2.5]); translate([8, 0, 2.5 - 0.01]) dove_rail(26); }
// Snap hook pair, 2D in the plate's plane (prints flat, bends along the layers), 6 mm tall.
L = 10;  lip = 0.8;  clear = 0.2;
module hook_piece(t) {
    linear_extrude(hook_w) {
        translate([-8, -8]) square([t + 16, 8]);
        square([t, L]);
        polygon([[t - 0.01, L - 0.01], [t + lip, L], [t + lip, L + 0.6], [t - 0.01, L + 0.6 + lip / tan(30)]]);
    }
}
// The catch block: the hook goes in through a slot under a 2 mm roof (the roof holds the two
// halves together) and catches on the far face.
module hook_block(t) {
    difference() {
        translate([-10, 0.2, 0]) cube([t + 20, L - 0.2, hook_w + 2.4]);
        translate([-lip - clear, -1, -1]) cube([t + lip + 2 * clear, L + 2, hook_w + 1.4]);
    }
}
module test_board() {
    difference() { cube([25, 30, pcb_t]); translate([6, 6, -1]) cylinder(d = 2.7, h = 5); translate([19, 24, -1]) cylinder(d = 2.2, h = 5); }
}
module pieces() {
    translate([0, 0, 0]) tongue();
    for (i = [0 : 2]) {
        translate([30 + i * 34, 10, 0]) hook_piece(hooks[i]);
        translate([30 + i * 34, 26, 0]) hook_block(hooks[i]);
        translate([34 + i * 34, 2, hook_w - 0.5]) linear_extrude(0.51) text(fmt(hooks[i]), size = 3, halign = "center", font = "Liberation Sans:style=Bold");
    }
    translate([0, 40, 0]) rotate([0, 0, 0]) translate([0, 0, lid_t]) chan_lid(40, label = "E");
    translate([30, 44, 0]) test_board();
}

if (part == "plate" || part == "all") plate();
if (part == "pieces" || part == "all") translate([0, D + 10, 0]) pieces();
