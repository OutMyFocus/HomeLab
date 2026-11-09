// Sorter Mk2: the one set of numbers every Mk2 part is placed from.
//
// Machine coordinates: x across (0 = centre, + = right as seen from the front), y front to back
// (0 = the middle of the card pockets, - = towards the front), z up (0 = the table).
// The datum is the frame: the inner faces of the two side walls (x = +-wall_in) and the top of
// the base (z = base_top). Every module is located by a dovetail rail in the walls, so nothing
// is ever placed by eye or by a screw hole.
//
// Card path (a stacked push sorter, checked in sim/drops.py and sim/push.py):
//   magazine and feeder (top back) -> scan bed (30 degree slope, camera above) -> stop bar at the
//   bed's front edge -> the card drops onto LEVEL 1's floor (two trapdoors) ->
//     bin 1 / bin 2: level 1's pusher moves it sideways, slowly, off the floor into the bin
//                    beside it (left / right);
//     bin 3 / bin 4: level 1's trapdoors open, the card falls flat down the shaft between bins 1
//                    and 2 onto level 2's floor, and level 2's pusher moves it left / right.
// All four bins are the same part. Bins 1 and 2 stand on level 2's shelves, bins 3 and 4 on the base.

// ---- cards ---------------------------------------------------------------------------------
card_w = 63;  card_l = 88;  card_t = 0.31;

// ---- card pockets (the same on both levels) --------------------------------------------------
pk_x = 33.5;           // floor half-width: the card (31.5) is pushed off this edge into the bin
pk_y = 45.5;           // pocket half-length (front wall and shaft liners' inner faces)
paddle_in = 34.0;      // the pushers' paddles at rest: inner faces at x = +-34 (they guide the card too)
paddle_t = 2.5;
paddle_h = 6;          // paddles stand 6 over the floor; two fingers each reach 0.8 below it, in grooves
paddle_y = 41;         // paddles run y = -41 .. 41 (the card is -44 .. 44)
finger_y = 30;         // fingers (and the floor grooves) at y = +-30
push_stroke = 71;      // the card's trailing edge ends at x = 37, past the bin's inner wall (36.5)
push_speed = 120;      // mm/s: the firmware moves a pusher at 100 .. 150 (sim: slower tips the card, faster throws it)

// ---- bins (four identical) ---------------------------------------------------------------------
bin_in   = [65, 91];   // inside, x by y (card 63 x 88)
bin_wall = 2;
bin_out_x = bin_in[0] + 2 * bin_wall;   // 69
bin_x    = pk_x + 1 + bin_out_x / 2;    // 69: bin centres at x = +-69 (inner wall 34.5 .. 36.5)
bin_y0   = -bin_in[1] / 2;              // -45.5 inside front ...
bin_y1   = bin_in[1] / 2;               // ... 45.5 inside back
bin_back = bin_y1 + bin_wall;           // 47.5
bin_floor = 3;
bin_depth = 150;                        // inside: about 400 cards
bin_h    = bin_floor + bin_depth;       // 153 outside

// ---- frame ----------------------------------------------------------------------------------
wall_in  = 112;        // inner faces of the side walls (a pusher's far paddle reaches 108.5)
wall_t   = 10;
wall_skin = 3;
wall_out = wall_in + wall_t;   // 122: the machine is 244 wide
front_y  = -66;        // front face of walls, bins and fascias (all flush)
back_y   = 242;        // outside face of the back panels
back_t   = 6;
back_in  = back_y - back_t;    // 236
base_t   = 6;
base_top = base_t;
wall_z0  = 3;          // the walls stand in a 3 mm rebate along the base's outer edges
base_seam_y = 88;

// ---- the stack ------------------------------------------------------------------------------
bin3_z   = base_top;                    // bins 3 and 4 stand on the base ...
lv2_z    = bin3_z + bin_h + 3;          // 162: level 2's floor, 3 above their tops
shelf_t  = 5;
shelf_z  = lv2_z + 8;                   // 170 .. 175: level 2's shelves, over its paddles (to +6)
bin1_z   = shelf_z + shelf_t;           // 175: bins 1 and 2 stand here ...
lv1_gap  = 17;                          // bins 1 and 2 stand 17 below level 1's floor (room for the door servos; sim: flat)
lv1_z    = bin1_z + bin_h + lv1_gap;    // 345: level 1's floor
front_h  = 30;                          // level 1's front wall (the card from the bed hits it)

// ---- scan bed -------------------------------------------------------------------------------
bed_a    = 30;                 // slope
bed_len  = 100;                // along the slope
bed_drop = 44;                 // bed front edge over level 1's floor (sim: lands flat 24 / 24)
bed_e    = [50, lv1_z + bed_drop];   // front edge of the card surface (y, z)
function bedpt(s, n = 0) = [bed_e[0] + s * cos(bed_a) - n * sin(bed_a), bed_e[1] + s * sin(bed_a) + n * cos(bed_a)];
card_s   = 2 + card_l / 2;     // card centre, measured up the slope from the front edge
cam_dist = 120;                // lens above the card centre, square to the bed

// ---- top ------------------------------------------------------------------------------------
top_z    = 580;                // top of the walls; the lid sits flush between them (camera 516, magazine to the top)
seam_y   = 88;                 // side walls are 2 x 3 tiles
seam_z   = [150, 330];         // tile rows: 3..150, 150..330, 330..580 (each under the A1's 256, none on a rail)

// ---- module rails (dovetail slots in the walls' inner faces, running along y) ----------------
// [z of the slot centre, y from, y to]
rail_lv2  = [lv2_z + 6, front_y, 56];          // level 2 (and its shelves), from the front
rail_lv1  = [lv1_z + 14, front_y, 56];         // level 1, from the front
rail_scan = [bed_e[1] + 2, front_y, 160];      // scan carrier and camera arch, from the front (over level 1's webs)
rail_feed = [bedpt(bed_len)[1] - 12, 152, back_in];  // feeder cartridge, from the back (under its magazine)
rails = [rail_lv2, rail_lv1, rail_scan, rail_feed];

// ---- the back: pusher drives and electronics -------------------------------------------------
xbar_y  = [66, 72];            // the pushers' carriages (crossbars) run along x here, behind everything
lever_y = [73, 75.5];          // the drive levers (scotch yoke) turn in this plane
psv_face = 76;                 // pusher servos' top faces (their tabs at +6.6, bodies to 99.4)
psv_dz  = -50;                 // pusher servo shafts sit 50 below their level's floor (lever points up)
lever_r = 72.1;                // 71 / sin(80): +-80 degrees of servo is the full stroke
etray_y0 = 104;                // the electronics tray, behind the pusher servos
etray_y1 = back_y;
etray_h  = 76;
etray_z1 = base_top + etray_h; // 82
fcover_z = lv1_z + front_h + 4;   // 379: the front cover (over the scan module) starts here
pwr_btn = [88, 21];            // the power button in level 1's fascia: x, z over level 1's floor
chan_y  = 76;                  // the walls' vertical cable trunks
back_up_z = etray_z1 + 4;      // the upper back panel starts here
