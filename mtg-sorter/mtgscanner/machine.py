"""The sorter's moving parts: four servos on the PCA9685 board and the feeder motor.

Nothing here talks to the hardware until it's first used, and nothing fails if the
hardware isn't there (a PC, or a Pi with nothing wired up yet): each part reports
what's missing instead. The Machine page (/machine in the app) uses this to test
every part by hand. Pins, channels and starting angles are in config.py.

Angles you find and save on the Machine page go in data/machine_settings.json and win
over config.py. That file isn't in git, so saving there never blocks an update (editing
config.py on the Pi would: see deploy/update.sh).
"""

import copy
import json
import threading
import time

from flask import jsonify, request, send_from_directory

from . import config


def settings_file():
    return config.DATA_DIR / "machine_settings.json"


def load_saved() -> dict:
    try:
        saved = json.loads(settings_file().read_text())
        return saved if isinstance(saved, dict) else {}
    except (OSError, ValueError):
        return {}


class Machine:
    def __init__(self):
        self.lock = threading.Lock()
        self._kit = None          # the PCA9685, once found
        self._motor = None        # the feeder motor, once found
        self.servo_error = None   # why the servo board couldn't be used, if it couldn't
        self.feeder_error = None
        self.angles = {}          # last angle sent to each channel (None: relaxed)
        self.feeding = False
        self._stop_timer = None

    # --- connecting ---------------------------------------------------------

    def _servos(self):
        if self._kit is None:
            try:
                from adafruit_servokit import ServoKit
                self._kit = ServoKit(channels=16)
                self.servo_error = None
            except Exception as e:   # not a Pi, I2C off, board not wired
                self.servo_error = f"Servo board not found ({e}). Is I2C on and is it wired to pins 1, 3, 5 and 6?"
        return self._kit

    def _feeder(self):
        if self._motor is None:
            try:
                from gpiozero import Motor
                self._motor = Motor(*config.FEEDER_PINS, pwm=True)
                self.feeder_error = None
            except Exception as e:
                self.feeder_error = f"Feeder motor not available ({e})."
        return self._motor

    # --- settings: config.py, with what was saved on the page on top ---------

    def servos(self) -> dict:
        """{part: (channel, {position: angle})}, with saved angles applied."""
        saved = load_saved().get("servos", {})
        parts = copy.deepcopy(config.SERVOS)
        for part, positions in saved.items():
            if part in parts and isinstance(positions, dict):
                for pos, angle in positions.items():
                    if pos in parts[part][1] and isinstance(angle, (int, float)):
                        parts[part][1][pos] = max(0, min(180, angle))
        return parts

    def feeder_defaults(self) -> dict:
        saved = load_saved().get("feeder", {})
        return {"seconds": float(saved.get("seconds", config.FEEDER_SECONDS)),
                "speed": float(saved.get("speed", config.FEEDER_SPEED))}

    def _write(self, saved: dict):
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = settings_file().with_suffix(".tmp")
        tmp.write_text(json.dumps(saved, indent=2))
        tmp.replace(settings_file())

    def save_position(self, part: str, position: str, angle: float):
        """Keep an angle as a part's named position, e.g. save_position("pins", "down", 58)."""
        if part not in config.SERVOS or position not in config.SERVOS[part][1]:
            raise ValueError(f"Unknown part or position: {part} {position}")
        angle = round(max(0.0, min(180.0, float(angle))), 1)
        saved = load_saved()
        saved.setdefault("servos", {}).setdefault(part, {})[position] = angle
        self._write(saved)

    def save_feeder(self, seconds: float, speed: float):
        saved = load_saved()
        saved["feeder"] = {"seconds": round(min(5.0, max(0.05, float(seconds))), 2),
                           "speed": round(min(1.0, max(0.1, float(speed))), 2)}
        self._write(saved)

    def reset_saved(self):
        """Back to the angles and feeder settings in config.py."""
        settings_file().unlink(missing_ok=True)

    # --- servos -------------------------------------------------------------

    def set_angle(self, channel: int, angle: float | None):
        """Move one servo (0-180), or relax it with None so it stops holding."""
        if not 0 <= channel <= 15:
            raise ValueError("Channel must be 0-15")
        if angle is not None:
            angle = max(0.0, min(180.0, float(angle)))
        with self.lock:
            kit = self._servos()
            if kit is None:
                raise RuntimeError(self.servo_error)
            kit.servo[channel].angle = angle
            self.angles[channel] = angle

    def move(self, part: str, position: str):
        """Move a part to one of its named positions, e.g. move("pins", "down")."""
        try:
            channel, positions = self.servos()[part]
            angle = positions[position]
        except KeyError:
            raise ValueError(f"Unknown part or position: {part} {position}")
        self.set_angle(channel, angle)

    def relax_all(self):
        for channel, _ in config.SERVOS.values():
            self.set_angle(channel, None)

    def self_test(self, pause: float = 0.6) -> list[dict]:
        """Moves every servo through its positions and back, then nudges the feeder.
        Returns what worked, one line per part, for the Maintenance page."""
        report = []
        for part, (channel, positions) in self.servos().items():
            try:
                names = list(positions)
                for pos in names + names[:1]:      # through each one, then back to the first
                    self.move(part, pos)
                    time.sleep(pause)
                self.set_angle(channel, None)
                report.append({"part": part, "ok": True, "detail": "moved to " + ", ".join(names)})
            except (RuntimeError, OSError, ValueError) as e:
                report.append({"part": part, "ok": False, "detail": str(e)})
        try:
            self.feed(seconds=0.3, speed=0.6)
            time.sleep(0.4)
            report.append({"part": "feeder", "ok": True, "detail": "turned for 0.3 seconds"})
        except (RuntimeError, OSError, ValueError) as e:
            report.append({"part": "feeder", "ok": False, "detail": str(e)})
        return report

    # --- feeder -------------------------------------------------------------

    def feed(self, seconds: float = None, speed: float = None, backward: bool = False):
        """Turn the feeder roller for a moment, then stop on its own."""
        defaults = self.feeder_defaults()
        seconds = min(5.0, max(0.05, float(seconds or defaults["seconds"])))
        speed = min(1.0, max(0.1, float(speed or defaults["speed"])))
        with self.lock:
            motor = self._feeder()
            if motor is None:
                raise RuntimeError(self.feeder_error)
            if self._stop_timer:
                self._stop_timer.cancel()
            (motor.backward if backward else motor.forward)(speed)
            self.feeding = True
            self._stop_timer = threading.Timer(seconds, self.stop_feeder)
            self._stop_timer.daemon = True
            self._stop_timer.start()

    def stop_feeder(self):
        with self.lock:
            if self._stop_timer:
                self._stop_timer.cancel()
                self._stop_timer = None
            if self._motor is not None:
                self._motor.stop()
            self.feeding = False

    # --- for the page -------------------------------------------------------

    def state(self) -> dict:
        servos, defaults = self.servos(), self.feeder_defaults()
        with self.lock:
            self._servos()
            self._feeder()
            return {
                "servos": {"ok": self._kit is not None, "error": self.servo_error},
                "feeder": {"ok": self._motor is not None, "error": self.feeder_error,
                           "running": self.feeding},
                "parts": {part: {"channel": ch, "positions": pos,
                                 "factory": config.SERVOS[part][1],
                                 "angle": self.angles.get(ch)}
                          for part, (ch, pos) in servos.items()},
                "feeder_defaults": defaults,
                "customized": settings_file().exists(),
            }


