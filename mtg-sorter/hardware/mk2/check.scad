// Sorter Mk2 clash checks: each `what` must come out empty (check.py runs them all).
include <joints.scad>
include <layout.scad>
use <frame.scad>
use <etray.scad>
use <sort.scad>
what = "none";

module walls() { wall_r(); wall_l(); }
module bins() { for (b = [-1, 0, 1]) translate([b * bin_pitch, 0, 0]) bin(); }
module dividers() { divider(true); mirror([1, 0, 0]) divider(true); }
module fixed_low() { walls(); bins(); dividers(); base_full(); }
module tray_at(t, o) tray_moving(t, o);

// the tray, tipped either way or level with its doors open, against the frame and bins
if (what == "tray_level") intersection() { tray_at(0, 0); union() { fixed_low(); deck(); } }
if (what == "tray_right") intersection() { tray_at(tilt_max, 0); union() { fixed_low(); deck(); } }
if (what == "tray_left") intersection() { tray_at(-tilt_max, 0); union() { fixed_low(); deck(); } }
if (what == "doors_open") intersection() { tray_at(0, 1); union() { fixed_low(); deck(); } }
// the deck sits in the walls' rails without touching anything else
if (what == "deck_frame") intersection() { deck(); union() { bins(); dividers(); base_full(); } }
if (what == "deck_walls") intersection() { deck(); walls(); }
// the electronics tray
if (what == "etray_frame") intersection() { etray(); union() { walls(); bins(); dividers(); deck(); } }
if (what == "bins_frame") intersection() { bins(); union() { walls(); dividers(); base_full(); } }
