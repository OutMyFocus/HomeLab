// Enclosure: wraps the mechanism from bed_chute.scad in a sleek countertop box,
// Roca-style, with Nic's three storage drawers sliding into a dock at the front.
//
// What changes from the open-frame build (bed_chute.scad on its own):
//   - frame_side, front_bar and bin are not used. The shell replaces them.
//   - the bed side walls no longer stand on the table: they stand on a BRIDGE plate
//     above the drawers (bed_chute.scad: wall_z0), screwed from below through its ears.
//   - the feeder sits on the bridge too, on a shorter stand (feeder_test.scad: stand_h).
//   - the Pi, servo board and motor driver live in a bay at the back, under the bridge.
//
// Layout (x across, y front(-) to back(+), z up, table z = 0), front to back:
//   fascia + three drawers | scan bay under the deck | hopper tower | Pi bay below
//
// Build: a FLOOR plate with grooves and peg holes locates everything. Four CORNER POSTS
// peg into it; the SIDE, FASCIA and BACK panels slide down into the posts' grooves and
// stand in the floor's grooves. The DECK tiles screw onto the posts from above. Two
// DIVIDERS between the drawers carry the bridge. Rubber feet go under the floor.
// Plates too big for the 256 mm bed are split into tiles. Tiles are joined on the
// bench with SPLICE strips that sit in pockets on the underside (M2 screws or glue),
// then the joined plate goes in as one piece.
//
// Printable parts (set `epart`, F6, F7). No supports, 0.2 mm, 15-20% infill:
//   post_front    x2    16 mm quarter-round corner post, prints standing (pegs up); its inner
//                       face is the dock's cheek, the outer drawer plate slides along it
//   post_back     x2    same, with the back panel's groove running the full height
//   side          x4    side panel half (two per side, flip one end for end)
//   fascia_l/m/r        the band above the drawers, three pieces: the seams sit right above the
//                       gaps between the drawer plates. Print it in a lighter colour
//   light_bar           white strip behind the three light slots (LED strip behind it); glued
//                       across the fascia seams, it also ties the three pieces together
//   back_l back_r       back panel halves (l/r as seen from the front), port cut-outs
//   floor_fl floor_fr   floor, front: the drawers slide on it; stop rail at the back
//   floor_bl floor_br   floor, back: Pi bay, with the board standoffs and vent slots
//   deck_fl deck_fr     top deck, front (print upside down, as it opens)
//   deck_bl deck_br     top deck, back: bay opening and hopper well
//   divider       x2    between the drawers, carries the bridge
//   bridge_front bridge_back   the plate the mechanism stands on
//   leg           x2    rear bridge legs
//   splice        x10   strip that joins two tiles
//   tower, tower_lid    hopper shroud
//   post_sleeve, head_cover   camera arm covers
//   "assembly" shows everything (preview only); "shell" just the enclosure parts
//
// Drawers: "Card Catalog v1.2" from MakerWorld, printed from Nic's 3MF (not in this repo).
// Their size is set here, once, in dr_*; card_catalog_drawer.scad only draws one.

include <bed_chute.scad>
part = "none";            // keep bed_chute.scad quiet
show_frame = false;
wall_z0 = 111;            // bed walls start on top of the bridge (= bridge_top below)

epart = "assembly";
show_mech = true;         // draw the mechanism in the assembly preview
show_drawer_out = 60;     // pull the middle drawer out this far in the preview

// --- Drawers: "Card Catalog v1.2" (MakerWorld 3016550), measured from Nic's 3MF -------------
// The drawer is a 76 x 67 x 223 mm tray with an 86 x 109 x 8 mm front plate (the toploader
// pocket), a clip-on bar along the top of the plate and a loop handle 16 mm proud at the
// bottom. In its own box the plates sit side by side at 86.5 mm pitch in an 8 mm deep rebate,
// flush with the box face, and the trays run on the cubby floor. The dock here is three such
// cubbies in a row: the plates fill the front between the two front posts, the trays run
// between guide curbs on the floor, and the fascia starts just above the plates.
dr_w = 76;                // tray outside width
dr_body_h = 67.4;         // tray height
dr_l = 231;               // front face of the plate to the back of the tray (8 + 223)
dr_face_w = 86;  dr_face_h = 109;  dr_face_t = 8;
dr_cap = 4.5;             // room above the plate for its clip-on top bar
dr_pitch = 86.5;          // plate to plate, as in the Card Catalog box (0.5 mm between plates)
dr_clr = 0.5;             // side clearance for the tray between the guide curbs
div_t = 3;                // divider thickness

