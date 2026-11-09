// Sorter Mk2: every printed part, turned the way it prints (export.py writes stl/mk2_<part>.stl).
// The 3MF builder (bambu/make_mk2.py) only centres them on the plate and drops them to z = 0.
include <joints.scad>
include <layout.scad>
use <frame.scad>
use <levels.scad>
use <scan.scad>
use <feeder.scad>
use <etray.scad>
use <covers.scad>
part = "none";

// walls: the outside skin on the plate, the rails' slots open upwards
for (s = ["r", "l"]) for (iy = [0, 1]) for (iz = [0, 1, 2])
    if (part == str("wall_", s, iy, iz)) rotate([0, s == "r" ? 90 : -90, 0]) wall_tile(s, iy, iz);
base_names = ["fl", "fr", "bl", "br"];
for (i = [0 : 3]) if (part == str("base_", base_names[i])) base_tile(base_tiles_list(i));
function base_tiles_list(i) = [["fl", [-wall_out - 1, 0], [front_y - 1, base_seam_y]], ["fr", [0, wall_out + 1], [front_y - 1, base_seam_y]],
                               ["bl", [-wall_out - 1, 0], [base_seam_y, back_y + 1]], ["br", [0, wall_out + 1], [base_seam_y, back_y + 1]]][i];
if (part == "bin") bin();                                          // upright, open at the top
if (part == "trunk_lid") rotate([180, 0, 0]) trunk_lid("");         // outer face down
if (part == "branch_lid") rotate([180, 0, 0]) branch_lid();
if (part == "key") key();                                           // bowtie key for the wall and base seams (x28)

// sorting levels: the fascia (the machine's face) on the plate
if (part == "lv1_frame") rotate([90, 0, 0]) lv1_frame();
if (part == "lv2_frame") rotate([90, 0, 0]) lv2_frame();
if (part == "door") rotate([0, 90, 0]) door();                    // on its edge (brim)
if (part == "carriage1") carriage(1);
if (part == "carriage2") carriage(2);
if (part == "lever") lever();
if (part == "col_front") rotate([180, 0, 0]) col_front();         // standing on its end (brim)
if (part == "liner_back") rotate([90, 0, 0]) liner_back();

// scan module: the bed and the carrier lie flat (turned back by the bed's slope)
if (part == "scan_carrier") rotate([90 - bed_a, 0, 0]) carrier();  // standing on its back edge (tree supports)
if (part == "scan_bed") rotate([-bed_a, 0, 0]) bed();
if (part == "stop_bar") rotate([60, 0, 0]) stop_bar(0);           // the arms' outer faces on the plate
if (part == "cam_arch") rotate([180, 0, 0]) cam_arch();            // the beam on the plate
if (part == "cam_hood") rotate([180 - bed_a, 0, 0]) cam_hood();
if (part == "lightbar") rotate([90, 0, 0]) rotate([0, 90, 0]) rotate([-bed_a, 0, 0]) lightbar(1);   // on its end

// feeder cartridge (as feeder v4)
if (part == "fd_stand") stand();
if (part == "fd_hopper") hopper();
if (part == "fd_shoe") rotate([0, 90, 0]) rotate([-90, 0, 0]) shoe();   // on its long edge (brim)
if (part == "fd_roller") rotate([0, 90, 0]) roller();              // standing on its motor end
if (part == "fd_motor_lid") rotate([180, 0, 0]) motor_lid();

// electronics
if (part == "etray") etray();
if (part == "pca_comb") rotate([-90, 0, 0]) pca_comb();           // on its side: the hooks flex along the layers

// covers
if (part == "front_cover") rotate([-90, 0, 0]) front_cover();      // its face on the plate
if (part == "back_low") rotate([-90, 0, 0]) back_low();            // its outside skin on the plate
if (part == "back_high") rotate([-90, 0, 0]) back_high();
if (part == "lid_front") rotate([180, 0, 0]) lid_front();
if (part == "lid_back") lid_back();                                  // right way up: its half-lap step is on top
if (part == "drawer") drawer();
