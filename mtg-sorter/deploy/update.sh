#!/bin/bash
# Keeps the Pi on the latest main from GitHub. Run every 5 minutes by mtg-sorter-update.timer,
# and by the Update now button on the app's Maintenance page.
#
# Each run:
#   1. Makes sure the system files (services, maintenance helper, `mtg` command) are installed.
#   2. If main has new commits, pulls them, reinstalls Python packages if requirements.txt
#      changed, and restarts the app.
#   3. Checks the app answers afterwards. If the new version doesn't start, it goes back to
#      the version that worked and skips that commit until a newer one arrives.
# What happened is written to data/update_status.json for the Maintenance page.
# Your card database and collection (mtg-sorter/data/) aren't in git, so a pull never touches them.
set -euo pipefail

REPO=/home/nic/HomeLab
APP=$REPO/mtg-sorter
STATUS=$APP/data/update_status.json
BAD=$APP/data/update_bad_commit
FORCE=/run/mtg-sorter-force-update
as_nic() { runuser -u nic -- "$@"; }

# Records the result for the Maintenance page: status RESULT MESSAGE
status() {
    local msg=${2//\\/\\\\}; msg=${msg//\"/\\\"}
    as_nic mkdir -p "$APP/data"
    printf '{"result": "%s", "message": "%s", "time": "%s", "commit": "%s"}\n' \
        "$1" "$msg" "$(date -Iseconds)" "$(as_nic git -C "$REPO" rev-parse --short HEAD)" \
        | as_nic tee "$STATUS.tmp" >/dev/null
    as_nic mv "$STATUS.tmp" "$STATUS"
}

# Waits up to 90 seconds for the app to answer (loading a big card database takes a while).
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
    cd "$REPO"

    # 1. System files, every run, so changes to them arrive even without a new commit.
    installed=$(bash "$APP/deploy/install.sh" || echo "install.sh failed")
    [ -n "$installed" ] && echo "$installed"

    force=0
    if [ -e "$FORCE" ]; then force=1; rm -f "$FORCE"; fi

    if ! as_nic git fetch -q origin main; then
        status failed "Couldn't reach GitHub to check for updates. Is the internet up?"
        exit 1
    fi
    old=$(as_nic git rev-parse HEAD)
    new=$(as_nic git rev-parse origin/main)

    if [ "$old" = "$new" ]; then
        if [[ $installed == *app-changed* ]]; then
            systemctl restart mtg-sorter
        fi
        status "up to date" "Up to date."
        exit 0
    fi
    if [ "$force" = 0 ] && [ -e "$BAD" ] && [ "$(cat "$BAD")" = "$new" ]; then
        exit 0   # this version already failed to start; wait for a newer one (or Update now)
    fi

    # Edits made on the Pi block a fast-forward. Fix updates (force) sets them aside with
    # git stash, where they can still be found: git stash list.
    if [ -n "$(as_nic git status --porcelain --untracked-files=no)" ]; then
        if [ "$force" = 1 ]; then
            as_nic git stash push -q -m "Set aside by Fix updates, $(date '+%Y-%m-%d %H:%M')"
            echo "Set aside edits made on the Pi (git stash list shows them)"
        else
            status failed "Updates are stuck: files were changed on the Pi. Press Fix updates on the Maintenance page."
            echo "Files were changed on the Pi, so not updating. Undo them, or use Fix updates." >&2
            exit 1
        fi
    fi

    as_nic git checkout -q main
    if ! as_nic git merge -q --ff-only origin/main; then
        status failed "Couldn't move to the new version (the Pi's copy has its own commits)."
        exit 1
    fi
    echo "Updated ${old:0:7} -> ${new:0:7}"

    changed() { ! as_nic git diff --quiet "$old" "$new" -- "$@"; }
    if changed mtg-sorter/requirements.txt; then
        echo "requirements.txt changed, installing packages"
        as_nic "$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt" || echo "pip install failed" >&2
    fi
    bash "$APP/deploy/install.sh" || true   # the new version's system files

    systemctl restart mtg-sorter
    if app_answers; then
        rm -f "$BAD"
        status updated "Updated to $(as_nic git log -1 --format='%h, %s')."
        return 0
    fi

    # 3. The new version doesn't start: go back to the one that did.
    echo "The new version didn't start. Going back to ${old:0:7}." >&2
    journalctl -u mtg-sorter -n 30 --no-pager >&2 || true
    as_nic git reset -q --hard "$old"
    if changed mtg-sorter/requirements.txt; then
        as_nic "$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt" || true
    fi
    bash "$APP/deploy/install.sh" >/dev/null || true
    echo "$new" | as_nic tee "$BAD" >/dev/null
    systemctl restart mtg-sorter
    status "rolled back" "Version ${new:0:7} didn't start, so the Pi went back to ${old:0:7}. It tries again when there's a newer version."
    exit 1
}

# Everything is inside main, which bash reads in full before running, so a pull that
# changes this file can't confuse the run that's already going.
main "$@"
exit