// --- Shell ------------------------------------------------------------------------
pt = 3;                   // panel thickness
inset = 1.5;              // panels sit this far inside the posts' outer surface
post_r = 16;              // corner post radius (= its size)
groove_d = 6;             // how deep panels go into the posts
floor_t = 4;
deck_t = 4;
deck_z = 212;             // top of the deck
lip_h = 8;                // lip under the deck, just inside the panels
deck_ch = 2;              // chamfer on the deck's top edges
seam_ch = 1;              // small chamfer along every visible seam, so it reads as a panel line
light_slot = [54, 2.2];   // status light slot above each drawer (length, height); 0 length for none
bridge_t = 4;
bridge_top = 111;         // = wall_z0
bridge_half = 52;         // bridge spans x = +-52
front_y = -88;            // outer face of the shell, front
back_y = 268;             // outer face, back

// --- Hopper and feeder (numbers from feeder_test.scad, on the mid stand) ----------------------
feeder_front_y = 150;     // inside face of the hopper's front wall (just behind the bed's back edge)
feeder_out_w = 73;        // hopper outside width
feeder_in_l = 92;
feeder_wall = 3;
feeder_shelf = 30;        // exit shelf in front of the hopper
feeder_floor_z = 206;     // top of the hopper floor
hopper_h = 60;
stand_h = feeder_floor_z - 3 - bridge_top;   // 92: print feeder_stand with stand_h = this

// --- Electronics -----------------------------------------------------------------
pi_pos = [40, 178];       // Pi 5 board corner (x, y). Board is 56 across, 85 deep, ports at the back
pca_pos = [-110, 190];    // PCA9685 board corner, 62 across, 25 deep

// --- Colours -----------------------------------------------------------------------------
c_shell = "#1b1d21";  c_fascia = "#2c3036";  c_inner = "#3a3f47";  c_drawer = ["#e5e2d6", "#2d63b8", "#d8262a"];

$fn = 48;

// ============================ DERIVED ========================================
slot_w = dr_w + 2 * dr_clr;                  // 77: a tray between its guide curbs
pitch = dr_pitch;                            // 86.5
curb_w = pitch - slot_w;                     // 9.5: guide curb on the floor between two trays
curb_h = 3;
dock_w = 3 * pitch;                          // 259.5: the three plates side by side, between the front posts
ow = dock_w + 2 * post_r;                    // shell outside width: the front posts' inner faces flank the plates
hw = ow / 2;
inner_w = ow - 2 * pt - 2 * inset;           // between the side panels' inner faces
panel_top = deck_z - deck_t;                 // top of the posts and panels
post_h = panel_top - floor_t;                // posts and panels stand on the floor plate
div_x = [-pitch, 0, pitch];                  // drawer centres
floor_y0 = front_y + inset + pt;             // inside faces of the fascia and back panel
floor_y1 = back_y - inset - pt;
floor_x = inner_w / 2;
depth = back_y - front_y;  yc = (front_y + back_y) / 2;
dock_y0 = front_y + inset;                   // the plates' front faces, flush with the fascia
dock_y1 = dock_y0 + dr_l + 0.5 + 3;          // back of the dock (drawer stop rail)
dock_wall_y = dock_y0 + dr_face_t + 1;       // behind the plates: curbs, dividers and the bridge start here
floor_seam_y = 152;                          // just behind the stop rail (keeps the front tiles under 250 mm)
bridge_y0 = dock_wall_y;
axle_y = bridge_y0 + 0.5;                    // front face of the chute axle upstand, at the bridge's front edge
bridge_y1 = floor_y1 - 2;
bridge_seam_y = 56;                          // just behind the trapdoor opening
deck_seam_y = 100;
split_x = ow > 250;                          // deck and floor split at x = 0 when too wide
bay_x = side_in + side_t + 1;                // bay opening half width (around the bed walls)
bay_y0 = bed_y - 6;  bay_y1 = bed_back_y + 2;
well_x = feeder_out_w / 2 + 2.5 + 1;         // hopper well half width (tower wall goes in it)
well_y0 = bay_y1;  well_y1 = feeder_front_y + feeder_in_l + feeder_wall + 2.5 + 1;
stand_y0 = feeder_front_y - feeder_shelf - feeder_wall;
stand_l = feeder_shelf + 2 * feeder_wall + feeder_in_l;
hole_d = 2.8;                                // M3 self-tapping
splice_l = 40;  splice_w = 16;  splice_t = 1.5;

module rrect(w, l, r) { offset(r = r) offset(delta = -r) square([w, l], center = true); }

