// Sorter Mk2 electronics tray: every board on one tray that slides out of the back.
//
// The tray's back plate is the machine's lower back panel. Pull it by the finger recess: two
// magnets let go, it slides 120 mm out on the base's rails (the service loops allow that), and
// every plug is in reach. Nothing is screwed:
//   Pi 5            split pegs through its four holes (58 x 49), USB-C and both micro-HDMI facing
//                   the back plate's port window, so its own USB-C supply plugs in from outside
//   PCA9685         split pegs (55.9 x 19, the Adafruit layout; measure yours); a snap-on comb holds
//                   every servo plug on its header
//   DRV8833         a cradle with a snap hook over it
//   Wago 221-415 x2 a clip holder: 5 V and ground for servos, motor, lights and sensors
//   DC jack         panel-mount 5.5 x 2.1 mm in an 11 mm hole (its own nut)
//   patch bar       one labelled socket per module harness, at the front edge, under the trunks
include <joints.scad>
include <layout.scad>
part = "etray";

et_x = wall_in - fit_slide;    // the tray fills the width between the walls
et_floor = 3;
et_y0 = etray_y0;  et_y1 = back_in;
plate_top = back_up_z - reveal;            // flush with the upper back panel, one reveal below it

// board positions (x, y of the board's corner nearest -x, -y)
pi_at  = [-112, et_y1 - 2 - 56];   pi_sz = [85, 56];   pi_holes = [[3.5, 3.5], [61.5, 3.5], [3.5, 52.5], [61.5, 52.5]];
pca_at = [-6, 196];   pca_sz = [62.5, 25.4];   pca_holes = [[3.3, 3.2], [59.2, 3.2], [3.3, 22.2], [59.2, 22.2]];
drv_at = [70, 200];   drv_sz = [18.6, 16.4];
wago_at = [20, 120];  wago_sz = [30.2, 20.4, 8.6];   // 221-415, approximate: measure and adjust
jack_at = [96, 40];   // x, z of the DC jack in the back plate
stand = 6;            // boards stand this high on their pegs

