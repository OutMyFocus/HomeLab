// Card Catalog v1.2 drawer (MakerWorld 3016550, by Aspect of Frost): the bin the sorter drops
// cards into. Nic prints these from the MakerWorld 3MF (not in this repo), so this file only
// DRAWS one for the enclosure preview, from the sizes measured off that 3MF on 2026-10-25:
//
//   tray         76.0 wide x 67.4 tall x 223.0 long. 2 mm walls (3.5 mm along the bottom
//                band), honeycomb floor, divider grooves along the inside walls
//   front plate  86.0 wide x 109.0 tall x 8.0 thick, its bottom flush with the tray's. The
//                toploader pocket is open at the top, behind a 3 mm frame, and closed by a
//                clip-on bar ("drawer top", 65 x 11.8 mm) that hooks into the plate's top corners
//   handle       loop at the bottom of the plate, 16 mm proud, 58 mm wide
//   its box      plates sit side by side at 86.5 mm pitch in an 8 mm deep rebate at the mouth,
//                flush with the box face; the cubby behind is 76.6 wide, the tray rides on
//                the cubby floor, 113.5 mm of room above it for the plate and its bar
//
// Origin: middle of the plate's front face, on the floor. x across, y back, z up.

module cc_rr(w, l, r) { offset(r = r) offset(delta = -r) square([w, l], center = true); }

module card_catalog_drawer(w = 76, body_h = 67.4, l = 231, face_w = 86, face_h = 109, face_t = 8) {
    tray_l = l - face_t;
    // front plate: frame with the window the toploader shows through
    difference() {
        translate([-face_w / 2, 0, 0]) cube([face_w, face_t, face_h]);
        translate([-33, -1, 8]) cube([66, 3, 92]);
        translate([-38.5, 2.9, 5]) cube([77, 2.4, face_h]);   // the pocket, open at the top
    }
    color("#9fb7c4", 0.6) translate([-38, 3, 5]) cube([76, 2.2, 102]);   // 3 x 4 toploader
    // clip-on top bar
    translate([-32.5, -2.8, face_h - 11.8]) cube([65, 2.8, 11.8]);
    // handle loop
    linear_extrude(7) difference() {
        translate([0, -8]) cc_rr(58, 16, 7);
        translate([0, -9]) cc_rr(46, 8, 3);
    }
    // tray
    translate([-w / 2, face_t, 0]) difference() {
        cube([w, tray_l, body_h]);
        translate([2, 2, 2]) cube([w - 4, tray_l - 4, body_h]);
        // finger notch at the back
        translate([w / 2, tray_l + 1, body_h]) rotate([90, 0, 0]) cylinder(r = 12, h = 4, $fn = 32);
    }
}

card_catalog_drawer();
