// Enclosure concept: the sorter as one sleek countertop box, Roca-style.
//
// This is a PICTURE for deciding the look. The mechanism inside is exactly what is in
// bed_chute.scad and feeder_test.scad today (bed, pins, camera tower, chute, feeder);
// the enclosure wraps around it and replaces the open frame sides, the front bar and
// the three printed bins. The bins become Nic's MakerWorld storage drawers, which
// slide into a dock at the front, so a full drawer goes straight onto the shelf.
//
// Coordinates match bed_chute.scad: x across, y front(-) to back(+), z up, table z = 0.

show_drawer_out = 1;      // pull the middle drawer out a bit in the preview
show_hopper_lid = true;

// --- Storage drawers (Nic's MakerWorld boxes). Placeholder sizes until the link arrives.
drawer_w = 100;           // outside width of one drawer
drawer_h = 100;           // outside height
drawer_l = 250;           // outside length (front to back)
dock_wall = 4;            // wall between drawers
drawer_lip = 2;           // how far the drawer front stands proud of the fascia

// --- Mechanism, from bed_chute.scad / feeder_test.scad ------------------------------
bed_angle = 20;
bed_y = 54;  bed_z = 170;  bed_len = 100;
side_in = 56;  side_t = 6;  wall_h = 32;
card_s = 47;  cam_height = 120;  tower_x = 80;
pivot_z = 145;
hopper_in_w = 67;  hopper_in_l = 92;  hopper_h = 60;
feeder_floor_z = 206;     // tall stand (203) + floor

// --- Body ----------------------------------------------------------------------------
body_w = 3 * drawer_w + 4 * dock_wall + 2 * 8;   // 8 mm skin each side
body_y0 = -82;                                    // front face (just in front of the front bar)
body_y1 = 285;                                    // back face (behind the hopper)
body_h = 212;                                     // top deck, just above the bed's back edge
corner_r = 16;
edge_r = 3;
drawer_z = 8;                                     // drawers ride this far above the table

// --- Colours -----------------------------------------------------------------------------
shell = "#1b1d21";
shell2 = "#24272c";
trim = "#8e949c";
accent = "#e8772e";
drawer_cols = ["#e5e2d6", "#2d63b8", "#d8262a"];   // whatever Nic prints them in

$fn = 48;

module rbox(size, r, e = edge_r) {
    translate([e, e, e]) minkowski() {
        hull() for (x = [r - e, size[0] - r - e], y = [r - e, size[1] - r - e])
            translate([x, y, 0]) cylinder(r = r - e, h = size[2] - 2 * e);
        sphere(r = e, $fn = 16);
    }
}

bed_back_y = bed_y + bed_len * cos(bed_angle);
bed_back_z = bed_z + bed_len * sin(bed_angle);
drawer_pitch = drawer_w + dock_wall;
dock_y0 = body_y0 + 2;                     // drawer fronts sit here

module body() {
    difference() {
        color(shell) translate([-body_w / 2, body_y0, 0]) rbox([body_w, body_y1 - body_y0, body_h], corner_r);
        // drawer openings
        for (i = [-1, 0, 1]) translate([i * drawer_pitch - drawer_w / 2 - 0.5, body_y0 - 1, drawer_z - 0.5])
            cube([drawer_w + 1, drawer_l + 6, drawer_h + 1]);
        // scan bay: a well in the deck around the bed, its rim following the bed walls
        translate([-side_in - side_t, bed_y - 6, bed_z - 30]) cube([2 * (side_in + side_t), bed_back_y - bed_y + 12, 200]);
        // hopper well
        translate([-hopper_in_w / 2 - 3, 178, feeder_floor_z - 20]) cube([hopper_in_w + 6, hopper_in_l + 6, 200]);
        // cable / power cutout at the back
        translate([body_w / 2 - 60, body_y1 - 5, 20]) cube([30, 10, 14]);
        // upper fascia: a shallow recess above the drawers, filled with a lighter panel
        translate([-body_w / 2 + 14, body_y0 - 1, drawer_z + drawer_h + 10]) cube([body_w - 28, 2.5, body_h - drawer_z - drawer_h - 30]);
        // recessed foot line
        translate([-body_w / 2 - 1, body_y0 - 1, -1]) cube([body_w + 2, body_y1 - body_y0 + 2, 1 + 2]);
    }
    color(shell2) translate([-body_w / 2 + 14, body_y0 + 1.5, drawer_z + drawer_h + 10]) rbox([body_w - 28, 1.5, body_h - drawer_z - drawer_h - 30], 6, 0.6);
    // feet
    for (x = [-1, 1], y = [body_y0 + 30, body_y1 - 30]) color(shell2) translate([x * (body_w / 2 - 30), y, 0]) cylinder(d = 16, h = 2.2);
}

