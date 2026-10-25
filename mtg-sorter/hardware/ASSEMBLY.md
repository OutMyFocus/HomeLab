# Assembly guide

How to put the machine together, in the order you'll actually build it:

1. [**Part 1: the feeder test**](#part-1-the-feeder-test). Uses only the round 1 parts
   (items 6, 11, 12, 14 and 19 in [`SHOPPING.md`](../SHOPPING.md)) plus printed parts.
   Do this first and get it working before buying round 2.
2. [**Part 2: the full machine**](#part-2-the-full-machine). The Pi, camera, scan bed,
   chute and bins, once round 2 arrives.
3. [**Part 3: the enclosure**](#part-3-the-enclosure). The sleek box around it, with your
   storage drawers as the bins. Build it once the open machine works.
4. [**Things the repo doesn't decide yet**](#things-the-repo-doesnt-decide-yet). Read this
   before round 2, because a few of them change what you build.

Card path, so the directions make sense: **hopper → roller pushes the bottom card out
under the gate → card slides down the scan bed and stops on two pins → photo → pins drop →
card lands in the chute → chute sends it to bin 1, 2 or 3.**

---

# Part 1: the feeder test

The goal is one number: out of 100 cards, how many come out **on their own** (not two
stuck together, not zero).

## What you need

| | Part | From |
|---|---|---|
| 1 | N20 gear motor, 6 V, 150 RPM, 3 mm D-shaft | Shopping item 6 |
| 2 | O-rings, **20 mm inside × 3 mm thick** | Shopping item 11 (pick two from the kit) |
| 2 | M3 × 10 mm self-tapping screws | Shopping item 12 |
| 2–3 | Small zip ties | Shopping item 14 |
| 1 | 4×AA battery holder with switch, plus 4 AA batteries | Shopping item 19 |
| | Printed: stand, hopper, gate, roller | See below |
| | Tools: small Phillips screwdriver, scissors or flush cutters, electrical tape | |

> **Check the motor's wires when it arrives.** Many N20 listings come with two short wires
> already soldered on. If yours only has two bare metal tabs, you don't need to solder.
> Either push the **female end of a Dupont jumper** onto each tab (they usually grip
> snugly), or strip about 1 cm off a wire, thread it through the tab's hole, twist it back
> on itself tightly, and cover it with electrical tape.
>
> **No battery holder?** Any 5 V USB phone charger works instead: cut the end off an old
> USB cable, and the red (+) and black (−) wires inside give you 5 V. Twist and tape them
> to the motor wires. Don't use a 12 V adapter: it will overheat a 6 V motor.

## 1. Print the parts

Bambu Studio, **0.20 mm Standard**, PLA, no supports.

| File | How to lay it | Infill | Notes |
|---|---|---|---|
| `stl/feeder_stand_mid.stl` | as it opens | 15% | 92 mm tall. The same stand later goes on the enclosure's bridge |
| `stl/feeder_hopper.stl` | as it opens | 15% | |
| `stl/feeder_gate.stl` | flat | 15% | |
| `stl/feeder_roller.stl` | standing on its end | **100%** | It has to grip the shaft tightly |

When they're off the printer, clean any strings or blobs from the **floor of the hopper**
and the **bottom edge of the gate**. Cards catch on anything sticking up.

## 2. Put the tyres on the roller

1. Find two O-rings in the kit that are 20 mm inside and 3 mm thick. With calipers, the
   outside should measure about 26 mm.
2. Stretch one into each groove on the roller. They should sit snug and not twist. If
   they're loose, the ring is too big; if you can't get one on, it's too small.

## 3. Fit the roller to the motor

1. Look at the motor shaft: one side is flat (the "D").
2. Line the flat side of the roller's hole up with the flat on the shaft, and press the
   roller on until it stops. Push on the roller's hub, not on the O-rings.
3. It should be tight enough that you can't turn the roller without turning the motor.
   If it slips, wrap the shaft in one layer of tape and press it on again.

## 4. Mount the motor in the stand

The motor lies sideways in the stand, with the roller in the middle (under the hole in
the hopper floor) and the motor body on a block called the cradle.

1. With the hopper **off**, lower the motor and roller in from the open top of the stand.
   The roller can't fit through the side hole, so it goes in from above.
2. Rest the gearbox on the cradle block and point the back of the motor (where the wires
   are) at the square hole in the side wall. The wires come out through that hole.
3. Thread zip ties down through the two slots in the cradle, around the motor, and pull
   them tight. Snip the tails.
4. Spin the roller with a finger. It should turn freely without rubbing the stand.

## 5. Put the hopper on

1. Set the hopper on top of the stand. The four small pegs on the stand's top edge go into
   the holes in the hopper's floor.
2. Look at the floor from above. The roller's O-rings should **just** poke up through the
   opening (by design, 0.8 mm, about the thickness of two or three cards). Run a fingertip
   across: you should feel the rubber, not a bump.
   - **Doesn't poke through at all:** put a strip of card or tape under the motor on the cradle
     to raise it a little.
   - **Sticks up a lot** (cards rock on it): the O-rings are too thick, try a different pair.

## 6. Fit and set the gate

The gate is the plate on the front wall. The gap under it decides how many cards get out:
one card fits under it, two shouldn't.

1. Screw the gate onto the front of the hopper with the two M3 screws, through its slotted
   holes. The bevelled bottom edge faces **into** the hopper. Leave the screws loose.
2. Slide one card under the gate, onto the floor.
3. Push the gate down until it rests on the card, then tighten both screws.
4. Pull the card out.

Sleeved cards need a bigger gap: do step 2 with a sleeved card instead.

## 7. Wire it up

1. Put 4 AA batteries in the holder. Switch it **off**.
2. Connect the holder's red wire to one motor tab or wire and black to the other. Twist and
   tape, or use the jumpers if the motor has them. Polarity doesn't matter for safety, it
   only sets which way the roller turns.
3. Hold the switch on for half a second and watch the **top** of the roller: it must move
   **toward the gate** (the front, where the exit shelf is). If it goes the other way, swap
   the two wires.

## 8. Test it

1. Put **20 cards** in the hopper, face up, squared up.
2. Flick the switch on for a moment, then off. Each flick should push out one card onto the
   exit shelf.
3. Once 20 works, do the real test: **100 cards**, counting:
   - singles (good)
   - doubles (two or more together)
   - misses (roller spun, nothing came out)
   - jams or crooked cards

| What happens | Try |
|---|---|
| Two cards come out together | Loosen the gate screws, lower the gate a hair, tighten |
| Nothing comes out, the roller spins | Wipe the O-rings with a damp cloth; put a heavy flat thing on top of the stack |
| Cards come out crooked | Check the roller is centred under the opening and both O-rings are seated |
| Card jams under the gate | Raise the gate a hair; check the gate's bottom edge has no blobs |
| Works with 20 cards, not 150 | Normal at first. Note the numbers; the gate and roller get tuned together |
| Motor stalls or just hums | Fresh batteries. If still stuck, the roller is rubbing the stand: re-seat the motor |

Write down the singles/doubles/misses counts and what kind of cards you used (new, old,
foil, sleeved). That decides whether the feeder design changes before round 2.

---

# Part 2: the full machine

Round 2 parts. Build it in this order, testing each stage before the next, so a problem
only ever has one place to hide.

## Stage A: Raspberry Pi and camera

This gets recognition working on the real camera before any moving parts.

1. Set up the Pi and the scanner software: follow [Raspberry Pi setup](#raspberry-pi-setup)
   below. You can do all of it before the camera cable arrives.
2. Check the camera is seen: `rpicam-hello --list-cameras` should list an `imx708`
   (that's the Camera Module 3).
3. Connect the camera: the Pi 5 cable (item 3) into the camera and into the Pi. The silver
   contacts face the board on both ends. Lift the connector latch, push the cable in straight,
   press the latch down. Until the scan bed is printed, prop the camera about 120 mm above a
   sheet of white paper, lens down, with the LED strip (item 10) lighting it from the side.
4. Start the app and open it from your laptop or phone (step 7 of the setup below). Put cards
   under the camera and check they're recognized. Try a foil too.

> **Camera not found?** Check with `rpicam-hello --list-cameras`. If it says "No cameras
> available" with the cable seated properly, the Pi's auto-detect may be missing it. Edit
> `/boot/firmware/config.txt`: change `camera_auto_detect=1` to `camera_auto_detect=0`, and
> add `dtoverlay=imx708` and `dtoverlay=imx708,cam0` under `[all]` at the end. Reboot.
> The app uses the Pi camera automatically when there is one. You can switch to a USB webcam
> on the page, or start it with `--camera 0`.

### Raspberry Pi setup

**What you need:** the Pi 5, the **official 27 W USB-C power supply** (5 V 5 A; a phone
charger will make it throttle or reboot), a **32 GB or bigger microSD card**, and a computer
with an SD card slot or a USB card reader. A case with a fan is a good idea, since the Pi 5
runs hot under load.

**1. Flash the SD card** (on your computer)

1. Install [Raspberry Pi Imager](https://www.raspberrypi.com/software/) and open it.
2. **Device:** Raspberry Pi 5. **OS:** Raspberry Pi OS (64-bit). **Storage:** your microSD card.
3. When it asks to apply OS customisation settings, choose **Edit settings**:
   - **General:** hostname `mtgsorter`; a username and password you'll remember;
     your Wi-Fi name and password; Wi-Fi country **CA**; your time zone and keyboard layout.
   - **Services:** turn on **Enable SSH**, with password authentication.
4. Save, then **Yes** to write. It takes a few minutes.

**2. First boot**

Put the card in the Pi (slot underneath, contacts facing up toward the board), plug in the
power, and wait about 2 minutes. Then, from a terminal on your computer (PowerShell on Windows,
Terminal on a Mac):

```bash
ssh <your username>@mtgsorter.local
```

Type `yes` the first time, then your password. If `mtgsorter.local` isn't found, look up the
Pi's address in your router's device list and use that instead.

**3. Update and install system packages** (on the Pi)

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git python3-venv python3-picamera2 rpicam-apps i2c-tools
sudo reboot
```

Wait a minute, then `ssh` back in. (The camera packages are usually already installed; this
just makes sure.)

**4. Turn on I²C** (for the servo board later)

```bash
sudo raspi-config nonint do_i2c 0
```

**5. Get the scanner code and its Python packages**

```bash
git clone https://github.com/OutMyFocus/HomeLab.git
cd HomeLab/mtg-sorter
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`--system-site-packages` lets the virtual environment see `picamera2`, which is installed by
`apt`, not `pip`. The `pip install` takes a few minutes on the Pi.

**6. Build the card database**

```bash
python build_db.py --sets dmu,one      # quick test, under a minute
python build_db.py --all               # every card: a few hours, safe to stop and resume
```

**7. Start the app**

With no camera yet, use phone photos of cards. Copy them to the Pi from your computer
(`scp *.jpg <your username>@mtgsorter.local:~/photos/` after `mkdir ~/photos` on the Pi), then:

```bash
cd ~/HomeLab/mtg-sorter && source .venv/bin/activate
python app.py --host 0.0.0.0 --demo ~/photos
```

Once the camera is connected, drop `--demo ~/photos` and the app uses it. On your laptop or phone (same Wi-Fi), open
**http://mtgsorter.local:5000**. Press Ctrl+C in the terminal to stop it.

**Getting updates later:** to run the app on boot and keep it updated from GitHub by itself,
follow steps 1 and 1b of [`deploy/REMOTE_ACCESS.md`](../deploy/REMOTE_ACCESS.md). By hand, it's
`cd ~/HomeLab && git pull`, then `pip install -r mtg-sorter/requirements.txt` inside the virtual
environment.

## Stage B: print the scan bed and chute

All from `stl/bed_chute_*.stl`, flat, as they open, no supports, 15–20% infill.

| Part | Qty | Colour |
|---|---|---|
| `bed_plate` | 1 | **white** (the camera sees it) |
| `bed_side_left_enclosure`, `bed_side_right_enclosure` | 1 each | black |
| `tower_post`, `camera_head` | 1 each | black |
| `pin_rocker` | 1 | any |
| `tilt_bracket` | 1 | black |
| `chute` | 1 | any |
| `trapdoor`, `trapdoor_left` | 1 each | any |
| `trapdoor_mount`, `trapdoor_mount_left` | 1 each | any |
| `hinge_lug`, `hinge_lug_left` | 1 each | any |

The bed walls, the chute and the feeder stand from Part 1 all go on the enclosure's bridge
(Part 3), which holds them at the right heights: the hopper floor ends up about 2 mm above
the top of the scan bed, so cards drop straight on.

## Before any servo goes in: centre it

Every servo needs its horn fitted at the **middle** of its travel, or the part it moves
ends up at the wrong angle. Wire up the electronics first (Stage C), then for each servo:
plug it into the PCA9685, set it to 90°, and only then press the horn on. See
[the test snippet](#servo-test-snippet) below.

## Stage C: electronics

> **No soldering needed if you buy the right versions.** Three round 2 parts often need it:
> - **Motor driver boards** (DRV8833 and the similar small ones) usually ship with the header
>   pins loose in the bag. Buy a listing that says **"pre-soldered headers"** or has **screw
>   terminals**, so the jumper wires (item 13) push straight on. Most generic PCA9685 boards
>   (blue, with the green screw terminal) come fully assembled; the Adafruit one doesn't.
> - **LED strip:** cutting it and joining the two pieces normally means soldering. Instead,
>   don't cut the wire between them: run one length along the first wall, loop it under or
>   behind, and carry on along the second wall, then cut only the far end. Or use
>   **solderless clip connectors** sized for the strip width (8 or 10 mm).
>
> Everything else is plug-in or screw terminals: servos plug into the PCA9685, the 5 V adapter
> goes into the barrel jack's screw terminals, the camera cable clips in.

There's no motor or servo code in the repo yet, so **these connections are a proposal**,
picked so they don't clash with anything the Pi or camera uses. When the sorter code gets
written, it should use these.

```
 5 V 4 A adapter ──► barrel jack adapter ──┬──► PCA9685  V+ / GND  (servo power)
                                           └──► DRV8833  VM / GND  (motor power)

 Raspberry Pi 5                 PCA9685 servo board
   pin 1  3.3 V  ─────────────► VCC
   pin 3  GPIO2 (SDA) ────────► SDA
   pin 5  GPIO3 (SCL) ────────► SCL
   pin 6  GND  ───────────────► GND      ◄── all grounds joined

 Raspberry Pi 5                 DRV8833 motor driver ──► N20 feeder motor (OUT1 / OUT2)
   pin 11 GPIO17 ─────────────► IN1
   pin 13 GPIO27 ─────────────► IN2
   pin 14 GND ────────────────► GND
```

| PCA9685 channel | Servo | Moves |
|---|---|---|
| 0 | Stop pins | Pins up (card stops) / down 28° (card slides off) |
| 1 | Chute tilt | Centre / 25° left / 25° right |
| 2 | Right trapdoor | Closed / open 90° |
| 3 | Left trapdoor | Closed / open 90° |

Rules that matter:

- **The servo supply must be 5 V.** MG90S servos take 4.8–6 V; a 12 V adapter will burn them
  out in seconds. Check the label on the adapter before connecting it. If it's 12 V, either
  swap it for a 5 V 4 A one, or add a small **buck converter** (12 V in, set to 5 V out,
  with screw terminals so it's solder-free) between the adapter and the boards.

- **Never power the servos from the Pi's 5 V pin.** Four servos moving at once will crash
  the Pi. They get the separate 5 V 4 A adapter (item 8) through the barrel jack adapter (item 9).
- **Join all the grounds** (Pi, PCA9685, DRV8833, adapter). Without a shared ground the
  signals don't work.
- Turn on I²C on the Pi: `sudo raspi-config` → Interface Options → I2C → Enable. Then
  `i2cdetect -y 1` should show `40` (the PCA9685).
- The N20 is a 6 V motor running on 5 V here. It'll turn a little slower than on the
  batteries, which is fine for feeding.

### Servo test snippet

Not in the repo yet; for checking wiring and centring servos.

```bash
pip install adafruit-circuitpython-servokit
```

```python
from adafruit_servokit import ServoKit
kit = ServoKit(channels=16)
kit.servo[0].angle = 90   # change the channel and angle to test each servo
```

## Stage D: the scan bed

1. **Bed plate into the walls.** Slide the white bed plate into the grooves on the inside of
   `bed_side_left` and `bed_side_right`, so the walls stand on the table on either side.
   The low rails on the plate face up; the pin slots are at the low (front) edge.
2. **Tilt bracket.** It goes across between the two walls near the bottom front. Screw it in
   with M3 screws through the holes in each wall (2 per side).
3. **Stop-pin servo.** Push a servo into the rectangular hole in the **left** wall from the
   outside, shaft pointing into the bed, and screw it in with the two screws that came with it.
4. **Pin rocker.** Centre the servo (see above), fit a single-arm horn, and screw the rocker's
   flat plate to the horn with the two tiny horn screws. With the servo at "up", the two pins
   should poke up through the slots at the front of the bed. Set the servo to "down" (28° the
   other way): the pins must drop fully below the bed surface.
5. **LED strips.** Cut two pieces about 9 cm long and stick one in the groove along each
   wall, just above the bed. Join them and power them from a Pi USB port.
6. **Camera tower.** Push `tower_post` into the socket on the right wall, then
   `camera_head` onto the top of the post. Screw the camera onto the head
   (4× M2 × 6 mm, lens down). The lens should end up 120 mm above the middle of a card resting
   on the pins, square to the sloped bed.

Test: power the LEDs, put a card on the bed so it rests against the pins, and check the
app recognizes it. Then drop the pins and check the card slides off cleanly.

## Stage E: the chute and trapdoors

1. **Trapdoor servos.** Screw a servo into each `trapdoor_mount` (2 screws each). Screw each
   mount under the **front** of the chute floor, one each side, with M2 screws from above.
2. **Hinge lugs.** Screw `hinge_lug` and `hinge_lug_left` under the **back** of the chute floor,
   same way.
3. **Trapdoors.** Each door has two ears. The back ear's hole goes over a hinge pin through
   the lug: use an M3 screw as the pin (1.75 mm filament is too thin for the 2.9 mm hole and
   would rattle). The front ear screws to the servo horn.
   Centre each servo first, so both doors close flush with the chute floor.
4. **Into the machine.** The chute's front axle goes into the upstand on the enclosure's
   bridge (Part 3). The plate on the chute's back end screws to the **tilt servo's** horn:
   push the tilt servo through the tilt bracket from the back, screw it in, centre it, then
   attach the horn to the chute.

Test each move by hand with the snippet: tray level and doors shut; doors open; tilt 25° each
way. Nothing should touch the bed walls or the bridge.

## Stage F: drawers and feeder

1. Slide the three Card Catalog drawers into the dock under the bridge (Part 3): left = bin 1,
   middle = bin 2, right = bin 3.
2. Put the hopper on the feeder stand (`feeder_stand_mid`) on the bridge, behind the bed, with
   its exit shelf facing the bed. Cards should come off the shelf and drop onto the top of the bed.
3. Move the motor wires from the battery holder to the DRV8833's OUT1 / OUT2.

The whole run, card by card: feeder pulse → card slides to the pins → photo → chute set to
the bin → pins drop → card slides into the chute → doors open (bin 2) or the tray tilts
(bins 1 and 3) → back to level. That loop doesn't exist in the code yet.

---

# Part 3: the enclosure

The box from [`README.md`, Enclosure](README.md#enclosure). The open frame and bins that
Part 2 first had are gone; everything else from Part 2 stays. Print list and part
names are in the README; the print order, slicer settings and the fit-check plates to
print first are in [`PRINTING.md`](PRINTING.md).

> **The drawers are Card Catalog v1.2** (MakerWorld 3016550). The dock is sized from
> Nic's 3MF of it (the `dr_*` block in `enclosure.scad`), so print three drawers and three
> drawer tops from that 3MF, in whatever colours you like. If you ever switch drawers,
> change the `dr_*` numbers and run `export_enclosure.sh`.

## 1. Bench work

1. **Floor:** join `floor_fl` + `floor_fr` and `floor_bl` + `floor_br` with splices in the
   pockets underneath (M2 screws or CA glue), then the front pair to the back pair. Stick
   the six rubber feet in the recesses underneath.
2. **Bridge:** join `bridge_front` + `bridge_back` the same way. Screw the two new bed walls
   (`..._enclosure.stl`) to it from below (M3 into the holes in their bottom edges), the
   bed plate between them, then the tilt bracket, pins and camera tower exactly as in
   Part 2, Stage D. Screw the chute's front axle through the upstand at the front.
3. **Deck:** join `deck_fl` + `deck_fr`, and `deck_bl` + `deck_br`. Leave the front pair and
   back pair separate: the back pair lifts off for access to the Pi bay.
4. **Drawers:** print three Card Catalog drawers and their top bars from the MakerWorld
   3MF. Slide a toploader with a card into each pocket from the top, clip the bar on.
5. **Fascia and back:** join `fascia_l` + `fascia_m` + `fascia_r` with splices glued in
   the pockets on the inside face (CA glue, the pockets are too shallow for screws), and
   glue the `light_bar` across the top of the seams, over the three slots. Join
   `back_l` + `back_r` the same way.

## 2. Assembly, bottom up

1. Fix the Pi (4 × M2.5) and the PCA9685 to the standoffs on the floor, the motor driver
   with a zip tie. The Pi's ports face the back.
2. Push the two `post_front`s and two `post_back`s onto their pegs at the corners (the
   front ones have a shorter fascia groove). Slide the fascia (light slots at the top),
   the four `side` pieces (two per side, pockets facing in, splice them) and the back panel
   down the posts' grooves into the groove in the floor. The Pi's ports line up with the
   cut-outs in the back panel.
3. Stand the two `divider`s in the grooves in the middle curbs, flanges facing out.
4. Lower the bridge (with the whole mechanism on it) onto the dividers' flanges and the two
   `leg`s at the back; screw it to the flanges (M3, 3 per side). Wire everything up (Stage C).
5. Put `feeder_stand_mid` in the fence on the bridge with the hopper on it, exit shelf facing
   the bed.
6. Slide the `post_sleeve` over the camera post, lay the front deck on, then the back deck.
   Screw both to the posts (M3, countersunk, 4 corners). Push the `head_cover` over the
   camera head, the `tower` over the hopper, and its lid on.
7. Slide the three drawers in.

---

# Things the repo doesn't decide yet

| # | Gap | Why it matters | Suggested answer |
|---|---|---|---|
| 1 | **No motor or servo code.** `app.py` and `mtgscanner/` only recognize and price cards. There's no `send_to_bin`, no pin numbers, no servo angles. | The machine can't sort until it's written. | Write it after the feeder test, using the wiring above. |
| 2 | **The code has 4 bins, the machine has 3.** `config.py` sends cards to bin 0 (no price), 1 (bulk), 2 ($1–10) and 3 ($10+). | Bin 0 has nowhere to go. | Merge "no price" into bin 1, or leave them on the bed for you to pull by hand. |
| 3 | **Servo model.** The shopping list says 4× MG90S; `hardware/README.md` says SG90 for the pins and trapdoors. | None really: same size and screw holes. | MG90S everywhere is fine, and stronger. |
| 4 | **Nothing fastens the three assemblies together** until the enclosure's bridge exists. | Alignment by eye, every time. | Print `bridge_front` and `bridge_back` early (plates 4 and 5 in PRINTING.md); the bed walls, chute and feeder stand all screw to them. |
| 5 | **Where the Pi sits, and cable length.** The camera on the tower is about 30 cm off the table. The 300 mm cable may not reach a Pi on the table. | You might need a longer cable. | Mount the Pi on the right bed wall, or on the floor under the bridge as the enclosure plans; check the reach before ordering anything. |
| 6 | **Servo angles are from the CAD, not tested.** Pins 28°, tilt ±25°, doors 90°. | Real servos vary by a few degrees. | Find each end position with the test snippet and write them down. |
| 7 | **Trapdoor hinge pin.** The design says "3 mm screw or filament", but the holes are 2.9–3.2 mm and filament is 1.75 mm. | Filament would rattle. | Use M3 screws (they're in the screw kit). |
| 8 | **The motor's direction and run time per card.** | Too long and it feeds two cards. | Start with short pulses (~0.2 s) and tune during the full-machine test. |
