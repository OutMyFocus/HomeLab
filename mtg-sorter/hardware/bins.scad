// Sorter bins and the card organizer they live in.
//
// A BIN is a drawer: it sits in one of the three bays at the front of the sorter, under an
// output (bin 1 = left end of the tilting tray, bin 2 = under the trapdoors, bin 3 = right
// end), and slides out of the front when it's full. The same bin then slides into a cubby of
// the ORGANIZER, a stackable cabinet, so sorted cards never have to be re-boxed.
//
// Our own design. It keeps the outside size the sorter's dock was built around
// (enclosure.scad, dr_*): 76 wide tray, 86 x 109 front plate, 231 long, so it fits the
// enclosure you already printed with no changes there. See BINS.md.
//
// In the sorter cards land FLAT (63 x 88, long side front to back), about 220 of them before
// the pile reaches the top. In the organizer, stand them on end, faces to the front, and flip
// through them like an index; the dividers slot into the grooves along the walls.
//
// Printable parts (set `part`). All fit the A1's 256 mm bed, no supports:
//   bin            the drawer (module sorter_bin). Prints standing on its floor (x3 for the sorter)
//   divider        card divider with a tab ("divider_l", "divider_m", "divider_r": where the tab
//                  sits). Prints flat; white filament writes well with a pencil or marker
//   label          a blank 66 x 25 card for the label pocket on the front plate (or cut paper)
//   organizer_2x2  4 cubbies, 2 wide x 2 high (173 x 222 x 229.5). Prints standing on its back
//   organizer_1x2  2 cubbies, 1 wide x 2 high (86.5 x 222 x 229.5): next to a 2x2 it makes
//                  a 3-wide cabinet, the same as the sorter
//   organizer_2x1, organizer_1x1   the same, one row high
//   key            bow-tie key: joins two organizer units, tapped flush into the pockets on their
//                  back faces across the seam (one per row side by side, one per column stacked)
//   "assembly"     preview: sorter bins in a 3-wide, 2-high organizer, one bin pulled out
//
// Coordinates for the bin: x across, y front (0, the plate's front face) to back, z up from
// the floor it rides on. Same origin as card_catalog_drawer.scad, so the enclosure preview can
// draw either.

part = "assembly";

// --- Cards -------------------------------------------------------------------------
card_w = 63;  card_l = 88;

// --- Bin: the outside size is the sorter's dock (enclosure.scad dr_*) -------------
bin_w = 76;               // tray outside width (dock slot is 77 between the floor curbs)
bin_h = 70;               // tray height (the dock has room to ~100; 70 keeps standing cards easy to flip)
bin_len = 231;            // front of the plate to the back of the tray (dock: dr_l)
face_w = 86;  face_h = 109;  face_t = 5;     // front plate (dock: 86 x 109, 8 thick; 5 is enough, the
                                            // bin's length keeps the plate flush with the fascia)
wall = 2.0;               // tray side and back walls
floor_th = 1.6;           // tray floor
corner_r = 3;             // tray's back corners, plate corners
foot_ch = 0.8;            // chamfer round the tray's bottom edge (no elephant foot catching the curbs)

// divider grooves on the inside walls
groove_d = 0.8;  groove_w = 1.8;
groove_y = [for (y = [35 : 20 : 215]) y];   // from the plate's front face

// label pocket at the top of the plate, open at the top: a 66 x 25 card or paper slides in
lab_w = 66.6;  lab_h = 26;  lab_t = 1.2;    // the slot
lip_t = 1.2;  lip_side = 3;  lip_bot = 4;   // the lips in front of it (window 60.6 x 22)

// finger pull: a cup along the bottom of the plate, its upturned lip catches your fingertips
pull_w = 56;  pull_out = 13;  pull_h = 12;  pull_t = 2.6;  pull_base = 3;