module scan_bay() {
    // the real bed walls and white bed, seen through the well in the deck
    translate([0, bed_y, bed_z]) rotate([bed_angle, 0, 0]) {
        color("white") translate([-side_in, 0, -3]) cube([2 * side_in, bed_len, 3]);
        color("#c9a46a") translate([-31.5, 4.5, 0.05]) cube([63, 88, 0.4]);
        for (m = [0, 1]) mirror([m, 0, 0]) {
            color(shell2) translate([side_in, 0, -3]) cube([side_t, bed_len, wall_h + 3]);
            color("#fff6d8") translate([side_in - 0.6, 5, 14.5]) cube([0.6, bed_len - 10, 10.5]);
        }
    }
    // dark floor under the bed (hides the chute from the top)
    color(shell2) translate([-side_in - side_t, bed_y - 6, bed_z - 30]) cube([2 * (side_in + side_t), 6, 70]);
    color(shell2) translate([-side_in - side_t, bed_back_y, bed_back_z - 8]) cube([2 * (side_in + side_t), 6, 20]);
}

module camera_arm() {
    // the existing 20 mm tower post, wrapped in a rounded cover; arm reaches across to the head
    head_y = bed_y + card_s * cos(bed_angle) - cam_height * sin(bed_angle);
    head_z = bed_z + card_s * sin(bed_angle) + cam_height * cos(bed_angle);
    top_z = head_z + 26;
    color(shell2) {
        hull() {
            translate([tower_x, head_y, body_h - 1]) cylinder(d = 28, h = 1);
            translate([tower_x, head_y, top_z]) sphere(d = 24);
        }
        hull() {
            translate([tower_x, head_y, top_z]) sphere(d = 22);
            translate([0, head_y, top_z]) sphere(d = 22);
        }
        hull() {
            translate([0, head_y, top_z]) sphere(d = 20);
            translate([0, head_y, head_z + 6]) rotate([bed_angle, 0, 0]) cylinder(d = 40, h = 1);
        }
    }
    translate([0, head_y, head_z]) rotate([bed_angle, 0, 0]) {
        color(shell2) cylinder(d = 42, h = 7);
        color("#101010") translate([0, 0, -0.6]) cylinder(d = 15, h = 1);
        color("#8fb3c9") translate([0, 0, -0.9]) cylinder(d = 8, h = 1);
        color(accent) translate([0, 0, 1.5]) rotate_extrude() translate([21, 0]) square([0.8, 1.6]);
    }
}

module hopper_tower() {
    w = hopper_in_w + 6 + 14;  d = hopper_in_l + 6 + 14;  h = hopper_h + 34;
    difference() {
        color(shell) translate([-w / 2, 178 - 7, body_h - 2]) rbox([w, d, h], 10, 2.5);
        color(shell2) translate([-hopper_in_w / 2, 178 + 3, body_h]) cube([hopper_in_w, hopper_in_l, 200]);
        // card level window on the right side
        color(shell2) translate([w / 2 - 6, 178 + 20, body_h + 10]) cube([8, d - 54, h - 24]);
    }
    color("#9fb7c4", 0.55) translate([w / 2 - 3.5, 178 + 20, body_h + 10]) cube([1, d - 54, h - 24]);
    color("#c9a46a") translate([-31.5, 180, feeder_floor_z]) cube([63, 88, 55]);
    if (show_hopper_lid) color(shell2) translate([-w / 2 + 2, 178 - 5, body_h - 2 + h - 0.5]) rbox([w - 4, d - 4, 5], 8, 1.5);
}

module drawer(i) {
    col = drawer_cols[i + 1];
    out = (i == 0) ? show_drawer_out * 70 : 0;
    translate([i * drawer_pitch, dock_y0 - out, drawer_z]) {
        // box
        color(col) translate([-drawer_w / 2 + 1, drawer_lip, 1]) difference() {
            cube([drawer_w - 2, drawer_l - 4, drawer_h - 2]);
            translate([2, 2, 2]) cube([drawer_w - 6, drawer_l - 8, drawer_h]);
        }
        // front face with a finger notch at the top
        color(col) difference() {
            translate([-drawer_w / 2 + 1, -drawer_lip, 1]) rbox([drawer_w - 2, drawer_lip + 2, drawer_h - 2], 4, 1.5);
            translate([0, -drawer_lip - 1, drawer_h + 2]) rotate([-90, 0, 0]) cylinder(r = 11, h = 10);
        }
        // a few sorted cards, lying flat at the back of the drawer
        color("#c9a46a") translate([-31.5, drawer_l - 4 - 92, 3]) cube([63, 88, 18]);
    }
}

module front_details() {
    // thin orange status line along the top front edge, and a power button
    color(accent) translate([-body_w / 2 + corner_r + 6, body_y0 + 1.3, body_h - 26]) cube([body_w - 2 * corner_r - 12, 1, 1.6]);
    color(shell2) translate([body_w / 2 - 28, body_y0 + 1.3, body_h - 44]) rotate([90, 0, 0]) cylinder(d = 11, h = 1.5);
    color(accent) translate([body_w / 2 - 28, body_y0 + 0.8, body_h - 44]) rotate([90, 0, 0]) cylinder(d = 4, h = 0.8);
    // drawer numbers as dots under each drawer
    for (i = [-1, 0, 1]) for (n = [0 : i + 1]) color(trim)
        translate([i * drawer_pitch - (i + 1) * 4 + n * 8, body_y0 - 0.3, drawer_z - 4]) rotate([-90, 0, 0]) cylinder(d = 3, h = 1);
}

body();
scan_bay();
camera_arm();
hopper_tower();
for (i = [-1, 0, 1]) drawer(i);
front_details();
