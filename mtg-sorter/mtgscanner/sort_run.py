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
  unsure    the scanner's best guess wasn't sure, or
  unknown   not recognized in time (config.SORT_RECOGNIZE_SECONDS, with the light bars
            dimmed for a second look after SORT_FOIL_AFTER: foils glare). Nic (2026-11-07):
            the pins only drop for a recognized card. So the run waits with the pins up
            and the card on the bed ("waiting" in the status) until you choose on the page:
            Look again, Unread bin (drop it into the fallback bin: the Bins page's
            "everything else", or config.SORT_FALLBACK_BIN when that is bin 0), or Stop. If
            the scanner reads the card meanwhile (you straightened it, say), it carries on
            by itself. config.SORT_DROP_UNREAD = True drops it to the fallback bin at once.
  none      nothing reached the bed (the run stops after two in a row: hopper empty)
  stuck     a card came part way out and stopped moving: the gate holds it; the run stops
  double    two cards came out together: the run stops with the pins up, nothing dropped

The run stops on its own when a card is left on the bed after the retries (something is
caught) or when nothing came out twice in a row.

Wanted cards (Bins page, 2026-11-08): a card on the wanted list goes to the wanted bin,
whatever the price rules say, until the listed number of copies has been pulled in this
run. The rules are fixed when the run starts. Started from the server (MTG_MACHINE_URL),
the server sends its own Bins page rules with the start, so the list you made there is
the one the Pi uses; started on the Pi's own page, the Pi's saved rules are used.
"""

import threading
import time

from flask import jsonify, request

from . import config, sort_rules

LANDED_FROM = 0.45          # a landed card's middle is below this share of the picture's height
MAX_CARDS = 1000


class DoubleFeed(RuntimeError):
    """Two cards reached the bed at once; the run stops rather than sort them as one."""


class StopHere(RuntimeError):
    """Stop pressed while a card waited on the bed: the run ends with the pins up."""


class SortRun:
    def __init__(self, watcher, scanner, machine):
        self.watcher, self.scanner, self.machine = watcher, scanner, machine
        self.lock = threading.Lock()
        self.thread = None
        self.stop_asked = False
        self.decision = None        # what was chosen for a card waiting on the bed
        self.rules = None           # the Bins page rules for this run (fixed at the start)
        self.taken = {}             # wanted cards pulled this run: {name key: copies}
        self.state = {"running": False, "cards": [], "done": None, "speed": None, "max_cards": 0,
                      "waiting": None}

    # --- control ----------------------------------------------------------------

    def start(self, speed=None, max_cards=None, rules=None) -> dict:
        """`rules`: Bins page rules sent with the start (from the server); else the saved ones."""
        rules = sort_rules.clean(rules) if isinstance(rules, dict) else sort_rules.load()
        with self.lock:
            if self.state["running"]:
                raise RuntimeError("A sort run is already going: stop it first")
            speed = round(min(1.0, max(0.1, float(speed or self.machine.feeder_defaults()["speed"]))), 2)
            max_cards = max(0, min(MAX_CARDS, int(max_cards or 0)))
            self.stop_asked = False
            self.decision = None
            self.rules, self.taken = rules, {}
            self.state = {"running": True, "cards": [], "done": None, "speed": speed,
                          "max_cards": max_cards, "started_at": time.time(), "waiting": None}
            self.thread = threading.Thread(target=self._run, args=(speed, max_cards), daemon=True)
            self.thread.start()
        return self.status()

    def stop(self) -> dict:
        self.stop_asked = True
        return self.status()

    def decide(self, action) -> dict:
        """For a card waiting on the bed: "retry" (look again), "fallback" (drop it into
        the unread bin and carry on) or "stop"."""
        if action not in ("retry", "fallback", "stop"):
            raise ValueError("Choose retry, fallback or stop")
        if not self.state.get("waiting"):
            raise ValueError("No card is waiting")
        self.decision = action
        return self.status()

    def status(self) -> dict:
        with self.lock:
            s = dict(self.state)
            cards = s["cards"]
        rules = self.rules or sort_rules.load()
        names = rules["names"]
        tally = {}
        for c in cards:
            if c.get("bin") is not None:
                tally[str(c["bin"])] = tally.get(str(c["bin"]), 0) + 1
        s["tally"] = [{"bin": int(b), "label": names.get(b, f"Bin {b}"), "cards": n} for b, n in sorted(tally.items())]
        s["counts"] = {k: sum(1 for c in cards if c.get("status") == k)
                       for k in ("saved", "unsure", "unknown", "none", "stuck", "double")}
        want = sort_rules.wanted_counts(rules)
        s["wanted"] = {"bin": rules["wanted"]["bin"], "cards": sum(want.values()),
                       "found": sum(min(self.taken.get(k, 0), q) for k, q in want.items()),
                       "pulled": [c["name"] for c in cards if c.get("wanted")]} if want else None
        s["value"] = round(sum(c.get("price") or 0 for c in cards if c.get("status") == "saved"), 2)
        warn = int(getattr(config, "SORT_BIN_WARN", 0) or 0)
        s["full"] = [t["bin"] for t in s["tally"] if warn and t["cards"] >= warn]
        s["warning"] = (f"Bin {', '.join(map(str, s['full']))} has had {warn}+ cards since the start: "
                        "empty it so the cards keep dropping clear" if s["full"] else None)
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
                # Start this card with a clean table: a new card lands where the last one
                # sat, and the scanner would carry on that card's track (and name) for it.
                with self.scanner.lock:
                    self.scanner.forget_tracks()
                # Held servos let go after SERVO_HOLD_LIMIT with no new move, and the
                # trapdoors sag open once they do: tell them "closed" again for every card.
                for part, position in (("door_l", "closed"), ("door_r", "closed"), ("pins", "up")):
                    try:
                        self.machine.move(part, position)
                    except Exception:
                        pass
                try:
                    out = self.watcher.sort_one(None, speed=speed, choose=lambda fed, c=card: self._choose(c))
                except (DoubleFeed, StopHere) as e:
                    with self.lock:
                        self.state["cards"].append(card | {"seconds": round(time.monotonic() - t0, 1)})
                    reason = str(e)
                    return
                except (RuntimeError, ValueError) as e:
                    reason = f"error: {e}"
                    return
                card.update({"result": out["result"], "dropped": out.get("dropped"),
                             "drop_tries": out.get("drop_tries", 0), "left_share": out.get("left_share"),
                             "seconds": round(time.monotonic() - t0, 1)})
                if out["result"] in ("none", "stuck"):
                    card["status"], card["bin"] = out["result"], None
                with self.lock:
                    self.state["cards"].append(card)
                if out["result"] == "stuck":
                    reason = "a card is held in the slot: open the gate a little and take the card off the bed"
                    return
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
                self.state["waiting"] = None
                self.state["done"] = reason

    @staticmethod
    def _apart(tracks) -> bool:
        """Two card-sized tracks whose middles are a fifth of a card apart or more. A card
        the scanner sees twice at nearly the same spot doesn't count, and neither does a
        much smaller outline: a borderless card's art or text box found as a "card" of its
        own stopped a run with one card on the bed (Precise Redaction, 2026-11-08)."""
        import itertools
        least = float(getattr(config, "SORT_DOUBLE_MIN_SIZE", 0.8))
        for a, b in itertools.combinations(tracks, 2):
            small, big = sorted((a.size, b.size))
            if big <= 0 or small / big < least:
                continue
            gap = float(abs(a.center - b.center).max())
            if gap > 0.2 * max(a.size, b.size, 1.0):
                return True
        return False

    @staticmethod
    def real_bin(bin_no) -> int:
        """The rules' bin 0 (unknown price) has no tray: config.SORT_FALLBACK_BIN instead."""
        bins = getattr(config, "SORT_BINS", {1: "left", 2: "centre", 3: "right"})
        return int(bin_no) if int(bin_no) in bins else int(getattr(config, "SORT_FALLBACK_BIN", 1))

    def _lights(self):
        lights = getattr(self.scanner, "lights", None)
        return lights if lights is not None and hasattr(lights, "update") and hasattr(lights, "settings") else None

    def _dim_lights(self):
        """Turn the light bars down for a second look at a card that glares (a foil).
        Returns the brightness to put back, or None when there are no bars to dim."""
        lights = self._lights()
        if lights is None:
            return None
        try:
            before = int(lights.settings.get("brightness", 0))
            level = int(getattr(config, "SORT_FOIL_BRIGHTNESS", 8))
            if before <= level:
                return None
            lights.update({"brightness": level})
            return before
        except Exception:
            return None

    def _restore_lights(self, brightness):
        lights = self._lights()
        if lights is not None:
            try:
                lights.update({"brightness": int(brightness)})
            except Exception:
                pass

    def _read(self, card: dict, fed_at: float):
        """The track the scanner has for the card on the teeth right now (locked, unsure or
        "unknown" so far), or None. Raises DoubleFeed. Call with scanner.lock held."""
        height = (self.scanner.frame_size or (0, 0))[1] or 1
        # Only a card recognized since this feed began, in the lower half of the picture
        # (cards come in at the top and stop at the teeth at the bottom): the scanner keeps
        # a dropped card's track, and the next card hanging out of the slot shows at the
        # top, and either would end the wait at once.
        tracks = [t for t in self.scanner.tracks
                  if t.status in ("locked", "unsure", "unknown") and t.checked_time >= fed_at
                  and t.streak_key == (t.card.id if t.card else "unknown")   # latest look agrees
                  and float(t.center[1]) / height >= LANDED_FROM]
        if len(tracks) >= 2 and self._apart(tracks):
            # Two cards on the bed at once: the feeder let a pair through. Sorting the pair
            # as one card puts an unsaved card in the wrong bin, so stop with the pins up
            # and let someone take them off (seen 2026-11-06).
            card.update({"status": "double", "bin": None})
            raise DoubleFeed("two cards came out together: take them off the bed and press Start again")
        return max(tracks, key=lambda t: float(t.center[1]), default=None)

    def _hold_for_decision(self, card: dict, fed_at: float):
        """An unread card stays on the bed, pins up, until it is read after all (returns
        the locked track), or the page says "retry" (returns "retry"), "fallback" (None)
        or "stop" (raises StopHere)."""
        self.decision = None
        with self.lock:
            self.state["waiting"] = {"n": card["n"], "status": card.get("status"), "name": card.get("name"),
                                     "since": time.time(),
                                     "message": "Card not recognized: the pins stay up. Straighten or turn it, "
                                                "then Look again, or send it to the unread bin."}
        try:
            while True:
                if self.stop_asked:
                    raise StopHere("stopped with an unread card on the bed")
                choice, self.decision = self.decision, None
                if choice == "stop":
                    self.stop_asked = True
                    raise StopHere("stopped with an unread card on the bed: take it off")
                if choice in ("retry", "fallback"):
                    return choice if choice == "retry" else None
                with self.scanner.lock:
                    track = self._read(card, fed_at)
                    if track is not None and track.status == "locked":
                        return track            # read after all (moved by hand, say)
                time.sleep(0.2)
        finally:
            with self.lock:
                self.state["waiting"] = None

    def _choose(self, card: dict) -> int:
        """Asked by sort_one once the card is on the stop teeth: wait for the scanner to
        recognize it, save it, and say which bin it goes in. Fills in `card` for the table.
        An unread card waits on the bed for a decision (see the top of this file)."""
        rules = self.rules or sort_rules.load()
        fallback = self.real_bin(sort_rules.unread_bin(rules))
        while True:
            track = self._look(card)
            if track is not None and track.status == "locked":
                break
            with self.scanner.lock:
                shown = track.card if track is not None else None
            card.update({"status": "unsure" if shown is not None else "unknown",
                         "name": shown.name if shown is not None else None})
            if getattr(config, "SORT_DROP_UNREAD", False):
                break
            held = self._hold_for_decision(card, card.get("fed_at", 0.0))
            if held == "retry":
                # a fresh look: forget what was seen, so an old "unsure" doesn't end it at once
                card["retries"] = card.get("retries", 0) + 1
                with self.scanner.lock:
                    self.scanner.forget_tracks()
                card["fed_at"] = time.monotonic()
                continue
            track = held                # the locked track, or None for the unread bin
            if track is None:
                card["by_hand"] = "unread bin"
            break
        return self._finish(card, track, rules, fallback)

    def _look(self, card: dict):
        """Wait up to SORT_RECOGNIZE_SECONDS for the card to be read (dimming the bars for
        a second look); the track found (locked or unsure), or None."""
        started = time.monotonic()
        deadline = started + float(getattr(config, "SORT_RECOGNIZE_SECONDS", 8.0))
        foil_after = float(getattr(config, "SORT_FOIL_AFTER", 3.0))
        track = None
        dimmed = None
        fed_at = card.get("fed_at", 0.0)
        try:
            while time.monotonic() < deadline and not self.stop_asked:
                if dimmed is None and time.monotonic() - started >= foil_after:
                    dimmed = self._dim_lights()     # a second look with less glare (foils)
                    card["dimmed"] = dimmed is not None
                with self.scanner.lock:
                    track = self._read(card, fed_at)
                    if track is not None and track.status in ("locked", "unsure"):
                        break
                    # "unknown" so far: the first looks at a card are often while it is still
                    # sliding or blurred, so keep waiting for a match until the deadline
                    track = None
                time.sleep(0.1)
        finally:
            # Always put the bars back, also when a double feed stops the run mid-look:
            # left at 8 % the camera crawled at 4 fps and looked frozen (2026-11-08).
            if dimmed is not None:
                self._restore_lights(dimmed)
        card["seconds_reading"] = round(card.get("seconds_reading", 0) + time.monotonic() - started, 1)
        return track

    def _finish(self, card: dict, track, rules, fallback) -> int:
        """Save a recognized card and pick its bin; anything else goes to the fallback bin."""
        if track is None:
            card.update({"status": card.get("status") if card.get("status") in ("unsure", "unknown") else "unknown",
                         "bin": fallback, "bin_label": rules["names"][str(fallback)]})
            return fallback
        with self.scanner.lock:
            shown = track.card
            if track.status == "locked" and shown is not None:
                foil = self.scanner.foil
                if not track.saved:
                    self.scanner._save(shown, foil, track, auto=True)
                saved = self.scanner.session[-1] if self.scanner.session else {}
                if saved.get("track") != track.id:
                    saved = {}
                # this run's rules (and wanted copies left), not the bin the scan was saved with
                wanted = sort_rules.wanted_for(shown, rules, self.taken)
                bin_no, label = sort_rules.pick(shown, foil, saved.get("price"), rules, self.taken)
                if wanted:
                    self.taken[wanted] = self.taken.get(wanted, 0) + 1
                    card["wanted"] = True
                real = self.real_bin(bin_no)
                if real != bin_no and not wanted:       # bin 0 → the tray for unread cards
                    real = self.real_bin(sort_rules.unread_bin({**rules, "fallback": real}))
                card.update({"status": "saved", "name": shown.name, "set": shown.set_code,
                             "number": shown.collector_number, "price": saved.get("price"),
                             "bin": real, "bin_label": label if real == bin_no else rules["names"][str(real)]})
                return real
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
            # the Pi sorts by the rules (and wanted list) on this server's Bins page
            return answer(lambda: machine.sort_start({**body, "rules": sort_rules.load()}))
        return answer(lambda: run.start(body.get("speed"), body.get("max_cards"), body.get("rules")), 409)

    @app.get("/api/machine/sort")
    def sort_status():
        return answer(machine.sort_status if run is None else run.status)

    @app.post("/api/machine/sort/stop")
    def sort_stop():
        return answer(machine.sort_stop if run is None else run.stop)

    @app.post("/api/machine/sort/decide")
    def sort_decide():
        """For a card waiting on the bed: {"action": "retry" | "fallback" | "stop"}."""
        action = (request.get_json(silent=True) or {}).get("action")
        if run is None:
            return answer(lambda: machine.sort_decide(action))
        return answer(lambda: run.decide(action))

    return run
