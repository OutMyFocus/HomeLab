// Sorter Mk2 sorting levels: the card's two floors, the trapdoors, and the sideways pushers.
//
//   level 1 (lv1_z)   floor = two trapdoors, hinged at the pocket's front and back edges, each on
//                     its own MG90S (the servo's shaft is the door's hinge on the left, a 3 mm steel
//                     pin on the right). Both open together: the card falls flat down the shaft.
//   level 2 (lv2_z)   a fixed floor, and the two shelves bins 1 and 2 stand on.
//   pusher (each)     a carriage: two paddles either side of the card on one crossbar behind the
//                     pocket, running along x on a dovetail on the level's back beam. Its MG90S sits
//                     under the beam with a 72 mm lever whose pin runs in a slot in the crossbar
//                     (scotch yoke): +-80 degrees of servo = +-71 mm of paddle. Left paddle pushes
//                     the card right into the bin there, and the other way round. Two fingers on each
//                     paddle run 0.8 mm below the floor in grooves, so a thin card can't slip under.
//
// Each level frame slides in from the front on the walls' rails and a magnet holds it home; its
// fascia is the machine's face between the bin rows. Nothing is screwed or glued: the doors, the
// carriage and the lever come off by pulling 3 mm steel pins or sliding them off their rails.
//
// Parts: lv1_frame, door (x2, the same part turned round), lv2_frame, carriage (x2), lever (x2),
// col_front, liner_back. `part = "levels"` shows both levels assembled; `push` (-1..1) and
// `doors` (0..1) move them.
include <joints.scad>
include <layout.scad>
part = "levels";
push = 0;
doors = 0;

// ---- MG90S (measured; same numbers as the sort module) ---------------------------------------
sv_len = 22.7;  sv_w = 12.2;  sv_shaft_off = 5.9;  sv_top = 6.6;  sv_tab_len = 32.2;  sv_body = 16.8;
horn1_hub = 7.8;  horn1_w = 6.6;  horn1_len = 22;

// A servo stand-in, its shaft on the origin pointing -x ("top" faces -x), the long side along +u,
// where u is +y (dir = [0,1,0]) or +z (dir = [0,0,1]); the shaft sits sv_shaft_off from that end.
module servo_x(dir, g = 0) {
    // body coordinates: a = along the shaft (+x is into the body), u = long side, w = the other way
    m = dir[2] == 1 ? [[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]] : [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];
    multmatrix(m) {
        translate([-sv_top - g, -sv_shaft_off - g, -sv_w / 2 - g]) cube([sv_top + sv_body + 2 * g, sv_len + 2 * g, sv_w + 2 * g]);
        translate([0 - g, -sv_shaft_off - (sv_tab_len - sv_len) / 2 - g, -sv_w / 2 - g]) cube([2.5 + 2 * g, sv_tab_len + 2 * g, sv_w + 2 * g]);
        translate([-sv_top - 2.9, 0, 0]) rotate([0, 90, 0]) cylinder(d = 5 + 2 * g, h = 2.9 + 0.01);
    }
}
// the pocket the servo slides into (from +x, its tabs on a shoulder) and the box round it
module servo_x_cut(dir) {
    servo_x(dir, 0.25);
    m = dir[2] == 1 ? [[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]] : [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];
    multmatrix(m) translate([0, -sv_shaft_off - (sv_tab_len - sv_len) / 2 - 0.25, -sv_w / 2 - 0.25]) cube([sv_body + 20, sv_tab_len + 0.5, sv_w + 0.5]);
}
module servo_x_box(dir, depth = sv_body + 2.5) {
    m = dir[2] == 1 ? [[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]] : [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];
    multmatrix(m) translate([-sv_top + 0.5, -sv_shaft_off - (sv_tab_len - sv_len) / 2 - 2.5, -sv_w / 2 - 2.5]) cube([sv_top - 0.5 + depth, sv_tab_len + 5, sv_w + 5]);
}
// a snap hook over the back of the servo's body, so it can't back out of its pocket
module servo_x_hook(dir) {
    m = dir[2] == 1 ? [[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]] : [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];
    multmatrix(m) translate([sv_body + 2.5, sv_len / 2 - sv_shaft_off, sv_w / 2 + 2.5]) rotate([0, 90, 0]) rotate([0, 0, 180]) translate([0, 0, -10]) snap_hook(len = 10, t = 1.6, w = 6, lip = 1.2);
}