// Pocket for a splice strip, cut into a plate's underside at (x, y), strip running along x or y.
module splice_pocket(x, y, z_under, along_y = true) {
    translate([x, y, z_under - 1]) rotate([0, 0, along_y ? 90 : 0]) {
        translate([0, 0, 0]) linear_extrude(splice_t + 1 + 0.1) square([splice_l + 0.4, splice_w + 0.4], center = true);
        for (dx = [-12, 12], dy = [-4, 4]) translate([dx, dy, 0]) cylinder(d = 1.8, h = splice_t + 1 + 2.2);
    }
}

// A small V along a seam on a plate's top face: half on each tile, so the joint shows
// as a clean line instead of a ragged crack. along_y: the seam runs along y (at x).
module seam_v(x, y, z_top, along_y, len) {
    translate([x, y, z_top]) rotate([0, 0, along_y ? 90 : 0]) rotate([45, 0, 0]) cube([len + 2, seam_ch * 1.414, seam_ch * 1.414], center = true);
}

// ============================ POSTS AND PANELS =====================================

// Corner post, modelled for the front-left corner with the outer corner at the origin.
// front = true: a front post. Its inner face is the dock's cheek and the outer drawer plate slides
// along it, so the fascia groove only starts where the fascia starts.
module post(front = true) {
    g0 = front ? fascia_z0 - floor_t - 2 : -1;
    difference() {
        intersection() {
            translate([post_r, post_r, 0]) cylinder(r = post_r, h = post_h);
            cube([post_r, post_r, post_h]);
        }
        // grooves: front / back panel (along x) and side panel (along y)
        translate([post_r - groove_d, inset, g0]) cube([groove_d + 1, pt + 0.4, post_h + 2]);
        translate([inset, post_r - groove_d, -1]) cube([pt + 0.4, groove_d + 1, post_h + 2]);
        // deck screw
        translate([7, 7, post_h - 10]) cylinder(d = hole_d, h = 11);
    }
    // pegs into the floor plate
    for (q = post_pegs) translate([q[0], q[1], -2.5]) cylinder(d = 3.6, h = 2.5);
}
post_pegs = [[7, 7], [12.5, 12.5]];
module peg_holes(z) {
    for (i = [0 : 3], q = post_pegs) translate([(i % 2 == 0 ? -1 : 1) * (hw - q[0]), (i < 2 ? front_y + q[1] : back_y - q[1]), z]) cylinder(d = 4, h = 3);
}

panel_w = ow - 2 * post_r + 2 * groove_d - 0.6;     // front and back panels, groove to groove
side_len = (back_y - front_y) - 2 * post_r + 2 * groove_d - 0.6;
side_piece = side_len / 2;
fascia_z0 = floor_t + dr_face_h + dr_cap + 0.5;     // bottom edge of the fascia: plate, top bar, a hair of room
fascia_h = panel_top - fascia_z0;

// Panels are modelled lying flat: x along the panel, y up the panel, z = thickness (inside face up).

// Pocket for a splice strip on a panel's inside face, the strip running along x across a seam at x.
// Shallow (1.2 mm) so the panel keeps 1.8 mm: glue these, no screws.
module panel_pocket(x, y) {
    translate([x, y, pt - 1.2]) linear_extrude(2) square([splice_l + 0.4, splice_w + 0.4], center = true);
}

// The fascia is wider than the bed, so it is three pieces whose seams sit right above the gaps
// between the drawer plates: the lines run from the floor to the deck, one bay each. Each bay
// has its own status light slot; one light bar behind all three also ties the pieces together.
fascia_seams = [-pitch / 2, pitch / 2];
light_y = fascia_h - 26;                                 // slots, up the fascia
module fascia_full() {
    difference() {
        translate([-panel_w / 2, 0, 0]) cube([panel_w, fascia_h, pt]);
        if (light_slot[0] > 0) for (x = div_x) translate([x - light_slot[0] / 2, light_y, -1]) cube([light_slot[0], light_slot[1], pt + 2]);
        for (x = fascia_seams) {
            seam_v(x, fascia_h / 2, 0, true, fascia_h);
            for (y = [16, 40]) panel_pocket(x, y);          // the light bar is the third tie, higher up
        }
    }
}
module fascia_tile(i) {   // 0 left, 1 middle, 2 right, seen from the front
    x0 = i == 0 ? -500 : fascia_seams[i - 1];
    x1 = i == 2 ? 500 : fascia_seams[i];
    intersection() { fascia_full(); translate([x0, -50, -50]) cube([x1 - x0, 500, 100]); }
}
// White (or translucent) strip glued behind the three slots, across the seams. Two walls thick, so it glows evenly.
light_bar_l = 2 * pitch + light_slot[0] + 12;
module light_bar() {
    translate([-light_bar_l / 2, 0, 0]) cube([light_bar_l, 12, 1.2]);
}