// --- Organizer --------------------------------------------------------------------
// An egg crate of thin walls, with diamond windows to save plastic (about a third of a solid
// box). The pitch is set by the bins' front plates: they sit side by side, 0.5 apart.
pitch_x = 86.5;           // cubby to cubby across
pitch_z = 111;            // row to row (109 plates, 1-2 mm between them)
t_out = 2.0;              // outside walls
t_in = 1.6;               // walls and shelves between cubbies
slot = 77.5;              // between the guide curbs on each cubby floor (0.75 a side for the tray)
curb_w = 2;  curb_h = 2.5;  curb_ramp = 8;
back_t = 4;               // back frame (the bow-tie pockets are cut into it)
wall_d = bin_len - face_t - 0.5;           // front edge to the back frame: the tray's back end
org_d = wall_d + back_t;                   // stops on the frame, the plate 0.5 in front of the edges
rim = 6;                  // back frame round each cubby's back opening
win_d = 50;  win_bar = 5;  win_frame = 8;  // diamond windows: size, bars between, solid border
win_front = 14;  win_back = 10;            // solid bands at the front and back of every wall
// joining units: bow-tie keys in pockets on the back face, across the seam
key_l = 26;  key_neck = 7;  key_end = 12;  key_t = 2.3;  key_clr = 0.2;  key_depth = 2.5;
key_above = 92;           // side pockets this far above a row's floor (above the bin)

$fn = 48;

// ============================ BIN ==========================================

module rrect(w, l, r) { offset(r = r) offset(delta = -r) square([w, l], center = true); }

// tray outline seen from above: square at the front (it joins the plate), rounded at the back
module tray_2d(inset = 0) {
    w = bin_w - 2 * inset;  y0 = inset;  y1 = bin_len - inset;  r = max(corner_r - inset, 0.5);
    hull() {
        translate([-w / 2, y0]) square([w, 1]);
        for (s = [-1, 1]) translate([s * (w / 2 - r), y1 - r]) circle(r = r);
    }
}

// the plate seen from the front (x, z), rounded corners
module plate_2d() { translate([0, face_h / 2]) rrect(face_w, face_h, corner_r); }

module sorter_bin() {
    difference() {
        union() {
            // tray, with a chamfer round the bottom edge
            hull() {
                translate([0, 0, foot_ch]) linear_extrude(bin_h - foot_ch) tray_2d();
                linear_extrude(foot_ch) tray_2d(foot_ch);
            }
            // front plate
            translate([0, face_t, 0]) rotate([90, 0, 0]) linear_extrude(face_t) plate_2d();
            // finger pull: base flat on the bed, lip straight up, so it prints without support
            translate([0, 0, 0]) pull();
        }
        // inside of the tray
        translate([0, 0, floor_th]) linear_extrude(bin_h) intersection() {
            tray_2d(wall);
            translate([-50, face_t]) square([100, bin_len]);
        }
        // divider grooves, floor to rim, both walls
        for (y = groove_y, s = [-1, 1])
            translate([s * (bin_w / 2 - wall + groove_d / 2) - groove_d / 2 - 0.01 * s, y - groove_w / 2, floor_th]) cube([groove_d + 0.02, groove_w, bin_h]);
        // label pocket: slot behind the lips, window in front, both open at the top
        translate([-lab_w / 2, lip_t, face_h - lab_h]) cube([lab_w, lab_t, lab_h + 1]);
        translate([-lab_w / 2 + lip_side, -1, face_h - lab_h + lip_bot]) cube([lab_w - 2 * lip_side, lip_t + 1.01, lab_h]);
        // a thumb notch at the top of the window to slide the label out
        translate([0, -1, face_h]) rotate([-90, 0, 0]) cylinder(r = 7, h = lip_t + lab_t + 1.5);
    }
}

module pull() {
    // seen from the side (y, z): base slab + upturned lip; extruded across x, rounded ends
    intersection() {
        translate([-pull_w / 2, 0, 0]) rotate([90, 0, 90]) linear_extrude(pull_w) polygon([
            [0.5, 0], [-pull_out + 1, 0], [-pull_out, 1], [-pull_out, pull_h - 1], [-pull_out + 1, pull_h],
            [-pull_out + pull_t, pull_h], [-pull_out + pull_t, pull_base + 2], [-pull_out + pull_t + 2, pull_base],
            [0.5, pull_base]]);
        // round the two ends seen from above
        linear_extrude(pull_h + 1) translate([0, 0.5 - (pull_out + 1) / 2]) rrect(pull_w, pull_out + 1, 6);
    }
}

// ============================ DIVIDERS AND LABEL ==================================

div_t = 1.2;
div_body_w = bin_w - 2 * wall + 2 * (groove_d - 0.2);   // reaches 0.8 into each groove
div_body_h = bin_h - floor_th - 1;                      // inside the tray
div_top_w = 66;                                         // above the rim, about a card wide
div_top_h = card_l - 1;                                 // as tall as a standing card
tab_w = 26;  tab_h = 9;