// ---- doors (level 1) --------------------------------------------------------------------------
hinge_y = 56.5;  hinge_z = -2.5;       // relative to the level's floor: far enough out that the door
                                       // servos' boxes stay clear of the card (|y| <= 45.5) and the bins
door_t = 2.5;  knuckle_r = 3;  knuckle_x = 33.2;  door_gap = 0.25;
sv_door_x = -knuckle_x - 0.3 - 3.5 - sv_top;   // the servo's tab face: its horn's hub sits between its top and the knuckle
// One door, drawn as the BACK door of a level at z = 0 (hinge at y = +hinge_y); the front door is
// the same part turned 180 degrees about z.
module door() {
    difference() {
        union() {
            translate([-knuckle_x, door_gap, -door_t]) cube([2 * knuckle_x, hinge_y - door_gap, door_t]);
            translate([-knuckle_x, hinge_y, hinge_z]) rotate([0, 90, 0]) cylinder(r = knuckle_r, h = 2 * knuckle_x);
            translate([-knuckle_x, hinge_y - knuckle_r, hinge_z]) cube([2 * knuckle_x, knuckle_r, -hinge_z]);
        }
        // fingers' grooves
        translate([-pk_x - 1, finger_y - 1.8, -0.8]) cube([2 * pk_x + 2, 3.6, 1]);
        // the servo's single-arm horn presses into the left end; the right end turns on a 3 mm pin
        translate([-knuckle_x - 0.01, hinge_y, hinge_z]) rotate([0, 90, 0]) linear_extrude(1.8) { circle(d = horn1_hub); rotate(-90) translate([0, -horn1_w / 2]) square([horn1_len - 7, horn1_w]); }
        translate([-knuckle_x - 0.01, hinge_y, hinge_z]) rotate([0, 90, 0]) cylinder(d = 2.4, h = 8);
        translate([knuckle_x - 8, hinge_y, hinge_z]) rotate([0, 90, 0]) cylinder(d = pin_free, h = 8.02, $fn = 32);
        // the same horn pocket and pin hole at the other end, so one part is both doors
        translate([knuckle_x + 0.01, hinge_y, hinge_z]) rotate([0, -90, 0]) linear_extrude(1.8) { circle(d = horn1_hub); rotate(90) translate([0, -horn1_w / 2]) square([horn1_len - 7, horn1_w]); }
        translate([-knuckle_x - 0.01, hinge_y, hinge_z]) rotate([0, 90, 0]) cylinder(d = pin_free, h = 8.02, $fn = 32);
        // the floor surface ends in a 0.4 chamfer at the push edges
        for (m = [0, 1]) mirror([m, 0, 0]) translate([pk_x - 1, -1, -1]) rotate([-90, 0, 0]) difference() {
            translate([0, -2, 0]) cube([2, 2, hinge_y + 2]); translate([0, 0, -1]) cylinder(r = 1, h = hinge_y + 4, $fn = 24); }
    }
}
module door_at(L, front, open = 0) {
    a = open * 90;
    translate([0, 0, L]) rotate([0, 0, front ? 180 : 0]) translate([0, hinge_y, hinge_z]) rotate([a, 0, 0]) translate([0, -hinge_y, -hinge_z]) door();
}

