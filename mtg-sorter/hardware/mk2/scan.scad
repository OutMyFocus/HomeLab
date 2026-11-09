// Sorter Mk2 scan module: the 30 degree scan bed, the stop bar, the camera and the lights, all
// located from the walls' scan rail, so the camera can never move relative to the card.
//
//   carrier    the sloped black plate under the bed, with a light box under the card (the
//              backlight), the stop bar's servo pocket and bearing, two side light bars, and long
//              skids at each end whose dovetail tongues ride the walls' scan rail. Slides in from
//              the front (take the front cover off first) and stops on the rail's end.
//   bed        white, 1.6 mm, drops into the carrier and clicks under two hooks: four PTFE tape
//              lands (6.5 mm, for 1/4" tape), a 65 mm centring channel with a funnel, the feeder
//              wheels' slots at the top, ArUco sticker pockets. Light from the box below comes
//              through it round the card, so the card's outline is sharp whatever its border or foil.
//   stop_bar   one full-width bar on two arms; the right arm takes the servo's own horn, the left
//              turns on a 3 mm steel pin. Up: the card rests on it. Down (60 degrees): it is below
//              the card's path.
//   cam_arch   two posts and a beam over the bed, riding the same rail as the carrier and keyed to
//              it. The Camera Module 3 clicks onto two pegs, square to the bed, 120 mm over the
//              card's centre; a twist-on hood holds a polarizer disc in front of the lens.
//   lightbar   x2, white diffusers: 5 LEDs of the WS2812B strip each, 27 degrees above the card,
//              outside the angle where foil glare bounces into the lens; a slot in front of each
//              takes a strip of polarizer film turned 90 degrees to the lens disc.
//
// Bed coordinates (on_bed): x across, s up the slope from the card surface's front edge, n square
// to the surface (+ = up, towards the camera).
include <joints.scad>
include <layout.scad>
part = "scan";
stop_down = 0;     // 0 = up (holding the card), 1 = down

module on_bed() translate([0, bed_e[0], bed_e[1]]) rotate([bed_a, 0, 0]) children();

// ---- bed ----------------------------------------------------------------------------------
bed_t = 1.6;
bed_s = [2.3, bed_len];
bed_half = 40;
lands = [9, 24.5];  land_w = 6.5;  land_h = 0.8;
chan_in = 32.5;  chan_wall = 6;  chan_h = 4;  funnel_s = [55, 90];  funnel_in = 38;
wheel_x = 16.75;  wheel_slot = [7.6, 14];      // feeder wheels come through the bed's top end
aruco = [[10], [50]];
box = [30, [5, 92], 12];        // light box under the card: x +-30, s 5..92, 12 deep
box_leds = [14, 36, 58, 80];    // 4 LEDs on the box floor (s); strip at 16.7 mm pitch is cut in 4 singles
// ---- carrier ------------------------------------------------------------------------------
car_t = 3;
car_half = wall_in - fit_slide; // 118.7 (its skids' outer faces)
skid_t = 6;  skid_h = 14;  skid_y = [0, 150];
// ---- stop bar -----------------------------------------------------------------------------
stop_axis = [0, -16];           // (s, n)
stop_half = 26;  stop_face = 2;  stop_n = [-6, 10];  stop_t = 3.7;
stop_turn = 60;
// ---- MG90S -----------------------------------------------------------------------------------
sv_len = 22.7;  sv_w = 12.2;  sv_shaft_off = 5.9;  sv_top = 6.6;  sv_tab_len = 32.2;  sv_body = 16.8;
stop_sv_x = 33.6;               // the stop servo's tab face (its top faces -x, its horn on the right arm)
// ---- lights --------------------------------------------------------------------------------
lb_x = 50;  lb_n = 25;  lb_s = [6, 90];
// ---- camera ---------------------------------------------------------------------------------
cam_board = [25, 24];  cam_holes = [[2, 2], [23, 2], [2, 14.5], [23, 14.5]];   // CM3: 21 x 12.5, 2.2 mm holes
arch_y = [14, 46];  arch_top = 419;  post_w = 14;