// The back panel is wider than the bed too: two halves, the seam down the middle between two vent slots.
module back_full() {
    difference() {
        translate([-panel_w / 2, 0, 0]) cube([panel_w, post_h, pt]);
        // Pi ports (USB x4 + ethernet, on the board's short edge)
        translate([pi_pos[0] - 2, 4, -1]) cube([60, 24, pt + 2]);
        // power cables (5 V adapter + Pi USB-C)
        translate([-floor_x + 24, 6, -1]) cube([28, 14, pt + 2]);
        // vent slots behind the Pi bay
        for (i = [0 : 7]) translate([-50 + i * 14, 40, -1]) cube([6, 50, pt + 2]);
        seam_v(0, post_h / 2, 0, true, post_h);
        for (y = [20, 110, 150, post_h - 18]) panel_pocket(0, y);
    }
}
module back_tile(i) {   // 0 left, 1 right, seen from the front
    intersection() { back_full(); translate([i == 0 ? -500 : 0, -50, -50]) cube([500, 500, 100]); }
}

// One half of a side. The pocket for the splice is at the x = side_piece end; flip the
// second piece end for end (pocket still inside).
module side() {
    difference() {
        cube([side_piece, post_h, pt]);
        for (y = [30, post_h / 2, post_h - 30]) translate([side_piece - splice_l / 2, y, pt - 1.2]) rotate([0, 0, 90])
            translate([0, 0, 0]) linear_extrude(2) square([splice_w + 0.4, splice_l + 0.4], center = true);
    }
}

// ============================ FLOOR ==========================================

module floor_full() {
    difference() {
        union() {
            // the base plate: the posts and panels stand on it
            linear_extrude(floor_t) translate([0, yc]) rrect(ow, depth, post_r);
            // drawer stop rail
            translate([-(floor_x - 1), dock_y1 - 3, 0]) cube([2 * (floor_x - 1), 3, floor_t + 10]);
            // guide curbs the trays run between: one under each divider, one along each side
            for (x = [-pitch / 2, pitch / 2]) translate([x - curb_w / 2, dock_wall_y, 0]) cube([curb_w, dock_y1 - 3 - dock_wall_y, floor_t + curb_h]);
            for (m = [0, 1]) mirror([m, 0, 0]) translate([pitch + slot_w / 2, dock_wall_y, 0]) cube([4.5, dock_y1 - 3 - dock_wall_y, floor_t + curb_h]);
            // Pi 5 standoffs: 49 x 58 hole pattern, 3.5 mm in from the board edges
            for (x = [3.5, 52.5], y = [3.5, 61.5]) translate([pi_pos[0] + x, pi_pos[1] + y, 0]) cylinder(d = 6, h = floor_t + 5);
            // PCA9685 standoffs: 56 x 19 pattern
            for (x = [3, 59], y = [3, 22]) translate([pca_pos[0] + x, pca_pos[1] + y, 0]) cylinder(d = 6, h = floor_t + 5);
            // rear bridge legs locate here
            for (x = [-1, 1]) translate([x * (bridge_half - 7), bridge_y1 - 8, 0]) cylinder(d = 14, h = floor_t + 3);
        }
        // grooves the panels stand in, and peg holes for the posts
        translate([0, yc, floor_t - 1.5]) linear_extrude(2) difference() {
            rrect(ow - 2 * inset + 0.4, depth - 2 * inset + 0.4, post_r - inset);
            rrect(ow - 2 * inset - 2 * pt - 0.4, depth - 2 * inset - 2 * pt - 0.4, post_r - inset - pt);
            // no groove under the drawer plates: the fascia stops above them
            translate([-(hw - post_r), front_y - yc - 1]) square([2 * (hw - post_r), inset + pt + 2]);
        }
        peg_holes(floor_t - 2.5);
        // recesses for stick-on rubber feet underneath
        for (x = [-1, 1], y = [front_y + 14, yc, back_y - 14]) translate([x * (hw - 14), y, -1]) cylinder(d = 9, h = 2);
        // vent slots under the Pi bay (air comes in here, out through the back panel)
        for (i = [0 : 6], x = [-1, 1]) translate([x * 60 - 20, 185 + i * 10, -1]) cube([40, 4, floor_t + 2]);
        // seam chamfers, so the seams read as panel lines
        seam_v(0, floor_seam_y, floor_t, false, ow);
        if (split_x) seam_v(0, yc, floor_t, true, depth);
        // divider grooves
        for (x = [-pitch / 2, pitch / 2]) translate([x - (div_t + 0.4) / 2, dock_wall_y - 0.01, floor_t - 2]) cube([div_t + 0.4, dock_y1 - 3 - dock_wall_y + 0.02, 3 + curb_h]);
        // splice pockets along the seams (the middle one is under the middle drawer, flush)
        for (x = [-floor_x + 30, 0, floor_x - 30]) splice_pocket(x, floor_seam_y, 0);
        if (split_x) for (y = [floor_y0 + 40, dock_y1 - 40, floor_y1 - 30]) splice_pocket(0, y, 0, false);
        // standoff screw holes (M2.5 self-tapping)
        for (x = [3.5, 52.5], y = [3.5, 61.5]) translate([pi_pos[0] + x, pi_pos[1] + y, 1]) cylinder(d = 2.2, h = 20);
        for (x = [3, 59], y = [3, 22]) translate([pca_pos[0] + x, pca_pos[1] + y, 1]) cylinder(d = 2.2, h = 20);
        for (x = [-1, 1]) translate([x * (bridge_half - 7), bridge_y1 - 8, floor_t]) cylinder(d = 10.4, h = 10);
        // zip-tie slots for the motor driver and cables
        for (x = [-60, -45], y = [230, 250]) translate([x, y, -1]) cube([4, 2.5, floor_t + 2]);
    }
}

