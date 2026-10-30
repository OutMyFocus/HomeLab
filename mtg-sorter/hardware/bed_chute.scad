// Scan bed + chute: the middle and bottom of the sifter.
//
// Card path:
//   1. Card drops from the feeder onto the BED, which slopes 20 degrees down to the front.
//      It slides until two small PINS near the front edge stop it, under the camera.
//   2. Photo. A servo under the bed swings the pins down and the card slides off.
//   3. It lands in the CHUTE, a level tray above the three bins.
//        bin 2 (middle): two trapdoors in the tray floor open, card drops straight down
//        bin 1 / bin 3:  a servo tilts the tray 25 degrees and the card slides off that end
//
// Coordinates: x = left/right, y = front(-) to back(+), z = up. The table is z = 0.
//
// Printable parts (set `part`, F6, F7). All fit a 256 mm bed, no supports:
//   bed_plate        white, the surface the camera looks at
//   bed_side_left    side wall with the LED groove and the pin servo
//   bed_side_right   side wall with the LED groove and the camera tower socket
//   pin_rocker       the two stop pins, on an arm the pin servo turns
//   tower_post       camera tower post
//   camera_head      arm + camera plate
//   tilt_bracket     holds the tilt servo, between the two bed side walls
//   chute            the tray
//   trapdoor         x2 (print one, then one mirrored: part = "trapdoor_left")
//   door_carrier     x2 (servo mount + back hinge on one bar) ("door_carrier_left" for the other)
//   trapdoor_mount, hinge_lug: the older separate versions, replaced by door_carrier
//   frame_side       x2 (identical)
//   front_bar        holds the front of the tray's pivot
//   bin              x3
//   "assembly" shows everything together (preview only)

part = "assembly";

// Preview positions for the moving parts
show_tilt = 0;          // chute tilt in degrees: 0, 25 or -25
show_doors_open = false;
show_pins_down = false;
show_frame = true;      // the open frame, front bar and bins (enclosure.scad turns this off)

// Where the bed side walls start. 0 = they stand on the table (open-frame build).
// enclosure.scad sets this to the top of its bridge plate; the walls then get two screw
// holes in their bottom edge, and the bridge screws up into them from below.
wall_z0 = 0;

// --- Cards ---------------------------------------------------------------------
card_w = 63;
card_l = 88;

// --- Bed -------------------------------------------------------------------------
bed_angle = 20;
bed_len = 100;          // along the slope
bed_t = 3;
bed_y = 54;             // front edge of the bed
bed_z = 170;            // height of the bed surface at its front edge
side_in = 56;           // inner faces of the side walls (x = +-56)
side_t = 6;
wall_h = 32;            // side walls rise this far above the bed
led_w = 10.5;
led_n = 20;             // LED strip centre, above the bed surface
card_s = 47;            // card centre, measured up the slope from the front edge
cam_height = 120;       // camera lens above the card
tower_x = 80;           // tower post, beside the bed
post_s = 20;
socket_d = 18;
boss_s = 32;
fit = 0.3;

// Stop pins
pin_x = 20;             // pins at x = +-20
pin_axis = [75, 165];   // pin servo shaft (y, z), on the left wall
pin_drop = 28;          // degrees the rocker turns to pull the pins down

// --- Chute -------------------------------------------------------------------------
pivot_z = 145;          // tilt axis height (along y, at x = 0) = top of the tray floor
tilt = 25;
ch_half = 60;           // tray reaches x = +-60
ch_in = 45.5;           // inside of the tray, y = +-45.5 (card is 88 long)
rail_t = 2.5;
floor_t = 2.5;
front_rail_h = 30;      // tall: the falling card hits it
back_rail_h = 6;
door_half = 36;         // trapdoor opening x = +-36
hinge_z = 136;          // trapdoor hinge axes (x = +-36, along y)
axle_d = 8;
front_bar_y = -75;      // inside face of the front bar

// --- Bins and frame -------------------------------------------------------------------
bin_w = 74;
bin_l = 100;
bin_h = 92;             // about 250 cards
bin_pitch = 76;
frame_x = 118;          // inside faces of the frame sides
frame_t = 6;
frame_h = 152;

// --- Servo (SG90 / MG90S, all four are the same size) --------------------------------
sv_len = 22.7;          // body length
sv_w = 12.2;            // body width
sv_shaft_off = 5.9;     // shaft distance from one end of the body
sv_top = 6.6;           // body above the mounting tabs (the part that pokes through)
sv_tab_len = 32.2;
sv_screw = 27.5;        // distance between the two tab screw holes

