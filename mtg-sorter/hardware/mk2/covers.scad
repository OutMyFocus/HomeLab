// Sorter Mk2 covers: everything that closes the machine, all dropped or slid in, nothing screwed.
//
//   front_cover   over the scan module, between level 1's fascia and the lid. It drops into the
//                 walls' front grooves from the top (lid off first), flush with the fascias, and
//                 keeps room light off the scan bed (the camera works best in the dark).
//   back_low,     the back above the electronics tray, in two panels that drop into the walls'
//   back_high     back grooves; the upper one lifts out to slide the feeder cartridge out.
//   lid_front,    the top, in two halves on the walls' ledge, held by magnets. The back half has
//   lid_back      the magazine's opening: load cards from the top, lift the shoe out the same way.
//   drawer        the bay under level 2, between bins 3 and 4: a drawer on the base's two front
//                 rails for spare pins, magnets, coins and test cards. Same handle as the bins.
include <joints.scad>
include <layout.scad>
use <feeder.scad>
part = "covers";

in_groove = 4.3 - fit_slide;           // the walls' grooves and ledge are 4.3 deep
cov_half = wall_in + in_groove;        // 116: panels' half-width, into the grooves
face_half = wall_in - reveal / 2;      // between the walls

// ---- front cover ---------------------------------------------------------------------------
fc_y = [front_y + reveal / 2, front_y + 6];   // its face is flush with the fascias ...
fc_groove = [front_y + 3, front_y + 6];       // ... its edges in the walls' grooves are 3 thick
module front_cover() {
    z0 = fcover_z + reveal / 2;  z1 = top_z - 0.01;
    difference() {
        union() {
            translate([-face_half, fc_y[0], z0]) ccube([2 * face_half, fc_y[1] - fit_slide / 2 - fc_y[0], z1 - z0]);   // full depth between the walls
            translate([-cov_half, fc_groove[0] + fit_slide / 2, z0]) cube([2 * cov_half, 3 - fit_slide, z1 - z0]);
        }
        // a finger notch at the top to lift it out, and a reveal line where it meets level 1
        translate([0, front_y - 1, z1]) rotate([-90, 0, 0]) scale([1, 0.6, 1]) cylinder(d = 40, h = 4, $fn = 64);
        translate([-face_half - 1, front_y - 0.01, z0 + 30]) cube([2 * face_half + 2, 0.6, 0.5]);
    }
}

// ---- back panels ---------------------------------------------------------------------------
back_split = 330;
bk_y = [back_in + fit_slide / 2, back_y - fit_slide / 2];
module back_panel(z0, z1, tongue) {
    difference() {
        union() {
            translate([-cov_half, bk_y[1] - 2, z0]) cube([2 * cov_half, 2, z1 - z0]);              // outside skin
            difference() {                                                                          // rim
                translate([-cov_half, bk_y[0], z0]) cube([2 * cov_half, bk_y[1] - bk_y[0], z1 - z0]);
                translate([-cov_half + 10, bk_y[0] - 1, z0 + 10]) cube([2 * cov_half - 20, bk_y[1] - bk_y[0] - 1, z1 - z0 - 20]);
            }
            for (x = [-60, 0, 60]) translate([x - 2, bk_y[0], z0]) cube([4, bk_y[1] - bk_y[0], z1 - z0]);   // ribs
            for (z = [z0 + (z1 - z0) / 3, z0 + 2 * (z1 - z0) / 3]) translate([-cov_half, bk_y[0], z - 2]) cube([2 * cov_half, bk_y[1] - bk_y[0], 4]);
            // the lower panel's tongue fits the upper's groove
            if (tongue) translate([-cov_half + 12, bk_y[0] + 2, z1 - 0.01]) cube([2 * cov_half - 24, 2, 4]);
        }
        if (!tongue) translate([-cov_half + 12 - fit_slide, bk_y[0] + 2 - fit_slide, z0 - 0.01]) cube([2 * cov_half - 24 + 2 * fit_slide, 2 + 2 * fit_slide, 4.4]);
        // finger notch at the top
        translate([0, bk_y[1] + 1, z1]) rotate([90, 0, 0]) scale([1, 0.6, 1]) cylinder(d = 40, h = 3.01, $fn = 64);
    }
}
module back_low() back_panel(back_up_z + reveal / 2, back_split, true);
module back_high() back_panel(back_split, top_z - 0.01, false);

