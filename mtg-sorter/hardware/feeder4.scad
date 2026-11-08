// Feeder box v4 (2026-11-08): one card per feed, every time, everything built into the box.
//
// What was wrong with v2 (feeder.scad), from the camera tests:
//   - The wheels pushed the card 20 mm behind the gate, so each card's tail stayed under the stack
//     and hung there until the next feed dragged it out (0, 1 or 3 cards). The app's back-off hid it.
//   - The gate was a gap over the hopper floor, set with a thumb screw. A card is 0.3 mm thick, so
//     a few tenths either way meant two cards, or none and a grinding motor.
//   - The card left the hopper flat and dropped 5 mm onto the 20° bed, so it bent, caught and
//     landed crooked.
//
// v4, all in the box:
//   1. WHEELS AT THE MOUTH. The roller sits right under the front of the stack, on fixed bearings in
//      the stand (no hinged arm, no rubber band). The card is driven until its tail is clear of the
//      stack, so nothing is left hanging.
//   2. A SELF-SETTING SEPARATOR instead of a gap. A shoe drops into two slots in the box's front
//      cheeks and rests by its own weight on the wheels, with a friction pad over each wheel (cork).
//      The wheel grips the bottom card harder than the pad does, so it goes; the pad grips the second
//      card harder than the cards grip each other, so it stays. It works for any card thickness,
//      foils and curled cards included, and needs no setting. Coins in its pocket set the pressure.
//      The shoe slides straight up and down, so the card dragging under it can't pull it down
//      harder (it can't lock), and the stack leaning on it can't lift it.
//   3. THE CARD LEAVES ALONG THE BED. The wheels meet the pad 20° ahead of their top, so the card
//      comes out at the bed's own 20°, 0.8 mm above the PTFE tape lands: no drop, no bend, nothing
//      to catch on. The cheeks guide it straight into the bed's centring funnel.
//   4. The last cards feed too: the shoe presses them onto the wheels even when the stack is gone.
//   5. It can't move: the stand's foot closes over the bridge's 2 mm outline ridge (skirt + roof), and
//      the hopper sits on a ridge along the stand's walls in a groove under its floor. (The motor
//      dragged the whole old box forward.)
//
// Parts (set `part`, F6, F7). All print without supports, as exported (stl/feeder4_*.stl):
//   stand4    box on the bridge, holds the roller and motor (replaces the v2 stand and arm)
//   hopper4   floor, walls and the two front cheeks with the shoe slots (replaces the v2 hopper)
//   roller4   two O-ring wheels, 33.5 mm apart so they run between the bed's PTFE lands (100 % infill)
//   shoe4     the separator shoe with its coin pocket (100 % infill)
//   "assembly" shows it all with the scan bed v3.1 (preview only)
// Kept from v2: the N20 motor and its wires, the O-rings (20x3 or 22x3), weight_solid (feeder.scad).
// Goes with: bed_plate3 with the two wheel slots at its back edge (bed_chute.scad, bp3_wheel_slots).
//
// Coordinates as feeder.scad: x across, y = 0 at the inside of the hopper's front wall (+y towards
// the back), z = 0 on top of the bridge. enclosure.scad puts y = 0 at y 150 and z = 0 at z 111.

part = "assembly";
$fn = 64;

// --- The scan bed (bed_chute.scad), in these coordinates --------------------------------------
bed_a = 20;
bed_o = [54 - 150, 170 - 111];           // the bed's front edge, top of its base plate (y, z)
land_n = 2 + 0.8;                         // bed_plate3: face 2 mm over the base, lands 0.8 more
exit_n = land_n + 0.8;                    // the card leaves the wheels 0.8 mm above the lands
function bedpt(s, n) = [bed_o[0] + s * cos(bed_a) - n * sin(bed_a), bed_o[1] + s * sin(bed_a) + n * cos(bed_a)];
function bed_s(y, n) = (y - bed_o[0] + n * sin(bed_a)) / cos(bed_a);   // s where the line n crosses y

