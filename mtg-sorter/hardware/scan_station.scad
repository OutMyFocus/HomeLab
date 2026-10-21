// MTG scan station: holds the camera at a fixed height over a card pocket.
//
// Three parts, printed separately:
//   base  - plate with the card pocket and two LED light walls
//           (print in WHITE PLA: it's the background the camera sees)
//   post  - vertical column, slots into the base
//   head  - arm + camera plate, slots onto the post
//
// The light comes from the sides, low down. Light from above (next to the camera)
// would bounce off glossy and foil cards straight into the lens as a glare spot.
//
// Open in OpenSCAD, set `part` below, press F6 (render) then F7 (export STL).
// Or from a terminal:  openscad -D 'part="base"' -o base.stl scan_station.scad
//
// All sizes are in millimetres.

part = "assembly"; // "base", "post", "head" or "assembly" (preview only)

// --- Things you might want to change -------------------------------------
cam_height = 120;   // camera lens above the card. Pi Camera Module 3 focuses from 100.
fit = 0.3;          // gap for parts that slot together. Too tight? Raise to 0.4.

// --- Card ------------------------------------------------------------------
card_w = 63;        // MTG cards are 63 x 88
card_l = 88;
card_gap = 1.5;     // room around the card in its pocket (sleeved cards: try 3)
pocket_d = 1.2;     // pocket depth

// --- Base --------------------------------------------------------------------
base_w = 130;
base_l = 150;
base_t = 5;
post_y = 66;        // post centre, behind the card

// --- Post --------------------------------------------------------------------
post_s = 20;        // square post
socket_d = 18;      // how deep the post sits in the base and in the head
boss_s = 32;        // block around each socket

// --- Light walls (on the base, left and right of the card) ----------------------
wall_x = 50;        // inner face of each wall, from the card centre
wall_t = 6;
wall_h = 32;
wall_len = 110;
led_w = 10.5;       // LED strip width (most 5 V strips are 8 or 10 mm)
led_z = 20;         // height of the strip's centre above the card

// --- Head --------------------------------------------------------------------
arm_t = 6;

// Raspberry Pi Camera Module 3 (25 x 24 mm board, M2 holes).
// The board sits on top of the plate with its lens pointing down through the window.
cam_board = [25, 24];
cam_holes = [[-10.5, -10], [10.5, -10], [-10.5, 2.5], [10.5, 2.5]]; // from board centre
cam_window = [14, 18];
cam_plate = 34;

$fn = 48;

card_z = base_t - pocket_d;               // card surface height
cam_z = card_z + cam_height;              // underside of the head
post_bottom = base_t + 2;                 // floor of the base socket
post_len = cam_z + socket_d - post_bottom - 1;  // 1 mm spare at the top

module base() {
    pocket = [card_w + 2 * card_gap, card_l + 2 * card_gap];
    difference() {
        union() {
            translate([-base_w / 2, -base_l / 2 + 4, 0]) rounded_box([base_w, base_l, base_t], 6);
            // block around the post socket
            translate([-boss_s / 2, post_y - boss_s / 2, 0]) rounded_box([boss_s, boss_s, post_bottom + socket_d], 3);
            // light walls
            for (m = [0, 1]) mirror([m, 0, 0])
                translate([wall_x, -wall_len / 2, 0]) rounded_box([wall_t, wall_len, card_z + wall_h], 2);
        }
        // LED strip groove on the inner face of each wall
        for (m = [0, 1]) mirror([m, 0, 0])
            translate([wall_x - 1, -wall_len / 2 + 5, card_z + led_z - led_w / 2]) cube([2.5, wall_len - 10, led_w]);
        // wire channel under the base, joining the two walls, and holes up into each groove
        translate([-wall_x - 3, post_y - 22, -1]) cube([2 * wall_x + 6, 5, 3.5]);
        for (m = [0, 1]) mirror([m, 0, 0])
            translate([wall_x + 0.5, post_y - 22, -1]) cube([3, 5, card_z + led_z - led_w / 2 + 2]);
        // card pocket
        translate([-pocket[0] / 2, -pocket[1] / 2, card_z]) cube([pocket[0], pocket[1], 10]);
        // finger notches to lift the card out
        for (x = [-1, 1]) translate([x * pocket[0] / 2, 0, card_z - 2]) cylinder(r = 11, h = 10);
        // post socket
        translate([-(post_s + fit) / 2, post_y - (post_s + fit) / 2, post_bottom]) cube([post_s + fit, post_s + fit, 50]);
        // rubber feet recesses (optional), 8 mm round
        for (x = [-1, 1], y = [-1, 1]) translate([x * (base_w / 2 - 12), y * (base_l / 2 - 14) + 4, -1]) cylinder(d = 8.5, h = 1.6);
    }
}

