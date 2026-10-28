#!/bin/sh
# One-time Pi setup for the single power button (hardware/POWER.md). Run with sudo, then reboot:
#   sudo sh deploy/power-setup.sh
# Safe to run again: it only adds what isn't there yet.
set -e
CFG=/boot/firmware/config.txt
[ -f "$CFG" ] || CFG=/boot/config.txt

add_line() {   # add $1 to config.txt under a final [all] section, unless it's already there
  if grep -qxF "$1" "$CFG"; then
    echo "already set: $1"
  else
    tail -n 5 "$CFG" | grep -qxF "[all]" || printf '\n[all]\n' >> "$CFG"
    echo "$1" >> "$CFG"
    echo "added: $1"
  fi
}

cp "$CFG" "$CFG.bak-power"
# the 5 V supply can't tell the Pi it's good for 5 A; without this USB is capped at 0.6 A
add_line "usb_max_current_enable=1"
# the power button's LED ring, on GPIO22 (pin 15): on while the Pi runs
add_line "dtoverlay=gpio-led,gpio=22,label=power,trigger=default-on"

# bootloader: switch everything off after a shutdown (the button wakes it)
EE=$(mktemp)
rpi-eeprom-config > "$EE"
if grep -q '^POWER_OFF_ON_HALT=1' "$EE"; then
  echo "already set: POWER_OFF_ON_HALT=1"
else
  sed -i '/^POWER_OFF_ON_HALT=/d' "$EE"
  echo "POWER_OFF_ON_HALT=1" >> "$EE"
  rpi-eeprom-config --apply "$EE"
  echo "added: POWER_OFF_ON_HALT=1 (bootloader)"
fi
rm -f "$EE"
echo "Done. Reboot to apply: sudo reboot"
