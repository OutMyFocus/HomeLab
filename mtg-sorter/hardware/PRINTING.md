# Printing the enclosure

Print order and slicer settings for the enclosure parts in
[`README.md`, Enclosure](README.md#enclosure), on the Bambu Lab A1 in Bambu Studio.
23 plates plus the three drawers, roughly 1.6 kg of PLA (nearly all black) and 60-odd hours
of printing. Plate 1, one drawer and plate 2 are a fit check: print those, try the fits, and
only then commit the rest of the filament.

## The easy way: one project file

Open **`bambu/MTG_Sorter_Enclosure.3mf`** with **File → Open Project** in Bambu Studio. It has
all 23 plates of the enclosure laid out, each on its own plate tab, named after what's on it,
and every setting below already applied (the per-part ones too). Pick a plate, check the
filament is your black PLA (white for the light bar), and press **Slice plate**, then
**Print plate**. The bins aren't in it; they're in `bambu/MTG_Sorter_Bins_And_Organizer.3mf` (see the end).

If Bambu Studio asks whether to load the project's settings, say **yes**. The process then reads
"0.20mm Standard @BBL A1" with a few values changed; that's correct.

`bambu/presets/` has the same settings as four process presets, for **File → Import →
Import Configs** (the "Select profile to load" window): flat panels, structural, tall parts
with brim, and solid. You only need them if you build plates yourself from the STLs.

## Building a plate yourself from the STLs

`stl/` holds only what gets printed: the 27 `enc_*.stl` (the box), the two
`bed_chute_bed_side_*_enclosure.stl` walls, `feeder_stand_mid.stl`, the mechanism from Part 2
(`bed_chute_bed_plate`, `chute`, `trapdoor` + `trapdoor_left`, `door_carrier` +
`door_carrier_left`, `pin_rocker`, `tilt_bracket`,
`tower_post`, `camera_head`) and the feeder's `hopper`, `gate` and `roller`.

Use **File → New Project**, then **File → Import → Import 3MF/STL/STEP**, pick only the files
for one plate, and when it asks "Load these files as a single object with multiple parts?"
answer **No**. Answering Yes merges them into one giant object (the 472 mm error). Then pick
the matching preset from `bambu/presets/` for each part, or right-click a part to change its
settings.

## Settings

Start every plate from **0.20 mm Standard @BBL A1** with a **PLA** filament profile
(Bambu PLA Basic, or Generic PLA for the Elegoo rolls), on the **textured PEI plate**.
Every flat part opens with its visible face down, so the plate's texture becomes the
finish. Then:

| Setting | Value | Why |
|---|---|---|
| Supports | **off**, on every part | nothing needs them |
| Wall loops | 3 for panels and tiles; **4** for posts, legs, dividers, bridge, tower, sleeve | the thick parts take screws and carry weight |
| Sparse infill | 15 % gyroid for flat parts; **25 %** for posts, legs, dividers, bridge; **100 %** for `light_bar` and `splice` | |
| Top / bottom shell layers | default (5 / 3) | |
| Brim | **5 mm outer brim** on the tall parts only: posts, legs, `post_sleeve`, `tower`; none elsewhere | 16 mm posts 206 mm tall need the help; the brim ends up under the deck |
| Seam position | Aligned (default) | lands in the panel grooves and the posts' inner corner |
| Precise wall | on | the pegs, grooves and pockets are sized with 0.4 mm clearance |
| Elephant foot compensation | 0.15 mm (the A1 profile has 0.075) | same reason: the pegs and grooves on the bottom face |
| Orientation | **as each file opens**, no rotation | the export already flips what needs flipping (posts, deck tiles, tower lid, head cover) |
| Ironing | off | the visible faces are the plate side |

Keep the plate clean (IPA) before the big floor and deck tiles: a 146 × 240 mm first
layer is the one thing on this list that can fail. If the Elegoo rolls have been open a
while and the parts string, dry them first.

## Colours

Black PLA for everything, except **white** for `light_bar` and the scan bed plate (the camera
looks at the bed, and the light bar is the white line across the front). The drawers can be
black too. If you get a dark grey roll later, the fascia, tower lid, post sleeve and head cover
look good in it, but black is fine.

## Plates, in order

The numbers are the plate tabs in `MTG_Sorter_Enclosure.3mf`. Weights and times are rough;
Bambu Studio's estimate is the real one.

| Plate | What's on it | Colour | About | Note |
|---|---|---|---|---|
| 1 | `floor_fl` + `post_front` + 2 × `splice` | black | 100 g, 5 h | **fit check A** |
| - | the bin trays and front plates, plates 1 and 2 of `MTG_Sorter_Bins_And_Organizer.3mf` | black | 17 h | **fit check B**, print them after plate 1 |
| 2 | 2 × `divider` | black | 110 g, 6 h | **fit check C** |
| 3 | `bridge_front` | black | 60 g, 4 h (estimate) | the mechanism moves onto the bridge from here. v3 since 2026-11-04 (bearing wall, drop-in tray); it's also on plate 2 of `MTG_Sorter_Chute_v3.3mf` with its cap ([CHUTE_V3.md](CHUTE_V3.md)) |
| 4 | `bridge_back` | black | 70 g, 3.5 h | |
| 5 | `bed_chute_bed_side_left_enclosure` + `..._right_enclosure` | black | 100 g, 5 h | the walls with screw holes in their bottom edge. Walls printed before 2026-10-30 have no bed-plate groove (only the LED groove): reprint them from the current STLs. The committed 3MF still has the old walls |
| 6 | `feeder_stand_mid` | black | 90 g, 4.5 h | the 96 mm stand, front cut away under the bed. Stands printed before 2026-10-30 (92 mm, square front) hit the bed plate: reprint |
| 7 | `floor_fr` + 8 × `splice` | black | 100 g, 5 h | |
| 8 | `floor_bl` + `floor_br` | black | 75 g, 4 h | |
| 9 | `post_front_r` + `post_back` + `leg` | black | 60 g, 4 h | brims on all three. `post_front_r` is the front-right post, the mirror image of plate 1's |
| 10 | `post_back` + `leg` + `tower` | black | 90 g, 5 h | brims on all three |
| 11–14 | `side`, one per plate (4) | black | 75 g, 3.5 h each | |
| 15 | `back_l` | black | 55 g, 2.5 h | |
| 16 | `back_r` | black | 55 g, 2.5 h | |
| 17 | `fascia_l` + `fascia_m` + `fascia_r` | black | 50 g, 2.5 h | |
| 18 | `light_bar` | **white** | 4 g, 10 min | |
| 19 | `tower_lid` + `post_sleeve` + `head_cover` | black | 80 g, 4 h | brim on the sleeve |
| 20 | `deck_fl` | black | 70 g, 3.5 h | the deck last: it goes on once the mechanism is in |
| 21 | `deck_fr` | black | 70 g, 3.5 h | |
| 22 | `deck_bl` | black | 50 g, 2.5 h | |
| 23 | `deck_br` | black | 50 g, 2.5 h | |

**Splices:** the build uses 24 of them (floor 6, bridge 2, front deck 2, fascia 4, back panel 4,
sides 6), more than the 10 on plates 1 and 7. Count the ones in your project and add more
`enc_splice` to any plate with room until you have 26 (two spare). They're 40 × 16 mm and take a
few minutes each.

The order is: fit checks, then the parts the mechanism moves onto (so the machine keeps
working on the bridge while the shell prints), then the shell from the floor up, trim,
deck. Swap plates 7–16 around freely; they don't depend on each other.

## The fit checks

After plate 1:

- Push `post_front` onto its two pegs at the front-left corner of `floor_fl`. It should
  go on by hand and stay put without wobbling. Too tight: a 4 mm drill through the holes.
  Loose: a drop of CA glue at assembly.
- Drop a `splice` into one of the pockets underneath. It should sit flush.

After the drawer (fit check B), still on `floor_fl`:

- Slide the tray into the **left** slot, between the outer curb and the first middle curb.
  It should slide with a little side play (1 mm in total) and not catch on the curbs.
- With the post on, slide the drawer all the way in: the plate's left edge passes the
  post's flat inner face with about a quarter millimetre to spare. If it rubs, say so;
  that's a one-number change in `enclosure.scad` (`dr_pitch`).
- Our bin has no top bar: its plate is 109 tall, so it stops 5 mm under the fascia (which
  starts 114 mm above the floor tile). (With a Card Catalog drawer instead, clip its top bar on and check it
  clears the fascia.)

After plate 2:

- Stand a `divider` in the groove down the middle curb, flange facing out. It should drop
  in and stand on its own; the flange ends up at the height of the bridge's underside.

If all of that fits, print the rest. If something binds, post what binds and where, and
I'll adjust the numbers before you print another plate.

## The bins

Our own bins (`bins.scad`), the same outside size as the Card Catalog drawer the dock was sized
from: open `bambu/MTG_Sorter_Bins_And_Organizer.3mf`. It also has card dividers, labels and the
organizer the full bins slide into. Everything about them is in [BINS.md](BINS.md). Card Catalog
drawers from `Card_Catalog_v1.2_All-in-one.3mf` still fit the dock if you'd rather print those.
