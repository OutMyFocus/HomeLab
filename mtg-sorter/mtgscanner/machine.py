"""The sorter's moving parts: the servos on the PCA9685 board and the feeder motor.

Two machines: the first one (four servos: stop pins, chute tilt, two trapdoors) and Mk2
(five: stop bar, two pushers, two trapdoors). Which one is saved on the Machine page;
each has its own parts, home order and saved angles.

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
import math
import threading
import time

from flask import jsonify, request, send_from_directory

from . import config, health


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


MODELS = {"mk1": "First machine", "mk2": "Sorter Mk2", "mault": "Mault sorter"}


def model_of(saved: dict) -> str:
    """The machine this is: what was saved, else config.MACHINE_MODEL (Mk2; Nic only has that one now)."""
    if saved.get("model") in MODELS:
        return saved["model"]
    return getattr(config, "MACHINE_MODEL", "mk2")


def parts_for(model: str) -> dict:
    """{part: (channel, {position: angle})} as config.py has them, for that machine."""
    if model == "mault":
        return config.SERVOS_MAULT
    return config.SERVOS_MK2 if model == "mk2" else config.SERVOS


def per_model(model: str, name: str, default=None):
    """config.<NAME>_MK2 or _MAULT for those machines, config.<NAME> for the first one."""
    suffix = {"mk2": "_MK2", "mault": "_MAULT"}.get(model, "")
    return getattr(config, name + suffix, default)


class Busy(RuntimeError):
    """Something else is driving the machine right now (a sort run, a tuning run, a card
    being fed): the Machine page's buttons wait until it has stopped."""


def busy_message(who: str) -> str:
    return f"The {who} is using the machine: wait for it to stop, then try again."


def claim(machine, who: str):
    """Mark the machine as driven by `who` ("sort run", "tuning run", ...) until release().
    Raises Busy when something else drives it. Only the Flask routes and the runs' start
    call this, never the moves themselves, since a run's own thread makes those moves.
    A machine without the guard (RemoteMachine on the server: the Pi checks) is let through."""
    lock = getattr(machine, "run_lock", None)
    if lock is None:
        return
    model = getattr(machine, "model", lambda: "mk1")()
    if model == "mault" and who in ("tuning run", "sort run", "one-card feed", "test run"):
        raise RuntimeError(f"The {who} doesn't drive the Mault sorter yet. Set each part's angles on the "
                           "Machine page and try the Bin buttons; runs come once the machine is built.")
    if who == "tuning run" and model == "mk2":
        raise RuntimeError(f"The {who} doesn't drive Mk2 yet. Set each part's angles on the Machine page "
                           "and try the Bin buttons; runs come once those work.")
    with lock:
        if machine.run is not None:
            raise Busy(busy_message(machine.run))
        machine.run = who


def release(machine, who: str):
    lock = getattr(machine, "run_lock", None)
    if lock is None:
        return
    with lock:
        if machine.run == who:
            machine.run = None


