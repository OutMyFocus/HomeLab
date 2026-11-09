// Sorter Mk2 frame: side walls, base, bins.
//
// How it goes together (no screws, no glue: everything slides, keys or clicks into place):
//   1. The four base tiles lie on the table; bowtie keys drop into the sockets across their seams
//      and 3 mm steel pins line the seams up.
//   2. Each side wall (2 x 3 tiles, joined the same way) slides onto the base's outer rebate from
//      the front. The base's rebate and the modules' dovetails hold the walls square.
//   3. Level 2 (with its two shelves) slides in from the front on the lowest rail, level 1 on the
//      next, then the scan module; the feeder slides in from the back on the top rail. A magnet at
//      the end of each rail holds each module home.
//   4. The bins slide in from the front, onto the base (bins 3, 4) or level 2's shelves (bins 1,
//      2), and click onto their magnets.
//
// Parts (set `part`): wall_r, wall_l (cut into 6 tiles each by wall_tile), base (4 tiles), bin (x4).
include <joints.scad>
include <layout.scad>
part = "frame";

// ================================ SIDE WALLS ================================================
// Drawn for the right wall (x from wall_in to wall_out); the left wall is its mirror image.
rim = 8;                       // full-thickness rim round each tile
rib = 14;                      // full-thickness strips behind each rail
chan_z = [etray_z1 - 20, top_z - 40];
zrows = [[wall_z0, seam_z[0]], [seam_z[0], seam_z[1]], [seam_z[1], top_z]];
ycols = [[front_y, seam_y], [seam_y, back_y]];

module wall_blank() {
    y0 = front_y;  y1 = back_y;  z0 = wall_z0;  z1 = top_z;
    translate([wall_out - wall_skin, y0, z0]) cube([wall_skin, y1 - y0, z1 - z0]);   // the outside skin
    intersection() {
        translate([wall_in, y0, z0]) cube([wall_t, y1 - y0, z1 - z0]);
        union() {
            for (yy = ycols) for (zz = zrows) difference() {
                translate([wall_in - 1, yy[0], zz[0]]) cube([wall_t + 2, yy[1] - yy[0], zz[1] - zz[0]]);
                translate([wall_in - 2, yy[0] + rim, zz[0] + rim]) cube([wall_t + 4, yy[1] - yy[0] - 2 * rim, zz[1] - zz[0] - 2 * rim]);
            }
            for (r = rails) translate([wall_in - 1, y0, r[0] - rib / 2]) cube([wall_t + 2, y1 - y0, rib]);
            translate([wall_in - 1, chan_y - 9, z0]) cube([wall_t + 2, 18, z1 - z0]);
            translate([wall_in - 1, back_in - 10, z0]) cube([wall_t + 2, 10 + back_t, z1 - z0]);
            translate([wall_in - 1, front_y, z0]) cube([wall_t + 2, 14, z1 - z0]);
            for (yy = ycols) for (zz = zrows) hull() {        // a diagonal brace in each tile
                translate([wall_in - 1, yy[0] + rim, zz[0] + rim]) cube([wall_t + 2, 8, 8]);
                translate([wall_in - 1, yy[1] - rim - 8, zz[1] - rim - 8]) cube([wall_t + 2, 8, 8]);
            }
        }
    }
}

module into_face_run_y() multmatrix([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]]) children();
module into_face_run_z() multmatrix([[0, 0, -1, 0], [-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]]) children();
module key_across_y() multmatrix([[0, 0, -1, 0], [1, 0, 0, 0], [0, -1, 0, 0], [0, 0, 0, 1]]) children();
module key_across_z() multmatrix([[0, 0, -1, 0], [0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 1]]) children();