// ================================ BED ======================================================
module bed() {
    on_bed() difference() {
        union() {
            translate([-bed_half, bed_s[0], -bed_t]) cube([2 * bed_half, bed_s[1] - bed_s[0], bed_t]);
            for (x = lands) for (m = [-1, 1]) translate([m * x - land_w / 2, bed_s[0], -0.01]) cube([land_w, bed_s[1] - bed_s[0], land_h]);
            // centring channel walls, opening out to the funnel at the top
            for (m = [0, 1]) mirror([m, 0, 0]) hull() {
                translate([chan_in, bed_s[0], -0.01]) cube([chan_wall, funnel_s[0] - bed_s[0], chan_h]);
                translate([chan_in, funnel_s[0], -0.01]) cube([chan_wall, 0.01, chan_h]);
            }
            for (m = [0, 1]) mirror([m, 0, 0]) hull() {
                translate([chan_in, funnel_s[0], -0.01]) cube([chan_wall, 0.01, chan_h]);
                translate([funnel_in, funnel_s[1], -0.01]) cube([bed_half - funnel_in, bed_s[1] - funnel_s[1], chan_h]);
            }
            // two hooks under it click into the carrier
            for (m = [-1, 1]) translate([m * (box[0] + 4), 60, -bed_t]) rotate([180, 0, 0]) rotate([0, 0, m > 0 ? 0 : 180]) snap_hook(len = 6, t = 1.4, w = 6, lip = 0.6);
        }
        for (m = [-1, 1]) translate([m * wheel_x - wheel_slot[0] / 2, bed_s[1] - wheel_slot[1], -5]) cube([wheel_slot[0], wheel_slot[1] + 1, 10]);
        for (m = [-1, 1]) for (s = aruco) translate([m * (chan_in + chan_wall / 2) - 2.7, s[0] - 2.7, chan_h - 0.4]) cube([5.4, 5.4, 1]);
        // chamfer the front edge so the card leaves cleanly
        translate([-bed_half - 1, bed_s[0], 0]) rotate([45, 0, 0]) cube([2 * bed_half + 2, 1, 1]);
    }
}

