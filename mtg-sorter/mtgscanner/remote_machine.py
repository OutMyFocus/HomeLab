"""The sorter's moving parts, driven from another computer over the network.

The servos and feeder are wired to the Pi, but the app also runs on a server (tower, see
deploy/UNRAID.md). Give the server the Pi's address and its Machine page, Home page and
check-up send every move to the Pi's own /api/machine instead of looking for hardware it
doesn't have:

    MTG_MACHINE_URL=http://10.0.0.247:5000      the Pi (its LAN or Tailscale address)
    MTG_MACHINE_KEY=<the Pi's data/machine_key>  only if the Pi has a PIN or accounts on

RemoteMachine has the same methods as machine.Machine, so add_machine_routes and the rest
of the app use it without knowing the difference. Saved angles stay on the Pi.
"""

import copy
import hmac
import os
import time

import requests
from flask import request

from . import config

TIMEOUT = (2, 6)      # seconds to connect, then to answer; a move answers in well under one
DOWN_PAUSE = 20       # after the Pi didn't answer, report it as down this long without asking again
KEY_HEADER = "X-Machine-Key"


def remote_url() -> str | None:
    url = (os.environ.get("MTG_MACHINE_URL") or "").strip().rstrip("/")
    return url or None


class RemoteMachine:
    def __init__(self, url: str, key: str | None = None):
        self.url = url.rstrip("/")
        self.key = key if key is not None else (os.environ.get("MTG_MACHINE_KEY") or "").strip()
        self.http = requests.Session()
        self._down_until = 0.0   # every page's header runs the check-up, so a Pi that's off
        self._down_error = ""    # mustn't make each one wait for a timeout

    # --- talking to the Pi ---------------------------------------------------

    def _call(self, path: str, body: dict | None = None, timeout: float = TIMEOUT) -> dict:
        headers = {KEY_HEADER: self.key} if self.key else {}
        try:
            if body is None:
                r = self.http.get(self.url + path, headers=headers, timeout=timeout)
            else:
                r = self.http.post(self.url + path, json=body, headers=headers, timeout=timeout)
        except requests.RequestException:
            raise RuntimeError(f"Can't reach the sorter's Pi at {self.url}. Is it on, and is the app running there?")
        self._down_until = 0.0
        try:
            data = r.json()
        except ValueError:
            data = {}
        if r.status_code in (401, 403):
            raise RuntimeError("The sorter's Pi has a PIN or accounts on, so it refused. Put the Pi's "
                               "data/machine_key in MTG_MACHINE_KEY on this server (deploy/PI_DOCKER.md).")
        if r.status_code == 400:
            raise ValueError(data.get("error") or "The Pi didn't accept that.")
        if r.status_code >= 300 or not isinstance(data, dict):
            raise RuntimeError(data.get("error") if isinstance(data, dict) and data.get("error")
                               else f"The sorter's Pi answered with an error ({r.status_code}).")
        return data

    # --- the same methods as Machine ----------------------------------------------

    def state(self) -> dict:
        try:
            if time.monotonic() < self._down_until:
                raise RuntimeError(self._down_error)
            s = self._call("/api/machine")
        except (RuntimeError, ValueError) as e:
            if time.monotonic() >= self._down_until:
                self._down_until, self._down_error = time.monotonic() + DOWN_PAUSE, str(e)
            # Still show the parts (with config.py's angles) so the page draws, greyed by the error.
            parts = {part: {"channel": ch, "positions": copy.deepcopy(pos), "factory": pos, "angle": None}
                     for part, (ch, pos) in config.SERVOS.items()}
            return {"servos": {"ok": False, "error": str(e)},
                    "feeder": {"ok": False, "error": str(e), "running": False},
                    "parts": parts, "customized": False, "remote": self.url,
                    "feeder_defaults": {"seconds": config.FEEDER_SECONDS, "speed": config.FEEDER_SPEED,
                                        "reverse": False},
                    "wide_travel": config.SERVO_WIDE_TRAVEL, "home_at_startup": config.HOME_AT_STARTUP}
        self._down_until = 0.0
        s["remote"] = self.url
        return s

    def servos(self) -> dict:
        return {part: (p["channel"], p["positions"]) for part, p in self.state()["parts"].items()}

    def feeder_defaults(self) -> dict:
        return self.state()["feeder_defaults"]

    def move(self, part: str, position: str):
        self._call("/api/machine/move", {"part": part, "position": position})

    def set_angle(self, channel: int, angle: float | None):
        self._call("/api/machine/move", {"channel": channel, "angle": angle})

    def relax_all(self):
        self._call("/api/machine/relax", {})

    def home(self):
        self._call("/api/machine/home", {}, timeout=(2, 15))

    def set_home_at_startup(self, on: bool):
        self._call("/api/machine/save", {"home_at_startup": bool(on)})

    def feed(self, seconds: float = None, speed: float = None, backward: bool = False):
        self._call("/api/machine/feed", {"seconds": seconds, "speed": speed, "backward": backward})

    def stop_feeder(self):
        self._call("/api/machine/stop", {})

    def save_position(self, part: str, position: str, angle: float):
        self._call("/api/machine/save", {"part": part, "position": position, "angle": angle})

    def save_feeder(self, seconds: float, speed: float):
        self._call("/api/machine/save", {"seconds": seconds, "speed": speed})

    def set_feeder_reverse(self, on: bool):
        self._call("/api/machine/save", {"reverse": bool(on)})

    def set_wide_travel(self, on: bool):
        self._call("/api/machine/save", {"wide_travel": bool(on)})

    def reset_saved(self):
        self._call("/api/machine/reset", {})

    def self_test(self, pause: float = 0.6) -> list[dict]:
        try:
            return self._call("/api/machine/test", {}, timeout=(2, 60)).get("test", [])
        except (RuntimeError, ValueError) as e:
            return [{"part": "machine", "ok": False, "detail": str(e)}]


# --- the Pi's side: letting the server in ----------------------------------------------

def key_file():
    return config.DATA_DIR / "machine_key"


def server_allowed() -> bool:
    """True for a request to /api/machine that carries this Pi's machine key, so the server
    can drive the machine even with a PIN or accounts on. No key file: no way in."""
    if not request.path.startswith("/api/machine"):
        return False
    given = request.headers.get(KEY_HEADER, "")
    try:
        key = key_file().read_text().strip()
    except OSError:
        return False
    return bool(key) and bool(given) and hmac.compare_digest(given, key)