// ---- pusher carriage ----------------------------------------------------------------------------
xbar_z = [-46, 12];                    // crossbar, relative to the floor
neck_z = [paddle_h + 1, paddle_h + 7]; // the necks run over the back rail and the back door's hinge
xbar_half = paddle_in + paddle_t;      // 36.5
module carriage(lv = 1) {
    difference() {
        union() {
            for (m = [0, 1]) mirror([m, 0, 0]) {
                // paddle: a bar beside the card, with two fingers
                // fully rounded profile, so the card only ever meets a smooth curve
                hull() for (z = [0.2 + paddle_t / 2, paddle_h - paddle_t / 2]) for (y = [-paddle_y + paddle_t / 2, paddle_y - paddle_t / 2])
                    translate([paddle_in + paddle_t / 2, y, z]) sphere(d = paddle_t, $fn = 24);
                translate([paddle_in + paddle_t / 2, -paddle_y + paddle_t / 2, 0.2 + paddle_t / 2]) rotate([-90, 0, 0]) cylinder(d = paddle_t, h = 2 * paddle_y - paddle_t, $fn = 24);
                for (y = [-finger_y, finger_y]) hull() for (yy = [y - 0.6, y + 0.6]) for (z = [-0.8 + 0.6, 1.2])
                    translate([paddle_in + paddle_t / 2, yy, z]) rotate([0, 90, 0]) cylinder(d = 1.2, h = paddle_t, center = true, $fn = 16);
                // the neck back to the crossbar (level 1 climbs over the back rail, level 2 stays low)
                if (lv == 1) {
                    hull() {
                        translate([paddle_in, paddle_y - 8, 0.2]) cube([paddle_t, 8, paddle_h - 0.2]);
                        translate([paddle_in, paddle_y - 2, neck_z[0]]) cube([paddle_t, 4, neck_z[1] - neck_z[0]]);
                    }
                    translate([paddle_in, paddle_y, neck_z[0]]) cube([paddle_t, xbar_y[0] - paddle_y + 0.01, neck_z[1] - neck_z[0]]);
                } else {
                    translate([paddle_in, paddle_y - 0.01, 0.2]) cube([paddle_t, xbar_y[0] - paddle_y + 0.02, paddle_h - 0.2]);
                }
            }
            // the crossbar
            translate([-xbar_half, xbar_y[0], xbar_z[0]]) cube([2 * xbar_half, xbar_y[1] - xbar_y[0], xbar_z[1] - xbar_z[0]]);
            // the dovetail tongue under it, along x
            translate([-xbar_half, (xbar_y[0] + xbar_y[1]) / 2, xbar_z[0] + 0.01]) rotate([0, 0, -90]) mirror([0, 0, 1]) dove_rail(2 * xbar_half, 3, 2);
        }
        // the lever's pin runs in this vertical slot
        translate([-1.75 - 0.15, xbar_y[1] - 3, xbar_z[0] + 4]) cube([3.5 + 0.3, 3.01, xbar_z[1] - xbar_z[0] - 8]);
        // lighten the crossbar
        for (x = [-22, 0, 22]) translate([x - 7, xbar_y[0] - 1, xbar_z[0] + 8]) cube([14, xbar_y[1] - xbar_y[0] - 2.5, xbar_z[1] - xbar_z[0] - 16]);
    }
}
module carriage_at(L, lv, p = 0) translate([p * push_stroke, 0, L]) carriage(lv);

// the lever: servo horn pocket at its hub, a 3 mm steel pin at its tip
module lever() {
    difference() {
        hull() {
            cylinder(r = 7, h = lever_y[1] - lever_y[0]);
            translate([0, lever_r, 0]) cylinder(r = 4, h = lever_y[1] - lever_y[0]);
        }
        translate([0, 0, -0.01]) linear_extrude(1.8) translate([-horn1_w / 2, 0]) square([horn1_w, horn1_len - 3]);
        translate([0, 0, -1]) cylinder(d = horn1_hub, h = 10);   // the horn's hub goes right through
        translate([0, lever_r, -1]) cylinder(d = pin_press, h = 10, $fn = 32);
    }
}
module lever_at(L, p = 0) {
    a = asin(max(-1, min(1, p * push_stroke / lever_r)));
    translate([0, lever_y[1], L + psv_dz]) rotate([90, 0, 0]) rotate([0, 0, a]) lever();
}
// the lever's pin (3 x 12, pressed into the lever, sliding in the crossbar's slot)
module lever_pin_at(L, p = 0) {
    a = asin(max(-1, min(1, p * push_stroke / lever_r)));
    translate([0, 0, L + psv_dz]) translate([-lever_r * sin(a), 0, lever_r * cos(a)]) translate([0, xbar_y[1] - 3, 0]) rotate([-90, 0, 0]) cylinder(d = 3, h = lever_y[1] - xbar_y[1] + 3);
}

