#!/bin/sh
# Regenerate every STL for the enclosure build. Run it after changing anything in the dr_*
# block (the drawer size) in enclosure.scad, because almost every panel follows from it.
#   sh export_enclosure.sh
cd "$(dirname "$0")"
for p in post_front post_front_r post_back side fascia_l fascia_m fascia_r light_bar back_l back_r \
         floor_fl floor_fr floor_bl floor_br deck_fl deck_fr deck_bl deck_br \
         divider bridge_front bridge_cap bridge_back leg leg_offset splice tower tower_lid post_sleeve head_cover; do
  openscad -q --export-format binstl -o "stl/enc_$p.stl" -D "epart=\"$p\"" enclosure.scad
done
# the bed walls starting on the bridge, and the feeder stand that sits on it
openscad -q -o stl/bed_chute_bed_side_left_enclosure.stl  -D 'part="bed_side_left"'  -D 'wall_z0=111' bed_chute.scad
openscad -q -o stl/bed_chute_bed_side_right_enclosure.stl -D 'part="bed_side_right"' -D 'wall_z0=111' bed_chute.scad
# the feeder (v2: spring-loaded roller arm, see feeder.scad) that stands on the bridge
openscad -q --export-format binstl -o stl/feeder_stand_mid.stl -D 'part="stand"' feeder.scad
for p in arm roller hopper gate weight weight_solid; do
  openscad -q --export-format binstl -o "stl/feeder_$p.stl" -D "part=\"$p\"" feeder.scad
done
# scan bed v2 (stop gate), and chute v3 (solid bomb bay: tray, doors on journals, cranks and links)
for p in bed_plate bed_plate3 stop_gate stop_gate3 gate_bearing chute3 door3 door3_left door_crank3 door_crank3_left \
         servo_crank3 servo_crank3_left door_link3 hinge_frame3; do
  openscad -q --export-format binstl -o "stl/bed_chute_$p.stl" -D "part=\"$p\"" bed_chute.scad
done
# the drawers themselves come from the Card Catalog 3MF (MakerWorld 3016550), not from here
# holder + bezel for the servo-power barrel jack in the back panel's power cut-out
for p in holder bezel; do
  openscad -q --export-format binstl -o "stl/dc_jack_$p.stl" -D "part=\"$p\"" dc_jack_holder.scad
done
