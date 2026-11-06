// Holder for the servo-power DC jack (2026-11-06).
//
// The 5 V 4 A adapter plugs into a female 5.5 x 2.1 mm barrel jack with green screw terminals
// (ANLINK, about 38 x 14 x 13 mm). This holds that jack in the back panel's power cut-out
// (back_l, the 28 x 14 mm hole near the left rear corner as seen from the front), so the
// adapter plugs straight in from outside the box. No new holes: everything clamps through the
// cut-out that is already there, and the Pi's USB-C cable still passes beside the jack.
//
//   holder  inside the box: stands on the floor, its flange against the back panel's inside
//           face, a tongue reaching into the cut-out. The jack lies in its trough, nose through
//           the cut-out, held down by two zip ties.
//   bezel   outside the box: a cover plate over the cut-out with a hole for the plug. One M3
//           screw goes through it, through the cut-out, into the holder's tongue, and clamps
//           the panel between the two.
//
// Print: holder on its side (flat face down, as exported), bezel flat. No supports.
//   openscad -o stl/dc_jack_holder.stl -D 'part="holder"' dc_jack_holder.scad
//   openscad -o stl/dc_jack_bezel.stl  -D 'part="bezel"'  dc_jack_holder.scad
//   part="assembly" shows both in place on a stub of the back panel and floor.
//
// If your jack is a different size, change the jack_* numbers and re-export.

part = "assembly";

// ---- the jack ------------------------------------------------------------------
jack_l   = 38;      // front face (socket mouth) to the back of the green block
jack_w   = 14;      // widest, across (the green block)
jack_h   = 13;      // tallest (the green block)
nose_d   = 11.5;    // black body just behind the socket mouth (it tapers from there back)
fit      = 0.6;     // play around the jack in the trough

// ---- the panel and its cut-out (enclosure.scad: back_full, pt, floor groove) ---
pt       = 3;       // back panel thickness
cut_w    = 28;      // power cut-out
cut_h    = 14;
cut_z0   = 4.5;     // cut-out bottom above the floor's top face (6 up the panel, panel sits 1.5 in the groove)
clr      = 0.2;     // per side, parts in the cut-out

// ---- the holder ----------------------------------------------------------------
wall     = 2;
jack_u   = -14 + 1 + nose_d / 2;         // jack axis across the cut-out (cut-out centre = 0): at its left end
axis_z   = cut_z0 + cut_h / 2;           // jack axis height: the cut-out's middle
tongue_u = [7.6, cut_w / 2 - clr];       // tongue across the cut-out; the cable passes between nose and tongue
screw_u  = (tongue_u[0] + tongue_u[1]) / 2;
flange_t = 3;
flange_z = 24;                           // flange height
hole_d   = 2.8;                          // M3 self-tapping
stop_h   = 3;                            // back stop behind the green block
tie      = [5, 2.2];                     // zip-tie tunnels (along the jack x height)
tie_y    = [-9, -20];                    // ... their centres (y = 0 is the panel's inside face)

// ---- the bezel -----------------------------------------------------------------
bez_t    = 2.4;
bez_z    = [1, 24];                      // above the floor's top face (the floor plate sticks out 1.5 mm)
plug_d   = 7.5;                          // the plug's 5.5 mm sleeve goes through, the jack face does not
cable_w  = 7.5;                          // slot for the Pi's USB-C cable, open at the bottom

$fn = 64;

in_w = jack_w + fit;
u0 = jack_u - in_w / 2 - wall;           // the holder's flat (left) face
u1 = cut_w / 2 + 3;                      // flange right edge
floor_z = axis_z - jack_h / 2;           // trough floor = bottom of the green block
y_back = pt - jack_l - clr - 0.3;        // jack face flush with the panel's outside face
y_end = y_back - wall;

module rbox(p0, p1, r = 2) {             // box from p0 to p1, edges along y rounded
    hull() for (u = [p0[0] + r, p1[0] - r], z = [p0[2] + r, p1[2] - r])
        translate([u, p0[1], z]) rotate([-90, 0, 0]) cylinder(r = r, h = p1[1] - p0[1]);
}

