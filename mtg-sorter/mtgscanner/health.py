"""Machine health: everything the sorter reports, in one place.

The /machine/health page and GET /api/machine/health show the Pi (temperature, throttling,
power), the camera, each servo (where it is, when it last moved, its saved angles), the feeder
(every pulse on GPIO17/27 and what each fed card did), the bin sensors, the lights, recent scans
and misreads, jams and errors, and the warnings in the log.

The Pi keeps the record (the moves and feeds happen there). On the server the page and the
JSON come from the Pi through MTG_MACHINE_URL, like the Machine page. Add ?download=1 to the
JSON address to save it as a file, to send to someone who'll look into a problem.

The machine code tells this module what it does (servo_moved, feeder_pulse, feed_result, ...).
Everything is kept in memory, the newest few hundred of each, so a restart starts afresh.
"""

import logging
import socket
import threading
import time
from collections import deque

from . import config
from .bin_sensors import BinSensors

_lock = threading.Lock()
EVENTS: deque = deque(maxlen=300)      # moves, drops, jams, errors, run ends, log warnings
PULSES: deque = deque(maxlen=60)       # each time the feeder motor was turned on
FEEDS: deque = deque(maxlen=60)        # each card fed while watching the camera, and what it did
MOVES: dict = {}                       # channel -> the last angle sent and when
COUNTS = {"pulses": 0, "feeds": 0, "moves": 0, "drops": 0, "errors": 0, "jams": 0}
STARTED = time.time()

# What a fed card did, as feed_watch.py reports it: the ones that aren't "landed" are problems.
FEED_PROBLEMS = {
    "none": "no card came out",
    "stuck": "a card stuck in the slot",
    "over": "a card went over the stop bar",
    "crowded": "the camera saw more than one card on the bed",
}
JAMS = ("stuck", "crowded")


def reset():
    """Forget everything (the tests start each one afresh)."""
    global STARTED
    with _lock:
        EVENTS.clear()
        PULSES.clear()
        FEEDS.clear()
        MOVES.clear()
        for k in COUNTS:
            COUNTS[k] = 0
        STARTED = time.time()


# --- what the machine tells us --------------------------------------------------------

def event(kind: str, text: str, level: str = "info", **data):
    """One line in the record. level: info, warn or bad."""
    with _lock:
        if level == "bad":
            COUNTS["errors"] += 1
        EVENTS.append({"at": time.time(), "kind": kind, "level": level, "text": str(text)} | data)


def servo_moved(channel: int, angle):
    """Called for every angle sent to a servo (a pusher's slow sweep sends many)."""
    with _lock:
        COUNTS["moves"] += 1
        MOVES[int(channel)] = {"at": time.time(), "angle": None if angle is None else round(float(angle), 1)}


def feeder_pulse(seconds: float, speed: float, backward: bool):
    with _lock:
        COUNTS["pulses"] += 1
        PULSES.append({"at": time.time(), "seconds": round(float(seconds), 2), "speed": round(float(speed), 2),
                       "direction": "back" if backward else "forward"})


def feed_result(out: dict):
    """What one fed card did (FeedWatcher.feed_one's answer)."""
    result = out.get("result")
    row = {"at": time.time(), "result": result, "landed_ms": out.get("landed_ms"), "motor_ms": out.get("motor_ms")}
    with _lock:
        COUNTS["feeds"] += 1
        if result in JAMS:
            COUNTS["jams"] += 1
        FEEDS.append(row)
    if result in FEED_PROBLEMS:
        event("feed", "Feed: " + FEED_PROBLEMS[result], "bad" if result in JAMS else "warn", result=result)


def drop_result(out: dict):
    """What one sort did after its feed (FeedWatcher.sort_one's answer)."""
    if out.get("dropped") is False:
        event("drop", f"Bin {out.get('bin')}: the card was still on the bed after {out.get('drop_tries')} "
                      "tries (a jam on level 1 or the doors?)", "bad", bin=out.get("bin"))
        with _lock:
            COUNTS["jams"] += 1
    elif out.get("dropped"):
        with _lock:
            COUNTS["drops"] += 1   # counted, not listed: a long run would push the problems out of the list
        if (out.get("drop_tries") or 0) > 1:
            event("drop", f"Bin {out.get('bin')}: the card only left on try {out['drop_tries']}", "warn",
                  bin=out.get("bin"))


def run_ended(reason: str):
    """Finished, stopped or the hopper ran out: fine. An error: bad. Anything else (a jam, two
    cards, a card over the stop bar) stopped the run on a problem."""
    if reason in ("finished", "stopped") or reason.startswith(("did the", "nothing came out")):
        level = "info"
    else:
        level = "bad" if reason.startswith("error") else "warn"
    event("run", "Sort run ended: " + reason, level)


