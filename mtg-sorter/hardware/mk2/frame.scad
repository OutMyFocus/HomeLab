// Sorter Mk2 frame: side walls, base, bin dividers, bins.
//
// How it goes together (no screws, no glue):
//   1. The four base tiles lie on the table; bowtie keys drop into the sockets across their seams
//      and 3 mm steel pins line the seams up.
//   2. Each side wall (two lower tiles, two upper tiles, joined the same way) slides onto the base's
//      outer rails from the front. The dovetail holds the wall upright and holds the base together.
//   3. The two dividers slide onto their base rails from the front.
//   4. The bins slide in between the dividers and walls and click onto their magnets.
//   5. Modules slide onto the walls' inner rails (sort and scan from the front, feeder from the back);
//      the electronics tray slides in from the back on its base rails.
//
// Parts (set `part`): wall_r_fl, wall_r_bl, wall_r_fu, wall_r_bu (right wall: front/back, lower/upper)
// and the same with wall_l_ (mirror images), base_fl, base_fr, base_bl, base_br, divider (x2),
// bin (x3), key, chan_lid_*. "frame" shows the assembled frame.
include <joints.scad>
include <layout.scad>
part = "frame";

// ---- small dovetails for thin parts (dividers): 3 wide, 2 tall ------------------------------
sdove_w = 3;  sdove_h = 2;

// ================================ SIDE WALLS ================================================
// Drawn for the right wall (x from wall_in to wall_out); the left wall is its mirror image.
// Seen from inside (looking at the inner face) the wall is a plate in (y, z).
rim = 8;                       // full-thickness rim round each tile
rib = 14;                      // full-thickness strips behind each rail
chan_y = 62;                   // the wall's cable trunk (vertical), y centre
chan_z = [etray_z1 - 20, 352]; // from the electronics tray up past the feeder rail
beam_y_wall = -8;              // full-bin beam (bin on this side), y

module wall_blank() {
    // full-thickness solid where it carries load, skin elsewhere
    y0 = front_y;  y1 = back_y;  z0 = wall_z0;  z1 = top_z;
    translate([wall_out - wall_skin, y0, z0]) cube([wall_skin, y1 - y0, z1 - z0]);   // the outside skin
    intersection() {
        translate([wall_in, y0, z0]) cube([wall_t, y1 - y0, z1 - z0]);
        union() {
            // rims of every tile (so the seams are full thickness)
            for (yy = [[y0, seam_y], [seam_y, y1]]) for (zz = [[z0, seam_z], [seam_z, z1]]) difference() {
                translate([wall_in - 1, yy[0], zz[0]]) cube([wall_t + 2, yy[1] - yy[0], zz[1] - zz[0]]);
                translate([wall_in - 2, yy[0] + rim, zz[0] + rim]) cube([wall_t + 4, yy[1] - yy[0] - 2 * rim, zz[1] - zz[0] - 2 * rim]);
            }
            // strips behind the rails
            for (r = rails) translate([wall_in - 1, y0, r[0] - rib / 2]) cube([wall_t + 2, y1 - y0, rib]);
            // the cable trunk's rib, the back panels' grooves, the bin beam boss
            translate([wall_in - 1, chan_y - 9, z0]) cube([wall_t + 2, 18, z1 - z0]);
            translate([wall_in - 1, back_in - 10, z0]) cube([wall_t + 2, 10 + back_t, z1 - z0]);
            translate([wall_in - 1, front_y, z0]) cube([wall_t + 2, 14, z1 - z0]);
            translate([wall_in - 1, beam_y_wall - 8, beam_z - 8]) cube([wall_t + 2, 16, 16]);
            // a diagonal brace in each lower tile, between the rails
            for (yy = [[y0, seam_y], [seam_y, y1]]) hull() {
                translate([wall_in - 1, yy[0] + rim, z0 + 40]) cube([wall_t + 2, 8, 8]);
                translate([wall_in - 1, yy[1] - rim - 8, rail_sort[0] - 20]) cube([wall_t + 2, 8, 8]);
            }
        }
    }
}

