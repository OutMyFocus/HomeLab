// Scenes for the picture assembly guide (ASSEMBLY_PICTURES.md / assembly_guide.html).
// Every part is drawn where it ends up in the machine, from the same modules the STLs are
// exported from, so the pictures follow the design. Parts already fitted are grey, the parts
// a step adds are orange (electronics keep their own colours), and arrows show where they go.
// Render all the pictures with: sh guide/render.sh
//
//   step = 0 .. 19 (see the if-chain at the end)

include <../enclosure.scad>
use <../feeder_test.scad>
epart = "none";

step = 0;
n20_w = 12.2;  n20_h = 10.2;   // from feeder_test.scad (use<> brings modules, not variables)

c_done = "#a3a9b1";  c_dark = "#7d848d";  c_new = "#ff7a1a";  c_arrow = "#d81b60";
c_white = "#f4f4f0";

// ---------- helpers ----------------------------------------------------------------
module arrow(from, to, d = 3) {
    v = to - from;  L = norm(v);  head = min(14, L * 0.45);
    b = acos(v[2] / L);  c = atan2(v[1], v[0]);
    color(c_arrow) translate(from) rotate([0, b, c]) {
        cylinder(d = d, h = L - head, $fn = 16);
        translate([0, 0, L - head]) cylinder(d1 = d * 3, d2 = 0, h = head, $fn = 20);
    }
}
module screw(at, dir = [0, 0, 1], len = 8, d = 3) {   // a screw at `at`, pointing along dir
    b = acos(dir[2] / norm(dir));  c = atan2(dir[1], dir[0]);
    color("#c0c4c8") translate(at) rotate([0, b, c]) {
        cylinder(d = d, h = len, $fn = 12);
        translate([0, 0, -1.6]) cylinder(d = d * 1.9, h = 1.6, $fn = 16);
    }
}