module etray() {
    difference() {
        union() {
            // floor and back plate
            translate([-et_x, et_y0, base_top]) ccube([2 * et_x, et_y1 - et_y0, et_floor]);
            translate([-et_x, et_y1, base_top]) cube([2 * et_x, back_t, plate_top - base_top]);
            // side rails (stiffen the floor, guide the tray between the walls)
            for (s = [-1, 1]) translate([s > 0 ? et_x - 3 : -et_x, et_y0, base_top]) cube([3, et_y1 - et_y0, 16]);
            // patch bar across the front
            translate([-et_x, et_y0, base_top]) cube([2 * et_x, 8, 24]);
            // boards
            for (h = pi_holes) translate([pi_at[0] + h[0], pi_at[1] + h[1], base_top + et_floor - 0.01]) board_peg(peg_pi, stand);
            for (h = pca_holes) translate([pca_at[0] + h[0], pca_at[1] + h[1], base_top + et_floor - 0.01]) board_peg(peg_pi, stand);
            // DRV8833 cradle with a hook
            translate([drv_at[0] - 2, drv_at[1] - 2, base_top + et_floor - 0.01]) difference() {
                cube([drv_sz[0] + 4, drv_sz[1] + 4, 5]);
                translate([2 - 0.2, 2 - 0.2, 2]) cube([drv_sz[0] + 0.4, drv_sz[1] + 0.4, 10]);
                translate([2 + drv_sz[0] / 2 - 4, -1, 2]) cube([8, 30, 10]);   // its headers' pins pass here
            }
            translate([drv_at[0] + drv_sz[0] + 2, drv_at[1] + drv_sz[1] / 2, base_top + et_floor + 0.5]) rotate([0, 0, 180]) snap_hook(len = 5.5, t = 1.4, w = 5, lip = 0.8);
            // Wago holder: two pockets side by side, a lip each side holds them down
            translate([wago_at[0] - 2, wago_at[1] - 2, base_top + et_floor - 0.01]) difference() {
                cube([2 * wago_sz[0] + 6, wago_sz[1] + 4, wago_sz[2] + 1.5]);
                for (i = [0, 1]) translate([2 + i * (wago_sz[0] + 2) - 0.2, 2 - 0.2, 1]) cube([wago_sz[0] + 0.4, wago_sz[1] + 0.4, 20]);
                // wires in and out along y; the lever tops stay open
                translate([-1, 6, 4]) cube([2 * wago_sz[0] + 8, wago_sz[1] - 8, 20]);
            }
        }
        // the base's rails, underneath
        for (s = [-1, 1]) translate([s * 60, et_y0 - 1, base_top]) dove_slot_cut(et_y1 - et_y0 + back_t + 2, 3, 2);
        // port window for the Pi's USB-C and micro-HDMI side
        translate([pi_at[0] + 3, et_y1 - 1, base_top + et_floor + stand + pcb_t - 1]) cube([48, back_t + 2, 9]);
        // DC jack
        translate([jack_at[0], et_y1 - 1, jack_at[1]]) rotate([-90, 0, 0]) cylinder(d = 11.2, h = back_t + 2);
        // vents behind the Pi's cooler, and under it
        for (i = [0 : 6]) translate([pi_at[0] + 56 + i * 4, et_y1 - 1, base_top + 30]) cube([2, back_t + 2, 34]);
        for (i = [0 : 7]) translate([pi_at[0] + 10 + i * 8, pi_at[1] + 8, base_top - 1]) cube([3, 40, et_floor + 2]);
        // finger recess to pull it
        translate([0, et_y1 + back_t + 0.01, plate_top - 16]) rotate([90, 0, 0]) scale([1, 0.5, 1]) cylinder(d = 50, h = 3.5, $fn = 64);
        // magnets in the back plate's edges (the walls hold the other halves)
        for (s = [-1, 1]) for (z = [base_top + 20, etray_z1 - 16]) translate([s * (et_x + 0.01), et_y1 + back_t / 2, z]) rotate([0, s > 0 ? -90 : 90, 0]) magnet_cut();
        // patch bar sockets: JST-XH housings push in from the front and click (6.2 deep x n pitch)
        for (p = patch) translate([p[0], et_y0 - 0.01, base_top + 12]) xh_socket_cut(p[1]);
        for (p = patch) translate([p[0], et_y0 - 0.01, base_top + 20.5]) rotate([90, 0, 0]) mirror([0, 0, 1]) linear_extrude(0.6)
            text(p[2], size = 3, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
        // wire passes behind the patch bar and up from the base's sensor holes
        translate([-et_x + 6, et_y0 + 7.99, base_top + et_floor]) cube([2 * et_x - 12, 0.02, 1]);
    }
}
// JST-XH housing pocket for n pins (XHP: (n - 1) x 2.5 + 4.9 wide, 5.75 deep, 7 tall), through the bar
module xh_socket_cut(n) { w = (n - 1) * 2.5 + 4.9;  translate([-w / 2 - 0.2, 0, -3.5 - 0.2]) cube([w + 0.4, 8.02, 7.4]); }
// [x, pins, label]: left half = the power side, right half = the signal side
patch = [[-96, 2, "FEED"], [-74, 3, "LIGHT"], [-52, 3, "EXIT"], [-30, 2, "5V IN"],
         [8, 6, "BEAMS"], [36, 5, "BINS"], [62, 4, "BUTTON"], [90, 3, "SPARE"]];

// A comb that snaps over the PCA9685's servo headers so no plug can work loose.
module pca_comb() {
    difference() {
        cube([pca_sz[0] + 4, 12, 16]);
        translate([2, -1, -0.01]) cube([pca_sz[0], 14, 12.5]);   // over the plugs (12.5 tall above the board)
    }
    for (x = [0, pca_sz[0] + 4 - 1.6]) translate([x + (x > 0 ? 1.6 : 0), 6, 0]) rotate([0, 0, x > 0 ? 0 : 180]) translate([-1.6, 0, 0]) snap_hook(len = 16, t = 1.6, w = 8, lip = 0.8);
}

if (part == "etray") etray();
if (part == "pca_comb") pca_comb();
