// Sorter Mk2 sort module: the tray that catches each card, tips it left or right, or opens its two
// trapdoors to drop it into the middle bin.
//
// It is chute v3's proven tray (the card pocket, door hinge line, crank-and-link door drive and
// tilt angles are the same), rebuilt without screws:
//   - The DECK is one printed frame: a front fascia (flush with the bin fronts, with the status
//     light slot), two thin side webs whose dovetail tongues ride the walls' sort rail, and a back
//     beam holding the tilt servo. It slides in from the front and two magnets hold it.
//   - The TRAY's back plate slides onto the tilt servo's double-arm horn (the horn's arms sit in a
//     slot, nothing screwed to the tray), and its front axle drops into an open bearing on the
//     fascia with a snap-on cap. To take the tray out: unclip the cap, lift the front, slide it off.
//   - Each DOOR turns in two closed bores: slide its long front journal forward through the front
//     wall, drop the back end in, slide it back into the back bore. The crank then pushes onto the
//     D-shaped end and clicks over its barb, so the door can't slide forward again.
//   - The door servos sit in closed pockets in the tray's front wall, held by a snap hook (no tabs
//     screwed). Each servo's own horn presses into its crank (the horn screw is the one screw left).
//   - The links turn on 3 mm steel pins pressed into the cranks; the fascia, 1 mm in front of them,
//     keeps them on.
//   - The servo leads run along the tray's front wall to the tilt axis, leave along it (they twist,
//     they don't bend), and follow a lidded channel on the right web to the right wall's trunk.
//
// Parts (set `part`): deck, tray, door (x2, the left one mirrored: door_l), door_crank, door_crank_l,
// servo_crank (x2: servo_crank_l mirrored), link (x2), bearing_cap, web_lid, light_bar.
// part = "sort" shows it assembled (`tilt`, `doors` for the moving parts).
include <joints.scad>
include <layout.scad>
part = "sort";
tilt = 0;          // degrees, + = right side down
doors = 0;         // 0 shut .. 1 open

// ---- MG90S (measured; the same numbers as bed_chute.scad) --------------------------------------
sv_len = 22.7;  sv_w = 12.2;  sv_shaft_off = 5.9;  sv_top = 6.6;  sv_tab_len = 32.2;  sv_body = 16.8;
horn2_len = 32;  horn2_w = 5.6;  horn2_hub = 7.6;   // stock double-arm horn: measure yours

// ---- tray (chute v3 numbers, raised to pivot_z) --------------------------------------------------
floor_t = 2.5;
hx = 36.6;                 // door hinge axes x = +-36.6, along y ...
hz = pivot_z - floor_t - 0.5;   // ... just under the floor
d_edge = 36;  d_gap = 0.25;
door_y = tray_in - 0.25;   // doors run y = +-45.25
hub_r = 4;  bore_r = hub_r + fit_turn;
wall_y0 = -tray_in - 8;    // front wall y -53.5 .. -45.5
back_y1 = tray_in + 6;     // back rail y 45.5 .. 51.5
back_h = 6;                // back rail above the floor (low, so it clears the bed when tipped)
front_h = 30;              // front rail: the falling card hits it
sv_x = 28;  sv_z = pivot_z + 60;   // door servo shafts: high, above where the falling card flies
mount_x = 41;  mount_top = sv_z + 12;
crank_r = 12;  crank_shut = 145;  crank_open = 95;
// along y, in front of the tray's front wall:
crank_y = [wall_y0 - 0.5, wall_y0 - 5];         // door crank -54 .. -58.5
scrank_y = [-tray_in - 11, -tray_in - 13.5];   // servo crank -56.5 .. -59 (the horn in a pocket behind it)
link_y = [-59.3, -62];
fascia_y = [front_y, front_y + 3];             // fascia -66 .. -63: the links run 1 mm behind it, so they can't come off their pins
axle_d = 8;  neck_d = 6.4;                     // front axle, with a neck the bearing's rib sits in
front_axle_y = [-63, wall_y0];
neck_y = [-61.5, -58.5];
plate_y1 = 55;             // the back plate thickens to here at the middle, with the horn slot behind
// tilt servo: shaft on the tilt axis, pointing forward; body behind
tsv_face = plate_y1 + 0.5 + sv_top;   // 62.1: the tilt servo's tab face (its horn sits in the back plate's slot, y 52.4 .. 55)