module wall_cuts() {
    // module rails: dovetail grooves, open at the end the module comes in from; a magnet near the
    // closed end holds the module home (its own magnet sits in the tongue's neck)
    for (r = rails) {
        translate([wall_in, r[1] - 0.01, r[0]]) into_face_run_y() dove_slot_cut(r[2] - r[1] + 0.02);
        translate([wall_in - 0.01, r[1] == front_y ? r[2] - 8 : r[1] + 8, r[0] + dove_w / 2 + 5]) rotate([0, 90, 0]) magnet_cut();
    }
    // back panels: plain grooves, they drop in from the top
    translate([wall_in - 0.01, back_in - 0.3, back_up_z]) cube([4.3, back_t + 0.6, top_z]);
    for (z = [base_top + 20, etray_z1 - 16]) translate([wall_in - 0.01, back_in + back_t / 2, z]) rotate([0, 90, 0]) magnet_cut();
    // the front cover (over the scan module): a groove at the front from fcover_z up
    translate([wall_in - 0.01, front_y + 3 - 0.3, fcover_z]) cube([4.3, 3 + 0.6, top_z]);
    // the lid: a 4 mm ledge round the top
    translate([wall_in - 0.01, front_y + 6, top_z - 4]) cube([4.3, back_in - front_y - 6, 5]);
    // cable trunk with a flush snap lid
    translate([wall_in, chan_y, chan_z[0]]) into_face_run_z() chan_cut(chan_z[1] - chan_z[0]);
    // tile seams: 3 mm steel pins across each seam (in the rims), bowtie keys on the inner face
    for (zz = zrows) for (z = [zz[0] + 30, zz[1] - 30]) translate([wall_in + wall_t / 2, seam_y - 8, z]) rotate([-90, 0, 0]) pin_press_cut(16);
    for (sz = seam_z) for (y = [front_y + 30, seam_y - 30, seam_y + 30, back_y - 40]) translate([wall_in + wall_t / 2, y, sz - 8]) pin_press_cut(16);
    for (zz = zrows) translate([wall_in, seam_y, (zz[0] + zz[1]) / 2]) key_across_y() key_socket_cut();
    for (sz = seam_z) for (y = [front_y + 40, seam_y + 40, back_in - 40]) translate([wall_in, y, sz]) key_across_z() key_socket_cut();
    // the even shadow lines on the outside where the tiles meet
    translate([wall_out - reveal, seam_y - reveal / 2, base_top - 1]) cube([1, reveal, top_z]);
    for (sz = seam_z) translate([wall_out - reveal, front_y - 1, sz - reveal / 2]) cube([1, back_y - front_y + 2, reveal]);
}

module wall_r() difference() { wall_blank(); wall_cuts(); }
module wall_l() mirror([1, 0, 0]) wall_r();
module wall_tile(side, iy, iz) intersection() {
    if (side == "r") wall_r(); else wall_l();
    translate([-200, ycols[iy][0] - (iy == 0 ? 1 : 0), zrows[iz][0] - (iz == 0 ? 1 : 0)]) cube([400, ycols[iy][1] - ycols[iy][0] + 1, zrows[iz][1] - zrows[iz][0] + (iz == 2 ? 1 : 0)]);
}

// ================================ BASE ======================================================
// Four tiles. The walls stand in the rebate along the outer edges. Bins 3 and 4 run on two low
// runners each and click onto a magnet; a hall sensor under 1 mm of plastic reads a second magnet
// in the bin (bin present). The power bay (middle, front) and the electronics tray (back) run on rails.
bin_mag = [14, 30];            // bin magnets at (bin centre +- 14, 30): + = detent, - = sensed
runner = [3, 2];               // the bins' runner rails: 3 wide, 2 tall
runner_x = 22;                 // at bin centre +- 22
etray_rail_x = 60;
pbay_x = 18;                   // the power bay's rails
module bin_seat(zt) {          // the runners a bin stands on (zt = the seat's top)
    for (s = [-1, 1]) translate([s * runner_x - runner[0] / 2, front_y + 8, zt - 0.01]) ccube([runner[0], bin_back - front_y - 10, runner[1]], 0.3);
}
module bin_seat_cut(zt, below) {
    translate([bin_mag[0], bin_mag[1], zt - mag_pocket_h]) magnet_cut();
    translate([-bin_mag[0] - 2.4, bin_mag[1] - 1.8, zt - below - 0.01]) cube([4.8, 3.6, below - 1]);
}
module base_full() {
    difference() {
        union() {
            translate([-wall_out, front_y, 0]) ccube([2 * wall_out, back_y - front_y, base_t]);
            for (s = [-1, 1]) translate([s * bin_x, 0, 0]) bin_seat(base_top);
            for (s = [-1, 1]) translate([s * etray_rail_x, etray_y0, base_top - 0.01]) dove_rail(back_y - etray_y0, 3, 2);
            for (s = [-1, 1]) translate([s * pbay_x, front_y + 4, base_top - 0.01]) dove_rail(etray_y0 - front_y - 6, 3, 2);
        }
        for (s = [-1, 1]) translate([s > 0 ? wall_in - fit_slide : -wall_out - 1, front_y - 1, wall_z0]) cube([wall_t + 1 + fit_slide, back_y - front_y + 2, 10]);
        for (s = [-1, 1]) translate([s * bin_x, 0, 0]) {
            bin_seat_cut(base_top, base_t);
            // hall wires: a groove underneath, back to the electronics tray, and up through a hole
            translate([-bin_mag[0] - 1.5, bin_mag[1], -0.01]) cube([3, etray_y0 + 6 - bin_mag[1], 2]);
            translate([-bin_mag[0], etray_y0 + 6, -1]) cylinder(d = 4, h = base_t + 2);
        }
        for (x = [-wall_out + 14, -14, 14, wall_out - 14]) for (y = [front_y + 14, base_seam_y - 14, base_seam_y + 14, back_y - 14])
            translate([x, y, -0.01]) cylinder(d = 12.6, h = 1);
        for (x = [-90, 90]) translate([x, base_seam_y, base_top]) rotate([0, 0, 90]) key_socket_cut();
        for (y = [front_y + 30, base_seam_y + 60, back_y - 30]) translate([0, y, base_top]) key_socket_cut();
        for (y = [front_y + 50, 60, 150]) translate([-8, y, base_t / 2]) rotate([0, 90, 0]) pin_press_cut(16);
        for (x = [-60, 60]) translate([x, base_seam_y - 8, base_t / 2]) rotate([-90, 0, 0]) pin_press_cut(16);
    }
}
base_tiles = [["fl", [-wall_out - 1, 0], [front_y - 1, base_seam_y]], ["fr", [0, wall_out + 1], [front_y - 1, base_seam_y]],
              ["bl", [-wall_out - 1, 0], [base_seam_y, back_y + 1]], ["br", [0, wall_out + 1], [base_seam_y, back_y + 1]]];
