"""The RGB light bars: 5 V addressable LEDs (WS2812, "3-pin ARGB") driven from the Pi.

The bars need one data wire. It goes to GPIO10 (pin 19), the Pi's SPI MOSI pin, and the
app sends the LED colors over SPI. (The usual LED library, rpi_ws281x, doesn't work on a
Pi 5, and SPI needs no extra package.) Each bit an LED expects becomes one SPI byte: a
short pulse (0b11000000) for 0, a long one (0b11111000) for 1, at 6.4 MHz.

One strip can do two jobs. The first LEDs ("count") are the status lights behind the
fascia slots: they take the color, effect and flashes. The LEDs chained after them ("card"
LEDs) light the scan bed for the camera: they stay one steady color and never flash, so the
picture's colors don't change while a card is being read.

Like the rest of the machine, nothing fails without the bars: on a PC, or with SPI off,
the Lights page says what's missing, and the preview on the page still shows what the
bars would do. The Pi can't tell whether bars are plugged in, because LEDs only listen.

The Lights page (/lights) sets the color, brightness and effect, and the colors the bars
flash when a card is saved, valuable, unsure or not recognized. Those are kept in
data/lights.json. Pins and limits are in config.py.
"""

import colorsys
import fcntl
import json
import math
import os
import re
import struct
import threading
import time
from pathlib import Path

import numpy as np
from flask import jsonify, request, send_from_directory

from . import config

EFFECTS = {"solid": "Solid", "breathe": "Breathe", "rainbow": "Rainbow", "sweep": "Sweep"}
EVENTS = {   # what the scanner can flash, and its starting color
    "saved": ("Card saved", "#1fd65f"),
    "valuable": ("Valuable or wishlist card", "#ffb000"),
    "unsure": ("Not sure which card it is", "#ff6a00"),
    "unknown": ("Card not recognized", "#ff1a1a"),
}
DEFAULTS = {
    "on": True,
    "color": "#ff7a1a",      # the enclosure's orange
    "brightness": 30,        # percent. Low on purpose: the 5 V supply is shared with everything
    "effect": "solid",
    "speed": 50,             # percent, for the moving effects
    "count": config.LIGHTS_COUNT,
    "flashes": True,
    "events": {k: {"on": True, "color": c} for k, (_, c) in EVENTS.items()},
    # the card light: LEDs chained after the status lights, in the scan bed walls
    "card": {"on": True, "count": config.LIGHTS_CARD_COUNT, "color": "#ffffff",
             "brightness": config.LIGHTS_CARD_BRIGHTNESS},
}
MAX_LEDS = 150         # one SPI write holds 4096 bytes: 150 LEDs x 24 bytes plus the reset
FLASH_SECONDS = 1.4
MA_PER_CHANNEL = 20.0  # an LED's red, green or blue at full draws about 20 mA
MA_IDLE = 1.0          # and each LED draws about 1 mA even when dark

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

# Linux spidev ioctls (from linux/spi/spidev.h): _IOW('k', nr, size).
SPI_IOC_WR_MODE = 0x40016B01
SPI_IOC_WR_BITS_PER_WORD = 0x40016B03
SPI_IOC_WR_MAX_SPEED_HZ = 0x40046B04


def settings_file() -> Path:
    return config.DATA_DIR / "lights.json"


def _bit_table() -> np.ndarray:
    """table[v] is the 8 SPI bytes that send the byte v to an LED."""
    t = np.zeros((256, 8), np.uint8)
    for v in range(256):
        for b in range(8):
            t[v, b] = 0b11111000 if v >> (7 - b) & 1 else 0b11000000
    return t


BITS = _bit_table()
LEAD = bytes(8)       # a moment of quiet first
RESET = bytes(240)    # then ~300 microseconds low after the colors, which makes the LEDs show them


def encode(pixels: np.ndarray, order: str = "GRB") -> bytes:
    """(n, 3) RGB bytes -> what goes out on the SPI pin."""
    idx = ["RGB".index(c) for c in order]
    return LEAD + BITS[pixels[:, idx].reshape(-1)].tobytes() + RESET


def to_rgb(hex_color: str) -> np.ndarray:
    return np.array([int(hex_color[i:i + 2], 16) for i in (1, 3, 5)], float)


def to_hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb)


