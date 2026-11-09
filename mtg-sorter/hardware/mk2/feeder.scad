// Sorter Mk2 feeder: the proven v4 bottom feeder (one card per feed, 0 doubles in 125 feeds) as one
// cartridge that slides in from the back on the walls' top rail, with a magazine 2.3 x as tall.
//
// What it keeps from v4 (FEEDER_V4.md):
//   - The wheels sit right at the stack's mouth, on fixed bearings, so each card is driven until its
//     tail is out and nothing is left hanging.
//   - The separator is the shoe: the magazine's front wall slides straight up and down in two slots
//     and rests by its own weight (plus coins) on the wheels with a cork pad over each one. The
//     wheel grips the bottom card harder than the cork does, so the bottom card goes; the cork grips
//     the second card harder than two cards grip each other, so it stays. Nothing to adjust.
//   - The pad meets the wheels ahead of their top by the bed's own angle (30 degrees in Mk2), so the
//     card leaves along the bed, 0.8 mm over the PTFE tape lands: no drop, no bend.
// What is new:
//   - The magazine holds about 450 cards (141 mm) and stands up through the lid, so you load it
//     from the top without taking anything off. The shoe and its coins lift out the same way.
//   - A full magazine weighs 4 x what v4 had. The old box stalled its N20 with a full 180 cards, so:
//     two PTFE tape strips on the magazine floor (the bottom card slides on them) and the 6 V
//     50-60 RPM N20 (same size, 2.5 x the torque of the 150 RPM one). Keep the old motor for tests.
//   - No screws: the motor sits in a pod in the stand, a snap-on lid holds it down and a rib on the
//     lid holds it in. The hopper drops onto the stand's ridge (as v4). The cartridge's wings carry
//     dovetail tongues on the walls' feed rail and a magnet holds it home.
//
// Parts (set `part`): stand, hopper, shoe, roller, motor_lid; "feeder" = all of it in place.
include <joints.scad>
include <layout.scad>
part = "feeder";
$fn = 64;

module rbox(p, s) { translate(p) cube(s); }
module yz(x0, t) { translate([x0, 0, 0]) rotate([90, 0, 90]) linear_extrude(t) children(); }
function bed_s(y, n) = (y - bed_e[0] + n * sin(bed_a)) / cos(bed_a);   // s where the line n reaches y

// ---- the bed (scan.scad) -------------------------------------------------------------------
land_n = 0.8;                             // the PTFE tape lands' top over the bed's surface
exit_n = land_n + 0.8;                    // the card leaves the wheels this high

// ---- magazine ------------------------------------------------------------------------------
in_w = card_w + 4;  in_l = card_l + 4;    // 67 x 92 inside, as v4
wall = 3;  out_w = in_w + 2 * wall;       // 73
floor_t = 3;

// ---- roller (as v4: 3 mm O-rings over a 23 mm groove, 25x3.1 or 27x3.1 from the kit) ----------
oring = 3;  groove_root = 23;
wheel_d = groove_root + 2;
R = groove_root / 2 + oring;              // 14.5 over the O-rings
core_d = 16;
wheel_x = 16.75;                          // between the bed's lands (x 9 and 24.5)
wheel_w = 7;
stub_d = 5;  shaft_len = 9;
roller_x0 = -wheel_x - wheel_w / 2;
roller_x1 = 20.5;
gear_face_x = 22.5;
n20_w = 12.4;  n20_h = 10.4;  n20_len = 26;   // gearbox and motor, without the tabs

// ---- where the wheels go -------------------------------------------------------------------
nip_s = 98;                               // the nip, this far up the bed (the card's tail leaves here)
nip = bedpt(nip_s, exit_n);               // (y, z) = (134.1, 439.4)
Y0 = nip[0] - 1 + R * sin(bed_a);         // 140.3: the magazine's inside front (the wheels' top is 1 mm behind it)
wc = [nip[0] + R * sin(bed_a), nip[1] - R * cos(bed_a)];   // the wheels' axis (141.3, 426.8)
poke = 2.2;                               // the wheels stand this far over the magazine floor
floor_top = wc[1] + R - poke;             // 439.1
floor_z0 = floor_top - floor_t;
hopper_h = top_z - floor_top;             // 141: the magazine's top is flush with the lid
hop_y1 = Y0 + in_l + wall;                // 235.3, just inside the back panel

