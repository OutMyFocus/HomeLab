// =====================================================================
//  Fujifilm X-H2 / X-H2S  — 3D-printable half cage  (v1, parametric)
// ---------------------------------------------------------------------
//  Base plate (Arca-Swiss grooves + anti-twist lip) + left side upright
//  (port window, 1/4"-20 nut traps) + short top arm with cold shoe.
//  Open on the grip side so the camera slides in from the right.
//
//  Coordinates (camera seen from BEHIND, as you shoot):
//    X = 0 at camera's LEFT side (port side), +X toward the grip
//    Y = 0 at camera's REAR face (bottom edge), +Y toward the lens
//    Z = 0 at camera's BOTTOM, +Z up
//
//  !!! Values marked MEASURE are estimates. Measure your camera with
//  !!! calipers and update them before printing the final version.
//
//  Print: lay the part on its OUTER left face (the default STL is already
//  rotated for this) -> no supports needed. PETG/ASA, 4-5 walls, 40%+ infill.
// =====================================================================

part = "print";        // "print" = rotated for printing, "assembly" = in place with ghost camera

// ---------- camera (MEASURE) ----------
cam_w        = 136.3;  // overall width incl. grip (spec)
cam_h        = 92.9;   // overall height (spec, EVF hump)
cam_d        = 48;     // MEASURE: body depth at the bottom, rear face -> front face (no grip)
left_shoulder_h = 80;  // MEASURE: height of the LEFT top shoulder (mode-dial side)
socket_x     = 52;     // MEASURE: tripod socket centre, from camera's left side
socket_y     = 20;     // MEASURE: tripod socket centre, from camera's rear face

// ---------- fit / layout ----------
side_gap     = 10;     // air gap between camera left side and upright (strap lug, port doors)
top_gap      = 3;      // clearance between left shoulder and top arm
base_t       = 10;     // base plate thickness
base_end_x   = socket_x + 20;  // where the base stops toward the grip (keep battery door free!)
lip_h        = 5;      // anti-twist lip height (keep low so the rear screen can tilt)
lip_t        = 4;

wall         = 9;      // upright thickness
up_y0        = 6;      // upright starts this far in front of rear face (vari-angle screen clearance)
up_y1        = 38;     // upright ends here (Y)
top_t        = 9;      // top arm thickness
top_len      = 40;     // how far the top arm reaches over the camera (from inside of upright)

// ---------- hardware ----------
q_clear      = 6.8;    // 1/4"-20 clearance hole
q_nut_af     = 11.4;   // 1/4"-20 hex nut across flats (7/16" = 11.11 + tolerance)
q_nut_t      = 6.0;    // nut pocket depth (nut is 5.56)
screw_cb_d   = 13;     // counterbore for camera screw head (from below)
screw_cb_h   = 5;      // counterbore depth
slot_len     = 18;     // camera screw slot length (along X) for adjustment

arca_w       = 38;     // Arca-Swiss plate width
arca_groove  = 3.5;    // groove depth each side (45 deg)

// cold shoe receiver (sliding from the rear)
shoe_w       = 19.0;   // inner slot width  (shoe foot is 18.6)
shoe_slot_h  = 2.3;    // slot height       (foot is ~2.0)
shoe_open    = 12.8;   // top opening       (neck ~12.5)
shoe_len     = 22;

$fn = 48;
eps = 0.01;

ux0 = -side_gap - wall;   // upright outer face
ux1 = -side_gap;          // upright inner face
top_z0 = left_shoulder_h + top_gap;
top_z1 = top_z0 + top_t;

// ---------------------------------------------------------------------
module hex_pocket(af, h) { cylinder(d = af / cos(30), h = h, $fn = 6); }

