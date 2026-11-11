# Shopping list (Amazon.ca)

Everything for the scan station, feeder, scan bed and chute, beyond the Bambu Lab A1.
Each link opens an Amazon.ca search: pick a well-reviewed listing that matches the
details. Prices are rough, in CAD.

**Total: roughly $400–450**, most of it the Pi kit and camera. To spread it out, buy in
two rounds:

- **Round 1, the feeder test (about $55):** items 6, 11, 12, 14 and 19. Ordered 2026-10-22. With the printer,
  that's enough to build and test the feeder.
- **Round 2, the camera and sorting:** everything else.
- **Round 3, one plug and one power button (about $80):** items 22–27, see
  [`hardware/POWER.md`](hardware/POWER.md).

Ticked items are what Nic has ordered (checked against the Amazon orders on 2026-10-28);
the brand in brackets is the listing that was bought.

## Brain and camera

- [x] 1. [Raspberry Pi 5 4GB starter kit](https://www.amazon.ca/s?k=raspberry+pi+5+4gb+starter+kit): includes the power supply, a case with a fan, and a microSD card. CanaKit's kits are a safe pick. About $150. *(Nic has a bare Pi 5 board, already set up and running.)*
- [x] 2. [Raspberry Pi Camera Module 3](https://www.amazon.ca/s?k=raspberry+pi+camera+module+3): the standard one, not Wide or NoIR. About $35.
- [ ] 3. [Raspberry Pi 5 camera cable, 300 mm](https://www.amazon.ca/s?k=raspberry+pi+5+camera+cable+300mm): the cable that comes with the camera doesn't fit the Pi 5. About $10. *(Wonrabai 22-to-15 pin, 0.5 m, plus a uxcell 15-pin FFC extension board.)*

## Moving parts

- [x] 4. [MG90S servo, 4-pack](https://www.amazon.ca/s?k=mg90s+servo+4+pack): metal gears. One each for the stop pins and the chute tilt, two for the trapdoors. About $20. *(Miuzei.)*
- [x] 5. [PCA9685 servo driver board](https://www.amazon.ca/s?k=pca9685+16+channel+servo+driver): lets the Pi run all four servos. About $12. *(HUAREW 2-pack, arriving 2026-10-30; one is a spare.)*
- [x] 6. [N20 gear motor, 6 V, 150 RPM](https://www.amazon.ca/s?k=n20+gear+motor+6v+150rpm): needs a 3 mm D-shaft. Turns the feeder roller. Get a 2-pack for a spare. About $15. *(MECCANIXITY 6 V 150 RPM 2-pack.)*
- [x] 7. [DRV8833 motor driver](https://www.amazon.ca/s?k=drv8833+motor+driver): lets the Pi switch the feeder motor on and off. About $10. *(ACEIRMC 8-pack; the header pins come loose and need soldering. Max 10.8 V, so 5 V is right.)*

## Power and light

- [x] 8. [5 V 4 A power adapter, 5.5 × 2.1 mm plug](https://www.amazon.ca/s?k=5v+4a+power+adapter+5.5x2.1): powers the servos and LEDs separately, so the Pi doesn't crash. About $15. *(Facmogu 5 V 4 A. Too small to run the Pi and the servos together; keep it as the bench supply for testing servos. The finished machine uses item 22.)*
- [x] 9. [DC barrel jack screw-terminal adapters](https://www.amazon.ca/s?k=dc+barrel+jack+screw+terminal+adapter+5.5x2.1): about $8. *(ANLINK 20-pack, female, 5.5 × 2.1.)*
- [x] 10. [5 V USB LED strip, cool white, 6000K](https://www.amazon.ca/s?k=5v+usb+led+strip+cool+white+6000k): 8–10 mm wide. Not warm white: yellow light makes cards harder to recognize. About $15. *(Aclorol 1 m COB, 6000K, with an inline dimmer.)*

## Small hardware

- [x] 11. [Metric nitrile O-ring assortment](https://www.amazon.ca/s?k=metric+nitrile+o+ring+assortment+kit): check it includes **20 mm inside diameter × 3 mm thick**, the feeder roller's tyres. About $15. *(ZDBB 1540-piece kit. It's sized by outside diameter × thickness: use the **25 × 3.1** rings (19 mm inside, snug) or **27 × 3.1** (21 mm inside, looser).)*
- [x] 12. [M2 + M3 self-tapping screw assortment](https://www.amazon.ca/s?k=m2+m3+self+tapping+screw+assortment): servos, camera, brackets, hinge pins. About $15. *(MNSYJK M2–M3 500-piece, arriving 2026-10-30.)*
- [x] 13. [Dupont jumper wire kit](https://www.amazon.ca/s?k=dupont+jumper+wire+kit): about $10. *(ELEGOO 120-piece, 20 cm.)*
- [x] 14. [Small zip ties](https://www.amazon.ca/s?k=small+zip+ties): about $5. *(Fuctok 150-piece.)*

## Filament

You're getting 2 rolls of Bambu PLA Tough with the printer. On top of those:

- [x] 15. [White PLA, 1 kg](https://www.amazon.ca/s?k=white+pla+filament+1.75mm+1kg): the scan bed and scan station base, which the camera sees. About $25.
- [x] 16. [Black PLA, 1 kg](https://www.amazon.ca/s?k=black+pla+filament+1.75mm+1kg): the frame, walls and bins. Get 2 if you're printing the bins. About $25 each. *(Elegoo white + black.)*

## Handy to have

- [ ] 17. [Digital calipers](https://www.amazon.ca/s?k=digital+calipers): for measuring parts and checking fits. About $20.
- [ ] 18. [99% isopropyl alcohol](https://www.amazon.ca/s?k=99+isopropyl+alcohol): wipe the build plate so prints stick. About $10.
- [x] 19. [4×AA battery holder with switch](https://www.amazon.ca/s?k=4+aa+battery+holder+with+switch): test the feeder before the Pi is set up. About $5.

## Soldering (only if you solder the header pins)

The small motor driver boards often come with their header pins loose. You already have an iron.

- [ ] 20. [Rosin-core solder, 63/37, 0.8 mm](https://www.amazon.ca/s?k=63%2F37+rosin+core+solder+0.8mm): easiest to work with for header pins. Contains lead, so wash your hands after. Lead-free (SAC305, 0.8 mm) works too but needs a hotter iron (~350 °C). About $12–18.
- [ ] 21. [No-clean flux pen](https://www.amazon.ca/s?k=mg+chemicals+no+clean+flux+pen): MG Chemicals 8341 or similar. A dab on each pin before soldering, nothing to clean off after. About $12–15.

## One plug, one power button

See [`hardware/POWER.md`](hardware/POWER.md) for why and how these go together.

- [ ] 22. [5 V 10 A power supply, 5.5 × 2.1 mm plug](https://www.amazon.ca/s?k=5v+10a+power+supply+5.5x2.1): replaces item 8 for the finished machine. Runs everything: Pi, servos, motor, light. Get the desktop "brick" kind with a separate wall cord, and make sure the plug is **5.5 × 2.1** (many 10 A ones are 5.5 × 2.5; then buy the 2.5 version of item 23 instead). About $25.
- [ ] 23. [Panel-mount DC jack, 5.5 × 2.1 mm, with wires](https://www.amazon.ca/s?k=panel+mount+dc+jack+5.5x2.1+with+wire): the one power inlet in the back panel. The DC-022B kind needs an 11 mm hole, which is what the back panel has. Pre-wired ones are solder-free. About $10 for a pack.
- [ ] 24. [16 mm momentary metal push button with LED ring, 3–6 V](https://www.amazon.ca/s?k=16mm+momentary+metal+push+button+led+ring+5v): the power button on the deck. Must say **momentary** (self-reset), not latching. Pick the 3 V, 3–6 V or 5 V version, any colour. About $10.
- [ ] 25. [USB-C male plug to screw terminal adapter](https://www.amazon.ca/s?k=usb+c+male+screw+terminal+adapter): feeds the Pi from the 5 V supply without soldering. About $10 for a pack.
- [ ] 26. [Wago 221 lever connectors, 5-way](https://www.amazon.ca/s?k=wago+221-415): two of them, one for +5 V and one for ground, so every board gets its own wire from one point. About $12.
- [ ] 27. [18 AWG silicone wire, red and black](https://www.amazon.ca/s?k=18+awg+silicone+wire+red+black): for the power wires (the Dupont jumpers are too thin to carry the servo and Pi current). About $12.

## Already have

- [x] Bambu Lab A1 + AMS Lite
- [x] 2 rolls Bambu PLA Tough
