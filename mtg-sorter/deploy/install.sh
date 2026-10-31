#!/bin/bash
# Puts the sorter's system files in place: the app and update services, the maintenance
# helper and its sudo rule, and the `mtg` command. Safe to run any number of times: it only
# copies files that changed. Run as root (update.sh runs it every 5 minutes; setup.sh too).
# Prints "app-changed" if the app's service file changed, so the caller restarts the app.
set -euo pipefail

APP=/home/nic/HomeLab/mtg-sorter
D=$APP/deploy
units_changed=0

# put SOURCE DEST MODE: copy if different, owned by root.
put() {
    if ! cmp -s "$1" "$2"; then
        install -o root -g root -m "$3" "$1" "$2"
        echo "Installed $2"
        return 0
    fi
    return 1
}

for unit in mtg-sorter.service mtg-sorter-update.service mtg-sorter-update.timer; do
    if put "$D/$unit" "/etc/systemd/system/$unit" 644; then
        units_changed=1
        [ "$unit" = mtg-sorter.service ] && echo app-changed
    fi
done
put "$D/mtg-sorter-admin" /usr/local/sbin/mtg-sorter-admin 755 || true
put "$D/mtg" /usr/local/bin/mtg 755 || true

# A broken sudoers file can lock sudo for everyone, so check it before it goes in.
if ! cmp -s "$D/mtg-sorter.sudoers" /etc/sudoers.d/mtg-sorter; then
    if visudo -cqf "$D/mtg-sorter.sudoers"; then
        install -o root -g root -m 440 "$D/mtg-sorter.sudoers" /etc/sudoers.d/mtg-sorter
        echo "Installed /etc/sudoers.d/mtg-sorter"
    else
        echo "mtg-sorter.sudoers didn't pass visudo's check, so it wasn't installed" >&2
    fi
fi

if [ "$units_changed" = 1 ]; then
    systemctl daemon-reload
fi