class _WarningLog(logging.Handler):
    """Warnings and errors from anywhere in the app go into the record too."""
    def __init__(self):
        super().__init__(level=logging.WARNING)

    def emit(self, record):
        if record.name == "werkzeug" and record.levelno < logging.ERROR:
            return   # "This is a development server", every start
        try:
            msg = record.getMessage()
            if record.exc_info and record.exc_info[1] is not None:
                msg += f" ({record.exc_info[1]})"
            event("log", msg[:500], "bad" if record.levelno >= logging.ERROR else "warn", logger=record.name)
        except Exception:
            pass


_HANDLER = _WarningLog()


def keep_warnings():
    root = logging.getLogger()
    if _HANDLER not in root.handlers:
        root.addHandler(_HANDLER)


# --- the report -------------------------------------------------------------------------

NAMES = {"stop": "Stop bar", "push1": "Level 1 pusher", "door_f": "Front trapdoor", "door_b": "Back trapdoor",
         "push2": "Level 2 pusher", "pins": "Stop pins", "chute": "Chute tilt", "door_r": "Right trapdoor",
         "door_l": "Left trapdoor"}


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _problem(area: str, state: str, text: str, fix: str | None = None) -> dict:
    return {"area": area, "state": state, "text": text, "fix": fix}


def pi_part() -> tuple[dict, list]:
    from . import system
    flags = _safe(system.throttled)
    temp = _safe(system.temperature)
    out = {
        "model": _safe(system.model), "hostname": _safe(socket.gethostname),
        "temperature_c": None if temp is None else round(temp, 1),
        "throttled_raw": None if flags is None else hex(flags),
        "throttled": [t for bit, t in system.THROTTLE_BITS.items() if (flags or 0) >> bit & 1],
        "supply_volts": _safe(system.supply_volts), "uptime_s": _safe(system.uptime),
        "memory": _safe(system.memory), "disk": _safe(system.disk),
        "version": (_safe(system.version) or {}).get("commit"), "on_pi": system.ON_PI,
    }
    problems = []
    for check in (_safe(system.temperature_check), _safe(system.power_check), _safe(system.disk_check),
                  _safe(system.memory_check)):
        if check and check["state"] in ("warn", "bad"):
            problems.append(_problem("pi", check["state"], f"{check['label']}: {check['summary']}", check.get("fix")))
    return out, problems


def camera_part(scanner) -> tuple[dict, list]:
    from . import system
    check = _safe(lambda: system.camera_check(scanner)) or {"state": "off", "summary": "Unknown"}
    perf = getattr(scanner, "perf", None) or {}
    src = getattr(scanner, "source", None)
    info = _safe(lambda: src.info()) if src is not None and hasattr(src, "info") else None
    out = {"state": check["state"], "summary": check["summary"], "fix": check.get("fix"),
           "name": getattr(src, "name", None), "size": (info or {}).get("size") or getattr(scanner, "frame_size", None),
           "fps": None if perf.get("fps") is None else round(perf["fps"], 1),
           "frame_age_ms": None if perf.get("frame_age_ms") is None else round(perf["frame_age_ms"]),
           "started": bool(getattr(scanner, "started", False))}
    problems = [_problem("camera", check["state"], f"Camera: {check['summary']}", check.get("fix"))] \
        if check["state"] in ("warn", "bad") else []
    return out, problems


def servo_part(machine, state: dict) -> tuple[list, list]:
    lo, hi = getattr(config, "SERVO_SAFE_RANGE", (10, 170))
    with _lock:
        moves = dict(MOVES)
    last = _safe(machine.last_angles, {}) if hasattr(machine, "last_angles") else {}
    rows, problems = [], []
    for part, p in sorted(state.get("parts", {}).items(), key=lambda kv: kv[1]["channel"]):
        ch = p["channel"]
        warnings = []
        for pos, angle in (p.get("positions") or {}).items():
            if angle is not None and not lo <= float(angle) <= hi:
                warnings.append(f'"{pos}" is saved at {float(angle):g}°, outside {lo}-{hi}°')
        move = moves.get(ch)
        name = NAMES.get(part, part)
        rows.append({"part": part, "name": name, "channel": ch, "angle": p.get("angle"),
                     "holding": p.get("angle") is not None, "positions": p.get("positions"),
                     "factory": p.get("factory"), "last_sent": (last or {}).get(str(ch)),
                     "last_move_at": move["at"] if move else None,
                     "last_move_angle": move["angle"] if move else None, "warnings": warnings})
        for w in warnings:
            problems.append(_problem("servos", "warn", f"{name} (channel {ch}): {w}",
                                     f"On the Machine page, set {name} between {lo} and {hi}° and save it. "
                                     "At its own stop a servo strains and wears out."))
    return rows, problems


