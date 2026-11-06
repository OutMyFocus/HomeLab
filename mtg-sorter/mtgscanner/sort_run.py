"""The sort run: the machine working on its own. Card after card it feeds one onto the
bed, lets the scanner recognize it, saves it to the collection, picks its bin by the Bins
page rules (sort_rules.py) and drops it there, until the hopper is empty or you press Stop.

Started with POST /api/machine/sort (Start sorting on the Machine page) and watched with
GET /api/machine/sort; it runs on its own thread on the Pi, which has the motor, the
camera and a scanner. Each card is FeedWatcher.sort_one with a `choose` step in the
middle: once the card has landed on the stop teeth the camera's pictures go back to the
scanner, which recognizes the card as on the Scan page; then the pins drop and the card
is dropped into its bin, with the usual check that the bed is clear.

What each card ends up as:
  saved     recognized for sure: saved to the collection, dropped into its rules bin
  unsure    the scanner's best guess wasn't sure: not saved, dropped into the fallback bin
            (the Bins page's "everything else", or config.SORT_FALLBACK_BIN when that is
            bin 0, which has no tray) so you can look at it by hand
  unknown   not recognized in time: the same, not saved
  none      nothing reached the bed (the run stops after two in a row: hopper empty)

The run stops on its own when a card is left on the bed after the retries (something is
caught) or when nothing came out twice in a row.
"""

import threading
import time

from flask import jsonify, request

from . import config, sort_rules

RECOGNIZE_SECONDS = 6.0     # how long to give the scanner to make its mind up
LANDED_FROM = 0.45          # a landed card's middle is below this share of the picture's height
MAX_CARDS = 1000


