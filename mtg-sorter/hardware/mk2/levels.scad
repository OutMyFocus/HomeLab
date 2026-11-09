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
// the pocket the servo slides into (from +x, its tabs on a shoulder) and the box round it.
// One side wall of the box is slit into a spring finger with a lip that snaps over the back of the
// servo's body, so the servo can't back out. side = +1 or -1 picks which side wall.
sv_lip = 1.2;  sv_finger = [14, 6, 1.4];      // the finger: length, width, thickness
module servo_x_cut(dir, side = 1) {
    m = dir[2] == 1 ? [[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]] : [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];
    uc = sv_len / 2 - sv_shaft_off;  w0 = sv_w / 2 + 0.25;  a1 = sv_body + 2.5;  a0 = a1 - sv_finger[0];
    difference() {
        union() {
            servo_x(dir, 0.25);
            multmatrix(m) translate([0, -sv_shaft_off - (sv_tab_len - sv_len) / 2 - 0.25, -sv_w / 2 - 0.25]) cube([sv_body + 20, sv_tab_len + 0.5, sv_w + 0.5]);
        }
        // the lip (left standing in the pocket)
        multmatrix(m) scale([1, 1, side]) translate([0, uc + sv_finger[1] / 2, 0]) rotate([90, 0, 0]) linear_extrude(sv_finger[1])
            polygon([[sv_body + 0.3, w0 + 0.01], [sv_body + 0.3, w0 - sv_lip], [sv_body + 0.9, w0 - sv_lip], [a1 + 0.01, w0 + 0.01]]);
    }
    // the finger: a slit each side of it, and its outside thinned so it can spring
    multmatrix(m) scale([1, 1, side]) {
        for (u = [uc - sv_finger[1] / 2 - 0.8, uc + sv_finger[1] / 2]) translate([a0, u, w0 - 0.05]) cube([sv_finger[0] + 0.1, 0.8, 3]);
        translate([a0, uc - sv_finger[1] / 2 - 0.8, w0 + sv_finger[2]]) cube([sv_finger[0] + 0.1, sv_finger[1] + 1.6, 3]);
    }
}
module servo_x_box(dir, depth = sv_body + 2.5) {
    m = dir[2] == 1 ? [[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]] : [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];
    multmatrix(m) translate([-sv_top + 0.5, -sv_shaft_off - (sv_tab_len - sv_len) / 2 - 2.5, -sv_w / 2 - 2.5]) cube([sv_top - 0.5 + depth, sv_tab_len + 5, sv_w + 5]);
}

// ---- doors (level 1) --------------------------------------------------------------------------
hinge_y = 56.5;  hinge_z = -2.5;       // relative to the level's floor: far enough out that the door
                                       // servos' boxes stay clear of the card (|y| <= 45.5) and the bins