// ================================ CARRIER ==================================================
module carrier_plate() {
    on_bed() difference() {
        union() {
            // the plate under the bed, across between the skids
            translate([-car_half, -6, -bed_t - car_t]) cube([2 * car_half, bed_len + 6, car_t]);
            // light box walls under the card
            translate([-box[0] - 2, box[1][0] - 2, -bed_t - box[2] - car_t]) cube([2 * box[0] + 4, box[1][1] - box[1][0] + 4, box[2] + car_t]);
            // rim the bed drops into
            for (m = [0, 1]) mirror([m, 0, 0]) translate([bed_half + 0.3, 0, -bed_t - 0.01]) cube([3, bed_len, bed_t + 1]);
            // stop bar bearings: a boss each side at the axis
            for (m = [-1, 1]) translate([m * (stop_half + 4) - 2, stop_axis[0], stop_axis[1]]) rotate([0, 90, 0]) cylinder(r = 6, h = 4);
            for (m = [-1, 1]) hull() {
                translate([m * (stop_half + 4) - 2, stop_axis[0] - 6, stop_axis[1] - 2]) cube([4, 12, 2]);
                translate([m * (stop_half + 4) - 2, 2, -bed_t - car_t]) cube([4, 14, 1]);
            }
            // the stop servo's box (right), its top through the bearing boss side
            translate([stop_sv_x, stop_axis[0], stop_axis[1]]) rotate([0, 0, 0]) stop_servo_box();
            // light bar seats
            for (m = [0, 1]) mirror([m, 0, 0]) translate([lb_x - 7, lb_s[0], -bed_t - car_t]) cube([14, lb_s[1] - lb_s[0], lb_n - 4 + bed_t + car_t]);
        }
        // light box inside (white PLA bed above it; line it with foil tape if you want more light)
        translate([-box[0], box[1][0], -bed_t - box[2]]) cube([2 * box[0], box[1][1] - box[1][0], box[2] + 0.01]);
        // LED pads on its floor: four 5 mm squares, the strip's wires along a groove
        for (s = box_leds) translate([-2.6, s - 2.6, -bed_t - box[2] - 0.6]) cube([5.2, 5.2, 0.61]);
        translate([-1.5, box[1][0], -bed_t - box[2] - 1]) cube([3, box[1][1] - box[1][0], 1.01]);
        // the stop bar swings through here
        translate([-stop_half - 1.5, -8, -20]) cube([2 * stop_half + 3, 10.3, 40]);
        for (m = [-1, 1]) translate([m * (stop_half + 4) - 2.01 + (m > 0 ? 0 : 0), stop_axis[0], stop_axis[1]]) rotate([0, 90, 0]) cylinder(d = m > 0 ? 7.6 : pin_press, h = 4.02, $fn = 32);
        translate([stop_sv_x, stop_axis[0], stop_axis[1]]) stop_servo_cut();
        // the bed's hook windows
        for (m = [-1, 1]) translate([m * (box[0] + 4) - 3.3, 60 - 8, -bed_t - car_t - 1]) cube([6.6, 8, car_t + 2]);
        // light bar slots (the bar drops in, the polarizer strip goes in front of it)
        for (m = [0, 1]) mirror([m, 0, 0]) translate([lb_x - 4.25, lb_s[0] - 0.01, 0]) cube([8.5, lb_s[1] - lb_s[0] + 0.02, lb_n]);
    }
}
module stop_servo_box() {   // shaft on the stop axis, pointing -x; body behind (+x), long side along -n
    translate([0, -sv_w / 2 - 2.5, -(sv_len - sv_shaft_off) - 2.5 - (sv_tab_len - sv_len) / 2]) cube([sv_body + 2.5, sv_w + 5, sv_tab_len + 5]);
}
module stop_servo_cut() {
    translate([-sv_top - 1, -sv_w / 2 - 0.25, -(sv_len - sv_shaft_off) - 0.25]) cube([sv_top + 1.01, sv_w + 0.5, sv_len + 0.5]);
    translate([0, -sv_w / 2 - 0.25, -(sv_len - sv_shaft_off) - (sv_tab_len - sv_len) / 2 - 0.25]) cube([sv_body + 10, sv_w + 0.5, sv_tab_len + 0.5]);
}
module stop_servo_body() {
    translate([0, -sv_w / 2, -(sv_len - sv_shaft_off)]) cube([sv_body, sv_w, sv_len]);
    translate([0, -sv_w / 2, -(sv_len - sv_shaft_off) - (sv_tab_len - sv_len) / 2]) cube([2.5, sv_w, sv_tab_len]);
    translate([-sv_top, -sv_w / 2, -(sv_len - sv_shaft_off)]) cube([sv_top, sv_w, sv_len]);
    translate([-sv_top, 0, 0]) rotate([0, -90, 0]) cylinder(d = 5, h = 3.5);
}

// the skids: machine-level bars along the rail, joined to the plate by a gusset wall each side
module skids() {
    for (m = [0, 1]) mirror([m, 0, 0]) {
        translate([car_half - skid_t, skid_y[0], rail_scan[0] - skid_h / 2]) cube([skid_t, skid_y[1] - skid_y[0], skid_h]);
        // tongue at the wall's face, with a neck over the 0.3 mm gap
        translate([wall_in, skid_y[0] + 2, rail_scan[0]]) multmatrix([[0, 0, 1, 0], [0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 1]]) translate([0, 0, -0.01]) dove_rail(skid_y[1] - skid_y[0] - 4);
        translate([car_half - 0.01, skid_y[0] + 2, rail_scan[0] - dove_w / 2]) cube([wall_in - car_half + 0.02, skid_y[1] - skid_y[0] - 4, dove_w]);
        // gusset: the wall between skid and the plate's end
        intersection() {
            translate([car_half - skid_t, skid_y[0], rail_scan[0]]) cube([skid_t, skid_y[1] - skid_y[0], 100]);
            on_bed() translate([-200, -6, -bed_t - car_t - 200]) cube([400, bed_len + 6, 200 + 0.01]);
        }
        // key socket at the skid's front end (the camera arch's foot keys in here)
        }
}
module carrier() difference() {
    union() { carrier_plate(); skids(); }
    for (m = [-1, 1]) translate([m * (car_half - skid_t / 2), skid_y[0], rail_scan[0] + skid_h / 2]) rotate([0, 0, 90]) key_socket_cut();
    // wire notch in the right skid at the wall's trunk
    translate([car_half - skid_t - 0.01, 62 - 6, rail_scan[0] - skid_h / 2 - 0.01]) cube([skid_t + 0.02, 12, 4]);
}