// ---- level frame (shared) ------------------------------------------------------------------------
web_x = wall_in - fit_slide;           // 111.7: the webs' outer faces
web_t = 3;
beam = [[64, 72.5], [-56, -46]];       // back beam (y, z rel. floor): carries the carriage's dovetail on top
fascia_y = [front_y + reveal / 2, front_y + 4];
bin_fp_back = front_y + reveal / 2 + 4;   // the bins' front plates' back faces (-61.75)
module level_webs(L, zr, yr, fz) {
    for (m = [0, 1]) mirror([m, 0, 0]) {
        translate([web_x - web_t, bin_fp_back + 0.25, L + zr[0]]) cube([web_t, yr[1] - bin_fp_back - 0.25, zr[1] - zr[0]]);
        translate([web_x - web_t, fascia_y[1] - 0.01, fz[0]]) cube([web_t, bin_fp_back + 0.26 - fascia_y[1], fz[1] - fz[0]]);
    }
}
module web_tongues(L, rz) {
    for (m = [0, 1]) mirror([m, 0, 0]) {
        translate([wall_in, front_y + 2, rz]) multmatrix([[0, 0, 1, 0], [0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 1]]) translate([0, 0, -0.01]) dove_rail(56 - front_y - 4);
        translate([web_x - 0.01, front_y + 2, rz - dove_w / 2]) cube([wall_in - web_x + 0.02, 56 - front_y - 4, dove_w]);
    }
}
module web_tongue_cuts(rz) for (m = [0, 1]) mirror([m, 0, 0]) translate([wall_in - 2.5, 56 - 8, rz + dove_w / 2 + 5]) rotate([0, 90, 0]) magnet_cut();
module back_beam(L) {
    difference() {
        translate([-web_x + web_t - 0.01, beam[0][0], L + beam[1][0]]) cube([2 * (web_x - web_t) + 0.02, beam[0][1] - beam[0][0], beam[1][1] - beam[1][0]]);
        translate([-web_x, (xbar_y[0] + xbar_y[1]) / 2, L + beam[1][1] + 0.01]) rotate([0, 0, -90]) mirror([0, 0, 1]) dove_slot_cut(2 * web_x, 3, 2, false);
    }
    // the pusher servo's box, under the beam's back edge, shaft on x = 0 pointing -y
    difference() {
        translate([0, psv_face + sv_top, L + psv_dz]) rotate([0, 0, 90]) servo_x_box([0, 0, 1]);
        translate([0, psv_face + sv_top, L + psv_dz]) rotate([0, 0, 90]) servo_x_cut([0, 0, 1]);
    }
    translate([0, psv_face + sv_top, L + psv_dz]) rotate([0, 0, 90]) servo_x_hook([0, 0, 1]);
    // the box stands on a bracket that runs under the lever's hub back from the beam
    translate([-sv_w / 2 - 2.5, beam[0][0], L + beam[1][0] - 12]) cube([sv_w + 5, psv_face + sv_top + sv_body + 2.5 - beam[0][0], 10.01]);
    translate([-sv_w / 2 - 2.5, beam[0][0], L + beam[1][0] - 12]) cube([sv_w + 5, beam[0][1] - beam[0][0], 12.02]);
}