// --- Cards and box ----------------------------------------------------------------------------
card_w = 63;  card_l = 88;
wall = 3;
in_w = card_w + 4;                        // 67
in_l = card_l + 4;                        // 92
out_w = in_w + 2 * wall;                  // 73 (the bridge fence and the deck's hopper well still fit)
hopper_h = 60;                            // about 180 cards
floor_t = 3;
// The bridge's fence (enclosure.scad) is 73.6 x 128.6 inside, around y -33.3 .. 95.3. The v2 stand was
// 73 x 128, 0.3 mm each side, so with the first layer's squish it didn't drop in. v4: 72 x 127,
// 0.8 mm each side, and a 0.8 mm chamfer round the bottom edge.
fence = [73.6, 128.6];  fence_yc = 31;
stand_w = fence[0] - 1.6;                 // 72
stand_l = fence[1] - 1.6;                 // 127
stand_y0 = fence_yc - stand_l / 2;        // -32.5
stand_y1 = stand_y0 + stand_l;            // 94.5
stand_wall = 2.75;                        // inside stays x +-33.25
foot_ch = 0.8;
// The fence itself is a 2 mm wall, 2 mm tall. The motor's pull could tip the old box over it and slide
// it forward, so the v4 foot closes over it: a skirt outside the fence and a roof over its top join the
// stand's walls, so the box can only come out straight up.
fence_t = 2;  fence_h = 2;
skirt_gap = 0.4;  skirt_t = 1.6;  roof_z = [fence_h + 0.4, fence_h + 2];
// The hopper sits on a ridge that runs along the top of the stand's side and back walls, in a groove
// under its floor (the hopper locks onto it; replaces v2's four 2 mm pegs), so it can't slide on the stand either.
ridge_w = 1.4;  ridge_h = 2.4;  groove_c = 0.3;

// --- Roller (same O-rings as v2: 3 mm cord over a 23 mm groove) --------------------------------
oring = 3;  groove_root = 23;
wheel_d = groove_root + 2;                // flanks
R = groove_root / 2 + oring;              // 14.5 over the O-rings
core_d = 16;
wheel_x = 16.75;                          // between the bed's lands (x 9 and 24.5, 7.5 wide at the foot)
wheel_w = 7;
stub_d = 5;  shaft_len = 9;
roller_x0 = -wheel_x - wheel_w / 2;       // -20.25: the left wheel's outer face
roller_x1 = 20.5;                         // motor end
gear_face_x = 22.5;
n20_w = 12.4;  n20_h = 10.4;  n20_len = 26;

// --- Where the wheels go ----------------------------------------------------------------------
// The wheels' top is 1 mm inside the stack's front edge (y = 0), so they drive the bottom card from
// under the stack. The nip (where the pad presses) is 20° ahead of the top, so the card leaves
// along the bed's slope; that point sits on the line exit_n.
nip_y = 1 - R * sin(bed_a);               // -3.96
nip_s = bed_s(nip_y, exit_n);             // 99.3 mm up the bed
nip = bedpt(nip_s, exit_n);               // (y, z) = (-3.96, 96.3)
wc = [nip[0] + R * sin(bed_a), nip[1] - R * cos(bed_a)];   // wheel axis (y, z) = (1.0, 82.7)
poke = 2.2;                               // wheels stand this far above the floor
floor_top = wc[1] + R - poke;             // 95.0
stand_h = floor_top - floor_t;            // 92.0

// --- The shoe: the box's front wall, sliding up and down ----------------------------------------
// Built in the pad's frame: d along the bed, up the slope, from the nip (+d = into the hopper);
// v square to the bed from the pad line (the card's underside at the nip).
function shoept(d, v) = [nip[0] + d * cos(bed_a) - v * sin(bed_a), nip[1] + d * sin(bed_a) + v * cos(bed_a)];
pad_x0 = wheel_x - 4;  pad_x1 = wheel_x + 4;   // pad pockets over each wheel, x 12.75 .. 20.75
pad_d0 = -4.5;  pad_d1 = 3.0;             // ... and along the bed
pad_t = 1.6;                              // cork 1.5 - 2 mm, glued in a 1 mm pocket
bar_v = 0.6;                              // the shoe's underside (with pads in, it rests on them)
pocket = 1.0;
lead_v = 1.2;                             // the underside rises to this at the back face (lead-in)
d_back = (0 - nip[0]) / cos(bed_a);       // 4.2: the shoe's back face is the hopper's inside front (y = 0)
d_front = -5;
shoe_half = in_w / 2 - 0.4;               // 33.1
shoe_t = 3;                               // the wall part, y -3 .. 0
bar_top = 104;                            // the bar under the wall reaches forward to d_front up to here
top_z = floor_top + hopper_h;             // 155, flush with the side walls
tongue_y = [-2.8, 0];                     // tongues on both ends, the full height of the shoe
tongue_z0 = 102;
tongue_out = 2.1;                         // into the side walls' slots
box_half = 16;  box_y0 = -8.6;  box_z = [bar_top - 0.01, 131];   // coin box on the front face
coin_y = [-7.0, -3.0];  coin_half = 13.9; // two loonies or three quarters, standing up

