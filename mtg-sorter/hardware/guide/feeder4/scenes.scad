// Pieces for the feeder box v4 pictures (render.py exports each `what` as an STL).
include <../../bed_chute.scad>
use <../../feeder4.scad>
use <../../feeder.scad>
part = "none";
what = "stand";
slice = false;      // true: only a 4 mm slab through the right wheel (side section pictures)
module F() translate([0, 150, 111]) children();
// a card just let go: its tail at the nip, sliding along the exit line onto the lands
module card_out() on_bed() translate([-31.5, 99.3 - 88, 3.62]) cube([63, 88, 0.3]);
module piece() {
    if (what == "bed") on_bed() bed_plate3();
    if (what == "walls") { bed_side(false); mirror([1, 0, 0]) bed_side(true); }
    if (what == "gate") stop_gate(true);
    if (what == "stand") F() stand4();
    if (what == "hopper") F() hopper4();
    if (what == "shoe") F() shoe4();
    if (what == "pads") F() pads();
    if (what == "roller") F() roller4();
    if (what == "motor") F() translate([22.5, 1.0 - 6.2, 82.7 - 5.2]) cube([26, 12.4, 10.4]);
    if (what == "stack") F() for (i = [0:24]) translate([-31.5, 0.6, 97.25 + 0.32 * i]) cube([63, 88, 0.3]);
    if (what == "card") card_out();
    if (what == "weight") F() translate([0, 46, 97.25 + 0.32 * 25]) weight_solid();
    if (what == "fence") translate([0, 31 + 150, 111 - 0.01]) linear_extrude(2) difference() {
        square([73 + 4.6, 128 + 4.6], center = true); square([73.6, 128.6], center = true); }
    if (what == "bridge") translate([-52, 110, 107]) cube([104, 150, 4]);
    // the parts as printed
    if (what == "p_stand") stand4();
    if (what == "p_hopper") translate([0, 0, -92]) hopper4();
    if (what == "p_shoe") rotate([-90, 0, 0]) shoe4();
    if (what == "p_roller") translate([0, 0, 20.5]) rotate([0, 90, 0]) roller4_body();
    if (what == "flatbed") bed_plate3();
}
if (slice) intersection() { piece(); translate([14.75, -200, -10]) cube([4, 600, 600]); }
else piece();