module post() {
    difference() {
        translate([-post_s / 2, -post_s / 2, 0]) cube([post_s, post_s, post_len]);
        // groove for the camera's ribbon cable (16 mm wide), on the back face
        translate([-8.5, post_s / 2 - 1.5, -1]) cube([17, 2, post_len + 2]);
        // small chamfers so the ends slide into the sockets
        for (z = [0, post_len]) translate([0, 0, z]) chamfer_ring();
    }
}

module chamfer_ring() {
    difference() {
        cube([post_s + 2, post_s + 2, 2], center = true);
        rotate([0, 0, 45]) cylinder(d1 = post_s * 1.41 - 2, d2 = post_s * 1.41 + 2, h = 2.01, center = true, $fn = 4);
    }
}

module head() {
    difference() {
        union() {
            // socket block that slides onto the top of the post
            translate([-boss_s / 2, post_y - boss_s / 2, 0]) rounded_box([boss_s, boss_s, socket_d + 6], 3);
            // arm from the post to the camera plate
            translate([-10, 0, 0]) cube([20, post_y, arm_t]);
            // camera plate, centred over the card
            translate([-cam_plate / 2, -cam_plate / 2, 0]) rounded_box([cam_plate, cam_plate, 3], 3);
            // standoffs that the camera board screws onto
            for (h = cam_holes) translate([h[0], h[1], 0]) cylinder(d = 5, h = 6);
        }
        // post socket (open at the bottom)
        translate([-(post_s + fit) / 2, post_y - (post_s + fit) / 2, -1]) cube([post_s + fit, post_s + fit, socket_d + 1]);
        // lens window
        translate([-cam_window[0] / 2, -cam_window[1] / 2, -1]) cube([cam_window[0], cam_window[1], 10]);
        // M2 screw holes (self-tapping M2 x 6 screws)
        for (h = cam_holes) translate([h[0], h[1], -1]) cylinder(d = 1.8, h = 10);
    }
}

module rounded_box(size, r) {
    hull() for (x = [r, size[0] - r], y = [r, size[1] - r]) translate([x, y, 0]) cylinder(r = r, h = size[2]);
}

module card() {
    color("tan") translate([-card_w / 2, -card_l / 2, card_z]) cube([card_w, card_l, 0.3]);
}

if (part == "base") base();
else if (part == "post") post();
else if (part == "head") head();
else {
    color("white") base();
    card();
    color("dimgray") translate([0, post_y, post_bottom]) post();
    color("lightblue") translate([0, 0, cam_z]) head();
    // camera board, for the preview only
    color("green") translate([-cam_board[0] / 2, -cam_board[1] / 2 + 3.75, cam_z + 6]) cube([cam_board[0], cam_board[1], 1]);
    // LED strips, for the preview only
    for (m = [0, 1]) mirror([m, 0, 0]) color("yellow")
        translate([wall_x - 0.5, -wall_len / 2 + 6, card_z + led_z - led_w / 2]) cube([0.5, wall_len - 12, led_w]);
}
