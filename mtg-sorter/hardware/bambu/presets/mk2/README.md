# Sorter Mk2 print config

Process presets for Bambu Studio, for the Bambu Lab A1 with the 0.4 mm nozzle. Written by `make_mk2.py`, so they always match the settings inside `MTG_Sorter_Mk2.3mf`.

The 3MF already has these settings on every part. You only need the presets to slice a part on its own, or to check a plate against them.

## Import

1. In Bambu Studio: **File → Import → Import Configs...**
2. Pick all eight `.json` files in this folder and press Open.
3. They show up in the **Process** list under User presets, named `MTG Mk2 - ...`.

## Printer, plate and filament

| Setting | Value |
|---|---|
| Printer | Bambu Lab A1 0.4 nozzle |
| Plate | Textured PEI |
| Filament | Bambu PLA Basic @BBL A1, black; white for the parts marked below |
| Layer height | 0.20 mm (every preset inherits `0.20mm Standard @BBL A1`) |
| On every preset | seam aligned, precise outer wall on, elephant foot compensation 0.15 mm |

## The presets

| Preset | Settings | Parts |
|---|---|---|
| `MTG Mk2 - 1 Panels and covers` | 4 walls, 20% gyroid infill | back_high, back_low, branch_lid, coupon_pieces, coupon_plate, front_cover, lid_back, lid_front, trunk_lid |
| `MTG Mk2 - 2 Frame` | 5 walls, 30% gyroid infill | base_bl, base_br, base_fl, base_fr, fd_motor_lid, liner_back, pca_comb, stop_bar, wall_l00, wall_l01, wall_l02, wall_l10, wall_l11, wall_l12, wall_r00, wall_r01, wall_r02, wall_r10, wall_r11, wall_r12 |
| `MTG Mk2 - 3 Frame, brim` | 5 walls, 30% gyroid infill, 5 mm outer brim | bin, col_front, door, drawer, fd_hopper |
| `MTG Mk2 - 4 Frame, tree supports` | 5 walls, 30% gyroid infill, tree supports (auto, 35 degrees) | carriage1, carriage2, etray, fd_stand |
| `MTG Mk2 - 5 Frame, brim, tree supports` | 5 walls, 30% gyroid infill, 5 mm outer brim, tree supports (auto, 35 degrees) | cam_arch, lv1_frame, lv2_frame, scan_carrier |
| `MTG Mk2 - 6 Solid` | 4 walls, 100% zig-zag infill | cam_hood, fd_roller, key, lever |
| `MTG Mk2 - 7 Solid, brim` | 4 walls, 100% zig-zag infill, 5 mm outer brim | fd_shoe, lightbar |
| `MTG Mk2 - 8 Scan bed, ironed` | 4 walls, 25% gyroid infill, 7 top layers, top surface ironed | scan_bed |

## Plate by plate

| Plate | Colour | Presets on it |
|---|---|---|
| 01 Fit coupon - print first, set fit.scad | black | 1 Panels and covers |
| 02 Base front-left, front-right | black | 2 Frame |
| 03 Base back-left, back-right | black | 2 Frame |
| 04 Right wall, front bottom + 10 keys | black | 2 Frame; 6 Solid |
| 05 Right wall, back bottom + 10 keys | black | 2 Frame; 6 Solid |
| 06 Right wall, front middle + 2 trunk lids | black | 1 Panels and covers; 2 Frame |
| 07 Right wall, back middle + 2 trunk lids | black | 1 Panels and covers; 2 Frame |
| 08 Right wall, front top | black | 2 Frame |
| 09 Right wall, back top | black | 2 Frame |
| 10 Left wall, front bottom + 8 keys | black | 2 Frame; 6 Solid |
| 11 Left wall, back bottom + 2 feed lids | black | 1 Panels and covers; 2 Frame |
| 12 Left wall, front middle + 2 trunk lids | black | 1 Panels and covers; 2 Frame |
| 13 Left wall, back middle | black | 2 Frame |
| 14 Left wall, front top | black | 2 Frame |
| 15 Left wall, back top | black | 2 Frame |
| 16 Bins x4 (WHITE, brim) | white | 3 Frame, brim |
| 17 Level 2 frame (tree supports) | black | 5 Frame, brim, tree supports |
| 18 Level 1 frame (tree supports) | black | 5 Frame, brim, tree supports |
| 19 Pushers, levers, liners, stop bar | black | 2 Frame; 3 Frame, brim; 4 Frame, tree supports; 6 Solid |
| 20 Trapdoors x2, drawer (WHITE) | white | 3 Frame, brim |
| 21 Scan carrier (tree supports) | black | 5 Frame, brim, tree supports |
| 22 Scan bed, light bars (WHITE) | white | 7 Solid, brim; 8 Scan bed, ironed |
| 23 Camera arch and hood (tree supports) | black | 5 Frame, brim, tree supports; 6 Solid |
| 24 Feeder stand (tree supports), motor lid | black | 2 Frame; 4 Frame, tree supports |
| 25 Feeder magazine, shoe, roller | black | 3 Frame, brim; 6 Solid; 7 Solid, brim |
| 26 Electronics tray (tree supports), comb | black | 2 Frame; 4 Frame, tree supports |
| 27 Front cover | black | 1 Panels and covers |
| 28 Lid, front half | black | 1 Panels and covers |
| 29 Lid, back half | black | 1 Panels and covers |
| 30 Back panel, lower | black | 1 Panels and covers |
| 31 Back panel, upper | black | 1 Panels and covers |

Supports are only on where the table says so. Every other part prints without them.
