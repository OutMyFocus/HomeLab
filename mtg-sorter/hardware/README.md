# Hardware

- [Scan station](#scan-station): camera stand, print this first
- [Feeder test rig](#feeder-test-rig): the first piece of the full sifter
- [Scan bed and chute](#scan-bed-and-chute): the middle of the sifter: stops the card for its photo, then sorts it into a bin
- [Full sifter concept](#full-sifter-concept): where it's all heading

# Scan station

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

---

# Full sifter concept

Two pictures of the whole machine, in the style of TCGplayer's Roca Sifter: a countertop
box with a stack of cards at the back, a camera arm over a scan bay, and three pull-out
bins at the front. They're plans, not printable parts.

| File | Shows |
|---|---|
| `sifter_concept.scad` | The outside: what the finished machine will look like |
| `sifter_inside.scad` | The mechanism inside, as an open frame |

Card path, back to front:

1. **Hopper:** up to about 400 cards, face up.
2. **Pick roller:** pushes the bottom card out under the gate, one at a time.
3. **Scan bed:** sloped 20°, so the card slides down until a stop gate catches it.
   It always ends up in the same spot.
4. **Camera:** on a tower beside the bed (not in the card's way), square to the bed.
5. **Stop gate drops:** a servo flips it, and the card slides into the chute.
6. **Chute:** a servo tilts it left, centre or right into bin 1, 2 or 3.

Each piece gets designed and tested on its own, starting with the feeder, the hardest part.

# Feeder test rig

The hardest part of any card sorter is getting **exactly one** card out of the stack
every time. Two stuck together, or none at all, and the sort is wrong. So this gets
built and tested on its own first.

A roller with rubber O-rings sits under the stack and pokes 0.8 mm up through the floor.
When it turns, it drags the bottom card forward under the **gate**: a plate whose bottom
edge sits just over one card's thickness above the floor. One card fits under it, two don't.

| File | Print | Notes |
|---|---|---|
| `stl/feeder_stand.stl` | as it opens, 15% infill | The box underneath, with the motor cradle |
| `stl/feeder_hopper.stl` | as it opens, 15% infill | Floor and walls. Holds about 190 cards |
| `stl/feeder_gate.stl` | flat | The adjustable gate |
| `stl/feeder_roller.stl` | standing on its end, **100% infill** | Goes on the motor shaft |

### Parts to buy

| Part | Notes |
|---|---|
| N20 gear motor, 6 V, **100–200 RPM**, 3 mm D-shaft | Very common, a few dollars |
| 2× O-rings, **20 mm inside × 3 mm thick**, nitrile | They're the "tyre" on the roller. Hardware store or Amazon |
| 2× M3 × 10 mm self-tapping screws | Hold the gate |
| A couple of small zip ties | Strap the motor to its cradle |
| 4× AA battery holder with a switch | Enough to test. A Raspberry Pi controls it later |

### Putting it together

1. Stretch the two O-rings into the grooves on the roller.
2. Push the roller onto the motor shaft (the flat side of the hole matches the flat on the shaft).
3. Slide the motor in through the hole in the side of the stand, so the roller is in the middle
   under the floor opening. Strap it down with zip ties through the slots in the cradle.
4. Set the hopper on top of the stand. The small pegs line it up.
5. Screw the gate loosely onto the front of the hopper.

### Setting the gate

1. Slide one card under the gate and push the gate down onto it.
2. Tighten the screws, then pull the card out.

That leaves a gap of about one card. If cards jam, loosen the screws and raise the gate a
hair. Sleeved cards need a bigger gap: use a sleeved card in step 1.

### Testing

Put 20 cards in the hopper and tap the motor's switch on for a moment at a time. Each tap
should push out one card.

| What happens | Try |
|---|---|
| Two cards come out together | Lower the gate a little |
| Nothing comes out, the roller spins | Clean the O-rings with a damp cloth, or put something heavy on the stack |
| Cards come out crooked | Check the roller is centred, and both O-rings are seated |
| It works with 20 cards but not 150 | Normal at first. Note it, and we'll tune the gate and roller together |

Count how many cards out of 100 come out on their own. That number tells us whether
the design works or what to change.

# Scan bed and chute

`bed_chute.scad`. The card comes off the feeder onto the scan bed, gets its photo, and
drops into the chute, which sends it to one of three bins.

1. **Scan bed** (white, sloped 20°): the card slides down until **two small pins** near
   the front edge stop it, square under the camera. LED strips in both side walls light it.
2. **Photo.** Then a servo swings the pins down below the bed, and the card slides off.
3. **Chute**: a level tray above the bins catches it.
   - **Bin 2 (middle):** two small trapdoors in the tray floor drop open, like bomb-bay
     doors, and the card falls straight down. (Two half-width doors, because one full-width
     door would swing down into the middle bin.)
   - **Bin 1 or bin 3:** a servo tilts the whole tray 25° left or right and the card slides
     off that end. The frame's side panels stop it flying past the bin.

Every moving part was checked in OpenSCAD for collisions at both ends of its travel:
the tray tilted both ways, the trapdoors open, and the pins up and down.

### Parts to print (`stl/bed_chute_*.stl`)

| File | How many | Colour | Notes |
|---|---|---|---|
| `bed_plate` | 1 | **white** | The surface the camera looks at |
| `bed_side_left`, `bed_side_right` | 1 each | black | 236 mm tall, lie them flat. Right one has the camera socket |
| `tower_post`, `camera_head` | 1 each | black | |
| `pin_rocker` | 1 | any | The two stop pins |
| `tilt_bracket` | 1 | black | |
| `chute` | 1 | any | The tray |
| `trapdoor`, `trapdoor_left` | 1 each | any | |
| `trapdoor_mount`, `trapdoor_mount_left` | 1 each | any | |
| `hinge_lug`, `hinge_lug_left` | 1 each | any | |
| `frame_side` | **2** | black | |
| `front_bar` | 1 | black | 235 mm long |
| `bin` | **3** | black | About 250 cards each |

All print flat, as they open, with no supports. 15–20% infill is fine.

### Moving parts

| Job | Part |
|---|---|
| Stop pins up / down | SG90 servo, on the left bed wall |
| Tilt the tray | **MG90S** servo (metal gears), on the tilt bracket |
| Trapdoors | 2× SG90 servos, under the front of the tray |

A PCA9685 servo board connects all four servos to the Raspberry Pi. The feeder rig sits
behind the bed on a taller stand (`stand_h = 203` in `feeder_test.scad`), so cards come
off its exit shelf straight onto the bed.
