// Shared bits for the mechanism v2 picture scenes (feeder_scenes.scad, bed_scenes.scad).
// Same look as ../scenes.scad: grey = already fitted, orange = this step, pink = where it goes.
c_done = "#a3a9b1";  c_dark = "#7d848d";  c_new = "#ff7a1a";  c_arrow = "#d81b60";
c_white = "#f4f4f0";  c_rubber = "#222222";  c_metal = "#c0c4c8";

module arrow(from, to, d = 2.2) {
    v = to - from;  L = norm(v);  head = min(10, L * 0.45);
    b = acos(v[2] / L);  c = atan2(v[1], v[0]);
    color(c_arrow) translate(from) rotate([0, b, c]) {
        cylinder(d = d, h = L - head, $fn = 16);
        translate([0, 0, L - head]) cylinder(d1 = d * 3, d2 = 0, h = head, $fn = 20);
    }
}
module screw(at, dir = [0, 0, 1], len = 8, d = 3) {   // tip at `at`, head behind it, pointing along dir
    b = acos(dir[2] / norm(dir));  c = atan2(dir[1], dir[0]);
    color(c_metal) translate(at) rotate([0, b, c]) translate([0, 0, -len]) {
        cylinder(d = d, h = len, $fn = 12);
        translate([0, 0, -1.6]) cylinder(d = d * 1.9, h = 1.6, $fn = 16);
    }
}
// Numbered callout facing the camera (render passes eye and ctr), on a leader line to `at`.
module label(n, at, off = [0, 0, 30], r = 6) {
    d = eye - ctr;  el = atan2(d[2], norm([d[0], d[1]]));  az = atan2(d[1], d[0]) + 90;
    p = at + off;
    color("#1d2733") hull() { translate(at) sphere(d = 0.9, $fn = 8); translate(p) sphere(d = 0.9, $fn = 8); }
    translate(p) rotate([0, 0, az]) rotate([90 - el, 0, 0]) {
        color("#1d2733") cylinder(r = r, h = 0.8, center = true, $fn = 40);
        color("white") translate([0, 0, 0.5]) cylinder(r = r - 1, h = 0.8, center = true, $fn = 40);
        color("#1d2733") translate([0, 0, 0.9]) linear_extrude(0.6) text(str(n), size = r * 1.05, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
    }
}
// MG90S stand-in: shaft at the origin pointing +z, body along +x from the shaft.
module servo_body(len = 22.7, w = 12.2, off = 5.9, tab = 32.2, top = 6.6) {
    color("#2e6fd8") {
        translate([-off, -w / 2, -22.5]) cube([len, w, 22.5]);
        translate([-off - (tab - len) / 2, -w / 2, -top - 2.5]) cube([tab, w, 2.5]);
        cylinder(d = 11.8, h = 1.5, $fn = 24);
    }
    color("white") translate([0, 0, 1.5]) cylinder(d = 4.8, h = 3.5, $fn = 16);
    color("#333") translate([len - off - 1, -1.5, -20]) cube([8, 3, 3]);
}
// a double-arm servo horn, hub at the origin, lying in the xy plane, arms along y
module horn() {
    color("white") {
        cylinder(d = 7, h = 4, $fn = 24);
        hull() for (y = [-14, 14]) translate([0, y, 0]) cylinder(d = 4.5, h = 1.6, $fn = 16);
    }
}