$fn = 48;

tan_a = tan(bed_angle);
bed_back_y = bed_y + bed_len * cos(bed_angle);
bed_back_z = bed_z + bed_len * sin(bed_angle);
ch_out = ch_in + rail_t;

// Bed coordinates: x across, s up the slope from the front edge, n square to the bed.
module on_bed() { translate([0, bed_y, bed_z]) rotate([bed_angle, 0, 0]) children(); }

// Profile in the (y, z) plane, given as 2D points, extruded along x from x0 to x0 + t.
module yz_plate(x0, t) { translate([x0, 0, 0]) rotate([90, 0, 90]) linear_extrude(t) children(); }

// Rectangle for an SG90 seen from its top, with the shaft at the origin; length along u.
module servo_hole(depth, flip = false) {
    u0 = flip ? -(sv_len - sv_shaft_off) : -sv_shaft_off;
    translate([u0 - 0.3, -sv_w / 2 - 0.3, -1]) cube([sv_len + 0.6, sv_w + 0.6, depth + 2]);
}
module servo_screws(depth, flip = false) {
    c = (flip ? -1 : 1) * (sv_len / 2 - sv_shaft_off);
    for (d = [-1, 1]) translate([c + d * sv_screw / 2, 0, -1]) cylinder(d = 1.8, h = depth + 2);
}

// ============================ BED ============================================

module bed_plate() {
    difference() {
        union() {
            translate([-side_in - 2 + 0.3, 0, -bed_t]) cube([2 * side_in + 4 - 0.6, bed_len, bed_t]);
            // low rails that keep the card straight
            for (m = [0, 1]) mirror([m, 0, 0]) translate([card_w / 2 + 2, 8, 0]) cube([1.5, bed_len - 8, 1.5]);
        }
        // slots the stop pins come up through (open at the front edge)
        for (m = [0, 1]) mirror([m, 0, 0]) translate([pin_x - 2.5, -1, -bed_t - 1]) cube([5, 9, bed_t + 2]);
    }
}

module bed_side(left) {
    difference() {
        union() {
            yz_plate(side_in, side_t) polygon([
                [bed_y, wall_z0], [bed_back_y, wall_z0], [bed_back_y, bed_back_z + wall_h], [bed_y, bed_z + wall_h]]);
            // camera tower socket block, square to the bed (right wall only)
            if (!left) on_bed() translate([side_in + side_t - 2, card_s - boss_s / 2, -10])
                cube([tower_x + boss_s / 2 - side_in - side_t + 2, boss_s, 24]);
        }
        on_bed() {
            // groove the bed plate slides into
            translate([side_in - 0.01, -1, -bed_t - 0.15]) cube([2.01, bed_len + 2, bed_t + 0.3]);   // 2 mm into the wall
            // LED strip groove
            translate([side_in - 0.01, 5, led_n - led_w / 2]) cube([1.6, bed_len - 10, led_w]);
            // tower socket
            if (!left) translate([tower_x - (post_s + fit) / 2, card_s - (post_s + fit) / 2, -4]) cube([post_s + fit, post_s + fit, 30]);
        }
        if (left) {
            // pin servo: pokes in through the wall, shaft along x
            translate([side_in - 1, pin_axis[0], pin_axis[1]]) rotate([0, 90, 0]) rotate([0, 0, 90]) {
                servo_hole(side_t + 2);
                servo_screws(side_t + 2);
            }
        }
        // screw holes for the tilt bracket
        for (z = [pivot_z - 8, pivot_z + 2]) translate([side_in - 1, tilt_bracket_y + 3, z]) rotate([0, 90, 0]) cylinder(d = 3.2, h = side_t + 2);
        // enclosure build: M3 screws come up through the bridge plate into the bottom edge
        if (wall_z0 > 0) for (y = [bed_y + 12, bed_back_y - 12]) translate([side_in + side_t / 2, y, wall_z0 - 1]) cylinder(d = 2.6, h = 11);
    }
}

