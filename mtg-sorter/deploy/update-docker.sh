#!/bin/bash
# Keeps the Pi on the newest Docker image, the same one the server (tower) runs. update.sh
# hands over to this once the Pi is switched to Docker (mtg docker on; see PI_DOCKER.md), so
# it runs every 5 minutes from mtg-sorter-update.timer and from the Update now button.
#
# Each run:
#   1. Brings the Pi's copy of the repo up to date, for the system files only (services,
#      maintenance helper, `mtg`), and installs them. The app itself comes from the image.
#   2. Pulls ghcr.io/outmyfocus/mtg-sorter:latest. If it's new, tags it mtg-sorter:run and
#      restarts the app with it.
#   3. Checks the app answers. If it doesn't, goes back to the image that worked and skips
#      the new one until a newer one comes out.
# What happened is written to data/update_status.json for the Maintenance page.
set -euo pipefail

REPO=/home/nic/HomeLab
APP=$REPO/mtg-sorter
IMAGE=ghcr.io/outmyfocus/mtg-sorter:latest
RUN=mtg-sorter:run
STATUS=$APP/data/update_status.json
BAD=$APP/data/update_bad_image
as_nic() { runuser -u nic -- "$@"; }

image_id() { docker image inspect -f '{{.Id}}' "$1" 2>/dev/null || true; }
image_version() {
    docker image inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$1" 2>/dev/null \
        | sed -n 's/^MTG_VERSION=//p' | cut -c1-7
}

status() {
    local msg=${2//\\/\\\\}; msg=${msg//\"/\\\"}
    as_nic mkdir -p "$APP/data"
    printf '{"result": "%s", "message": "%s", "time": "%s", "commit": "%s"}\n' \
        "$1" "$msg" "$(date -Iseconds)" "$(image_version "$RUN")" \
        | as_nic tee "$STATUS.tmp" >/dev/null
    as_nic mv "$STATUS.tmp" "$STATUS"
}

app_answers() {
    for _ in $(seq 45); do
        sleep 2
        if curl -fsS -m 5 -o /dev/null http://127.0.0.1:5000/; then
            return 0
        fi
    done
    return 1
}

main() {
    # 1. System files. A failed pull here only means older helper scripts, so carry on.
    if as_nic git -C "$REPO" fetch -q origin main 2>/dev/null; then
        as_nic git -C "$REPO" merge -q --ff-only origin/main 2>/dev/null \
            || echo "Couldn't move the repo to the latest main (edits made on the Pi?); system files stay as they are"
    fi
    installed=$(bash "$APP/deploy/install.sh" || echo "install.sh failed")
    [ -n "$installed" ] && echo "$installed"

    # 2. The image.
    old=$(image_id "$RUN")
    if ! docker pull -q "$IMAGE" >/dev/null; then
        status failed "Couldn't download the newest image. Is the internet up?"
        exit 1
    fi
    new=$(image_id "$IMAGE")
    if [ "$old" = "$new" ]; then
        [[ $installed == *app-changed* ]] && systemctl restart mtg-sorter
        systemctl is-active -q mtg-sorter || systemctl start mtg-sorter
        status "up to date" "Up to date (same image as the server, version $(image_version "$RUN"))."
        exit 0
    fi
    if [ -e "$BAD" ] && [ "$(cat "$BAD")" = "$new" ] && [ ! -e /run/mtg-sorter-force-update ]; then
        exit 0   # this image already failed to start; wait for a newer one (or Update now)
    fi
    rm -f /run/mtg-sorter-force-update

    docker tag "$IMAGE" "$RUN"
    systemctl restart mtg-sorter
    if app_answers; then
        rm -f "$BAD"
        [ -n "$old" ] && docker image rm "$old" >/dev/null 2>&1 || true   # free the space
        status updated "Updated to version $(image_version "$RUN"), the same image as the server."
        return 0
    fi

    # 3. The new image doesn't start: go back to the one that did.
    echo "The new image didn't start." >&2
    journalctl -u mtg-sorter -n 30 --no-pager >&2 || true
    echo "$new" | as_nic tee "$BAD" >/dev/null
    if [ -n "$old" ]; then
        docker tag "$old" "$RUN"
        systemctl restart mtg-sorter
        status "rolled back" "The newest image didn't start, so the Pi went back to version $(image_version "$RUN"). It tries again when there's a newer one."
    else
        status failed "The image didn't start. See the app log."
    fi
    exit 1
}

main "$@"
exit