def add_machine_routes(app, machine: Machine, web_dir):
    """The Machine page and its API, added to the scanner app."""

    @app.get("/machine")
    def machine_page():
        return send_from_directory(web_dir, "machine.html")

    def answer(action):
        try:
            action()
        except (ValueError, TypeError) as e:
            return jsonify(error=str(e)), 400
        except RuntimeError as e:
            return jsonify(error=str(e)), 503
        return jsonify(machine.state())

    @app.get("/api/machine")
    def machine_state():
        return jsonify(machine.state())

    @app.post("/api/machine/move")
    def machine_move():
        body = request.get_json(silent=True) or {}
        if "angle" in body:
            return answer(lambda: machine.set_angle(int(body.get("channel", -1)), body["angle"]))
        return answer(lambda: machine.move(str(body.get("part")), str(body.get("position"))))

    @app.post("/api/machine/relax")
    def machine_relax():
        return answer(machine.relax_all)

    @app.post("/api/machine/feed")
    def machine_feed():
        body = request.get_json(silent=True) or {}
        return answer(lambda: machine.feed(body.get("seconds"), body.get("speed"),
                                           bool(body.get("backward"))))

    @app.post("/api/machine/stop")
    def machine_stop():
        return answer(machine.stop_feeder)

    @app.post("/api/machine/save")
    def machine_save():
        """Keep an angle as a named position, or the feeder's seconds and speed."""
        body = request.get_json(silent=True) or {}
        if "part" in body:
            return answer(lambda: machine.save_position(str(body["part"]), str(body.get("position")),
                                                        body.get("angle")))
        return answer(lambda: machine.save_feeder(body.get("seconds"), body.get("speed")))

    @app.post("/api/machine/reset")
    def machine_reset():
        return answer(machine.reset_saved)

    @app.post("/api/machine/test")
    def machine_test():
        report = machine.self_test()
        return jsonify(machine.state() | {"test": report})