// Rocker: a flat plate the servo horn screws onto, a cross bar, and the two pins.
// Modelled where it sits with the pins up. Everything starts at the same height
// underneath, so it prints flat with no supports.
rocker_bottom = 159;
module pin_rocker() {
    hub_x = -side_in + sv_top - 1;   // just inside the left wall, where the servo shaft ends
    bar_y = bed_y + 1.5;
    difference() {
        union() {
            // plate in the y-z plane: the horn screws to its outer (left) face
            yz_plate(hub_x, 3) polygon([[bar_y, rocker_bottom], [pin_axis[0] + 6, rocker_bottom],
                [pin_axis[0] + 6, pin_axis[1] + 4], [pin_axis[0] - 2, pin_axis[1] + 6], [bar_y, rocker_bottom + 5]]);
            // cross bar
            translate([hub_x, bar_y, rocker_bottom]) cube([pin_x + 4 - hub_x, 4, 5]);
            // pins, up through the bed slots to about 4 mm above the bed
            for (x = [-pin_x, pin_x]) translate([x - 1.5, bar_y + 0.5, rocker_bottom])
                cube([3, 3, bed_z + 1 * tan_a + 4 - rocker_bottom]);
        }
        // hole for the horn's hub, and two horn screw holes
        translate([hub_x - 1, pin_axis[0], pin_axis[1]]) rotate([0, 90, 0]) cylinder(d = 7.2, h = 5);
        for (d = [-1, 1]) translate([hub_x - 1, pin_axis[0] + d * 5.5, pin_axis[1] - 1]) rotate([0, 90, 0]) cylinder(d = 1.5, h = 5);
    }
}

module tower_post() {
    len = cam_height + socket_d - 1 + 4;
    difference() {
        translate([-post_s / 2, -post_s / 2, 0]) cube([post_s, post_s, len]);
        translate([-8.5, post_s / 2 - 1.5, -1]) cube([17, 2, len + 2]);   // camera cable groove
    }
}

// Same camera plate as the scan station, with the arm reaching across (x) to the tower.
cam_holes = [[-10.5, -10], [10.5, -10], [-10.5, 2.5], [10.5, 2.5]];
module camera_head() {
    difference() {
        union() {
            translate([tower_x - boss_s / 2, -boss_s / 2, 0]) cube([boss_s, boss_s, socket_d + 6]);
            translate([0, -10, 0]) cube([tower_x, 20, 6]);
            translate([-17, -17, 0]) cube([34, 34, 3]);
            for (h = cam_holes) translate([h[0], h[1], 0]) cylinder(d = 5, h = 6);
        }
        translate([tower_x - (post_s + fit) / 2, -(post_s + fit) / 2, -1]) cube([post_s + fit, post_s + fit, socket_d + 1]);
        translate([-7, -9, -1]) cube([14, 18, 10]);                             // lens window
        for (h = cam_holes) translate([h[0], h[1], -1]) cylinder(d = 1.8, h = 10);
        translate([tower_x - boss_s / 2 - 1, -8.5, 6.5]) cube([3, 17, 2]);      // cable slot
    }
}

// ============================ CHUTE ==========================================

tilt_bracket_y = 78;      // front face of the tilt bracket
back_axle_end = 70;       // where the back axle meets the horn plate

module chute() {
    difference() {
        union() {
            // floor
            translate([-ch_half, -ch_in, pivot_z - floor_t]) cube([2 * ch_half, 2 * ch_in, floor_t]);
            // front and back rails
            translate([-ch_half, -ch_out, pivot_z - floor_t]) cube([2 * ch_half, rail_t, front_rail_h + floor_t]);
            translate([-ch_half, ch_in, pivot_z - floor_t]) cube([2 * ch_half, rail_t, back_rail_h + floor_t]);
            // axles along y (flat underneath so they print without supports)
            for (y = [[front_bar_y - 8, -ch_out], [ch_out, back_axle_end]])
                translate([0, y[0], pivot_z]) intersection() {
                    rotate([-90, 0, 0]) cylinder(d = axle_d, h = y[1] - y[0]);
                    translate([-axle_d, 0, -floor_t]) cube([2 * axle_d, y[1] - y[0], axle_d]);
                }
            // plate the tilt servo's horn screws onto
            translate([-12, back_axle_end, pivot_z - floor_t]) cube([24, 2.5, 14]);
        }
        // trapdoor opening
        translate([-door_half, -ch_in - 0.01, pivot_z - floor_t - 1]) cube([2 * door_half, 2 * ch_in + 0.02, floor_t + 2]);
        // horn screw holes and hub clearance
        translate([0, back_axle_end - 1, pivot_z]) rotate([-90, 0, 0]) cylinder(d = 7.2, h = 5);
        for (d = [-1, 1]) translate([d * 7, back_axle_end - 1, pivot_z]) rotate([-90, 0, 0]) cylinder(d = 1.5, h = 5);
        // screw holes for the trapdoor mounts and hinge lugs (from above, M2 self-tapping)
        for (m = [0, 1]) mirror([m, 0, 0]) for (y = [-ch_in + 5, ch_in - 5]) translate([door_half + 8, y, pivot_z - floor_t - 1]) cylinder(d = 2.4, h = floor_t + 2);
        // ... and for the door carriers that replace them
        for (m = [0, 1]) mirror([m, 0, 0]) for (y = carrier_screws_y) translate([carrier_x + 3, y, pivot_z - floor_t - 1]) cylinder(d = 2.4, h = floor_t + 2);
    }
}