// ================================ STOP BAR ==================================================
module stop_bar() {
    on_bed() translate([0, stop_axis[0], stop_axis[1]]) rotate([stop_down * -stop_turn, 0, 0]) translate([0, -stop_axis[0], -stop_axis[1]]) difference() {
        union() {
            translate([-stop_half, stop_face - stop_t, stop_n[0]]) cube([2 * stop_half, stop_t, stop_n[1] - stop_n[0]]);
            for (m = [-1, 1]) hull() {
                translate([m * (stop_half - 1.5) - 1.5, stop_face - stop_t, stop_n[0]]) cube([3, stop_t, 1]);
                translate([m * (stop_half - 1.5) - 1.5, stop_axis[0], stop_axis[1]]) rotate([0, 90, 0]) cylinder(r = 4.5, h = 3);
            }
            // the right hub reaches the servo's horn
            translate([stop_half - 0.01, stop_axis[0], stop_axis[1]]) rotate([0, 90, 0]) cylinder(r = 4.5, h = 3.9);
            translate([-stop_half - 3.9, stop_axis[0], stop_axis[1]]) rotate([0, 90, 0]) cylinder(r = 4.5, h = 3.9);
        }
        // left: free on the steel pin; right: the servo's single-arm horn presses into a pocket
        translate([-stop_half - 5, stop_axis[0], stop_axis[1]]) rotate([0, 90, 0]) cylinder(d = pin_free, h = 12, $fn = 32);
        translate([stop_half + 3.91 - 2, stop_axis[0], stop_axis[1]]) rotate([0, 90, 0]) linear_extrude(2.01) { circle(d = 7.8); rotate(90) translate([0, -3.3]) square([20, 6.6]); }
        translate([stop_half - 2, stop_axis[0], stop_axis[1]]) rotate([0, 90, 0]) cylinder(d = 2.4, h = 10);
    }
}