module along_y(a, b) { translate([0, min(a, b), 0]) rotate([-90, 0, 0]) linear_extrude(abs(b - a)) mirror([0, 1, 0]) children(); }
module hub_2d(r = hub_r) { intersection() { circle(r = r); translate([-r - 1, -r - 1]) square([2 * r + 2, pivot_z - hz + r + 1]); } }
module dshape_2d(r = hub_r) { intersection() { circle(r = r); translate([-r, -r]) square([2 * r, 1.5 * r]); } }   // D: flat on top

// MG90S stand-in, shaft at the origin pointing -y, long side along z, shaft near the top end
module servo_body() {
    translate([-sv_w / 2, 0, -(sv_len - sv_shaft_off)]) cube([sv_w, sv_body, sv_len]);          // body, behind the tab face
    translate([-sv_w / 2, -0.01, -(sv_len - sv_shaft_off) - (sv_tab_len - sv_len) / 2]) cube([sv_w, 2.5, sv_tab_len]);   // tabs
    translate([-sv_w / 2, -sv_top, -(sv_len - sv_shaft_off)]) cube([sv_w, sv_top, sv_len]);     // top
    translate([0, -sv_top, 0]) rotate([90, 0, 0]) cylinder(d = 5, h = 3.5);
}
// A pocket the servo slides into from behind (+y), tab face on z = 0 plane at y = 0; snap hook
// over the back of its body. Drawn the same orientation as servo_body.
module servo_pocket_cut() {
    translate([-sv_w / 2 - 0.25, -sv_top - 1, -(sv_len - sv_shaft_off) - 0.25]) cube([sv_w + 0.5, sv_top + 1.01, sv_len + 0.5]);    // the top, through the wall
    translate([-sv_w / 2 - 0.25, 0, -(sv_len - sv_shaft_off) - (sv_tab_len - sv_len) / 2 - 0.25]) cube([sv_w + 0.5, sv_body + 10, sv_tab_len + 0.5]);   // tabs and body
}
module servo_box(depth = sv_body + 2.5) {      // the box round the body, from the tab face back
    translate([-sv_w / 2 - 2.5, 0, -(sv_len - sv_shaft_off) - (sv_tab_len - sv_len) / 2 - 2.5]) cube([sv_w + 5, depth, sv_tab_len + 5]);
}
module servo_hook() {   // presses on the back of the body; drawn at the box's back top edge
    translate([0, sv_body + 0.1, sv_shaft_off + 2.5]) rotate([180, 0, 0]) rotate([0, 0, 90]) translate([0, 0, 0]) snap_hook(len = 10, t = 1.6, w = 6, lip = 1.2);
}