// flat on the bed, x across, y up the divider
module divider(tab = 0) {   // tab: -1 left, 0 middle, 1 right
    tx = tab * (div_top_w - tab_w) / 2;
    linear_extrude(div_t) {
        translate([-div_body_w / 2, 0]) square([div_body_w, div_body_h]);
        hull() {
            translate([-div_top_w / 2, 0]) square([div_top_w, div_top_h - 3]);
            for (s = [-1, 1]) translate([s * (div_top_w / 2 - 3), div_top_h - 3]) circle(r = 3);
        }
        hull() for (s = [-1, 1]) {
            translate([tx + s * (tab_w / 2 - 3), div_top_h + tab_h - 3]) circle(r = 3);
            translate([tx + s * (tab_w / 2 + 3), div_top_h - 3]) circle(r = 1);
        }
    }
}

module label() { linear_extrude(0.8) translate([0, 12.5]) rrect(66, 25, 1.5); }

// ============================ ORGANIZER =====================================

// Origin: front face, bottom, middle. x across, y back, z up (the cabinet as it stands).
function org_w(cols) = cols * pitch_x;
function org_h(rows) = rows * pitch_z;
function wall_x(cols, i) = -org_w(cols) / 2 + i * pitch_x;           // i = 0 .. cols
function shelf_z(rows, j) = j * pitch_z;                             // j = 0 .. rows
function wall_t(n, i) = (i == 0 || i == n) ? t_out : t_in;
// a wall's span: outer walls sit inside the unit's outline, inner ones straddle the line
function span(n, i, p) = let(t = wall_t(n, i)) i == 0 ? [i * p, i * p + t] : i == n ? [i * p - t, i * p] : [i * p - t / 2, i * p + t / 2];
function floor_z(rows, j) = span(rows, j, pitch_z)[1];               // a row's cubby floor

// staggered diamonds in the (u, v) plane, v from v0 to v1 (whole diamonds only, so every edge
// is at 45 degrees or along v), u clipped to u0 .. u1 (those cut edges run along v)
module diamonds(u0, u1, v0, v1) {
    p = win_d + win_bar * sqrt(2);  h = win_d / 2;
    nk = floor((v1 - v0 - win_d) / (p / 2));
    vs = v0 + h + ((v1 - v0 - win_d) - nk * p / 2) / 2;
    intersection() {
        translate([u0, v0 - 1]) square([u1 - u0, v1 - v0 + 2]);
        if (nk >= 0 && u1 > u0) for (k = [0 : nk]) for (m = [-4 : 4])
            translate([(u0 + u1) / 2 + m * p + (k % 2) * p / 2, vs + k * p / 2]) rotate(45) square(win_d / sqrt(2), center = true);
    }
}

module organizer(cols = 2, rows = 2) {
    W = org_w(cols);  H = org_h(rows);  x0 = -W / 2;
    // walls across (normal x), full height
    for (i = [0 : cols]) let(s = span(cols, i, pitch_x)) difference() {
        translate([x0 + s[0], 0, 0]) cube([s[1] - s[0], wall_d + 0.01, H]);
        for (j = [0 : rows - 1])
            translate([x0 + s[0] - 1, 0, 0]) rotate([90, 0, 90]) linear_extrude(s[1] - s[0] + 2) rotate(90) mirror([0, 1])
                diamonds(floor_z(rows, j) + win_frame, span(rows, j + 1, pitch_z)[0] - win_frame, win_front, wall_d - win_back);
    }
    // shelves (normal z), between the walls; windows only in the middle, the bin rides on the edges
    for (j = [0 : rows]) let(s = span(rows, j, pitch_z)) for (i = [0 : cols - 1]) let(c = x0 + (i + 0.5) * pitch_x) difference() {
        translate([x0 + span(cols, i, pitch_x)[1] - 0.01, 0, s[0]]) cube([span(cols, i + 1, pitch_x)[0] - span(cols, i, pitch_x)[1] + 0.02, wall_d + 0.01, s[1] - s[0]]);
        translate([0, 0, s[0] - 1]) linear_extrude(s[1] - s[0] + 2) diamonds(c - slot / 2 + 9, c + slot / 2 - 9, win_front, wall_d - win_back);
    }
    // guide curbs on each cubby floor, ramped up at the mouth
    for (i = [0 : cols - 1], j = [0 : rows - 1], sd = [-1, 1]) let(c = x0 + (i + 0.5) * pitch_x)
        translate([c + sd * (slot / 2 + curb_w / 2) - curb_w / 2, 0, floor_z(rows, j) - 0.01]) rotate([90, 0, 90]) linear_extrude(curb_w)
            polygon([[0, 0], [wall_d, 0], [wall_d, curb_h], [curb_ramp, curb_h], [0, 0.5]]);
    // back frame, with the bow-tie pockets
    difference() {
        translate([0, wall_d, 0]) rotate([90, 0, 0]) mirror([0, 0, 1]) linear_extrude(back_t) back_2d(cols, rows);
        for (p = key_spots(cols, rows)) translate([p[0], org_d + 1, p[1]]) rotate([90, 0, 0]) linear_extrude(key_depth + 1)
            rotate(p[2]) offset(delta = key_clr) half_key_2d();
    }
}

