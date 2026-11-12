// Sorter Mk2, one part (or one small set) at a time in machine coordinates, for the picture
// assembly guide (guide/build_guide.py): openscad -D 'a="..."' -o w/a_<name>.stl scene_atoms.scad
include <etray.scad>      // brings joints + layout, and the tray's board positions
use <frame.scad>
use <levels.scad>
use <scan.scad>
use <feeder.scad>
use <covers.scad>
part = "none";            // etray.scad draws nothing
a = "base_fl";

// as frame.scad / levels.scad (variables don't pass through `use`)
zrows = [[wall_z0, seam_z[0]], [seam_z[0], seam_z[1]], [seam_z[1], top_z]];
ycols = [[front_y, seam_y], [seam_y, back_y]];
chan_z = [etray_z1 - 20, top_z - 40];
lid_len = (chan_z[1] - chan_z[0]) / 3 - 0.5;
base_tiles = [["fl", [-wall_out - 1, 0], [front_y - 1, base_seam_y]], ["fr", [0, wall_out + 1], [front_y - 1, base_seam_y]],
              ["bl", [-wall_out - 1, 0], [base_seam_y, back_y + 1]], ["br", [0, wall_out + 1], [base_seam_y, back_y + 1]]];
module key_across_y() multmatrix([[0, 0, -1, 0], [1, 0, 0, 0], [0, -1, 0, 0], [0, 0, 0, 1]]) children();
module key_across_z() multmatrix([[0, 0, -1, 0], [0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 1]]) children();
module into_face_run_z() multmatrix([[0, 0, -1, 0], [-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]]) children();
module wall_keys() {      // the right wall's 9 keys, in their sockets on the inside face
    for (zz = zrows) translate([wall_in, seam_y, (zz[0] + zz[1]) / 2]) key_across_y() translate([0, 0, -key_t]) key();
    for (sz = seam_z) for (y = [front_y + 40, seam_y + 40, back_in - 40]) translate([wall_in, y, sz]) key_across_z() translate([0, 0, -key_t]) key();
}
module board(at, sz, h = 1.6) translate([at[0], at[1], base_top + et_floor + stand]) cube([sz[0], sz[1], h]);

for (t = base_tiles) if (a == str("base_", t[0])) base_tile(t);
if (a == "base_keys") {
    for (x = [-90, 90]) translate([x, base_seam_y, base_top - key_t]) rotate([0, 0, 90]) key();
    for (y = [front_y + 30, base_seam_y + 60, back_y - 30]) translate([0, y, base_top - key_t]) key();
}
for (iy = [0, 1]) for (iz = [0 : 2]) if (a == str("wall_r", iy, iz)) wall_tile("r", iy, iz);
if (a == "wall_keys") wall_keys();
if (a == "wall_r") wall_r();
if (a == "wall_l") wall_l();
if (a == "lv1_frame") lv1_frame();
if (a == "lv2_frame") lv2_frame();
if (a == "carriage1") carriage_at(lv1_z, 1, 0);
if (a == "carriage2") carriage_at(lv2_z, 2, 0);
if (a == "lever1") lever_at(lv1_z, 0);
if (a == "lever2") lever_at(lv2_z, 0);
if (a == "pin1") lever_pin_at(lv1_z, 0);
if (a == "pin2") lever_pin_at(lv2_z, 0);
if (a == "psv1") servos_at(0, "push1");
if (a == "psv2") servos_at(0, "push2");
if (a == "dsv") servos_at(0, "doors");
if (a == "doors") { door_at(lv1_z, false, 0); door_at(lv1_z, true, 0); }
if (a == "col_front") col_front();
if (a == "liner_back") liner_back();
if (a == "ir") ir_holders_at();
if (a == "carrier") carrier();
if (a == "bed") bed();
if (a == "lightbars") { lightbar(1); lightbar(-1); }
if (a == "stop_bar") stop_bar(0);
if (a == "stop_sv") stop_servo_placed();
if (a == "cam_arch") cam_arch();
if (a == "cam_hood") cam_hood();
if (a == "stand") stand();
if (a == "motor_lid") motor_lid();
if (a == "roller") roller();
if (a == "n20") n20();
if (a == "hopper") hopper();
if (a == "shoe") shoe();
if (a == "pads") pads();
if (a == "etray") etray();
if (a == "pi") board(pi_at, pi_sz);
if (a == "pca") board(pca_at, pca_sz);
if (a == "drv") board(drv_at, drv_sz, 4);
if (a == "relay") translate([relay_at[0], relay_at[1], base_top + et_floor + 1]) cube(relay_sz);
if (a == "wago") translate([wago_at[0], wago_at[1], base_top + et_floor + 1]) cube(wago_sz);
if (a == "lids") for (m = [0, 1]) mirror([m, 0, 0]) for (k = [0 : 2]) translate([wall_in, chan_y, chan_z[0] + k * (lid_len + 0.5)]) into_face_run_z() trunk_lid("");
if (a == "front_cover") front_cover();
if (a == "back_low") back_low();
if (a == "back_high") back_high();
if (a == "lid_front") lid_front();
if (a == "lid_back") lid_back();
if (a == "drawer") drawer();
for (i = [0 : 3]) if (a == str("bin", i)) bin_at(i);
