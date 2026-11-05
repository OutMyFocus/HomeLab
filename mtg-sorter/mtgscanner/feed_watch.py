"""Feed one card while watching the camera, and stop the motor as soon as it lands.

Why a timed push can't do this: the feeder's wheels sit about 20 mm behind its gate
(roller_y in hardware/feeder.scad). When a card has gone as far as they can push it, its
last 20 mm is still under the stack, so it hangs in the slot until the next card drags it
out, and then two or three come at once and the first one flies over the stop teeth. The
same push time gave 0, 1 or 3 cards in Nic's tests (2026-11-05), depending on grip.

So instead the motor runs until the camera sees a card drop into the LANDING ZONE, a
band across the bed just above the stop teeth, then stops at once. A card hanging in the
slot doesn't reach the zone; the moment it comes free and slides down, it does.

The zone is a box [x0, y0, x1, y1] as shares of the camera picture (after the Scanner
page's Rotate and Crop). It's kept in data/machine_settings.json ("feeder": {"zone": ...})
and set with POST /api/machine/save {"feed_zone": [...]}; config.FEED_ZONE until then.
The bed must be empty when a feed starts: the zone is compared with how it looked then.
"""

import threading
import time

import cv2
import numpy as np
from flask import jsonify, request

from . import config
from .machine import load_saved

SMALL_W = 160   # pictures are compared at this width: plenty to see a card, and quick


def small_gray(frame) -> np.ndarray:
    h, w = frame.shape[:2]
    small = cv2.resize(frame, (SMALL_W, max(1, round(h * SMALL_W / w))), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) if small.ndim == 3 else small
    return cv2.GaussianBlur(gray, (5, 5), 0)


def clean_zone(zone):
    """[x0, y0, x1, y1] shares of the picture, or None if it isn't one."""
    try:
        x0, y0, x1, y1 = (float(v) for v in zone)
    except (TypeError, ValueError):
        return None
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        return None
    return [round(v, 4) for v in (x0, y0, x1, y1)]


def changed_share(ref: np.ndarray, now: np.ndarray, zone) -> float:
    """How much of the zone looks different from the reference picture (0-1)."""
    if ref.shape != now.shape:
        return 0.0
    h, w = ref.shape
    x0, y0, x1, y1 = zone
    top, left = int(y0 * h), int(x0 * w)
    rows = slice(top, max(top + 1, int(y1 * h)))
    cols = slice(left, max(left + 1, int(x1 * w)))
    # A shadow or the lights changing shifts the whole picture a little; a card is a big
    # local change. Taking out the whole picture's typical shift (the median, which the bed
    # around the card sets) keeps a passing hand from counting as a card.
    shift = int(np.median(now.astype(np.int16) - ref.astype(np.int16)))
    diff = np.abs(now[rows, cols].astype(np.int16) - ref[rows, cols].astype(np.int16) - shift)
    return float(np.count_nonzero(diff > config.FEED_DIFF_LEVEL)) / diff.size


class FrameTap:
    """The machine camera's latest picture, small and grey, handed over by the Scanner's
    loop (Scanner.tap). Only kept while a feed is watching, so it costs nothing otherwise."""

    def __init__(self):
        self.cond = threading.Condition()
        self.watching = 0
        self.seq = 0
        self.small = None

    def put(self, frame):
        if not self.watching:
            return
        small = small_gray(frame)
        with self.cond:
            self.small, self.seq = small, self.seq + 1
            self.cond.notify_all()

    def next(self, after: int, timeout: float):
        """The first picture newer than `after`: (seq, picture), or (after, None) on a timeout."""
        end = time.monotonic() + timeout
        with self.cond:
            while self.seq <= after:
                left = end - time.monotonic()
                if left <= 0:
                    return after, None
                self.cond.wait(left)
            return self.seq, self.small


def feed_zone() -> list:
    saved = load_saved().get("feeder", {})
    return clean_zone(saved.get("zone")) or list(config.FEED_ZONE)


def save_zone(machine, zone):
    zone = clean_zone(zone)
    if zone is None:
        raise ValueError("The zone is [x0, y0, x1, y1], each 0-1, as shares of the picture")
    saved = load_saved()
    saved.setdefault("feeder", {})["zone"] = zone
    machine._write(saved)