// ================================ LEVEL 1 ====================================================
// Fascia (the machine's face over bins 1 and 2), front wall (the card from the bed stops on it),
// the hinge bars front and back (left: the door servos; right: the doors' pins), back rail,
// back beam with the pusher, webs with the rail tongues.
bar_y = [hinge_y - 3.5, hinge_y + 3.5];  bar_z = [-11, 1];
lv1_fz = [-14.5, front_h + 3.5];       // fascia z (rel. floor): from bin 1's top + 0.5 to the front cover
module lv1_frame() {
    L = lv1_z;
    difference() {
        union() {
            level_webs(L, [beam[1][0], lv1_fz[1]], [front_y + 4, beam[0][1]], [L + lv1_fz[0], L + lv1_fz[1]]);
            web_tongues(L, rail_lv1[0]);
            translate([-web_x, fascia_y[0], L + lv1_fz[0]]) ccube([2 * web_x, fascia_y[1] - fascia_y[0], lv1_fz[1] - lv1_fz[0]]);
            // front wall and the two ribs that hold it off the fascia
            difference() {
                translate([-26, -pk_y - 3, L + 0.5]) cube([52, 3, front_h]);
                translate([-27, -pk_y, L + 0.5 + front_h]) rotate([45, 0, 0]) cube([54, 2.8, 2.8], center = true);
            }
            for (m = [0, 1]) mirror([m, 0, 0]) translate([22, fascia_y[1] - 0.01, L + front_h - 9.5]) cube([4, -pk_y - fascia_y[1] + 0.02, 10]);
            // hinge bars (y +-46..53), each side, web to the hinge; left ends carry the door servos
            for (f = [-1, 1]) for (m = [0, 1]) mirror([m, 0, 0]) {
                y0 = f > 0 ? bar_y[0] : -bar_y[1];
                translate([knuckle_x + 0.3, y0, L + bar_z[0]]) cube([web_x - web_t - knuckle_x - 0.3 + 0.01, bar_y[1] - bar_y[0], bar_z[1] - bar_z[0]]);
            }
            // right bosses for the doors' pins
            for (f = [-1, 1]) translate([knuckle_x + 0.3, f * hinge_y, L + hinge_z]) rotate([0, 90, 0]) cylinder(r = 4.5, h = 4);
            // door servo boxes: front one long side up, back one long side back
            translate([sv_door_x, -hinge_y, L + hinge_z]) mirror([1, 0, 0]) servo_x_box([0, 0, 1]);
            translate([sv_door_x, hinge_y, L + hinge_z]) mirror([1, 0, 0]) mirror([0, 0, 1]) servo_x_box([0, 0, 1]);
            // back rail (the card can't bounce back off the floor), hung from the bars' inner ends
            difference() {
                translate([-26, pk_y, L + 0.5]) cube([52, 3, 6]);
                translate([-27, pk_y, L + 6.5]) rotate([45, 0, 0]) cube([54, 4.3, 4.3], center = true);
            }
            for (m = [0, 1]) mirror([m, 0, 0]) translate([25.9, pk_y, L + 0.5]) cube([3, bar_y[0] - pk_y + 0.01, 6]);
            for (m = [0, 1]) mirror([m, 0, 0]) translate([25.9, bar_y[0], L + 0.5]) cube([knuckle_x + 0.3 + 4 - 25.9, bar_y[1] - bar_y[0], 6]);
            back_beam(L);
            // stiffen: the beam to the bars
            for (m = [0, 1]) mirror([m, 0, 0]) translate([web_x - web_t - 12, bar_y[1] - 0.01, L + beam[1][0]]) cube([12, beam[0][0] - bar_y[1] + 0.02, bar_z[1] - beam[1][0]]);
        }
        web_tongue_cuts(rail_lv1[0]);
        // servo pockets (they slide in from the outside, -x)
        translate([sv_door_x, -hinge_y, L + hinge_z]) mirror([1, 0, 0]) servo_x_cut([0, 0, 1]);
        translate([sv_door_x, hinge_y, L + hinge_z]) mirror([1, 0, 0]) mirror([0, 0, 1]) servo_x_cut([0, 0, 1]);
        // doors' pins (3 x 10 mm, pressed into the boss)
        for (f = [-1, 1]) translate([knuckle_x - 2, f * hinge_y, L + hinge_z]) rotate([0, 90, 0]) pin_press_cut(10);
        // the doors swing through here
        translate([-knuckle_x - 0.3, -hinge_y - knuckle_r - 1, L - 70]) cube([2 * knuckle_x + 0.6, 2 * (hinge_y + knuckle_r + 1), 70.5]);
        // status light slot in the fascia
        translate([-60, front_y - 1, L + 18]) cube([120, 7, 3]);
        // the power button: a 16 mm LED-ring push button, nut behind the fascia (its body stays
        // above the paddles and the cards going into bin 2), with a ring engraved round it
        translate([pwr_btn[0], front_y - 1, L + pwr_btn[1]]) rotate([-90, 0, 0]) cylinder(d = 16.3, h = 10, $fn = 64);
        translate([pwr_btn[0], front_y + reveal / 2 - 0.01, L + pwr_btn[1]]) rotate([-90, 0, 0]) difference() {
            cylinder(d = 24, h = 0.6, $fn = 64);  translate([0, 0, -1]) cylinder(d = 22.4, h = 3, $fn = 64); }
    }
}