// Coordinates: u across the cut-out (0 = its centre, + = towards the box's middle), y along the
// jack (0 = the back panel's inside face, + = out of the box), z up from the floor's top face.
module holder() {
    difference() {
        union() {
            // base + trough
            translate([u0, y_end, 0]) cube([in_w + 2 * wall, -flange_t - y_end, axis_z + 1]);
            // flange against the panel
            rbox([u0, -flange_t, 0], [u1, 0, flange_z], 2);
            // tongue in the cut-out
            translate([tongue_u[0], -0.01, cut_z0 + clr]) cube([tongue_u[1] - tongue_u[0], pt - clr + 0.01, cut_h - 2 * clr]);
            // screw boss behind the flange
            translate([screw_u, -flange_t + 0.01, axis_z]) rotate([90, 0, 0]) cylinder(d = 6.5, h = 4);
        }
        // trough
        translate([jack_u - in_w / 2, y_back, floor_z]) cube([in_w, -flange_t - y_back + 0.01, 50]);
        // back stop: only the bottom stop_h stays, the wires come out above it
        translate([jack_u - in_w / 2 + 2, y_end - 1, floor_z + stop_h]) cube([in_w - 4, wall + 2, 50]);
        // opening in the flange: the whole cut-out except the tongue (jack nose + cable)
        translate([-cut_w / 2, -flange_t - 1, cut_z0]) cube([tongue_u[0] - clr + cut_w / 2, flange_t + 2, cut_h]);
        // zip-tie tunnels under the trough, across
        for (y = tie_y) translate([u0 - 1, y - tie[0] / 2, floor_z - 1.2 - tie[1]]) cube([in_w + 2 * wall + 2, tie[0], tie[1]]);
        // M3 pilot through tongue, flange and boss
        translate([screw_u, pt + 1, axis_z]) rotate([90, 0, 0]) cylinder(d = hole_d, h = pt + flange_t + 6);
    }
}

module bezel() {
    difference() {
        rbox([u0 + 0.6, pt, bez_z[0]], [u1, pt + bez_t, bez_z[1]], 3);
        translate([jack_u, pt - 1, axis_z]) rotate([-90, 0, 0]) cylinder(d = plug_d, h = bez_t + 2);
        // countersunk M3 clearance
        translate([screw_u, pt - 1, axis_z]) rotate([-90, 0, 0]) cylinder(d = 3.4, h = bez_t + 2);
        translate([screw_u, pt + bez_t - 1.7, axis_z]) rotate([-90, 0, 0]) cylinder(d1 = 3.4, d2 = 6.6, h = 1.71);
        // USB-C cable slot, open at the bottom
        cu = (jack_u + nose_d / 2 + tongue_u[0]) / 2;
        translate([cu - cable_w / 2, pt - 1, bez_z[0] - 1]) cube([cable_w, bez_t + 2, cut_z0 + cut_h - 1.5 - bez_z[0] + 1]);
    }
}

module jack() {   // rough stand-in, for the assembly view
    color("#1d1d1d") hull() {
        translate([jack_u, pt, axis_z]) rotate([90, 0, 0]) cylinder(d = nose_d - 1, h = 3);
        translate([jack_u, pt - (jack_l - 11), axis_z]) rotate([90, 0, 0]) cylinder(d = jack_h, h = 1);
    }
    color("#3fbf5a") translate([jack_u - jack_w / 2, pt - jack_l, floor_z]) cube([jack_w, 11, jack_h]);
}

module panel_stub() {
    color("#2c3036", 0.6) difference() {
        translate([-40, 0, -1.5]) cube([80, pt, 40]);
        translate([-cut_w / 2, -1, cut_z0]) cube([cut_w, pt + 2, cut_h]);
    }
    color("#3a3f47") translate([-40, -60, -4]) cube([80, 60 + pt + 1.5, 4]);
}

if (part == "holder") translate([0, 0, -u0]) rotate([0, -90, 0]) holder();               // flat face down
else if (part == "bezel") translate([0, 0, pt + bez_t]) rotate([-90, 0, 0]) bezel();          // outside face down
else { panel_stub(); color("#e8e8e8") holder(); color("#d0d0d0") bezel(); jack(); }