// Helpers that turn the joint library's shapes (drawn into -z or +z from z = 0) into shapes cut
// into the wall's inner face (x = wall_in, depth towards +x).
module into_face_run_y() multmatrix([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]]) children();   // local z -> +x, y stays
module into_face_run_z() multmatrix([[0, 0, -1, 0], [-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]]) children();  // local -z -> +x, y -> z
module key_across_y() multmatrix([[0, 0, -1, 0], [1, 0, 0, 0], [0, -1, 0, 0], [0, 0, 0, 1]]) children();     // key's long axis along y
module key_across_z() multmatrix([[0, 0, -1, 0], [0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 1]]) children();      // ... along z

module wall_cuts() {
    // module rails: grooves in the inner face, open at the end the module comes in from
    for (r = rails) translate([wall_in, r[1] - 0.01, r[0]]) into_face_run_y() dove_slot_cut(r[2] - r[1] + 0.02);
    // back panels: plain grooves, they drop in from the top
    translate([wall_in - 0.01, back_in - 0.3, back_up_z]) cube([4.3, back_t + 0.6, top_z]);
    // magnets that hold the electronics tray shut (its back plate's edges)
    for (z = [base_top + 20, etray_z1 - 16]) translate([wall_in - 0.01, back_in + back_t / 2, z]) rotate([0, 90, 0]) magnet_cut();
    // the front top cover: same, at the front
    translate([wall_in - 0.01, front_y + 3 - 0.3, sort_top_z]) cube([4.3, 3 + 0.6, top_z]);
    // magnets that hold the sort deck's fascia shut
    translate([wall_in - 0.01, front_y + 5, pivot_z]) rotate([0, 90, 0]) magnet_cut();
    // the lid: a 4 mm ledge round the top
    translate([wall_in - 0.01, front_y + 6, top_z - 4]) cube([4.3, back_in - front_y - 6, 5]);
    // cable trunk: channel in the inner face with a flush snap lid
    translate([wall_in, chan_y, chan_z[0]]) into_face_run_z() chan_cut(chan_z[1] - chan_z[0]);
    // full-bin beam: 5 mm sensor pocket, 8 deep, wires out through a groove to the trunk
    translate([wall_in - 0.01, beam_y_wall, beam_z]) rotate([0, 90, 0]) cylinder(d = 5.3, h = 8, $fn = 32);
    translate([wall_in - 0.01, beam_y_wall, beam_z]) rotate([0, 90, 0]) cylinder(d = 6.2, h = 1.2, $fn = 32);
    translate([wall_in - 0.01, beam_y_wall, beam_z - 1.5]) cube([3, chan_y - beam_y_wall, 3]);
    // tile seams: pin holes (3 mm steel, pressed) across each seam, sideways in the rims
    for (z = [base_top + 30, seam_z - 30, seam_z + 30, top_z - 30]) translate([wall_in + wall_t / 2, seam_y - 8, z]) rotate([-90, 0, 0]) pin_press_cut(16);
    for (y = [front_y + 30, seam_y - 30, seam_y + 30, back_y - 40]) translate([wall_in + wall_t / 2, y, seam_z - 8]) pin_press_cut(16);
    // bowtie keys on the inner face across each seam
    for (z = [base_top + 60, seam_z - 60, seam_z + 60, top_z - 60]) translate([wall_in, seam_y, z]) key_across_y() key_socket_cut();
    for (y = [front_y + 40, seam_y - 40, seam_y + 40, back_in - 40]) translate([wall_in, y, seam_z]) key_across_z() key_socket_cut();
    // the even shadow line on the outside where the tiles meet
    translate([wall_out - reveal, seam_y - reveal / 2, base_top - 1]) cube([1, reveal, top_z]);
    translate([wall_out - reveal, front_y - 1, seam_z - reveal / 2]) cube([1, back_y - front_y + 2, reveal]);
}

module wall_r() difference() { wall_blank(); wall_cuts(); }
module wall_l() mirror([1, 0, 0]) wall_r();

// tiles: [name, y range, z range]
tiles = [["fl", [front_y, seam_y], [0, seam_z]], ["bl", [seam_y, back_y + 1], [0, seam_z]],
         ["fu", [front_y, seam_y], [seam_z, top_z + 1]], ["bu", [seam_y, back_y + 1], [seam_z, top_z + 1]]];
module wall_tile(side, t) {
    intersection() {
        if (side == "r") wall_r(); else wall_l();
        translate([-200, t[1][0], t[2][0]]) cube([400, t[1][1] - t[1][0], t[2][1] - t[2][0]]);
    }
}


