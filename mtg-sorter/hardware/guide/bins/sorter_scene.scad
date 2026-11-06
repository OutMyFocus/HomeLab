// The bins in the sorter's dock, for render.py (each `what` is exported as an STL).
include <../../enclosure.scad>
use <../../bins.scad>
epart = "none";
what = "floor";
out = 0;
if (what == "floor") for (xi = [0, 1]) floor_tile(xi, 0);
if (what == "dividers") for (m = [0, 1]) mirror([m, 0, 0]) place_divider();
if (what == "posts") for (i = [0, 1]) place_post(i);
if (what == "fascia") for (i = [0 : 2]) translate([0, floor_y0 - pt, fascia_z0]) rotate([90, 0, 0]) fascia_tile(i);
if (what == "bridge") { bridge_front3(); bridge_cap3(); }
if (what == "chute") chute3_moving(0, 0);
if (what == "bin_l") translate([div_x[0], dock_y0, floor_t]) sorter_bin();
if (what == "bin_r") translate([div_x[2], dock_y0, floor_t]) sorter_bin();
if (what == "bin_m") translate([div_x[1], dock_y0 - out, floor_t]) sorter_bin();
