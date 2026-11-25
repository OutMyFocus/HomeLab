// Pieces for the chute v3 / front bridge v3 pictures, each exported in machine coordinates as
// its own STL (render.py), then drawn in a browser with three.js (view.html, render.js).
include <../../enclosure.scad>
epart = "none";
what = "tray";
tilt = 0; open = 0;
module tilted() { translate([0, 0, pivot_z]) rotate([0, tilt, 0]) translate([0, 0, -pivot_z]) children(); }
module turn_about(p, a) { translate(p) rotate([0, -a, 0]) translate(-p) children(); }
module door_only(o) { turn_about([v3_hx, 0, v3_hz], o * crank3_open) door3(); }
module mech_only(o) {
    a = o * crank3_open;
    turn_about([v3_hx, 0, v3_hz], a) door_crank3();
    turn_about([sv3_x, 0, sv3_z], a) servo_crank3();
    translate([crank3_r * (cos(crank3_shut + a) - cos(crank3_shut)), 0, crank3_r * (sin(crank3_shut + a) - sin(crank3_shut))]) door_link3();
}
if (what == "tray") tilted() chute3();
else if (what == "frame") tilted() hinge_frame3();
else if (what == "doors") tilted() for (m = [0, 1]) mirror([m, 0, 0]) door_only(open);
else if (what == "mech") tilted() for (m = [0, 1]) mirror([m, 0, 0]) mech_only(open);
else if (what == "servos") tilted() for (m = [0, 1]) mirror([m, 0, 0]) translate([sv3_x, -ch_in, sv3_z]) servo_body3();
else if (what == "crank") for (m = [0, 1]) mirror([m, 0, 0]) door_crank3();
else if (what == "scrank") for (m = [0, 1]) mirror([m, 0, 0]) servo_crank3();
else if (what == "link") for (m = [0, 1]) mirror([m, 0, 0]) door_link3();
else if (what == "bridge") bridge_front3();
else if (what == "cap") bridge_cap3();
else if (what == "back") bridge_tile(1);
else if (what == "div") for (m = [0, 1]) mirror([m, 0, 0]) place_divider();
else if (what == "tiltbr") tilt_bracket();
else if (what == "old_front") bridge_tile(0);
else if (what == "splices") for (x = [-26, 26]) translate([x, bridge_seam_y, bridge_top - bridge_t]) rotate([0, 0, 90]) splice();
else if (what == "walls") { bed_side(false); mirror([1, 0, 0]) bed_side(true); }
else if (what == "legs") for (x = [-1, 1]) translate([x * (bridge_half - 7), bridge_y1 - 8, floor_t]) leg();
else if (what == "floor") for (xi = [0, 1], yi = [0, 1]) floor_tile(xi, yi);
else if (what == "feeder") translate([-feeder_out_w / 2, stand_y0, bridge_top]) cube([feeder_out_w, stand_l, stand_h]);
else if (what == "tiltservo") translate([0, tilt_bracket_y + 6 + 1, pivot_z]) rotate([90, 0, 0]) {
    translate([-sv_shaft_off, -sv_w / 2, -1]) cube([sv_len, sv_w, sv_top + 1]);
    translate([-sv_shaft_off - (sv_tab_len - sv_len) / 2, -sv_w / 2, sv_top]) cube([sv_tab_len, sv_w, 2.5]);
    translate([-sv_shaft_off, -sv_w / 2, sv_top + 2.5]) cube([sv_len, sv_w, 16]);
}