// tile = intersection with a box; xi, yi: 0 = left / front, 1 = right / back
module floor_tile(xi, yi) {
    x0 = split_x ? (xi == 0 ? -500 : 0) : -500;
    x1 = split_x ? (xi == 0 ? 0 : 500) : 500;
    y0 = yi == 0 ? -500 : floor_seam_y;
    y1 = yi == 0 ? floor_seam_y : 500;
    intersection() { floor_full(); translate([x0, y0, -50]) cube([x1 - x0, y1 - y0, 200]); }
}

// ============================ DECK ==========================================

module deck_full() {
    difference() {
        union() {
            // the plate, with rounded corners matching the posts and a chamfer on the top edge
            hull() {
                translate([0, 0, deck_z - deck_t]) linear_extrude(deck_t - deck_ch) translate([0, yc]) rrect(ow, depth, post_r);
                translate([0, 0, deck_z - 0.01]) linear_extrude(0.01) translate([0, yc]) rrect(ow - 2 * deck_ch, depth - 2 * deck_ch, post_r - deck_ch);
            }
            // lip just inside the panels: keeps them straight and locates the deck
            translate([0, 0, deck_z - deck_t - lip_h]) linear_extrude(lip_h + 0.01) difference() {
                translate([0, yc]) rrect(inner_w - 0.8, floor_y1 - floor_y0 - 0.8, 4);
                translate([0, yc]) rrect(inner_w - 0.8 - 2 * pt, floor_y1 - floor_y0 - 0.8 - 2 * pt, 2);
            }
        }
        // scan bay opening (the bed walls rise through it) and the hopper well, chamfered at the top
        for (o = [[-bay_x, bay_y0, 2 * bay_x, bay_y1 - bay_y0], [-well_x, well_y0 - 1, 2 * well_x, well_y1 - well_y0 + 1]]) {
            translate([o[0], o[1], 0]) cube([o[2], o[3], 300]);
            hull() {
                translate([o[0], o[1], deck_z - deck_ch]) cube([o[2], o[3], 0.01]);
                translate([o[0] - deck_ch, o[1] - deck_ch, deck_z]) cube([o[2] + 2 * deck_ch, o[3] + 2 * deck_ch, 0.01]);
            }
        }
        // seam lines
        seam_v(0, deck_seam_y, deck_z, false, ow);
        if (split_x) seam_v(0, yc, deck_z, true, depth);
        // the camera tower post passes through (tilted with the bed)
        on_bed() translate([tower_x - 15, card_s - 15, -4]) cube([30, 30, 200]);
        // post screws, countersunk
        for (x = [-1, 1], y = [front_y + 7, back_y - 7]) translate([x * (hw - 7), y, deck_z - deck_t - 1]) {
            cylinder(d = 3.4, h = 10);
            translate([0, 0, deck_t + 1 - 1.8]) cylinder(d1 = 3.4, d2 = 7, h = 1.8);
        }
        // splice pockets: front / back seam (outside the bay) and the x = 0 seam (front tile only)
        for (x = [-floor_x + 24, floor_x - 24]) splice_pocket(x, deck_seam_y, deck_z - deck_t);
        if (split_x) for (y = [front_y + 36, deck_seam_y - 34]) splice_pocket(0, y, deck_z - deck_t, false);
        // notches in the lip for the cables (LED strips, pin servo) coming up beside the bay
        for (m = [0, 1]) mirror([m, 0, 0]) translate([floor_x - pt - 4, bay_y0, deck_z - deck_t - lip_h - 1]) cube([pt + 6, 14, lip_h + 2]);
    }
}