module base_tile(t) intersection() { base_full(); translate([t[1][0], t[2][0], -1]) cube([t[1][1] - t[1][0], t[2][1] - t[2][0], 20]); }

// ================================ BINS ======================================================
// Four identical bins: any bin goes in any slot. A card shaft 65 x 91 inside and 150 deep (about
// 400 cards); a front block flush with the machine's face with a pull-and-lift handle (fingers go
// through the slot and hook behind the plate); a hand hold at the back; two runner grooves and two
// magnets underneath; a window in the back wall where the full sensor looks in.
bin_fw = bin_out_x / 2 + 8.2;          // the front plate covers the frame's gaps: x +-42.7 round the bin
bin_fp = 4;                            // front plate thickness
full_z = 14;                           // the full sensor looks in this far below the bin's top
module bin() {
    xo = bin_out_x / 2;  zt = bin_h;
    difference() {
        union() {
            translate([-xo, bin_y0 - bin_wall, 0]) ccube([bin_out_x, bin_back - bin_y0 + bin_wall, zt]);
            translate([-xo, front_y + reveal / 2, 0]) ccube([bin_out_x, bin_y0 - bin_wall - front_y - reveal / 2 + 0.01, zt]);
            translate([-bin_fw + reveal / 2, front_y + reveal / 2, 0]) ccube([2 * bin_fw - reveal, bin_fp, zt - reveal]);
        }
        translate([-bin_in[0] / 2, bin_y0, bin_floor]) cube([bin_in[0], bin_in[1], zt]);
        // a 1.5 mm lead-in round the mouth, so an arriving card never meets a sharp edge
        translate([0, 0, zt - 1.5]) linear_extrude(1.51, scale = [(bin_in[0] + 3) / bin_in[0], (bin_in[1] + 3) / bin_in[1]]) square([bin_in[0], bin_in[1]], center = true);
        translate([-xo + bin_wall, front_y + reveal / 2 + bin_fp, bin_floor]) cube([bin_out_x - 2 * bin_wall, bin_y0 - bin_wall - front_y - reveal / 2 - bin_fp, zt]);
        hull() for (x = [-24, 24]) translate([x, front_y - 1, zt - 22]) rotate([-90, 0, 0]) cylinder(d = 18, h = bin_fp + 2);
        translate([-30, front_y + reveal / 2 - 0.01, 30]) cube([60, 0.8, 20]);
        hull() for (x = [-18, 18]) translate([x, bin_y1 - 1, zt - 10]) rotate([-90, 0, 0]) cylinder(d = 14, h = bin_wall + 2);
        translate([-6, bin_y1 - 1, zt - full_z - 4]) cube([12, bin_wall + 2, 8]);
        for (s = [-1, 1]) translate([s * runner_x - runner[0] / 2 - fit_slide, front_y - 1, -0.01]) cube([runner[0] + 2 * fit_slide, bin_back - front_y + 2, runner[1] + 0.3]);
        for (s = [-1, 1]) translate([s * bin_mag[0], bin_mag[1], -0.01]) magnet_cut();
    }
}
// [x, z of the bin's bottom]: bin 1 left, bin 2 right (on level 2's shelves), bins 3 and 4 on the base.
bin_spots = [[-bin_x, bin1_z], [bin_x, bin1_z], [-bin_x, bin3_z], [bin_x, bin3_z]];
module bin_at(i) translate([bin_spots[i][0], 0, bin_spots[i][1]]) bin();

module trunk_lid(label) chan_lid((chan_z[1] - chan_z[0]) / 3 - 0.5, label = label);

module frame_assembly() {
    color("#2b2b2b") { wall_r(); wall_l(); }
    color("#3a3f47") base_full();
    for (i = [0 : 3]) color("#e8e8e8") bin_at(i);
}

if (part == "frame") frame_assembly();
if (part == "wall_r") wall_r();
if (part == "base") base_full();
if (part == "bin") bin();
