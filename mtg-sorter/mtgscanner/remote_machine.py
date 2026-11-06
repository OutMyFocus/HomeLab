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
import threading
import time

import cv2
import numpy as np
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

    def feed_one(self, speed=None, max_seconds=None, zone=None, backoff=None) -> dict:
        """The Pi feeds a card watching its own camera (feed_watch.py) and says what happened."""
        return self._call("/api/machine/feed_one", {"speed": speed, "max_seconds": max_seconds, "zone": zone,
                                                    "backoff": backoff}, timeout=(2, 15))

    def drop(self, bin_no, pins_seconds=None, doors_seconds=None, tilt_seconds=None):
        self._call("/api/machine/drop", {"bin": bin_no, "pins_seconds": pins_seconds,
                                         "doors_seconds": doors_seconds, "tilt_seconds": tilt_seconds},
                   timeout=(2, 30))

    def sort_one(self, bin_no, speed=None, drop=None, backoff=None) -> dict:
        return self._call("/api/machine/sort_one", {"bin": bin_no, "speed": speed, "drop": drop, "backoff": backoff},
                          timeout=(2, 60))

    def sort_defaults(self) -> dict:
        return self.state().get("sort_defaults", {})

    def save_sort(self, **timings):
        self._call("/api/machine/save", {"sort": timings})

    # the tuning run (tuning.py) happens on the Pi; these pass the page's calls on
    def tune_start(self, body: dict) -> dict:
        return self._call("/api/machine/tune", body)

    def tune_status(self) -> dict:
        return self._call("/api/machine/tune")

    def tune_stop(self) -> dict:
        return self._call("/api/machine/tune/stop", {})

    def tune_save(self) -> dict:
        return self._call("/api/machine/tune/save", {}, timeout=(2, 15))

    # the sort run (sort_run.py) happens on the Pi too, with the Pi's scanner
    def sort_start(self, body: dict) -> dict:
        return self._call("/api/machine/sort", body)

    def sort_status(self) -> dict:
        return self._call("/api/machine/sort")

    def sort_stop(self) -> dict:
        return self._call("/api/machine/sort/stop", {})

    def feed_zone(self) -> list:
        return self._call("/api/machine/feed_zone")["zone"]

    def save_feed_zone(self, zone):
        self._call("/api/machine/feed_zone", {"zone": zone})

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


# What the server may ask of a locked Pi with the machine key: the moving parts, the light
# bars, the camera's focus, and the camera's live stream (RemoteCameraSource).
SERVER_PATHS = ("/api/machine", "/api/lights", "/api/camera/focus", "/stream.mjpg")


def server_allowed() -> bool:
    """True for a request to the machine, lights or camera that carries this Pi's machine key,
    so the server can use them even with a PIN or accounts on. No key file: no way in."""
    if not request.path.startswith(SERVER_PATHS):
        return False
    given = request.headers.get(KEY_HEADER, "")
    try:
        key = key_file().read_text().strip()
    except OSError:
        return False
    return bool(key) and bool(given) and hmac.compare_digest(given, key)


class RemoteLights:
    """The Pi's light bars, driven from the server's Lights page: the same methods as
    lights.Lights, each one a request to the Pi's own /api/lights. The Pi's scanner flashes
    its lights itself, so event() does nothing here."""

    def __init__(self, url: str, key: str | None = None):
        self.link = RemoteMachine(url, key)
        self.url = self.link.url
        from .lights import Lights
        self._local = Lights()   # never started: only the page's defaults while the Pi is away

    @property
    def http(self):
        return self.link.http

    @http.setter
    def http(self, session):
        self.link.http = session

    def start(self):
        pass

    def event(self, name: str):
        pass

    def state(self) -> dict:
        try:
            s = self.link._call("/api/lights")
        except (RuntimeError, ValueError) as e:
            s = self._local.state() | {"ok": False, "error": str(e)}
        s["remote"] = self.url
        return s

    def preview(self) -> list[str]:
        try:
            return list(self.link._call("/api/lights/preview").get("colors") or [])
        except (RuntimeError, ValueError):
            return []

    def update(self, raw: dict):
        self.link._call("/api/lights", dict(raw))

    def flash(self, event: str, force: bool = False):
        self.link._call("/api/lights/flash", {"event": event})

    def reset(self):
        self.link._call("/api/lights/reset", {})

    def spi_on(self) -> str:
        return str(self.link._call("/api/lights/spi-on", {}).get("message") or "")


