# The Pi on the same Docker image as the server

The server (tower, see [UNRAID.md](UNRAID.md)) runs `ghcr.io/outmyfocus/mtg-sorter:latest`.
The sorter's Pi can run that exact image too, so the two always have the same version of
the app. GitHub builds the image for both: amd64 for the server and arm64 for the Pi
(the Pi's flavour adds Raspberry Pi OS's camera and GPIO packages).

Cards are still kept separately on each one: this keeps the **code** the same, not the
collection. To move cards, use Maintenance → Backup on one and Restore on the other.

## Switch the Pi over

On the Pi (SSH in, or the terminal):

```bash
mtg docker on
```

It installs Docker the first time, downloads the image (a few minutes), and restarts the
app from it. If the new app doesn't answer within 2 minutes it goes back to the old way by
itself. Everything stays where it was:

- same address: http://10.0.0.247:5000 and https://mtgsorter.taild0ce28.ts.net
- same data folder (`~/HomeLab/mtg-sorter/data`): cards, settings, saved servo angles
- `mtg status`, `mtg logs`, `mtg restart` and the Maintenance page work as before

To go back to running from the git copy: `mtg docker off`.

## How it works

| Piece | What it does |
|---|---|
| `mtg-sorter-docker.service` | Installed as `mtg-sorter.service`. Runs the image with `--privileged` (camera, I2C servo board, GPIO feeder, SPI lights, `vcgencmd`) and `--network host` |
| `update-docker.sh` | `update.sh` hands over to it. Every 5 minutes: pulls the newest image; if it's new, restarts with it; if that doesn't start, goes back to the image that did |
| `mtg-sorter-host.path`, `mtg-sorter-host` | The app can't use sudo inside the container. For Restart, Reboot, Update now, logs, Wi-Fi and SPI it drops a file in `data/host/`, and the Pi runs the job through `mtg-sorter-admin` (the same fixed list of jobs as before) |
| `/etc/mtg-sorter/docker` | The switch. While it exists, `install.sh` installs the Docker versions of the services |

Not available inside the container: the Wi-Fi network list and the Tailscale address on
the Maintenance page (adding and forgetting networks still works).

## Driving the machine from the server

The servos and feeder are wired to the Pi. To use the server's Machine page instead of the
Pi's, set on the server's container (Unraid: edit mtg-sorter, the "Sorter's Pi" field):

```
MTG_MACHINE_URL=http://10.0.0.247:5000
```

The server's Machine page, Home page and check-up then send every move to the Pi. Saved
angles stay on the Pi. If the Pi has a PIN or accounts on, also run `mtg machine-key` on
the Pi and put what it prints in `MTG_MACHINE_KEY` on the server. The key only opens the
Pi's machine controls, nothing else.