// ---- the shoe (v4's geometry at 30 degrees) -------------------------------------------------
function shoept(d, v) = [nip[0] + d * cos(bed_a) - v * sin(bed_a), nip[1] + d * sin(bed_a) + v * cos(bed_a)];
pad_x0 = wheel_x - 4;  pad_x1 = wheel_x + 4;
pad_d0 = -4.5;  pad_d1 = 3.0;
pad_t = 1.6;  bar_v = 0.6;  pocket = 1.0;  lead_v = 1.2;
d_back = (Y0 - nip[0]) / cos(bed_a);      // the shoe's back face is the magazine's inside front
d_front = -5;
shoe_half = in_w / 2 - 0.4;
shoe_t = 3;
bar_top = floor_top + 9;
tongue_y = [Y0 - 2.8, Y0];
tongue_z0 = floor_top + 7;
tongue_out = 2.1;
box_half = 16;  box_y0 = Y0 - 8.6;  box_z = [bar_top - 0.01, floor_top + 36];   // coin box
coin_y = [Y0 - 7.0, Y0 - 3.0];  coin_half = 13.9;
lip_y0 = Y0 - 4.6;
cut_n = exit_n + 0.6;
slot_y = [tongue_y[0] - 0.35, tongue_y[1] + 0.35];
slot_x1 = in_w / 2 + tongue_out + 0.25;
slot_bot = tongue_z0 - 1.6;

// ---- stand and wings -----------------------------------------------------------------------
stand_half = out_w / 2;                   // the stand is the magazine's width ...
pod_x1 = gear_face_x + n20_len + 2.5;     // ... plus the motor pod on the right (to x 51)
stand_y0 = wc[0] - 7;                     // 134.3
stand_z0 = wc[1] - 17;                    // 409.8
sw_t = 2.75;                              // its walls
ridge_w = 1.4;  ridge_h = 2.4;  groove_c = 0.3;
wing_z = [stand_z0, rail_feed[0] + 9];            // from the stand's foot (it prints upright) to 436
skid_top = rail_feed[0] + 12;                     // the skids rise over the magnet (it sits at +8)
wing_y = [rail_feed[1], hop_y1];
skid_t = 6;
car_out = wall_in - fit_slide;            // 111.7

// the space below (under) or above (over) the bed-parallel line n, in front of y = y1
module bed_side_of(n, y1, up) {
    a = bedpt(-50, n);  b = bedpt(200, n);  e = up ? 900 : 0;
    intersection() {
        yz(-200, 400) polygon([a, b, [b[0], e], [a[0], e]]);
        rbox([-200, y1 - 400, 0], [400, 400, 900]);
    }
}
module under_bed(n, y1) bed_side_of(n, y1, false);
module over_bed(n, y1) bed_side_of(n, y1, true);

// ============================ ROLLER ===========================================================
module roller_body() {
    function wheel(c) = [[c - wheel_w / 2, wheel_d / 2], [c - 1.6, wheel_d / 2], [c - 1.6, groove_root / 2],
                         [c + 1.6, groove_root / 2], [c + 1.6, wheel_d / 2], [c + wheel_w / 2, wheel_d / 2]];
    pts = concat([[roller_x0 - 4, 0], [roller_x0 - 4, stub_d / 2], [roller_x0, stub_d / 2]],
                 wheel(-wheel_x),
                 [[-wheel_x + wheel_w / 2 + (wheel_d - core_d) / 2, core_d / 2],
                  [wheel_x - wheel_w / 2 - (wheel_d - core_d) / 2, core_d / 2]],
                 wheel(wheel_x),
                 [[roller_x1, wheel_d / 2 - 0.25], [roller_x1, 0]]);
    difference() {
        rotate([0, 90, 0]) rotate_extrude() polygon([for (p = pts) [p[1], p[0]]]);
        translate([roller_x1 - shaft_len + 1, 0, 0]) rotate([0, 90, 0]) intersection() {   // the N20's D shaft
            cylinder(d = 3.15, h = shaft_len + 1, $fn = 32);
            translate([-2, -1.65, 0]) cube([4, 3.3, shaft_len + 1]);
        }
    }
}
module roller() translate([0, wc[0], wc[1]]) roller_body();
// the room a turning wheel needs (the bed, the carrier and the stand stay out of it)
module wheel_sweep(c = 0) translate([0, wc[0], wc[1]]) for (x = [-wheel_x, wheel_x])
    translate([x - wheel_w / 2 - c, 0, 0]) rotate([0, 90, 0]) cylinder(r = R + c, h = wheel_w + 2 * c);

