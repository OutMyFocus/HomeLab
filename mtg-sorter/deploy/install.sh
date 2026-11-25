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

# Once the Pi is switched to the Docker image (mtg docker on, see PI_DOCKER.md), the app's
# service runs the container instead, and a small bridge lets the app ask for root jobs.
docker_mode=0
[ -e /etc/mtg-sorter/docker ] && docker_mode=1
app_unit=mtg-sorter.service
[ "$docker_mode" = 1 ] && app_unit=mtg-sorter-docker.service

if put "$D/$app_unit" /etc/systemd/system/mtg-sorter.service 644; then
    units_changed=1
    echo app-changed
fi
for unit in mtg-sorter-update.service mtg-sorter-update.timer; do
    put "$D/$unit" "/etc/systemd/system/$unit" 644 && units_changed=1
done
put "$D/mtg-sorter-admin" /usr/local/sbin/mtg-sorter-admin 755 || true
if [ "$docker_mode" = 1 ]; then
    for unit in mtg-sorter-host.path mtg-sorter-host.service; do
        put "$D/$unit" "/etc/systemd/system/$unit" 644 && units_changed=1
    done
    put "$D/mtg-sorter-host" /usr/local/sbin/mtg-sorter-host 755 || true
fi
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
if [ "$docker_mode" = 1 ] && ! systemctl is-enabled -q mtg-sorter-host.path 2>/dev/null; then
    systemctl enable --now mtg-sorter-host.path
fi
