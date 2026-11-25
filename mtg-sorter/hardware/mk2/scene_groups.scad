// Sorter Mk2 in pieces, in machine coordinates, for pictures (guide/shot.py): openscad -D 'grp="..."'
include <joints.scad>
include <layout.scad>
use <frame.scad>
use <levels.scad>
use <scan.scad>
use <feeder.scad>
use <etray.scad>
use <covers.scad>
grp = "walls";
ex = 0;     // 1: exploded (each module pulled out the way it goes in)
cut = 0;    // 1: only the left half (x < 0), to see the card path from the side
wire_d = 2.4;
module wire(pts) for (i = [0 : len(pts) - 2]) hull() { translate(pts[i]) sphere(d = wire_d, $fn = 10); translate(pts[i + 1]) sphere(d = wire_d, $fn = 10); }
chan_z = [etray_z1 - 20, top_z - 40];   // as frame.scad
lid_len = (chan_z[1] - chan_z[0]) / 3 - 0.5;
// wires (concept): each module's wires to the right wall's trunk (the left side mirrors this)
L1 = lv1_z; L2 = lv2_z;
ir_z = [bin1_z + bin_h - full_z, bin3_z + bin_h - full_z];   // as levels.scad

module G() {
if (grp == "walls") { wall_r(); wall_l(); }
if (grp == "wall_r") wall_r();
if (grp == "wall_l") wall_l();
if (grp == "base") base_full();
if (grp == "bins") for (i = [0 : 3]) bin_at(i);
if (grp == "lvframes") { lv1_frame(); lv2_frame(); }
if (grp == "movers") { for (L = [lv1_z, lv2_z]) { lever_at(L, 0); lever_pin_at(L, 0); } carriage_at(lv1_z, 1, 0); carriage_at(lv2_z, 2, 0); }
if (grp == "doors") { door_at(lv1_z, false, 0); door_at(lv1_z, true, 0); }
if (grp == "servos") { servos_at(); stop_servo_placed(); }
if (grp == "shaft") { col_front(); liner_back(); }
if (grp == "ir") ir_holders_at();
if (grp == "scan") { carrier(); cam_arch(); cam_hood(); stop_bar(0); }
if (grp == "scan_white") { bed(); lightbar(1); lightbar(-1); }
if (grp == "feeder") { stand(); motor_lid(); hopper(); shoe(); }
if (grp == "roller") roller();
if (grp == "etray") etray();
if (grp == "covers") { front_cover(); back_low(); back_high(); lid_front(); lid_back(); }
if (grp == "covers_back") { back_low(); back_high(); lid_back(); }
if (grp == "drawer") drawer();
if (grp == "lids") for (m = [0, 1]) mirror([m, 0, 0]) for (k = [0 : 2]) translate([wall_in, chan_y, chan_z[0] + k * (lid_len + 0.5)]) into_face_run_z() trunk_lid("");
if (grp == "w_servo") {   // door servos (left) and pusher servos
    wire([[-50, -56, 362], [-105, -56, 371], [-106.5, 72, 371], [-112, 81, 371]]);
    wire([[-52, 60, 326], [-52, 58, 286], [-106, 58, 286], [-106, 72, 286], [-112, 81, 286]]);
    for (L = [L1, L2]) wire([[0, 101, L - 45], [0, 95, L - 30], [100, 92, L - 30], [112, 81, L - 30]]);
}
if (grp == "w_sense") {   // bin seated (hall) and bin full (IR), right side
    wire([[55, 30, 173.5], [55, 51, 173.5], [104, 51, 176], [104, 51, 196], [106, 72, 196], [112, 81, 196]]);
    wire([[95, 56, ir_z[0]], [104, 50, ir_z[0]], [104, 50, 286], [106, 72, 286], [112, 81, 286]]);
    wire([[95, 56, ir_z[1]], [104, 50, ir_z[1]], [104, 50, 100], [106, 72, 100], [112, 81, 100]]);
}
if (grp == "w_trunk") for (s = [-1, 1]) wire([[s * 116, 77, 372], [s * 116, 77, 70], [s * 100, 112, 60]]);
}
off = grp == "bins" ? [0, -230, 0] : grp == "drawer" ? [0, -230, 0]
    : grp == "wall_l" ? [-170, 0, 0] : grp == "wall_r" ? [170, 0, 0]
    : grp == "scan" || grp == "scan_white" ? [0, -40, 170]
    : grp == "feeder" || grp == "roller" ? [0, 140, 330]
    : grp == "etray" ? [0, 260, 0]
    : grp == "covers" ? [0, 0, 0] : [0, 0, 0];
translate(ex * off) if (cut == 1) intersection() { G(); translate([-300, -300, -10]) cube([300, 900, 900]); } else G();
