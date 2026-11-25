// Clash check for the bins in the sorter's dock (see BINS.md): renders whatever of the shell or
// the mechanism reaches into a bin. Empty = clear. Try show_tilt = 0 / 25 / -25 and
// show_doors_open = true / false; lift raises the bins (lift = 30 hits, to prove it works).
//   openscad --backend=manifold -o clash.stl -D show_tilt=25 -D show_doors_open=true clash_bins.scad
include <enclosure.scad>
lift = 0;
use <bins.scad>
epart = "none";
// anything of the shell or mechanism inside a bin (in the dock, lifted 0.05 off the floor)?
intersection() {
    union() { shell(); mechanism(); }
    for (i = [0 : 2]) translate([div_x[i], dock_y0, floor_t + 0.05 + lift]) sorter_bin();
}