door_t = 2.5;  knuckle_r = 3;  knuckle_x = 33.2;  door_gap = 0.25;
sv_door_x = -knuckle_x - 0.3 - 3.5 - sv_top;   // the servo's tab face: its horn's hub sits between its top and the knuckle
// One door, drawn as the BACK door of a level at z = 0 (hinge at y = +hinge_y); the front door is
// the same part turned 180 degrees about z.
// The groove the paddles' fingers run in (the fingers reach 0.8 below the floor), with a 45 degree
// lead-in at each end (xe) so a finger that sags a little rides in instead of catching the edge.
finger_dz = 1.2;
module finger_groove(y, zt, xe) {
    translate([-pk_x - 1, y - 1.8, zt - finger_dz]) cube([2 * pk_x + 2, 3.6, finger_dz + 0.2]);
    for (m = [0, 1]) mirror([m, 0, 0]) translate([xe, y, zt - finger_dz]) rotate([0, 45, 0]) cube([1.414, 3.6, 1.414], center = true);
}
module door() {
    difference() {
        union() {
            translate([-knuckle_x, door_gap, -door_t]) cube([2 * knuckle_x, hinge_y - door_gap, door_t]);
            translate([-knuckle_x, hinge_y, hinge_z]) rotate([0, 90, 0]) cylinder(r = knuckle_r, h = 2 * knuckle_x);
            translate([-knuckle_x, hinge_y - knuckle_r, hinge_z]) cube([2 * knuckle_x, knuckle_r, -hinge_z]);
        }
        // fingers' grooves: 0.4 below the fingers, with a 45 degree lead-in where they come in
        finger_groove(finger_y, 0, knuckle_x);
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
xbar_z = [-46, 20];                    // crossbar, relative to the floor
neck_z = [paddle_h + 6, paddle_h + 14]; // level 1's necks run over the back rail and the back door's servo
xbar_half = paddle_in + paddle_t;      // 36.5
xbar_c = (xbar_y[0] + xbar_y[1]) / 2;
// The crossbar slides on the back beam. Three hooked lugs under it run in the beam's slot: the slot
// is undercut at the front only, so the beam keeps a solid lip on both sides. The lugs drop in
// through three gates in the front lip, with the carriage 50 mm right of centre. Everywhere else the
// lip is over them, and the slot's back wall holds them at every position.
lug_x = [-30, 0, 30];  lug_len = 10;  lug_h = 2;  gate_dx = 50;
guide_y = xbar_y[0] - 0.3;             // the frames' guide face, which the crossbar's front runs along
module lug_2d(g = 0) polygon([[-1.5 - g, 0.01], [1.5 + g, 0.01], [1.5 + g, -lug_h - g], [-1.5 - lug_h - 2 * g, -lug_h - g]]);
module along_x(len) rotate([90, 0, 90]) linear_extrude(len) children();
// the fork the lever's pin runs in: open at the top, so the lever drops in from above
fork_half = 9;  fork_top = 28;  fork_w = pin_free + 0.1;  fork_y0 = xbar_y[0] + 1.5;  fork_z0 = -40.5;
module fork_space() translate([-fork_w / 2, fork_y0, fork_z0]) cube([fork_w, xbar_y[1] - fork_y0 + 0.01, fork_top - fork_z0 + 1]);
module carriage(lv = 1) {
    ph = lv == 1 ? paddle_h : paddle_h - 1;     // level 2's paddles are 1 lower: the carriage goes in under the shelves, lifted over the beam
    nz = lv == 1 ? neck_z : [0.2, ph];
    difference() {
        union() {
            for (m = [0, 1]) mirror([m, 0, 0]) {
                // paddle: a bar beside the card, with two fingers
                // fully rounded profile, so the card only ever meets a smooth curve
                hull() for (z = [0.2 + paddle_t / 2, ph - paddle_t / 2]) for (y = [-paddle_y + paddle_t / 2, paddle_y - paddle_t / 2])
                    translate([paddle_in + paddle_t / 2, y, z]) sphere(d = paddle_t, $fn = 24);
                translate([paddle_in + paddle_t / 2, -paddle_y + paddle_t / 2, 0.2 + paddle_t / 2]) rotate([-90, 0, 0]) cylinder(d = paddle_t, h = 2 * paddle_y - paddle_t, $fn = 24);
                for (y = [-finger_y, finger_y]) hull() for (yy = [y - 0.6, y + 0.6]) for (z = [-0.8 + 0.6, 1.2])
                    translate([paddle_in + paddle_t / 2, yy, z]) rotate([0, 90, 0]) cylinder(d = 1.2, h = paddle_t, center = true, $fn = 16);
                // the neck back to the crossbar (level 1 climbs over the back rail and the door servo, level 2 stays low)
                if (lv == 1) hull() {
                    translate([paddle_in, paddle_y - 12, 0.2]) cube([paddle_t, 10, ph - 0.2]);
                    translate([paddle_in, paddle_y - 2, nz[0]]) cube([paddle_t, 4, nz[1] - nz[0]]);
                }
                nk = lv == 1 ? 0.01 : 3;     // level 2's neck starts inside the paddle, so the two are one piece
                translate([paddle_in, paddle_y - nk, nz[0]]) cube([paddle_t, xbar_y[0] - paddle_y + nk + 0.01, nz[1] - nz[0]]);
                // a gusset where the neck meets the crossbar
                translate([0, 0, nz[0]]) linear_extrude(nz[1] - nz[0]) polygon([[paddle_in + 0.01, xbar_y[0] - 10], [paddle_in + 0.01, xbar_y[0] + 0.01], [paddle_in - 10, xbar_y[0] + 0.01]]);
            }
            // the crossbar
            translate([-xbar_half, xbar_y[0], xbar_z[0]]) cube([2 * xbar_half, xbar_y[1] - xbar_y[0], xbar_z[1] - xbar_z[0]]);
            // the fork's tower: its front wall joins the two prongs so they can't spread
            translate([-fork_half, xbar_y[0], xbar_z[1] - 0.01]) cube([2 * fork_half, xbar_y[1] - xbar_y[0], fork_top - xbar_z[1] + 0.01]);
            // (kept low at its front edge: the stop bar, when down, comes to 22 over the floor there)
            hull() {
                translate([-fork_half, xbar_y[0] - 4, xbar_z[1] - 4]) cube([2 * fork_half, 4.01, 5]);
                translate([-fork_half, xbar_y[0] - 0.01, xbar_z[1] - 6]) cube([2 * fork_half, 0.02, 7]);   // (over level 2's shelves at 13)
            }
            // the hooked lugs under it
            for (x = lug_x) translate([x - lug_len / 2, xbar_c, xbar_z[0]]) along_x(lug_len) lug_2d();
        }
        fork_space();
    }
}
module carriage_at(L, lv, p = 0) translate([p * push_stroke, 0, L]) carriage(lv);

// the lever: servo horn pocket at its hub, a 3 mm steel pin at its tip
// It is 2.5 thick where it passes the servo's box and 7 thick beyond it, so the pin is pressed
// through 7 mm of plastic and can't work loose. Prints with its flat (carriage) face down.
lever_thick = 4.5;                     // how far the outer arm stands back past the servo's face
lever_r0 = 40;                         // the thick arm starts here, clear of the servo's box
lever_tip = 5.5;
module lever() {
    t = lever_y[1] - lever_y[0];
    difference() {
        union() {
            hull() {
                cylinder(r = 7, h = t);
                translate([0, lever_r, 0]) cylinder(r = lever_tip, h = t);
            }
            hull() for (r = [lever_r0, lever_r]) translate([0, r, -lever_thick]) cylinder(r = lever_tip, h = t + lever_thick);
            // a ramp up to the thick arm, so there is no sharp step to crack at
            hull() {
                translate([0, lever_r0 - 5, 0]) cylinder(r = lever_tip, h = t);
                translate([0, lever_r0, -lever_thick]) cylinder(r = lever_tip, h = t + lever_thick);
            }
        }
        translate([0, 0, -0.01]) linear_extrude(1.8) translate([-horn1_w / 2, 0]) square([horn1_w, horn1_len - 3]);
        translate([0, 0, -1]) cylinder(d = horn1_hub, h = 10);   // the horn's hub goes right through
        translate([0, lever_r, -lever_thick - 1]) cylinder(d = pin_press, h = 20, $fn = 32);
    }
}
function lever_a(p) = asin(max(-1, min(1, p * push_stroke / lever_r)));
module lever_at(L, p = 0) {
    translate([0, lever_y[1], L + psv_dz]) rotate([90, 0, 0]) rotate([0, 0, -lever_a(p)]) lever();
}
// the lever's pin (3 x 16, the same pins as the wall seams: pressed through the lever, its front
// 5 mm sliding in the carriage's fork, its back 4 mm standing out behind the lever, where nothing is)
pin_y = [lever_y[1] + lever_thick - 12, lever_y[1] + lever_thick + 4];     // 68 .. 84
module lever_pin_at(L, p = 0) {
    a = lever_a(p);
    translate([lever_r * sin(a), pin_y[0], L + psv_dz + lever_r * cos(a)]) rotate([-90, 0, 0]) cylinder(d = 3, h = pin_y[1] - pin_y[0], $fn = 32);
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
        // the carriage's lugs run in this slot, hooked under its front lip
        translate([-web_x, xbar_c, L + beam[1][1]]) along_x(2 * web_x) lug_2d(fit_dove);
        // gates: the lugs drop in here
        for (x = lug_x) translate([x + gate_dx - lug_len / 2 - 0.5, xbar_c - 1.5 - lug_h - 2 * fit_dove, L + beam[1][1] - lug_h - fit_dove])
            cube([lug_len + 1, 3 + lug_h + 3 * fit_dove, lug_h + 1]);
    }
    // the pusher servo's box, under the beam's back edge, shaft on x = 0 pointing -y
    // (it stands on a bracket that runs back from the beam, under the lever's hub)
    difference() {
        union() {
            translate([0, psv_face + sv_top, L + psv_dz]) rotate([0, 0, 90]) servo_x_box([0, 0, 1]);
            translate([-sv_w / 2 - 2.5, beam[0][0], L + beam[1][0] - 12]) cube([sv_w + 5, psv_face + sv_top + sv_body + 2.5 - beam[0][0], 10.01]);
        }
        translate([0, psv_face + sv_top, L + psv_dz]) rotate([0, 0, 90]) servo_x_cut([0, 0, 1]);
    }
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
                translate([knuckle_x + 0.3, y0, L + bar_z[0]]) cube([web_x - web_t - knuckle_x - 0.3 + 0.01, (f > 0 ? guide_y : bar_y[1]) - bar_y[0], bar_z[1] - bar_z[0]]);
            }
            // the pusher's guide rail: the crossbar's front face runs along it
            translate([-knuckle_x - 0.31, bar_y[1] + 1, L + bar_z[0]]) cube([2 * knuckle_x + 0.62, guide_y - bar_y[1] - 1, bar_z[1] - bar_z[0]]);
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
            // the front door servo's wire channel, along the left web over everything that moves,
            // from the fascia back past the beam (it prints standing up, so it needs no support)
            difference() {
                translate([-(web_x - web_t) - 0.01, fascia_y[1] - 0.01, L + 22]) cube([5.7, beam[0][1] - fascia_y[1] + 0.01, 8]);
                translate([-(web_x - web_t) - 0.02, fascia_y[1] + 3, L + 24]) cube([4.2 + 0.02, beam[0][1] - fascia_y[1], 8.01]);
            }
            // ... and forward under the bars, to carry the bin-full sensor holders
            for (m = [0, 1]) mirror([m, 0, 0]) translate([web_x - web_t - 12, irh_slot[0], L + beam[1][0]]) cube([12, bar_y[1] - irh_slot[0] + 0.01, bar_z[0] - beam[1][0] + 0.01]);
        }
        for (m = [0, 1]) mirror([m, 0, 0]) ir_holder_slot_cut(ir_z[0]);
        web_tongue_cuts(rail_lv1[0]);
        // servo pockets (they slide in from the outside, -x)
        translate([sv_door_x, -hinge_y, L + hinge_z]) mirror([1, 0, 0]) servo_x_cut([0, 0, 1]);
        translate([sv_door_x, hinge_y, L + hinge_z]) mirror([1, 0, 0]) mirror([0, 0, 1]) servo_x_cut([0, 0, 1], -1);
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
            translate([-pk_x, fascia_y[1] - 0.01, L - 3]) cube([2 * pk_x, guide_y - fascia_y[1] + 0.01, 3]);
            // shelves
            for (m = [0, 1]) mirror([m, 0, 0]) difference() {
                translate([bin_x - bin_out_x / 2, fascia_y[1] - 0.01, shelf_z]) cube([web_x - web_t - bin_x + bin_out_x / 2 + 0.02, guide_y - fascia_y[1] + 0.01, shelf_t]);
            }
            for (m = [0, 1]) mirror([m, 0, 0]) translate([bin_x, 0, 0]) bin_seat_here(shelf_z + shelf_t);
            // posts: shelves to floor at the front and back (outside the paddles' run, y beyond +-41)
            // the floor's back edge hangs a plate down to the back beam (behind the paddles' run)
            translate([-pk_x, beam[0][0] - 2, L + beam[1][1] - 0.01]) cube([2 * pk_x, guide_y - beam[0][0] + 2, -beam[1][1] - 3 + 0.02]);
            for (m = [0, 1]) mirror([m, 0, 0]) for (y = [[bin_fp_back + 0.25, -pk_y - 3]])
                translate([pk_x - 0.01, y[0] - 0.01, L - 3]) cube([bin_x - bin_out_x / 2 - pk_x + 0.02, y[1] - y[0] + 0.02, shelf_z + shelf_t - L + 3]);
            back_beam(L);
            for (m = [0, 1]) mirror([m, 0, 0]) translate([web_x - web_t - 12, bin_back + 6, L + beam[1][0]]) cube([12, beam[0][0] - bin_back - 6 + 0.01, -1 - beam[1][0]]);
        }
        web_tongue_cuts(rail_lv2[0]);
        for (m = [0, 1]) mirror([m, 0, 0]) ir_holder_slot_cut(ir_z[1]);
        for (f = [-1, 1]) finger_groove(f * finger_y, L, pk_x);
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
    // the hall sensor lies flat in a pocket open to the top (the bin covers it), its legs and wires
    // along a groove to behind the bin, where nothing moves (out of the cards' way under the shelf)
    translate([-bin_mag[0] - 2.4, bin_mag[1] - 1.8, zt - 3]) cube([4.8, 3.6, 3.01]);
    translate([-bin_mag[0] - 1.8, bin_mag[1], zt - 2.5]) cube([3.6, bin_back + 4 - bin_mag[1], 2.51]);
}