module deck_tile(xi, yi) {
    x0 = split_x ? (xi == 0 ? -500 : 0) : -500;
    x1 = split_x ? (xi == 0 ? 0 : 500) : 500;
    y0 = yi == 0 ? -500 : deck_seam_y;
    y1 = yi == 0 ? deck_seam_y : 500;
    intersection() { deck_full(); translate([x0, y0, 0]) cube([x1 - x0, y1 - y0, 400]); }
}

// ============================ DOCK ==========================================

div_y0 = dock_wall_y + 0.2;
div_len = dock_y1 - 3 - div_y0 - 0.2;
div_h = bridge_top - bridge_t - floor_t + 2;       // 2 mm sits in the floor groove
flange_w = bridge_half - pitch / 2 - div_t / 2 + div_t;   // reaches out to the bridge's edge
div_holes = [20, div_len / 2, div_len - 20];

// Divider, modelled flat: x along the dock, y up, z = thickness, with the top flange
// reaching in +z. Prints as it opens.
module divider() {
    difference() {
        union() {
            cube([div_len, div_h, div_t]);
            translate([0, div_h - div_t, 0]) cube([div_len, div_t, flange_w]);
        }
        // bridge screw holes (M3 self-tapping) through the flange
        for (x = div_holes) translate([x, div_h - div_t - 1, flange_w - 4]) rotate([-90, 0, 0]) cylinder(d = 2.6, h = 6);
    }
}

// Standing in place: right divider at x = +pitch/2 with the flange reaching outwards; mirror for the left.
module place_divider() {
    translate([pitch / 2 - div_t / 2, div_y0, floor_t - 2]) rotate([90, 0, 90]) divider();
}

// ============================ BRIDGE ==========================================

module bridge_full() {
    difference() {
        union() {
            translate([-bridge_half, bridge_y0, bridge_top - bridge_t]) cube([2 * bridge_half, bridge_y1 - bridge_y0, bridge_t]);
            // ears under the bed side walls
            translate([-(side_in + side_t + 4), bed_y, bridge_top - bridge_t]) cube([2 * (side_in + side_t + 4), bed_back_y - bed_y, bridge_t]);
            // upstand for the chute's front axle (replaces front_bar), with gussets
            translate([-bridge_half + 4, axle_y, bridge_top - 0.01]) cube([2 * bridge_half - 8, 6, pivot_z + 7 - bridge_top]);
            for (x = [-bridge_half + 6, bridge_half - 9]) translate([x, axle_y + 6, bridge_top - 0.01]) rotate([90, 0, 90]) linear_extrude(3) polygon([[0, 0], [14, 0], [0, 24]]);
            // fence around the feeder stand's footprint
            translate([0, stand_y0 + stand_l / 2, bridge_top - 0.01]) linear_extrude(2) difference() {
                square([feeder_out_w + 4.6, stand_l + 4.6], center = true);
                square([feeder_out_w + 0.6, stand_l + 0.6], center = true);
            }
        }
        // the axle
        translate([0, axle_y - 1, pivot_z]) rotate([-90, 0, 0]) cylinder(d = axle_d + 0.5, h = 8);
        // middle drop opening (trapdoors)
        translate([-door_half - 9, -ch_in - 5, bridge_top - bridge_t - 1]) cube([2 * door_half + 18, 2 * ch_in + 8, bridge_t + 2]);
        // bed wall screws (M3, from below, into the walls' bottom edges)
        for (x = [-1, 1], y = [bed_y + 12, bed_back_y - 12]) translate([x * (side_in + side_t / 2), y, bridge_top - bridge_t - 1]) cylinder(d = 3.2, h = 6);
        // divider flange screws
        for (x = [-1, 1], y = div_holes) translate([x * (bridge_half - 4), div_y0 + y, bridge_top - bridge_t - 1]) cylinder(d = 3.4, h = 6);
        // rear legs
        for (x = [-1, 1]) translate([x * (bridge_half - 7), bridge_y1 - 8, bridge_top - bridge_t - 1]) cylinder(d = 10.4, h = 6);
        // cable slots: servo wires near the tilt bracket, camera + LED + feeder wires at the back
        translate([-40, tilt_bracket_y + 10, bridge_top - bridge_t - 1]) cube([25, 8, bridge_t + 2]);
        translate([-bridge_half + 6, well_y1 + 2, bridge_top - bridge_t - 1]) cube([20, 8, bridge_t + 2]);
        translate([bridge_half - 26, well_y1 + 2, bridge_top - bridge_t - 1]) cube([20, 8, bridge_t + 2]);
        // splice pockets along the seam
        for (x = [-26, 26]) splice_pocket(x, bridge_seam_y, bridge_top - bridge_t);
    }
}

