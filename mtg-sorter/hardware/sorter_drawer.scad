// Sorter drawer: the bin the sorter drops cards into, shaped to slide into the
// cubbies of Nic's storage shelf (MakerWorld "Modular TCG Card Storage", jimpf2000),
// with a 3 x 4 toploader pocket in the front for a display card, like "Card Catalog".
//
// The outside size (w, h, l) is the one thing that has to match the shelf's cubby, and
// it comes from enclosure.scad (dr_w, dr_h, dr_l), so set it there. The numbers here
// are PLACEHOLDERS until the drawer from the MakerWorld file has been measured.
//
// Cards drop in flat from above and pile up at the back. Divider grooves along the
// sides take the same card dividers as the shelf's own drawers, so once a drawer is
// full you can stand the cards up and file it.

part = "drawer";      // "drawer" or "front" (the front plate with the toploader pocket, printed flat)

w = 80;  h = 100;  l = 250;      // outside size, from enclosure.scad
wall = 2;
floor_t = 2;
groove_pitch = 10;    // divider grooves along the inside walls
groove_w = 1.6;
groove_d = 1;

// 3 x 4 toploader: 76.5 x 102.5 x 1.6 (most brands are within half a millimetre)
tl_w = 77;  tl_h = 103;  tl_t = 2.2;
window = [66, 92];    // what shows through the front

$fn = 32;

module rrect(w, l, r) { offset(r = r) offset(delta = -r) square([w, l], center = true); }

module body(w, h, l) {
    difference() {
        translate([-w / 2, 0, 0]) cube([w, l, h]);
        translate([-w / 2 + wall, wall, floor_t]) cube([w - 2 * wall, l - 2 * wall, h]);
        // divider grooves
        for (y = [wall + 12 : groove_pitch : l - wall - 12], m = [0, 1]) mirror([m, 0, 0])
            translate([w / 2 - wall - groove_d, y - groove_w / 2, floor_t]) cube([groove_d + 0.01, groove_w, h]);
        // finger notch at the back, so the pile is easy to lift out
        translate([0, l + 1, h]) rotate([90, 0, 0]) cylinder(r = 12, h = wall + 2);
    }
}

// The front plate is a separate part so the pocket can print flat and clean. It is
// glued (or screwed, 2 x M2) to the drawer's front wall and stands 2 mm proud of it.
module front_plate(w, h) {
    t = tl_t + 2 + 1.2;   // pocket depth + back wall + front wall
    difference() {
        translate([-w / 2, 0, 0]) linear_extrude(t) translate([w / 2, h / 2]) rrect(w, h, 3);
        // toploader pocket, open at the top
        translate([-tl_w / 2 - 0.5, 5, 1.2]) cube([tl_w + 1, h, tl_t]);
        // window
        translate([-window[0] / 2, 5 + (tl_h - window[1]) / 2, -1]) cube([window[0], window[1], 3]);
        // finger pull along the bottom edge
        translate([-14, -1, t - 1.2]) cube([28, 6, 3]);
    }
}

// What enclosure.scad draws in its preview.
module sorter_drawer_preview(w, h, l) {
    body(w, h, l);
    translate([0, 0, 0]) rotate([90, 0, 0]) front_plate(w, h);
    color("#9fb7c4", 0.7) translate([-tl_w / 2, -tl_t - 1.2, 5]) cube([tl_w, tl_t, tl_h]);
}

if (part == "drawer") body(w, h, l);
else if (part == "front") front_plate(w, h);
else sorter_drawer_preview(w, h, l);
