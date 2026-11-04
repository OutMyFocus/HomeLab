// Picture scenes for the v2 scan bed stop gate and door carriers (see ../../MECHANISM_V2.md).
// Render with: python3 guide/v2/render.py bed
include <../../enclosure.scad>
include <helpers.scad>
epart = "none";
step = 1;
eye = [300, -300, 300];  ctr = [0, 60, 160];

module wall_l() { mirror([1, 0, 0]) bed_side(true); }
module wall_r() { bed_side(false); }
module pin_servo(e = 0) {   // outside the left wall, shaft pointing in (+x)
    translate([-side_in - side_t + sv_top - e, pin_axis[0], pin_axis[1]]) rotate([0, 90, 0]) rotate([0, 0, -90]) servo_body();
}
module gate_at(a = 0) { translate([0, pin_axis[0], pin_axis[1]]) rotate([a, 0, 0]) translate([0, -pin_axis[0], -pin_axis[1]]) children(); }
module gate_horn() { translate([gate_left, pin_axis[0], pin_axis[1]]) rotate([0, -90, 0]) horn(); }
module card() { color("#c9a46a") on_bed() translate([-card_w / 2, 3, 0.05]) cube([card_w, card_l, 0.3]); }
module door_servo_in(right = true, e = 0) {   // body pointing in, towards the middle of the tray
    mirror([right ? 0 : 1, 0, 0]) translate([door_half, -ch_out - 2.5 + sv_top - e, hinge_z]) rotate([-90, 0, 0]) mirror([1, 0, 0]) servo_body();
}
bear_top = pivot_z - 20 + 32;

if (step == 1) {        // gate bearing onto the right end of the tilt bracket
    color(c_done) { wall_l(); tilt_bracket(); }
    color(c_new) translate([0, 0, 30]) gate_bearing();
    arrow([52.5, tilt_bracket_y + 3, bear_top + 62], [52.5, tilt_bracket_y + 3, bear_top + 36]);
    screw([52.5, tilt_bracket_y + 6.2, bear_top - 3.5 + 30], [0, -1, 0], 6, 2);
    arrow([52.5, tilt_bracket_y + 30, bear_top + 26.5], [52.5, tilt_bracket_y + 16, bear_top + 26.5]);
    label(1, [gate_right - 2, pin_axis[0], pin_axis[1] + 30], [-26, -20, 14]);
    label(2, [52.5, tilt_bracket_y + 12, bear_top + 26.5], [16, 14, 14]);
    label(3, [0, tilt_bracket_y, pivot_z + 12], [-20, -20, 26]);
}
else if (step == 2) {   // horn onto the stop gate's left plate
    color(c_new) stop_gate();
    translate([-14, 0, 0]) gate_horn();
    for (d = [-1, 1]) screw([gate_left - 1, pin_axis[0] + d * 5.5, pin_axis[1]], [1, 0, 0], 6, 1.6);
    arrow([gate_left - 40, pin_axis[0], pin_axis[1] + 20], [gate_left - 20, pin_axis[0], pin_axis[1] + 20]);
    label(1, [gate_left - 14, pin_axis[0] + 14, pin_axis[1]], [-12, -6, 22]);
    label(2, [gate_left + 1, pin_axis[0], pin_axis[1] + 3], [6, -14, 26]);
    label(3, [8, bed_y + 2, bed_z + 4], [0, -24, 22]);
}
else if (step == 3) {   // gate in: right hole over the bearing pin, horn onto the servo
    color(c_done) { wall_l(); tilt_bracket(); gate_bearing(); }
    pin_servo();
    translate([0, 0, 32]) { color(c_new) stop_gate(); gate_horn(); }
    for (x = [-40, 40]) arrow([x, pin_axis[0] - 16, pin_axis[1] + 70], [x, pin_axis[0] - 16, pin_axis[1] + 46]);
    label(1, [gate_right - 4, pin_axis[0], pin_axis[1]], [18, -18, -24]);
    label(2, [-side_in - side_t + 2, pin_axis[0], pin_axis[1]], [-20, -24, -22]);
    label(3, [0, bed_y + 2, bed_z + 36], [10, -26, 24]);
}
else if (step == 4) {   // gate down (Pins 50), slide the white bed plate down its grooves
    color(c_done) { wall_l(); tilt_bracket(); gate_bearing(); }
    pin_servo();
    gate_at(40) { color(c_new) stop_gate(); gate_horn(); }
    color(c_white) on_bed() translate([0, 55, 0]) bed_plate();
    on_bed() arrow([0, 120, 14], [0, 75, 14]);
    label(1, [-24, bed_y - 8, bed_z - 20], [-20, -22, -14]);
}
else if (step == 5) {   // Pins 90: teeth up through the slots, the card stops on them
    color(c_done) { wall_l(); tilt_bracket(); gate_bearing(); }
    color(c_white) on_bed() bed_plate();
    pin_servo();
    color(c_new) stop_gate(); gate_horn();
    card();
    label(1, [-24, bed_y + 1, bed_z + 6], [-16, -24, 18]);
}
else if (step == 6) {   // door carriers under the chute, servos pointing inwards
    color(c_done) chute();
    color(c_white) trapdoors();
    translate([0, 0, -30]) {
        color(c_new) for (m = [0, 1]) mirror([m, 0, 0]) door_carrier();
        door_servo_in(true); door_servo_in(false);
    }
    for (m = [-1, 1]) arrow([m * (carrier_x + 3), 0, pivot_z - 70], [m * (carrier_x + 3), 0, pivot_z - 40]);
    label(1, [door_half - 10, -ch_out - 8, hinge_z - 38], [10, -26, -20]);
    label(2, [door_half, ch_in - 3, hinge_z - 30], [24, 10, -16]);
}
module trapdoors() { for (m = [0, 1]) mirror([m, 0, 0]) trapdoor(); }
