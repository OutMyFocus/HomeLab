#!/bin/bash
# Sets up the MTG sorter on a Raspberry Pi, or repairs it. One command, safe to run again
# any time something seems broken: it only changes what's missing or wrong, and never
# touches your collection, card database or training (mtg-sorter/data/).
#
#   On a freshly flashed Pi (user nic, connected to Wi-Fi):
#     curl -fsSL https://raw.githubusercontent.com/OutMyFocus/HomeLab/main/mtg-sorter/deploy/setup.sh | bash
#   On a Pi that already has it:
#     mtg repair        (or: bash ~/HomeLab/mtg-sorter/deploy/setup.sh)
#
# It asks for your password once (for sudo). What it does, in order:
#   1. System packages: git, Python, the Pi camera library, I2C tools
#   2. Turns on I2C (the servo board) and, if the camera isn't seen, its driver
#   3. Gets the code from GitHub (or checks the copy that's there)
#   4. The Python environment and packages
#   5. A starter card database, if there isn't one
#   6. The app service, automatic updates, the Maintenance page's helper, and the `mtg` command
#   7. Starts the app and runs the check-up
set -euo pipefail

USER_NAME=nic
HOME_DIR=/home/$USER_NAME
REPO=$HOME_DIR/HomeLab
APP=$REPO/mtg-sorter
REPO_URL=https://github.com/OutMyFocus/HomeLab.git
CONFIG=/boot/firmware/config.txt
reboot_needed=0

step() { printf '\n\033[1;33m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[32mok\033[0m  %s\n' "$*"; }
note() { printf '    \033[33m!!\033[0m  %s\n' "$*"; }
as_user() { if [ "$(id -un)" = "$USER_NAME" ]; then "$@"; else sudo -u "$USER_NAME" -- "$@"; fi; }