// ================================ LEVEL 2 ====================================================
// Floor, two shelves (bins 1 and 2 stand on them), the fascia between the bin rows, back beam
// with the pusher, webs with the rail tongues. The shaft's back liner and the front column (front
// panel + front liner) stand in its grooves.
module lv2_frame() {
    L = lv2_z;
    difference() {
        union() {
            level_webs(L, [beam[1][0], shelf_z + shelf_t - L], [front_y + 4, beam[0][1]], [bin3_z + bin_h + reveal, bin1_z - reveal]);
            web_tongues(L, rail_lv2[0]);
            translate([-web_x, fascia_y[0], bin3_z + bin_h + reveal]) ccube([2 * web_x, fascia_y[1] - fascia_y[0], bin1_z - reveal - bin3_z - bin_h - reveal]);
            // the floor, in front of and behind the pocket too (it ties the front to the back)
            translate([-pk_x, fascia_y[1] - 0.01, L - 3]) cube([2 * pk_x, beam[0][0] - fascia_y[1] + 0.02, 3]);
            // shelves
            for (m = [0, 1]) mirror([m, 0, 0]) difference() {
                translate([bin_x - bin_out_x / 2, fascia_y[1] - 0.01, shelf_z]) cube([web_x - web_t - bin_x + bin_out_x / 2 + 0.02, beam[0][0] - fascia_y[1] + 0.02, shelf_t]);
            }
            for (m = [0, 1]) mirror([m, 0, 0]) translate([bin_x, 0, 0]) bin_seat_here(shelf_z + shelf_t);
            // posts: shelves to floor at the front and back (outside the paddles' run, y beyond +-41)
            // the floor's back edge hangs a plate down to the back beam (behind the paddles' run)
            translate([-pk_x, beam[0][0] - 2, L + beam[1][1] - 0.01]) cube([2 * pk_x, 2, -beam[1][1] - 3 + 0.02]);
            for (m = [0, 1]) mirror([m, 0, 0]) for (y = [[bin_fp_back + 0.25, -pk_y - 3]])
                translate([pk_x - 0.01, y[0] - 0.01, L - 3]) cube([bin_x - bin_out_x / 2 - pk_x + 0.02, y[1] - y[0] + 0.02, shelf_z + shelf_t - L + 3]);
            back_beam(L);
            for (m = [0, 1]) mirror([m, 0, 0]) translate([web_x - web_t - 12, bin_back + 6, L + beam[1][0]]) cube([12, beam[0][0] - bin_back - 6 + 0.01, -1 - beam[1][0]]);
        }
        web_tongue_cuts(rail_lv2[0]);
        translate([-pk_x - 1, finger_y - 1.8, L - 0.8]) cube([2 * pk_x + 2, 3.6, 1]);
        translate([-pk_x - 1, -finger_y - 1.8, L - 0.8]) cube([2 * pk_x + 2, 3.6, 1]);
        for (m = [0, 1]) mirror([m, 0, 0]) translate([pk_x - 1, fascia_y[1] - 1, L - 1]) rotate([-90, 0, 0]) difference() {
            translate([0, -2, 0]) cube([2, 2, beam[0][0] - fascia_y[1] + 2]); translate([0, 0, -1]) cylinder(r = 1, h = beam[0][0] - fascia_y[1] + 4, $fn = 24); }
        for (m = [0, 1]) mirror([m, 0, 0]) translate([bin_x, 0, 0]) bin_seat_cut_here(shelf_z + shelf_t, shelf_t);
        // liners' grooves in the floor
        for (f = [-1, 1]) translate([-pk_x - 0.01, f > 0 ? pk_y + 0.1 - 0.3 : -pk_y - 2.1 - 0.3, L - 1.5]) cube([2 * pk_x + 0.02, 2.6, 1.51]);
    }
}
// the same seat as the base's (frame.scad), drawn here so this file stands alone
runner = [3, 2];  runner_x = 22;  bin_mag = [14, 30];
module bin_seat_here(zt) for (s = [-1, 1]) translate([s * runner_x - runner[0] / 2, front_y + 8, zt - 0.01]) ccube([runner[0], bin_back - front_y - 10, runner[1]], 0.3);
module bin_seat_cut_here(zt, below) {
    translate([bin_mag[0], bin_mag[1], zt - mag_pocket_h]) magnet_cut();
    translate([-bin_mag[0] - 2.4, bin_mag[1] - 1.8, zt - below + 1]) cube([4.8, 3.6, below - 2]);
}