// Right trapdoor, closed: fills x = 0.5 .. 35.5 of the opening, hinged at x = 36.
module trapdoor() {
    difference() {
        union() {
            translate([0.5, -ch_in + 0.5, pivot_z - floor_t]) cube([door_half - 1, 2 * ch_in - 1, floor_t]);
            // ears down to the hinge axis: front (servo horn) and back (hinge pin)
            for (y = [-ch_in + 6, ch_in - 10]) hull() {
                translate([door_half - 10, y, pivot_z - floor_t]) cube([10, 4, 0.1]);
                translate([door_half, y, hinge_z]) rotate([-90, 0, 0]) cylinder(r = 4, h = 4);
            }
        }
        // hinge pin hole (back ear) and horn screw holes (front ear)
        translate([door_half, ch_in - 11, hinge_z]) rotate([-90, 0, 0]) cylinder(d = 3.2, h = 6);
        translate([door_half, -ch_in + 5, hinge_z]) rotate([-90, 0, 0]) cylinder(d = 1.5, h = 6);
    }
}

// Servo mount under the front of the tray, right side. The servo's shaft lines up with the hinge.
module trapdoor_mount() {
    difference() {
        union() {
            translate([door_half - 12, -ch_out - 2.5, hinge_z - 10]) cube([sv_len + 12, 2.5, pivot_z - floor_t - hinge_z + 10]);
            // flange screwed under the tray floor, outside the trapdoor opening
            translate([door_half + 1, -ch_out - 2.5, pivot_z - floor_t - 3]) cube([sv_len - 1, 12, 3]);
        }
        translate([door_half, -ch_out - 2.5 - 1, hinge_z]) rotate([-90, 0, 0]) rotate([0, 0, 0]) {
            translate([-sv_shaft_off - 0.3, -sv_w / 2 - 0.3, 0]) cube([sv_len + 0.6, sv_w + 0.6, 6]);
        }
        for (d = [-1, 1]) translate([door_half + sv_len / 2 - sv_shaft_off + d * sv_screw / 2, -ch_out - 4, hinge_z]) rotate([-90, 0, 0]) cylinder(d = 1.8, h = 5);
        translate([door_half + 8, -ch_in + 5, pivot_z - floor_t - 4]) cylinder(d = 2.4, h = 5);
    }
}

// Back hinge lug, right side: screwed under the tray floor, holds the hinge pin.
module hinge_lug() {
    difference() {
        hull() {
            translate([door_half + 2, ch_in - 6, pivot_z - floor_t - 3]) cube([10, 6, 3]);
            translate([door_half, ch_in - 6, hinge_z]) rotate([-90, 0, 0]) cylinder(r = 4, h = 6);
        }
        translate([door_half, ch_in - 7, hinge_z]) rotate([-90, 0, 0]) cylinder(d = 2.9, h = 8);  // pin: 3 mm screw or filament
        translate([door_half + 8, ch_in - 5, pivot_z - floor_t - 4]) cylinder(d = 2.4, h = 5);
    }
}

