"""Looking after the Pi: health, updates, restarts, logs, Wi-Fi and backups.

The Maintenance page (/maintenance in the app) is built on this. Everything here reads
what it can and says plainly when something isn't available, so the page also opens on
a PC (where most of it is "only on the Pi").

The app runs as the user nic, not as root. Anything that needs root (restarting the
service, rebooting, saving a Wi-Fi network) goes through one small helper,
deploy/mtg-sorter-admin, which deploy/install.sh puts in /usr/local/sbin and lets nic
run with sudo without a password. It only does the handful of jobs it knows.
"""

import io
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

from . import config

APP_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = APP_DIR.parent
ADMIN = "/usr/local/sbin/mtg-sorter-admin"
UPDATE_STATUS = config.DATA_DIR / "update_status.json"   # written by deploy/update.sh
BACKUP_DIR = config.DATA_DIR / "backups"                 # copies made before a restore
SETUP_HINT = ("The maintenance helper isn't installed yet. It installs itself within 5 minutes of an "
              "update, or run: bash ~/HomeLab/mtg-sorter/deploy/setup.sh")
ON_PI = sys.platform.startswith("linux") and Path("/proc/device-tree/model").exists()


def run(cmd: list[str], timeout: float = 10, input: str | None = None) -> tuple[bool, str]:
    """Runs a command, returning (worked, its output). Never raises."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, input=input)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)


def admin_installed() -> bool:
    return Path(ADMIN).exists()


def admin(*args: str, input: str | None = None, timeout: float = 30) -> str:
    """Asks the root helper to do one of its jobs. Raises RuntimeError in plain words."""
    if not admin_installed():
        raise RuntimeError(SETUP_HINT)
    ok, out = run(["sudo", "-n", ADMIN, *args], timeout=timeout, input=input)
    if not ok:
        if "password is required" in out or "a terminal is required" in out:
            raise RuntimeError("The Pi asked for a password, so the helper isn't fully set up. " + SETUP_HINT)
        raise RuntimeError(out or "That didn't work.")
    return out


def later(*args: str, delay: float = 1.0):
    """Runs an admin job after the page has had its answer (for restart, reboot, power off)."""
    def go():
        time.sleep(delay)
        try:
            admin(*args)
        except RuntimeError as e:
            print(f"{' '.join(args)} failed: {e}")
    threading.Thread(target=go, daemon=True).start()


# --- Readings --------------------------------------------------------------------------

def model() -> str | None:
    try:
        return Path("/proc/device-tree/model").read_text().strip("\x00\n ")
    except OSError:
        return None


def temperature() -> float | None:
    try:
        return int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
    except (OSError, ValueError):
        return None


# What each bit of `vcgencmd get_throttled` means.
THROTTLE_BITS = {0: "under-voltage now", 1: "speed capped now", 2: "slowed down now", 3: "too hot now",
                 16: "under-voltage since it started", 17: "speed capped since it started",
                 18: "slowed down since it started", 19: "too hot since it started"}


def throttled() -> int | None:
    ok, out = run(["vcgencmd", "get_throttled"], timeout=3)
    m = re.search(r"0x([0-9a-fA-F]+)", out) if ok else None
    return int(m.group(1), 16) if m else None


def supply_volts() -> float | None:
    """The 5 V coming in, as the Pi 5 measures it."""
    ok, out = run(["vcgencmd", "pmic_read_adc", "EXT5V_V"], timeout=3)
    m = re.search(r"=([\d.]+)V", out) if ok else None
    return round(float(m.group(1)), 2) if m else None


def uptime() -> float | None:
    try:
        return float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def memory() -> dict | None:
    try:
        info = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        kb = lambda k: int(info[k].split()[0])  # noqa: E731
        return {"total_mb": kb("MemTotal") // 1024, "free_mb": kb("MemAvailable") // 1024}
    except (OSError, ValueError, KeyError):
        return None


def disk() -> dict:
    u = shutil.disk_usage(config.DATA_DIR if config.DATA_DIR.exists() else APP_DIR)
    return {"total_gb": round(u.total / 1e9, 1), "free_gb": round(u.free / 1e9, 1),
            "used_pct": round(100 * u.used / u.total)}


def ip_address() -> str | None:
    try:   # the address the Pi would use to reach the internet (nothing is sent)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("1.1.1.1", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def wifi() -> dict:
    """The Wi-Fi network in use, its signal (0-100) and the networks saved on the Pi."""
    if not shutil.which("nmcli"):
        return {"available": False}
    now = {"available": True, "ssid": None, "signal": None, "saved": []}
    ok, out = run(["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL", "device", "wifi", "list", "--rescan", "no"])
    for line in out.splitlines() if ok else []:
        active, *ssid, signal = line.replace("\\:", "\x00").split(":")
        if active == "yes":
            now["ssid"] = ":".join(ssid).replace("\x00", ":")
            now["signal"] = int(signal) if signal.isdigit() else None
    ok, out = run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"])
    for line in out.splitlines() if ok else []:
        name, _, kind = line.replace("\\:", "\x00").rpartition(":")
        if kind == "802-11-wireless":
            now["saved"].append(name.replace("\x00", ":"))
    return now


def tailscale_ip() -> str | None:
    if not shutil.which("tailscale"):
        return None
    ok, out = run(["tailscale", "ip", "-4"], timeout=3)
    return out.splitlines()[0] if ok and out else None


_internet = {"at": 0.0, "ok": None}


def internet() -> bool:
    """Can the Pi reach Scryfall (for prices)? Checked at most once a minute."""
    if time.monotonic() - _internet["at"] > 60:
        try:
            socket.create_connection(("api.scryfall.com", 443), timeout=3).close()
            _internet["ok"] = True
        except OSError:
            _internet["ok"] = False
        _internet["at"] = time.monotonic()
    return _internet["ok"]


def git(*args: str) -> str | None:
    ok, out = run(["git", "-C", str(REPO_DIR), *args], timeout=5)
    return out if ok else None


def version() -> dict:
    """Which version of the code is running, and whether GitHub has a newer one."""
    head = git("rev-parse", "--short", "HEAD")
    if not head:
        return {"available": False}
    when, subject = (git("log", "-1", "--format=%cI%x00%s") or "\x00").split("\x00", 1)
    upstream = git("rev-parse", "--short", "origin/main")
    behind = git("rev-list", "--count", "HEAD..origin/main")
    changed = git("diff", "--name-only", "HEAD")   # files edited here (they'd block updates)
    return {"available": True, "commit": head, "date": when, "subject": subject,
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"), "latest": upstream,
            "behind": int(behind) if behind and behind.isdigit() else None,
            "local_edits": (changed or "").splitlines()}


def update_status() -> dict | None:
    try:
        return json.loads(UPDATE_STATUS.read_text())
    except (OSError, ValueError):
        return None


def auto_updates_on() -> bool | None:
    if not shutil.which("systemctl"):
        return None
    ok, out = run(["systemctl", "is-enabled", "mtg-sorter-update.timer"], timeout=5)
    return out.strip() == "enabled" if out else None


def as_service() -> bool:
    """True when systemd started the app (so Restart brings it back by itself)."""
    return bool(os.environ.get("INVOCATION_ID"))


# --- The check-up ----------------------------------------------------------------------

def check(id, label, state, summary, fix=None, action=None) -> dict:
    """One line of the check-up. state: ok, warn, bad, or off (not on this computer)."""
    return {"id": id, "label": label, "state": state, "summary": summary, "fix": fix, "action": action}


POWER_FIX = ("Use the official Raspberry Pi 27 W USB-C supply (5 V, 5 A), or a 5 V supply of at least 5 A "
             "with a short, thick cable. A weak supply makes the Pi slow down, lose Wi-Fi and crash.")


def power_check() -> dict:
    flags, volts = throttled(), supply_volts()
    if flags is None:
        return check("power", "Power supply", "off", "Only measured on the Pi.")
    v = f" The Pi measures {volts:.2f} V coming in." if volts else ""
    if flags & 0x1:
        return check("power", "Power supply", "bad", "Not enough power right now." + v, POWER_FIX)
    if flags & 0x10000:
        return check("power", "Power supply", "warn",
                     "The power dipped too low at some point since the Pi started." + v, POWER_FIX)
    return check("power", "Power supply", "ok", "Power is fine." + v)


def temperature_check() -> dict:
    t, flags = temperature(), throttled() or 0
    if t is None:
        return check("temp", "Temperature", "off", "Only measured on the Pi.")
    fix = "Make sure the Pi's fan spins and the vents in the case aren't blocked."
    if t >= 80 or flags & 0x8:
        return check("temp", "Temperature", "bad", f"{t:.0f} °C: too hot, the Pi is slowing itself down.", fix)
    if t >= 70:
        return check("temp", "Temperature", "warn", f"{t:.0f} °C: warm.", fix)
    return check("temp", "Temperature", "ok", f"{t:.0f} °C")


def disk_check() -> dict:
    d = disk()
    text = f"{d['free_gb']} GB free of {d['total_gb']} GB"
    fix = ("Saved scans add up: turn off Collect scans in the Train tab if you don't need more. Or download "
           "a backup and move to a bigger SD card.")
    if d["free_gb"] < 0.5:
        return check("disk", "Storage", "bad", text + ": almost full. Saving cards can fail.", fix)
    if d["free_gb"] < 2 or d["used_pct"] > 90:
        return check("disk", "Storage", "warn", text + ": getting full.", fix)
    return check("disk", "Storage", "ok", text)


def memory_check() -> dict:
    m = memory()
    if not m:
        return check("memory", "Memory", "off", "Only measured on the Pi.")
    text = f"{m['free_mb']} MB free of {m['total_mb']} MB"
    if m["free_mb"] < 200:
        return check("memory", "Memory", "warn", text + ": low.", "Restart the app, or reboot the Pi.", "restart")
    return check("memory", "Memory", "ok", text)


def network_check() -> dict:
    w, ip = wifi(), ip_address()
    if not ip:
        return check("network", "Network", "bad", "Not connected to a network.",
                     "Check the Wi-Fi router is on. See MAINTENANCE.md, \"Wi-Fi is gone\".")
    where = f"Wi-Fi \"{w['ssid']}\", signal {w['signal']}%" if w.get("ssid") else "Connected"
    text = f"{where}, address {ip}"
    if w.get("signal") is not None and w["signal"] < 35:
        return check("network", "Network", "warn", text + ": weak signal.",
                     "Move the sorter closer to the router, or turn it so the Pi's side faces the router.")
    return check("network", "Network", "ok", text)


def internet_check() -> dict:
    if internet():
        return check("internet", "Internet", "ok", "Can reach Scryfall for prices and GitHub for updates.")
    return check("internet", "Internet", "warn", "Can't reach the internet.",
                 "Scanning still works, but prices fall back to the saved ones and updates wait. "
                 "Check your router's internet connection.")


def camera_check(scanner) -> dict:
    src = type(scanner.source).__name__
    if src == "DemoSource":
        return check("camera", "Camera", "ok", "Using demo photos instead of a camera.")
    if src == "WaitingForCamera" or scanner.source is None:
        return check("camera", "Camera", "bad", "No camera found.",
                     "Power off, then check the ribbon cable: contacts facing the board at both ends, latches "
                     "pressed down. Then turn the Pi back on. See MAINTENANCE.md, \"Camera not found\".")
    perf = scanner.perf or {}
    name = getattr(scanner.source, "name", None) or "Camera"
    if not scanner.started:
        return check("camera", "Camera", "warn", f"{name} is starting…")
    age = perf.get("frame_age_ms")
    if age is not None and age > 3000:
        return check("camera", "Camera", "bad", f"{name} stopped sending pictures.",
                     "Restart the app. If it keeps happening, reseat the camera cable.", "restart")
    fps = perf.get("fps")
    return check("camera", "Camera", "ok", f"{name}" + (f", {fps:.0f} pictures a second" if fps else ""))


def machine_checks(machine) -> list[dict]:
    if machine is None:
        return []
    s = machine.state()
    i2c = Path("/dev/i2c-1").exists()
    out = []
    if s["servos"]["ok"]:
        out.append(check("servos", "Servo board", "ok", "Found the servo board."))
    elif ON_PI and not i2c:
        out.append(check("servos", "Servo board", "bad", "I2C is turned off, so the Pi can't talk to the servo board.",
                         "Run the setup (it turns I2C on), then reboot: bash ~/HomeLab/mtg-sorter/deploy/setup.sh"))
    elif ON_PI:
        out.append(check("servos", "Servo board", "warn", "Servo board not found.",
                         "Check its 4 wires to the Pi: VCC to pin 1, SDA to pin 3, SCL to pin 5, GND to pin 6."))
    else:
        out.append(check("servos", "Servo board", "off", "Only on the Pi."))
    if s["feeder"]["ok"]:
        out.append(check("feeder", "Feeder motor", "ok", "Feeder driver ready (GPIO 17 and 27)."))
    else:
        out.append(check("feeder", "Feeder motor", "warn" if ON_PI else "off",
                         s["feeder"]["error"] or "Not available.",
                         "Check the motor driver's IN1 and IN2 wires go to GPIO 17 and 27." if ON_PI else None))
    return out


def database_check(scanner) -> dict:
    n = scanner.matcher.card_count
    if not n:
        return check("cards", "Card database", "bad", "The card database is empty, so no card can be recognized.",
                     "On the Pi: cd ~/HomeLab/mtg-sorter && .venv/bin/python build_db.py --sets dmu,one")
    learned = scanner.matcher.learned_count
    return check("cards", "Card database", "ok", f"{n:,} cards" + (f", {learned:,} learned scans" if learned else ""))


def updates_check() -> dict:
    v, st, on = version(), update_status(), auto_updates_on()
    if not v.get("available"):
        return check("updates", "Updates", "off", "Not a git copy, so it can't update itself.")
    if not ON_PI:
        return check("updates", "Updates", "off", f"Version {v['commit']}. Only the Pi updates itself.")
    if v["local_edits"]:
        return check("updates", "Updates", "bad",
                     "Updates are stuck: files were changed on the Pi (" + ", ".join(v["local_edits"][:3]) + ").",
                     "Press Fix updates. It sets those edits aside (nothing is deleted) and gets the latest version.",
                     "update_force")
    if st and st.get("result") in ("failed", "rolled back"):
        return check("updates", "Updates", "warn", st.get("message", "The last update didn't work."),
                     "Press Update now to try again. If it keeps failing, see the update log below.", "update")
    if on is False:
        return check("updates", "Updates", "warn", "Automatic updates are off.", "Turn them on below.", "autoupdate_on")
    if v.get("behind"):
        return check("updates", "Updates", "ok", f"An update is waiting ({v['behind']} new change"
                     f"{'s' if v['behind'] != 1 else ''}). It installs within 5 minutes.", None, "update")
    return check("updates", "Updates", "ok", f"Up to date (version {v['commit']}).")


def helper_check() -> dict | None:
    if not ON_PI:
        return None
    if admin_installed():
        return None
    return check("helper", "Maintenance buttons", "warn", "Restart, Update and Reboot don't work yet.", SETUP_HINT)


def checkup(scanner, machine) -> list[dict]:
    checks = [power_check(), temperature_check(), camera_check(scanner), *machine_checks(machine),
              database_check(scanner), network_check(), internet_check(), disk_check(), memory_check(),
              updates_check(), helper_check()]
    return [c for c in checks if c]


def overall(checks: list[dict]) -> str:
    states = {c["state"] for c in checks}
    return "bad" if "bad" in states else "warn" if "warn" in states else "ok"


def summary(scanner, machine) -> dict:
    checks = checkup(scanner, machine)
    up = uptime()
    return {
        "overall": overall(checks),
        "checks": checks,
        "on_pi": ON_PI,
        "model": model(),
        "hostname": socket.gethostname(),
        "uptime_s": up,
        "version": version(),
        "update": update_status(),
        "auto_updates": auto_updates_on(),
        "helper": admin_installed(),
        "service": as_service(),
        "wifi": wifi(),
        "ip": ip_address(),
        "tailscale_ip": tailscale_ip(),
        "throttled": [text for bit, text in THROTTLE_BITS.items() if (throttled() or 0) >> bit & 1],
    }


# --- Logs ------------------------------------------------------------------------------

LOGS = {"app": "mtg-sorter", "updates": "mtg-sorter-update", "system": None}


def logs(which: str, lines: int = 200) -> str:
    if which not in LOGS:
        raise ValueError("Pick app, updates or system")
    lines = max(10, min(2000, int(lines)))
    if admin_installed():
        try:
            return admin("logs", which, str(lines))
        except RuntimeError:
            pass
    if not shutil.which("journalctl"):
        raise RuntimeError("Logs are only kept on the Pi. On this computer, look at the terminal running app.py.")
    cmd = ["journalctl", "--no-pager", "-o", "short", "-n", str(lines)]
    cmd += ["-u", LOGS[which]] if LOGS[which] else ["-b", "-p", "warning"]
    ok, out = run(cmd)
    if not ok:
        raise RuntimeError(out or "Couldn't read the logs. " + SETUP_HINT)
    return out


# --- Wi-Fi -----------------------------------------------------------------------------

def add_wifi(ssid: str, password: str):
    """Saves another Wi-Fi network. The Pi joins it on its own when the current one is gone."""
    ssid, password = (ssid or "").strip(), password or ""
    if not 1 <= len(ssid.encode()) <= 32:
        raise ValueError("Type the network's name (up to 32 characters).")
    if password and not 8 <= len(password) <= 63:
        raise ValueError("Wi-Fi passwords are 8 to 63 characters.")
    if "\n" in ssid or "\n" in password:
        raise ValueError("Names and passwords can't have line breaks.")
    admin("wifi-add", input=f"{ssid}\n{password}\n")


def forget_wifi(name: str):
    if not name or "\n" in name:
        raise ValueError("Pick a network.")
    if name == wifi().get("ssid"):
        raise ValueError("That's the network the Pi is using right now, so forgetting it would cut you off.")
    admin("wifi-forget", input=name + "\n")


# --- Backups ---------------------------------------------------------------------------

# What a backup holds, all from data/. Scans (captures/) are big and optional: what the
# scanner learned from them is already in cards.db.
BACKUP_FILES = ["collection.csv", "cards.db", "app_settings.json", "machine_settings.json",
                "vault_prices.json", "usd_cad.json"]


def make_backup(with_scans: bool = False) -> io.BytesIO:
    """A zip of your collection, card database (with training), and settings."""
    buf, data = io.BytesIO(), config.DATA_DIR
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", "MTG sorter backup, " + time.strftime("%Y-%m-%d %H:%M") +
                   ".\nRestore it from the app's Maintenance page.\n")
        for name in BACKUP_FILES:
            path = data / name
            if not path.exists():
                continue
            if name.endswith(".db"):   # copied through SQLite so it's consistent while the app runs
                tmp = data / ".backup.db"
                try:
                    src, dst = sqlite3.connect(path), sqlite3.connect(tmp)
                    with dst:
                        src.backup(dst)
                    src.close(); dst.close()
                    z.write(tmp, name)
                finally:
                    tmp.unlink(missing_ok=True)
            else:
                z.write(path, name)
        if with_scans and (data / "captures").is_dir():
            for path in sorted((data / "captures").rglob("*")):
                if path.is_file():
                    z.write(path, path.relative_to(data).as_posix())
    buf.seek(0)
    return buf


def _safe_member(name: str) -> bool:
    if name in BACKUP_FILES:
        return True
    parts = Path(name).parts
    return (len(parts) >= 2 and parts[0] == "captures" and ".." not in parts
            and not name.startswith("/") and "\\" not in name)


def restore_backup(stream) -> dict:
    """Puts a backup back. The current data is saved in data/backups first, just in case.
    Returns what was restored; the app must restart afterwards to use it."""
    try:
        z = zipfile.ZipFile(stream)
    except zipfile.BadZipFile:
        raise ValueError("That isn't a backup zip file.")
    members = [m for m in z.infolist() if not m.is_dir() and _safe_member(m.filename)]
    if not members:
        raise ValueError("That zip doesn't look like an MTG sorter backup (no collection or card database in it).")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    before = BACKUP_DIR / time.strftime("before-restore-%Y%m%d-%H%M%S.zip")
    before.write_bytes(make_backup(with_scans=False).getvalue())
    for old in sorted(BACKUP_DIR.glob("before-restore-*.zip"))[:-5]:   # keep the last 5
        old.unlink()
    restored = []
    for m in members:
        dest = config.DATA_DIR / m.filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".restoring")
        with z.open(m) as src, open(tmp, "wb") as out:
            shutil.copyfileobj(src, out)
        if m.filename == "cards.db":   # the old database's write-ahead files would confuse the new one
            for extra in ("cards.db-wal", "cards.db-shm"):
                (config.DATA_DIR / extra).unlink(missing_ok=True)
        tmp.replace(dest)
        restored.append(m.filename)
    return {"restored": restored, "saved_first": before.name}


# --- The Maintenance page and its API ---------------------------------------------------

def add_system_routes(app, scanner, machine, web_dir):
    from flask import Response, jsonify, request, send_file, send_from_directory

    def answer(action, then=None):
        try:
            result = action()
        except (ValueError, TypeError) as e:
            return jsonify(error=str(e)), 400
        except RuntimeError as e:
            return jsonify(error=str(e)), 503
        return jsonify(result if isinstance(result, dict) else {"ok": True, "message": then})

    def need_helper():
        if not admin_installed():
            raise RuntimeError(SETUP_HINT)

    @app.get("/maintenance")
    def maintenance_page():
        return send_from_directory(web_dir, "maintenance.html")

    @app.get("/api/health")
    def health():
        """Quick answer for "is it up, and is anything wrong?" (the page header uses it)."""
        checks = checkup(scanner, machine)
        problems = [c for c in checks if c["state"] in ("bad", "warn")]
        return jsonify(alive=True, overall=overall(checks),
                       problems=[{"label": c["label"], "summary": c["summary"], "state": c["state"]}
                                 for c in problems])

    @app.get("/api/system")
    def system_state():
        return jsonify(summary(scanner, machine))

    def soon(*args, message):
        def go():
            need_helper()
            later(*args)
        return answer(go, message)

    @app.post("/api/system/restart")
    def restart():
        return soon("restart", message="Restarting the app. The page comes back in about 10 seconds.")

    @app.post("/api/system/reboot")
    def reboot():
        return soon("reboot", message="Rebooting the Pi. The page comes back in about a minute.")

    @app.post("/api/system/poweroff")
    def poweroff():
        return soon("poweroff", message="Shutting down. Unplug it once the green light on the Pi stops flashing.")

    @app.post("/api/system/update")
    def update():
        force = bool((request.get_json(silent=True) or {}).get("force"))
        # The update restarts the app when there's something new, so it runs after answering.
        return soon("update-force" if force else "update",
                    message="Checking GitHub. If there's a new version the app restarts with it in a minute.")

    @app.post("/api/system/autoupdate")
    def autoupdate():
        on = bool((request.get_json(silent=True) or {}).get("on"))
        return answer(lambda: admin("autoupdate", "on" if on else "off"),
                      "Automatic updates are " + ("on." if on else "off."))

    @app.get("/api/system/logs")
    def system_logs():
        which, lines = request.args.get("which", "app"), request.args.get("lines", 200)
        try:
            text = logs(which, int(lines))
        except (ValueError, TypeError) as e:
            return jsonify(error=str(e)), 400
        except RuntimeError as e:
            return jsonify(error=str(e)), 503
        if request.args.get("download"):
            return Response(text, mimetype="text/plain", headers={
                "Content-Disposition": f"attachment; filename=mtg-sorter-{which}-log.txt"})
        return jsonify(text=text)

    @app.get("/api/system/backup")
    def backup():
        buf = make_backup(with_scans=bool(request.args.get("scans")))
        return send_file(buf, mimetype="application/zip", as_attachment=True,
                         download_name=time.strftime("mtg-sorter-backup-%Y-%m-%d.zip"))

    @app.post("/api/system/restore")
    def restore():
        f = request.files.get("backup")
        if not f:
            return jsonify(error="Pick a backup zip file."), 400

        def go():
            done = restore_backup(f.stream)
            if admin_installed():
                later("restart")
                done["message"] = "Restored. The app restarts to load it."
            else:
                done["message"] = "Restored. Restart the app (or the Pi) to load it."
            return done
        return answer(go)

    @app.post("/api/system/wifi")
    def wifi_add():
        body = request.get_json(silent=True) or {}
        return answer(lambda: add_wifi(body.get("ssid"), body.get("password")),
                      "Saved. The Pi will join that network by itself whenever it's in range "
                      "and the current one isn't.")

    @app.post("/api/system/wifi/forget")
    def wifi_forget():
        body = request.get_json(silent=True) or {}
        return answer(lambda: forget_wifi(body.get("name")), "Forgotten.")