// ================================ BASE ======================================================
// Four tiles (front/back x left/right). The walls stand in the rebate along the outer edges; the
// dividers and the electronics tray slide onto rails on top; each bin clicks onto a magnet and a
// hall sensor reads a second magnet in it (bin present). Wires run in grooves underneath.
etray_rail_x = 60;
bin_mag = [12, 38];            // bin magnets at (bin centre +- 12, 38): + = detent, - = sensed
module base_full() {
    difference() {
        union() {
            translate([-wall_out, front_y, 0]) ccube([2 * wall_out, back_y - front_y, base_t]);
            for (s = [-1, 1]) translate([s * (bin_pitch / 2), front_y, base_top - 0.01]) dove_rail(divider_y1 - front_y, sdove_w, sdove_h);
            for (s = [-1, 1]) translate([s * etray_rail_x, etray_y0, base_top - 0.01]) dove_rail(back_y - etray_y0, sdove_w, sdove_h);
        }
        // the walls' rebate
        for (s = [-1, 1]) translate([s > 0 ? wall_in - fit_slide : -wall_out - 1, front_y - 1, wall_z0]) cube([wall_t + 1 + fit_slide, back_y - front_y + 2, 10]);
        // bin magnets and hall sensors (A3144, TO-92 face up, 1 mm of plastic over it)
        for (b = [-1, 0, 1]) {
            translate([b * bin_pitch + bin_mag[0], bin_mag[1], base_top - mag_pocket_h]) magnet_cut();
            translate([b * bin_pitch - bin_mag[0] - 2.4, bin_mag[1] - 1.8, -0.01]) cube([4.8, 3.6, base_t - 1]);
            // its wires: a groove underneath, back to the electronics tray, then up through a hole
            translate([b * bin_pitch - bin_mag[0] - 1.5, bin_mag[1], -0.01]) cube([3, etray_y0 + 6 - bin_mag[1], 2]);
            translate([b * bin_pitch - bin_mag[0], etray_y0 + 6, -1]) cylinder(d = 4, h = base_t + 2);
        }
        // the dividers' beam wires come down the dividers' back edges and go through here
        for (s = [-1, 1]) translate([s * (bin_pitch / 2) + s * 3, divider_y1 + 0.5, -1]) cylinder(d = 4, h = base_t + 2);
        // stick-on rubber feet (12 mm), 1 mm recesses
        for (x = [-wall_out + 14, -14, 14, wall_out - 14]) for (y = [front_y + 14, base_seam_y - 14, base_seam_y + 14, back_y - 14])
            translate([x, y, -0.01]) cylinder(d = 12.6, h = 1);
        // seams: bowtie keys on top (under the bins and tray), pins along the seams
        for (y = [front_y + 30, 20, 120, back_y - 30]) translate([0, y, base_top]) rotate([0, 0, 0]) key_socket_cut();
        for (x = [-100, -22, 22, 100]) translate([x, base_seam_y, base_top]) rotate([0, 0, 90]) key_socket_cut();
        for (y = [front_y + 50, 60, 150]) translate([-8, y, base_t / 2]) rotate([0, 90, 0]) pin_press_cut(16);
        for (x = [-70, 70]) translate([x, base_seam_y - 8, base_t / 2]) rotate([-90, 0, 0]) pin_press_cut(16);
    }
}
base_tiles = [["fl", [-wall_out - 1, 0], [front_y - 1, base_seam_y]], ["fr", [0, wall_out + 1], [front_y - 1, base_seam_y]],
              ["bl", [-wall_out - 1, 0], [base_seam_y, back_y + 1]], ["br", [0, wall_out + 1], [base_seam_y, back_y + 1]]];
module base_tile(t) intersection() { base_full(); translate([t[1][0], t[2][0], -1]) cube([t[1][1] - t[1][0], t[2][1] - t[2][0], 20]); }