// Door carrier, right side: the servo mount and the hinge lug joined by a bar, so the
// servo shaft and the hinge pin can't end up out of line. Three M2 screws from above, along
// the outer edge of the tray floor (clear of the servo body). Replaces trapdoor_mount +
// hinge_lug. Prints upside down, bar on the bed.
carrier_x = door_half + 17.5;    // bar x = carrier_x .. carrier_x + 6, screws on its centre line
module door_carrier() {
    top = pivot_z - floor_t;
    difference() {
        union() {
            // servo plate (as trapdoor_mount)
            translate([door_half - 12, -ch_out - 2.5, hinge_z - 10]) cube([sv_len + 12, 2.5, top - hinge_z + 10]);
            // bar along the outer edge, front to back
            translate([carrier_x, -ch_out - 2.5, top - 3]) cube([6, ch_in + ch_out + 2.5, 3]);
            // stiffening rib under the bar
            translate([carrier_x + 4, -ch_out, top - 5]) cube([2, ch_in + ch_out - 6, 5]);
            // hinge lug (as hinge_lug), tied across to the bar behind the door's back ear
            hull() {
                translate([door_half + 2, ch_in - 6, top - 3]) cube([10, 6, 3]);
                translate([door_half, ch_in - 6, hinge_z]) rotate([-90, 0, 0]) cylinder(r = 4, h = 6);
            }
            translate([door_half + 2, ch_in - 6, top - 3]) cube([carrier_x + 6 - door_half - 2, 6, 3]);
        }
        // servo hole and its two tab screws
        translate([door_half, -ch_out - 2.5 - 1, hinge_z]) rotate([-90, 0, 0])
            translate([-sv_shaft_off - 0.3, -sv_w / 2 - 0.3, 0]) cube([sv_len + 0.6, sv_w + 0.6, 6]);
        for (d = [-1, 1]) translate([door_half + sv_len / 2 - sv_shaft_off + d * sv_screw / 2, -ch_out - 4, hinge_z]) rotate([-90, 0, 0]) cylinder(d = 1.8, h = 5);
        // hinge pin
        translate([door_half, ch_in - 7, hinge_z]) rotate([-90, 0, 0]) cylinder(d = 2.9, h = 8);
        // screws up into the tray floor
        for (y = carrier_screws_y) translate([carrier_x + 3, y, top - 9]) cylinder(d = 2.4, h = 10);
    }
}
carrier_screws_y = [-ch_in + 6, 0, ch_in - 3];

// Tilt servo bracket: a plate across between the bed side walls, with the servo through it.
module tilt_bracket() {
    difference() {
        translate([-side_in + 0.3, tilt_bracket_y, pivot_z - 20]) cube([2 * side_in - 0.6, 6, 32]);
        // servo pokes through from the back; shaft lines up with the tilt axis
        translate([0, tilt_bracket_y + 6 + 1, pivot_z]) rotate([90, 0, 0]) {
            servo_hole(8);
            servo_screws(8);
        }
        // screws into the side walls
        for (m = [0, 1]) mirror([m, 0, 0]) for (z = [pivot_z - 8, pivot_z + 2])
            translate([side_in - 12, tilt_bracket_y + 3, z]) rotate([0, 90, 0]) cylinder(d = 2.6, h = 14);
    }
}

// ============================ FRAME AND BINS ===================================

module frame_side() {
    difference() {
        yz_plate(frame_x, frame_t) polygon([[front_bar_y - 6, 0], [ch_out + 4, 0], [ch_out + 4, frame_h], [front_bar_y - 6, frame_h]]);
        // big window so you can see into the bins (and save filament)
        yz_plate(frame_x - 1, frame_t + 2) offset(r = 8) offset(delta = -8)
            polygon([[front_bar_y + 14, 14], [ch_out - 10, 14], [ch_out - 10, frame_h - 40], [front_bar_y + 14, frame_h - 40]]);
        // screw holes for the front bar
        for (z = [frame_h - 22, frame_h - 8]) translate([frame_x - 1, front_bar_y - 3, z]) rotate([0, 90, 0]) cylinder(d = 3.2, h = frame_t + 2);
    }
}

module front_bar() {
    difference() {
        translate([-frame_x + 0.3, front_bar_y - 6, frame_h - 30]) cube([2 * frame_x - 0.6, 6, 30]);
        translate([0, front_bar_y - 7, pivot_z]) rotate([-90, 0, 0]) cylinder(d = axle_d + 0.5, h = 8);
        for (m = [0, 1]) mirror([m, 0, 0]) for (z = [frame_h - 22, frame_h - 8])
            translate([frame_x - 12, front_bar_y - 3, z]) rotate([0, 90, 0]) cylinder(d = 2.6, h = 14);
    }
}

module bin() {
    difference() {
        translate([-bin_w / 2, -bin_l / 2, 0]) cube([bin_w, bin_l, bin_h]);
        translate([-bin_w / 2 + 2, -bin_l / 2 + 2, 2]) cube([bin_w - 4, bin_l - 4, bin_h]);
        // finger pull in the front
        translate([0, -bin_l / 2 - 1, bin_h]) rotate([-90, 0, 0]) cylinder(r = 14, h = 4);
    }
}

// ============================ OUTPUT ==========================================

