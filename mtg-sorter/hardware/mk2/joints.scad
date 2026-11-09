// Sorter Mk2: the screwless joints every part is built from. Sizes come from fit.scad.
//
// Conventions: each joint is drawn in its own local frame and placed with translate/rotate.
// "Positive" modules add material, "_cut" modules are subtracted from the mating part.
include <fit.scad>

// ---- Dovetail -----------------------------------------------------------------------------
// Profile in the XZ plane: base (z = 0) w wide, flanks lean out at 45 degrees to the top (z = h).
// Rails run along +y. Prints with the rail standing up off the plate: the flanks are 45 degree
// overhangs built from layers, no bridges.
dove_w = 6;  dove_h = 3;
module dove_2d(w = dove_w, h = dove_h, grow = 0) {
    polygon([[-w / 2 - grow, -0.01 - grow], [w / 2 + grow, -0.01 - grow],
             [w / 2 + h + grow, h + grow], [-w / 2 - h - grow, h + grow]]);
}
module dove_rail(len, w = dove_w, h = dove_h) {
    rotate([-90, 0, 0]) mirror([0, 1, 0]) linear_extrude(len) dove_2d(w, h);
}
// The slot it slides in: fit_dove clear on every face, plus a 0.4 mm lead-in at the open end.
module dove_slot_cut(len, w = dove_w, h = dove_h, lead = true, g = fit_dove) {
    rotate([-90, 0, 0]) mirror([0, 1, 0]) translate([0, 0, -0.01]) linear_extrude(len + 0.02) dove_2d(w, h, g);
    if (lead) rotate([-90, 0, 0]) mirror([0, 1, 0]) translate([0, 0, -0.01])
        linear_extrude(1.2, scale = 1) dove_2d(w, h, g + 0.4);
}

// ---- Cantilever snap hook -------------------------------------------------------------------
// Arm stands on z = 0 and rises along +z; it bends in x. The hook at its tip points +x with a
// 30 degree lead-in on top and a square (locking) or 45 degree (pull-apart) back face.
// Print it lying down (the arm along the plate) so it bends along the layers.
module snap_hook(len = hook_len, t = hook_t, w = hook_w, lip = hook_lip, locking = true) {
    back = locking ? 0 : lip;              // 45 degree back face drops lip over lip
    translate([0, -w / 2, 0]) {
        cube([t, w, len]);
        rotate([90, 0, 0]) translate([0, 0, -w]) linear_extrude(w) polygon([
            [t - 0.01, len - 0.01 - back], [t + lip, len], [t + lip, len + 0.6],
            [t - 0.01, len + 0.6 + lip / tan(30)]]);
    }
}
// The window a hook catches in: a slot through a wall of thickness wall_t, the hook's width +
// fit_slide each side. Placed with its catching edge at z = 0.
module hook_window_cut(wall_t, w = hook_w, lip = hook_lip) {
    translate([-0.01, -w / 2 - fit_slide, 0]) cube([wall_t + 0.02, w + 2 * fit_slide, lip + 0.6 + lip / tan(30) + 1]);
}

// ---- Steel pins, magnets ------------------------------------------------------------------
module pin_press_cut(h) { translate([0, 0, -0.01]) cylinder(d = pin_press, h = h + 0.02, $fn = 32); }
module pin_free_cut(h)  { translate([0, 0, -0.01]) cylinder(d = pin_free,  h = h + 0.02, $fn = 32); }
module magnet_cut()     { translate([0, 0, -0.01]) cylinder(d = mag_pocket_d, h = mag_pocket_h + 0.01, $fn = 32); }

// ---- Board pegs -----------------------------------------------------------------------------
// A split peg with a barb: stands on a boss; the board pushes down over the barb and clicks.
// d = the peg size for that board (peg_pi, peg_cam), stand = boss height under the board.
module board_peg(d, stand = 5) {
    boss = d + 3;
    cylinder(d = boss, h = stand);
    difference() {
        union() {
            cylinder(d = d, h = stand + pcb_t + 0.2);
            translate([0, 0, stand + pcb_t + 0.2]) cylinder(d1 = d + 2 * peg_barb, d2 = d - 0.6, h = 1.6);
        }
        translate([-0.4, -d, stand + 1]) cube([0.8, 2 * d, pcb_t + 3]);   // the split lets the barb squeeze
    }
}
// Card-guide grooves for a small board: a pair of rails, the board slides in edge first.
module card_guides(len, board_w, rail_h = 4, rail_t = 2.4) {
    for (s = [-1, 1]) translate([s * (board_w / 2 + rail_t / 2 + 0.15) - rail_t / 2, 0, 0]) difference() {
        cube([rail_t, len, rail_h]);
        translate([s < 0 ? rail_t - 1.2 : -0.01, -0.01, rail_h - 1.2 - pcb_groove]) cube([1.21, len + 0.02, pcb_groove]);
    }
}

