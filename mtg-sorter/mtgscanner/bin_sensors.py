"""Mk2's bin sensors: is each bin full (TCRT5000), and is it in place (A3144 hall sensor)?

The pins are in config.BIN_FULL_PINS and config.BIN_SEATED_PINS (hardware/mk2/MK2.md, Pin
map). Nothing is read until the Machine health page says the sensors are fitted, so pins that
aren't wired yet show as "not connected" instead of a made-up "empty" or "bin out". Which kinds
are fitted is kept in data/bin_sensors.json.

Reading a sensor only listens on a pin: it never moves anything.
"""

import json
import threading

from . import config

KINDS = ("full", "seated")


def settings_file():
    return config.DATA_DIR / "bin_sensors.json"


class BinSensors:
    def __init__(self, make_input=None):
        self.lock = threading.Lock()
        self._inputs = {}           # pin -> the open input
        self.error = None           # why the pins couldn't be opened, if they couldn't
        self._make_input = make_input or self._gpio_input

    # --- which sensors are fitted --------------------------------------------------

    def fitted(self) -> dict:
        try:
            saved = json.loads(settings_file().read_text())
        except (OSError, ValueError):
            saved = {}
        if not isinstance(saved, dict):
            saved = {}
        return {k: bool(saved.get(k, False)) for k in KINDS}

    def set_fitted(self, kind: str, on: bool):
        if kind not in KINDS:
            raise ValueError("Pick full or seated")
        now = self.fitted() | {kind: bool(on)}
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = settings_file().with_suffix(".tmp")
        tmp.write_text(json.dumps(now))
        tmp.replace(settings_file())
        if not on:
            self._close(self._pins(kind))

    # --- the pins ------------------------------------------------------------------

    @staticmethod
    def _pins(kind: str) -> dict:
        return dict(getattr(config, "BIN_FULL_PINS" if kind == "full" else "BIN_SEATED_PINS", {}) or {})

    @staticmethod
    def _gpio_input(pin: int):
        from gpiozero import DigitalInputDevice
        return DigitalInputDevice(pin, pull_up=True)   # with the pull-up, "active" means the pin is low

    def _input(self, pin: int):
        dev = self._inputs.get(pin)
        if dev is None:
            dev = self._make_input(pin)
            self._inputs[pin] = dev
        return dev

    def _close(self, pins: dict):
        with self.lock:
            for pin in pins.values():
                dev = self._inputs.pop(pin, None)
                try:
                    if dev is not None and hasattr(dev, "close"):
                        dev.close()
                except Exception:
                    pass

    def _low(self, pin: int) -> bool:
        return bool(self._input(pin).is_active)

    def read(self) -> dict:
        """Every bin: {"bin", "full", "seated", "full_pin", "seated_pin"}, where full and seated
        are True/False, or None when that sensor isn't fitted (or couldn't be read)."""
        fitted = self.fitted()
        full_pins, seated_pins = self._pins("full"), self._pins("seated")
        rows, errors = [], []
        with self.lock:
            for b in sorted(set(full_pins) | set(seated_pins), key=int):
                row = {"bin": int(b), "full": None, "seated": None,
                       "full_pin": full_pins.get(b), "seated_pin": seated_pins.get(b)}
                for kind, pins, active_low in (("full", full_pins, config.BIN_FULL_ACTIVE_LOW),
                                               ("seated", seated_pins, config.BIN_SEATED_ACTIVE_LOW)):
                    if not fitted[kind] or pins.get(b) is None:
                        continue
                    try:
                        low = self._low(int(pins[b]))
                    except Exception as e:   # not a Pi, or the pin is taken
                        errors.append(f"GPIO{pins[b]}: {e}")
                        continue
                    row[kind] = low if active_low else not low
                rows.append(row)
        self.error = ("Couldn't read the bin sensors (" + "; ".join(errors[:2]) + ")") if errors else None
        return {"fitted": fitted, "bins": rows, "error": self.error}