class RemoteCameraSource:
    """The sorter Pi's camera, watched from the server: the Pi's live stream (/stream.mjpg)
    becomes the server scanner's pictures, so the server's Scan page shows and recognizes
    what the machine sees. The same read()/info()/release() as CameraSource."""
    index = "pi"
    format = "MJPG"
    RETRY = 2.0        # seconds between attempts when the Pi can't be reached

    def __init__(self, url: str, key: str | None = None, name: str | None = None, http=None):
        self.url = url.rstrip("/")
        self.key = key if key is not None else (os.environ.get("MTG_MACHINE_KEY") or "").strip()
        self.name = name or "Sorter's Pi camera"
        self.http = http or requests.Session()
        self.size = None
        self.camera_fps = None
        self.error: str | None = "Connecting to the sorter's Pi…"
        self._cond = threading.Condition()
        self._frame, self._seq, self._given, self._stop = None, 0, 0, False
        self._count, self._since = 0, time.monotonic()
        self._resp = None
        self._thread = threading.Thread(target=self._pump, name="pi-camera", daemon=True)
        self._thread.start()

    # --- pulling the stream --------------------------------------------------------

    def _pump(self):
        while not self._stop:
            try:
                self._watch()
            except requests.RequestException:
                self.error = f"Can't reach the sorter's Pi at {self.url}. Is it on, and is the app running there?"
            except Exception as e:   # a bad chunk mustn't kill the thread
                self.error = str(e) or "The Pi's stream broke off"
            with self._cond:
                self._cond.wait_for(lambda: self._stop, self.RETRY)

    def _watch(self):
        headers = {KEY_HEADER: self.key} if self.key else {}
        with self.http.get(self.url + "/stream.mjpg?full=1", headers=headers, stream=True, timeout=(2, 15)) as r:
            self._resp = r
            if r.status_code in (401, 403):
                self.error = ("The sorter's Pi has a PIN or accounts on, so it refused. Put the Pi's "
                              "data/machine_key in MTG_MACHINE_KEY on this server (deploy/PI_DOCKER.md).")
                return
            if r.status_code != 200:
                self.error = f"The sorter's Pi answered {r.status_code} for its camera stream."
                return
            buf = b""
            for chunk in r.iter_content(chunk_size=65536):
                if self._stop:
                    return
                buf += chunk
                # One JPEG per frame, from its start marker to its end marker.
                while True:
                    start = buf.find(b"\xff\xd8")
                    if start < 0:
                        buf = buf[-1:]
                        break
                    end = buf.find(b"\xff\xd9", start + 2)
                    if end < 0:
                        buf = buf[start:]
                        break
                    jpeg, buf = buf[start:end + 2], buf[end + 2:]
                    self._push(jpeg)
            self.error = "The Pi's stream ended."

    def _push(self, jpeg: bytes):
        frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return
        now = time.monotonic()
        self._count += 1
        if now - self._since >= 2.0:
            self.camera_fps, self._count, self._since = self._count / (now - self._since), 0, now
        with self._cond:
            self._frame, self._seq = frame, self._seq + 1
            self.size = (frame.shape[1], frame.shape[0])
            self.error = None
            self._cond.notify_all()

    # --- the same face as CameraSource ---------------------------------------------

    def read(self, timeout: float = 2.0):
        """The newest picture not handed out yet (None while the Pi sends nothing)."""
        with self._cond:
            seq = self._given
            if not self._cond.wait_for(lambda: self._seq > seq or self._stop, timeout) or self._stop:
                return None
            self._given = self._seq
            return self._frame

    def info(self) -> dict:
        out = {"index": self.index, "name": self.name, "format": self.format,
               "size": list(self.size) if self.size else None, "remote": self.url, "pi": True}
        if self.camera_fps is not None:
            out["fps"] = round(self.camera_fps, 1)
        if self.error:
            out["error"] = self.error
        return out

    def set_focus(self, cm: float | None) -> bool:
        """Focus is the Pi camera's: the ask goes to the Pi's own /api/camera/focus."""
        link = RemoteMachine(self.url, self.key)
        link.http = self.http
        try:
            link._call("/api/camera/focus", {"cm": cm})
        except (RuntimeError, ValueError):
            return False
        return True

    def release(self):
        self._stop = True
        with self._cond:
            self._cond.notify_all()
        resp, self._resp = self._resp, None
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass

