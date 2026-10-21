// What is INSIDE the full sifter (see sifter_concept.scad for the outside), in the style of the Roca Sifter: a countertop box
// with a card stack at the back, a camera tower, and three bins at the front.
//
// This is a PICTURE of the plan, not printable parts. The pieces get designed one at a
// time (feeder_test.scad is the first) and tested before the next one is built.
//
// Card path, back to front:
//   1. hopper: up to ~400 cards, face up
//   2. pick roller pushes the bottom card under the gate
//   3. card slides down the sloped scan bed and stops against the stop gate
//   4. camera in the tower takes the picture
//   5. stop gate drops, card slides into the chute
//   6. chute tilts left / centre / right into bin 1, 2 or 3

card_w = 63;
card_l = 88;
bed_angle = 20;       // steep enough for cards to slide on PLA
bed_len = 100;
bed_top = 165;        // height of the scan bed's back edge
cam_height = 120;     // camera above the card, square to the bed
bin_w = 76;
bin_l = 100;
bin_h = 85;           // holds about 250 cards
hopper_h = 130;       // holds about 400 cards

$fn = 48;

// --- bins ----------------------------------------------------------------------
module bins() {
    for (i = [-1, 0, 1]) translate([i * (bin_w + 2) - bin_w / 2, -bin_l - 70, 0]) difference() {
        cube([bin_w, bin_l, bin_h]);
        translate([2, 2, 2]) cube([bin_w - 4, bin_l - 4, bin_h]);
    }
}

// --- chute: a tray that slides cards down into a bin; a servo tilts it sideways ----
module chute(tilt = -25) {
    translate([0, -85, bin_h + 25]) rotate([0, tilt, 0]) rotate([-35, 0, 0])
        difference() {
            translate([-36, -60, 0]) cube([72, 100, 3]);
        }
}

// --- scan bed, tilted down towards the front -------------------------------------------
module bed() {
    translate([0, 0, bed_top]) rotate([bed_angle, 0, 0]) {
        color("white") translate([-40, -bed_len, -4]) cube([80, bed_len, 4]);
        // card resting against the stop gate
        color("tan") translate([-card_w / 2, -bed_len + 3, 0]) cube([card_w, card_l, 0.5]);
        // stop gate (servo flips it down to let the card go)
        color("orange") translate([-36, -bed_len - 3, 0]) cube([72, 3, 8]);
        // camera tower beside the bed (not in the card's path), square to the bed
        color("lightblue") {
            translate([56, -bed_len / 2 + 3 - 10, -4]) cube([20, 20, cam_height + 30]);
            translate([0, -bed_len / 2 + 3 - 10, cam_height]) cube([76, 20, 6]);
            translate([-17, -bed_len / 2 + 3 - 17, cam_height]) cube([34, 34, 3]);
        }
        color("green") translate([-12.5, -bed_len / 2 + 3 - 12, cam_height + 6]) cube([25, 24, 1]);
        // light walls on both sides
        for (m = [0, 1]) mirror([m, 0, 0]) color("white") translate([46, -bed_len, -4]) cube([5, bed_len, 34]);
    }
}

// --- hopper with the pick roller underneath (see feeder_test.scad) --------------------
module hopper() {
    in_w = card_w + 4; in_l = card_l + 4;
    translate([0, 0, bed_top]) {
        color("white") difference() {
            translate([-in_w / 2 - 3, -3, 0]) cube([in_w + 6, in_l + 6, hopper_h]);
            translate([-in_w / 2, 0, 3]) cube([in_w, in_l, hopper_h]);
            translate([-in_w / 2, -4, 3]) cube([in_w, 5, 4]);  // gate slot
        }
        color("tan") translate([-card_w / 2, 2, 3]) cube([card_w, card_l, 70]);
        color("black") translate([0, 20, -10]) rotate([0, 90, 0]) cylinder(d = 26.5, h = 14, center = true);
    }
}

// --- body: drawn as an open frame so the inside shows ------------------------------
module body() {
    color("dimgray") {
        for (x = [-125, 120], y = [-175, 110]) translate([x, y, 0]) cube([5, 5, bed_top - 2]);
        for (y = [-175, 110]) translate([-125, y, bed_top - 7]) cube([250, 5, 5]);
        for (x = [-125, 120]) translate([x, -175, bed_top - 7]) cube([5, 290, 5]);
        // shelf the hopper and bed sit on
        translate([-45, 0, bed_top - 12]) cube([90, 110, 5]);
    }
}

body();
bins();
color("orange") chute();
bed();
hopper();