// ============================ STAND (with its wings) ============================================
module ridge(c = 0, h = ridge_h) {
    rx = stand_half - sw_t / 2;
    for (x = [-rx, rx]) rbox([x - ridge_w / 2 - c, Y0 + 2 - c, floor_z0 - 0.01], [ridge_w + 2 * c, hop_y1 - sw_t / 2 - Y0 - 2 + ridge_w / 2 + 2 * c, h]);
    rbox([-rx - ridge_w / 2 - c, hop_y1 - sw_t / 2 - ridge_w / 2 - c, floor_z0 - 0.01], [2 * rx + ridge_w + 2 * c, ridge_w + 2 * c, h]);
}
module stand() {
    sh = stand_half;
    difference() {
        union() {
            // the box under the magazine
            difference() {
                rbox([-sh, stand_y0, stand_z0], [2 * sh, hop_y1 - stand_y0, floor_z0 - stand_z0]);
                rbox([-sh + sw_t, stand_y0 + sw_t, stand_z0 + 2.5], [2 * sh - 2 * sw_t, hop_y1 - stand_y0 - 2 * sw_t, 100]);
            }
            ridge();
            // left bearing block for the roller's stub (45 degrees underneath)
            bw = sh - sw_t + 0.01 - 21;
            hull() {
                rbox([-21 - bw, wc[0] - 6, wc[1] - 8], [bw, 12, floor_z0 - wc[1] + 8]);
                rbox([-21 - bw, wc[0] - 6, stand_z0 + 2], [0.01, 12, 1]);
            }
            // the motor pod on the right: the gearbox and motor lie in a channel, open at the top
            rbox([21, wc[0] - n20_w / 2 - 2.5, stand_z0], [pod_x1 - 21, n20_w + 5, wc[1] + n20_h / 2 - stand_z0]);
            // the wings, out to the skids on the walls' feed rail
            for (m = [0, 1]) mirror([m, 0, 0]) {
                x0 = sh - 0.01;
                rbox([x0, wing_y[0], wing_z[1] - 3], [car_out - x0, wing_y[1] - wing_y[0], 3]);              // top plate
                for (y = [wing_y[0], (wing_y[0] + wing_y[1]) / 2 - 1.5, wing_y[1] - 3])
                    rbox([x0, y, wing_z[0]], [car_out - x0, 3, wing_z[1] - wing_z[0]]);                     // ribs
                rbox([car_out - skid_t, wing_y[0], wing_z[0]], [skid_t, wing_y[1] - wing_y[0], skid_top - wing_z[0]]);   // skid
                translate([wall_in, wing_y[0], rail_feed[0]]) multmatrix([[0, 0, 1, 0], [0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 1]]) translate([0, 0, -0.01]) dove_rail(wing_y[1] - wing_y[0] - 2);
                rbox([car_out - 0.01, wing_y[0], rail_feed[0] - dove_w / 2], [wall_in - car_out + 0.02, wing_y[1] - wing_y[0] - 2, dove_w]);
                // a diagonal brace in the wing, stand to skid
                hull() {
                    rbox([x0, wing_y[1] - 6, wing_z[1] - 3], [1, 3, 3]);
                    rbox([car_out - skid_t - 1, wing_y[0] + 3, wing_z[1] - 3], [1, 3, 3]);
                }
            }
        }
        // in front, the stand stays under the scan bed (the carrier is cut away round it)
        over_bed(-2.4, Y0);
        // stub slot, open at the top through a 4.6 mm snap
        translate([-sh - 1, wc[0], wc[1]]) rotate([0, 90, 0]) cylinder(d = stub_d + 0.6, h = sh - 21 + 0.5);
        hull() {
            translate([-sh - 1, wc[0], wc[1] + 1.5]) rotate([0, 90, 0]) cylinder(d = 4.6, h = sh - 21 + 0.5);
            translate([-sh - 1, wc[0], floor_z0 + 1]) rotate([0, 90, 0]) cylinder(d = 4.6, h = sh - 21 + 0.5);
        }
        // the roller's turning room
        translate([-21.6, wc[0], wc[1]]) rotate([0, 90, 0]) cylinder(r = wheel_d / 2 + 1, h = 43.2);
        wheel_sweep(1);
        // gearbox and motor channel, open at the top (the lid closes it), the wires out at the end
        // (the motor slides in from the right, onto the roller's shaft; the lid's end rib closes it)
        rbox([gear_face_x, wc[0] - n20_w / 2, wc[1] - n20_h / 2], [pod_x1 - gear_face_x + 1, n20_w, 40]);
        translate([gear_face_x - 3, wc[0], wc[1]]) rotate([0, 90, 0]) cylinder(d = 5, h = 4);   // its boss and shaft
        rbox([gear_face_x - 0.8, wc[0] - n20_w / 2 - 2.8, wc[1] + n20_h / 2 - 0.01], [pod_x1 - gear_face_x + 2, n20_w + 5.6, 2.4]);   // the lid sits in here
        // notches the lid's hooks catch in, both sides of the pod
        for (s = [0, 1]) translate([0, wc[0], 0]) mirror([0, s, 0]) rbox([(stand_half + pod_x1) / 2 - 4.4, n20_w / 2 + 2.5 - 1.0, lid_catch - 2.2], [8.8, 1.01, 2.2 + 0.4]);
        // magnets in the skids' faces, opposite the wall's at the rail's closed end
        for (m = [0, 1]) mirror([m, 0, 0]) translate([wall_in - 2.5, rail_feed[1] + 8, rail_feed[0] + dove_w / 2 + 5]) rotate([0, 90, 0]) magnet_cut();
        // lighten the stand's floor
        for (y = [stand_y0 + 30 : 20 : hop_y1 - 20]) rbox([-sh + 8, y, stand_z0 - 1], [2 * sh - 16, 12, 5]);
    }
}
// The motor pod's lid: snaps over the channel, presses the gearbox down, and its end rib stops the
// motor sliding out (the wires leave through a notch in the rib).
lid_hook = n20_h + 2;                       // the hooks reach this far down the pod's sides ...
lid_catch = wc[1] + n20_h / 2 - lid_hook;   // ... and catch in notches here
module motor_lid() {
    l = pod_x1 - gear_face_x + 0.5;  wy = n20_w + 5;
    difference() {
        translate([gear_face_x - 0.5, wc[0] - wy / 2, wc[1] + n20_h / 2]) {
            cube([l, wy, 2]);
            translate([2, 2.5 + 0.2, -0.2]) cube([l - 7, n20_w - 0.4, 0.21]);                  // presses on the gearbox and motor
            translate([n20_len + 0.5 + 0.4, 2.5 + 0.2, -n20_h + 1]) cube([1.6, n20_w - 0.4, n20_h - 1 + 0.01]);   // behind the motor
        }
        translate([gear_face_x + n20_len + 0.3, wc[0] - 2.5, wc[1] - 2]) cube([3, 5, 4]);         // the wires
        over_bed(-2.4, Y0);
    }
    for (s = [0, 1]) translate([0, wc[0], 0]) mirror([0, s, 0])
        translate([(stand_half + pod_x1) / 2, n20_w / 2 + 2.5 + 0.2 + 1.4, wc[1] + n20_h / 2 + 0.01]) rotate([0, 0, -90]) rotate([180, 0, 0]) snap_hook(len = lid_hook, t = 1.4, w = 8, lip = 0.6);
}