def feeder_part(state: dict) -> tuple[dict, list]:
    feeder = state.get("feeder") or {}
    with _lock:
        pulses, feeds = list(PULSES), list(FEEDS)
    tally = {}
    for f in feeds:
        tally[f["result"]] = tally.get(f["result"], 0) + 1
    out = {"ok": feeder.get("ok"), "error": feeder.get("error"), "running": feeder.get("running"),
           "pins": list(getattr(config, "FEEDER_PINS", ())), "settings": state.get("feeder_defaults"),
           "pulses": pulses[::-1][:20], "feeds": feeds[::-1][:20], "tally": tally,
           "landed_share": round(tally.get("landed", 0) / len(feeds), 2) if feeds else None}
    problems = []
    if feeder.get("ok") is False:
        problems.append(_problem("feeder", "bad" if config_on_pi() else "off",
                                 "Feeder: " + (feeder.get("error") or "not available")))
    recent = feeds[-5:]
    jams = [f for f in recent if f["result"] in JAMS]
    nones = [f for f in recent if f["result"] == "none"]
    if jams:
        problems.append(_problem("feeder", "bad", f"Feeder: {len(jams)} of the last {len(recent)} feeds jammed "
                                 f"({FEED_PROBLEMS[jams[-1]['result']]}).",
                                 "Open the gate a little (one card slides through by hand, two together don't) "
                                 "and clear the bed."))
    if len(nones) >= 2:
        problems.append(_problem("feeder", "warn", f"Feeder: no card came out {len(nones)} of the last "
                                 f"{len(recent)} times.",
                                 "Keep 30+ cards in the magazine, square the stack, and clean the rings."))
    return out, problems


def config_on_pi() -> bool:
    from . import system
    return bool(system.ON_PI)


def sensors_part(sensors) -> tuple[dict, list]:
    if sensors is None:
        return {"fitted": {"full": False, "seated": False}, "bins": [], "error": None}, []
    s = _safe(sensors.read) or {"fitted": {"full": False, "seated": False}, "bins": [], "error": "Couldn't read them"}
    problems = []
    for b in s["bins"]:
        if b["full"]:
            problems.append(_problem("bins", "warn", f"Bin {b['bin']} is full.", "Empty it before the next run."))
        if b["seated"] is False:
            problems.append(_problem("bins", "warn", f"Bin {b['bin']} is out.", "Slide it back in until it clicks."))
    if s.get("error"):
        problems.append(_problem("bins", "warn", s["error"], "Check the sensor's 3 wires: VCC to 3.3 V, GND, "
                                 "and DO to its GPIO pin (Machine health page, Bin sensors)."))
    return s, problems


def lights_part(scanner) -> dict | None:
    lights = getattr(scanner, "lights", None)
    if lights is None:
        return None
    s = _safe(lights.state) or {}
    set_ = s.get("settings") or {}
    card = set_.get("card") or {}
    return {"ok": s.get("ok"), "error": s.get("error"), "on": set_.get("on"), "color": set_.get("color"),
            "effect": set_.get("effect"), "brightness": set_.get("brightness"), "count": set_.get("count"),
            "card_on": card.get("on"), "card_count": card.get("count"), "card_color": card.get("color"),
            "amps": s.get("amps"), "dimmed": s.get("dimmed"), "pin": s.get("pin")}


def scans_part(scanner, run) -> tuple[dict, list]:
    session = list(getattr(scanner, "session", []) or [])
    saved = [{"name": c.get("name"), "set": c.get("set"), "number": c.get("number"), "price": c.get("price"),
              "bin": c.get("bin"), "time": c.get("time"), "foil": c.get("foil")} for c in session[::-1][:15]]
    run_state = _safe(run.status) if run is not None else None
    cards = list((run_state or {}).get("cards") or [])
    misreads = [{"n": c.get("n"), "status": c.get("status"), "name": c.get("name"), "bin": c.get("bin"),
                 "seconds": c.get("seconds")}
                for c in cards if c.get("status") in ("unsure", "unknown", "none", "stuck", "double", "over", "crowded")]
    captures = dict(getattr(getattr(scanner, "captures", None), "counts", {}) or {})
    out = {"saved_this_session": len(session), "recent": saved, "captures": captures,
           "run": None if run_state is None else {
               "running": run_state.get("running"), "done": run_state.get("done"),
               "counts": run_state.get("counts"), "tally": run_state.get("tally"),
               "warning": run_state.get("warning"), "cards": len(cards), "started_at": run_state.get("started_at")},
           "misreads": misreads[::-1][:20]}
    problems = []
    done = (run_state or {}).get("done") or ""
    if done.startswith("error"):
        problems.append(_problem("run", "bad", "The last sort run stopped on an " + done))
    if (run_state or {}).get("warning"):
        problems.append(_problem("run", "warn", run_state["warning"]))
    counts = (run_state or {}).get("counts") or {}
    if cards and (counts.get("unknown", 0) + counts.get("unsure", 0)) / len(cards) > 0.25:
        problems.append(_problem("scans", "warn", f"{counts.get('unknown', 0) + counts.get('unsure', 0)} of the last "
                                 f"{len(cards)} run cards weren't read for sure.",
                                 "Keep the room lights off, check the card light is on, and press Bed is empty."))
    return out, problems