// ================================ DIVIDERS ==================================================
// Between the bins, at x = +-41. Each carries one full-bin beam receiver (its +x face) and one
// emitter (its -x face), in 5 mm through holes; the wires run in a groove on the other face to
// the back edge and down it to the base. Drawn for the right divider (x = +41).
div_beam = [[-8, 1], [8, -1]];     // right divider: receiver at y -8 (faces +x), emitter at y +8 (faces -x)
module divider(right = true) {
    xc = bin_pitch / 2;  t = divider_t;
    beams = right ? div_beam : [[8, 1], [-8, -1]];
    difference() {
        translate([xc - t / 2, front_y, base_top]) ccube([t, divider_y1 - front_y, bin_top - base_top]);
        translate([xc, front_y - 1, base_top]) dove_slot_cut(divider_y1 - front_y + 2, sdove_w, sdove_h);
        for (b = beams) {
            translate([xc - t, b[0], beam_z]) rotate([0, 90, 0]) cylinder(d = 5.3, h = 2 * t, $fn = 32);
            // the 5.8 mm flange sits in a counterbore on the face the sensor looks out of
            translate([xc + b[1] * (t / 2 - 1.2) - (b[1] > 0 ? 0 : 0.01), b[0], beam_z]) rotate([0, b[1] > 0 ? 90 : -90, 0]) cylinder(d = 6.2, h = 1.3, $fn = 32);
            // wire groove on the other face: along y to the back edge, then down it
            translate([xc - b[1] * t / 2 - (b[1] > 0 ? 0.01 : 2.5 - 0.01), b[0], beam_z - 1.25]) cube([2.51, divider_y1 - b[0] + 1, 2.5]);
        }
        translate([xc - 1.5, divider_y1 - 2.5, base_top - 1]) cube([3, 2.6, beam_z - base_top + 3]);
    }
}

// ================================ BINS ======================================================
// Three identical bins: any bin goes in any slot. Each is a card-sized shaft (68 x 94 inside,
// 177 deep, about 475 cards) with a display pocket at the front for a toploader, a finger notch,
// two 5 mm windows each side for the full-bin beams, and two magnets underneath.
bin_front_t = 3;
module bin() {
    xo = bin_out_x / 2;  z0 = base_top;  zt = bin_top;
    difference() {
        union() {
            translate([-xo, bin_y0 - bin_wall, z0]) ccube([bin_out_x, bin_back - bin_y0 + bin_wall, zt - z0]);
            // the display pocket and front plate (flush with the frame's front)
            translate([-xo, front_y + reveal / 2, z0]) ccube([bin_out_x, bin_y0 - bin_wall - front_y - reveal / 2 + 0.01, zt - z0]);
        }
        // the card shaft
        translate([-bin_in[0] / 2, bin_y0, z0 + bin_floor]) cube([bin_in[0], bin_in[1], zt]);
        // display pocket for a toploader (77 x 101 x 2.5 fits in 69 x 175 with its top showing)
        translate([-xo + 1.5, front_y + reveal / 2 + bin_front_t, z0 + bin_floor]) cube([bin_out_x - 3, bin_y0 - bin_wall - front_y - reveal / 2 - bin_front_t, zt]);
        // window in the front plate
        translate([-xo + 7, front_y - 1, z0 + 22]) cube([bin_out_x - 14, bin_front_t + 2, zt - z0 - 52]);
        // finger notch at the top of the front plate
        translate([0, front_y - 1, zt]) rotate([-90, 0, 0]) cylinder(d = 26, h = bin_y0 - front_y, $fn = 48);
        // full-bin beam windows, both sides, at y -8 and +8
        for (s = [-1, 1]) for (y = [-8, 8]) translate([s * (xo - bin_wall - 0.01) - (s > 0 ? 0 : bin_wall + 0.02) + 0, y, beam_z]) rotate([0, 90, 0]) cylinder(d = 5, h = bin_wall + 0.04, $fn = 24);
        // magnets underneath
        for (s = [-1, 1]) translate([s * bin_mag[0], bin_mag[1], z0 - 0.01]) magnet_cut();
    }
}

// ================================ CABLE TRUNK LIDS ==========================================
module trunk_lid(label) chan_lid((chan_z[1] - chan_z[0]) / 2 - 0.5, label = label);

// ================================ ASSEMBLY ===================================================
module frame_assembly() {
    color("#2b2b2b") { wall_r(); wall_l(); }
    color("#3a3f47") base_full();
    color("#4a4f57") { divider(true); mirror([1, 0, 0]) divider(true); }
    for (b = [-1, 0, 1]) color("#5a6068") translate([b * bin_pitch, 0, 0]) bin();
}

if (part == "frame") frame_assembly();
if (part == "wall_r") wall_r();
if (part == "base") base_full();
if (part == "divider") divider(true);
if (part == "bin") bin();