class FeedWatcher:
    def __init__(self, scanner, machine):
        self.scanner, self.machine = scanner, machine
        self.tap = FrameTap()
        scanner.tap = self.tap
        self.busy = threading.Lock()

    def feed_one(self, speed=None, max_seconds=None, zone=None, backoff=None) -> dict:
        """Run the feeder until a card lands in the zone (or max_seconds pass), then stop,
        then turn the wheels backwards for `backoff` seconds (config.FEED_BACKOFF_SECONDS) so
        the next card, which followed it out of the slot, goes back into the hopper.
        Returns what happened: result is "landed", "over" (it went past the zone, over the
        teeth), or "none" (nothing reached the zone: no grip, or a card hanging in the slot)."""
        zone = clean_zone(zone) if zone is not None else feed_zone()
        if zone is None:
            raise ValueError("The zone is [x0, y0, x1, y1], each 0-1, as shares of the picture")
        max_seconds = min(5.0, max(0.2, float(max_seconds or config.FEED_MAX_SECONDS)))
        if not self.busy.acquire(blocking=False):
            raise RuntimeError("Already feeding a card")
        self.tap.watching += 1
        try:
            seq, ref = self.tap.next(self.tap.seq, timeout=2.0)
            if ref is None:
                raise RuntimeError("No camera picture to watch: is the Pi camera on and picked on the Scanner page?")
            trace, landed_ms = [], None
            t0 = time.monotonic()
            # The machine's own timer stops the motor at max_seconds even if this thread dies.
            self.machine.feed(seconds=max_seconds, speed=speed)
            try:
                while time.monotonic() - t0 < max_seconds:
                    seq, now = self.tap.next(seq, timeout=0.5)
                    if now is None:
                        continue
                    share = changed_share(ref, now, zone)
                    trace.append([round(1000 * (time.monotonic() - t0)), round(share, 3)])
                    if share >= config.FEED_LAND_SHARE:
                        landed_ms = trace[-1][0]
                        break
            finally:
                self.machine.stop_feeder()
            motor_ms = round(1000 * (time.monotonic() - t0))
            backoff = min(1.0, max(0.0, float(config.FEED_BACKOFF_SECONDS if backoff is None else backoff)))
            if landed_ms is not None and backoff:
                # The wheels drive the next card out behind the one that landed (they touch it as
                # soon as the first card's tail passes them). It ends up hanging over the landed
                # card and pins it, so pull it back into the hopper: a short turn the other way.
                self.machine.feed(seconds=backoff, speed=speed, backward=True)
                time.sleep(backoff)
                self.machine.stop_feeder()
            # Let it come to rest, then look again: still there, or did it go over the teeth?
            share = 0.0
            settle_end = time.monotonic() + config.FEED_SETTLE_SECONDS
            while time.monotonic() < settle_end:
                seq, now = self.tap.next(seq, timeout=0.5)
                if now is not None:
                    share = changed_share(ref, now, zone)
                    trace.append([round(1000 * (time.monotonic() - t0)), round(share, 3)])
            if landed_ms is None:
                result = "landed" if share >= config.FEED_LAND_SHARE else "none"
            else:
                result = "landed" if share >= config.FEED_LAND_SHARE / 2 else "over"
            return {"result": result, "landed_ms": landed_ms, "motor_ms": motor_ms, "backoff_ms": round(1000 * backoff) if landed_ms is not None else 0,
                    "zone": zone, "settled_share": round(share, 3), "trace": trace}
        finally:
            self.tap.watching -= 1
            self.busy.release()


MESSAGES = {
    "landed": "Fed one card: it landed on the bed.",
    "over": "A card came out but slid past the stop teeth: try a lower speed.",
    "none": "No card reached the bed: check the feeder's grip, or a card stuck in the slot.",
}


def add_feed_watch_routes(app, scanner, machine):
    """POST /api/machine/feed_one: feed a card watching the camera. On the server (no
    hardware) the Pi does it, since the Pi has both the motor and the camera."""
    watcher = None if hasattr(machine, "feed_one") else FeedWatcher(scanner, machine)
    run = machine.feed_one if watcher is None else watcher.feed_one

    @app.post("/api/machine/feed_one")
    def machine_feed_one():
        body = request.get_json(silent=True) or {}
        try:
            out = run(body.get("speed"), body.get("max_seconds"), body.get("zone"), body.get("backoff"))
        except (ValueError, TypeError) as e:
            return jsonify(error=str(e)), 400
        except RuntimeError as e:
            return jsonify(error=str(e)), 503
        return jsonify(out | {"message": MESSAGES.get(out.get("result"), "")})

    @app.get("/api/machine/feed_zone")
    def machine_feed_zone_get():
        if watcher is None:
            return jsonify({"zone": machine.feed_zone()})
        return jsonify({"zone": feed_zone()})

    @app.post("/api/machine/feed_zone")
    def machine_feed_zone():
        body = request.get_json(silent=True) or {}
        try:
            if watcher is None:
                machine.save_feed_zone(body.get("zone"))
            else:
                save_zone(machine, body.get("zone"))
        except (ValueError, TypeError) as e:
            return jsonify(error=str(e)), 400
        except RuntimeError as e:
            return jsonify(error=str(e)), 503
        return jsonify({"zone": clean_zone(body.get("zone"))})

    return watcher