// ============================ MAGAZINE ===========================================================
module hopper() {
    z0 = floor_z0;
    difference() {
        union() {
            rbox([-out_w / 2, Y0, z0], [out_w, in_l + wall, floor_t]);                                     // floor
            for (x = [-out_w / 2, in_w / 2]) rbox([x, lip_y0, z0], [wall, hop_y1 - lip_y0, floor_t + hopper_h]);
            rbox([-out_w / 2, hop_y1 - wall, z0], [out_w, wall, floor_t + hopper_h]);                   // back
        }
        under_bed(cut_n, Y0);
        lz = bedpt(bed_s(Y0, cut_n), cut_n)[1];
        yz(-out_w, 2 * out_w) polygon([[Y0 + 0.01, lz], [Y0 - 20, lz + 20.01], [Y0 - 20, 0], [Y0 + 0.01, 0]]);
        for (x = [-wheel_x, wheel_x]) rbox([x - wheel_w / 2 - 1, Y0 - 1, z0 - 1], [wheel_w + 2, 14, floor_t + 2]);
        translate([0, Y0, z0 + floor_t]) rotate([45, 0, 0]) cube([2 * out_w, 1.6, 1.6], center = true);
        // the shoe's slots, open at the top
        for (m = [0, 1]) mirror([m, 0, 0]) rbox([in_w / 2 - 1, slot_y[0], slot_bot], [slot_x1 - in_w / 2 + 1, slot_y[1] - slot_y[0], 300]);
        ridge(groove_c, ridge_h + 0.4);
        // PTFE tape strips on the floor: two shallow 13 mm tracks (1/2" tape) under the stack
        for (m = [-1, 1]) rbox([m * 28 - 6.5, Y0 + 14, floor_top - 0.2], [13, in_l - 16, 1]);
        // finger slots in the side walls' tops to take the last cards out
        for (m = [0, 1]) mirror([m, 0, 0]) translate([in_w / 2 - 1, Y0 + in_l / 2, top_z]) rotate([0, 90, 0]) cylinder(r = 12, h = wall + 5);
    }
}

