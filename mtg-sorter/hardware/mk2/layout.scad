// Sorter Mk2: the one set of numbers every Mk2 part is placed from.
//
// Machine coordinates: x across (0 = centre, + = right as seen from the front), y front to back
// (0 = the middle of the sort tray, - = towards the front), z up (0 = the table).
// The datum is the frame: the inner faces of the two side walls (x = +-wall_in) and the top of
// the base (z = base_top). Every module is located by a dovetail rail in the walls, so nothing
// is ever placed by eye or by a screw hole.
//
// Card path, back to front: hopper and feeder (top back) -> scan bed (30 degree slope, camera
// above) -> stop bar at the bed's front edge -> sort tray (tilts left / right, or opens its two
// trapdoors) -> three identical bins standing on the base.

// ---- cards ---------------------------------------------------------------------------------
card_w = 63;  card_l = 88;  card_t = 0.31;

// ---- frame ----------------------------------------------------------------------------------
wall_in  = 119;        // inner faces of the side walls, x = +-119
wall_t   = 10;         // rails and rim; the skin between ribs is wall_skin
wall_skin = 3;
wall_out = wall_in + wall_t;   // 129: the machine is 258 wide
front_y  = -66;        // front face of walls, dividers and bin fronts (all flush)
back_y   = 242;        // outside face of the back panels
back_t   = 6;
back_in  = back_y - back_t;    // 236
top_z    = 424;        // top of the walls; the lid sits flush between them
seam_y   = 88;         // side walls are 2 x 2 tiles: front/back seam ...
seam_z   = 228;        // ... and lower/upper seam, between the sort and scan rails (tiles 154 x 225 / 154 x 196)

base_t   = 6;
base_top = base_t;     // bins and dividers stand here
wall_z0  = 3;          // the walls stand in a 3 mm rebate along the base's outer edges
base_seam_y = 88;      // the base is two tiles too

// ---- bins -------------------------------------------------------------------------------------
bin_pitch = 82;                // bin centres at x = -82, 0, 82
bin_in    = [68, 94];          // inside, x by y (card 63 x 88)
bin_wall  = 2;
bin_out_x = bin_in[0] + 2 * bin_wall;   // 72
bin_y0    = -47;               // inside front (card side) ...
bin_y1    = bin_y0 + bin_in[1];         // ... and inside back, y = 47
bin_back  = bin_y1 + bin_wall;          // 49: back face of the bin
bin_floor = 3;
bin_top   = 186;               // open top
bin_depth = bin_top - base_top - bin_floor;   // 177 inside: about 475 cards
divider_t = 9.4;               // between bins (x = +-41): carries the break-beam sensors
divider_y1 = 56;               // dividers run front_y .. 56
beam_z    = bin_top - 15;      // the full-bin beam crosses each bin here

// ---- sort tray (chute v3's tray, raised; same card pocket) ------------------------------------
pivot_z   = 230;               // tilt axis (along y, x = 0) = top of the tray floor
tray_half = 60;                // tray reaches x = +-60
tray_in   = 45.5;              // inside y = +-45.5
tilt_max  = 25;

// ---- scan bed -------------------------------------------------------------------------------
bed_a    = 30;                 // slope
bed_len  = 100;                // along the slope
bed_e    = [50, 274];          // front edge of the card surface (y, z): 44 above the tray, so the tray can tip under it
function bedpt(s, n = 0) = [bed_e[0] + s * cos(bed_a) - n * sin(bed_a), bed_e[1] + s * sin(bed_a) + n * cos(bed_a)];
card_s   = 2 + card_l / 2;     // card centre, measured up the slope from the front edge
cam_dist = 120;                // lens above the card centre, square to the bed

// ---- module rails (dovetail slots in the walls' inner faces, running along y) ----------------
// [name, z of the slot centre, y from, y to]
rail_sort = [205, front_y, 96];
rail_scan = [262, front_y, 160];
rail_feed = [338, 90, back_in];
rails = [rail_sort, rail_scan, rail_feed];

// ---- electronics tray (slides out of the back, under the scan bed) ---------------------------
etray_y0 = divider_y1 + 2;     // 58
etray_y1 = back_y;             // its back plate is the lower back panel
etray_h  = 76;                 // tray floor to its top rail
etray_z1 = base_top + etray_h; // 82
back_up_z = etray_z1 + 4;      // the upper back panel starts here
sort_top_z = 250;              // the sort deck's fascia covers z 186.5 .. 249.5; the front cover starts here
