// Sorter Mk2 clash checks: each `what` must come out empty (check.py runs them all).
include <joints.scad>
include <layout.scad>
use <frame.scad>
use <levels.scad>
what = "none";

module walls() { wall_r(); wall_l(); }
module bins() for (i = [0 : 3]) bin_at(i);
module frames() { lv1_frame(); lv2_frame(); }
module shaft() { col_front(); liner_back(); }
module static_all() { walls(); base_full(); bins(); frames(); shaft(); servos_at(); }
module doors_shut() { door_at(lv1_z, false, 0); door_at(lv1_z, true, 0); }
module doors_open() { door_at(lv1_z, false, 1); door_at(lv1_z, true, 1); }
module movers(p) { for (L = [lv1_z, lv2_z]) { lever_at(L, p); lever_pin_at(L, p); } carriage_at(lv1_z, 1, p); carriage_at(lv2_z, 2, p); }
// a card's path: lying on a level, pushed by p (0..1 right, 0..-1 left)
module card_at(L, p) translate([p * push_stroke, 0, L + 0.05]) translate([-card_w / 2, -card_l / 2, 0]) cube([card_w, card_l, card_t]);
module card_sweep(L, s) hull() { card_at(L, 0); card_at(L, s); }
// ... and falling flat from level 1 to level 2, centred or 2 mm off in x and y
module card_fall() for (o = [[-2, -1.5], [2, 1.5]]) translate([o[0], o[1], 0]) hull() { card_at(lv1_z, 0); card_at(lv2_z, 0); }

// the frames sit in the walls without touching anything else
if (what == "frames_walls") intersection() { frames(); walls(); }
if (what == "frames_bins") intersection() { frames(); union() { bins(); base_full(); shaft(); } }
if (what == "lv1_lv2") intersection() { lv1_frame(); lv2_frame(); }
if (what == "bins_frame") intersection() { bins(); union() { walls(); base_full(); shaft(); } }
if (what == "bins_each") intersection() { union() { bin_at(0); bin_at(3); } union() { bin_at(1); bin_at(2); } }
if (what == "servos") intersection() { servos_at(); union() { walls(); bins(); shaft(); doors_shut(); } }
// moving parts, both ends of their travel and the middle
if (what == "push_mid") intersection() { movers(0); union() { static_all(); doors_shut(); } }
if (what == "push_r") intersection() { movers(1); union() { static_all(); doors_shut(); } }
if (what == "push_l") intersection() { movers(-1); union() { static_all(); doors_shut(); } }
if (what == "push_half") intersection() { movers(0.5); union() { static_all(); doors_shut(); } }
if (what == "doors_mid") intersection() { union() { door_at(lv1_z, false, 0.5); door_at(lv1_z, true, 0.5); } union() { static_all(); movers(0); } }
if (what == "doors_open") intersection() { doors_open(); union() { static_all(); movers(0); } }
// the card's paths stay clear of everything but the floor it lies on and the paddle pushing it
if (what == "card_lv1_r") intersection() { card_sweep(lv1_z, 1); union() { walls(); bins(); frames(); shaft(); servos_at(); } }
if (what == "card_lv1_l") intersection() { card_sweep(lv1_z, -1); union() { walls(); bins(); frames(); shaft(); servos_at(); } }
if (what == "card_lv2_r") intersection() { card_sweep(lv2_z, 1); union() { walls(); bins(); frames(); shaft(); servos_at(); } }
if (what == "card_lv2_l") intersection() { card_sweep(lv2_z, -1); union() { walls(); bins(); frames(); shaft(); servos_at(); } }
if (what == "card_fall") intersection() { card_fall(); union() { walls(); bins(); frames(); shaft(); servos_at(); doors_open(); movers(0); } }