module base() {
    by0 = socket_y - arca_w/2;
    difference() {
        union() {
            translate([ux0, by0, -base_t]) cube([base_end_x - ux0, arca_w, base_t]);
            // rear anti-twist lip, extends the base back to the camera's rear face
            translate([ux1, -lip_t, -base_t]) cube([base_end_x - ux1, lip_t + by0 + eps, base_t + lip_h]);
        }
        // Arca grooves along X on front & back edges (45 deg V)
        for (s = [0, 1]) {
            yy = s == 0 ? by0 : by0 + arca_w;
            // diamond centred on the edge -> 45 deg V-groove, depth = arca_groove
            translate([(ux0 + base_end_x)/2, yy, -base_t + 3 + arca_groove])
                rotate([45, 0, 0])
                    cube([base_end_x - ux0 + 2, arca_groove * sqrt(2), arca_groove * sqrt(2)], center = true);
        }
        // camera screw slot + counterbore
        hull() for (dx = [-slot_len/2, slot_len/2])
            translate([socket_x + dx, socket_y, -base_t - 1]) cylinder(d = q_clear, h = base_t + 2);
        hull() for (dx = [-slot_len/2, slot_len/2])
            translate([socket_x + dx, socket_y, -base_t - 1]) cylinder(d = screw_cb_d, h = screw_cb_h + 1);
    }
}

module upright() {
    h = top_z1 + base_t;
    win_z0 = 10; win_z1 = top_z0 - 10;
    difference() {
        translate([ux0, up_y0, -base_t]) cube([wall, up_y1 - up_y0, h]);
        // port window (HDMI / USB-C / mic / headphone doors)
        translate([ux0 - 1, up_y0 + 7, win_z0]) cube([wall + 2, (up_y1 - up_y0) - 14, win_z1 - win_z0]);
        // 1/4"-20 holes with nut traps from the inside, two columns
        for (z = [win_z0 - 5 + 0, win_z1 + 5], y = [up_y0 + 9, up_y1 - 9])
            translate([ux0 - 1, y, z]) rotate([0, 90, 0]) {
                cylinder(d = q_clear, h = wall + 2);
                translate([0, 0, wall + 1 - q_nut_t]) hex_pocket(q_nut_af, q_nut_t + 1);
            }
    }
}

module top_arm() {
    difference() {
        union() {
            translate([ux0, up_y0, top_z0]) cube([wall + top_len, up_y1 - up_y0, top_t]);
            cold_shoe_body();
        }
        cold_shoe_cut();
        // 1/4"-20 hole in top arm, nut trap from below
        translate([ux1 + top_len - 9, (up_y0 + up_y1)/2, top_z0 - 1]) {
            cylinder(d = q_clear, h = top_t + 2);
            hex_pocket(q_nut_af, q_nut_t + 1);
        }
    }
}

shoe_cx = ux1 + 13;                 // cold shoe centre X
module cold_shoe_body() {
    translate([shoe_cx - (shoe_w + 6)/2, up_y0, top_z1 - 1])
        cube([shoe_w + 6, shoe_len, shoe_slot_h + 3]);
}
module cold_shoe_cut() {
    // slot (open at rear, y = up_y0)
    translate([shoe_cx - shoe_w/2, up_y0 - 1, top_z1]) cube([shoe_w, shoe_len - 3 + 1, shoe_slot_h]);
    translate([shoe_cx - shoe_open/2, up_y0 - 1, top_z1]) cube([shoe_open, shoe_len - 3 + 1, shoe_slot_h + 3]);
}

// inner-corner gussets (stay inside the side gap, so they never touch the camera)
module gussets() {
    g = side_gap - 1;
    for (y = [up_y0, up_y1 - 4]) {
        // base <-> upright
        translate([ux1 - eps, y, 0 - eps]) rotate([90, 0, 0]) translate([0, 0, -4])
            linear_extrude(4) polygon([[-1, -1], [g, -1], [-1, g]]);
        // top arm <-> upright
        translate([ux1 - eps, y, top_z0 + eps]) rotate([90, 0, 0]) translate([0, 0, -4])
            linear_extrude(4) polygon([[-1, 1], [g, 1], [-1, -g]]);
    }
}

module cage() { union() { base(); upright(); top_arm(); gussets(); } }

module ghost_camera() {
    %translate([0, 0, 0]) cube([cam_w, cam_d, left_shoulder_h]);
    %translate([30, 0, 0]) cube([45, cam_d - 10, cam_h]);          // EVF hump (rough)
    %translate([socket_x, cam_d, 35]) rotate([-90, 0, 0]) cylinder(d = 60, h = 50); // lens
}

if (part == "assembly") { cage(); ghost_camera(); }
else if (part == "cage") cage();
else rotate([0, -90, 0]) translate([-ux0, 0, 0]) cage();   // outer left face down on bed