def amps(pixels: np.ndarray) -> float:
    """Roughly how much current the bars draw showing these colors."""
    return (pixels.sum() / 255 * MA_PER_CHANNEL + len(pixels) * MA_IDLE) / 1000


def limit_power(pixels: np.ndarray, max_amps: float) -> np.ndarray:
    """Dims the whole picture evenly if it would draw more than max_amps."""
    idle = len(pixels) * MA_IDLE / 1000
    lit = pixels.sum() / 255 * MA_PER_CHANNEL / 1000
    if lit + idle <= max_amps or lit <= 0:
        return pixels
    return pixels * max(0.0, (max_amps - idle) / lit)


def clean(raw: dict, old: dict) -> dict:
    """Checks what the page sent, on top of the current settings. Raises ValueError."""
    s = json.loads(json.dumps(old))
    if "on" in raw:
        s["on"] = bool(raw["on"])
    if "flashes" in raw:
        s["flashes"] = bool(raw["flashes"])
    if "color" in raw:
        if not HEX.match(str(raw["color"])):
            raise ValueError("Color has to look like #ff7a1a")
        s["color"] = raw["color"].lower()
    if "effect" in raw:
        if raw["effect"] not in EFFECTS:
            raise ValueError("Unknown effect")
        s["effect"] = raw["effect"]
    for key, lo, hi in (("brightness", 0, 100), ("speed", 1, 100), ("count", 0, MAX_LEDS)):
        if key in raw:
            s[key] = _number(raw[key], lo, hi, key.capitalize())
    card = raw.get("card")
    if card is not None:
        if not isinstance(card, dict):
            raise ValueError("Card light settings have to be a list of values")
        if "on" in card:
            s["card"]["on"] = bool(card["on"])
        if "color" in card:
            if not HEX.match(str(card["color"])):
                raise ValueError("Color has to look like #ffffff")
            s["card"]["color"] = card["color"].lower()
        for key, hi in (("count", MAX_LEDS), ("brightness", 100)):
            if key in card:
                s["card"][key] = _number(card[key], 0, hi, f"Card light {key}")
    if s["count"] + s["card"]["count"] > MAX_LEDS:
        raise ValueError(f"That's more than {MAX_LEDS} LEDs together")
    for name, ev in (raw.get("events") or {}).items():
        if name not in EVENTS or not isinstance(ev, dict):
            raise ValueError(f"Unknown flash: {name}")
        if "on" in ev:
            s["events"][name]["on"] = bool(ev["on"])
        if "color" in ev:
            if not HEX.match(str(ev["color"])):
                raise ValueError("Color has to look like #ff7a1a")
            s["events"][name]["color"] = ev["color"].lower()
    return s


def _number(v, lo: int, hi: int, name: str) -> int:
    try:
        return int(max(lo, min(hi, round(float(v)))))
    except (TypeError, ValueError):
        raise ValueError(f"{name} has to be a number")


def load_settings() -> dict:
    s = json.loads(json.dumps(DEFAULTS))
    try:
        saved = json.loads(settings_file().read_text())
        if isinstance(saved, dict):
            s = clean(saved, s)
    except (OSError, ValueError):
        pass
    return s


class SpiOut:
    """Writes bytes to /dev/spidevB.D with the Linux spidev driver (no package needed)."""

    def __init__(self, bus: int, device: int, hz: int):
        self.path = f"/dev/spidev{bus}.{device}"
        self.fd = os.open(self.path, os.O_WRONLY)
        try:
            fcntl.ioctl(self.fd, SPI_IOC_WR_MODE, struct.pack("B", 0))
            fcntl.ioctl(self.fd, SPI_IOC_WR_BITS_PER_WORD, struct.pack("B", 8))
            fcntl.ioctl(self.fd, SPI_IOC_WR_MAX_SPEED_HZ, struct.pack("I", hz))
        except OSError:
            os.close(self.fd)
            raise

    def write(self, data: bytes):
        os.write(self.fd, data)

    def close(self):
        os.close(self.fd)


def open_spi():
    bus, device = config.LIGHTS_SPI
    return SpiOut(bus, device, config.LIGHTS_SPI_HZ)