// ================================ CAMERA ARCH ===============================================
cam_c = bedpt(card_s, cam_dist);        // the lens, (y, z)
module cam_arch() {
    difference() {
        union() {
            // feet on the rail, in front of the carrier's skids, keyed to them
            for (m = [0, 1]) mirror([m, 0, 0]) {
                translate([car_half - skid_t, front_y + 8, rail_scan[0] - skid_h / 2]) cube([skid_t, skid_y[0] - front_y - 8, skid_h]);
                translate([wall_in, front_y + 10, rail_scan[0]]) multmatrix([[0, 0, 1, 0], [0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 1]]) translate([0, 0, -0.01]) dove_rail(skid_y[0] - front_y - 10);
                translate([car_half - 0.01, front_y + 10, rail_scan[0] - dove_w / 2]) cube([wall_in - car_half + 0.02, skid_y[0] - front_y - 10, dove_w]);
                // post
                translate([car_half - post_w, arch_y[0], rail_scan[0] - skid_h / 2]) cube([post_w, arch_y[1] - arch_y[0], arch_top - rail_scan[0] + skid_h / 2]);
            }
            // the beam across, and the camera plate under it, square to the bed
            translate([-car_half, arch_y[0], arch_top - 12]) cube([2 * car_half, arch_y[1] - arch_y[0], 12]);
            translate([0, cam_c[0], cam_c[1]]) rotate([bed_a, 0, 0]) translate([-cam_board[0] / 2 - 4, -cam_board[1] / 2 - 4, 8]) cube([cam_board[0] + 8, cam_board[1] + 8, 3]);
            hull() {
                translate([0, cam_c[0], cam_c[1]]) rotate([bed_a, 0, 0]) translate([-cam_board[0] / 2 - 4, -cam_board[1] / 2 - 4, 10.99]) cube([cam_board[0] + 8, cam_board[1] + 8, 0.01]);
                translate([-cam_board[0] / 2 - 4, arch_y[0], arch_top - 12]) cube([cam_board[0] + 8, arch_y[1] - arch_y[0], 0.01]);
            }
        }
        // the camera's board sits under the plate on two pegs (added below); lens hole through it
        translate([0, cam_c[0], cam_c[1]]) rotate([bed_a, 0, 0]) translate([0, 0, -1]) cylinder(d = 9, h = 30);
        // ribbon slot, and its channel down the right post
        translate([0, cam_c[0], cam_c[1]]) rotate([bed_a, 0, 0]) translate([-9, cam_board[1] / 2 + 1, 5]) cube([18, 3, 10]);
        translate([car_half - post_w - 0.01, (arch_y[0] + arch_y[1]) / 2 - 9, rail_scan[0]]) cube([2.6, 18, arch_top - rail_scan[0] - 14]);
        // key sockets at the feet's back ends (one key joins each foot to its skid)
        for (m = [-1, 1]) translate([m * (car_half - skid_t / 2), skid_y[0], rail_scan[0] + skid_h / 2]) rotate([0, 0, 90]) key_socket_cut();
    }
    // camera pegs (two diagonal holes are enough), standing down from the plate
    translate([0, cam_c[0], cam_c[1]]) rotate([bed_a, 0, 0]) for (h = [cam_holes[0], cam_holes[3]])
        translate([h[0] - cam_board[0] / 2, h[1] - cam_board[1] / 2, 8.01]) mirror([0, 0, 1]) board_peg(peg_cam, 3);
}
// Lens hood: twists onto the camera plate around the lens, holds a 12 mm polarizer disc.
module cam_hood() {
    translate([0, cam_c[0], cam_c[1]]) rotate([bed_a, 0, 0]) difference() {
        translate([0, 0, -4]) cylinder(d = 16, h = 12);
        translate([0, 0, -5]) cylinder(d = 10, h = 14);
        translate([0, 0, -2.2]) cylinder(d = 12.4, h = 0.6);   // the disc's groove
        translate([-12.4 / 2, 0, -2.2]) cube([12.4, 10, 0.6]);   // ... and its way in
    }
}

// ================================ LIGHT BARS ===============================================
// White, 8 x lb_n, the LED strip (10 mm) stuck on its outer face, light out through its inner
// face and a polarizer strip in the slot in front of it.
module lightbar(m = 1) {
    on_bed() translate([m * lb_x, 0, 0]) difference() {
        translate([-4, lb_s[0] + 0.2, 0.2]) cube([8, lb_s[1] - lb_s[0] - 0.4, lb_n - 0.2]);
        translate([m * 4 - (m > 0 ? 1.2 : 0) - 0.01 * m, lb_s[0] - 1, 4]) cube([1.21, lb_s[1] - lb_s[0] + 2, 12]);   // strip pocket
        translate([-m * 4 + (m > 0 ? 0 : -0.8) + m * 0.4, lb_s[0] - 1, 2]) cube([0.4, lb_s[1] - lb_s[0] + 2, lb_n]);   // polarizer slot
    }
}

// ================================ ASSEMBLY =================================================
module scan_assembly() {
    color("#3a3f47") carrier();
    color("#f4f4f4") bed();
    color("#e8772e") stop_bar();
    color("#2b2b2b") cam_arch();
    color("#2b2b2b") cam_hood();
    color("#f4f4f4") { lightbar(1); lightbar(-1); }
    color("#3060c0") on_bed() translate([stop_sv_x, stop_axis[0], stop_axis[1]]) stop_servo_body();
}
module card_on_bed() on_bed() translate([-card_w / 2, stop_face, land_h]) cube([card_w, card_l, card_t]);

if (part == "scan") scan_assembly();
if (part == "carrier") carrier();
if (part == "bed") bed();
if (part == "stop_bar") stop_bar();
if (part == "cam_arch") cam_arch();
