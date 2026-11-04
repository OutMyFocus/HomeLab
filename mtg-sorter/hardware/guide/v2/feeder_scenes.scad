// Picture scenes for the v2 feeder (see ../../MECHANISM_V2.md). Render with: python3 guide/v2/render.py
// Feeder coordinates: x across, y back (cards leave towards -y), z up, 0 = bottom of the stand.
include <../../feeder.scad>
include <helpers.scad>
part = "none";
step = 1;
eye = [300, -300, 260];  ctr = [0, 40, 70];

module motor() {   // N20: gearbox from gear_face_x outwards (+x), shaft towards -x
    translate([gear_face_x, roller_y - n20_w / 2 + 0.2, roller_z - n20_h / 2 + 0.2]) {
        color("#d4af37") cube([9, n20_w - 0.4, n20_h - 0.4]);
        color("#b8bcc2") translate([9, (n20_w - 0.4) / 2, (n20_h - 0.4) / 2]) rotate([0, 90, 0]) cylinder(d = 10, h = 17, $fn = 24);
        color("#c33") translate([26, 2, 1]) cube([5, 1, 1]);
        color("#333") translate([26, 4.5, 1]) cube([5, 1, 1]);
    }
    color("#e0e0e0") translate([gear_face_x - shaft_len, roller_y, roller_z]) rotate([0, 90, 0]) cylinder(d = 3, h = shaft_len, $fn = 16);
}
module orings() {   // the two 3 mm O-rings, in their grooves
    color(c_rubber) for (x = [-wheel_x, wheel_x]) translate([x, roller_y, roller_z]) rotate([0, 90, 0])
        rotate_extrude($fn = 48) translate([groove_root / 2 + oring_cs / 2, 0]) circle(d = oring_cs, $fn = 16);
}
module band() {    // rubber band from under the stand's bar up over the arm's tail
    color("#9c27b0") for (x = [-3, 3]) hull() {
        translate([x, tail_y - 3, arm_z0 + arm_t + 0.7]) rotate([0, 90, 0]) cylinder(d = 2.6, h = 2.6, center = true, $fn = 12);
        translate([x, 87, -0.7]) rotate([0, 90, 0]) cylinder(d = 2.6, h = 2.6, center = true, $fn = 12);
    }
    color("#9c27b0") for (z = [-0.7, arm_z0 + arm_t + 0.7]) translate([-3.6, z < 0 ? 87 : tail_y - 3, z]) rotate([0, 90, 0]) cylinder(d = 2.6, h = 7.2, $fn = 12);
}
module cards(n = 14) { color("#c9a46a") for (i = [0:n - 1]) translate([-card_w / 2, 2, floor_top + 0.02 + 0.33 * i]) cube([card_w, card_l, 0.3]); }
module coins() { color("#d4af37") for (x = [-15.5, 15.5], y = [-22, 22]) translate([x, y, 2.5]) cylinder(d = 26.5, h = 3.8, $fn = 40); }
module pad() { color(c_rubber) translate([-in_w / 2, -wall - 4.3 + 0.05, stand_h + floor_t + gate_gap - 0.6]) cube([in_w, 1.9, 1.9]); }
// the right half of the stand, cut away so you can see in
module stand_cut() { difference() { stand(); translate([-50, -50, -1]) cube([50 - out_w / 2 + wall + 0.01, 200, 200]); } }
module cutaway() { intersection() { children(); translate([-100, -80, -10]) cube([100 + 4.5, 220, 220]); } }

