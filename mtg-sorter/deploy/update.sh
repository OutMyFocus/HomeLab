#!/bin/bash
# Keeps the Pi on the latest main from GitHub. Run every few minutes by mtg-sorter-update.timer.
# When main has new commits it pulls them, reinstalls Python packages if requirements.txt changed,
# reinstalls the service files if they changed, and restarts the app. Does nothing otherwise.
# Your card database and collection (mtg-sorter/data/) aren't in git, so a pull never touches them.
set -euo pipefail

REPO=/home/nic/HomeLab
APP=$REPO/mtg-sorter
as_nic() { runuser -u nic -- "$@"; }

cd "$REPO"
as_nic git fetch -q origin main
old=$(as_nic git rev-parse HEAD)
new=$(as_nic git rev-parse origin/main)
[ "$old" = "$new" ] && exit 0

# Fast-forward only: if someone edited files on the Pi, stop rather than overwrite them.
as_nic git checkout -q main
as_nic git merge -q --ff-only origin/main
echo "Updated ${old:0:7} -> ${new:0:7}"

changed() { ! as_nic git diff --quiet "$old" "$new" -- "$@"; }

if changed mtg-sorter/requirements.txt; then
    echo "requirements.txt changed, installing packages"
    as_nic "$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"
fi

if changed mtg-sorter/deploy/*.service mtg-sorter/deploy/*.timer; then
    echo "Service files changed, reinstalling them"
    cp "$APP"/deploy/*.service "$APP"/deploy/*.timer /etc/systemd/system/
    systemctl daemon-reload
fi

systemctl restart mtg-sorter
