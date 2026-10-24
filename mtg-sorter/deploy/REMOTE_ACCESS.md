# Reaching the sorter from anywhere

Two pieces, each doing one job:

| | What it's for | Who can use it |
|---|---|---|
| **Tailscale** | SSH into the Pi, and open the app privately from your own devices | Only devices signed in to your tailnet |
| **Cloudflare Tunnel** | The app at a real address like `https://mtg.example.com` | Anyone you allow in Cloudflare Access |

Neither needs a port opened on your router. Both connect to the app on the Pi at
`127.0.0.1:5000`. The app also answers on your home Wi-Fi at `http://mtgsorter.local:5000`
(see the end of 2c to turn that off).

> **The app has no login.** Anyone who can open it can scan, delete, and download your
> collection. Don't publish it through Cloudflare without step 3c (Access) in front.

Replace `example.com` with your domain throughout.

## 1. Run the app as a service

So it starts on boot and comes back if it crashes. From an SSH session on the Pi:

```bash
cd ~/HomeLab && git pull
sudo cp mtg-sorter/deploy/mtg-sorter.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mtg-sorter
systemctl status mtg-sorter        # should say "active (running)"
curl -I http://127.0.0.1:5000      # should say "200 OK"
```

No camera yet? Edit the service to use demo photos, then restart it:

```bash
sudo nano /etc/systemd/system/mtg-sorter.service
#   end the ExecStart line with:  --demo /home/nic/photos
sudo systemctl daemon-reload && sudo systemctl restart mtg-sorter
```

Useful later: `journalctl -u mtg-sorter -f` shows the app's output live, and
`sudo systemctl restart mtg-sorter` picks up a `git pull`.

### 1b. Keep it up to date from GitHub

A timer checks GitHub a minute after boot and then every 5 minutes. When `main` has new
commits it pulls them, reinstalls Python packages if `requirements.txt` changed, reinstalls
these service files if they changed, and restarts the app. Your card database and collection
live in `mtg-sorter/data/`, which isn't in git, so updates never touch them.

```bash
sudo cp mtg-sorter/deploy/mtg-sorter-update.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mtg-sorter-update.timer
systemctl list-timers mtg-sorter-update      # shows when it runs next
journalctl -u mtg-sorter-update -n 20        # what the last updates did
```

It only fast-forwards. If you edit files in `~/HomeLab` on the Pi, updates stop (the log
says so) until you undo the edits with `git checkout -- .` or commit and push them.

If you stop the app from the service to run it by hand, use `sudo systemctl stop mtg-sorter`
first, or the two will fight over port 5000.

## 2. Tailscale

### 2a. Join the Pi to your tailnet

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh
```

It prints a login link. Open it on any device and sign in with your Tailscale account.
The Pi shows up in the [admin console](https://login.tailscale.com/admin/machines) as
`mtgsorter`. In its `...` menu, pick **Disable key expiry** so it doesn't drop off the
tailnet in 6 months.

Tailscale starts on boot by itself.

### 2b. SSH

`--ssh` turns on Tailscale SSH: Tailscale handles the login, no password or keys.

- **From the browser, no SSH client needed:** in the admin console, open the `mtgsorter`
  machine's `...` menu and pick **SSH to machine**. Log in as `nic`. This is the quickest fix
  while Windows is missing OpenSSH.
- **From Windows with OpenSSH installed** (and Tailscale running on the PC):
  `ssh nic@mtgsorter`. The short name works anywhere, not just on your home Wi-Fi.

The first time, Tailscale may ask you to approve the session in the browser.

### 2c. Open the app privately

```bash
sudo tailscale serve --bg 5000
tailscale serve status
```

The status shows an address like `https://mtgsorter.tail1234.ts.net`. Open it on any of
your devices with Tailscale on. If it says HTTPS isn't enabled, follow its link to turn on
HTTPS certificates for the tailnet, then run the command again. This setting survives reboots.

The service file runs the app with `--host 0.0.0.0`, so `http://mtgsorter.local:5000` keeps
working on your home Wi-Fi too. To allow only the Tailscale address, change it to
`--host 127.0.0.1` in `deploy/mtg-sorter.service` and push; the updater installs it.

## 3. Cloudflare Tunnel on your domain

Needs a domain whose DNS is on Cloudflare (it shows as **Active** in the Cloudflare
dashboard).

### 3a. Install cloudflared

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update && sudo apt install -y cloudflared
```

### 3b. Create the tunnel

1. In the [Cloudflare dashboard](https://one.dash.cloudflare.com), go to **Zero Trust →
   Networks → Tunnels → Create a tunnel**. Pick **Cloudflared**, name it `mtgsorter`.
2. It shows install commands. Pick **Debian** and **arm64-bit**, and copy only the last
   one, which looks like:

   ```bash
   sudo cloudflared service install eyJhIjoi...
   ```

   Run it on the Pi. That installs cloudflared as a service, so it starts on boot. Back in
   the dashboard the connector should show **Connected** within a few seconds.
3. Click **Next** to add a public hostname:
   - **Subdomain:** `mtg` · **Domain:** `example.com`
   - **Service type:** `HTTP` · **URL:** `localhost:5000`
4. Save. Cloudflare adds the DNS record for you.

Don't open the address yet, it's public until the next step.

### 3c. Put a login in front (Cloudflare Access)

1. **Zero Trust → Access → Applications → Add an application → Self-hosted.**
2. Name `MTG sorter`, add the public hostname `mtg.example.com`.
3. Add a policy: **Action** `Allow`, **Include** `Emails` → your email address (add anyone
   else you want to let in).
4. Save. One-time PIN login is on by default, so Cloudflare emails you a code.

Now open `https://mtg.example.com`. Cloudflare asks for your email, sends a code, then
shows the app. A private window should show the login page, not the app; if it shows the
app, the Access application isn't covering the hostname.

## Checking after a reboot

```bash
sudo reboot
# a minute later, SSH back in through Tailscale, then:
systemctl status mtg-sorter cloudflared tailscaled
```

All three should be `active (running)`.

## If something's wrong

| Symptom | Check |
|---|---|
| Cloudflare shows error 502 | The app isn't running: `systemctl status mtg-sorter`, `journalctl -u mtg-sorter -n 50` |
| Cloudflare shows error 1033 | The tunnel is down: `systemctl status cloudflared`, `journalctl -u cloudflared -n 50` |
| `ssh nic@mtgsorter` can't find the host | Tailscale isn't running on the PC, or MagicDNS is off (admin console → DNS) |
| Live camera view stutters through Cloudflare | Expected: the stream goes out and back through Cloudflare. Use the Tailscale address at home. |