// Each printable part is turned and moved so it sits flat on the print bed.
if (part == "bed_plate") translate([0, 0, bed_t]) bed_plate();
else if (part == "bed_side_left") translate([0, 0, -side_in]) rotate([0, 90, 0]) mirror([1, 0, 0]) bed_side(true);
else if (part == "bed_side_right") translate([0, 0, -side_in]) rotate([0, -90, 0]) bed_side(false);
else if (part == "pin_rocker") translate([0, 0, -rocker_bottom]) pin_rocker();
else if (part == "tower_post") translate([0, 0, post_s / 2]) rotate([0, 90, 0]) tower_post();
else if (part == "camera_head") camera_head();
else if (part == "tilt_bracket") translate([0, 0, -tilt_bracket_y]) rotate([90, 0, 0]) tilt_bracket();
else if (part == "chute") translate([0, 0, -pivot_z + floor_t]) chute();
else if (part == "trapdoor") mirror([0, 0, 1]) translate([0, 0, -pivot_z]) trapdoor();
else if (part == "trapdoor_left") mirror([1, 0, 0]) mirror([0, 0, 1]) translate([0, 0, -pivot_z]) trapdoor();
else if (part == "trapdoor_mount") translate([0, 0, ch_out + 2.5]) rotate([90, 0, 0]) trapdoor_mount();
else if (part == "trapdoor_mount_left") mirror([1, 0, 0]) translate([0, 0, ch_out + 2.5]) rotate([90, 0, 0]) trapdoor_mount();
else if (part == "hinge_lug") translate([0, 0, -(ch_in - 6)]) rotate([90, 0, 0]) hinge_lug();
else if (part == "hinge_lug_left") mirror([1, 0, 0]) translate([0, 0, -(ch_in - 6)]) rotate([90, 0, 0]) hinge_lug();
else if (part == "door_carrier") mirror([0, 0, 1]) translate([0, 0, -(pivot_z - floor_t)]) door_carrier();
else if (part == "door_carrier_left") mirror([1, 0, 0]) mirror([0, 0, 1]) translate([0, 0, -(pivot_z - floor_t)]) door_carrier();
else if (part == "frame_side") translate([0, 0, -frame_x]) rotate([0, -90, 0]) frame_side();
else if (part == "front_bar") translate([0, 0, -(front_bar_y - 6)]) rotate([90, 0, 0]) front_bar();
else if (part == "bin") bin();
else if (part == "none") { }
else assembly();

module assembly() {
    color("white") on_bed() bed_plate();
    color("#2b2b2b") bed_side(false);
    color("#2b2b2b") mirror([1, 0, 0]) bed_side(true);
    // LED strips
    for (m = [0, 1]) mirror([m, 0, 0]) color("#fff2b0") on_bed() translate([side_in - 0.5, 6, led_n - led_w / 2]) cube([0.5, bed_len - 12, led_w]);
    // card resting against the pins
    color("#c9a46a") on_bed() translate([-card_w / 2, 1.5 + 3, 0.05]) cube([card_w, card_l, 0.3]);
    // pins + rocker (rotates about the pin servo shaft)
    color("orange") translate([0, pin_axis[0], pin_axis[1]]) rotate([show_pins_down ? pin_drop : 0, 0, 0]) translate([0, -pin_axis[0], -pin_axis[1]]) pin_rocker();
    // camera tower
    color("#3a3f47") on_bed() translate([tower_x, card_s, -4]) tower_post();
    color("#3a3f47") on_bed() translate([0, card_s, cam_height]) rotate([0, 0, 0]) camera_head();
    // chute, tilting about the y axis through (x = 0, z = pivot_z)
    translate([0, 0, pivot_z]) rotate([0, show_tilt, 0]) translate([0, 0, -pivot_z]) {
        color("#e8772e") chute();
        for (m = [0, 1]) mirror([m, 0, 0]) {
            color("#d0d0d0") translate([door_half, 0, hinge_z]) rotate([0, show_doors_open ? -90 : 0, 0]) translate([-door_half, 0, -hinge_z]) trapdoor();
            color("#2b2b2b") trapdoor_mount();
            color("#2b2b2b") hinge_lug();
        }
    }
    color("#2b2b2b") tilt_bracket();
    if (show_frame) {
        for (m = [0, 1]) mirror([m, 0, 0]) color("#2b2b2b", 0.9) frame_side();
        color("#2b2b2b") front_bar();
        for (i = [-1, 0, 1]) color("#3a3f47") translate([i * bin_pitch, 0, 0]) bin();
    }
}