module bridge_tile(i) {
    y0 = i == 0 ? -500 : bridge_seam_y;
    y1 = i == 0 ? bridge_seam_y : 500;
    intersection() { bridge_full(); translate([-500, y0, 0]) cube([1000, y1 - y0, 400]); }
}

leg_h = bridge_top - bridge_t - floor_t;
module leg() {
    cylinder(d = 10, h = leg_h + 3);                  // pegs: into the floor boss, through the bridge
    translate([0, 0, 3]) cylinder(d = 14, h = leg_h - 3);
}

module splice() {
    difference() {
        translate([-splice_l / 2, -splice_w / 2, 0]) cube([splice_l, splice_w, splice_t]);
        for (dx = [-12, 12], dy = [-4, 4]) translate([dx, dy, -1]) cylinder(d = 2.2, h = 4);
    }
}

// ============================ COVERS ==========================================

tower_w = 2 * well_x - 2;  tower_l = well_y1 - well_y0 - 1 + 4;
tower_yc = (well_y0 + well_y1) / 2 + 1;
tower_h = feeder_floor_z + hopper_h + 6 - deck_z;

module tower() {
    difference() {
        translate([0, tower_yc, deck_z]) linear_extrude(tower_h) rrect(tower_w + 5, tower_l + 5, 8);
        translate([0, tower_yc, deck_z - 1]) linear_extrude(tower_h + 2) rrect(tower_w, tower_l, 6);
        // card-level window on the right side
        translate([tower_w / 2, well_y0 + 30, deck_z + 12]) cube([10, tower_l - 50, tower_h - 20]);
        // lid rebate
        translate([0, tower_yc, deck_z + tower_h - 2]) linear_extrude(3) rrect(tower_w + 2, tower_l + 2, 6.5);
    }
}
module tower_lid() {
    translate([0, tower_yc, deck_z + tower_h - 2]) {
        linear_extrude(2) rrect(tower_w + 1.4, tower_l + 1.4, 6.3);
        hull() {
            translate([0, 0, 2]) linear_extrude(1) rrect(tower_w + 5, tower_l + 5, 8);
            translate([0, 0, 2]) linear_extrude(3) rrect(tower_w + 1, tower_l + 1, 6);
        }
    }
}

// Round sleeve over the 20 mm square camera post, between the wall boss and the head.
sleeve_len = cam_height - 14 - 2;
module post_sleeve() {
    difference() {
        linear_extrude(sleeve_len) rrect(28, 28, 9);
        translate([0, 0, -1]) linear_extrude(sleeve_len + 2) square(post_s + 0.6, center = true);
    }
}

// Cap over the camera head's arm and plate. Open underneath, the tower boss pokes through the top.
module head_cover() {
    difference() {
        hull() {
            cylinder(d = 46, h = 16);
            translate([tower_x, 0, 0]) linear_extrude(16) rrect(40, 40, 6);
        }
        translate([0, 0, -1]) hull() {
            cylinder(d = 42, h = 15);
            translate([tower_x, 0, 0]) linear_extrude(15) rrect(36, 36, 5);
        }
        translate([tower_x, 0, -1]) linear_extrude(20) square(boss_s + 0.6, center = true);
        // camera cable
        translate([-8, 12, -1]) cube([16, 20, 10]);
    }
}

// ============================ ASSEMBLY ==========================================
use <card_catalog_drawer.scad>

module place_post(i) {   // 0 fl, 1 fr, 2 bl, 3 br
    x = (i % 2 == 0) ? -hw : hw;  y = (i < 2) ? front_y : back_y;
    translate([x, y, floor_t]) mirror([i % 2, 0, 0]) mirror([0, i >= 2 ? 1 : 0, 0]) post(i < 2);
}

module shell(open = false) {   // open: no deck, tower or right side, to see inside
    color(c_shell) for (i = [0 : 3]) place_post(i);
    color(c_fascia) for (i = [0 : 2]) translate([0, floor_y0 - pt, fascia_z0]) rotate([90, 0, 0]) fascia_tile(i);
    color("white") translate([0, floor_y0 + 1.2, fascia_z0 + light_y - 5]) rotate([90, 0, 0]) light_bar();
    color(c_shell) for (i = [0, 1]) translate([0, back_y - inset, floor_t]) rotate([90, 0, 0]) back_tile(i);
    for (m = open ? [0] : [0, 1]) mirror([m, 0, 0]) color(c_shell) {
        translate([-hw + inset, front_y + post_r - groove_d + 0.3, floor_t]) rotate([90, 0, 90]) side();
        translate([-hw + inset + pt, front_y + post_r - groove_d + 0.3 + side_piece, panel_top]) rotate([90, 0, 90]) rotate([180, 0, 0]) side();
    }
    color(c_inner) for (xi = [0, 1], yi = [0, 1]) floor_tile(xi, yi);
    if (!open) color(c_shell) for (xi = [0, 1], yi = [0, 1]) deck_tile(xi, yi);
    color(c_inner) for (m = [0, 1]) mirror([m, 0, 0]) place_divider();
    color("#555b63") for (i = [0, 1]) bridge_tile(i);
    color(c_inner) for (x = [-1, 1]) translate([x * (bridge_half - 7), bridge_y1 - 8, floor_t]) leg();
    if (!open) { color(c_shell) tower(); color(c_fascia) tower_lid(); }
    color(c_fascia) on_bed() translate([tower_x, card_s, 14]) post_sleeve();
    color(c_fascia) on_bed() translate([0, card_s, cam_height]) head_cover();
}