def _why(e: Exception) -> str:
    on_pi = Path("/proc/device-tree/model").exists()
    if not on_pi:
        return "Only on the Pi. The preview shows what the bars would do."
    bus, device = config.LIGHTS_SPI
    if isinstance(e, FileNotFoundError):
        return (f"SPI is turned off, so there's no /dev/spidev{bus}.{device}. Press Turn SPI on below, "
                "then reboot.")
    if isinstance(e, PermissionError):
        return ("The app isn't allowed to use SPI. Press Turn SPI on below (it also gives the app "
                "permission), then reboot.")
    return f"Couldn't use SPI ({e})."


class Lights:
    def __init__(self, opener=open_spi):
        self.lock = threading.Lock()
        self._open = opener
        self._out = None
        self._tried = -1e9
        self.error = None
        self.settings = load_settings()
        self._flash = None        # (rgb, started) while a flash is showing
        self._held = 0            # > 0 while a feed watches the camera: the picture must not change
        self._held_at = 0.0
        self._wake = threading.Event()
        self._thread = None
        self.started = time.monotonic()

    # --- the bars -----------------------------------------------------------

    def _device(self):
        """The SPI output, opened on first use and retried every 10 seconds if it failed."""
        now = time.monotonic()
        if self._out is None and now - self._tried > 10:
            self._tried = now
            try:
                self._out = self._open()
                self.error = None
            except Exception as e:   # a PC, SPI off, no permission
                self.error = _why(e)
        return self._out

    def _send(self, frame: np.ndarray):
        out = self._device()
        if out is None:
            return
        # Always the full MAX_LEDS, so LEDs past the count (after lowering it) go dark.
        full = np.zeros((MAX_LEDS, 3), np.uint8)
        full[:len(frame)] = frame[:MAX_LEDS]
        try:
            out.write(encode(full, config.LIGHTS_ORDER))
        except OSError as e:
            self.error = f"Sending to the bars stopped working ({e}). Trying again."
            try:
                out.close()
            except OSError:
                pass
            self._out = None

    def start(self):
        """Starts showing the saved color (once; later calls do nothing)."""
        with self.lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, daemon=True, name="lights")
                self._thread.start()

    def _run(self):
        last = None
        while True:
            with self.lock:
                frame, moving = self.render(time.monotonic())
                if last is None or frame.shape != last.shape or not np.array_equal(frame, last):
                    self._send(frame)
                    last = frame
                elif self._out is None:
                    self._device()   # keep retrying, so turning SPI on is picked up
            self._wake.wait(1 / 40 if moving else 1.0)
            self._wake.clear()

    # --- what to show ---------------------------------------------------------

    def render(self, now: float) -> tuple[np.ndarray, bool]:
        """The colors for every LED right now, and whether they're changing (call with the lock).
        The status lights come first, then the card light chained after them."""
        status, moving = self._render_status(now)
        card = self.settings["card"]
        px = np.zeros((card["count"], 3))
        if card["on"]:
            px[:] = to_rgb(card["color"]) * card["brightness"] / 100
        px = limit_power(np.vstack([status, px]), config.LIGHTS_MAX_AMPS)
        return np.clip(np.rint(px), 0, 255).astype(np.uint8), moving

    def hold(self):
        """Freeze the lights as they are: no effect movement, no flashes. A feed that
        watches the camera (feed_watch.py) tells a card from the bed by what changed in the
        picture, and a colour cycling under it looks like a change (2026-11-06). Every
        hold() needs a release()."""
        with self.lock:
            if self._held == 0:
                self._held_at = time.monotonic()
                self._flash = None
            self._held += 1
        self._wake.set()

    def release(self):
        with self.lock:
            self._held = max(0, self._held - 1)
        self._wake.set()

    def _render_status(self, now: float) -> tuple[np.ndarray, bool]:
        s = self.settings
        n = s["count"]
        level = s["brightness"] / 100
        if self._held:
            now = self._held_at      # the effect stands still
        if not s["on"]:
            return np.zeros((n, 3)), False
        t = now - self.started
        speed = s["speed"] / 50       # 1 at the middle of the slider
        color = to_rgb(s["color"])
        pos = np.arange(n) / max(1, n)
        effect = s["effect"]
        if effect == "breathe":
            k = 0.12 + 0.88 * (0.5 - 0.5 * math.cos(2 * math.pi * t * 0.25 * speed))
            px = np.tile(color * k, (n, 1))
        elif effect == "rainbow":
            px = np.array([colorsys.hsv_to_rgb((p + t * 0.15 * speed) % 1, 1, 1) for p in pos]).reshape(n, 3) * 255
        elif effect == "sweep":
            centre = 0.5 - 0.5 * math.cos(math.pi * t * 0.5 * speed)    # back and forth
            glow = np.clip(1 - np.abs(pos - centre) / 0.18, 0, 1) ** 1.6
            px = np.outer(0.12 + 0.88 * glow, color)
        else:
            px = np.tile(color, (n, 1))
        moving = effect != "solid" and not self._held
        px = px * level
        if self._flash is not None and not self._held:
            rgb, since = self._flash
            age = now - since
            if age >= FLASH_SECONDS:
                self._flash = None
            else:
                w = 1.0 if age < 0.5 else 1 - (age - 0.5) / (FLASH_SECONDS - 0.5)
                px = px * (1 - w) + np.tile(rgb * max(level, 0.25), (n, 1)) * w
                moving = True
        return px, moving

    def flash(self, event: str, force: bool = False):
        """Flashes the color for a scanner event (saved, valuable, unsure, unknown)."""
        with self.lock:
            s = self.settings
            ev = s["events"].get(event)
            if ev is None:
                raise ValueError(f"Unknown flash: {event}")
            if not force and not (s["on"] and s["flashes"] and ev["on"]):
                return
            if self._held:
                return               # a feed is watching the camera: keep the picture still
            self._flash = (to_rgb(ev["color"]), time.monotonic())
        self._wake.set()

    def event(self, name: str):
        """Called by the scanner. Never raises, so lights can't break scanning."""
        try:
            self.flash(name)
        except Exception:
            pass

    def update(self, raw: dict):
        with self.lock:
            self.settings = clean(raw, self.settings)
            config.DATA_DIR.mkdir(parents=True, exist_ok=True)
            tmp = settings_file().with_suffix(".tmp")
            tmp.write_text(json.dumps(self.settings, indent=2))
            tmp.replace(settings_file())
        self._wake.set()

    def reset(self):
        with self.lock:
            settings_file().unlink(missing_ok=True)
            self.settings = load_settings()
        self._wake.set()

    def spi_on(self) -> str:
        """Turns the Pi's SPI bus on through the maintenance helper (needs a reboot after)."""
        from . import system
        return system.admin("spi-on") or "SPI is on. Reboot the Pi to finish."

    # --- for the page -------------------------------------------------------

    def state(self) -> dict:
        with self.lock:
            frame, _ = self.render(time.monotonic())
            self._device()
            return {
                "ok": self._out is not None,
                "error": self.error,
                "settings": self.settings,
                "effects": list(EFFECTS.items()),                 # lists keep the order
                "events": [[k, label] for k, (label, _) in EVENTS.items()],
                "max_count": MAX_LEDS,
                "max_amps": config.LIGHTS_MAX_AMPS,
                "amps": round(amps(frame), 2),
                "full_white_amps": round(len(frame) * (3 * MA_PER_CHANNEL + MA_IDLE) / 1000, 1),
                "pin": "GPIO10 (pin 19)",
            }

    def preview(self) -> list[str]:
        with self.lock:
            return [to_hex(p) for p in self.render(time.monotonic())[0]]