def check_free(machine):
    """Raises Busy while a run (or a card being fed) is driving the machine."""
    who = getattr(machine, "run", None)
    if isinstance(who, str):
        raise Busy(busy_message(who))


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
        self.pins_up_at = None    # when the stop pins were last sent up from somewhere else
        self.run_lock = threading.Lock()
        self.run = None           # what drives the machine on its own right now (see claim)
        self._relay = None        # Mk2's power relay, once switched on
        self.relay_error = None

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

    def power_on(self) -> bool:
        """Mk2: close the power relay (config.RELAY_PIN) so the servos, feeder and lights get
        their 5 V. It stays closed while the app runs. Nothing happens on the first machine,
        which has no relay. Returns True when the relay is (now) closed."""
        if self.model() != "mk2" or not getattr(config, "RELAY_PIN", None):
            return False
        with self.lock:
            if self._relay is None:
                try:
                    from gpiozero import OutputDevice
                    self._relay = OutputDevice(config.RELAY_PIN, active_high=True, initial_value=True)
                    self.relay_error = None
                except Exception as e:   # not a Pi, or the pin is taken
                    self.relay_error = f"Couldn't switch the power relay on GPIO{config.RELAY_PIN} ({e})."
                    return False
            self._relay.on()
            # The servo board was without power until now: it wakes up asleep, so set it up again.
            self._kit = None
        return True

    # --- settings: config.py, with what was saved on the page on top ---------

    def model(self) -> str:
        """"mk1" (the first machine) or "mk2", as saved on the Machine page."""
        return model_of(load_saved())

    def set_model(self, model: str):
        """Switch machines. Every servo lets go first, so nothing holds at the other
        machine's angle; each machine keeps its own saved angles."""
        if model not in MODELS:
            raise ValueError(f"Unknown machine: {model!r} (it's one of {', '.join(MODELS)})")
        saved = load_saved()
        if model_of(saved) == model:
            return
        try:
            self.relax_all()
        except (RuntimeError, OSError):
            pass     # no servo board here: nothing is holding anyway
        saved["model"] = model
        self._write(saved)
        if model == "mk2":
            self.power_on()

    def parts(self) -> dict:
        """This machine's parts as config.py has them (no saved angles)."""
        return parts_for(self.model())

    @staticmethod
    def _servos_key(model: str) -> str:
        return {"mk2": "servos_mk2", "mault": "servos_mault"}.get(model, "servos")

    def bins(self) -> dict:
        """The bins this machine can drop into: {number: how}."""
        if self.model() == "mk2":
            return config.SORT_BINS_MK2
        if self.model() == "mault":
            return config.SORT_BINS_MAULT
        return getattr(config, "SORT_BINS", {1: "left", 2: "centre", 3: "right"})

    def stop_part(self) -> str:
        """The part that holds the card on the bed: the stop pins, or Mk2's stop bar."""
        return "stop" if self.model() == "mk2" else "pins"

    def servos(self) -> dict:
        """{part: (channel, {position: angle})}, with saved angles applied."""
        all_saved = load_saved()
        model = model_of(all_saved)
        saved = all_saved.get(self._servos_key(model), {})
        parts = copy.deepcopy(parts_for(model))
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
                "reverse": bool(saved.get("reverse", False)),
                # Feed one card: forward push after the card lands, then the wheels run
                # backwards (feed_watch.py); only kept when saved from the Machine page
                "backoff": float(saved.get("backoff", config.FEED_BACKOFF_SECONDS)),
                "push": float(saved.get("push", getattr(config, "FEED_PUSH_SECONDS", 0.0)))}

    def _write(self, saved: dict):
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = settings_file().with_suffix(".tmp")
        tmp.write_text(json.dumps(saved, indent=2))
        tmp.replace(settings_file())

    def save_position(self, part: str, position: str, angle: float):
        """Keep an angle as a part's named position, e.g. save_position("pins", "down", 58)."""
        saved = load_saved()
        model = model_of(saved)
        parts = parts_for(model)
        if part not in parts or position not in parts[part][1]:
            raise ValueError(f"Unknown part or position: {part} {position}")
        angle = round(max(0.0, min(180.0, float(angle))), 1)
        saved.setdefault(self._servos_key(model), {}).setdefault(part, {})[position] = angle
        self._write(saved)

    def save_feeder(self, seconds: float, speed: float, backoff=None, push=None):
        """The timed push's seconds and speed (the speed is Feed one card's too), and, when
        given, Feed one card's forward push after landing and its back-off, in seconds."""
        saved = load_saved()
        feeder = saved.setdefault("feeder", {})
        feeder.update(seconds=round(min(5.0, max(0.05, float(seconds))), 2),
                      speed=round(min(1.0, max(0.1, float(speed))), 2))
        if backoff is not None:
            feeder["backoff"] = round(min(float(getattr(config, "FEED_BACKOFF_MAX", 1.0)), max(0.0, float(backoff))), 2)
        if push is not None:
            feeder["push"] = round(min(1.0, max(0.0, float(push))), 2)
        self._write(saved)

    def sort_defaults(self) -> dict:
        """How a card is dropped into a bin (config.SORT_*), with what the tuning run saved."""
        saved = load_saved().get("sort", {})
        out = {}
        for key, name in (("pins_seconds", "SORT_PINS_SECONDS"), ("doors_seconds", "SORT_DOORS_SECONDS"),
                          ("tilt_seconds", "SORT_TILT_SECONDS")):
            v = saved.get(key, getattr(config, name))
            out[key] = float(v) if isinstance(v, (int, float)) else float(getattr(config, name))
        return out

    def save_sort(self, **timings):
        """Keep drop timings (pins_seconds, doors_seconds, tilt_seconds) from the tuning run."""
        saved = load_saved()
        sort = saved.setdefault("sort", {})
        for key in ("pins_seconds", "doors_seconds", "tilt_seconds"):
            if timings.get(key) is not None:
                sort[key] = round(min(10.0, max(0.1, float(timings[key]))), 2)
        self._write(saved)

    def set_feeder_reverse(self, on: bool):
        """For a motor fitted the other way round: "forward" then turns it backwards."""
        saved = load_saved()
        saved.setdefault("feeder", {})["reverse"] = bool(on)
        self._write(saved)

    def reset_saved(self):
        """Back to the angles and feeder settings in config.py. The old file is kept as
        machine_settings.json.bak, so a reset pressed by mistake can be undone by hand.
        Which machine it is stays as it was."""
        f = settings_file()
        if f.exists():
            model = self.model()
            f.replace(f.with_name(f.name + ".bak"))
            if model != "mk1":
                self._write({"model": model})

    def wide_travel(self) -> bool:
        return bool(load_saved().get("wide_travel", config.SERVO_WIDE_TRAVEL))

    def home_at_startup(self) -> bool:
        saved = load_saved()
        if model_of(saved) in ("mk2", "mault"):
            model = model_of(saved)
            return bool(saved.get("home_at_startup_" + model, per_model(model, "HOME_AT_STARTUP", False)))
        return bool(saved.get("home_at_startup", config.HOME_AT_STARTUP))

    def set_home_at_startup(self, on: bool):
        saved = load_saved()
        model = model_of(saved)
        saved["home_at_startup_" + model if model in ("mk2", "mault") else "home_at_startup"] = bool(on)
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
        parts = self.parts()
        if angle is not None and parts is config.SERVOS_MK2:
            self._stop_up_before_push(channel, angle)
        held = (config.SERVO_KEEP_HOLDING_MAULT if parts is config.SERVOS_MAULT else
                getattr(config, "SERVO_KEEP_HOLDING_MK2" if parts is config.SERVOS_MK2 else "SERVO_KEEP_HOLDING", ()))
        keep = {parts[p][0] for p in held if p in parts}
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
                health.event("servo", f"Lost the servo board moving channel {channel}", "bad", channel=channel)
                raise
            self.angles[channel] = angle
            health.servo_moved(channel, angle)
            if angle is not None:
                self._remember(channel, angle)
            old = self._relax_timers.pop(channel, None)
            if old:
                old.cancel()
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

    def _stop_up_before_push(self, channel: int, angle: float):
        """Mk2: down, the stop bar rests on the pushers, so a pusher never moves until the
        stop bar is up. Any pusher move (a sort, Home, a test button, a slider) first sends
        the stop bar up and waits config.FEED_PINS_UP_SECONDS for it to get there."""
        servos = self.servos()
        pushers = {servos[p][0] for p in getattr(config, "MK2_PUSHERS", ("push1", "push2")) if p in servos}
        if channel not in pushers or self.angles.get(channel) == angle or "stop" not in servos:
            return
        stop_ch, stop_pos = servos["stop"]
        up = stop_pos.get("up")
        if up is None or self.angles.get(stop_ch) == float(up):
            return
        self.set_angle(stop_ch, up)
        self.pins_up_at = time.monotonic()
        time.sleep(float(getattr(config, "FEED_PINS_UP_SECONDS", 0.6)))

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
        moving = self.angles.get(channel) != angle
        start = self.angles.get(channel)
        if start is None:   # let go (relaxed) or just started: sweep from where it was last sent
            start = self.last_angles().get(str(channel))
        if part in getattr(config, "MK2_PUSHERS", ()) and self.model() == "mk2" and start is not None:
            self._sweep(channel, float(start), float(angle))      # slowly, so a card doesn't jam
        else:
            self.set_angle(channel, angle)
        if part in ("pins", "stop") and position == "up" and moving:
            self.pins_up_at = time.monotonic()

    def pins_up(self) -> float:
        """Put the stop pins up and wait until they are all the way up (config.FEED_PINS_UP_SECONDS
        after they were sent up; no wait if they were up already), so the next card can't
        arrive under a stop bar that is still rising. Returns how long it waited."""
        if self.model() == "mault":
            return 0.0          # no stop bar: the card waits in the module's gate
        self.move(self.stop_part(), "up")
        if self.pins_up_at is None:
            return 0.0
        left = self.pins_up_at + float(getattr(config, "FEED_PINS_UP_SECONDS", 0.6)) - time.monotonic()
        if left <= 0:
            return 0.0
        time.sleep(left)
        return round(left, 2)

    def relax_all(self):
        for channel, _ in self.parts().values():
            self.set_angle(channel, None)

    def home(self, pause: float = 0.4, speed: float | None = None):
        """Every part to its home position (config.SERVO_HOME), with the saved angles, one
        at a time so they don't all draw current at once. Each one sweeps there slowly
        (config.SERVO_HOME_SPEED degrees a second) from the last angle it was sent, so
        nothing slams into a stop; a part with no last angle goes straight there."""
        speed = speed or config.SERVO_HOME_SPEED
        servos, last = self.servos(), self.last_angles()
        health.event("move", "Home: every part to its home position")
        order = per_model(self.model(), "SERVO_HOME")
        for part, position in order.items():
            if part not in servos or position not in servos[part][1]:
                continue
            channel, target = servos[part][0], float(servos[part][1][position])
            start = last.get(str(channel))
            # Pushers no faster than a sort moves them (MK2_PUSH_SPEED).
            part_speed = min(speed, float(getattr(config, "MK2_PUSH_SPEED", speed)))                 if part in getattr(config, "MK2_PUSHERS", ()) else speed
            if part in getattr(config, "MK2_PUSHERS", ()) and self.model() == "mk2" \
                    and isinstance(start, (int, float)) and part_speed > 0:
                self._sweep(channel, float(start), target, part_speed)   # the same glide as a sort
            elif isinstance(start, (int, float)) and part_speed > 0:
                steps = int(abs(target - start) // 2)            # 2 degree steps
                for i in range(1, steps + 1):
                    self.set_angle(channel, start + (target - start) * i / (steps + 1))
                    time.sleep(2 / part_speed)
            self.set_angle(channel, target)
            time.sleep(pause)

    def drop(self, bin_no: int, pins_seconds=None, doors_seconds=None, tilt_seconds=None, card_gone=None):
        """Send the card on the bed to a bin (config.SORT_BINS): drop the stop pins so the
        card slides onto the level tray, then open the trapdoors (bin 2) or tilt the chute
        to the side (bins 1 and 3); then put everything back. About 6 s. Nothing watches the
        camera here (sort_one in feed_watch.py does that). The tray stays level while the
        card slides: tilted first, the card turns as it comes down and catches on the rail
        (seen on the right side, 2026-11-06). `card_gone`, if given, is asked every 0.1 s
        while the pins are down and ends the wait early (after config.SORT_PINS_MIN_SECONDS
        plus a moment to clear) once it says True: sort_one passes the camera's view."""
        if self.model() == "mk2":
            return self._drop_mk2(bin_no, card_gone)
        if self.model() == "mault":
            return self._drop_mault(bin_no)
        bins = getattr(config, "SORT_BINS", {1: "left", 2: "centre", 3: "right"})
        try:
            position = bins[int(bin_no)]
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"No such bin: {bin_no!r} (bins are {', '.join(map(str, bins))})")
        defaults = self.sort_defaults()
        pins_seconds = float(defaults["pins_seconds"] if pins_seconds is None else pins_seconds)
        doors_seconds = float(defaults["doors_seconds"] if doors_seconds is None else doors_seconds)
        tilt_seconds = float(defaults["tilt_seconds"] if tilt_seconds is None else tilt_seconds)
        use_doors = int(bin_no) == getattr(config, "SORT_DOOR_BIN", 2)
        servos = self.servos()
        if "chute" not in servos or position not in servos["chute"][1]:
            raise ValueError(f"The chute has no '{position}' position: set it on the Machine page")

        def hold(where, seconds, until=None):
            # The chute lets go SERVO_HOLD_SECONDS after a move (so a stalled servo can't
            # cook); a tray left loose sags under the card, so send the angle again meanwhile.
            start = time.monotonic()
            end = start + seconds
            resend = start + 1.0
            least = start + float(getattr(config, "SORT_PINS_MIN_SECONDS", 0.5))
            while True:
                now = time.monotonic()
                if now >= end:
                    return seconds
                if until is not None and until():
                    if self.last_gone_at is None:
                        self.last_gone_at = round(now - start, 2)
                    if now >= least:
                        time.sleep(min(0.3, max(0.0, end - now)))   # let it clear the teeth
                        return round(time.monotonic() - start, 2)
                if now >= resend:
                    self.move("chute", where)
                    resend = now + 1.0
                time.sleep(min(0.1 if until is not None else 1.0, max(0.0, end - time.monotonic())))

        self.last_gone_at = None     # when card_gone first said so, seconds after pins down
        try:
            self.move("chute", "centre")
            self.move("pins", "down")
            self.last_pins_seconds = hold("centre", pins_seconds, card_gone)   # the card slides onto the level tray
            if use_doors:
                self.move("door_r", "open")
                self.move("door_l", "open")
                hold("centre", doors_seconds)
                # The card has fallen through: pins up now, while the doors close, so they
                # are all the way up before the next card is fed (Nic, 2026-11-09: after a
                # trapdoor drop the next card came while the pins were still rising).
                self.move("pins", "up")
                self.move("door_r", "closed")
                self.move("door_l", "closed")
                hold("centre", 0.4)
            else:
                # Pins back up before the tilt: a card sliding sideways off the tray caught
                # on the lowered stop bar (Nic, 2026-11-08).
                if getattr(config, "SORT_PINS_UP_BEFORE_TILT", True):
                    self.move("pins", "up")
                    hold("centre", float(getattr(config, "SORT_PINS_UP_SETTLE", 0.3)))
                self.move("chute", position)
                hold(position, tilt_seconds)        # and off the side of the tilted tray
                self._shake(servos["chute"], position)
        finally:
            self.move("chute", "centre")
            self.move("pins", "up")

    def _drop_mk2(self, bin_no, card_gone=None):
        """Mk2 (MK2.md, Software changes): the stop bar drops and the card lands on level 1;
        the stop bar goes back up before anything else moves (down, it hangs over level 1's
        pusher). Bins 1 and 2: level 1's pusher slides the card off to that side and comes back.
        Bins 3 and 4: both trapdoors open, the card falls to level 2, the doors shut, then
        level 2's pusher does the same."""
        bins = config.SORT_BINS_MK2
        try:
            pusher, side = bins[int(bin_no)]
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"No such bin: {bin_no!r} (bins are {', '.join(map(str, bins))})")
        servos = self.servos()
        for part in ("stop", pusher) + (("door_f", "door_b") if pusher == "push2" else ()):
            if part not in servos:
                raise ValueError(f"Mk2 has no {part}")
        stop_seconds = float(getattr(config, "MK2_STOP_SECONDS", 0.6))
        self.last_gone_at = None
        self.last_pins_seconds = 0.0
        try:
            self.move("push1", "centre")
            self.move("push2", "centre")
            # The doors let go after SERVO_HOLD_LIMIT with no new move and then hang loose:
            # a card dropped onto them falls straight through to level 2 (Nic, 2026-11-24).
            # Shut them, and give them time to get there, before the card comes down.
            for door in ("door_f", "door_b"):
                if door in servos:
                    self.move(door, "closed")
            time.sleep(float(getattr(config, "MK2_DOORS_SECONDS", 0.8)))
            self.move("stop", "down")
            start = time.monotonic()
            least = start + float(getattr(config, "MK2_STOP_MIN_SECONDS", 0.8))
            clear = float(getattr(config, "MK2_STOP_CLEAR_SECONDS", 0.3))
            while time.monotonic() < start + stop_seconds:
                if card_gone is not None and self.last_gone_at is None and card_gone():
                    self.last_gone_at = round(time.monotonic() - start, 2)
                if self.last_gone_at is not None and time.monotonic() >= max(least, start + self.last_gone_at + clear):
                    break
                time.sleep(0.05)
            self.last_pins_seconds = round(time.monotonic() - start, 2)
            self.move("stop", "up")
            time.sleep(float(getattr(config, "FEED_PINS_UP_SECONDS", 0.6)))
            if pusher == "push2":
                self.move("door_f", "open")
                self.move("door_b", "open")
                time.sleep(float(getattr(config, "MK2_DOORS_SECONDS", 0.8)))
                self.move("door_f", "closed")
                self.move("door_b", "closed")
                time.sleep(0.3)
            self._push(servos[pusher], side)
        finally:
            for part, position in (("stop", "up"), ("door_f", "closed"), ("door_b", "closed"),
                                   ("push1", "centre"), ("push2", "centre")):
                if part in servos:
                    self.move(part, position)

    def _drop_mault(self, bin_no):
        """Mault sorter: the card waits in module 1's gate. For a bin on a later module (or
        the end bin) the trapdoors before it open one after the other and the card slides on.
        At its module the paddle opens, the pusher slides the card off to that side, waits,
        comes back, and the paddle shuts. Everything ends shut, pushers in the middle."""
        bins = config.SORT_BINS_MAULT
        try:
            module, side = bins[int(bin_no)]
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"No such bin: {bin_no!r} (bins are {', '.join(map(str, bins))})")
        servos = self.servos()
        modules = sorted({int(p[1]) for p in servos if p.startswith("m") and p.endswith("_door")})
        through = [m for m in modules if module is None or m < module]
        stagger = float(config.MAULT_STAGGER)
        self.last_gone_at = None
        self.last_pins_seconds = 0.0
        try:
            for m in through:
                self.move(f"m{m}_door", "open")
                time.sleep(stagger)
            if through:
                time.sleep(float(config.MAULT_SLIDE_SECONDS) * len(through))
            if module is not None:
                if f"m{module}_push" not in servos:
                    raise ValueError(f"The Mault sorter has no module {module}")
                self.move(f"m{module}_paddle", "open")
                time.sleep(float(config.MAULT_PADDLE_SECONDS))
                self.move(f"m{module}_push", side)
                time.sleep(float(config.MAULT_PUSH_SECONDS) + float(config.MAULT_PUSH_HOLD))
                self.move(f"m{module}_push", "centre")
                time.sleep(float(config.MAULT_PUSH_SECONDS))
        finally:
            for m in modules:
                for part, position in ((f"m{m}_push", "centre"), (f"m{m}_paddle", "closed"), (f"m{m}_door", "closed")):
                    if part in servos:
                        self.move(part, position)
                        time.sleep(stagger)

    def _feeder_servo(self):
        """The Mault feeder's continuous servo on the servo board, or None with servo_error set."""
        kit = self._fresh_servos()
        return None if kit is None else kit.continuous_servo[int(config.MAULT_FEEDER_CHANNEL)]

    def _sweep(self, channel, a, b, speed=None):
        """Turn a pusher from angle a to b at a slow average speed (config.MK2_PUSH_SPEED
        degrees a second), so it eases the card along instead of shoving it into a jam
        (Nic, 2026-11-24). It starts and stops gently (a cosine ease) and moves in steps of
        about config.MK2_PUSH_STEP degrees at a steady rate, which a cheap servo follows as one
        smooth glide instead of a row of little jerks (Nic, 2026-11-26: "they moved so clunky")."""
        speed = float(speed or getattr(config, "MK2_PUSH_SPEED", 45))
        step = float(getattr(config, "MK2_PUSH_STEP", 1))
        span = b - a
        steps = max(1, int(math.ceil(abs(span) / step)))
        tick = abs(span) / speed / steps
        for i in range(1, steps + 1):
            eased = (1 - math.cos(math.pi * i / steps)) / 2
            self.set_angle(channel, b if i == steps else round(a + span * eased, 2))
            time.sleep(tick)

    def _push(self, pusher, side, speed=None):
        """Sweep a pusher from the centre to one side at a steady speed, wait, and sweep back."""
        channel, positions = pusher
        centre, end = float(positions["centre"]), float(positions[side])
        self._sweep(channel, centre, end, speed)
        time.sleep(float(getattr(config, "MK2_PUSH_HOLD", 0.3)))
        self._sweep(channel, end, centre, speed)

    def _shake(self, chute, position, shakes=None, seconds=None):
        """Rock the tilted tray half way back towards level and tilt it again, a few times
        (config.SORT_TILT_SHAKES), so a card left on the tray slides off. Half way, not level:
        a card nearly off the edge shouldn't slide back into the middle."""
        shakes = int(getattr(config, "SORT_TILT_SHAKES", 0) if shakes is None else shakes)
        seconds = float(getattr(config, "SORT_SHAKE_SECONDS", 0.4) if seconds is None else seconds)
        channel, positions = chute
        if shakes <= 0 or "centre" not in positions:
            return
        tilted, level = float(positions[position]), float(positions["centre"])
        half = round(level + (tilted - level) / 2, 1)
        # Each shake tilts further than the saved tilt (Nic, 2026-11-08: "a bigger angle when
        # it shakes"), by config.SORT_SHAKE_EXTRA degrees away from level.
        extra = float(getattr(config, "SORT_SHAKE_EXTRA", 0.0))
        side = 1.0 if tilted >= level else -1.0
        deeper = round(max(0.0, min(180.0, tilted + side * extra)), 1)
        for _ in range(shakes):
            self.set_angle(channel, half)
            time.sleep(seconds)
            if extra > 0:
                self.set_angle(channel, deeper)
            else:
                self.move("chute", position)
            time.sleep(seconds)
        if extra > 0:
            self.move("chute", position)

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
        mault = self.model() == "mault"
        with self.lock:
            motor = self._feeder_servo() if mault else self._feeder()
            if motor is None:
                raise RuntimeError(self.servo_error if mault else self.feeder_error)
            if self._stop_timer:
                self._stop_timer.cancel()
            if defaults["reverse"]:
                backward = not backward
            if mault:
                motor.throttle = -speed if backward else speed
            else:
                (motor.backward if backward else motor.forward)(speed)
            health.feeder_pulse(seconds, speed, backward)
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
            if self._kit is not None and self.model() == "mault":
                try:
                    # no pulse at all, so the servo stands still instead of creeping
                    self._kit.continuous_servo[int(config.MAULT_FEEDER_CHANNEL)].fraction = None
                except OSError:
                    self._kit = None
            self.feeding = False

    # --- for the page -------------------------------------------------------

    def state(self) -> dict:
        servos, defaults = self.servos(), self.feeder_defaults()
        model = self.model()
        factory = parts_for(model)
        with self.lock:
            self._servos()
            if model != "mault":
                self._feeder()
            feeder_ok = self._kit is not None if model == "mault" else self._motor is not None
            return {
                "servos": {"ok": self._kit is not None, "error": self.servo_error},
                "feeder": {"ok": feeder_ok, "error": self.servo_error if model == "mault" else self.feeder_error,
                           "running": self.feeding},
                "parts": {part: {"channel": ch, "positions": pos,
                                 "factory": factory[part][1],
                                 "angle": self.angles.get(ch)}
                          for part, (ch, pos) in servos.items()},
                "feeder_defaults": defaults,
                "sort_defaults": self.sort_defaults(),
                "wide_travel": self.wide_travel(),
                "home_at_startup": self.home_at_startup(),
                "customized": settings_file().exists(),
                "model": model,
                "relay": {"on": self._relay is not None and bool(self._relay.value),
                          "error": self.relay_error} if model == "mk2" else None,
                "models": MODELS,
                "bins": list(self.bins()),
            }


