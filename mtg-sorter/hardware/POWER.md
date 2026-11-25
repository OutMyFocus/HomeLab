# Power: one wall plug, one button

The finished sorter runs from **one 5 V power supply** plugged into the back, and turns on and
off with **one button** on the top deck. Everything inside (Pi, camera, servos, feeder motor,
LED light) runs on 5 V, so there's nothing to convert: one supply, two Wago blocks to share it
out, done.

The button is a **momentary** button wired to the Pi 5's own power-button pads, not a switch
that cuts the power. That matters: cutting power to a running Pi can corrupt the SD card. With
the button on the Pi's pads:

| You do | The sorter does |
|---|---|
| Plug it in | Boots by itself (about 30 s), button light comes on |
| Press the button while it's on | Shuts down cleanly, then switches itself fully off (light goes out, LED strip goes out) |
| Press the button while it's off | Boots |
| Hold the button for several seconds | Forces it off, for when it's frozen. Only then |

"Off" here means the Pi has shut down and switched off its own power; the supply stays plugged in,
and the whole thing draws a fraction of a watt, like a TV on standby. Unplug it if it's going
away for a while.

## Why not the 5 V 4 A adapter you already have

It's too small to run everything at once. Rough worst case, when the camera is working and a
card is being sorted:

| Part | Typical | Peak |
|---|---|---|
| Pi 5 + Camera Module 3 | 1.2 A | 2 A |
| LED strip (Aclorol 1 m COB, full brightness) | 1 A | 1.5 A |
| 4 × MG90S servos (two or three moving at once) | 0.3 A | 2 A |
| N20 feeder motor | 0.1 A | 0.5 A |
| **Total** | **about 2.6 A** | **about 6 A** |

At peak that's 50% over the 4 A adapter, and the Pi 5 is fussy: when the voltage sags under a
servo kick it throttles or reboots. A **5 V 10 A** supply (shopping item 22) has room to spare.
Keep the 4 A adapter as a bench supply for testing servos on their own.

## Parts

Shopping list items 22–27 ([`SHOPPING.md`](../SHOPPING.md)), about $80 in total, plus things you already have:

| # | Part | Job |
|---|---|---|
| 22 | 5 V 10 A power supply, 5.5 × 2.1 mm plug | The one wall plug |
| 23 | Panel-mount DC jack, 5.5 × 2.1 mm, pre-wired (DC-022B style, 11 mm hole) | The inlet in the back panel |
| 24 | 16 mm momentary metal push button with LED ring, 3–6 V | The power button, in the deck |
| 25 | USB-C male plug to screw terminal adapter | Feeds the Pi from the supply |
| 26 | 2 × Wago 221-415 (5-way lever connectors) | One for +5 V, one for ground |
| 27 | 18 AWG silicone wire, red and black | Power wires |
| 13 | Dupont jumpers (have) | Button and signal wires |
| — | 2-pin header (from the DRV8833 bag) + solder (have) | On the Pi's J2 pads |

If the supply you buy has a 5.5 × 2.5 mm plug instead (common at 10 A), buy the 2.5 version of
the panel jack so they match. Same 11 mm hole.

## Wiring diagram

```
                       back panel
  wall ── 5 V 10 A ──► [DC jack] ──red 18 AWG──►  WAGO +5V  ──┬──red──► USB-C screw adapter (+) ──► Pi 5 USB-C
          supply                 ──black──────►  WAGO GND  ──┼──black► USB-C screw adapter (−)
                                                             │
                                                  +5V ───────┼──red──► PCA9685 green terminal V+   (servo power)
                                                  GND ───────┼──black► PCA9685 green terminal GND
                                                             │
                                                  +5V ───────┴──red──► DRV8833 VCC / VM           (motor power)
                                                  GND ──────────black► DRV8833 GND

  LED strip (USB-A plug) ──► any Pi USB port   (goes off when the Pi switches off)

  Power button (16 mm, momentary, LED ring)
     C  ───────────►  Pi 5 J2 pad 1   ┐ the Pi's own power-button pads,
     NO ───────────►  Pi 5 J2 pad 2   ┘ either way round
     LED + ────────►  Pi pin 15 (GPIO22)    lights while the Pi is on
     LED − ────────►  Pi pin 9  (GND)
     (NC: not used)

  Signal wiring (I²C to the PCA9685, GPIO17/27 to the DRV8833) stays as in ASSEMBLY.md, Stage C.
```

Rules:

- **Everything is 5 V.** Nothing in this build wants 12 V. The DRV8833 tops out at 10.8 V and
  the MG90S at 6 V, so a 12 V supply anywhere would destroy them.
- **Each board gets its own pair of wires from the Wagos** (a "star"), rather than chaining
  from one board to the next. The servos' current then doesn't flow through the Pi's wires,
  which keeps servo kicks from browning out the Pi.
