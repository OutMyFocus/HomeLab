// Pieces for the scan bed v3 pictures (render.py exports each `what` as an STL).
include <../../bed_chute.scad>
use <../../feeder.scad>
part = "none";
wall_z0 = 111;
what = "plate3";
slice = false;      // true: only a 4 mm slab at x = 18 (side section pictures)
module feeder_at() translate([0, 150, 111]) children();
module card3() on_bed() rotate([bp3_extra, 0, 0]) translate([-card_w / 2, 3, bp3_lift + bp3_rib_h + 0.05]) cube([card_w, card_l, 0.4]);
module piece() {
    if (what == "plate3") on_bed() bed_plate3();
    if (what == "plate2") on_bed() bed_plate();
    if (what == "flat") bed_plate3();
    if (what == "card") card3();
    if (what == "card2") on_bed() translate([-card_w / 2, 3, 0.05]) cube([card_w, card_l, 0.4]);
    if (what == "walls") { bed_side(false); mirror([1, 0, 0]) bed_side(true); }
    if (what == "gate") stop_gate(true);
    if (what == "hopper") feeder_at() hopper();
    if (what == "fgate") feeder_at() gate();
    if (what == "stand") feeder_at() stand();
    if (what == "stack") feeder_at() for (i = [0:9]) translate([-card_w / 2, 2, 99 + 0.32 * i]) cube([card_w, card_l, 0.3]);
    if (what == "tray") chute3_moving(0, 0, false);
    if (what == "weight") weight_solid();
}
if (slice) intersection() { piece(); translate([16, -200, -10]) cube([4, 600, 600]); }
else piece();
