#!/bin/bash
# Switches the Pi between running the app from its git copy (the old way) and running the
# same Docker image as the server (tower). Run as root:
#   mtg docker on     (or: sudo bash use-docker.sh on)
#   mtg docker off    back to the git copy
# Cards, settings and saved servo angles stay in the same data folder either way.
# What happened goes to the journal: journalctl -u mtg-sorter-switch
set -euo pipefail

APP=/home/nic/HomeLab/mtg-sorter
IMAGE=ghcr.io/outmyfocus/mtg-sorter:latest
MARK=/etc/mtg-sorter/docker

answers() {
    for _ in $(seq 60); do
        sleep 2
        curl -fsS -m 5 -o /dev/null http://127.0.0.1:5000/ && return 0
    done
    return 1
}

case "${1:-}" in
on)
    if ! command -v docker >/dev/null; then
        echo "Installing Docker (a few minutes)..."
        apt-get update -q
        DEBIAN_FRONTEND=noninteractive apt-get install -y -q docker.io
    fi
    systemctl enable --now docker
    usermod -aG docker nic   # so `mtg status` can read the image's version
    echo "Downloading the app's image (the first time takes a few minutes)..."
    docker pull "$IMAGE"
    docker tag "$IMAGE" mtg-sorter:run
    mkdir -p /etc/mtg-sorter /home/nic/HomeLab/mtg-sorter/data/host
    touch "$MARK"
    bash "$APP/deploy/install.sh"       # the Docker service, the job bridge
    systemctl daemon-reload
    systemctl restart mtg-sorter
    if answers; then
        echo "Done: the Pi now runs the Docker image. Updates come every 5 minutes, the same as the server's."
    else
        echo "The app in Docker didn't answer within 2 minutes. Going back to the git copy." >&2
        journalctl -u mtg-sorter -n 40 --no-pager >&2 || true
        bash "$0" off
        exit 1
    fi ;;
off)
    rm -f "$MARK"
    systemctl disable --now mtg-sorter-host.path 2>/dev/null || true
    bash "$APP/deploy/install.sh"       # puts the git copy's service back
    chown -R nic:nic "$APP/data"        # files the container wrote as root
    systemctl daemon-reload
    systemctl restart mtg-sorter
    echo "Back to running from the git copy." ;;
*)
    echo "use-docker.sh on|off" >&2; exit 2 ;;
esac