class SortRun:
    def __init__(self, watcher, scanner, machine):
        self.watcher, self.scanner, self.machine = watcher, scanner, machine
        self.lock = threading.Lock()
        self.thread = None
        self.stop_asked = False
        self.state = {"running": False, "cards": [], "done": None, "speed": None, "max_cards": 0}

    # --- control ----------------------------------------------------------------

    def start(self, speed=None, max_cards=None) -> dict:
        with self.lock:
            if self.state["running"]:
                raise RuntimeError("A sort run is already going: stop it first")
            speed = round(min(1.0, max(0.1, float(speed or self.machine.feeder_defaults()["speed"]))), 2)
            max_cards = max(0, min(MAX_CARDS, int(max_cards or 0)))
            self.stop_asked = False
            self.state = {"running": True, "cards": [], "done": None, "speed": speed,
                          "max_cards": max_cards, "started_at": time.time()}
            self.thread = threading.Thread(target=self._run, args=(speed, max_cards), daemon=True)
            self.thread.start()
        return self.status()

    def stop(self) -> dict:
        self.stop_asked = True
        return self.status()

    def status(self) -> dict:
        with self.lock:
            s = dict(self.state)
            cards = s["cards"]
        names = sort_rules.names()
        tally = {}
        for c in cards:
            if c.get("bin") is not None:
                tally[str(c["bin"])] = tally.get(str(c["bin"]), 0) + 1
        s["tally"] = [{"bin": int(b), "label": names.get(b, f"Bin {b}"), "cards": n} for b, n in sorted(tally.items())]
        s["counts"] = {k: sum(1 for c in cards if c.get("status") == k) for k in ("saved", "unsure", "unknown", "none")}
        s["value"] = round(sum(c.get("price") or 0 for c in cards if c.get("status") == "saved"), 2)
        return s

    # --- the run ----------------------------------------------------------------

    def _run(self, speed, max_cards):
        reason = "finished"
        nothing_in_a_row = 0
        try:
            self.machine.home()
            while not self.stop_asked:
                if max_cards and len(self.state["cards"]) >= max_cards:
                    reason = f"did the {max_cards} cards asked for"
                    return
                card = {"n": len(self.state["cards"]) + 1, "status": "none", "bin": None, "name": None}
                t0 = time.monotonic()
                card["fed_at"] = t0
                try:
                    out = self.watcher.sort_one(None, speed=speed, choose=lambda fed, c=card: self._choose(c))
                except (RuntimeError, ValueError) as e:
                    reason = f"error: {e}"
                    return
                card.update({"result": out["result"], "dropped": out.get("dropped"),
                             "drop_tries": out.get("drop_tries", 0), "seconds": round(time.monotonic() - t0, 1)})
                if out["result"] == "none":
                    card["status"], card["bin"] = "none", None
                with self.lock:
                    self.state["cards"].append(card)
                nothing_in_a_row = nothing_in_a_row + 1 if out["result"] == "none" else 0
                if out.get("dropped") is False:
                    reason = "a card is still on the bed after the retries: take it out and look at what it caught on"
                    return
                if nothing_in_a_row >= 2:
                    reason = "nothing came out twice in a row: the hopper is empty"
                    return
            reason = "stopped"
        finally:
            with self.lock:
                self.state["running"] = False
                self.state["done"] = reason

    @staticmethod
    def real_bin(bin_no) -> int:
        """The rules' bin 0 (unknown price) has no tray: config.SORT_FALLBACK_BIN instead."""
        bins = getattr(config, "SORT_BINS", {1: "left", 2: "centre", 3: "right"})
        return int(bin_no) if int(bin_no) in bins else int(getattr(config, "SORT_FALLBACK_BIN", 1))

    def _choose(self, card: dict) -> int:
        """Asked by sort_one once the card is on the stop teeth: wait for the scanner to
        recognize it, save it, and say which bin it goes in. Fills in `card` for the table."""
        rules = sort_rules.load()
        fallback = self.real_bin(rules["fallback"])
        deadline = time.monotonic() + RECOGNIZE_SECONDS
        track = None
        fed_at = card.get("fed_at", 0.0)
        while time.monotonic() < deadline and not self.stop_asked:
            with self.scanner.lock:
                height = (self.scanner.frame_size or (0, 0))[1] or 1
                # Only a card recognized since this feed began, in the lower half of the
                # picture (cards come in at the top and stop at the teeth at the bottom):
                # the scanner keeps a dropped card's track, and the next card hanging out
                # of the slot shows at the top, and either would end the wait at once.
                tracks = [t for t in self.scanner.tracks
                          if t.status in ("locked", "unsure", "unknown") and t.checked_time >= fed_at
                          and float(t.center[1]) / height >= LANDED_FROM]
                track = max(tracks, key=lambda t: float(t.center[1]), default=None)
                if track is not None and track.status in ("locked", "unsure"):
                    break
                # "unknown" so far: the first looks at a card are often while it is still
                # sliding or blurred, so keep waiting for a match until the deadline
                track = None
            time.sleep(0.1)
        if track is None:
            card.update({"status": "unknown", "bin": fallback, "bin_label": rules["names"][str(fallback)]})
            return fallback
        with self.scanner.lock:
            shown = track.card
            if track.status == "locked" and shown is not None:
                foil = self.scanner.foil
                if not track.saved:
                    self.scanner._save(shown, foil, track, auto=True)
                saved = self.scanner.session[-1] if self.scanner.session else {}
                bin_no = int(saved.get("bin", fallback)) if saved.get("track") == track.id else None
                if bin_no is None:
                    bin_no, _ = sort_rules.pick(shown, foil, saved.get("price"), rules)
                bin_no = self.real_bin(bin_no)
                card.update({"status": "saved", "name": shown.name, "set": shown.set_code,
                             "number": shown.collector_number, "price": saved.get("price"),
                             "bin": bin_no, "bin_label": rules["names"][str(bin_no)]})
                return bin_no
            card.update({"status": "unsure" if shown is not None else "unknown",
                         "name": shown.name if shown is not None else None,
                         "bin": fallback, "bin_label": rules["names"][str(fallback)]})
            return fallback


def add_sort_run_routes(app, watcher, scanner, machine):
    """POST/GET /api/machine/sort and POST /api/machine/sort/stop. On the server (no
    hardware) the calls go to the Pi, which has the motor, the camera and a scanner."""
    run = None if watcher is None else SortRun(watcher, scanner, machine)

    def answer(action, timeout_error=503):
        try:
            return jsonify(action())
        except (ValueError, TypeError) as e:
            return jsonify(error=str(e)), 400
        except RuntimeError as e:
            return jsonify(error=str(e)), timeout_error

    @app.post("/api/machine/sort")
    def sort_start():
        body = request.get_json(silent=True) or {}
        if run is None:
            return answer(lambda: machine.sort_start(body))
        return answer(lambda: run.start(body.get("speed"), body.get("max_cards")), 409)

    @app.get("/api/machine/sort")
    def sort_status():
        return answer(machine.sort_status if run is None else run.status)

    @app.post("/api/machine/sort/stop")
    def sort_stop():
        return answer(machine.sort_stop if run is None else run.stop)

    return run