// --- Slots in the side walls ---------------------------------------------------------------
lip_y0 = -4.6;                            // the side walls run this far forward, in front of the slot
cut_n = exit_n + 0.6;                     // in front of the floor everything stays above this bed line
slot_y = [tongue_y[0] - 0.35, tongue_y[1] + 0.35];
slot_x1 = in_w / 2 + tongue_out + 0.25;   // 0.9 mm of side wall left outside the slot
slot_bot = tongue_z0 - 1.6;               // with no roller in, the shoe drops 1.6 mm at most

module rbox(p, s) { translate(p) cube(s); }
module yz(x0, t) { translate([x0, 0, 0]) rotate([90, 0, 90]) linear_extrude(t) children(); }
// the space below (under_bed) or above (over_bed) the bed-parallel line n, in front of y = y1
module bed_side_of(n, y1, up) {
    a = bedpt(-50, n);  b = bedpt(140, n);  e = up ? 400 : -50;
    intersection() {
        yz(-100, 200) polygon([a, b, [b[0], e], [a[0], e]]);
        rbox([-100, -200, -100], [200, 200 + y1, 600]);
    }
}
module under_bed(n, y1 = 0) bed_side_of(n, y1, false);
module over_bed(n, y1 = 0) bed_side_of(n, y1, true);

// ============================ ROLLER ==========================================
module roller4_body() {
    // (x, r) profile: stub, left wheel, core, right wheel cut off by the motor end
    function wheel(c) = [[c - wheel_w / 2, wheel_d / 2], [c - 1.6, wheel_d / 2], [c - 1.6, groove_root / 2],
                         [c + 1.6, groove_root / 2], [c + 1.6, wheel_d / 2], [c + wheel_w / 2, wheel_d / 2]];
    pts = concat([[roller_x0 - 4, 0], [roller_x0 - 4, stub_d / 2], [roller_x0, stub_d / 2]],
                 wheel(-wheel_x),
                 [[-wheel_x + wheel_w / 2 + (wheel_d - core_d) / 2, core_d / 2],      // 45° in towards the core
                  [wheel_x - wheel_w / 2 - (wheel_d - core_d) / 2, core_d / 2]],
                 wheel(wheel_x),
                 [[roller_x1, wheel_d / 2 - 0.25], [roller_x1, 0]]);
    difference() {
        rotate([0, 90, 0]) rotate_extrude() polygon([for (p = pts) [p[1], p[0]]]);
        translate([roller_x1 - shaft_len + 1, 0, 0]) rotate([0, 90, 0]) intersection() {
            cylinder(d = 3.15, h = shaft_len + 1, $fn = 32);
            translate([-2, -1.65, 0]) cube([4, 3.3, shaft_len + 1]);
        }
    }
}
module roller4() translate([0, wc[0], wc[1]]) roller4_body();
// the space a turning wheel sweeps (for the clash checks and the slots)
module wheel_sweep(c = 0) translate([0, wc[0], wc[1]]) for (x = [-wheel_x, wheel_x])
    translate([x - wheel_w / 2 - c, 0, 0]) rotate([0, 90, 0]) cylinder(r = R + c, h = wheel_w + 2 * c);