// ================================ TRAY ====================================================
module tray() {
    top = pivot_z;  bot = pivot_z - floor_t;
    difference() {
        union() {
            for (m = [0, 1]) mirror([m, 0, 0]) translate([d_edge + d_gap, -tray_in, bot]) cube([tray_half - d_edge - d_gap, 2 * tray_in, floor_t]);
            translate([-tray_half, wall_y0, bot]) cube([2 * tray_half, 8, front_h + floor_t]);
            translate([-mount_x, wall_y0, bot]) cube([2 * mount_x, 8, mount_top - bot]);
            translate([-tray_half, tray_in, bot]) cube([2 * tray_half, back_y1 - tray_in, back_h + floor_t]);
            // bosses round the door bores (they reach under the floor)
            for (m = [0, 1]) mirror([m, 0, 0]) for (y = [[wall_y0, -tray_in], [tray_in, back_y1]])
                translate([hx, 0, hz]) along_y(y[0], y[1]) circle(r = bore_r + 2.6);
            // servo boxes behind the front wall (above the card's flight)
            for (m = [0, 1]) mirror([m, 0, 0]) translate([sv_x, -tray_in, sv_z]) servo_box();
            // front axle, with its neck
            translate([0, 0, pivot_z]) along_y(front_axle_y[0], front_axle_y[1]) circle(d = axle_d);
            // back plate: thick in the middle, the tilt horn's slot behind it
            translate([-20, tray_in, bot - 4]) cube([40, plate_y1 - tray_in, back_h + floor_t + 4]);
            translate([0, 0, pivot_z]) along_y(back_y1 - 0.01, plate_y1) circle(r = 10);
        }
        translate([0, 0, pivot_z]) along_y(neck_y[0], neck_y[1]) difference() { circle(d = axle_d + 1); circle(d = neck_d); }
        // round the outer exit edges
        for (m = [0, 1]) mirror([m, 0, 0]) translate([tray_half, -tray_in - 1, top]) rotate([-90, 0, 0]) difference() {
            translate([-1.5, -1.5, 0]) cube([3, 3, 2 * tray_in + 2]); translate([-1.5, 1.5, -1]) cylinder(r = 1.5, h = 2 * tray_in + 4); }
        // door bores, closed
        for (m = [0, 1]) mirror([m, 0, 0]) for (y = [[wall_y0 - 1, -tray_in + 0.01], [tray_in - 0.01, back_y1 + 1]])
            translate([hx, 0, hz]) along_y(y[0], y[1]) circle(r = bore_r);
        // keep the card pocket clear (bosses and back plate stay below the floor top)
        translate([-tray_half - 1, -tray_in, top]) cube([2 * tray_half + 2, 2 * tray_in, 100]);
        for (m = [0, 1]) mirror([m, 0, 0]) translate([d_edge - 0.01, -tray_in + 0.01, bot - 20]) cube([d_gap + 0.02, 2 * tray_in - 0.02, 30]);
        // between the door bores the floor is open (the doors fill it)
        translate([-d_edge - d_gap, -tray_in, bot - 20]) cube([2 * (d_edge + d_gap), 2 * tray_in, 20 + floor_t + 0.01]);
        // servo pockets
        for (m = [0, 1]) mirror([m, 0, 0]) translate([sv_x, -tray_in, sv_z]) servo_pocket_cut();
        // the tilt horn's slot (double arm, 2.6 deep) in the back plate's back face
        translate([0, plate_y1 + 0.01, pivot_z]) rotate([90, 0, 0]) linear_extrude(2.6) offset(delta = 0.2) {
            circle(d = horn2_hub);  translate([-horn2_len / 2, -horn2_w / 2]) square([horn2_len, horn2_w]); }
        translate([0, plate_y1 - 5, pivot_z]) rotate([-90, 0, 0]) cylinder(d = 7.4, h = 6);   // the servo's spline boss
        // servo leads: a groove along the front wall's back face to the axle, and out through it
        for (m = [0, 1]) mirror([m, 0, 0]) translate([0, -tray_in - 2.5, mount_top - 22]) cube([sv_x - 8, 2.51, 3]);
        translate([-1.5, -tray_in - 2.5, pivot_z + 2]) cube([3, 2.51, mount_top - 22 - pivot_z]);
        translate([0, 0, pivot_z]) along_y(front_axle_y[0] - 1, -tray_in - 1) circle(d = 3.4);
        translate([0, -tray_in - 2.5, pivot_z]) rotate([-90, 0, 0]) cylinder(d = 3.4, h = 3);
    }
    for (m = [0, 1]) mirror([m, 0, 0]) translate([sv_x, -tray_in, sv_z]) servo_hook();
}