// pocket positions on the back face: [x, z, angle] (the half bow-tie points inwards)
function key_spots(cols, rows) = concat(
    [for (j = [0 : rows - 1], sd = [-1, 1]) [sd * org_w(cols) / 2, floor_z(rows, j) + key_above, sd > 0 ? 0 : 180]],
    [for (i = [0 : cols - 1], z = [0, org_h(rows)]) [-org_w(cols) / 2 + (i + 0.5) * pitch_x, z, z == 0 ? 270 : 90]]);

// back frame, seen from behind... drawn in (x, z): the outline, less an opening per cubby,
// with solid tabs left round each key pocket
module back_2d(cols, rows) {
    W = org_w(cols);  H = org_h(rows);
    difference() {
        translate([-W / 2, 0]) square([W, H]);
        for (i = [0 : cols - 1], j = [0 : rows - 1]) difference() {
            x0 = -W / 2 + span(cols, i, pitch_x)[1] + rim;  x1 = -W / 2 + span(cols, i + 1, pitch_x)[0] - rim;
            z0 = floor_z(rows, j) + rim;  z1 = span(rows, j + 1, pitch_z)[0] - rim;
            translate([(x0 + x1) / 2, (z0 + z1) / 2]) rrect(x1 - x0, z1 - z0, 6);
            for (p = key_spots(cols, rows)) translate([p[0], p[1]]) rotate(p[2]) translate([-key_l / 2 - 4, -key_end / 2 - 4]) square([key_l / 2 + 5, key_end + 8]);
        }
    }
}

// half a bow-tie, in the face's plane, from the seam (x = 0) inwards (-x); the key is two of them
module half_key_2d() { polygon([[0.01, -key_neck / 2], [0.01, key_neck / 2], [-key_l / 2, key_end / 2], [-key_l / 2, -key_end / 2]]); }
module key() { linear_extrude(key_t) { half_key_2d(); mirror([1, 0]) half_key_2d(); } }

// ============================ PRINT ORIENTATIONS ===================================

// the organizer stands on its back face to print: every wall vertical, the open fronts on top
module organizer_print(cols, rows) { translate([0, 0, org_d]) rotate([-90, 0, 0]) organizer(cols, rows); }

// ============================ PREVIEW =====================================

c_bin = ["#2d63b8", "#e5e2d6", "#d8262a"];
module assembly() {
    color("#24272c") {
        translate([-pitch_x / 2, 0, 0]) organizer(2, 2);
        translate([pitch_x, 0, 0]) organizer(1, 2);
    }
    for (i = [0 : 2], j = [0 : 1]) {
        out = (i == 1 && j == 0) ? 120 : 0;
        color(c_bin[i]) translate([(i - 1) * pitch_x, -face_t - 0.5 - out, floor_z(2, j) + 0.01]) sorter_bin();
    }
    // a few standing cards in the pulled-out bin
    color("#c9a46a") for (k = [0 : 4]) translate([-card_w / 2, -face_t - 120 + 60 + k * 6, floor_z(2, 0) + floor_th]) cube([card_w, 0.4, card_l]);
    color("white") translate([0, -face_t - 120 + 50, floor_z(2, 0) + floor_th]) rotate([90, 0, 0]) divider(0);
}

if (part == "bin") sorter_bin();
else if (part == "divider_l") divider(-1);
else if (part == "divider_m" || part == "divider") divider(0);
else if (part == "divider_r") divider(1);
else if (part == "label") label();
else if (part == "key") key();
else if (part == "organizer_2x2") organizer_print(2, 2);
else if (part == "organizer_1x2") organizer_print(1, 2);
else if (part == "organizer_2x1") organizer_print(2, 1);
else if (part == "organizer_1x1") organizer_print(1, 1);
else if (part == "assembly") assembly();
