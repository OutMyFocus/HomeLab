"""The tuning run: sort card after card round the bins, score every feed, and nudge the
settings after each miss until the machine runs clean.

Started from the Machine page (POST /api/machine/tune), it runs on its own thread on the
Pi (the one with the motor and the camera) and the page polls GET /api/machine/tune for
the table. Each feed is FeedWatcher.sort_one: feed one card watching the camera, drop it
into the next bin, check the bed is clear. What the result says, and what the run does
about it when "adjust" is on (from the 2026-11-06 camera tests):

  over      the card rushed past the stop teeth: the feeder was too fast  -> speed - 0.05
  none      nothing reached the bed: no grip, or the hopper is empty       -> speed + 0.05,
            and the run stops after two in a row (top up the stack)
  2 drops   the card needed a second drop: it slid off the teeth slowly    -> pins + 0.5 s
  not gone  the card is still on the bed after the retries: it is caught   -> stop, someone
            on something and needs a hand                                     has to look
  landed, gone first time = clean

The settings the run ends with are offered to be saved (POST /api/machine/tune/save):
the feeder speed as the usual one, the drop timings in data/machine_settings.json "sort".
"""

import threading
import time

from flask import jsonify, request

from . import config

SPEED_STEP = 0.05
PINS_STEP = 0.5
MAX_CYCLES = 20