// ---- Cable channel ---------------------------------------------------------------------------
// U channel, inside cw x ch, along +y, its open top at z = 0 (sunk into a wall). The lid drops
// in flush: a 1.2 mm step each side and two bumps that click under the step.
chan_w = 10;  chan_d = 8;  lid_t = 1.6;
module chan_cut(len, cw = chan_w, cd = chan_d) {
    translate([-cw / 2, -0.01, -cd]) cube([cw, len + 0.02, cd + 0.01]);
    translate([-cw / 2 - 1.2 - fit_slide, -0.01, -lid_t]) cube([cw + 2.4 + 2 * fit_slide, len + 0.02, lid_t + 0.01]);
    // the groove the lid's bumps click into
    for (s = [-1, 1]) translate([s * (cw / 2 + 0.6), -0.01, -lid_t - 0.6]) rotate([-90, 0, 0]) cylinder(d = 1.0, h = len + 0.02, $fn = 12);
}
// notches = true: a wire entry every 30 mm along one long edge (between the click bumps), so a
// module's wires drop into the channel there and the lid still lies flush.
module chan_lid(len, cw = chan_w, label = "", notches = false) {
    w = cw + 2.4;
    difference() {
        union() {
            translate([-w / 2, 0, -lid_t]) cube([w, len, lid_t]);
            for (s = [-1, 1]) for (y = [6 : 30 : len - 6]) translate([s * (cw / 2 + 0.4), y, -lid_t - 0.3]) rotate([-90, 0, 0]) cylinder(d = 0.8, h = 8, $fn = 12);
        }
        if (label != "") translate([0, len / 2, -0.4]) linear_extrude(0.41) text(label, size = 5, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
        if (notches) for (y = [21 : 30 : len - 11]) translate([-w / 2 - 0.01, y, -lid_t - 1]) cube([w / 2 - 1.7 + 0.01, 8, lid_t + 2]);
    }
}
// Comb: a strain-relief clip that holds n wires of diameter wd where they leave a module.
module wire_comb(n, wd = 1.6, h = 6) {
    pitch = wd + 1.2;
    difference() {
        translate([-(n * pitch + 2) / 2, 0, 0]) cube([n * pitch + 2, 4, h]);
        for (i = [0 : n - 1]) translate([-(n - 1) * pitch / 2 + i * pitch, -0.01, h - wd * 1.6]) {
            translate([0, 0, wd / 2]) rotate([-90, 0, 0]) cylinder(d = wd - 0.15, h = 4.02, $fn = 16);
            translate([-(wd - 0.5) / 2, 0, wd / 2]) cube([wd - 0.5, 4.02, wd * 2]);   // a mouth a little narrower than the wire
        }
    }
}

// ---- Tile joint -----------------------------------------------------------------------------
// Two tiles join along a seam with dovetail keys ("bowties") that drop into matching sockets
// across the seam from the inside face. Socket depth key_t; the key stands flush.
key_l = 18;  key_w0 = 6;  key_w1 = 11;  key_t = 4;
module key_2d(grow = 0) {
    offset(delta = grow) polygon([[-key_l / 2, -key_w1 / 2], [0, -key_w0 / 2], [key_l / 2, -key_w1 / 2],
                                  [key_l / 2, key_w1 / 2], [0, key_w0 / 2], [-key_l / 2, key_w1 / 2]]);
}
module key_socket_cut() { translate([0, 0, -key_t]) linear_extrude(key_t + 0.01) key_2d(fit_snug); }
module key() { linear_extrude(key_t - 0.1) key_2d(0); }

// ---- Edge chamfer helper -----------------------------------------------------------------
// A cube with chamfer on its bottom edges (the face that lies on the build plate).
module ccube(s, c = chamfer) {
    hull() {
        translate([c, c, 0]) cube([s[0] - 2 * c, s[1] - 2 * c, 0.01]);
        translate([0, 0, c]) cube([s[0], s[1], s[2] - c]);
    }
}