// Numbered callout facing the camera (render.py passes eye and ctr), on a leader line to `at`.
eye = [520, -760, 560];  ctr = [0, 90, 110];
lr = 9;   // callout radius, set per step
module label(n, at, off = [0, 0, 40], r = lr) {
    d = eye - ctr;  el = atan2(d[2], norm([d[0], d[1]]));  az = atan2(d[1], d[0]) + 90;
    p = at + off;
    color("#1d2733") hull() { translate(at) sphere(d = 1.2, $fn = 8); translate(p) sphere(d = 1.2, $fn = 8); }
    translate(p) rotate([0, 0, az]) rotate([90 - el, 0, 0]) {
        color("#1d2733") cylinder(r = r, h = 1, center = true, $fn = 40);
        color("white") translate([0, 0, 0.6]) cylinder(r = r - 1.4, h = 1, center = true, $fn = 40);
        color("#1d2733") translate([0, 0, 1]) linear_extrude(0.8) text(str(n), size = r * 1.05, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
    }
}

// ---------- electronics (simple stand-ins, real sizes) -------------------------------
// MG90S servo, shaft at the origin pointing +z, top of the body at z = 0, length along +x.
module servo() {
    color("#2e6fd8") {
        translate([-sv_shaft_off, -sv_w / 2, -22.5]) cube([sv_len, sv_w, 22.5]);
        translate([-sv_shaft_off - (sv_tab_len - sv_len) / 2, -sv_w / 2, -sv_top - 2.5]) cube([sv_tab_len, sv_w, 2.5]);
        translate([0, 0, 0]) cylinder(d = 11.8, h = 1.5, $fn = 24);
    }
    color("white") translate([0, 0, 1.5]) cylinder(d = 4.8, h = 3.5, $fn = 16);
    color("#333") translate([sv_len - sv_shaft_off - 1, -1.5, -20]) cube([8, 3, 3]);   // lead
}
module n20() {   // gearbox + motor, along +x from the origin, shaft along -x
    color("#d4af37") cube([9, n20_w - 0.2, n20_h - 0.2]);
    color("#b8bcc2") translate([9, (n20_w - 0.2) / 2, (n20_h - 0.2) / 2]) rotate([0, 90, 0]) cylinder(d = 10, h = 15, $fn = 24);
    color("#c33") translate([24, 2, 1]) cube([4, 1, 1]);
}
module pi5() {   // board corner at the origin, 56 across (x), 85 deep (y): USB + ethernet at +y,
                 // USB-C and micro HDMI on the +x edge, GPIO header along the -x edge
    color("#1f8a4c") cube([56, 85, 1.6]);
    color("#c9ccd0") {
        translate([38, 85 - 21, 1.6]) cube([16, 22, 13.5]);  // ethernet
        translate([21, 85 - 17, 1.6]) cube([14, 18, 16]);    // USB
        translate([4, 85 - 17, 1.6]) cube([14, 18, 16]);     // USB
        translate([50, 6, 1.6]) cube([7, 9, 3.2]);           // USB-C
        translate([50, 22, 1.6]) cube([7, 6, 3]);            // micro HDMI
        translate([50, 35, 1.6]) cube([7, 6, 3]);
    }
    color("#555") translate([20, 25, 1.6]) cube([15, 15, 2]);    // SoC
    color("#222") translate([1, 3.5, 1.6]) cube([5, 51, 8.5]);   // GPIO header
}
module pca9685() {   // 62 x 25
    color("#2457c5") cube([62, 25, 1.6]);
    color("#222") translate([8, 2, 1.6]) cube([40, 7.5, 2.5]);
    color("#e8c547") translate([8, 2, 4.1]) cube([40, 7.5, 6]);
    color("#2a9d4b") translate([24, 17, 1.6]) cube([12, 7, 9]);
}
module drv8833() {
    color("#7d3cbf") cube([18, 16, 1.6]);
    color("#222") for (y = [1, 13]) translate([1, y, 1.6]) cube([16, 2.5, 8]);
}
module barrel_jack() {
    color("#222") cube([30, 14, 12]);
    color("#2a9d4b") translate([18, 0, 12]) cube([12, 14, 6]);
}
module camera3() {   // Camera Module 3, lens at the origin pointing -z, board at z = 0
    color("#1f8a4c") translate([-12.5, -12, 0]) cube([25, 24, 1]);
    color("#222") translate([-4.25, -4.25, -5]) cube([8.5, 8.5, 5]);
    color("#444") translate([0, 0, -6.5]) cylinder(d = 7, h = 1.5, $fn = 24);
    color("#eee") translate([-8, 10, 1]) cube([16, 8, 0.3]);    // ribbon
}
module led_strip(len) { color("#fff2b0") cube([0.6, len, led_w]); }

// ---------- the parts in place ------------------------------------------------------
module floor_tiles(off = 0) {
    for (xi = [0, 1], yi = [0, 1]) translate([(xi * 2 - 1) * off, (yi * 2 - 1) * off, 0]) floor_tile(xi, yi);
}
floor_splices_xy = concat([for (x = [-floor_x + 30, 0, floor_x - 30]) [x, floor_seam_y, 90]],
                          [for (y = [floor_y0 + 40, dock_y1 - 40, floor_y1 - 30]) [0, y, 0]]);
feet_xy = [for (x = [-1, 1], y = [front_y + 14, yc, back_y - 14]) [x * (hw - 14), y]];

module backs(e = 0) { for (i = [0, 1]) translate([0, back_y - inset, floor_t + e]) rotate([90, 0, 0]) back_tile(i); }
module side_pieces(e = 0, which = [0, 1]) {
    for (m = which) mirror([m, 0, 0]) translate([0, 0, e]) {
        translate([-hw + inset, front_y + post_r - groove_d + 0.3, floor_t]) rotate([90, 0, 90]) side();
        translate([-hw + inset + pt, front_y + post_r - groove_d + 0.3 + side_piece, panel_top]) rotate([90, 0, 90]) rotate([180, 0, 0]) side();
    }
}
// fascia with its pocket face inside (the two end pieces are mirror images, so either fits either end)
module fascia(e = 0) {
    // (x, y, z) of the flat panel -> (x, z, y): up the panel is up, the pocket face (z = pt) faces in
    for (i = [0 : 2]) multmatrix([[1, 0, 0, 0], [0, 0, 1, floor_y0 - pt], [0, 1, 0, fascia_z0 + e], [0, 0, 0, 1]]) fascia_tile(i);
}
module fascia_lightbar(e = 0) { translate([0, floor_y0 + 1.2, fascia_z0 + light_y - 5 + e]) rotate([90, 0, 0]) light_bar(); }
module dividers(e = 0) { for (m = [0, 1]) mirror([m, 0, 0]) translate([0, 0, e]) place_divider(); }
module legs(e = 0) { for (x = [-1, 1]) translate([x * (bridge_half - 7), bridge_y1 - 8, floor_t + e]) leg(); }
module bridge(e = 0) { for (i = [0, 1]) translate([0, i == 1 ? e : 0, 0]) bridge_tile(i); }
module decks(e = 0, which = [[0, 0], [1, 0], [0, 1], [1, 1]]) { for (t = which) translate([0, 0, e]) deck_tile(t[0], t[1]); }

// mechanism parts
module bed_walls(e = 0) { translate([0, 0, e]) { bed_side(false); mirror([1, 0, 0]) bed_side(true); } }
module bed_plate_in(e = 0) { on_bed() translate([0, -e, 0]) bed_plate(); }
module rocker() { pin_rocker(); }
module pin_servo(e = 0) {   // on the outside of the left wall, shaft pointing in (+x)
    translate([-side_in - side_t + sv_top - e, pin_axis[0], pin_axis[1]]) rotate([0, 90, 0]) rotate([0, 0, -90]) servo();
}
module tilt_servo(e = 0) {  // behind the tilt bracket, shaft pointing forward (-y)
    translate([0, tilt_bracket_y + 6 - sv_top + e, pivot_z]) rotate([90, 0, 0]) servo();
}
module door_servo(right = true, e = 0) {   // in front of the trapdoor mount, shaft pointing back (+y)
    mirror([right ? 0 : 1, 0, 0]) translate([door_half, -ch_out - 2.5 + sv_top - e, hinge_z]) rotate([-90, 0, 0]) servo();
}
module leds() { for (m = [0, 1]) mirror([m, 0, 0]) on_bed() translate([side_in - 0.5, 6, led_n - led_w / 2]) led_strip(bed_len - 12); }
module towerpost(e = 0) { on_bed() translate([tower_x, card_s, -4 + e]) tower_post(); }
module camhead(e = 0) { on_bed() translate([0, card_s, cam_height + e]) camera_head(); }
module camera(e = 0) { on_bed() translate([0, card_s, cam_height + 6 + 0.1 + e]) camera3(); }
module sleeve(e = 0) { on_bed() translate([tower_x, card_s, 14 + e]) post_sleeve(); }
module headcover(e = 0) { on_bed() translate([0, card_s, cam_height + e]) head_cover(); }

module chute_frame() { children(); }   // chute parts are modelled in place, level
module trapdoors(open = false) {
    for (m = [0, 1]) mirror([m, 0, 0]) translate([door_half, 0, hinge_z]) rotate([0, open ? -90 : 0, 0]) translate([-door_half, 0, -hinge_z]) trapdoor();
}
module mounts() { for (m = [0, 1]) mirror([m, 0, 0]) trapdoor_mount(); }
module lugs() { for (m = [0, 1]) mirror([m, 0, 0]) hinge_lug(); }

// feeder, on its 92 mm stand on the bridge. feeder_test.scad's origin is the inside of the
// hopper's front wall, on the table; here that is (0, feeder_front_y, bridge_top).
f_floor_top = bridge_top + stand_h + 3;
f_roller_d = 20.5 + 6;
f_roller_z = f_floor_top + 0.8 - f_roller_d / 2;
module feeder_stand_in(e = 0) { translate([0, feeder_front_y, bridge_top + e]) import("../stl/feeder_stand_mid.stl"); }
module feeder_hopper_in(e = 0) { translate([0, feeder_front_y, bridge_top + stand_h + e]) hopper(); }
module feeder_gate_in(e = 0) { translate([0, feeder_front_y - 3 - 2.5 - e, f_floor_top + 0.45]) gate(); }
module feeder_roller_in(e = 0) { translate([0, feeder_front_y + 20, f_roller_z + e]) roller(); }
module feeder_motor_in(e = 0) { translate([14 / 2 + 0.5, feeder_front_y + 20 - n20_w / 2, f_roller_z - n20_h / 2 + e]) n20(); }
module feeder_all(e = 0) { feeder_stand_in(e); feeder_hopper_in(e); feeder_gate_in(0); feeder_roller_in(e); feeder_motor_in(e); }

module floor_electronics(e = 0) {
    translate([pi_pos[0], pi_pos[1], floor_t + 5 + e]) pi5();
    translate([pca_pos[0], pca_pos[1], floor_t + 5 + e]) pca9685();
    translate([-100, 232, floor_t + e]) drv8833();
    translate([-floor_x + 22, floor_y1 - 16, floor_t + e]) barrel_jack();
}

// whole sub-assemblies, for later steps
module shell_lower(c = c_done) {   // floor, posts, panels, dividers, legs
    color(c) { floor_tiles(); for (i = [0 : 3]) place_post(i); backs(); side_pieces(); fascia(); dividers(); legs(); }
    color(c_white) fascia_lightbar();
    floor_electronics();
}
module mech_on_bridge(c = c_done, with_head = false) {
    color(c) { bridge(); bed_walls(); tilt_bracket(); rocker(); towerpost(); chute(); mounts(); lugs(); }
    color(c_white) { bed_plate_in(); trapdoors(); }
    color(c) feeder_stand_in();
    color(c_white) feeder_hopper_in();
    color(c) feeder_gate_in();
    pin_servo(); tilt_servo(); door_servo(true); door_servo(false); leds(); feeder_motor_in();
    if (with_head) { color(c) camhead(); camera(); }
}
module drawers_in(out = [0, 0, 0]) {
    for (i = [0 : 2]) color(c_drawer[i]) translate([div_x[i], dock_y0 - out[i], floor_t])
        card_catalog_drawer(dr_w, dr_body_h, dr_l, dr_face_w, dr_face_h, dr_face_t);
}

// ---------- the steps ------------------------------------------------------------------
cam_y = card_s;   // shorthand
if (step == 0) {        // the finished machine
    shell_lower(c_dark); mech_on_bridge(c_dark, true);
    color(c_dark) { decks(); tower(); tower_lid(); sleeve(); headcover(); }
    drawers_in([0, 60, 0]);
}
else if (step == 1) {   // floor: four tiles, splices and feet underneath (seen from below)
    color(c_new) floor_tiles(10);
    color("#ffd166") for (s = floor_splices_xy) translate([s[0], s[1], -14]) rotate([0, 0, s[2]]) splice();
    for (s = floor_splices_xy) arrow([s[0], s[1], -40], [s[0], s[1], -16], 2.5);
    color("#333") for (f = feet_xy) translate([f[0], f[1], -30]) cylinder(d = 8, h = 2.5);
}
else if (step == 2) {   // electronics on the floor
    color(c_done) floor_tiles();
    floor_electronics(45);
    for (p = [[pi_pos[0] + 28, pi_pos[1] + 42], [pca_pos[0] + 31, pca_pos[1] + 12], [-91, 240], [-floor_x + 37, floor_y1 - 9]]) arrow([p[0], p[1], 42], [p[0], p[1], 10]);
    label(1, [pi_pos[0] + 28, pi_pos[1] + 30, 70], [30, 0, 30]);
    label(2, [pca_pos[0] + 10, pca_pos[1] + 12, 60], [-30, 0, 30]);
    label(3, [-91, 240, 60], [0, 0, 40]);
    label(4, [-floor_x + 30, floor_y1 - 9, 66], [-25, 0, 30]);
}
else if (step == 3) {   // corner posts onto their pegs
    color(c_done) floor_tiles(); floor_electronics();
    color(c_new) for (i = [0 : 3]) translate([0, 0, 50]) place_post(i);
    for (i = [0 : 3]) let(x = (i % 2 == 0 ? -1 : 1) * (hw - 9), y = i < 2 ? front_y + 9 : back_y - 9) arrow([x, y, 40], [x, y, 10]);
}
else if (step == 4) {   // back panel down the back posts (seen from behind)
    color(c_done) { floor_tiles(); for (i = [0 : 3]) place_post(i); }
    floor_electronics();
    color(c_new) backs(120);
    arrow([0, back_y + 15, 330], [0, back_y + 15, 240]);
}
else if (step == 5) {   // side panels
    color(c_done) { floor_tiles(); for (i = [0 : 3]) place_post(i); backs(); }
    floor_electronics();
    color(c_new) side_pieces(120);
    for (m = [-1, 1], y = [front_y + 90, back_y - 90]) arrow([m * (hw + 15), y, 330], [m * (hw + 15), y, 240]);
}
else if (step == 6) {   // fascia: three pieces, splices and the light bar, on the bench (inside face up)
    rotate([90, 0, 0]) translate([0, 0, 0]) {
        color(c_new) for (i = [0 : 2]) translate([(i - 1) * 8, 0, 0]) fascia_tile(i);
        color("#ffd166") for (x = fascia_seams, y = [16, 40]) translate([x, y, pt + 8]) splice();
        color(c_white) translate([0, light_y - 5, pt + 22]) light_bar();
    }
    for (x = fascia_seams, y = [16, 40]) arrow([x, -30, y], [x, -12, y], 2.5);
    arrow([0, -45, light_y + 1], [0, -26, light_y + 1], 2.5);
}
else if (step == 7) {   // fascia down the front posts
    color(c_done) { floor_tiles(); for (i = [0 : 3]) place_post(i); backs(); side_pieces(); }
    color(c_new) fascia(120);
    color(c_white) fascia_lightbar(120);
    arrow([0, front_y - 20, 330], [0, front_y - 20, 250]);
}
else if (step == 8) {   // dividers and rear legs (front and right side left out to see in)
    color(c_done) { floor_tiles(); for (i = [0, 2, 3]) place_post(i); backs(); side_pieces(which = [0]); }
    floor_electronics();
    color(c_new) { dividers(60); legs(60); }
    for (m = [-1, 1]) arrow([m * pitch / 2, 40, 190], [m * pitch / 2, 40, 140]);
    for (x = [-1, 1]) arrow([x * (bridge_half - 7), bridge_y1 - 8, 195], [x * (bridge_half - 7), bridge_y1 - 8, 150]);
}
else if (step == 9) {   // bridge: two halves and two splices (seen from below)
    color(c_new) bridge(12);
    color("#ffd166") for (x = [-26, 26]) translate([x, bridge_seam_y + 6, bridge_top - bridge_t - 16]) rotate([0, 0, 90]) splice();
    for (x = [-26, 26]) arrow([x, bridge_seam_y + 6, bridge_top - 45], [x, bridge_seam_y + 6, bridge_top - 20], 2.5);
}
else if (step == 10) {  // bed walls onto the bridge, bed plate into their grooves
    color(c_done) bridge();
    color(c_new) bed_walls(50);
    color(c_white) on_bed() translate([0, -70, 50]) bed_plate();
    for (x = [-1, 1], y = [bed_y + 12, bed_back_y - 12]) screw([x * (side_in + side_t / 2), y, bridge_top - bridge_t - 14], [0, 0, 1], 8);
    for (x = [-1, 1]) arrow([x * (side_in + side_t / 2), 100, bridge_top + 85], [x * (side_in + side_t / 2), 100, bridge_top + 55]);
    on_bed() arrow([0, -60, 52], [0, -15, 52]);
}
else if (step == 11) {  // tilt bracket, stop-pin servo and pin rocker (seen from the left)
    color(c_done) { bridge(); bed_walls(); }
    color(c_white) bed_plate_in();
    color(c_new) translate([0, 0, 0]) tilt_bracket();
    pin_servo(25);
    color(c_new) translate([0, -80, -10]) rocker();
    arrow([0, -20, rocker_bottom - 8], [0, 15, rocker_bottom - 8]);
    arrow([-side_in - side_t - 45, pin_axis[0], pin_axis[1]], [-side_in - side_t - 30, pin_axis[0], pin_axis[1]]);
    for (z = [pivot_z - 8, pivot_z + 2]) screw([-side_in - side_t - 12, tilt_bracket_y + 3, z], [1, 0, 0], 12);
    label(1, [-side_in, tilt_bracket_y, pivot_z - 18], [-40, -40, -30]);
    label(2, [-side_in - side_t - 25, pin_axis[0] + 10, pin_axis[1] + 6], [-20, 0, 35]);
    label(3, [-side_in + 6, pin_axis[0] - 80, pin_axis[1] - 4], [-20, -30, 30]);
}
else if (step == 12) {  // LED strips and the camera post
    color(c_done) { bridge(); bed_walls(); tilt_bracket(); rocker(); }
    color(c_white) bed_plate_in();
    pin_servo(); leds();
    color(c_new) towerpost(60);
    on_bed() arrow([tower_x, card_s, 150], [tower_x, card_s, 110]);
}
else if (step == 13) {  // chute, built on the bench: mounts + servos at the front, lugs at the back, doors
    color(c_new) chute();
    color(c_done) translate([0, 0, -25]) { mounts(); lugs(); }
    translate([0, 0, -25]) { door_servo(true, 22); door_servo(false, 22); }
    color(c_white) translate([0, 0, -70]) trapdoors();
    for (m = [-1, 1]) arrow([m * (door_half - 12), 0, hinge_z - 62], [m * (door_half - 12), 0, hinge_z - 32]);
    for (m = [-1, 1]) arrow([m * (door_half + 8), ch_in - 5, pivot_z - 36], [m * (door_half + 8), ch_in - 5, pivot_z - 10]);
    for (m = [-1, 1], y = [ch_in - 5, -ch_in + 5]) screw([m * (door_half + 8), y, pivot_z + 14], [0, 0, -1], 8, 2);
    label(1, [door_half + 14, -ch_out - 2.5, hinge_z - 25], [25, -10, -25], 6);
    label(2, [door_half + 7, ch_in - 3, hinge_z - 25], [30, 10, -15], 6);
    label(3, [door_half + 14, -ch_out - 26, hinge_z - 30], [0, -10, -30], 6);
    label(4, [door_half - 14, 0, pivot_z - 72], [0, -20, -30], 6);
}
else if (step == 14) {  // chute into the bridge, tilt servo through the bracket
    color(c_done) { bridge(); bed_walls(); tilt_bracket(); rocker(); towerpost(); }
    color(c_white) bed_plate_in();
    pin_servo(); leds();
    color(c_new) translate([0, 0, 0]) { chute(); mounts(); lugs(); }
    color(c_white) trapdoors();
    door_servo(true); door_servo(false);
    tilt_servo(30);
    arrow([0, tilt_bracket_y + 75, pivot_z], [0, tilt_bracket_y + 45, pivot_z]);
}
else if (step == 15) {  // feeder (built in Part 1) on its stand, into the fence on the bridge
    color(c_done) { bridge(); bed_walls(); tilt_bracket(); rocker(); towerpost(); chute(); mounts(); lugs(); }
    color(c_white) { bed_plate_in(); trapdoors(); }
    pin_servo(); tilt_servo(); door_servo(true); door_servo(false); leds();
    translate([0, 0, 90]) {
        color(c_new) { feeder_stand_in(); feeder_gate_in(); }
        color(c_white) feeder_hopper_in();
        color("#222") feeder_roller_in(); feeder_motor_in();
    }
    arrow([feeder_out_w / 2 + 20, stand_y0 + stand_l / 2, bridge_top + 100], [feeder_out_w / 2 + 20, stand_y0 + stand_l / 2, bridge_top + 10]);
    label(1, [-feeder_out_w / 2, stand_y0 + 10, bridge_top + 2], [-40, -20, 20]);
    label(2, [feeder_out_w / 2, feeder_front_y + 20, bridge_top + 90 + 75], [40, 0, 10]);
}
else if (step == 16) {  // the whole bridge into the box
    shell_lower(c_done);
    translate([0, 0, 140]) mech_on_bridge(c_new);
    for (x = [-1, 1]) arrow([x * (bridge_half + 30), 60, 300], [x * (bridge_half + 30), 60, 240]);
    for (x = [-1, 1], y = div_holes) screw([x * (bridge_half - 4), div_y0 + y, bridge_top + 140 + 10], [0, 0, -1], 8);
}
else if (step == 17) {  // post sleeve, deck
    shell_lower(c_done); mech_on_bridge(c_done);
    color(c_new) { sleeve(40); decks(80); }
    for (x = [-1, 1], y = [front_y + 7, back_y - 7]) screw([x * (hw - 7), y, deck_z + 100], [0, 0, -1], 8);
    arrow([0, -20, 330], [0, -20, 300]);
}
else if (step == 18) {  // camera on the head, head on the post, covers, hopper tower
    shell_lower(c_done); mech_on_bridge(c_done);
    color(c_done) { decks(); sleeve(); }
    color(c_new) camhead(60); camera(60);
    color(c_new) headcover(120);
    color(c_new) translate([0, 0, 90]) { tower(); }
    color(c_new) translate([0, 0, 150]) tower_lid();
    on_bed() arrow([tower_x, card_s, cam_height + 55], [tower_x, card_s, cam_height + 25]);
    arrow([0, tower_yc, deck_z + tower_h + 260], [0, tower_yc, deck_z + tower_h + 175]);
}
else if (step == 19) {  // drawers in
    shell_lower(c_dark); mech_on_bridge(c_dark, true);
    color(c_dark) { decks(); tower(); tower_lid(); sleeve(); headcover(); }
    drawers_in([0, 130, 0]);
    arrow([0, -360, 60], [0, -240, 60]);
}
else if (step == 20) {  // where all the electronics end up (shell left out)
    color(c_done) { floor_tiles(); bridge(); bed_walls(); tilt_bracket(); rocker(); towerpost(); chute(); mounts(); lugs(); camhead(); }
    color(c_white) { bed_plate_in(); trapdoors(); feeder_hopper_in(); }
    color(c_done) { feeder_stand_in(); feeder_gate_in(); }
    color("#222") feeder_roller_in();
    floor_electronics(); pin_servo(); tilt_servo(); door_servo(true); door_servo(false); leds(); feeder_motor_in(); camera();
    label(1, [pi_pos[0] + 40, pi_pos[1] + 60, floor_t + 20], [50, 30, 30]);
    label(2, [pca_pos[0] + 10, pca_pos[1] + 12, floor_t + 8], [-40, 30, 30]);
    label(3, [-91, 240, floor_t + 8], [0, 40, 30]);
    label(4, [-floor_x + 30, floor_y1 - 9, floor_t + 12], [-40, 20, 40]);
    on_bed() label(5, [0, card_s + 8, cam_height + 8], [-40, 0, 30]);
    on_bed() label(6, [side_in - 0.5, 70, led_n + 5], [-30, 0, 45]);
    label(7, [feeder_out_w / 2 + 8, feeder_front_y + 20, f_roller_z], [50, 0, 10]);
}
