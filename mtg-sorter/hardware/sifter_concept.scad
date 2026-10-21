// The full sifter as a finished machine: what it will look like from the outside.
// The mechanism inside is in sifter_inside.scad. Neither file is printable parts yet.
//
// Countertop body with a card hopper at the back, a scan bay on top under the camera
// arm, and three pull-out bins along the front.

// --- Overall size (a little smaller than a Roca Sifter's 330 x 340 mm) ------------
body_w = 250;
body_d = 290;
body_h = 140;
corner_r = 18;
edge_r = 4;           // softened top and bottom edges

// --- Bins (pull-out drawers along the front) ---------------------------------------
bin_w = 74;
bin_h = 92;
bin_gap = 6;

// --- Hopper (holds about 400 cards) --------------------------------------------------
hop_w = 83;
hop_d = 106;
hop_h = 120;

// --- Scan bay and camera arm -----------------------------------------------------------
bay_y = -38;          // centre of the scan bay
bed_angle = 20;       // the bed slopes down towards the front
bed_depth = 36;       // bed surface below the top of the body
cam_height = 120;     // camera above the card, square to the bed

// Where the camera head ends up, in normal (untilted) coordinates.
head_up = cam_height - bed_depth;
head_y = bay_y - head_up * sin(bed_angle);
head_z = body_h + head_up * cos(bed_angle);

// --- Colours -----------------------------------------------------------------------------
shell = "#f1f1ee";
dark = "#2b2f36";
accent = "#e8772e";
glass = "#9fb7c4";

$fn = 64;

module soft_box(size, r, e = edge_r) {
    // rounded-corner box with softened edges
    translate([e, e, e]) minkowski() {
        hull() for (x = [r - e, size[0] - r - e], y = [r - e, size[1] - r - e])
            translate([x, y, 0]) cylinder(r = r - e, h = size[2] - 2 * e, $fn = 48);
        sphere(r = e, $fn = 16);
    }
}

module body() {
    difference() {
        color(shell) translate([-body_w / 2, -body_d / 2, 0]) soft_box([body_w, body_d, body_h], corner_r);
        // drawer openings
        color(dark) for (i = [-1, 0, 1]) translate([i * (bin_w + bin_gap) - bin_w / 2, -body_d / 2 - 1, 14]) cube([bin_w, 30, bin_h]);
        // scan bay: a sloped well in the top
        color("#d9d9d5") translate([0, bay_y, body_h]) rotate([bed_angle, 0, 0]) translate([-46, -60, -40]) cube([92, 120, 60]);
    }
}

module drawers() {
    for (i = [-1, 0, 1]) translate([i * (bin_w + bin_gap), -body_d / 2 + 4, 14]) {
        color(dark) translate([-bin_w / 2 + 1, 0, 1]) soft_box([bin_w - 2, 26, bin_h - 2], 4, 1.5);
        // finger pull
        color(shell) translate([-14, -0.5, bin_h - 18]) cube([28, 2, 5]);
        // bin number, as dots
        for (n = [0 : i + 1]) color(accent) translate([-(i + 1) * 4 + n * 8, -0.6, 14]) rotate([-90, 0, 0]) cylinder(d = 4, h = 1);
    }
}

module scan_bay() {
    translate([0, bay_y, body_h]) rotate([bed_angle, 0, 0]) {
        // white bed with a card on it
        color("white") translate([-44, -58, -bed_depth]) cube([88, 116, 1]);
        color("#c9a46a") translate([-31.5, -44, -bed_depth + 1]) cube([63, 88, 0.6]);
        // soft light strips along both sides
        for (m = [0, 1]) mirror([m, 0, 0]) color("#fff6d8") translate([42, -55, -bed_depth + 6]) cube([1.5, 110, 8]);
    }
}

module hopper() {
    translate([0, 70, body_h - 2]) {
        difference() {
            color(shell) translate([-hop_w / 2, -hop_d / 2, 0]) soft_box([hop_w, hop_d, hop_h], 8, 3);
            color("#d9d9d5") translate([-hop_w / 2 + 4, -hop_d / 2 + 4, 8]) cube([hop_w - 8, hop_d - 8, hop_h]);
            // window in the side to see how many cards are left
            color("#d9d9d5") translate([hop_w / 2 - 5, -hop_d / 2 + 22, 18]) cube([10, hop_d - 44, hop_h - 34]);
        }
        color(glass, 0.6) translate([hop_w / 2 - 2.5, -hop_d / 2 + 22, 18]) cube([1, hop_d - 44, hop_h - 34]);
        // stack of cards inside
        color("#c9a46a") translate([-31.5, -44, 8]) cube([63, 88, 70]);
        color(dark) translate([-31.5, -44, 78]) cube([63, 88, 0.6]);
    }
}

module camera_arm() {
    // column on the right, arm reaching over to the camera head
    col_x = body_w / 2 - 30;
    arm_z = head_z + 34;
    color(dark) {
        translate([col_x, head_y, body_h - 2]) cylinder(d = 26, h = arm_z - body_h + 2);
        translate([col_x, head_y, arm_z]) sphere(d = 26);
        hull() {
            translate([col_x, head_y, arm_z]) sphere(d = 18);
            translate([0, head_y, arm_z]) sphere(d = 18);
        }
        // neck down to the head
        hull() {
            translate([0, head_y, arm_z]) sphere(d = 18);
            translate([0, head_y, head_z + 8]) sphere(d = 14);
        }
    }
    // camera head, square to the bed
    translate([0, head_y, head_z]) rotate([bed_angle, 0, 0]) {
        color(dark) hull() {
            cylinder(d = 44, h = 10);
            translate([0, 0, 10]) cylinder(d = 36, h = 4);
        }
        color("#111") translate([0, 0, -0.5]) cylinder(d = 14, h = 1);
        color(glass) translate([0, 0, -0.8]) cylinder(d = 8, h = 1);
        color(accent) translate([0, 0, 3]) rotate_extrude() translate([22, 0]) square([0.8, 2]);
    }
}

module status_strip() {
    // thin orange light along the top front edge, and a power button
    color(accent) translate([-body_w / 2 + corner_r, -body_d / 2 + 0.2, body_h - 10]) cube([body_w - 2 * corner_r, 1, 2]);
    color(dark) translate([body_w / 2 - 26, -body_d / 2 + 0.5, body_h - 26]) rotate([90, 0, 0]) cylinder(d = 10, h = 1);
    color(accent) translate([body_w / 2 - 26, -body_d / 2 - 0.4, body_h - 26]) rotate([90, 0, 0]) cylinder(d = 4, h = 0.6);
}

body();
drawers();
scan_bay();
hopper();
camera_arm();
status_strip();