// ================================ DOORS =================================================
// right door; door_l is its mirror image. Long front journal (through the wall, D-shaped end for
// the crank, split with a barb at its tip), short back stub.
front_j = [crank_y[1] - 1.6, -tray_in + 0.75];   // -60.1 .. -44.75
back_j = [tray_in - 0.75, back_y1 - 0.3];
module door() {
    top = pivot_z;
    difference() {
        union() {
            translate([d_gap, -door_y, top - floor_t]) cube([d_edge - d_gap, 2 * door_y, floor_t]);
            translate([hx - 8, -door_y, hz - 4]) cube([7, 2 * door_y, 4.01]);
            translate([hx, 0, hz]) along_y(wall_y0 + 0.01, front_j[1]) hub_2d();
            translate([hx, 0, hz]) along_y(back_j[0], back_j[1]) hub_2d();
            translate([hx, 0, hz]) along_y(front_j[0] + 1.6, wall_y0 + 0.02) dshape_2d();
            // the barb at the tip
            translate([hx, front_j[0] + 1.6, hz]) rotate([90, 0, 0]) cylinder(r1 = hub_r + 0.35, r2 = hub_r - 0.6, h = 1.6);
            for (y = [-door_y, door_y - 6]) translate([hx - 8, y, hz - 4]) cube([d_edge - hx + 8, 6, 4 + floor_t]);
        }
        translate([hx - 0.45, front_j[0] - 1, hz - hub_r - 1]) cube([0.9, 8, 2 * hub_r + 2]);   // the split
        translate([hx - 1.5, front_j[0] - 1, hz + hub_r * 0.5]) cube([3, 20, 4]);              // D flat
    }
}

// ================================ CRANKS AND LINKS ======================================
module door_crank() {
    a = crank_shut;
    difference() {
        hull() {
            translate([hx, 0, hz]) along_y(crank_y[0], crank_y[1]) circle(r = 6.5);
            translate([hx + crank_r * cos(a), 0, hz + crank_r * sin(a)]) along_y(crank_y[0], crank_y[1]) circle(r = 4.5);
        }
        translate([hx, 0, hz]) along_y(crank_y[0] + 1, crank_y[1] - 1) offset(delta = 0.15) dshape_2d();
        translate([hx + crank_r * cos(a), crank_y[1] - 1, hz + crank_r * sin(a)]) rotate([-90, 0, 0]) cylinder(d = pin_press, h = 10, $fn = 32);
    }
}
horn1_len = 22;  horn1_w = 6.6;  horn1_hub = 7.8;  horn_turn = 90;  horn_reach = 17;
module servo_crank() {
    a = crank_shut;
    difference() {
        hull() {
            translate([sv_x, 0, sv_z]) along_y(scrank_y[0], scrank_y[1]) circle(r = 7);
            translate([sv_x + crank_r * cos(a), 0, sv_z + crank_r * sin(a)]) along_y(scrank_y[0], scrank_y[1]) circle(r = 4.5);
            translate([sv_x + horn_reach * cos(a + horn_turn), 0, sv_z + horn_reach * sin(a + horn_turn)]) along_y(scrank_y[0], scrank_y[1]) circle(r = 4.5);
        }
        translate([sv_x, 0, sv_z]) along_y(scrank_y[0] + 1, scrank_y[0] - 2) rotate(a + horn_turn) {
            circle(d = horn1_hub);  translate([0, -horn1_w / 2]) square([horn1_len + 5, horn1_w]); }
        translate([sv_x, scrank_y[1] - 1, sv_z]) rotate([-90, 0, 0]) cylinder(d = 2.4, h = 10);
        translate([sv_x + crank_r * cos(a), scrank_y[1] - 1, sv_z + crank_r * sin(a)]) rotate([-90, 0, 0]) cylinder(d = pin_press, h = 10, $fn = 32);
    }
}
module link() {
    a = crank_shut;
    p0 = [hx + crank_r * cos(a), hz + crank_r * sin(a)];
    p1 = [sv_x + crank_r * cos(a), sv_z + crank_r * sin(a)];
    difference() {
        hull() for (p = [p0, p1]) translate([p[0], 0, p[1]]) along_y(link_y[0], link_y[1]) circle(r = 4);
        for (p = [p0, p1]) translate([p[0], link_y[1] - 1, p[1]]) rotate([-90, 0, 0]) cylinder(d = pin_free, h = 6, $fn = 32);
    }
}