// ============================ SHOE ===============================================================
function shoe_under(d) = d <= pad_d1 ? bar_v : bar_v + (lead_v - bar_v) * (d - pad_d1) / (d_back - pad_d1);
module shoe() {
    sec = [shoept(d_front, shoe_under(d_front)), shoept(pad_d1, shoe_under(pad_d1)), shoept(d_back, lead_v),
           [Y0, top_z], [Y0 - shoe_t, top_z], [Y0 - shoe_t, bar_top], [shoept(d_front, 0)[0] + 1.5, bar_top],
           [shoept(d_front, 0)[0], bar_top - 1.5]];
    difference() {
        union() {
            yz(-shoe_half, 2 * shoe_half) polygon(sec);
            for (m = [0, 1]) mirror([m, 0, 0])
                rbox([shoe_half - 0.01, tongue_y[0], tongue_z0], [tongue_out + 0.01, tongue_y[1] - tongue_y[0], top_z - tongue_z0]);
            rbox([-box_half, box_y0, box_z[0]], [2 * box_half, -shoe_t - (box_y0 - Y0) + 0.01, box_z[1] - box_z[0]]);
        }
        for (m = [0, 1]) mirror([m, 0, 0]) yz(pad_x0, pad_x1 - pad_x0)
            polygon([shoept(pad_d0, -1), shoept(pad_d1, -1), shoept(pad_d1, bar_v + pocket), shoept(pad_d0, bar_v + pocket)]);
        rbox([-coin_half, coin_y[0], box_z[0] + 2], [2 * coin_half, coin_y[1] - coin_y[0], 40]);
        translate([0, Y0 + 1, top_z - 9]) rotate([90, 0, 0]) cylinder(d = 14, h = shoe_t + 2);   // lift it out here
    }
}
module pads() color("#b07a43") for (m = [0, 1]) mirror([m, 0, 0]) yz(pad_x0 + 0.3, pad_x1 - pad_x0 - 0.6)
    polygon([shoept(pad_d0 + 0.3, bar_v + pocket - pad_t), shoept(pad_d1 - 0.3, bar_v + pocket - pad_t),
             shoept(pad_d1 - 0.3, bar_v + pocket), shoept(pad_d0 + 0.3, bar_v + pocket)]);

module n20() color("silver") translate([gear_face_x, wc[0] - n20_w / 2 + 0.2, wc[1] - n20_h / 2 + 0.2]) cube([n20_len, n20_w - 0.4, n20_h - 0.4]);
module feeder_assembly(cards = 40) {
    color("#3a3f47") stand();
    color("#2b2b2b") motor_lid();
    color("orange") roller();
    color("#5a6068") hopper();
    color("#2b2b2b") shoe();
    pads();
    n20();
    color("#c9a46a") for (i = [0 : cards - 1]) translate([-card_w / 2, Y0 + 0.5, floor_top + poke + 0.32 * i]) cube([card_w, card_l, 0.3]);
}

if (part == "feeder") feeder_assembly();
if (part == "stand") stand();
if (part == "hopper") hopper();
if (part == "shoe") shoe();
if (part == "roller") roller();
if (part == "motor_lid") motor_lid();
