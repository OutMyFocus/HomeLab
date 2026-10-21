# Scan station (phase 2 hardware)

A stand that holds the camera 120 mm above a white card pocket, with LED light from
both sides. Every card lands in the same spot under the same light, which makes
recognition much more reliable than holding cards under a webcam.

```
      camera ─►  ▄▄▄▄▄▄▄▄▄▄▄▄▄█
                              █  post
                              █
   light wall  ▌              █   ▐  light wall
               ▌   [ card ]   █   ▐
              ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀  base
```

The LEDs are on the side walls on purpose. A light next to the camera would bounce off
glossy and foil cards straight into the lens as a white glare spot.

## Files

| File | What |
|---|---|
| `stl/scan_station_base.stl` | Base with card pocket and light walls. **Print in white.** |
| `stl/scan_station_post.stl` | The post |
| `stl/scan_station_head.stl` | Arm and camera plate |
| `scan_station.scad` | The design. Change any size here and export new STLs. |

## Printing (Bambu Lab A1, PLA)

Open the STL files in Bambu Studio and use the default **0.20 mm Standard** profile with
**Generic PLA** or Bambu PLA. No supports needed.

| Part | Lay it | Infill | Time (rough) |
|---|---|---|---|
| Base | flat, as it opens | 15% | 3–4 h |
| Post | **on its side** (stronger that way) | 20% | 1 h |
| Head | flat, as it opens (socket pointing up) | 20% | 1 h |

**Print the base in white or a light colour.** It's the background the camera sees.
Most cards have black borders, so a white background makes them easy to find. If you
only have dark filament, glue a piece of white paper into the pocket.

## Other parts

| Part | Notes |
|---|---|
| Raspberry Pi Camera Module 3 | The standard one, not the "Wide" version |
| **Raspberry Pi 5 camera cable, 300 mm** | The Pi 5 uses a smaller connector than the cable the camera comes with |
| 4× M2 × 6 mm self-tapping screws | Hold the camera board on the head |
| 5 V USB LED strip, white, 8–10 mm wide | Cut two pieces about 10 cm long. "Natural" or "cool" white, not warm yellow |
| 4× small rubber feet, 8 mm (optional) | Stop it sliding. There are recesses for them under the base |

## Putting it together

1. Push the post into the base. It should be a snug fit. If it's too tight, sand it lightly,
   or change `fit` in `scan_station.scad` from 0.3 to 0.4 and reprint the post.
2. Screw the camera onto the head's standoffs, **lens pointing down** through the window.
3. Run the camera cable up through the groove on the back of the post, then push the head
   onto the post.
4. Stick an LED strip into the groove on the inside of each light wall. Run the wire through
   the channel under the base to join them.
5. Put a card in the pocket and run `python scan.py --camera 0`.

## Changing the design

Every size is a named number at the top of `scan_station.scad`, for example `cam_height`,
`card_gap` (raise it to 3 for sleeved cards) and `fit`. Install
[OpenSCAD](https://openscad.org) (free), open the file, change the number, press **F6**,
then **F7** to save a new STL. Or from a terminal:

```bash
openscad -D 'part="base"' -o stl/scan_station_base.stl scan_station.scad
```