class TuningRun:
    def __init__(self, watcher, machine):
        self.watcher, self.machine = watcher, machine
        self.lock = threading.Lock()
        self.thread = None
        self.stop_asked = False
        self.state = {"running": False, "feeds": [], "settings": None, "done": None}

    # --- control ----------------------------------------------------------------

    def start(self, cycles=4, bins=None, speed=None, adjust=True, pins_seconds=None,
              doors_seconds=None, tilt_seconds=None) -> dict:
        with self.lock:
            if self.state["running"]:
                raise RuntimeError("A tuning run is already going: stop it first")
            all_bins = sorted(getattr(config, "SORT_BINS", {1: "left", 2: "centre", 3: "right"}))
            bins = [int(b) for b in (bins or all_bins)]
            if not bins or any(b not in all_bins for b in bins):
                raise ValueError(f"Bins are {', '.join(map(str, all_bins))}")
            cycles = max(1, min(MAX_CYCLES, int(cycles or 4)))
            drop = self.machine.sort_defaults()
            settings = {
                "speed": round(min(1.0, max(0.1, float(speed or self.machine.feeder_defaults()["speed"]))), 2),
                "pins_seconds": float(drop["pins_seconds"] if pins_seconds is None else pins_seconds),
                "doors_seconds": float(drop["doors_seconds"] if doors_seconds is None else doors_seconds),
                "tilt_seconds": float(drop["tilt_seconds"] if tilt_seconds is None else tilt_seconds),
            }
            self.stop_asked = False
            self.state = {"running": True, "feeds": [], "settings": settings, "started": settings.copy(),
                          "plan": {"cycles": cycles, "bins": bins, "adjust": bool(adjust)},
                          "done": None, "changes": []}
            self.thread = threading.Thread(target=self._run, args=(cycles, bins, bool(adjust)), daemon=True)
            self.thread.start()
        return self.status()

    def stop(self) -> dict:
        self.stop_asked = True
        return self.status()

    def status(self) -> dict:
        with self.lock:
            s = dict(self.state)
            feeds = s["feeds"]
            clean = sum(1 for f in feeds if f.get("clean"))
            s["score"] = {"clean": clean, "total": len(feeds)}
            return s

    # --- the run ----------------------------------------------------------------

    def _run(self, cycles, bins, adjust):
        reason = "finished"
        nothing_in_a_row = 0
        try:
            self.machine.home()
            for cycle in range(cycles):
                for bin_no in bins:
                    if self.stop_asked:
                        reason = "stopped"
                        return
                    with self.lock:
                        st = dict(self.state["settings"])
                    drop = {k: st[k] for k in ("pins_seconds", "doors_seconds", "tilt_seconds")}
                    t0 = time.monotonic()
                    try:
                        out = self.watcher.sort_one(bin_no, speed=st["speed"], drop=drop)
                    except (RuntimeError, ValueError) as e:
                        reason = f"error: {e}"
                        return
                    feed = {"n": len(self.state["feeds"]) + 1, "cycle": cycle + 1, "bin": bin_no,
                            "result": out["result"], "landed_ms": out.get("landed_ms"),
                            "dropped": out.get("dropped"), "drop_tries": out.get("drop_tries", 0),
                            "left_share": out.get("left_share"), "speed": st["speed"],
                            "pins_seconds": st["pins_seconds"], "seconds": round(time.monotonic() - t0, 1)}
                    feed["clean"] = out["result"] == "landed" and out.get("dropped") is not False and feed["drop_tries"] <= 1
                    feed["note"], change = self._judge(out, st, adjust)
                    with self.lock:
                        self.state["feeds"].append(feed)
                        if change:
                            self.state["settings"].update(change)
                            self.state["changes"].append({"after": feed["n"], **change})
                    nothing_in_a_row = nothing_in_a_row + 1 if out["result"] == "none" else 0
                    if out.get("dropped") is False:
                        reason = "a card is still on the bed: take it out and look at what it caught on"
                        return
                    if nothing_in_a_row >= 2:
                        reason = "nothing came out twice in a row: is the hopper empty?"
                        return
        finally:
            with self.lock:
                self.state["running"] = False
                self.state["done"] = reason

    @staticmethod
    def _judge(out, st, adjust):
        """(note for the table, settings change or None)."""
        if out["result"] == "over":
            change = {"speed": round(max(0.3, st["speed"] - SPEED_STEP), 2)} if adjust else None
            return "went over the teeth: slower", change
        if out["result"] == "none":
            change = {"speed": round(min(1.0, st["speed"] + SPEED_STEP), 2)} if adjust else None
            return "nothing came out: faster", change
        if out.get("dropped") is False:
            return "still on the bed after the retries", None
        if out.get("drop_tries", 1) > 1:
            change = {"pins_seconds": round(min(6.0, st["pins_seconds"] + PINS_STEP), 1)} if adjust else None
            return "needed a second drop: pins down longer", change
        return "clean", None

    # --- saving -------------------------------------------------------------------

    def save(self) -> dict:
        with self.lock:
            st = self.state.get("settings")
            if not st or self.state["running"]:
                raise RuntimeError("Nothing to save yet: run the tuning first, and let it finish")
        feeder = self.machine.feeder_defaults()
        self.machine.save_feeder(feeder["seconds"], st["speed"])
        self.machine.save_sort(pins_seconds=st["pins_seconds"], doors_seconds=st["doors_seconds"],
                               tilt_seconds=st["tilt_seconds"])
        return dict(st)


def add_tuning_routes(app, watcher, machine):
    """POST/GET /api/machine/tune, /tune/stop, /tune/save. On the server (no hardware) the
    calls go to the Pi, which has the motor and the camera."""
    run = None if watcher is None else TuningRun(watcher, machine)

    def answer(action, timeout_error=503):
        try:
            return jsonify(action())
        except (ValueError, TypeError) as e:
            return jsonify(error=str(e)), 400
        except RuntimeError as e:
            return jsonify(error=str(e)), timeout_error

    @app.post("/api/machine/tune")
    def tune_start():
        body = request.get_json(silent=True) or {}
        if run is None:
            return answer(lambda: machine.tune_start(body))
        return answer(lambda: run.start(body.get("cycles"), body.get("bins"), body.get("speed"),
                                        body.get("adjust", True), body.get("pins_seconds"),
                                        body.get("doors_seconds"), body.get("tilt_seconds")), 409)

    @app.get("/api/machine/tune")
    def tune_status():
        return answer(machine.tune_status if run is None else run.status)

    @app.post("/api/machine/tune/stop")
    def tune_stop():
        return answer(machine.tune_stop if run is None else run.stop)

    @app.post("/api/machine/tune/save")
    def tune_save():
        return answer(machine.tune_save if run is None else run.save)

    return run