// ================================ DECK ==================================================
web_t = 3;                       // side webs x 116 .. 119
web_x = wall_in - fit_slide;     // outer face of the webs
deck_y1 = 88;                    // back of the back beam
fascia_z = [bin_top + reveal, sort_top_z - reveal];
beam_z = [190, 214];
light_slot = [150, 5];           // status light slot in the fascia (white bar behind it)
module deck() {
    difference() {
        union() {
            // fascia, with thick end blocks (magnets) and a bearing block in the middle
            translate([-web_x, fascia_y[0], fascia_z[0]]) cube([2 * web_x, fascia_y[1] - fascia_y[0], fascia_z[1] - fascia_z[0]]);
            for (s = [-1, 1]) translate([s > 0 ? web_x - 14 : -web_x, fascia_y[0], fascia_z[0]]) cube([14, 12, fascia_z[1] - fascia_z[0]]);
            translate([-10, fascia_y[0], fascia_z[0]]) cube([20, neck_y[1] + 0.2 - fascia_y[0], pivot_z + 7 - fascia_z[0]]);
            // side webs with their dovetail tongues
            for (s = [-1, 1]) {
                translate([s > 0 ? web_x - web_t : -web_x, fascia_y[0], rail_sort[0] - 7]) cube([web_t, deck_y1 - fascia_y[0], 14]);
                // the tongue starts at the wall's face; a 6 mm neck bridges the 0.3 mm gap
                translate([s * wall_in, fascia_y[0] + 2, rail_sort[0]]) multmatrix([[0, 0, s, 0], [0, 1, 0, 0], [s, 0, 0, 0], [0, 0, 0, 1]])
                    translate([0, 0, -0.01]) dove_rail(deck_y1 - fascia_y[0] - 4);
                translate([s > 0 ? web_x - 0.01 : -wall_in - 0.01, fascia_y[0] + 2, rail_sort[0] - dove_w / 2]) cube([wall_in - web_x + 0.02, deck_y1 - fascia_y[0] - 4, dove_w]);
            }
            // back beam across, and the tilt servo's box on it
            translate([-web_x, tsv_face + 8, beam_z[0]]) cube([2 * web_x, deck_y1 - tsv_face - 8, beam_z[1] - beam_z[0]]);
            translate([0, tsv_face, pivot_z]) servo_box(depth = deck_y1 - tsv_face);
        }
        // the front axle's bearing: open top, a rib in the neck stops it sliding
        translate([0, 0, pivot_z]) along_y(fascia_y[0] - 1, neck_y[0] + 0.3) circle(d = axle_d + 2 * fit_turn);
        translate([0, 0, pivot_z]) along_y(neck_y[1] - 0.3, neck_y[1] + 2) circle(d = axle_d + 2 * fit_turn);
        translate([0, 0, pivot_z]) along_y(neck_y[0] + 0.29, neck_y[1] - 0.29) circle(d = neck_d + 2 * fit_turn);
        translate([-(axle_d / 2 + fit_turn), fascia_y[0] - 1, pivot_z]) cube([axle_d + 2 * fit_turn, 20, 20]);
        // the cap's two magnets
        for (s = [-1, 1]) translate([s * 7.5, fascia_y[0] + 4.5, pivot_z + 7 - mag_pocket_h + 0.01]) magnet_cut();
        // tilt servo pocket (its top faces forward on the tilt axis)
        translate([0, tsv_face, pivot_z]) servo_pocket_cut();
        // magnets in the fascia's ends
        for (s = [-1, 1]) translate([s * (web_x + 0.01), front_y + 5, pivot_z]) rotate([0, s > 0 ? -90 : 90, 0]) magnet_cut();
        // the status light slot, and the light bar's pocket behind it
        translate([-light_slot[0] / 2, fascia_y[0] - 1, fascia_z[1] - 14]) cube([light_slot[0], 10, light_slot[1]]);
        // finger grip under the fascia's bottom edge
        translate([0, fascia_y[0] - 0.01, fascia_z[0] - 0.01]) scale([1, 1, 0.3]) rotate([-90, 0, 0]) cylinder(d = 50, h = 2, $fn = 48);
        // servo-lead channel along the right web's inner face
        translate([web_x - web_t - 0.01, fascia_y[0] + 12, rail_sort[0] - 4.5]) cube([1.6, deck_y1 - fascia_y[0] - 12, 9]);
    }
}
// Cap that closes the front bearing over the axle; two magnets hold it (lift it off by hand).
module bearing_cap() {
    difference() {
        translate([-10, fascia_y[0], pivot_z + 7 + 0.2]) cube([20, neck_y[1] + 0.2 - fascia_y[0], 7]);
        translate([0, 0, pivot_z]) along_y(fascia_y[0] - 1, neck_y[1] + 2) circle(d = axle_d + 2 * fit_turn);
        for (s = [-1, 1]) translate([s * 7.5, fascia_y[0] + 4.5, pivot_z + 7.2 - 0.01]) magnet_cut();
    }
    // a tongue that drops into the bearing slot and holds the axle down
    difference() {
        translate([-(axle_d / 2 + fit_turn) + 0.2, fascia_y[0] + 0.5, pivot_z + axle_d / 2 + 0.3]) cube([axle_d + 2 * fit_turn - 0.4, neck_y[1] - fascia_y[0] - 0.6, 7 - axle_d / 2 + 0.2]);
    }
}
// White diffuser bar behind the fascia's status light slot; the 14 status LEDs stick on its back.
module light_bar() { translate([-light_slot[0] / 2 + 0.2, fascia_y[0] + 0.01, fascia_z[1] - 14 + 0.2]) cube([light_slot[0] - 0.4, 10, light_slot[1] - 0.4]); }

