# Scan bed v3.1, the stop bar and the solid hopper weight

Print file: `bambu/MTG_Sorter_Scan_Bed_v3.3mf` (File > Open Project; answer **No** to "load as a single object").

| Plate | Part | Colour | Notes |
|---|---|---|---|
| 1 | `bed_plate3`, the scan bed (v3.1) | **white** | slippery-smooth settings set in the file (below), no supports, flat side down |
| 2 | `weight_solid`, the hopper weight | any | 100 % infill (set in the file), about 95 g |
| 3 | `stop_gate3`, one flat stop bar with a lip, instead of the four teeth | black | same screws, horn and bearing as the old stop gate. **Pins down goes from 155 to about 165** (below) |

Also needed: **1/4" (6 mm) PTFE (Teflon) tape**, about 40 cm (the self-adhesive kind sold for heat
sealers and 3D printer beds).

![bed v3.1 in the machine](img/bed3/bed3_in_machine.png)

## What changed, and why

Camera tests showed cards landing turned up to 15°, riding up on the old 2.5 mm rails, stopping
on the bed and not starting again, and sliding off slowly when the teeth dropped. The first v3
print (24°) still stopped cards: at the entrance, and anywhere on the slope.

- **The card's surface prints dead flat.** v3 tilted the surface 4° against the plate, so each print
  layer left a fine step across the slide direction (the camera shows them as lines), and its
  crest sat in front of the hopper floor's edge with a hollow under it, so a card coming off the
  floor met a face climbing towards it. v3.1's surface is parallel to the plate's underside: 20°
  like the walls, no steps, and from the floor's edge on it only goes down. It stands 2 mm higher
  than the old plate's face, so the card drops 5.4 mm off the floor instead of 8.
- **PTFE tape lands.** PLA is too grippy for a card to start sliding by itself at 20° (the 24° print
  proved more slope alone doesn't do it). Four lands, 6.5 mm wide and 0.8 mm tall, run down the slope
  and carry the card; a strip of 1/4" PTFE tape on each makes it slide. Without tape they are still
  smooth (ironed) and keep the card off the surface. They ramp in at the top so an edge can't catch.
  Truly more slope needs new side walls, stop gate, gate bearing and a deck piece.
- **A channel that centres the card.** 65 mm wide (card 63 + 1 mm each side) from the stop to the
  middle of the card, so the card sits square and in the middle, over the middle of the trapdoors,
  and leaves the bed that way. The walls are 4 mm tall and run right to the front edge. Above the
  card's middle they open out to 76 mm and get 6 mm tall, so a card coming out of the hopper crooked
  is caught and straightened. The inside top edge is chamfered: a corner that lands on a wall slides
  back in.
- **One stop bar instead of four teeth**, 51.6 mm wide, coming up through one chamfered opening, so the
  card's edge sits square and nothing pokes up between gaps. A wider bar would hit the tray's edge
  when it tilts with the stop down. On the printed v3, 1 card in 4 hopped the bar, so it is now 13.5 mm
  tall (10.7 mm above the lands; the old teeth stood 8) with a 1.5 mm lip along its top on the card's
  side, which catches a card that climbs the face. Being taller, it has to turn further to get out of
  the card's way: about 32° instead of 25°, so **Pins down about 165** instead of 155 (up stays 130).
- **Marker pockets for the camera.** Four 5 mm square pockets, 0.4 mm deep, beside the walls, for
  printed ArUco stickers (OpenCV DICT_4X4_50, ids 0-3), so the app can straighten the picture
  exactly. They are in the card's plane (0.8 mm under its face). Centres, in mm, measured along the
  surface from the front edge (u) and across from the middle (x, + = camera tower side, seen from the
  camera with the stop at the bottom): id 0 (-37.75, 10), id 1 (37.75, 10), id 2 (37.75, 50),
  id 3 (-37.75, 50), a 75.5 x 40 rectangle.

![plate](img/bed3/bed3_plate.png)
![card on the plate, seen from the camera](img/bed3/bed3_top_with_card.png)
![side section at x = 18: old bed grey, new white, hopper floor at the top](img/bed3/bed3_side_section.png)

## Fitting

1. Pins down (Machine page), then slide the old plate forward out of the wall grooves.
2. Swap the stop gate: unscrew the old one from the pin servo horn and the gate bearing, fit the
   stop bar the same way.
3. Put a strip of PTFE tape along each of the four lands, pressed down flat, with no wrinkles, and
   trimmed square at both ends.
4. Slide the new plate in from the front, lands up, the edge with the opening at the front, until
   its front edge lines up with the front of the side walls. Don't force it further: the top end
   only has 2.4 mm under the hopper floor.
5. On the Machine page set **Pins down to 165** (up stays 130) and Save. Pins up: the bar comes up
   through the opening. Pins down: on the camera, check that the bar's top goes fully below the
   lands. If it doesn't, try 168. (CAD says it clears from about 162; the tray is clear up to 170.)
6. On the Machine page, feed one card and check it lands at the stop. The camera stays where it was
   relative to the bed, so the saved landing zone should still work (the card is 2 mm closer).

Checked in CAD (OpenSCAD intersections, each with a positive control): the plate clears the hopper
floor by 2 to 3 mm and the feeder gate. The stop bar clears the plate from 6° past up to 44° down,
and the tray at 22° and 25° tilt either way and with the doors open, up to 40° down. A card can slide
out over it from 32° down. For scale: the old teeth cleared the card from 25°, which is your 155, so
servo angle is about 130 + the CAD angle.

## Slippery-smooth settings (already in the 3MF, plate 1)

| Setting | Value | Why |
|---|---|---|
| Top shell layers | 7 | a dense, flat top skin |
| Top surface line width | 0.40 mm | finer lines on top |
| Ironing | Top surfaces, flow 15 %, spacing 0.10 mm, speed 20 mm/s | the hot nozzle passes again over every top face and melts the lines flat |

The same settings as a preset you can import: `bambu/presets/MTG_Scan_Bed_Slippery_Smooth.json`
(Bambu Studio: File > Import > Import Configs, then pick "MTG Scan Bed - Slippery smooth @BBL A1" as
the process). You only need it when you slice the bed from the STL instead of the 3MF.

The PTFE tape is what makes it slippery; the print settings keep the lands flat under it. Don't use
spray, wax or lubricant: it rubs off onto the cards.

## Limits

- **Sleeved cards don't fit** the 65 mm channel (they are 66 to 67 mm). Set `bp3_half` in
  `bed_chute.scad` to 34.5 and re-export if you ever sort sleeved cards.
- A card held under the feeder gate is a gate problem, not a bed problem.
- The lands show up in the camera as stripes on the empty bed; the app should compare against the
  empty bed rather than look for an all-white one.

## The solid weight

![solid weight](img/bed3/weight_solid.png)

Same size as the coin weight (64 x 89 mm), 14 mm thick, flat and chamfered underneath, grip ridge on
top. It presses the stack down evenly so curled cards (foils) come out flat. Print it flat side down
at 100 % infill.

## Rebuilding

    openscad -o stl/bed_chute_bed_plate3.stl -D 'part="bed_plate3"' bed_chute.scad
    openscad -o stl/bed_chute_stop_gate3.stl -D 'part="stop_gate3"' bed_chute.scad
    openscad -o stl/feeder_weight_solid.stl -D 'part="weight_solid"' feeder.scad
    python3 bambu/make_small_projects.py MTG_Sorter_Scan_Bed_v3.3mf
    python3 guide/bed3/render.py     # the pictures (see the script for its needs)