// ================================ BIN-FULL SENSOR HOLDER =====================================
// A TCRT5000 module (about 32 x 14 mm) slides into the holder's two edge rails from the inner end,
// its sensor looking forward (-y) through the window in the bin's back wall. The holder's dovetail
// tongue slides back into a groove in the frame's stiffener, two crush ribs hold it there, and the
// bin in front stops it coming forward. One part for all four bins (the left ones are the same part
// turned over). Drawn for the right side, z = 0 at the window's centre.
irh_x = [63.5, web_x - web_t - 12];    // inner end (clear of level 1's back door servo), stiffener face
irh_y = [54.5, 59.4];  irh_pcb = [56, 57.9];  irh_half = 9.5;  irh_lip = 6.3;  irh_grv = 7.5;
irh_slot = [53.5, 62.5];               // the groove in the stiffener, open at the front
ir_z = [bin1_z + bin_h - full_z, bin3_z + bin_h - full_z];   // bins 1, 2 and bins 3, 4
module ir_holder(ribs = true) {
    for (m = [0, 1]) mirror([0, 0, m]) difference() {
        translate([irh_x[0], irh_y[0], irh_lip]) cube([irh_x[1] - irh_x[0], irh_y[1] - irh_y[0], irh_half - irh_lip]);
        translate([irh_x[0] - 0.01, irh_pcb[0], irh_lip - 0.01]) cube([irh_x[1] - 2 - irh_x[0], irh_pcb[1] - irh_pcb[0], irh_grv - irh_lip + 0.01]);
        translate([irh_x[0] - 0.01, irh_pcb[0] - 0.5, irh_lip - 0.01]) rotate([0, 90, 0]) cylinder(r = 0.5, h = 3, $fn = 4);   // lead-in
    }
    // the end: behind the module only, so its pins and wires leave freely
    translate([irh_x[1] - 3, irh_pcb[1], -irh_half]) cube([3, irh_slot[1] - 0.3 - irh_pcb[1], 2 * irh_half]);
    translate([irh_x[1] - 3, irh_y[0], -irh_half]) cube([3, irh_y[1] - irh_y[0], irh_half - irh_lip]);
    translate([irh_x[1] - 3, irh_y[0], irh_lip]) cube([3, irh_y[1] - irh_y[0], irh_half - irh_lip]);
    translate([irh_x[1] - 0.01, irh_y[0], 0]) rotate([0, 90, 0]) {
        dove_rail(irh_slot[1] - 0.3 - irh_y[0]);
        if (ribs) for (z = [-1.5, 1.5]) translate([z - 0.3, 0, dove_h - 0.01]) cube([0.6, irh_slot[1] - 0.3 - irh_y[0], fit_dove + 0.16]);   // crush ribs
    }
}
module ir_holder_slot_cut(zc) translate([irh_x[1], irh_slot[0] - 0.01, zc]) rotate([0, 90, 0]) dove_slot_cut(irh_slot[1] - irh_slot[0]);
// where the four holders sit (the left ones turned over about y)
module ir_holders_at(ribs = true) for (z = ir_z) for (m = [0, 1]) translate([0, 0, z]) rotate([0, m * 180, 0]) ir_holder(ribs);

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
// d: each servo pulled d back out of its pocket (the way it slides in), for the latch checks
module servos_at(d = 0, which = "all") {
    color("#3060c0") {
        if (which == "all" || which == "doors") {
            translate([sv_door_x - d, -hinge_y, lv1_z + hinge_z]) mirror([1, 0, 0]) servo_x([0, 0, 1]);
            translate([sv_door_x - d, hinge_y, lv1_z + hinge_z]) mirror([1, 0, 0]) mirror([0, 0, 1]) servo_x([0, 0, 1]);
        }
        for (L = [lv1_z, lv2_z]) if (which == "all" || which == (L == lv1_z ? "push1" : "push2"))
            translate([0, psv_face + sv_top + d, L + psv_dz]) rotate([0, 0, 90]) servo_x([0, 0, 1]);
    }
}
module levels_assembly(p = push, d = doors) {
    color("#2b2b2b") { lv1_frame(); lv2_frame(); }
    color("#f2f2f2") { door_at(lv1_z, false, d); door_at(lv1_z, true, d); }
    color("#e8772e") { carriage_at(lv1_z, 1, p); carriage_at(lv2_z, 2, p); }
    color("#e8772e") for (L = [lv1_z, lv2_z]) lever_at(L, p);
    color("#888") for (L = [lv1_z, lv2_z]) lever_pin_at(L, p);
    color("#2b2b2b") { col_front(); liner_back(); ir_holders_at(); }
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
if (part == "ir_holder") ir_holder();