// ============================ STAND ===========================================
module stand4() {
    sw = stand_w / 2;
    difference() {
        union() {
            difference() {
                hull() {
                    rbox([-sw + foot_ch, stand_y0 + foot_ch, 0], [stand_w - 2 * foot_ch, stand_l - 2 * foot_ch, 0.01]);
                    rbox([-sw, stand_y0, foot_ch], [stand_w, stand_l, stand_h - foot_ch]);
                }
                rbox([-sw + stand_wall, stand_y0 + stand_wall, -1], [stand_w - 2 * stand_wall, stand_l - 2 * stand_wall, stand_h + 2]);
            }
            // the foot that closes over the bridge's fence: skirt outside it, roof over it
            foot_cap();
            // the ridge the hopper sits on (sides and back; the right side starts behind the motor slot)
            ridge();
            // left bearing block for the roller's stub, 45° underneath so it prints without support
            bw = sw - stand_wall + 0.01 - 21;
            hull() {
                rbox([-21 - bw, wc[0] - 6, wc[1] - 8], [bw, 12, stand_h - wc[1] + 8]);
                rbox([-21 - bw, wc[0] - 6, wc[1] - 8 - bw], [0.01, 12, 1]);
            }
            // motor cradle on the right: the gearbox lies in a channel, 45° underneath
            cz = wc[1] - n20_h / 2 - 2.5;
            hull() {
                rbox([21, wc[0] - n20_w / 2 - 2.5, cz], [bw, n20_w + 5, stand_h - cz]);
                rbox([21 + bw - 0.01, wc[0] - n20_w / 2 - 2.5, cz - bw], [0.01, n20_w + 5, 1]);
            }
        }
        // under the scan bed: 2 mm below its underside (its base plate is 3 mm thick)
        over_bed(-3 - 2, 0.5);
        // stub slot, open at the top through a 4.6 mm snap
        translate([-sw, wc[0], wc[1]]) rotate([0, 90, 0]) cylinder(d = stub_d + 0.6, h = sw - 21 - 0.5);
        hull() {
            translate([-sw, wc[0], wc[1] + 1.5]) rotate([0, 90, 0]) cylinder(d = 4.6, h = sw - 21 - 0.5);
            translate([-sw, wc[0], stand_h + 1]) rotate([0, 90, 0]) cylinder(d = 4.6, h = sw - 21 - 0.5);
        }
        // the roller's turning room next to the blocks
        translate([-21.6, wc[0], wc[1]]) rotate([0, 90, 0]) cylinder(r = wheel_d / 2 + 1, h = 43.2);
        // gearbox channel, open at the top, and on out through the right wall for the motor
        rbox([gear_face_x, wc[0] - n20_w / 2, wc[1] - n20_h / 2], [30, n20_w, 40]);
        rbox([sw - stand_wall - 1, wc[0] - n20_w / 2 - 1, wc[1] - n20_h / 2 - 1], [stand_wall + 2, n20_w + 2, 40]);
        // hole in the channel's end wall for the gearbox boss and shaft
        translate([gear_face_x - 3, wc[0], wc[1]]) rotate([0, 90, 0]) cylinder(d = 5, h = 4);
        // M2 x 8 from the back pinches the gearbox against the front of the channel
        translate([28, wc[0] + n20_w / 2 - 1, wc[1]]) rotate([-90, 0, 0]) cylinder(d = 1.8, h = 10);
    }
}

module foot_cap() {
    fo = [fence[0] + 2 * fence_t, fence[1] + 2 * fence_t];      // the fence's outside, 77.6 x 132.6
    si = [fo[0] + 2 * skirt_gap, fo[1] + 2 * skirt_gap];
    so = [si[0] + 2 * skirt_t, si[1] + 2 * skirt_t];             // 81.6 x 136.6
    translate([0, fence_yc, 0]) difference() {
        hull() {
            translate([0, 0, 0.5]) linear_extrude(roof_z[1] - 0.5) square(so, center = true);
            linear_extrude(0.01) square([so[0] - 1, so[1] - 1], center = true);
        }
        translate([0, 0, -1]) linear_extrude(roof_z[0] + 1) square(si, center = true);
        translate([0, 0, -1]) linear_extrude(roof_z[1] + 2) square([stand_w - 2 * stand_wall, stand_l - 2 * stand_wall], center = true);
    }
}
ridge_x = stand_w / 2 - stand_wall / 2;          // 34.6, the middle of the side walls
ridge_yb = stand_y1 - stand_wall / 2;            // 93.1, the middle of the back wall
ridge_y0 = [2, wc[0] + n20_w / 2 + 2];           // left / right side start (in front: the stand is cut under the bed)
module ridge(c = 0, h = ridge_h) {
    for (i = [0, 1]) let (x = i == 0 ? -ridge_x : ridge_x)
        rbox([x - ridge_w / 2 - c, ridge_y0[i] - c, stand_h - 0.01], [ridge_w + 2 * c, ridge_yb - ridge_y0[i] + ridge_w / 2 + 2 * c, h]);
    rbox([-ridge_x - ridge_w / 2 - c, ridge_yb - ridge_w / 2 - c, stand_h - 0.01], [2 * ridge_x + ridge_w + 2 * c, ridge_w + 2 * c, h]);
}