// ================================ ASSEMBLY ==================================================
module tray_moving(t = 0, o = 0) {
    a = o * crank_open;
    translate([0, 0, pivot_z]) rotate([0, t, 0]) translate([0, 0, -pivot_z]) {
        color("#e8772e") tray();
        for (m = [0, 1]) mirror([m, 0, 0]) {
            translate([hx, 0, hz]) rotate([0, -a, 0]) translate([-hx, 0, -hz]) { color("#d0d0d0") door(); color("#2b2b2b") door_crank(); }
            translate([sv_x, 0, sv_z]) rotate([0, -a, 0]) translate([-sv_x, 0, -sv_z]) color("#2b2b2b") servo_crank();
            translate([crank_r * (cos(crank_shut + a) - cos(crank_shut)), 0, crank_r * (sin(crank_shut + a) - sin(crank_shut))]) color("#5a6068") link();
            color("#3060c0") translate([sv_x, -tray_in, sv_z]) servo_body();
        }
    }
}
module sort_assembly() {
    color("#3a3f47") deck();
    color("#2b2b2b") bearing_cap();
    color("#f4f4f4") light_bar();
    color("#3060c0") translate([0, tsv_face, pivot_z]) servo_body();
    tray_moving(tilt, doors);
}

if (part == "sort") sort_assembly();
if (part == "deck") deck();
if (part == "tray") tray();
if (part == "door") door();
