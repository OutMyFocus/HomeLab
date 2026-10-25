#!/bin/sh
# Regenerate every STL for the enclosure build. Run it after changing dr_w / dr_h / dr_l
# (the drawer size) in enclosure.scad, because almost every panel follows from it.
#   sh export_enclosure.sh
cd "$(dirname "$0")"
for p in post side fascia light_bar back floor_fl floor_fr floor_bl floor_br deck_fl deck_fr deck_bl deck_br \
         divider bridge_front bridge_back leg splice tower tower_lid post_sleeve head_cover; do
  openscad -q -o "stl/enc_$p.stl" -D "epart=\"$p\"" enclosure.scad
done
# the bed walls starting on the bridge, and the feeder stand that sits on it
openscad -q -o stl/bed_chute_bed_side_left_enclosure.stl  -D 'part="bed_side_left"'  -D 'wall_z0=111' bed_chute.scad
openscad -q -o stl/bed_chute_bed_side_right_enclosure.stl -D 'part="bed_side_right"' -D 'wall_z0=111' bed_chute.scad
openscad -q -o stl/feeder_stand_mid.stl -D 'part="stand"' -D 'stand_h=92' feeder_test.scad
openscad -q -o stl/sorter_drawer.stl       -D 'part="drawer"' sorter_drawer.scad
openscad -q -o stl/sorter_drawer_front.stl -D 'part="front"'  sorter_drawer.scad