// ============================ HOPPER ==========================================
// Floor, side walls and back. Its front wall is the shoe, which drops into the two slots at the
// front of the side walls.
module hopper4() {
    z0 = stand_h;
    difference() {
        union() {
            rbox([-out_w / 2, 0, z0], [out_w, in_l + wall, floor_t]);                                  // floor
            for (x = [-out_w / 2, in_w / 2]) rbox([x, lip_y0, z0], [wall, in_l + wall - lip_y0, floor_t + hopper_h]);
            rbox([-out_w / 2, in_l, z0], [out_w, wall, floor_t + hopper_h]);                            // back
        }
        // in front of the floor, everything stays above the bed (outside the card, 0.6 mm over its path)
        under_bed(cut_n, 0);
        // ... and the lips' undersides rise at 45° from there, so they print without support
        lz = bedpt(bed_s(0, cut_n), cut_n)[1];
        yz(-out_w, 2 * out_w) polygon([[0.01, lz], [-20, lz + 20.01], [-20, 0], [0.01, 0]]);
        // the wheel slots
        for (x = [-wheel_x, wheel_x]) rbox([x - wheel_w / 2 - 1, -1, z0 - 1], [wheel_w + 2, 14, floor_t + 2]);
        // floor's front top edge rounded off
        translate([0, 0, z0 + floor_t]) rotate([45, 0, 0]) cube([2 * out_w, 1.6, 1.6], center = true);
        // the shoe slots, open at the top
        for (m = [0, 1]) mirror([m, 0, 0]) rbox([in_w / 2 - 1, slot_y[0], slot_bot], [slot_x1 - in_w / 2 + 1, slot_y[1] - slot_y[0], 100]);
        // the groove for the stand's ridge
        ridge(groove_c, ridge_h + 0.4);
        // thumb notch in the back wall, to lift the weight out
        translate([0, in_l - 1, floor_top + hopper_h]) rotate([-90, 0, 0]) cylinder(r = 15, h = wall + 2);
    }
}

// ============================ SHOE ============================================
// The hopper's front wall, with the separator bar along its bottom edge. Its tongues slide in the
// side walls' slots, so it only moves straight up and down. Prints on its back face, as exported.
function shoe_under(d) = d <= pad_d1 ? bar_v : bar_v + (lead_v - bar_v) * (d - pad_d1) / (d_back - pad_d1);
module shoe4() {
    sec = [shoept(d_front, shoe_under(d_front)), shoept(pad_d1, shoe_under(pad_d1)), shoept(d_back, lead_v),
           [0, top_z], [-shoe_t, top_z], [-shoe_t, bar_top], [shoept(d_front, 0)[0] + 1.5, bar_top],
           [shoept(d_front, 0)[0], bar_top - 1.5]];
    difference() {
        union() {
            yz(-shoe_half, 2 * shoe_half) polygon(sec);
            // tongues
            for (m = [0, 1]) mirror([m, 0, 0])
                rbox([shoe_half - 0.01, tongue_y[0], tongue_z0], [tongue_out + 0.01, tongue_y[1] - tongue_y[0], top_z - tongue_z0]);
            // coin box on the front face
            rbox([-box_half, box_y0, box_z[0]], [2 * box_half, -shoe_t - box_y0 + 0.01, box_z[1] - box_z[0]]);
        }
        // pad pockets over the wheels
        for (m = [0, 1]) mirror([m, 0, 0]) yz(pad_x0, pad_x1 - pad_x0)
            polygon([shoept(pad_d0, -1), shoept(pad_d1, -1), shoept(pad_d1, bar_v + pocket), shoept(pad_d0, bar_v + pocket)]);
        // coin pocket, open at the top
        rbox([-coin_half, coin_y[0], box_z[0] + 2], [2 * coin_half, coin_y[1] - coin_y[0], 40]);
        // finger hole near the top to lift the shoe out
        translate([0, 1, top_z - 9]) rotate([90, 0, 0]) cylinder(d = 14, h = shoe_t + 2);
    }
}
module pads() color("#b07a43") for (m = [0, 1]) mirror([m, 0, 0]) yz(pad_x0 + 0.3, pad_x1 - pad_x0 - 0.6)
    polygon([shoept(pad_d0 + 0.3, bar_v + pocket - pad_t), shoept(pad_d1 - 0.3, bar_v + pocket - pad_t),
             shoept(pad_d1 - 0.3, bar_v + pocket), shoept(pad_d0 + 0.3, bar_v + pocket)]);
// with 1.6 mm pads the shoe sits with the pad faces on the pad line (v = 0)

// ============================ OUTPUT ==========================================
if (part == "stand4") stand4();
else if (part == "hopper4") translate([0, 0, -stand_h]) hopper4();
else if (part == "roller4") translate([0, 0, roller_x1]) rotate([0, 90, 0]) roller4_body();
else if (part == "shoe4") rotate([-90, 0, 0]) shoe4();    // back face (y = 0) on the plate
else if (part == "none") { }
else assembly4();

module assembly4() {
    color("#3a3f47") stand4();
    color("orange") roller4();
    color("#5a6068", 0.6) hopper4();
    color("#2b2b2b") shoe4();
    pads();
    color("silver") translate([gear_face_x, wc[0] - n20_w / 2 + 0.2, wc[1] - n20_h / 2 + 0.2]) cube([n20_len, n20_w - 0.4, n20_h - 0.4]);
    color("#c9a46a") for (i = [0:14]) translate([-card_w / 2, 0.5, floor_top + poke + 0.32 * i]) cube([card_w, card_l, 0.3]);
}
