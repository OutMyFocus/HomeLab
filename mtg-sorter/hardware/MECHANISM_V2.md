# Mechanism v2: new feeder, scan bed stop and door carriers

This replaces the parts that went wrong on the first test run:

| Problem | Cause | v2 fix |
|---|---|---|
| The roller didn't touch the cards | It only poked 0.8 mm above the hopper floor, fixed in place | Two O-ring wheels on a **hinged arm**. A rubber band pushes them up into the stack, and a stop keeps them 2.5 mm proud |
| Cards flew past the stop pins | Two thin pins, only 2.4 mm tall | A **stop gate**: four teeth, 8 mm tall, across the whole card, held at both ends |
| Servos got hot, and the tray couldn't tilt fully | At 25° the trapdoor servos dipped 4 mm into `bridge_front` | **Door carriers** with the servos turned to point inwards. They clear the bridge at 25° (checked in CAD) |

Everything else stays as it is: the enclosure, bridge, bed walls, chute tray, trapdoors, tilt
bracket and wiring. The feeder keeps the same footprint on the bridge.

![Side cut-away: hopper and wheel on the right, card resting on the stop teeth at the front of the bed](img/v2/mechanism_v2_side.png)

![Stop gate turned down: the teeth swing forward under the bed's front edge and the card slides into the chute](img/v2/stop_gate_down.png)

## Print

Open **`bambu/MTG_Sorter_Feeder_And_Bed_v2.3mf`** with **File > Open Project** (not Import).
The settings are already applied. There are five plates:

| Plate | Parts | Filament |
|---|---|---|
| 1 | feeder stand (with brim) | black |
| 2 | feeder hopper (with brim) | black |
| 3 | feeder arm, roller (100% infill), gate, weight | black |
| 4 | scan bed plate | **white** |
| 5 | stop gate, gate bearing, both door carriers | black |

No supports anywhere. You can stop using these old parts: `pin_rocker`, the old roller, hopper,
gate and stand, and the old door carriers.

## Bits you need

- A small rubber band, about **4 cm long lying flat**. A 40–50 mm O-ring from the kit works too.
- One **1.9 mm thick O-ring** from the kit (any size), cut open into a strip. This is the gate's rubber pad.
- Coins or nuts for the weight plate (2 loonies, quarters or M8 nuts per pocket).
- Screws: 2× M3 × 8 (arm hinge), 1× M3 × 12 (thumb screw), 2× M3 × 8 (gate lock, as before),
  2× M2 × 6 (motor pinch and gate bearing).
- The two 3 mm O-rings for the wheels (20x3 or 22x3), as before.

## Feeder

1. **Wheels.** Stretch one 3 mm O-ring into each groove on the roller.
2. **Motor into the arm.** Slide the N20 into the square tunnel on the arm from the outside,
   shaft first, until the gearbox stops against the end wall. Snug the M2 screw in the side of
   the tunnel to pinch it. Don't overtighten it.
3. **Roller onto the motor.** Line up the flat in the roller's hole with the flat on the shaft
   and press it on. The stub at the other end drops into the slot in the arm's left plate.
4. **Arm into the stand.** With the hopper off, lower the arm in from the top. The motor slides
   down the open slot in the right wall. Put an M3 × 8 through each side wall into the arm. The
   arm should swing up and down freely.
5. **Rubber band.** Loop it under the bar at the bottom back of the stand (through the notch)
   and over the arm's tail tongue. The bump at the end of the tongue keeps it on. With the
   band on, the wheels should push up firmly when you press them down.
6. **Hopper on**, onto the four pegs. The O-rings now stand about 2.5 mm above the floor. Press
   them down with a finger and they should spring back.
7. **Gate.** Press the cut 1.9 mm O-ring into the groove under the gate's bottom edge (a dab of
   glue helps). Hang the gate on the front wall with the two lock screws loose, and drive the
   M3 × 12 down through the tab until its tip rests on the little shelf behind the gate.
   Slip one card under the gate and turn the thumb screw until the card just drags when you
   pull it. Tighten the lock screws and take the card out.
8. **Stack and weight.** Load the cards face up and put the weight plate on top with coins in it.

Wiring is the same as before. If the wheels push cards **backwards**, swap the motor's two wires.

## Scan bed stop gate

1. Take out the old pin rocker and slide the old bed plate out of its grooves. Leave the pin
   servo where it is.
2. **Gate bearing.** Push it down over the **right** end of the tilt bracket, between the bracket
   and the right bed wall, with its pin pointing to the middle. Put an M2 × 6 through its back
   jaw into the bracket.
3. **Horn.** Screw the double-arm horn to the stop gate's left plate, using the two horn holes
   nearest the hub, as with the old rocker.
4. Centre the pin servo (90), then fit the gate. The right plate's hole goes over the bearing pin
   and the horn goes onto the servo shaft, with the teeth pointing up. Fit the horn's centre screw.
5. On the Machine page, move **Pins** to about 50 so the teeth are down, then slide the new white
   bed plate down its grooves. Move Pins back to 90: the four teeth come up through the slots,
   about 8 mm tall.

## Door carriers

Unscrew the chute and swap each door carrier for the new one. The servo goes in the same way,
except its body now points in towards the middle of the tray instead of out past the door. The
horn still slides up into the door's fork. The chute itself doesn't change.

## Servo angles to save on the Machine page

| Part | Positions | Why |
|---|---|---|
| Pins (the stop gate) | up **90**, down **50** | 40° drops the teeth well clear. CAD shows no contact from 6° past up to 44° down |
| Chute | centre 90, left **68**, right **112** | 22° each way. The servos now clear the bridge even at 25°, but 22° leaves about 2.5 mm |
| Doors | unchanged | |

Press **Save** after each one. If cards stick in the tray at 22°, try 24°.

## If something's off

| What you see | Try |
|---|---|
| Two cards come out | Lower the gate a quarter turn of the thumb screw |
| Nothing comes out, wheels spin | Add a second wrap of the rubber band, or more coins on the weight |
| Card lands crooked on the bed | The funnel at the top of the bed should straighten it. If not, check that both wheels touch the card |
| The pin servo buzzes with the teeth up | The bar is pressing on the bed's underside: save "up" a few degrees lower (towards 50) |