def overall(problems: list) -> str:
    states = {p["state"] for p in problems}
    return "bad" if "bad" in states else "warn" if "warn" in states else "ok"


def report(scanner, machine, sensors=None, run=None) -> dict:
    """Everything, as one dict (GET /api/machine/health on the Pi)."""
    state = _safe(machine.state, {}) if machine is not None else {}
    pi, p1 = pi_part()
    camera, p2 = camera_part(scanner)
    servos, p3 = servo_part(machine, state)
    feeder, p4 = feeder_part(state)
    bins, p5 = sensors_part(sensors)
    scans, p6 = scans_part(scanner, run)
    problems = p1 + p2 + p3 + p4 + p5 + p6
    if (state.get("servos") or {}).get("ok") is False:
        problems.insert(0, _problem("servos", "bad" if config_on_pi() else "off",
                                    "Servo board: " + (state["servos"].get("error") or "not found")))
    relay = state.get("relay")
    if relay and not relay.get("on") and relay.get("error"):
        problems.append(_problem("power", "bad", "Power relay: " + relay["error"]))
    problems = [p for p in problems if p["state"] != "off"]
    with _lock:
        events = list(EVENTS)[::-1][:80]
        counts = dict(COUNTS)
    return {
        "generated_at": time.time(), "since": STARTED, "where": "pi" if config_on_pi() else "this computer",
        "overall": overall(problems), "problems": problems,
        "pi": pi, "camera": camera,
        "machine": {"model": state.get("model"), "relay": relay, "busy": getattr(machine, "run", None),
                    "servo_board": state.get("servos"), "wide_travel": state.get("wide_travel"),
                    "safe_range": list(getattr(config, "SERVO_SAFE_RANGE", (10, 170)))},
        "servos": servos, "feeder": feeder, "bins": bins, "lights": lights_part(scanner), "scans": scans,
        "counts": counts, "events": events,
    }


def unreachable(error: str, url: str | None) -> dict:
    """The server's answer when the Pi didn't."""
    return {"generated_at": time.time(), "where": "server", "reachable": False, "pi_url": url,
            "overall": "bad", "problems": [_problem("pi", "bad", error, "Check that the Pi is on and its app is "
                                                    "running. Its own page is http://10.0.0.247:5000/machine/health?stay=1")],
            "error": error}


# --- the page and its API -------------------------------------------------------------

def add_health_routes(app, scanner, machine, web_dir, run=None, sensors=None):
    from flask import jsonify, request, send_from_directory

    from .remote_machine import RemoteMachine
    remote = isinstance(machine, RemoteMachine)
    if not remote:
        keep_warnings()
        sensors = sensors or BinSensors()

    @app.get("/machine/health")
    def health_page():
        return send_from_directory(web_dir, "health.html")

    @app.get("/api/machine/health")
    def machine_health():
        if remote:
            try:
                rep = machine.health()
                rep["reachable"] = True
            except (RuntimeError, ValueError) as e:
                rep = unreachable(str(e), machine.url)
            rep["server"] = {"hostname": _safe(socket.gethostname), "pi_url": machine.url}
        else:
            rep = report(scanner, machine, sensors, run)
        resp = jsonify(rep)
        if request.args.get("download") == "1":
            stamp = time.strftime("%Y%m%d-%H%M", time.localtime(rep.get("generated_at") or time.time()))
            resp.headers["Content-Disposition"] = f'attachment; filename="sortr-health-{stamp}.json"'
        return resp

    @app.post("/api/machine/health/sensors")
    def machine_health_sensors():
        """{"kind": "full" | "seated", "fitted": true/false}: which bin sensors are wired."""
        body = request.get_json(silent=True) or {}
        try:
            if remote:
                machine.set_bin_sensors(str(body.get("kind")), bool(body.get("fitted")))
                return jsonify(machine.health())
            sensors.set_fitted(str(body.get("kind")), bool(body.get("fitted")))
        except ValueError as e:
            return jsonify(error=str(e)), 400
        except RuntimeError as e:
            return jsonify(error=str(e)), 503
        except OSError:
            return jsonify(error="Couldn't save that. Is the data folder full or read-only?"), 503
        event("sensors", f"Bin {body.get('kind')} sensors marked as {'fitted' if body.get('fitted') else 'not fitted'}")
        return jsonify(report(scanner, machine, sensors, run))