if (step == 1) {        // O-rings onto the roller
    color(c_new) roller();
    color(c_rubber) for (x = [-wheel_x, wheel_x]) translate([x, roller_y, roller_z + 22]) rotate([0, 90, 0])
        rotate_extrude($fn = 48) translate([groove_root / 2 + oring_cs / 2 - 1.5, 0]) circle(d = oring_cs, $fn = 16);
    for (x = [-wheel_x, wheel_x]) arrow([x, roller_y - 4, roller_z + 36], [x, roller_y - 4, roller_z + 18]);
    label(1, [-wheel_x, roller_y - 12, roller_z + 22], [-12, -10, 12]);
    label(2, [roller_x0 - 4, roller_y, roller_z], [-14, -6, -10]);
    label(3, [roller_x1, roller_y, roller_z], [10, -6, -14]);
}
else if (step == 2) {   // motor into the arm's tunnel
    color(c_new) arm();
    translate([30, 0, 0]) motor();
    arrow([gear_face_x + 54, roller_y, roller_z + 14], [gear_face_x + 36, roller_y, roller_z + 14]);
    screw([28.5, roller_y + n20_w / 2 + 2.5, roller_z], [0, -1, 0], 6, 2);
    label(1, [gear_face_x + 2, roller_y - n20_w / 2 - 2.5, roller_z], [-8, -14, 18]);
    label(2, [28.5, roller_y + n20_w / 2 + 6, roller_z], [10, 12, 16]);
    label(3, [-22, roller_y, roller_z + 6], [-12, -10, 16]);
}
else if (step == 3) {   // roller onto the shaft
    color(c_done) arm();
    motor();
    translate([0, 0, 22]) { color(c_new) roller(); orings(); }
    for (x = [-wheel_x, 0]) arrow([x, roller_y - 16, roller_z + 26], [x, roller_y - 16, roller_z + 8]);
    label(1, [roller_x1 - 2, roller_y, roller_z + 22], [12, -8, 14]);
    label(2, [-22.5, roller_y, roller_z + 2], [-14, -10, 6]);
}
else if (step == 4) {   // arm into the stand from the top, two M3 hinge screws
    color(c_done) stand();
    translate([0, 0, 60]) { color(c_new) arm(); color(c_new) roller(); orings(); motor(); }
    arrow([0, 40, stand_h + 100], [0, 40, stand_h + 70]);
    for (s = [-1, 1]) screw([s * (out_w / 2 - 1), pivot[0], pivot[1]], [-s, 0, 0], 8, 3);
    for (s = [-1, 1]) arrow([s * (out_w / 2 + 24), pivot[0], pivot[1]], [s * (out_w / 2 + 12), pivot[0], pivot[1]]);
    label(1, [out_w / 2, roller_y, roller_z - 6], [16, -14, -18]);
    label(2, [out_w / 2 + 8, pivot[0], pivot[1]], [14, 0, -22]);
}
else if (step == 5) {   // rubber band, seen from the side, stand cut open
    cutaway() { color(c_done) stand(); color(c_done) arm(); color(c_dark) roller(); orings(); }
    band();
    label(1, [0, tail_y - 1, arm_z0 + arm_t + 2], [16, 10, 20]);
    label(2, [0, 87, 6], [16, 10, -2]);
    label(3, [0, pivot[0], pivot[1]], [16, 0, 26]);
}
else if (step == 6) {   // hopper onto the pegs
    color(c_done) { stand(); arm(); roller(); } orings(); motor();
    color(c_new) translate([0, 0, 40]) hopper();
    for (x = [-1, 1]) arrow([x * (out_w / 2 - wall / 2), 6, stand_h + 42], [x * (out_w / 2 - wall / 2), 6, stand_h + 12]);
    label(1, [wheel_x, roller_y, floor_top + 1], [20, -26, 10]);
}
else if (step == 7) {   // gate: pad, hang it, thumb screw, lock screws
    color(c_done) { stand(); hopper(); arm(); roller(); } orings(); motor();
    translate([0, -24, 0]) { color(c_new) gate(); pad(); }
    arrow([0, -wall - 46, stand_h + 20], [0, -wall - 32, stand_h + 20]);
    screw([0, -wall - 5.5 - 24, stand_h + floor_t + gate_gap + gate_h - 2 + 14], [0, 0, -1], 12, 3);
    arrow([0, -wall - 5.5 - 24, stand_h + floor_t + gate_gap + gate_h + 30], [0, -wall - 5.5 - 24, stand_h + floor_t + gate_gap + gate_h + 18]);
    for (x = [-22, 22]) screw([x, -wall - 2.5 - 24 - 12, stand_h + 23], [0, 1, 0], 8, 3);
    label(1, [-in_w / 2 + 6, -wall - 4.3 - 24, stand_h + floor_t], [-12, -8, -18]);
    label(2, [0, -wall - 5.5 - 24, stand_h + floor_t + gate_h + 20], [14, -6, 10]);
    label(3, [22, -wall - 2.5 - 24 - 20, stand_h + 23], [14, -6, -6]);
    label(4, [0, -wall, stand_h + 15], [-14, 0, -24]);
}
else if (step == 8) {   // cards and weight
    color(c_done) { stand(); hopper(); gate(); }
    cards();
    translate([0, in_l / 2 + 2, floor_top + 14 * 0.33 + 85]) { color(c_new) weight(); coins(); }
    arrow([0, in_l / 2 - 30, floor_top + 80], [0, in_l / 2 - 30, floor_top + 40]);
    label(1, [-card_w / 2, 10, floor_top + 3], [-14, -14, -6]);
    label(2, [15.5, in_l / 2 + 24, floor_top + 14 * 0.33 + 92], [20, 4, 14]);
}
else if (step == 9) {   // how it works: side cut, wheels into the stack, gate holding the next card back
    cutaway() { color(c_done) { stand(); hopper(); gate(); } color(c_dark) arm(); color(c_new) roller(); orings(); cards(); color(c_done) translate([0, in_l / 2 + 2, floor_top + 14 * 0.33]) weight(); }
    pad();
    color("#c9a46a") translate([0.01, -60, floor_top + 0.02]) cube([card_w / 2, 58, 0.3]);
    arrow([20, -10, floor_top + 6], [20, -45, floor_top + 6]);
    label(1, [wheel_x, roller_y, floor_top + 1], [20, 10, -20]);
    label(2, [10, -wall - 3, stand_h + floor_t + gate_gap], [20, -14, 18]);
    label(3, [10, tail_y - 4, arm_z0 + 4], [20, 8, -12]);
}
