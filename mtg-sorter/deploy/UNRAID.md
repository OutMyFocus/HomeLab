# The scanner on your Unraid server

The app runs as a Docker container on the server. Every device on your network (PC, phone,
tablet) opens the same app, and all scans land in the same collection. The server has no
camera: you scan with the camera of whatever device you're holding, or by uploading photos.
The Raspberry Pi keeps running the sorter machine itself (feeder, servos, Pi camera).

Three steps: start the container, give it an https address (the phone camera needs one),
move your data over from the Pi.

## 1. Start the container

On Unraid, **Docker → Add Container**, and fill in:

| Field | Value |
|---|---|
| Name | `mtg-sorter` |
| Repository | `ghcr.io/outmyfocus/mtg-sorter:latest` |
| Network type | Bridge |
| WebUI | `http://[IP]:[PORT:5000]` |
| Port (Add another Path, Port...) | Container port `5000`, host port `5000` |
| Path (Add another Path, Port...) | Container path `/data`, host path `/mnt/user/appdata/mtg-sorter` |

Press **Apply**. Unraid pulls the image and starts it. Open `http://<server's IP>:5000` on any
device at home: the app is there, with an empty collection for now.

Rather than typing the fields: copy [`unraid/mtg-sorter.xml`](unraid/mtg-sorter.xml) to
`/boot/config/plugins/dockerMan/templates-user/` on the server, then pick **mtg-sorter** in
the template dropdown of Add Container.

> If the pull fails with "denied", the image is still private on GitHub. On
> github.com/OutMyFocus/HomeLab, open **Packages → mtg-sorter → Package settings → Change
> visibility → Public** (needed once). The image is built by the `mtg-sorter image` workflow
> every time `mtg-sorter/` changes on `main`.

### Updates

Unraid's Docker tab: **Check for updates**, then **Update** next to mtg-sorter. Your data
stays in `/mnt/user/appdata/mtg-sorter` and is never touched by an update. (The app's own
Maintenance page says the same; it can't update itself inside Docker.)

### Without Unraid's form

Any Docker host works the same way:

```bash
docker run -d --name mtg-sorter --restart unless-stopped -p 5000:5000 \
  -v /path/for/its/data:/data ghcr.io/outmyfocus/mtg-sorter:latest
```

or, from a checkout of this repository, `cd mtg-sorter && docker compose up -d`
(see [`../docker-compose.yml`](../docker-compose.yml)).

## 2. An https address, so phones can use their camera

Browsers only share the camera with pages on **https** (or `localhost`). `http://server:5000`
is fine for looking at the collection, but the Scan page's **This device's camera** option
stays greyed out on it. The easy fix on Unraid 7 is its Tailscale integration: it gives the
container its own private https address, reachable from any of your devices that run
Tailscale, at home or away, with no port opened on your router.

1. Install the **Tailscale** plugin from Apps if you haven't (recommended, not required), and
   sign the server in.
2. **Docker → mtg-sorter → Edit**. Turn on **Use Tailscale**.
3. **Tailscale hostname:** `mtg` (or anything unique on your tailnet).
4. Leave exit node, userspace networking and SSH alone.
5. **Serve:** on. (Not Funnel: that would put the app, which has no login unless you set a PIN
   in Settings, on the public internet.) Leave the port on auto-detect; it uses the WebUI port.
6. **Apply**, then open the container's log and click the **To authenticate, visit...** link
   to approve it on your tailnet.
7. The log (or the Tailscale admin console) shows the address, like
   `https://mtg.<your-tailnet>.ts.net`. Open it on your phone, go to **Scan**, and pick
   **This device's camera** in the camera menu (or the button on the "No camera" panel). The
   phone asks once for camera permission.

If the log says `Couldn't detect persistent Docker directory for .tailscale_state`: Edit the
container, turn on **Show advanced settings**, set **State directory** to
`/data/.tailscale_state`, and restart it.

Tailscale's own guide for this: https://docs.unraid.net/go/tailscale-docker/

**No Tailscale?** A Cloudflare Tunnel with Cloudflare Access in front works too
([REMOTE_ACCESS.md](REMOTE_ACCESS.md), step 3, pointing at `mtg-sorter:5000` instead of the
Pi). For your own PC only, Chrome can be told to treat the plain address as secure:
`chrome://flags/#unsafely-treat-insecure-origin-as-secure`, add `http://<server's IP>:5000`.

## 3. Move your cards over from the Pi

The server starts with an empty card database and collection. The Pi has both, and they
move in one zip:

1. On the Pi's app (`http://mtgsorter.local:5000`): **Maintenance → Backup → Download** (the
   zip holds the card database with everything it learned, your collection, decks, bins,
   wishlist and settings).
2. On the server's app: **Maintenance → Restore a backup…**, pick that zip. The app restarts
   with your cards in it.

From then on, scan on the server. The Pi keeps its own copy for the sorter; do the same
backup-and-restore the other way whenever the sorter should know about cards you added on
the server (merging the two automatically is a later step).

To make the server know every card: **Maintenance → Card database → Download every card**
(30-60 minutes; scanning keeps working). From the server's terminal it's
`docker exec mtg-sorter python build_db.py --all` (stop and resume it any time).

## How scanning from a phone works

The phone's browser opens its camera and sends a picture to the server about eight times a
second; the server runs the same recognition the Pi does and sends back what it found, which
the page draws over the live video. Every phone gets a scanner of its own, so several people
can scan at the same time, each with their own table and session, and the machine's camera
(on the Pi) carries on untouched. The name typed under **Scanning as** is saved with each card
in the collection's Source column, so you can tell whose cards are whose on the Collection
page. Closing the page drops its scanner (its cards are already saved); a page left in the
background pauses and picks up again when it comes back. Everything else on the Scan page
(Auto-save, foil, slots, training, the photo upload) works exactly as before.

**Away from home:** the Tailscale address works anywhere your phone has Tailscale on.
**Friends:** they need a way in first. Cloudflare Tunnel with Cloudflare Access (an emailed
code; see [REMOTE_ACCESS.md](REMOTE_ACCESS.md), step 3) is the easy one, since they install
nothing. Set a PIN in Settings before sharing any link: without one, anyone with the link can
scan into, delete from and download your collection.

## The sorter machine

The servos and feeder are wired to the sorter's Pi. To drive them from this server's Machine
page, fill in **Sorter's Pi** (`MTG_MACHINE_URL`, e.g. `http://10.0.0.247:5000`) on the
container. The Pi can also run this same image, so both have the same version: see
[PI_DOCKER.md](PI_DOCKER.md).