main() {
    if [ "$(id -un)" != "$USER_NAME" ] && [ "$(id -u)" != 0 ]; then
        echo "Run this as $USER_NAME (the services expect the code in $HOME_DIR)." >&2
        exit 1
    fi
    if ! id "$USER_NAME" >/dev/null 2>&1; then
        echo "There's no user called $USER_NAME on this Pi. Flash it again with username $USER_NAME." >&2
        exit 1
    fi
    sudo -v   # ask for the password once, up front

    step "1/7 System packages"
    pkgs=(git python3-venv python3-pip python3-picamera2 rpicam-apps i2c-tools curl)
    missing=()
    for p in "${pkgs[@]}"; do dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p"); done
    if [ ${#missing[@]} -gt 0 ]; then
        sudo apt-get update -q
        sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q "${missing[@]}"
        ok "installed ${missing[*]}"
    else
        ok "all there"
    fi
    for g in adm video i2c gpio systemd-journal; do
        if getent group "$g" >/dev/null && ! id -nG "$USER_NAME" | grep -qw "$g"; then
            sudo usermod -aG "$g" "$USER_NAME"; ok "added $USER_NAME to the $g group"; reboot_needed=1
        fi
    done

    step "2/7 I2C and camera"
    if command -v raspi-config >/dev/null; then
        if [ "$(sudo raspi-config nonint get_i2c)" != 0 ]; then
            sudo raspi-config nonint do_i2c 0; ok "turned I2C on"; reboot_needed=1
        else
            ok "I2C is on"
        fi
    else
        note "raspi-config not found (not Raspberry Pi OS?), skipping I2C"
    fi
    if rpicam-hello --list-cameras 2>&1 | grep -q imx708; then
        ok "camera found (Camera Module 3)"
    elif [ -f "$CONFIG" ] && ! grep -q '^dtoverlay=imx708' "$CONFIG"; then
        # The Pi sometimes misses the Camera Module 3 on its own; naming its driver fixes that.
        sudo cp "$CONFIG" "$CONFIG.before-mtg-setup"
        sudo sed -i 's/^camera_auto_detect=1/camera_auto_detect=0/' "$CONFIG"
        printf '\n[all]\n# Camera Module 3 on both camera ports (added by mtg-sorter setup.sh)\ndtoverlay=imx708\ndtoverlay=imx708,cam0\n' \
            | sudo tee -a "$CONFIG" >/dev/null
        ok "camera not seen, so its driver is now named in $CONFIG (old copy: $CONFIG.before-mtg-setup)"
        reboot_needed=1
    else
        note "no camera seen. Power off and check the ribbon cable (see MAINTENANCE.md, \"Camera not found\")."
    fi

    step "3/7 The code"
    if [ ! -d "$REPO/.git" ]; then
        as_user git clone -q "$REPO_URL" "$REPO"; ok "downloaded to $REPO"
    else
        cd "$REPO"
        as_user git fetch -q origin main || note "couldn't reach GitHub; using the copy that's here"
        branch=$(as_user git rev-parse --abbrev-ref HEAD)
        edits=$(as_user git status --porcelain --untracked-files=no)
        if [ -n "$edits" ]; then
            note "files were changed on the Pi, which stops updates:"
            echo "$edits" | sed 's/^/          /'
            note "the Maintenance page's Fix updates button (or: mtg fix-updates) sets them aside safely"
        elif [ "$branch" != main ]; then
            as_user git checkout -q main && ok "switched from $branch back to main"
        fi
        if [ -z "$edits" ]; then
            as_user git merge -q --ff-only origin/main 2>/dev/null && ok "on the latest main ($(as_user git rev-parse --short HEAD))" \
                || note "couldn't move to the latest main; updates will try again"
        fi
    fi
    cd "$APP"

    step "4/7 Python packages"
    if ! as_user .venv/bin/python -c "import sys" 2>/dev/null; then
        rm -rf .venv
        # --system-site-packages lets it see picamera2, which comes from apt, not pip.
        as_user python3 -m venv --system-site-packages .venv; ok "made the Python environment"
    fi
    as_user .venv/bin/pip install -q --disable-pip-version-check -r requirements.txt
    if as_user .venv/bin/python -c "import cv2, flask, imagehash, numpy" 2>/dev/null; then
        ok "packages installed"
    else
        note "some packages didn't install. The lines above say which."
    fi

    step "5/7 Card database"
    as_user mkdir -p data
    if [ -s data/cards.db ]; then
        ok "data/cards.db is there ($(du -h data/cards.db | cut -f1))"
    else
        note "no card database yet, so fetching two sets to start with (about a minute)"
        as_user .venv/bin/python build_db.py --sets dmu,one
        note "for every card later: cd $APP && .venv/bin/python build_db.py --all  (a few hours)"
    fi

    step "6/7 Services, updates and maintenance tools"
    sudo bash "$APP/deploy/install.sh" | grep -v app-changed || true
    sudo systemctl daemon-reload
    sudo systemctl enable -q mtg-sorter mtg-sorter-update.timer
    sudo systemctl start mtg-sorter-update.timer
    ok "app starts on boot, checks for updates every 5 minutes"
    if sudo -u "$USER_NAME" sudo -n -l /usr/local/sbin/mtg-sorter-admin >/dev/null 2>&1; then
        ok "Maintenance page buttons can restart, update and reboot"
    else
        note "the Maintenance helper's sudo rule didn't take; the page's buttons won't work"
    fi

    step "7/7 Starting the app"
    sudo systemctl restart mtg-sorter
    for _ in $(seq 45); do
        sleep 2
        curl -fsS -m 5 -o /dev/null http://127.0.0.1:5000/ && break
    done
    if curl -fsS -m 5 -o /dev/null http://127.0.0.1:5000/; then
        ok "running"
        echo
        /usr/local/bin/mtg status || true
    else
        note "the app didn't answer. Its last messages:"
        journalctl -u mtg-sorter -n 25 --no-pager | sed 's/^/          /'
    fi

    ip=$(hostname -I | awk '{print $1}')
    printf '\n\033[1mDone.\033[0m Open http://%s.local:5000 or http://%s:5000\n' "$(hostname)" "$ip"
    printf 'The Maintenance page is the wrench button at the top. In SSH, type: mtg\n'
    if [ "$reboot_needed" = 1 ]; then
        printf '\n\033[1;33mReboot once to finish (I2C, camera or group changes):  sudo reboot\033[0m\n'
    fi
}

main "$@"
exit
