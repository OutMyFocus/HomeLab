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
**Print plate**. The Card Catalog drawers aren't in it; they come from their own file (see the end).

If Bambu Studio asks whether to load the project's settings, say **yes**. The process then reads
"0.20mm Standard @BBL A1" with a few values changed; that's correct.

`bambu/presets/` has the same settings as four process presets, for **File → Import →
Import Configs** (the "Select profile to load" window): flat panels, structural, tall parts
with brim, and solid. You only need them if you build plates yourself from the STLs.

### Power jack and button holes (2026-10-28)

`back_l` and `deck_fr` gained the holes for the one-plug, one-button power setup
([`POWER.md`](POWER.md)). Your copy of `MTG_Sorter_Enclosure.3mf` has your own changes in it,
so it wasn't regenerated: print those two parts from **`bambu/MTG_Sorter_Power_Parts.3mf`**
instead (File → Open Project, two plates, same settings). Already printed them? Drill the holes
instead: POWER.md, step 2, has the positions.

## Building a plate yourself from the STLs

`stl/` holds only what gets printed: the 26 `enc_*.stl` (the box), the two
`bed_chute_bed_side_*_enclosure.stl` walls, `feeder_stand_mid.stl`, the mechanism from Part 2
(`bed_chute_bed_plate`, `chute`, `trapdoor` + `trapdoor_left`, `trapdoor_mount` +
`trapdoor_mount_left`, `hinge_lug` + `hinge_lug_left`, `pin_rocker`, `tilt_bracket`,
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
| - | one Card Catalog drawer + one drawer top, from the Card Catalog 3MF | black | 4 h | **fit check B**, print it after plate 1 |
| 2 | 2 × `divider` | black | 110 g, 6 h | **fit check C** |
| 3 | `bridge_front` | black | 35 g, 2 h | the mechanism moves onto the bridge from here |
| 4 | `bridge_back` | black | 70 g, 3.5 h | |
| 5 | `bed_chute_bed_side_left_enclosure` + `..._right_enclosure` | black | 100 g, 5 h | the walls with screw holes in their bottom edge |
| 6 | `feeder_stand_mid` | black | 90 g, 4.5 h | the 92 mm stand |
| 7 | `floor_fr` + 8 × `splice` | black | 100 g, 5 h | |
| 8 | `floor_bl` + `floor_br` | black | 75 g, 4 h | |
| 9 | `post_front` + `post_back` + `leg` | black | 60 g, 4 h | brims on all three |
| 10 | `post_back` + `leg` + `tower` | black | 90 g, 5 h | brims on all three |
| 11–14 | `side`, one per plate (4) | black | 75 g, 3.5 h each | |
| 15 | `back_l` | black | 55 g, 2.5 h | has the 11 mm power-jack hole: print it from `MTG_Sorter_Power_Parts.3mf` (below) |
| 16 | `back_r` | black | 55 g, 2.5 h | |
| 17 | `fascia_l` + `fascia_m` + `fascia_r` | black | 50 g, 2.5 h | |
| 18 | `light_bar` | **white** | 4 g, 10 min | |
| 19 | `tower_lid` + `post_sleeve` + `head_cover` | black | 80 g, 4 h | brim on the sleeve |
| 20 | `deck_fl` | black | 70 g, 3.5 h | the deck last: it goes on once the mechanism is in |
| 21 | `deck_fr` | black | 70 g, 3.5 h | has the 16 mm power-button hole: print it from `MTG_Sorter_Power_Parts.3mf` (below) |
| 22 | `deck_bl` | black | 50 g, 2.5 h | |
| 23 | `deck_br` | black | 50 g, 2.5 h | |
| - | two more Card Catalog drawers + tops | black | 8 h | from the Card Catalog 3MF |

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
- Clip the top bar onto the plate and measure from the floor tile's top surface to the
  top of the bar. **Tell me that number.** The fascia starts 114 mm up; the box the drawer
  comes from allows 113.5. If the bar is taller than that, `dr_cap` changes and the fascia
  and posts are re-exported before you print them.

After plate 2:

- Stand a `divider` in the groove down the middle curb, flange facing out. It should drop
  in and stand on its own; the flange ends up at the height of the bridge's underside.

If all of that fits, print the rest. If something binds, post what binds and where, and
I'll adjust the numbers before you print another plate.

## The drawers

Open `Card_Catalog_v1.2_All-in-one.3mf` in Bambu Studio. It carries its own plates and
settings (the drawer prints standing, front plate vertical); use them as they are and
print only the **drawer** and **drawer top** objects, three of each. The box, dividers
and connectors are for your shelf, not the sorter. The sorter's dock is measured from
this exact file, so a drawer that fits your shelf fits the sorter.