def add_lights_routes(app, lights: Lights, web_dir):
    """The Lights page and its API, added to the scanner app."""

    @app.get("/lights")
    def lights_page():
        return send_from_directory(web_dir, "lights.html")

    def answer(action):
        try:
            action()
        except (ValueError, TypeError) as e:
            return jsonify(error=str(e)), 400
        except RuntimeError as e:
            return jsonify(error=str(e)), 503
        return jsonify(lights.state())

    @app.get("/api/lights")
    def lights_state():
        lights.start()
        return jsonify(lights.state())

    @app.get("/api/lights/preview")
    def lights_preview():
        return jsonify(colors=lights.preview())

    @app.post("/api/lights")
    def lights_set():
        lights.start()
        return answer(lambda: lights.update(request.get_json(silent=True) or {}))

    @app.post("/api/lights/flash")
    def lights_flash():
        body = request.get_json(silent=True) or {}
        return answer(lambda: lights.flash(str(body.get("event")), force=True))

    @app.post("/api/lights/reset")
    def lights_reset():
        return answer(lights.reset)

    @app.post("/api/lights/spi-on")
    def lights_spi_on():
        try:
            out = lights.spi_on()
        except RuntimeError as e:
            return jsonify(error=str(e)), 503
        return jsonify(lights.state() | {"message": out})
