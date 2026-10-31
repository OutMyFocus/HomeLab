#!/bin/sh
# Regenerate every STL for the enclosure build. Run it after changing anything in the dr_*
# block (the drawer size) in enclosure.scad, because almost every panel follows from it.
#   sh export_enclosure.sh
cd "$(dirname "$0")"
for p in post_front post_front_r post_back side fascia_l fascia_m fascia_r light_bar back_l back_r \
         floor_fl floor_fr floor_bl floor_br deck_fl deck_fr deck_bl deck_br \
         divider bridge_front bridge_back leg leg_offset splice tower tower_lid post_sleeve head_cover; do
  openscad -q -o "stl/enc_$p.stl" -D "epart=\"$p\"" enclosure.scad
done
# the bed walls starting on the bridge, and the feeder stand that sits on it
openscad -q -o stl/bed_chute_bed_side_left_enclosure.stl  -D 'part="bed_side_left"'  -D 'wall_z0=111' bed_chute.scad
openscad -q -o stl/bed_chute_bed_side_right_enclosure.stl -D 'part="bed_side_right"' -D 'wall_z0=111' bed_chute.scad
openscad -q -o stl/feeder_stand_mid.stl -D 'part="stand"' -D 'stand_h=96' -D 'bed_cut=true' feeder_test.scad
# the drawers themselves come from the Card Catalog 3MF (MakerWorld 3016550), not from here
