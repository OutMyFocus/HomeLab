// Pieces for the bin / organizer pictures (render.py exports each `what` as an STL).
include <../../bins.scad>
part = "none";
what = "org22";
out = 0;          // how far bin_m is pulled out
if (what == "org22") translate([-pitch_x / 2, 0, 0]) organizer(2, 2);
if (what == "org12") translate([pitch_x, 0, 0]) organizer(1, 2);
if (what == "org22_alone") organizer(2, 2);
// bins in the cabinet: column i (0 left .. 2 right), row j
if (what == "bin_l") for (j = [0, 1]) translate([-pitch_x, -face_t - 0.5, floor_z(2, j) + 0.01]) sorter_bin();
if (what == "bin_r") for (j = [0, 1]) translate([pitch_x, -face_t - 0.5, floor_z(2, j) + 0.01]) sorter_bin();
if (what == "bin_m_top") translate([0, -face_t - 0.5, floor_z(2, 1) + 0.01]) sorter_bin();
if (what == "bin_m") translate([0, -face_t - 0.5 - out, floor_z(2, 0) + 0.01]) sorter_bin();
if (what == "cards") translate([0, -face_t - 0.5 - out, floor_z(2, 0) + 0.01]) for (k = [0 : 39]) translate([-card_w / 2, 70 + k * 1.6, floor_th]) cube([card_w, 0.6, card_l]);
if (what == "dividers") translate([0, -face_t - 0.5 - out, floor_z(2, 0) + 0.01]) for (k = [0, 1]) translate([0, groove_y[1 + 4 * k] + div_t / 2, floor_th]) rotate([90, 0, 0]) divider(k == 0 ? -1 : 1);
if (what == "bin") sorter_bin();
if (what == "keys") for (p = key_spots(2, 2)) if (p[0] > 80) translate([-pitch_x / 2 + p[0], org_d - key_t + 0.3, p[1]]) rotate([-90, 0, 0]) rotate(p[2]) key();
// the bin taken apart: tray, plate lifted off, toploader + card above its pocket
if (what == "tray") bin_tray();
if (what == "plate_off") translate([0, -40, plate_lift + 85]) bin_plate();
if (what == "toploader_off") translate([-38.1, -40 + lip_t + 0.25, plate_lift + 85 + 125]) cube([76.2, 1.5, 101.6]);
if (what == "card_off") translate([-card_w / 2, -40 + lip_t + 0.2, plate_lift + 85 + 125 + 3]) cube([card_w, 0.4, card_l]);
// a showcase card in place
if (what == "plate_on") translate([0, 0, plate_lift]) bin_plate();
if (what == "card_on") translate([-card_w / 2, lip_t + 0.5, plate_lift + show_z0 + 3]) cube([card_w, 0.4, card_l]);
if (what == "cards_shown") for (i = [0 : 2], j = [0 : 1]) if (!(i == 1 && j == 0))
    translate([(i - 1) * pitch_x - card_w / 2, -face_t - 0.5 + lip_t + 0.5, floor_z(2, j) + plate_lift + show_z0 + 3]) cube([card_w, 0.4, card_l]);
