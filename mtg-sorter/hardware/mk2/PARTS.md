# Sorter Mk2 parts to order (Amazon.ca)

List from 2026-11-09. Everything on it was bought on 2026-11-10.

## Summary

Mk2 needs 17 new items from Amazon.ca, most of them under $20 each. Order them once, when the design is final: a few hole sizes in the print files get set to match the exact parts you buy.

You already have these, and Mk2 reuses them: the Pi 5 with its Active Cooler, the Camera Module 3, the PCA9685, the DRV8833 boards, the WS2812B light strip, your MG90S servos (you have plenty, plus the old machine's), the O-ring kit, PLA, and the old 150 RPM N20 (keep it as a spare).

## Power and the power button

One 5 V brick powers everything, through a jack on the back. The button turns the Pi on and off, and the relay cuts the servos, motor and lights whenever the Pi is off. Never use a 12 V adapter: Mk2 has no regulator.

| Part | Buy | Qty | What for | Price seen (CAD) |
| --- | --- | --- | --- | --- |
| 5 V 10 A power brick (5 V only, never 12 V). The Adafruit one is unavailable, so use the SUYOOULIN instead. Its plug may be 5.5 x 2.5 mm: if it wobbles in the 2.1 mm panel jack, get the 2.5 mm version of the jack. | [SUYOOULIN 5V 10A 50W, pick model PA-5V-10A (not PA-12V)](https://www.amazon.ca/s?k=SUYOOULIN+PA-5V-10A) | 1 | the one plug | 33.99 (2026-11-10, Prime) |
| Panel-mount DC jack, 5.5 x 2.1 mm, 10 A | [5.5 x 2.1 mm 10A threaded panel jack](https://www.amazon.ca/Socket-Threaded-Female-Connector-Adapter/dp/B0D3VCDXNV) | 1 | in the back panel | check |
| 1-channel 5 V relay module with a high/low trigger jumper | [AEDIKO 4-pack](https://www.amazon.ca/AEDIKO-Channel-Optocoupler-Isolation-Support/dp/B095YD3732) | 1 (4 in the pack) | cuts servo, motor and light power while the Pi is off | about 8 to 13 |
| 16 mm momentary push button with a 5 V LED ring | [Ulincos U16F1, red ring](https://www.amazon.ca/Ulincos-Momentary-Button-Suitable-Mounting/dp/B01I9KDV2Q) | 1 | the power button, front right | check |
| USB-C plug to screw terminals | [USB-C male screw terminal](https://www.amazon.ca/Connector-Solderless-Pluggable-Extension-Interface/dp/B08D93ZSM4) | 1 | feeds the Pi from the brick | check |
| WAGO 221-415 lever nuts | [WAGO 221-415, 10-pack](https://www.amazon.ca/221-415-Lever-Nuts-Conductor-Compact-Connectors/dp/B06XH47DC2) | 2 (10 in the pack) | 5 V and ground for everything | 15.75 |

Pick a brick whose plug really is 2.1 mm. Many 5 V 10 A bricks have a 2.5 mm plug that only claims to fit 2.1 mm, and it sits loose. The [COOLM 5V 10A](https://www.amazon.ca/5V-10A-Power-Supply-Adapter/dp/B07H9XRZBP) is one of those, so it's a fallback only.

## Servos and motors

Mk2 uses 5 MG90S servos: 2 for the trapdoors, 2 for the pushers and 1 for the stop bar. You already have enough of them, so no new servos are needed.

| Part | Buy | Qty | What for | Price seen (CAD) |
| --- | --- | --- | --- | --- |
| Servo extension cables, 300 mm, male to female | [Walfront 10-pack](https://www.amazon.ca/Walfront-Extension-Connector-Helicopter-Connection/dp/B0CFR8DDHB) | 1 pack | servos to the PCA9685 through the wall channels | check |
| N20 gear motor, 6 V 60 RPM, 3 mm D shaft 10 mm long | [CHANCS N20 6V 60RPM](https://www.amazon.ca/Motor-60RPM-Shaft-Length-Electric/dp/B07G1X7F59) | 1 (buy 2 if you can) | the feeder: about 2.5 x the torque of your 150 RPM one | about 10 to 13 |

The stronger motor matters. Your feeder stalled with a full 180-card stack, and the Mk2 magazine holds about 450. Check that the shaft is a 3 mm D shaft at least 9 mm long. The thread-shaft (M4 x 55 mm) versions won't fit the roller.

## Joints and gentle card handling

The steel pins and magnets replace every screw and drop of glue. The PTFE tape is what the cards slide on.

| Part | Buy | Qty | What for | Price seen (CAD) |
| --- | --- | --- | --- | --- |
| 3 x 16 mm steel dowel pins (15.8 mm is fine) | [uxcell 3 x 15.8 mm, 100 pcs](https://www.amazon.ca/Stainless-Steel-15-8mm-Fasten-Elements/dp/B00B3MFWY8) | 1 pack (about 40 used) | pin the wall and base tiles together, and the two pusher levers | 13.69 |
| 3 x 10 mm steel dowel pins | [uxcell 3 x 10 mm, 50 pcs](https://www.amazon.ca/uxcell-Stainless-Support-Shelves-Silver/dp/B07M9TS54L) | 1 pack (about 6 used) | trapdoor hinges, stop bar | check |
| 6 x 3 mm neodymium disc magnets | [6 x 3 mm N35, 50-pack](https://www.amazon.ca/Neodymium-Magnets-50-Pack-Crafts-Office/dp/B0F74W1SNS) | 2 packs (54 used, one pack is 4 short) | hold every module, bin and panel in place | check |
| PTFE tape, 1/2 inch, adhesive backed | [ProLine PTFE tape, 1/2 in x 33 ft](https://www.amazon.ca/Teflon-Vacuum-Impulse-Sealers-Thicker/dp/B08GFD3TLX) | 1 roll | scan bed lands, level floors, magazine floor | check |
| Linear polarizer film, A4 | [A4 linear polarizer sheet](https://www.amazon.ca/Polarization-Polarizer-Educational-Physics-Polarized/dp/B06XWXRB75) | 1 sheet | lens disc and light bar strips, to stop foil glare | about 11 to 25 |
| Cork sheet, 2 mm, self-adhesive | [uxcell 2 mm cork, 6 sheets](https://www.amazon.ca/uxcell-Self-Adhesive-Rectangle-Insulation-Decoration/dp/B0DQPKHCNL) | 1 pack | the feeder shoe's two pads (skip it if you have cork left from feeder v4) | 20.99 |

Avoid the 6 x 3 mm magnets sold as "actual 6 x 2.6 mm". They sit 0.4 mm low in their pockets and hold less.

## Sensors and wiring

A hall sensor tells the machine when a bin is slid all the way in, and an IR sensor behind each bin tells it when the bin is full. Every harness plugs into a labelled socket on the electronics tray, so nothing is soldered to the Pi.

| Part | Buy | Qty | What for | Price seen (CAD) |
| --- | --- | --- | --- | --- |
| TCRT5000 IR reflective sensor modules | [DAOKI 5-pack](https://www.amazon.ca/DAOKI-TCRT5000-Infrared-Reflective-Photoelectric/dp/B00XT0PBC0) | 4 (5 in the pack) | bin full | check |
| A3144 hall effect sensors (bare, 3 pins) | [uxcell A3144, 10 pcs](https://www.amazon.ca/uxcell-Terminal-Sensitive-Effect-Switch/dp/B00SWK15ZE) | 4 (10 in the pack) | bin seated | check |
| JST-XH 2.54 mm connectors, pre-crimped, 2 to 6 pins | [XH kit with pre-crimped 22 AWG wire](https://www.amazon.ca/Connector-Pre-Crimped-Silicone-Housing-Adapter/dp/B0FPLS51TM) | 1 kit | plugs for every harness at the tray's patch bar | about 15 to 42 |

The pre-crimped kit means you don't need a crimping tool. Thicker red and black wire for the 5 V runs (18 AWG) is worth having too, if you don't already.

## Before you order

The links come from Amazon.ca search results. Amazon.ca blocks automated page reads, so the listings themselves weren't opened. Prices marked "check" didn't show in the results, and the others are what the results showed today, so they may have changed.

- [ ] Brick plug is 5.5 x 2.1 mm, centre positive, 5 V 10 A
- [ ] Panel jack's thread size matches the back-panel hole
- [ ] Relay module has the high/low trigger jumper (the Pi's 3.3 V pin drives it on HIGH)
- [ ] Button is momentary (not latching), with a 5 V LED ring
- [ ] N20 is the 6 V 60 RPM (or 50 RPM) one with a 3 mm D shaft
- [ ] Magnets are a true 3 mm thick
