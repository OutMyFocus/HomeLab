# Looking after the sorter

Almost everything is on the **Maintenance page**: the wrench button at the top of the
scanner, or **http://mtgsorter.local:5000/maintenance**. When the wrench has a yellow or red
dot, the check-up found something. Open the page and it says what, and what to do.

You shouldn't need a terminal for normal use. When you do, everything is one word after
`mtg` (see [From a terminal](#from-a-terminal)).

## The Maintenance page

| Section | What it's for |
|---|---|
| **Check-up** | Power, temperature, camera, servo board, feeder, card database, Wi-Fi, internet, storage, memory and updates. Green is fine. Yellow and red come with a fix, and sometimes a button that does it. |
| **Restart and power** | **Restart app** if the page misbehaves. **Reboot Pi** if the camera or Wi-Fi went missing. **Shut down** before unplugging. |
| **Updates** | Which version is running and what the last update did. **Update now** checks GitHub straight away. **Fix updates** unsticks updates (see below). The switch turns automatic updates on or off. |
| **Test the moving parts** | Moves every servo through its positions and back, then turns the feeder for a moment, and lists anything that didn't respond. |
| **Wi-Fi** | The network it's on and the signal. Save another network (a second home, your phone's hotspot) before you move the sorter, and it joins that one by itself. |
| **Backup** | **Download backup** saves your collection, card database, everything the scanner learned, and your settings in one zip. **Restore a backup** puts one back. It keeps a copy of what was there first, in `data/backups`. |
| **Logs** | What the app and the Pi wrote down. If something goes wrong, **Download** the log and share it. |

**Servo angles** are set on the **Machine** page: move a part's slider until it sits right,
then press the position's name under "Save the slider's angle as". They're saved on the Pi,
so you never need to edit `config.py`. **Back to the original angles** undoes them.

## Updates

The Pi checks GitHub every 5 minutes. When you merge a pull request, the new version is
running within about 5 minutes, and the app restarts by itself to load it.

- **If a new version doesn't start**, the Pi goes back to the version that worked, and the
  Maintenance page says so. It tries again when there's a newer version, or when you press
  **Update now**.
- **"Updates are stuck: files were changed on the Pi."** Something edited a file in
  `~/HomeLab` on the Pi, and the Pi won't overwrite it. Press **Fix updates**. It sets the edits
  aside instead of deleting them, so they can still be found with `git stash list`, and then
  updates.

## When something's wrong

**The page won't open.**
1. Wait 2 minutes after plugging it in. It takes that long to start.
2. Try **http://10.0.0.247:5000** instead of `mtgsorter.local` (some phones don't do `.local`).
3. Unplug the Pi, wait 10 seconds, plug it back in. Wait 2 minutes.
4. Still nothing: SSH in (below) and type `mtg status`. It says what's wrong, even when the
   app isn't running.

**"Power supply: not enough power."** This is the most common cause of crashes, lost Wi-Fi
and a Pi that won't boot. The Pi 5 needs a real 5 V **5 A** supply (the official 27 W one), and
a short, thick USB-C cable. Phone chargers and the 5 V 4 A adapter aren't enough with the
servos and lights on it. "Since it started" means the power dipped at some point: it's worth fixing even
if nothing has crashed yet.

**"Camera not found."**
1. **Shut down** from the Maintenance page and unplug it. Never touch the ribbon cable with
   the power on.
2. At both ends: lift the latch, push the cable in straight, silver contacts facing the board,
   press the latch down. Only use the one-piece cable. The FFC extension board shorted the Pi.
3. Plug it back in. The camera is only looked for when the Pi starts.
4. Still not found: SSH in and run `mtg repair`. If the Pi can't see the camera, it names
   the camera's driver in the Pi's settings. Then `sudo reboot`.

**"Servo board not found."** Check its 4 wires to the Pi: VCC to pin 1, SDA to pin 3,
SCL to pin 5, GND to pin 6. In SSH, `mtg i2c` should show `40` in the grid. If it says I2C is
off, run `mtg repair` and reboot.

**A servo or the feeder doesn't move in the test.** The servo board needs its own 5 V on
its screw terminal (V+ and GND): the Pi's power doesn't reach the servos. Check each servo is
plugged into the channel the Machine page lists, the right way round (wiring:
[hardware/ASSEMBLY.md, Stage C](hardware/ASSEMBLY.md)). The feeder motor's driver needs 5 V on VM too.

**"Too hot."** Check the fan spins and nothing covers the vents.

**"Storage almost full."** Saved scans add up (they're in `data/captures`). Turn off
**Collect scans** in the Train tab if you don't need more, or download a backup and move to a
bigger SD card.

**Wi-Fi is gone** (after a move, a new router, or a crash):
- If you saved the other network beforehand, it joins that one by itself.
- Otherwise, plug the Pi into the router with an Ethernet cable, open the Maintenance page,
  and save the new network under Wi-Fi.
- No cable: take out the SD card, flash it again with Raspberry Pi Imager (Wi-Fi settings
  under Edit settings), then run the setup command below. Download a backup first if you can.

## Starting over (new SD card, or it's badly broken)

1. **Download a backup** from the Maintenance page, if it still opens. If it doesn't, the files are in
   `~/HomeLab/mtg-sorter/data/` on the old card.
2. Flash the SD card with Raspberry Pi Imager: Raspberry Pi OS (64-bit), hostname `mtgsorter`,
   username `nic`, your Wi-Fi, SSH on. (Full steps: [hardware/ASSEMBLY.md](hardware/ASSEMBLY.md#raspberry-pi-setup).)
3. SSH in and run this one line. It installs everything, sets up the service and
   updates, and checks it all at the end. It takes about 10 minutes:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/OutMyFocus/HomeLab/main/mtg-sorter/deploy/setup.sh | bash
   ```
4. `sudo reboot`, open the Maintenance page, and **Restore a backup**.

## From a terminal

SSH in from PowerShell on your PC: `ssh nic@mtgsorter.local` (or `ssh nic@10.0.0.247`).

| Type | It does |
|---|---|
| `mtg` | lists these |
| `mtg status` | the same check-up as the Maintenance page |
| `mtg logs` | the app's messages as they happen (Ctrl+C to stop). `mtg logs updates` for updates |
| `mtg restart` | restarts the app |
| `mtg update` | checks GitHub for a new version now |
| `mtg fix-updates` | unsticks updates (sets edits made on the Pi aside) |
| `mtg backup` | saves a backup zip in your home folder on the Pi |
| `mtg repair` | runs the setup again: fixes missing packages, services and settings, never touches your cards |
| `mtg camera` | lists the cameras the Pi can see |
| `mtg i2c` | checks the Pi can see the servo board |
| `mtg reboot` / `mtg off` | restart or shut down the Pi |

## How it fits together (for later)

- `deploy/setup.sh` sets up or repairs the Pi. It's safe to run any time.
- `deploy/update.sh` runs every 5 minutes (`mtg-sorter-update.timer`). It installs the
  system files (`deploy/install.sh`), pulls `main`, restarts the app, and rolls back if the app
  doesn't come up. It writes what happened to `data/update_status.json`.
- `deploy/mtg-sorter-admin` is the only thing the web app can run as root: restart, reboot,
  shut down, update, automatic updates on/off, logs, and saving Wi-Fi networks. The sudo rule in
  `deploy/mtg-sorter.sudoers` allows just that file.
- Your data lives in `data/`, which git never touches: `collection.csv`, `cards.db` (with
  what the scanner learned), `app_settings.json`, `machine_settings.json` (servo angles),
  and `captures/` (saved scans).
- The app has no login. Anyone on your Wi-Fi can open it, including the Restart and Shut down
  buttons. Keep it off the open internet unless something like Cloudflare Access is in front
  (see [deploy/REMOTE_ACCESS.md](deploy/REMOTE_ACCESS.md)).
