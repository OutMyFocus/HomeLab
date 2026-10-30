"""The sorter's moving parts: four servos on the PCA9685 board and the feeder motor.

Nothing here talks to the hardware until it's first used, and nothing fails if the
hardware isn't there (a PC, or a Pi with nothing wired up yet): each part reports
what's missing instead. The Machine page (/machine in the app) uses this to test
every part by hand. Pins, channels and angles are in config.py.
"""

import threading

from flask import jsonify, request, send_from_directory

from . import config


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
            channel, positions = config.SERVOS[part]
            angle = positions[position]
        except KeyError:
            raise ValueError(f"Unknown part or position: {part} {position}")
        self.set_angle(channel, angle)

    def relax_all(self):
        for channel, _ in config.SERVOS.values():
            self.set_angle(channel, None)

    # --- feeder -------------------------------------------------------------

    def feed(self, seconds: float = None, speed: float = None, backward: bool = False):
        """Turn the feeder roller for a moment, then stop on its own."""
        seconds = min(5.0, max(0.05, float(seconds or config.FEEDER_SECONDS)))
        speed = min(1.0, max(0.1, float(speed or config.FEEDER_SPEED)))
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
        with self.lock:
            self._servos()
            self._feeder()
            return {
                "servos": {"ok": self._kit is not None, "error": self.servo_error},
                "feeder": {"ok": self._motor is not None, "error": self.feeder_error,
                           "running": self.feeding},
                "parts": {part: {"channel": ch, "positions": pos,
                                 "angle": self.angles.get(ch)}
                          for part, (ch, pos) in config.SERVOS.items()},
                "feeder_defaults": {"seconds": config.FEEDER_SECONDS, "speed": config.FEEDER_SPEED},
            }


def add_machine_routes(app, machine: Machine, web_dir):
    """The Machine page and its API, added to the scanner app."""

    @app.get("/machine")
    def machine_page():
        return send_from_directory(web_dir, "machine.html")

    def answer(action):
        try:
            action()
        except ValueError as e:
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