- **Use the 18 AWG wire** for the supply-to-Wago, Wago-to-Pi and Wago-to-PCA9685 runs. The
  Dupont jumpers are fine for the DRV8833 (the feeder motor draws very little) and for all the
  signal wires.
- **All grounds end up joined** through the ground Wago and the Pi's USB-C. That's needed for
  the signals to work, and it's already done by the diagram above.
- Never feed the servos from the Pi's own 5 V pins.

## Steps

### 1. Solder the J2 header on the Pi

On the top of the board, near the edge by the **RTC battery connector (BAT)**, there are two small holes labelled **J2**. Shorting them is the
same as pressing the Pi's built-in power button.

1. Unplug the Pi. Take two pins off one of the header strips that came with the DRV8833 boards.
2. Push the short ends down through J2 from the top, flux, and solder from underneath (or hold
   the pins with Blu-Tack and solder from the top). Same as the DRV8833 headers.
3. Test before anything else: plug the Pi in, wait for it to boot, then briefly touch a
   screwdriver across the two J2 pins. It should shut down. Touch them again: it boots.

Then the button's C and NO wires go onto the two pins with female Dupont jumpers.

### 2. Fit the jack and the button

- **Jack:** from outside, through the 11 mm hole low on `back_l` (the left back panel, seen
  from the front), nut on the inside. If your jack's thread is bigger, open the hole up with a
  drill bit or a round file.
- **Button:** from the top, through the 16 mm hole in the front-right corner of `deck_fr`,
  nut underneath. Put the deck on last, so leave the button's wires long (about 45 cm) and
  zip-tie them along the right-hand wall, up under the deck lip, back to the Pi bay. Keep them
  clear of the right drawer, where cards drop.

Both holes are in the updated `enc_back_l.stl` and `enc_deck_fr.stl`. If you've printed those
two already, either reprint them (`bambu/MTG_Sorter_Power_Parts.3mf` has just those two) or
drill the holes: 11 mm for the jack, centred 103 mm left of the middle (seen from behind:
103 mm right of the middle) and 16 mm above the floor; 16 mm for the button, 30 mm in from the
front and the right edges of the deck.

### 3. Wire the power

1. Stick the two Wago blocks to the floor in the back-left corner, beside the jack
   (double-sided tape).
2. Jack red → +5 V Wago, black → ground Wago.
3. Cut 18 AWG pairs for the Pi, the PCA9685 and the DRV8833, strip 11 mm for the Wagos, and run
   them out as in the diagram. Red into +, black into −, every time.
4. Before plugging the USB-C adapter into the Pi, check twice that red goes to its **+** (or
   VBUS) terminal and black to **−** (GND). If you have a multimeter, plug the supply in and
   check it reads +5 V the right way round. A reversed feed can kill the Pi.
5. LED strip into a Pi USB port. Leave its inline dimmer where you can reach it.

### 4. Set up the Pi (once)

On the Pi, with the latest code pulled:

```
cd ~/HomeLab/mtg-sorter
sudo sh deploy/power-setup.sh
sudo reboot
```

It needs your password once. It does three things:

1. `usb_max_current_enable=1` in `/boot/firmware/config.txt`. A supply that isn't the official
   USB-C one can't tell the Pi it's good for 5 A, so the Pi limits its USB ports to 0.6 A
   unless told otherwise. The LED strip needs more.
2. `dtoverlay=gpio-led,gpio=22,label=power,trigger=default-on` in the same file: the button's
   light comes on as soon as the Pi starts and goes out when it's off.
3. `POWER_OFF_ON_HALT=1` in the Pi's bootloader settings: after a shutdown the Pi switches
   everything off (USB ports, 3.3 V, the button light) instead of idling at about 1 W.

To have it wait for the button after being plugged in, instead of booting straight away, also
set `WAIT_FOR_POWER_BUTTON=1` (`sudo rpi-eeprom-config --edit`). Most people don't want that:
it means it won't come back on by itself after a power cut.

### 5. Test

1. Press the button: within a few seconds the web app stops answering and the light goes out.
2. Press again: light on, and after about 30 s the web app is back at
   https://mtgsorter.taild0ce28.ts.net.
3. `vcgencmd get_throttled` on the Pi, after running a few cards, should print
   `throttled=0x0`. Anything else means the voltage dipped: check the 18 AWG runs and the Wago
   connections.

On Raspberry Pi OS Lite one press shuts down. If the Pi has the desktop installed, one press
pops up a menu instead; press twice to shut down.

## The button's light

The ring LED runs straight off a Pi pin at 3.3 V. The **3 V** version of the button is the
brightest that way; on the 3–6 V or 5 V version it's dimmer but visible (red, green and yellow
rings come out brighter than blue and white). A 12 V version would barely glow: don't buy that
one. If it doesn't light at all, swap the two LED wires; the ring only works one way round.