module drawers() {
    for (i = [0 : 2]) color(c_drawer[i]) translate([div_x[i], dock_y0 - (i == 1 ? show_drawer_out : 0), floor_t])
        card_catalog_drawer(dr_w, dr_body_h, dr_l, dr_face_w, dr_face_h, dr_face_t);
}

module mechanism() {
    assembly();   // from bed_chute.scad, without the frame
    // feeder on its mid stand (drawn as boxes; the real parts are in feeder_test.scad)
    color("dimgray") translate([-feeder_out_w / 2, stand_y0, bridge_top]) cube([feeder_out_w, stand_l, stand_h]);
    color("white") difference() {
        translate([-feeder_out_w / 2, stand_y0, bridge_top + stand_h]) cube([feeder_out_w, stand_l, 3 + hopper_h]);
        translate([-feeder_out_w / 2 + 3, feeder_front_y, bridge_top + stand_h + 3]) cube([feeder_out_w - 6, feeder_in_l, hopper_h + 1]);
        translate([-feeder_out_w / 2 - 1, stand_y0 - 1, bridge_top + stand_h + 3]) cube([feeder_out_w + 2, feeder_shelf + feeder_wall + 1, hopper_h + 1]);
    }
    color("#c9a46a") translate([-card_w / 2, feeder_front_y + 2, bridge_top + stand_h + 3]) cube([card_w, card_l, 40]);
    // Pi 5 and PCA9685
    color("green") translate([pi_pos[0], pi_pos[1], floor_t + 5]) cube([56, 85, 1.6]);
    color("blue") translate([pca_pos[0], pca_pos[1], floor_t + 5]) cube([62, 25, 1.6]);
}

// ============================ OUTPUT ==========================================

if (epart == "post_front") translate([0, 0, post_h]) mirror([0, 0, 1]) post(true);    // upside down: flat top on the bed, pegs up
else if (epart == "post_back") translate([0, 0, post_h]) mirror([0, 0, 1]) post(false);
else if (epart == "side") side();
else if (epart == "fascia_l") fascia_tile(0);
else if (epart == "fascia_m") fascia_tile(1);
else if (epart == "fascia_r") fascia_tile(2);
else if (epart == "light_bar") light_bar();
else if (epart == "back_l") back_tile(0);
else if (epart == "back_r") back_tile(1);
else if (epart == "floor_fl") floor_tile(0, 0);
else if (epart == "floor_fr") floor_tile(1, 0);
else if (epart == "floor_bl") floor_tile(0, 1);
else if (epart == "floor_br") floor_tile(1, 1);
else if (epart == "deck_fl") translate([0, 0, deck_z]) mirror([0, 0, 1]) deck_tile(0, 0);
else if (epart == "deck_fr") translate([0, 0, deck_z]) mirror([0, 0, 1]) deck_tile(1, 0);
else if (epart == "deck_bl") translate([0, 0, deck_z]) mirror([0, 0, 1]) deck_tile(0, 1);
else if (epart == "deck_br") translate([0, 0, deck_z]) mirror([0, 0, 1]) deck_tile(1, 1);
else if (epart == "divider") divider();
else if (epart == "bridge_front") translate([0, 0, -(bridge_top - bridge_t)]) bridge_tile(0);
else if (epart == "bridge_back") translate([0, 0, -(bridge_top - bridge_t)]) bridge_tile(1);
else if (epart == "leg") leg();
else if (epart == "splice") splice();
else if (epart == "tower") translate([0, 0, -deck_z]) tower();
else if (epart == "tower_lid") translate([0, 0, deck_z + tower_h + 3]) mirror([0, 0, 1]) tower_lid();
else if (epart == "post_sleeve") post_sleeve();
else if (epart == "head_cover") translate([0, 0, 16]) mirror([0, 0, 1]) head_cover();
else if (epart == "shell") shell();
else if (epart == "inside") { shell(true); drawers(); mechanism(); }
else {
    shell();
    drawers();
    if (show_mech) mechanism();
}