// ---- lid -----------------------------------------------------------------------------------
lid_y = [fc_y[1] + fit_slide, back_in - fit_slide];
lid_t = 4;
lid_split = seam_y;
lid_mags = [-30, 40, 150, 215];          // magnets in the walls' ledge, under the lid's edges
mag_x = wall_in + 2.15;
hop_open = [37, 131];                    // the magazine's opening: x +-37, from y 131 to the back
module lid_half(front) {
    y0 = front ? lid_y[0] : lid_split - 5;
    y1 = front ? lid_split + 5 : lid_y[1];
    difference() {
        translate([-cov_half, y0, top_z - lid_t]) cube([2 * cov_half, y1 - y0, lid_t]);
        // the half lap where the halves meet: the front half on top over the back half's step
        if (front) translate([-cov_half - 1, lid_split - 5, top_z - lid_t - 0.01]) cube([2 * cov_half + 2, 10.01, lid_t / 2 + 0.01 + fit_snug]);
        else translate([-cov_half - 1, lid_split - 5 - 0.01, top_z - lid_t / 2 - fit_snug]) cube([2 * cov_half + 2, 10.01, lid_t]);
        // magnets
        for (y = lid_mags) if ((y < lid_split) == front) for (s = [-1, 1]) translate([s * mag_x, y, top_z - lid_t - 0.01]) magnet_cut();
        // the magazine's opening
        if (!front) translate([-hop_open[0], hop_open[1], top_z - lid_t - 1]) cube([2 * hop_open[0], 200, lid_t + 2]);
        // shallow grip recess near the front edge of each half
        translate([0, front ? y0 + 14 : lid_split + 22, top_z + 0.01]) scale([1, 0.4, 1]) mirror([0, 0, 1]) cylinder(d1 = 60, d2 = 54, h = 1.6, $fn = 64);
    }
}
module lid_front() lid_half(true);
module lid_back() lid_half(false);

// ---- drawer --------------------------------------------------------------------------------
pbay_x = 18;
dr_half = 26.3 - reveal / 2;             // between bins 3 and 4's front plates
dr_y = [front_y + reveal / 2, 56];
dr_z = [base_top, lv2_z - 3 - reveal];   // 6 .. 158.5, under level 2's floor
dr_wall = 2;
module drawer() {
    difference() {
        union() {
            translate([-dr_half, dr_y[0], dr_z[0]]) ccube([2 * dr_half, dr_y[1] - dr_y[0], dr_z[1] - dr_z[0]]);
        }
        // the box inside, open at the top behind the front plate
        translate([-dr_half + dr_wall, dr_y[0] + 4, dr_z[0] + 3]) cube([2 * dr_half - 2 * dr_wall, dr_y[1] - dr_y[0] - 4 - dr_wall, 300]);
        // its front plate stays full height; the box's sides drop to 120 so you can reach in
        translate([-dr_half - 1, dr_y[0] + 30, 120]) cube([2 * dr_half + 2, dr_y[1] - dr_y[0], 100]);
        // the same rounded slot handle as the bins
        hull() for (x = [-12, 12]) translate([x, front_y - 1, dr_z[1] - 22]) rotate([-90, 0, 0]) cylinder(d = 18, h = 5, $fn = 48);
        translate([-20, front_y + reveal / 2 - 0.01, 60]) cube([40, 0.8, 16]);   // label recess
        // grooves for the base's front rails, and a magnet at the back
        for (s = [-1, 1]) translate([s * pbay_x, dr_y[0] - 1, dr_z[0]]) dove_slot_cut(dr_y[1] - dr_y[0] + 2, 3, 2);
        translate([0, dr_y[1] - 8, dr_z[0] - 0.01]) magnet_cut();
    }
}

module covers() {
    color("#2b2b2b") { front_cover(); back_low(); back_high(); lid_front(); lid_back(); }
    color("#e8e8e8") drawer();
}
if (part == "covers") covers();
if (part == "front_cover") front_cover();
if (part == "back_low") back_low();
if (part == "back_high") back_high();
if (part == "lid_front") lid_front();
if (part == "lid_back") lid_back();
if (part == "drawer") drawer();
