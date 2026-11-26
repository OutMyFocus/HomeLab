# Mault sorter

The sorter this project runs on now. The printed parts are the open **Mault** design
([mault.xyz/build](https://mault.xyz/build), models on MakerWorld, CC BY-NC-SA 4.0). They are not
copied into this repository: print them from the designer's page. What is different here is the
electronics: instead of Mault's own controller board and firmware, the Raspberry Pi 5 that runs
SortR drives the servo board directly, and the parts from the [Sorter Mk2](../mk2/MK2.md) are reused.

Two sorting modules give four bins plus the end bin. A third module needs three more servos.

## What is reused, and where it goes

| Part | In the Mault sorter |
|---|---|
| Raspberry Pi 5 + SortR | The controller. Replaces Mault's ESP32 board, so print plate 14 (its holder) is not needed |
| PCA9685 servo board | Same board Mault uses; wiring to the Pi is unchanged |
| 6 x MG90S servos | Three per module: trapdoor, paddle, pusher. The parts are drawn for SG90: print one module first and test the fit. Print plate 2 has looser and tighter horns |
| 4 x TCRT5000 sensors | One in the hopper, one in each module's gate, one spare |
| Pi Camera Module 3 | Looks down from the shroud in place of a webcam |
| WS2812B light strip | Inside the shroud |
| 5 V 10 A supply + 2 Wagos | Servo board, lights (and the Pi, see Power) |

**To buy:** one 360 degree (continuous rotation) micro servo for the feeder. The Mk2's N20 motor
and DRV8833 driver have no place in the Mault feeder and are not used.

## Servo board channels

The same channels as the Mault build guide.

| Channel | Part | Positions |
|---|---|---|
| 0 | Module 1 trapdoor (`m1_door`) | closed, open |
| 1 | Module 1 paddle (`m1_paddle`) | closed, open |
| 2 | Module 1 pusher (`m1_push`) | centre, left, right |
| 3 | Module 2 trapdoor (`m2_door`) | closed, open |
| 4 | Module 2 paddle (`m2_paddle`) | closed, open |
| 5 | Module 2 pusher (`m2_push`) | centre, left, right |
| 15 | Feeder (360 degree servo) | driven by the feed buttons |

Servo power goes to the board's V+ and GND; the Pi side (3.3 V, GND, SDA, SCL) stays on header
pins 1, 6, 3 and 5.

## Pi pins

| What | GPIO | Header pin |
|---|---|---|
| Hopper sensor DO | 16 | 36 |
| Module 1 gate sensor DO | 20 | 38 |
| Module 2 gate sensor DO | 21 | 40 |
| Spare sensor DO | 12 | 32 |
| Sensor VCC (3.3 V, never 5 V) | | 17 |
| Light strip data | 10 | 19 |

The sensors pull their output low when they see a card. They are read once **Sensors are fitted**
is ticked on the Machine health page.

## Bins

| Bin | Where the card goes |
|---|---|
| 1, 2 | Module 1, pushed left / right |
| 3, 4 | Module 2, pushed left / right (module 1's trapdoor opens first) |
| 5 | The end bin: every trapdoor opens |

## Power

One 5 V 10 A supply feeds a +5 V Wago and a GND Wago, and from there the servo board and the light
strip. Never use a supply with a voltage knob on the machine. The Pi can share the supply through a
USB-C plug only over short, thick wire (18 AWG): thin wire dropped it to 4.6 V and the Pi slowed
down. Until then the Pi keeps its own charger, with both on one switched power bar.

## Setting it up in SortR

1. **Machine** page: *Which machine* is **Mault sorter** (the default).
2. Centre each servo at 90 with its slider before pressing its horn on, then set each position and
   save it under its name. The angles in `config.py` (`SERVOS_MAULT`) are only starting points.
3. Try **Bin 1** to **Bin 5** and the feed buttons.

Not in yet: full sort runs on this machine (feeding to the first gate, scanning there and sorting
on their own). They need the built machine to place the camera and test the gate sensors.
