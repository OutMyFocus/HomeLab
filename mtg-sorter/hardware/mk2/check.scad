// Sorter Mk2 clash checks: each `what` must come out empty (check.py runs them all).
include <joints.scad>
include <layout.scad>
use <frame.scad>
use <levels.scad>
use <etray.scad>
use <scan.scad>
use <feeder.scad>
use <covers.scad>
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
// the electronics tray slides in between the walls, on the base, behind the pusher servos
if (what == "etray") intersection() { etray(); union() { walls(); base_full(); bins(); frames(); servos_at(); movers(1); movers(-1); } }
// the power button's body (20 across, 36 deep behind the fascia) clears the paddles and cards
module pwr_body() translate([pwr_btn[0], front_y, lv1_z + pwr_btn[1]]) rotate([-90, 0, 0]) cylinder(d = 20, h = 40);
if (what == "button") intersection() { pwr_body(); union() { walls(); bins(); lv2_frame(); shaft(); servos_at(); movers(1); movers(0); card_sweep(lv1_z, 1); } }
// the scan module: carrier, bed and camera arch sit on their rail without touching the rest
module scan_fixed() { carrier(); bed(); cam_arch(); cam_hood(); lightbar(1); lightbar(-1); }
if (what == "scan_frame") intersection() { scan_fixed(); union() { walls(); frames(); bins(); servos_at(); shaft(); } }
if (what == "scan_movers") intersection() { scan_fixed(); union() { movers(1); movers(-1); movers(0); doors_open(); } }
if (what == "scan_parts") intersection() { carrier(); union() { bed(); cam_arch(); lightbar(1); lightbar(-1); } }
// the stop bar, up, half way and down, against everything near it
// (the pushers stay at the centre while it's down: the app puts it back up before a push, see MK2.md)
if (what == "stop_bar") intersection() { union() { stop_bar(0); stop_bar(0.5); stop_bar(1); } union() { scan_fixed(); frames(); walls(); movers(0); } }
if (what == "stop_up_push") intersection() { stop_bar(0); union() { movers(1); movers(-1); movers(0.5); movers(-0.5); } }
// the feeder cartridge on its rail, against the frame, the scan module and the stop bar
module feeder_fixed() { stand(); motor_lid(); hopper(); shoe(); }
if (what == "feeder_frame") intersection() { feeder_fixed(); union() { walls(); frames(); scan_fixed(); stop_bar(0); stop_bar(1); } }
if (what == "feeder_parts") intersection() { stand(); union() { hopper(); shoe(); roller(); motor_lid(); } }
if (what == "feeder_shoe") intersection() { shoe(); union() { hopper(); roller(); } }
if (what == "wheels") intersection() { wheel_sweep(0.3); union() { scan_fixed(); stand(); hopper(); shoe(); motor_lid(); } }
// the covers close round everything without touching it
module covers_all() { front_cover(); back_low(); back_high(); lid_front(); lid_back(); }
if (what == "covers") intersection() { covers_all(); union() { walls(); base_full(); frames(); scan_fixed(); stop_bar(1); feeder_fixed(); etray(); bins(); } }
if (what == "covers_each") intersection() { union() { front_cover(); back_low(); lid_back(); } union() { back_high(); lid_front(); } }
if (what == "drawer") intersection() { drawer(); union() { walls(); base_full(); frames(); bins(); shaft(); servos_at(); movers(1); movers(-1); } }
// every servo sits free in its pocket (the latches are tested by pulling one back: see MK2.md)
if (what == "servos_frames") intersection() { servos_at(); frames(); }
// pulled back 2 mm, each level servo runs into its latch (these must CLASH)
if (what == "door_latch") intersection() { servos_at(2, "doors"); lv1_frame(); }
if (what == "push1_latch") intersection() { servos_at(2, "push1"); lv1_frame(); }
if (what == "push2_latch") intersection() { servos_at(2, "push2"); lv2_frame(); }
// ... and pulled back 2 mm it hits the latch (this one must CLASH)
if (what == "stop_latch") intersection() { stop_servo_placed(2); carrier(); }
if (what == "stop_servo") intersection() { stop_servo_placed(); union() { carrier(); stop_bar(0); stop_bar(1); bed(); lightbar(1); } }
// the pushers through their whole stroke in eighths, not just the ends and the middle
module sweep(ps) for (p = ps) movers(p);
module near_movers() { static_all(); doors_shut(); scan_fixed(); stop_bar(0); ir_holders_at(); }
if (what == "sweep_left") intersection() { sweep([-0.875, -0.75, -0.625, -0.375, -0.25, -0.125]); near_movers(); }
if (what == "sweep_right") intersection() { sweep([0.125, 0.25, 0.375, 0.625, 0.75, 0.875]); near_movers(); }
if (what == "sweep_ends") intersection() { sweep([-1, -0.5, 0, 0.5, 1]); union() { scan_fixed(); stop_bar(0); ir_holders_at(); } }
// the lever's pin stays inside the carriage's fork at every position (it can't jump out)
module pin_in_fork(L, lv, p) difference() {
    intersection() { lever_pin_at(L, p); translate([-200, 68, -100]) cube([400, 4, 800]); }
    translate([p * push_stroke, 0, L]) fork_space();
}
if (what == "yoke") for (L = [lv1_z, lv2_z]) for (p = [-1, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1]) pin_in_fork(L, L == lv1_z ? 1 : 2, p);
// the bin-full sensor holders sit in their grooves (crush ribs left out) and clear everything else
if (what == "ir_frames") intersection() { ir_holders_at(false); frames(); }
if (what == "ir_rest") intersection() { ir_holders_at(); union() { walls(); bins(); base_full(); shaft(); servos_at(); doors_shut(); doors_open(); } }