def add_machine_routes(app, machine: Machine, web_dir):
    """The Machine page and its API, added to the scanner app."""

    @app.get("/machine")
    def machine_page():
        return send_from_directory(web_dir, "machine.html")

    # the error itself goes to the log; the page gets the plain advice
    HARDWARE = "Lost touch with the servo board. Check its power and wiring, then try again."
    SAVING = "Couldn't save that. Is the data folder full or read-only?"

    def answer(action, oserror=HARDWARE, guard=None):
        """Run a page action. guard="check": refused (409) while a run drives the machine;
        guard="claim": also keeps runs out until this action is done (Home, Bin drops)."""
        try:
            if guard == "claim":
                claim(machine, "move you started")
                try:
                    action()
                finally:
                    release(machine, "move you started")
            else:
                if guard:
                    check_free(machine)
                action()
        except Busy as e:
            return jsonify(error=str(e)), 409
        except (ValueError, TypeError) as e:
            return jsonify(error=str(e)), 400
        except RuntimeError as e:
            health.event("error", f"{request.path}: {e}", "bad")
            return jsonify(error=str(e)), 503
        except OSError as e:     # the servo board lost power, an I2C glitch, a full disk
            print(f"Machine: {oserror} ({e})")
            health.event("error", f"{request.path}: {oserror}", "bad")
            return jsonify(error=oserror), 503
        return jsonify(machine.state())

    @app.get("/api/machine")
    def machine_state():
        return jsonify(machine.state())

    @app.post("/api/machine/move")
    def machine_move():
        body = request.get_json(silent=True) or {}
        if "angle" in body:
            return answer(lambda: machine.set_angle(int(body.get("channel", -1)), body["angle"]), guard="check")
        return answer(lambda: machine.move(str(body.get("part")), str(body.get("position"))), guard="check")

    @app.post("/api/machine/home")
    def machine_home():
        return answer(machine.home, guard="claim")

    @app.post("/api/machine/relax")
    def machine_relax():
        return answer(machine.relax_all)

    @app.post("/api/machine/feed")
    def machine_feed():
        body = request.get_json(silent=True) or {}
        return answer(lambda: machine.feed(body.get("seconds"), body.get("speed"),
                                           bool(body.get("backward"))),
                      "Lost touch with the feeder motor. Check its wiring, then try again.", guard="check")

    @app.post("/api/machine/stop")
    def machine_stop():
        return answer(machine.stop_feeder)

    @app.post("/api/machine/drop")
    def machine_drop():
        """Send the card on the bed to a bin (no feeding, no camera)."""
        body = request.get_json(silent=True) or {}
        return answer(lambda: machine.drop(body.get("bin"), body.get("pins_seconds"),
                                           body.get("doors_seconds"), body.get("tilt_seconds")), guard="claim")

    @app.post("/api/machine/save")
    def machine_save():
        """Keep an angle as a named position, or the feeder's seconds and speed."""
        body = request.get_json(silent=True) or {}
        if "part" in body:
            return answer(lambda: machine.save_position(str(body["part"]), str(body.get("position")),
                                                        body.get("angle")), SAVING)
        if "model" in body:
            return answer(lambda: machine.set_model(str(body["model"])), SAVING, guard="check")
        if "home_at_startup" in body:
            return answer(lambda: machine.set_home_at_startup(bool(body["home_at_startup"])), SAVING)
        if "wide_travel" in body:
            return answer(lambda: machine.set_wide_travel(bool(body["wide_travel"])), SAVING)
        if "sort" in body:
            return answer(lambda: machine.save_sort(**(body["sort"] if isinstance(body["sort"], dict) else {})), SAVING)
        if "reverse" in body and "seconds" not in body:
            return answer(lambda: machine.set_feeder_reverse(bool(body["reverse"])), SAVING)
        return answer(lambda: machine.save_feeder(body.get("seconds"), body.get("speed"),
                                                  body.get("backoff"), body.get("push")), SAVING)

    @app.post("/api/machine/reset")
    def machine_reset():
        return answer(machine.reset_saved, SAVING)

    @app.post("/api/machine/test")
    def machine_test():
        try:
            claim(machine, "self-test")
        except Busy as e:
            return jsonify(error=str(e)), 409
        try:
            report = machine.self_test()
        finally:
            release(machine, "self-test")
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
