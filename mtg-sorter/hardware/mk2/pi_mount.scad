// Sorter Mk2 Pi wall mount: a block that pushes into one of the right wall's pockets, with the
// Pi 5 screwed onto four standoffs on its face. It sits in the upper-front pocket of the right
// wall's middle back tile (behind level 2, under level 1), so the camera ribbon reaches the arch.
//
// No screws or glue go into the wall. The block fills the triangle between the tile's front rim,
// its top rim and its diagonal brace: it drops onto the brace, which slopes it into the corner, and
// three crush ribs on each straight side hold it tight. The Pi hangs off its face, so its weight
// presses the block's top into the wall rather than pulling it out. Pull it straight out to remove.
//
// The Pi: four M2.5 screws, 6 to 10 mm long, through its corner holes into the standoffs (the
// holes are 2.2 mm, so the screws cut their own thread). The GPIO header is along the bottom, the
// USB and Ethernet face the back, USB-C power and the camera sockets face up.
include <joints.scad>
include <layout.scad>
part = "pi_mount";

pm_rim = 8;                         // frame.scad: rim round each tile
pm_y0 = seam_y + pm_rim;            // 96: the pocket's front face
pm_ztop = seam_z[1] - pm_rim;       // 322: the pocket's ceiling
pm_floor = wall_out - wall_skin;    // 119: the pocket's floor (the skin)
// the brace's upper face runs from (96, 166) to (226, 322) in y, z
function brace_z(y) = (seam_z[0] + pm_rim + 8) + (y - pm_y0) * 156 / 130;
function brace_y(z) = pm_y0 + (z - (seam_z[0] + pm_rim + 8)) * 130 / 156;

pm_c = fit_snug;                    // gap per side to the pocket
pm_zlow = 200;                      // the block's bottom (the pocket's narrow tip below is left empty)
pm_yback = 210;                     // ... and its back end
pm_face = 3;                        // how far the block stands out of the wall
pm_x0 = wall_in - pm_face;          // 109: its face
pm_x1 = pm_floor - 0.2;             // 118.8: its back, just short of the skin

// the Pi 5 (board 85 x 56, holes 58 x 49 at 3.5 from the corner), standing on the block's face
pm_pi = [100, 250];                 // y, z of the board's front-bottom corner
pm_holes = [[3.5, 3.5], [61.5, 3.5], [3.5, 52.5], [61.5, 52.5]];
pm_stand = 5;                       // board's back this far off the block
pm_screw = 2.2;                     // M2.5 self-tapping hole
pm_boss = 6.5;

module pm_outline() offset(delta = -pm_c) polygon([
    [pm_y0, pm_zlow], [brace_y(pm_zlow), pm_zlow], [pm_yback, brace_z(pm_yback)],
    [pm_yback, pm_ztop], [pm_y0, pm_ztop]]);

// (y, z) -> the wall's frame: the outline lies in the y-z plane, extruded along x
module pm_yz(x0, x1) translate([x0, 0, 0]) multmatrix([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]]) linear_extrude(x1 - x0) children();

module pi_mount(ribs = true) {
    difference() {
        union() {
            pm_yz(pm_x0, pm_x1) pm_outline();
            // crush ribs along the push-in direction, 0.2 mm tight: three on the front side, three on the top
            if (ribs) for (z = [215, 262, 309]) translate([pm_x0 + pm_face + 0.5, pm_y0 + pm_c + 0.25, z]) rotate([0, 90, 0]) cylinder(d = 1.2, h = pm_x1 - pm_x0 - pm_face - 1, $fn = 12);
            if (ribs) for (y = [112, 150, 190]) translate([pm_x0 + pm_face + 0.5, y, pm_ztop - pm_c - 0.25]) rotate([0, 90, 0]) cylinder(d = 1.2, h = pm_x1 - pm_x0 - pm_face - 1, $fn = 12);
            for (h = pm_holes) translate([pm_x0 + 0.01, pm_pi[0] + h[0], pm_pi[1] + h[1]]) rotate([0, -90, 0]) cylinder(d = pm_boss, h = pm_stand + 0.01);
        }
        for (h = pm_holes) translate([pm_x0 - pm_stand - 0.01, pm_pi[0] + h[0], pm_pi[1] + h[1]]) rotate([0, 90, 0]) cylinder(d = pm_screw, h = 12, $fn = 24);
        // the bowtie keys across the tile seams poke 1 mm into the pocket: room for them
        translate([wall_in - 0.01, seam_y, (seam_z[0] + seam_z[1]) / 2]) pm_yz(0, key_t + 0.5) offset(delta = 0.4) pm_key();
        for (y = [seam_y + 40, back_in - 40]) translate([wall_in - 0.01, y, seam_z[1]]) pm_yz(0, key_t + 0.5) offset(delta = 0.4) rotate(90) pm_key();
        // windows to save plastic, clear of the standoffs and the ribs
        pm_yz(pm_x0 - 1, pm_x1 + 1) {
            translate([108, 262]) square([48, 34]);
            polygon([[108, 214], [brace_y(214) - 9, 214], [brace_y(246) - 9, 246], [108, 246]]);
            polygon([[169, brace_z(178)], [200, brace_z(209)], [200, 310], [169, 310]]);
        }
        // the label on the face (reads from inside the machine)
        translate([pm_x0 + 0.6, 0, 0]) pm_yz(-1, 0) translate([150, 316]) mirror([1, 0]) text("Pi", size = 5, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
    }
}
module pm_key() polygon([[-key_l / 2, -key_w1 / 2], [0, -key_w0 / 2], [key_l / 2, -key_w1 / 2],
                         [key_l / 2, key_w1 / 2], [0, key_w0 / 2], [-key_l / 2, key_w1 / 2]]);

// how it prints: the back (the end that goes into the wall) on the plate, the standoffs up
module pi_mount_print() multmatrix([[0, -1, 0, 0], [0, 0, 1, 0], [-1, 0, 0, pm_x1], [0, 0, 0, 1]]) pi_mount();

// the Pi itself, for pictures and clash checks
module pi_on_mount() {
    translate([pm_x0 - pm_stand - pcb_t, pm_pi[0], pm_pi[1]]) cube([pcb_t, 85, 56]);
    translate([pm_x0 - pm_stand - pcb_t - 14.4, pm_pi[0] + 18, pm_pi[1] + 12]) cube([14.4, 40, 34]);   // the Active Cooler
    translate([pm_x0 - pm_stand - pcb_t - 8.5, pm_pi[0] + 7, pm_pi[1] + 1]) cube([8.5, 51, 5]);       // GPIO header
    translate([pm_x0 - pm_stand - pcb_t - 16, pm_pi[0] + 85 - 21, pm_pi[1] + 2]) cube([16, 23, 52]);   // USB and Ethernet, past the board's back edge
}

if (part == "pi_mount") pi_mount();
if (part == "pi_mount_print") pi_mount_print();
if (part == "pi") pi_on_mount();