// ================================ SHAFT ======================================================
// Front column: a panel flush with the machine's face between bins 1 and 2, and the shaft's front
// liner behind it, joined by two ribs; it stands in level 2's floor groove and its top tab clicks
// under level 1's front hinge bar. The back liner is a plain plate the same way. Both stop 52 mm
// under level 1 so the open doors hang clear, and flare at the top into a funnel.
liner_z = [lv2_z - 1.5, lv1_z - hinge_y - 6];
module liner(f) {
    y0 = f > 0 ? pk_y + 0.1 : -pk_y - 2.1;
    difference() {
        union() {
            // the back liner clears level 2's paddles (they run back to the crossbar): two legs only
            z0 = f > 0 ? lv2_z + paddle_h + 1 : liner_z[0];
            translate([-pk_x, y0, z0]) cube([2 * pk_x, 2, liner_z[1] - z0]);
            if (f > 0) for (m = [0, 1]) mirror([m, 0, 0]) translate([pk_x - 3.4, y0, liner_z[0]]) cube([3.4, 2, z0 - liner_z[0] + 0.01]);
            hull() {
                translate([-pk_x, y0, liner_z[1] - 12]) cube([2 * pk_x, 2, 0.01]);
                translate([-pk_x, y0 + f * 4, liner_z[1]]) cube([2 * pk_x, 2, 0.01]);
            }
        }
        // the funnel's face
        hull() {
            translate([-pk_x - 1, f > 0 ? y0 - 1 : y0 + 2, liner_z[1] - 12]) cube([2 * pk_x + 2, 0.01, 0.01]);
            translate([-pk_x - 1, f > 0 ? y0 + 4 - 1 : y0 - 4 + 2, liner_z[1] + 0.01]) cube([2 * pk_x + 2, 0.01, 0.01]);
            translate([-pk_x - 1, f > 0 ? y0 - 10 : y0 + 12, liner_z[1] + 0.01]) cube([2 * pk_x + 2, 0.01, 0.01]);
            translate([-pk_x - 1, f > 0 ? y0 - 10 : y0 + 12, liner_z[1] - 12]) cube([2 * pk_x + 2, 0.01, 0.01]);
        }
    }
}
module col_front() {
    liner(-1);
    translate([-26 + reveal / 2 + 0.3, fascia_y[0], bin1_z + reveal]) ccube([52 - reveal - 0.6, fascia_y[1] - fascia_y[0], bin1_z + bin_h - bin1_z - reveal]);
    for (m = [0, 1]) mirror([m, 0, 0]) translate([22, fascia_y[1] - 0.01, bin1_z + 10]) cube([3, -pk_y - 2.1 - fascia_y[1] + 0.02, liner_z[1] - bin1_z - 10]);
}
module liner_back() liner(1);

// ================================ ASSEMBLY ===================================================
module servos_at() {
    color("#3060c0") {
        translate([sv_door_x, -hinge_y, lv1_z + hinge_z]) mirror([1, 0, 0]) servo_x([0, 0, 1]);
        translate([sv_door_x, hinge_y, lv1_z + hinge_z]) mirror([1, 0, 0]) mirror([0, 0, 1]) servo_x([0, 0, 1]);
        for (L = [lv1_z, lv2_z]) translate([0, psv_face + sv_top, L + psv_dz]) rotate([0, 0, 90]) servo_x([0, 0, 1]);
    }
}
module levels_assembly(p = push, d = doors) {
    color("#2b2b2b") { lv1_frame(); lv2_frame(); }
    color("#f2f2f2") { door_at(lv1_z, false, d); door_at(lv1_z, true, d); }
    color("#e8772e") { carriage_at(lv1_z, 1, p); carriage_at(lv2_z, 2, p); }
    color("#e8772e") for (L = [lv1_z, lv2_z]) lever_at(L, p);
    color("#888") for (L = [lv1_z, lv2_z]) lever_pin_at(L, p);
    color("#2b2b2b") { col_front(); liner_back(); }
    servos_at();
}

if (part == "levels") levels_assembly();
if (part == "lv1_frame") lv1_frame();
if (part == "lv2_frame") lv2_frame();
if (part == "door") door();
if (part == "carriage1") carriage(1);
if (part == "carriage2") carriage(2);
if (part == "lever") lever();
if (part == "col_front") col_front();
if (part == "liner_back") liner_back();
