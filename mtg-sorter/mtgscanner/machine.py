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


def last_angles_file():
    return config.DATA_DIR / "servo_last.json"


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
        self._relax_timers = {}   # channel -> timer that lets that servo go after a move

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
                "speed": float(saved.get("speed", config.FEEDER_SPEED)),
                "reverse": bool(saved.get("reverse", False))}

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
        feeder = saved.setdefault("feeder", {})
        feeder.update(seconds=round(min(5.0, max(0.05, float(seconds))), 2),
                      speed=round(min(1.0, max(0.1, float(speed))), 2))
        self._write(saved)

    def set_feeder_reverse(self, on: bool):
        """For a motor fitted the other way round: "forward" then turns it backwards."""
        saved = load_saved()
        saved.setdefault("feeder", {})["reverse"] = bool(on)
        self._write(saved)

    def reset_saved(self):
        """Back to the angles and feeder settings in config.py. The old file is kept as
        machine_settings.json.bak, so a reset pressed by mistake can be undone by hand."""
        f = settings_file()
        if f.exists():
            f.replace(f.with_name(f.name + ".bak"))

    def wide_travel(self) -> bool:
        return bool(load_saved().get("wide_travel", config.SERVO_WIDE_TRAVEL))

    def home_at_startup(self) -> bool:
        return bool(load_saved().get("home_at_startup", config.HOME_AT_STARTUP))

    def set_home_at_startup(self, on: bool):
        saved = load_saved()
        saved["home_at_startup"] = bool(on)
        self._write(saved)

    def pulse_range(self) -> tuple[int, int]:
        """The servo pulse widths (microseconds) that 0 and 180 mean. ServoKit's default
        750-2250 only turns an MG90S about 130-140 real degrees; 500-2500 gives about the
        full 180. 90 is 1500 either way, so a horn fitted at 90 stays put."""
        return config.SERVO_PULSE_WIDE if self.wide_travel() else config.SERVO_PULSE

    def set_wide_travel(self, on: bool):
        saved = load_saved()
        saved["wide_travel"] = bool(on)
        self._write(saved)

    # --- servos -------------------------------------------------------------

    def set_angle(self, channel: int, angle: float | None):
        """Move one servo (0-180), or relax it with None so it stops holding."""
        if not 0 <= channel <= 15:
            raise ValueError("Channel must be 0-15")
        if angle is not None:
            angle = max(0.0, min(180.0, float(angle)))
        with self.lock:
            kit = self._fresh_servos()
            if kit is None:
                raise RuntimeError(self.servo_error)
            try:
                servo = kit.servo[channel]
                if hasattr(servo, "set_pulse_width_range"):   # cheap: no I2C, just the scale
                    servo.set_pulse_width_range(*self.pulse_range())
                servo.angle = angle
            except OSError:
                self._kit = None   # board unplugged or lost: find it again next time
                raise
            self.angles[channel] = angle
            if angle is not None:
                self._remember(channel, angle)
            old = self._relax_timers.pop(channel, None)
            if old:
                old.cancel()
            keep = {config.SERVOS[p][0] for p in getattr(config, "SERVO_KEEP_HOLDING", ())
                    if p in config.SERVOS}
            # Let go once it has had time to get there. A servo held against something it
            # can't push past draws full current and gets hot. Parts that have to keep
            # holding (the gate, the doors) still let go after SERVO_HOLD_LIMIT with no new
            # move, so one jammed at a stop can't cook its servo.
            hold = (getattr(config, "SERVO_HOLD_LIMIT", 0) if channel in keep
                    else getattr(config, "SERVO_HOLD_SECONDS", 0))
            if angle is not None and hold > 0:
                token = object()
                t = threading.Timer(hold, self._relax_after_move, (channel, token))
                t.daemon = True
                t.token = token
                self._relax_timers[channel] = t
                t.start()

    def _remember(self, channel: int, angle: float):
        """Keep the last angle sent to each servo in data/servo_last.json, so homing after
        a restart can sweep from where the part was instead of jumping."""
        last = self.last_angles()
        if last.get(str(channel)) == angle:
            return
        last[str(channel)] = angle
        try:
            config.DATA_DIR.mkdir(parents=True, exist_ok=True)
            tmp = last_angles_file().with_suffix(".tmp")
            tmp.write_text(json.dumps(last))
            tmp.replace(last_angles_file())
        except OSError:
            pass   # only a nicety: homing then just goes straight there

    def last_angles(self) -> dict:
        try:
            last = json.loads(last_angles_file().read_text())
            return last if isinstance(last, dict) else {}
        except (OSError, ValueError):
            return {}

    def _relax_after_move(self, channel, token):
        with self.lock:
            t = self._relax_timers.get(channel)
            if t is None or t.token is not token:
                return            # moved again since: that move has its own timer
            self._relax_timers.pop(channel, None)
            try:
                if self._kit is not None:
                    self._kit.servo[channel].angle = None
                    self.angles[channel] = None
            except OSError:
                self._kit = None

    def _fresh_servos(self):
        """The servo board, set up again if it lost power since we last used it.

        A PCA9685 forgets its 50 Hz setting when its power goes off and on, and wakes
        up asleep. Moves sent to it then do nothing, so check and start over if so."""
        kit = self._servos()
        if kit is None:
            return None
        try:
            asleep = kit._pca.mode1_reg & 0x10
        except (AttributeError, OSError):
            asleep = False     # can't tell (fake board in tests, or a read error): carry on
        if asleep:
            self._kit = None
            kit = self._servos()
        return kit

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

    def home(self, pause: float = 0.4, speed: float | None = None):
        """Every part to its home position (config.SERVO_HOME), with the saved angles, one
        at a time so they don't all draw current at once. Each one sweeps there slowly
        (config.SERVO_HOME_SPEED degrees a second) from the last angle it was sent, so
        nothing slams into a stop; a part with no last angle goes straight there."""
        speed = speed or config.SERVO_HOME_SPEED
        servos, last = self.servos(), self.last_angles()
        for part, position in config.SERVO_HOME.items():
            if part not in servos or position not in servos[part][1]:
                continue
            channel, target = servos[part][0], float(servos[part][1][position])
            start = last.get(str(channel))
            if isinstance(start, (int, float)) and speed > 0:
                steps = int(abs(target - start) // 2)            # 2 degree steps
                for i in range(1, steps + 1):
                    self.set_angle(channel, start + (target - start) * i / (steps + 1))
                    time.sleep(2 / speed)
            self.set_angle(channel, target)
            time.sleep(pause)

    def drop(self, bin_no: int, pins_seconds=None, doors_seconds=None, tilt_seconds=None):
        """Send the card on the bed to a bin (config.SORT_BINS): drop the stop pins so the
        card slides onto the level tray, then open the trapdoors (bin 2) or tilt the chute
        to the side (bins 1 and 3); then put everything back. About 6 s. Nothing watches the
        camera here (sort_one in feed_watch.py does that). The tray stays level while the
        card slides: tilted first, the card turns as it comes down and catches on the rail
        (seen on the right side, 2026-11-06)."""
        bins = getattr(config, "SORT_BINS", {1: "left", 2: "centre", 3: "right"})
        try:
            position = bins[int(bin_no)]
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"No such bin: {bin_no!r} (bins are {', '.join(map(str, bins))})")
        pins_seconds = float(config.SORT_PINS_SECONDS if pins_seconds is None else pins_seconds)
        doors_seconds = float(config.SORT_DOORS_SECONDS if doors_seconds is None else doors_seconds)
        tilt_seconds = float(config.SORT_TILT_SECONDS if tilt_seconds is None else tilt_seconds)
        use_doors = int(bin_no) == getattr(config, "SORT_DOOR_BIN", 2)
        servos = self.servos()
        if "chute" not in servos or position not in servos["chute"][1]:
            raise ValueError(f"The chute has no '{position}' position: set it on the Machine page")

        def hold(where, seconds):
            # The chute lets go SERVO_HOLD_SECONDS after a move (so a stalled servo can't
            # cook); a tray left loose sags under the card, so send the angle again meanwhile.
            end = time.monotonic() + seconds
            while True:
                left = end - time.monotonic()
                if left <= 0:
                    return
                time.sleep(min(1.0, left))
                self.move("chute", where)

        try:
            self.move("chute", "centre")
            self.move("pins", "down")
            hold("centre", pins_seconds)            # the card slides onto the level tray
            if use_doors:
                self.move("door_r", "open")
                self.move("door_l", "open")
                hold("centre", doors_seconds)
                self.move("door_r", "closed")
                self.move("door_l", "closed")
                hold("centre", 0.4)
            else:
                self.move("chute", position)
                hold(position, tilt_seconds)        # and off the side of the tilted tray
        finally:
            self.move("chute", "centre")
            self.move("pins", "up")

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
            if defaults["reverse"]:
                backward = not backward
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
                "wide_travel": self.wide_travel(),
                "home_at_startup": self.home_at_startup(),
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

    @app.post("/api/machine/home")
    def machine_home():
        return answer(machine.home)

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

    @app.post("/api/machine/drop")
    def machine_drop():
        """Send the card on the bed to a bin (no feeding, no camera)."""
        body = request.get_json(silent=True) or {}
        return answer(lambda: machine.drop(body.get("bin"), body.get("pins_seconds"),
                                           body.get("doors_seconds"), body.get("tilt_seconds")))

    @app.post("/api/machine/save")
    def machine_save():
        """Keep an angle as a named position, or the feeder's seconds and speed."""
        body = request.get_json(silent=True) or {}
        if "part" in body:
            return answer(lambda: machine.save_position(str(body["part"]), str(body.get("position")),
                                                        body.get("angle")))
        if "home_at_startup" in body:
            return answer(lambda: machine.set_home_at_startup(bool(body["home_at_startup"])))
        if "wide_travel" in body:
            return answer(lambda: machine.set_wide_travel(bool(body["wide_travel"])))
        if "reverse" in body and "seconds" not in body:
            return answer(lambda: machine.set_feeder_reverse(bool(body["reverse"])))
        return answer(lambda: machine.save_feeder(body.get("seconds"), body.get("speed")))

    @app.post("/api/machine/reset")
    def machine_reset():
        return answer(machine.reset_saved)

    @app.post("/api/machine/test")
    def machine_test():
        report = machine.self_test()
        return jsonify(machine.state() | {"test": report})


def home_at_startup(machine: Machine, tries: int = 3, wait: float = 5.0):
    """Run once when the app starts (app.py main): put every part in its home position with
    the saved angles, unless that's turned off on the Machine page. The servo board can
    take a moment to show up after boot, so it tries a few times."""
    if not machine.home_at_startup():
        return
    for attempt in range(tries):
        try:
            machine.home()
            print("Machine: every part is at its home position.")
            return
        except (RuntimeError, OSError, ValueError) as e:
            error = e
            if attempt < tries - 1:
                time.sleep(wait)
    print(f"Machine: couldn't go to the home positions at startup ({error}).")
