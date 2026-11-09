// Sorter Mk2: every clearance in one place.
//
// These are starting values for a Bambu A1, 0.4 mm nozzle, 0.2 mm layers, PLA Basic, with the
// elephant-foot compensation the Bambu projects use (0.15). Print coupon.scad first, try each
// joint by hand, and write the size that fits here. Every Mk2 part reads this file, so a new
// filament or printer means changing these numbers and re-exporting, nothing else.
//
// Each number is the gap per side unless it says otherwise.

fit_slide   = 0.30;   // parts that slide by hand: module rails, bin runners, lids in grooves
fit_snug    = 0.15;   // parts that go together once and stay: keys, pegs into sockets
fit_dove    = 0.20;   // dovetail flanks (coupon row B: pick the one that slides with a light push)
fit_turn    = 0.25;   // a printed journal turning in a printed bore

// 3 mm steel dowel pins (h6). Holes print about 0.1 mm small on the A1.
pin_d       = 3.0;
pin_press   = 3.00;   // hole drawn this size grips the pin (coupon row A: firm push, no hammer)
pin_free    = 3.30;   // hole drawn this size lets the pin turn freely

// 6 x 3 mm neodymium disc magnets
mag_d = 6;  mag_h = 3;
mag_pocket_d = 6.20;  // coupon row D: the magnet presses in and stays
mag_pocket_h = 3.20;

// Snap hooks (coupon row C). PLA bends about 2 % before it cracks; PETG about 4 %.
hook_t   = 1.6;       // arm thickness
hook_len = 10;        // arm length (at least 6 x hook_t)
hook_lip = 0.8;       // how far the hook catches (PLA 0.8, PETG 1.2)
hook_w   = 6;

// Board pegs: split pegs with a barb, through the boards' own holes.
peg_pi   = 2.50;      // Pi 5 holes are 2.7
peg_cam  = 2.00;      // Camera Module 3 holes are 2.2
peg_barb = 0.30;
pcb_t    = 1.6;
pcb_groove = pcb_t + 2 * 0.15;   // card-guide grooves for the small boards

// Flush panels
reveal   = 0.5;       // the even shadow line between two panels (it reads as flush)
chamfer  = 0.4;       // on every edge that touches the build plate

$fn = 48;
