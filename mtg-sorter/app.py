"""The scanner as an app in your web browser. It scans every card the camera sees.

    python app.py                  # the Pi camera (or webcam 0), then open http://localhost:5000
    python app.py --camera 1       # a different webcam (you can also switch on the page)
    python app.py --demo photos/   # no webcam: cycles through the photos in a folder

The page shows the live camera, the card it recognizes with its price and bin, this
session's cards, and a Photos tab where you can drop in pictures to scan. Cards are
saved to data/collection.csv, the same file scan.py uses (ready for Commander Vault).

It looks for cards anywhere in the picture. In Slots mode you draw a box for each card
position instead (a tray, an open box, spots marked on the mat) and it looks only there,
which also works for cards whose edges it can't find, like a card sitting in a box.

On the Raspberry Pi, run it with --host 0.0.0.0 and open http://<pi's address>:5000
from your laptop or phone.
"""

import argparse
import itertools
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, Response, abort, jsonify, make_response, request, send_file, send_from_directory
from mtgscanner import camera as cameras_mod, config, view
from mtgscanner.camera import BrowserSource, CameraSource, list_cameras  # noqa: F401  (tests patch these here)
from mtgscanner.captures import CaptureLog, true_card
from mtgscanner.collection import add_card, remove_entry, remove_last
from mtgscanner.database import Card, Matcher, connect
from mtgscanner.exchange import load_rate
from mtgscanner import accounts, assets, logins, security, sort_rules, wishlist
from mtgscanner.decks import name_key
from mtgscanner.history import add_history_routes
from mtgscanner.home import add_home_routes
from mtgscanner.sets import add_sets_routes
from mtgscanner.bins import add_bins_routes
from mtgscanner.decks import add_deck_routes
from mtgscanner.upgrades import add_upgrade_routes
from mtgscanner.library import add_collection_routes, lookup
from mtgscanner.lights import Lights, add_lights_routes
from mtgscanner.auto_straighten import AutoStraighten
from mtgscanner.wishlist import add_wishlist_routes
from mtgscanner.play import add_play_routes
from mtgscanner.vault import add_vault_routes
from mtgscanner.live import Live
from mtgscanner.feed_watch import add_feed_watch_routes
from mtgscanner.tuning import add_tuning_routes
from mtgscanner.machine import Machine, add_machine_routes, home_at_startup
from mtgscanner.remote_machine import RemoteCameraSource, RemoteLights, RemoteMachine, remote_url
from mtgscanner.recognize import Match, find_card_in_slot, find_cards, identify_outlines
from mtgscanner.sort_run import add_sort_run_routes
from mtgscanner.sorting import card_price, choose_bin
from mtgscanner.system import ON_PI, add_system_routes
from mtgscanner.tracking import Track, free_number, pair_up
from mtgscanner.training import forget_all, ready_to_learn, train
from mtgscanner.vault_prices import VaultPrices

WEB = Path(__file__).resolve().parent / "webui"


# --- Camera sources -------------------------------------------------------------

# CameraSource and list_cameras live in mtgscanner/camera.py; they're imported into this
# module's namespace (tests swap them out here).
SETTINGS_FILE = (
    config.DATA_DIR / "app_settings.json"
)  # camera and "collect" picked on the page, for next time


class DemoSource:
    """Pretends to be a camera: shows each photo for a few seconds, with a blank gap
    in between (like taking one card away and putting the next one down)."""

    def __init__(self, folder: str, seconds: float = 4.0):
        exts = {".jpg", ".jpeg", ".png", ".webp"}
        self.frames = [
            cv2.imread(str(p))
            for p in sorted(Path(folder).iterdir())
            if p.suffix.lower() in exts
        ]
        self.frames = [f for f in self.frames if f is not None]
        if not self.frames:
            raise SystemExit(f"No photos found in {folder}")
        self.seconds = seconds
        self.start = time.time()
        h, w = self.frames[0].shape[:2]
        self.blank = np.full((h, w, 3), 235, np.uint8)
        self.taken_at = 0.0

    def read(self):
        time.sleep(0.05)
        self.taken_at = time.monotonic()
        t = (time.time() - self.start) % (len(self.frames) * self.seconds)
        i, into = divmod(t, self.seconds)
        return self.blank if into > self.seconds - 1 else self.frames[int(i)]


class WaitingForCamera:
    """Stands in for the camera when none opens at startup, so the page still loads and
    says so. Tries again every few seconds and hands the camera to the scanner once one
    opens. (The Pi camera only shows up after a reboot; a webcam can be plugged in live.)"""

    def __init__(self, index: int | None, seconds: float = 5.0):
        self.index, self.seconds = index, seconds
        self.on_found = None  # set to Scanner.use_source
        self._next_try = time.monotonic() + seconds

    def read(self):
        time.sleep(0.2)
        if time.monotonic() < self._next_try:
            return None
        self._next_try = time.monotonic() + self.seconds
        try:
            camera = startup_camera(self.index)
        except RuntimeError:
            return None
        print(f"Camera found: {camera.name}")
        if self.on_found:
            self.on_found(camera)
        else:
            camera.release()
        return None


# --- The scanner, running in the background ----------------------------------------

SESSION_SHOWN = 100  # cards of this session listed on the scanner page


def _smooth(old: float | None, new: float, weight: float = 0.2) -> float:
    """A running average that follows changes gently (for the speed readout)."""
    return new if old is None else old + weight * (new - old)


class Scanner:
    """Looks at every card in the camera picture, all the time, in a background thread."""

    def __init__(self, matcher: Matcher, vault: VaultPrices | None, source, live: Live | None = None):
        self.matcher, self.vault, self.source, self.live = matcher, vault, source, live
        self.lights = None  # the RGB light bars (lights.py), which flash for saved, unsure and unknown cards
        self.lock = threading.Lock()
        self.jpeg = None  # latest camera picture for the page
        self.tap = None  # feed_watch.FrameTap: "Feed one card" watches the pictures through it
        self.frame_size = None  # (width, height) of the camera picture
        self.started = False  # True once the first picture arrived
        self.tracks: list[Track] = []  # the cards in view (see tracking.py)
        self._ids = itertools.count(1)
        self.foil = False
        self.auto = False
        self.mode = "auto"  # "auto": cards anywhere in the picture; "slots": only in the boxes you drew
        self.slots: list[
            list[float]
        ] = []  # each [x0, y0, x1, y1], as shares of the picture's width and height
        self.rotate = 0  # the camera picture turned clockwise this many degrees (view.py)
        self.crop: list[float] | None = None  # then cropped to this part of it; None = all of it
        self.straight = None  # then the camera's tilt and keystone undone (view.straighten_from)
        self._last_view = None  # the last picture after rotate and crop, before straightening
        self.auto_straight = config.AUTO_STRAIGHTEN  # straighten by itself from sure cards
        # Smallest outline that counts as a card, as a share of the picture (None:
        # config.MIN_CARD_AREA). Set from the card on the scan bed, it stops the scanner
        # reading an art or text box as a card of its own (Nic, 2026-11-08).
        self.min_card = None
        self._auto_straight = AutoStraighten()
        self._pending_straight = None  # a new straightening, put in between cards
        self.outline = (
            46,
            119,
            232,
        )  # BGR; kept for scan.py-style drawing, the page draws its own outlines
        self.session: list[dict] = []
        self._next_source = None
        self.collect = False  # keep every scan in data/captures (see captures.py)
        self.learn = True  # learn each confirmed scan as soon as its card is taken away
        self.captures = CaptureLog(config.CAPTURES_DIR)
        # Who is scanning (a name typed on a phone), saved as each card's Source. Blank
        # for the machine itself.
        self.owner = ""
        # Whose collection the cards go into, once accounts are on (accounts.py): the
        # person a phone's scanner belongs to, or whoever used the machine last. None is
        # the owner's (and the only) collection.
        self.account = None
        # A scanner fed by a phone's or computer's own camera (BrowserSource) lives in its
        # own thread next to the machine's. When its pictures stop it pauses, and after
        # `expire` seconds without any it stops and on_stop() drops it from the app.
        self.expire = 10 * 60.0
        self.stopped = False
        self.on_stop = None
        self.perf = {
            "fps": None,
            "ms_frame": None,
            "ms_find": None,
            "ms_identify": None,
            "frame_age_ms": None,
        }
        self._last_frame_time = None
        self._last_small = None       # a small grey copy of the last picture looked at
        self._last_look = 0.0         # when it was looked at (time.monotonic)
        self.jpeg_full = None         # the full-size picture, made only while someone streams ?full=1
        self.full_viewers = 0
        workers = config.IDENTIFY_THREADS or min(8, os.cpu_count() or 2)
        self._pool = ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="identify"
        )

    def use_source(self, source):
        """Switch cameras. The background thread makes the swap between frames."""
        with self.lock:
            pending, self._next_source = self._next_source, source
            current = self.source
        if pending is not None:  # switched twice before the first one took over
            pending.release()
        if isinstance(current, BrowserSource):
            current.release()  # stops its wait for a picture, so the swap happens right away

    def restore(self, saved: dict):
        """Settings kept from last time (see SETTINGS_FILE)."""
        self.collect, self.learn = (
            bool(saved.get("collect")),
            bool(saved.get("learn", True)),
        )
        self.mode = saved["mode"] if saved.get("mode") in ("auto", "slots") else "auto"
        self.slots = clean_slots(saved.get("slots") or []) or []
        self.rotate = view.clean_rotation(saved.get("rotate", 0)) or 0
        self.crop = view.clean_box(saved["crop"]) if saved.get("crop") else None
        self.straight = view.clean_straighten(saved.get("straight")) if saved.get("straight") else None
        self.auto_straight = bool(saved.get("auto_straight", config.AUTO_STRAIGHTEN))
        self.min_card = clean_min_card(saved.get("min_card"))

    def set_min_card_from_bed(self) -> float:
        """Look only for whole cards: the smallest card becomes MIN_CARD_FROM_BED of the
        biggest card seen now (the one on the bed). Raises ValueError with no card in
        view. Call with the lock held."""
        w, h = self.frame_size or (0, 0)
        tracks = [t for t in self.tracks if t.missing == 0] or list(self.tracks)
        if not tracks or not w or not h:
            raise ValueError("No card in view: lay one card on the bed, against the stop pins, and try again")
        locked = [t for t in tracks if t.status == "locked"] or tracks
        biggest = max(float(cv2.contourArea(np.asarray(t.corners, np.float32))) for t in locked)
        share = biggest / float(w * h)
        value = clean_min_card(round(share * config.MIN_CARD_FROM_BED, 4))
        if value is None:
            raise ValueError("That card's outline doesn't look right: lay it flat on the bed and try again")
        self.min_card = value
        self.forget_tracks()
        return value

    def set_straight(self, on, corners=None):
        """Straighten the picture from the card on the bed now (True) or stop (False).
        `corners`: the card's 4 corners by hand, [[x, y], ...] as shares of the picture.
        Raises ValueError when there is no picture or no card in it. Call with the lock held."""
        self._pending_straight = None
        if not on:
            self.straight = None
            self._auto_straight.reset()
        else:
            frame = self._last_view
            if frame is None:
                raise ValueError("No camera picture yet")
            setting = view.straighten_from(frame, corners)
            if setting is None:
                raise ValueError("No card found: lay one card square on the bed, against the stop pins, and try again")
            from mtgscanner.auto_straighten import correction
            turn, stretch = correction(setting, setting["size"])
            if corners is None and (turn > config.AUTO_STRAIGHT_MAX_TURN or stretch > config.AUTO_STRAIGHT_MAX_STRETCH):
                # far more than the camera is off: the outline caught something else
                raise ValueError(f"That card's outline doesn't look right (it would turn the picture {turn:.1f}°): "
                                 "lay it square against the pins, or use a white-bordered card, and try again")
            self.straight = setting
        self.forget_tracks()

    def set_view(self, rotate: int | None = None, crop=False):
        """Turn the picture to `rotate` degrees and/or crop it. `crop` is a box drawn on
        the picture as it shows now (so it zooms in further), None for the whole picture,
        False to leave it. Slots stay on the same spots of the table. Call with the lock held."""
        if rotate is not None and rotate != self.rotate:
            turns = (rotate - self.rotate) // 90
            if self.crop:
                self.crop = view.turn_box(self.crop, turns)
            self.slots = [view.turn_box(sl, turns) for sl in self.slots]
            self.rotate = rotate
        if crop is not False:
            old = self.crop
            new = None if crop is None else view.inside(crop, old)
            if new is not None and view.is_whole(new):
                new = None
            full = [view.inside(sl, old) for sl in self.slots]
            self.crop = [round(v, 4) for v in new] if new else None
            self.slots = clean_slots([view.relative(sl, self.crop) for sl in full]) or []
            self.straight = None  # measured on the old picture: straighten again
        if rotate is not None:
            self.straight = None
        if rotate is not None or crop is not False:
            self._auto_straight.reset()
            self._pending_straight = None
        self.forget_tracks()  # outlines and numbers belong to the old picture

    def _find(self, frame):
        """Every card in the picture: the outlines of each, and its slot number (None in Auto mode)."""
        if self.mode != "slots" or not self.slots:
            cards = find_cards(frame, self.min_card)
            return cards, [None] * len(cards)
        found = [
            (find_card_in_slot(frame, slot), n) for n, slot in enumerate(self.slots, 1)
        ]
        return [c for c, _ in found if c], [n for c, n in found if c]

    def stop(self):
        self.stopped = True
        source = self.source
        if hasattr(source, "release"):
            source.release()   # wakes the thread out of its wait for a picture

    def run(self):
        while not self.stopped:
            self.turn()
        if self.on_stop:
            self.on_stop(self)

    def turn(self):
        """One go of the loop: switch cameras if asked, then look at the next picture."""
        with self.lock:
            new, self._next_source = self._next_source, None
            if new is not None:
                self.forget_tracks()
        if new is not None:
            old, self.source = self.source, new
            self.started = False  # "Starting camera…" until the new one's first picture
            if hasattr(old, "release"):
                old.release()
        if self.source is None:
            time.sleep(0.2)
            return
        frame = self.source.read()
        if frame is None:
            if isinstance(self.source, BrowserSource) and self.source.gone():
                with self.lock:
                    if self.started:   # the phone went quiet: pause, and clear the table
                        self.forget_tracks()
                        self.started = False
                if self.source.quiet_for() > self.expire:
                    self.stopped = True
            time.sleep(0.2)
            return
        if self.rotate or self.crop:
            frame = view.apply(frame, self.rotate, self.crop)
        self._last_view = frame
        if self._pending_straight is not None:
            with self.lock:
                if not self.tracks:     # between cards: the new warp can't upset a reading
                    self.straight, self._pending_straight = self._pending_straight, None
                    save_settings(straight=self.straight)
        if self.straight:
            frame = view.straighten(frame, self.straight)
        if self.tap is not None and self.tap.watching:
            # A feed is watching for its card to land (feed_watch.py): hand it every
            # picture straight away and skip finding and recognizing cards until it's done,
            # which can take a few hundred ms a picture and made it see the card late.
            self.tap.put(frame)
            self._publish(frame)
            return
        if self._still(frame) and time.monotonic() - self._last_look < 1 / max(0.5, config.SCAN_IDLE_FPS):
            return      # nothing has changed: no need to look again so soon
        self._last_look = time.monotonic()
        self.process(frame)

    def _still(self, frame) -> bool:
        """True when the picture is the same as the last one looked at and no card on the
        table is waiting for an answer, so the scanner can take it easy (SCAN_IDLE_FPS)."""
        small = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (64, 48), interpolation=cv2.INTER_AREA)
        last, self._last_small = self._last_small, small
        if last is None:
            return False
        if float(np.mean(cv2.absdiff(small, last))) >= config.SCAN_STILL_LEVEL:
            return False
        now = time.monotonic()
        with self.lock:
            return not any(t.needs_check(now) for t in self.tracks)

    def _publish(self, frame):
        """Keep the picture for the pages (and for a full-size stream when one is open)."""
        jpeg = self._encode(frame)
        full = self._encode(frame, full=True) if self.full_viewers > 0 else None
        with self.lock:
            self.started = True
            self.frame_size = (frame.shape[1], frame.shape[0])
            self.jpeg = jpeg
            self.jpeg_full = full

    def process(self, frame):
        """Find every card in one camera picture and update what's known about each."""
        t0 = time.perf_counter()
        cards, numbers = self._find(frame)
        t1 = time.perf_counter()
        now = time.monotonic()
        with self.lock:
            matched, new, gone = pair_up(self.tracks, cards)
            todo = [(t, outlines, t.needs_check(now)) for t, outlines in matched]
        # Recognizing is the slow part, so it happens without holding the lock, and
        # every card that needs a look is recognized at the same time on its own thread.
        jobs = [outlines for _, outlines, check in todo if check] + list(new)
        found = (
            list(
                self._pool.map(
                    lambda o: identify_outlines(self.matcher, frame, o), jobs
                )
            )
            if jobs
            else []
        )
        results = iter(found)
        t2 = time.perf_counter()
        with self.lock:
            self.started = True
            self.frame_size = (frame.shape[1], frame.shape[0])
            for t, outlines, check in todo:
                self._update(t, outlines, next(results) if check else None, frame)
            for outlines in new:
                number = next(
                    (n for c, n in zip(cards, numbers) if c is outlines), None
                )
                t = Track(
                    next(self._ids), number or free_number(self.tracks), outlines[0]
                )
                self.tracks.append(t)
                self._update(t, outlines, next(results), frame)
            for t in gone:
                if not t.missing:
                    t.missing_since = now
                t.missing += 1
                if t.gone(now):  # card taken away
                    self.finish_capture(t)
                    self.tracks.remove(t)
            self._note_speed(t0, t1, t2)
        self._publish(frame)

    # Called with the lock held.
    def _note_speed(self, t0, t1, t2):
        end = time.perf_counter()
        p = self.perf
        p["ms_find"] = _smooth(p["ms_find"], 1000 * (t1 - t0))
        p["ms_identify"] = _smooth(p["ms_identify"], 1000 * (t2 - t1))
        p["ms_frame"] = _smooth(p["ms_frame"], 1000 * (end - t0))
        if self._last_frame_time is not None and end > self._last_frame_time:
            p["fps"] = _smooth(p["fps"], 1 / (end - self._last_frame_time))
        self._last_frame_time = end
        taken = getattr(self.source, "taken_at", 0.0)
        if taken:
            p["frame_age_ms"] = _smooth(
                p["frame_age_ms"], 1000 * max(0.0, time.monotonic() - taken)
            )

    # Called with the lock held.
    def _update(self, t: Track, outlines, result: Match | None, frame):
        t.missing = 0
        if result is None:  # not checked this frame: just follow it
            t.corners = outlines[0]
            return
        card = result.card
        t.corners, t.distance, t.margin = result.corners, result.distance, result.margin
        if (self.auto_straight and card is not None and result.confidence == "sure"
                and result.corners is not None and not t.straight_sampled
                and not isinstance(self.source, BrowserSource)):
            # a sure match: its outline lined up with the stock picture, a good sample.
            # One per card: a card sitting on the bed is seen many times over, and
            # counting every look let one card (and its own skew) set the picture.
            size = (frame.shape[1], frame.shape[0])
            t.straight_sampled = True
            if self._auto_straight.add(result.corners, self.straight, size):
                new = self._auto_straight.proposal(self.straight)
                if new is not None:
                    self._pending_straight = new
        t.candidates, t.checked_at, t.checked_time = (
            result.candidates,
            result.corners.mean(axis=0),
            time.monotonic(),
        )
        key = card.id if card else "unknown"
        if card and self.live:
            self.live.prefetch(card.id)  # today's price, usually ready by the time it's saved
        settled = t.note_check(key, result.confidence or "unknown")
        fixed = t.fix[1] if t.fix and t.fix[0] == key else None
        if not settled:
            return  # a card already decided stays on screen until the new answer is sure
        self._keep_scan(t, frame, result.corners, card, result.distance)
        shown = fixed or card
        if shown is None:
            if t.status != "unknown":
                t.saved = False
                self._light("unknown")
            t.status, t.card, t.confidence = "unknown", None, None
            return
        if t.card is None or t.card.id != shown.id:
            t.saved = False  # a different card than before
        t.card = shown
        if fixed:
            t.status, t.confidence = "locked", None  # you told it; no doubt about it
        elif t.streak_conf == "unsure":
            if t.status != "unsure":
                self._light("unsure")
            t.status, t.confidence = (
                "unsure",
                "unsure",
            )  # a guess, with the alternatives, never auto-saved
        else:
            t.status, t.confidence = "locked", t.streak_conf
        if self.auto and t.status == "locked" and not t.saved:
            self._save(shown, self.foil, t, auto=True)

    def collection(self):
        """The collection file this scanner saves into."""
        with accounts.acting_as(self.account):
            return accounts.collection_csv()

    # Called with the lock held.
    def _save(
        self, card: Card, foil: bool, track: Track | None = None, auto: bool = False
    ):
        bin_no, bin_label = choose_bin(card, foil, self.vault, self.live)
        price = card_price(card, foil, self.vault, self.live)
        scanned_at = add_card(self.collection(), card, foil, bin_label, price, self.owner)
        with accounts.acting_as(self.account):   # their own alerts and wishlist
            special = self._special(card, price[0])
        self._light("valuable" if special else "saved")
        self.session.append(
            card_info(card, foil, self.vault, live=self.live)
            | {
                "time": time.strftime("%H:%M:%S"),
                "scanned_at": scanned_at,
                "track": track.id if track else None,
            }
        )
        if track:
            track.saved = True
            if track.card is None or track.card.id != card.id:
                track.card, track.status, track.confidence = card, "locked", None
            elif track.status == "unsure":
                track.status, track.confidence = (
                    "locked",
                    None,
                )  # you confirmed the guess
            if (
                track.capture
                and track.capture["card_id"] == card.id
                and track.capture["verdict"] != "corrected"
            ):
                track.capture["verdict"] = "auto-saved" if auto else "saved"

    def _light(self, event: str):
        if self.lights is not None:
            self.lights.event(event)

    @staticmethod
    def _special(card: Card, price: float | None) -> bool:
        """Worth the alert price on the Settings page, or on the wishlist."""
        try:
            alerts = wishlist.load_alerts()
            big = alerts.get("big_card")
            if big is not None and price is not None and price >= big:
                return True
            return bool(alerts.get("wishlist")) and name_key(card.name) in wishlist.wanted_names()
        except Exception:
            return False

    # Called with the lock held. Keeps one scan per card put down (and another if the
    # scanner changes its mind while the card is still there).
    def _keep_scan(self, t: Track, frame, corners, card, dist):
        key = card.id if card else "unknown"
        if not self.collect or key == t.capture_key:
            return
        self.finish_capture(t)
        camera = camera_info(self.source)
        t.capture = self.captures.capture(
            frame, corners, card, dist, camera["name"] if camera else "demo"
        )
        t.capture_key = key

    # Called with the lock held.
    def finish_capture(self, t: Track):
        record, t.capture, t.capture_key = t.capture, None, None
        if not record:
            return
        self.captures.finish(record)
        truth = true_card(
            record, include_auto=False
        )  # only what you confirmed yourself
        if self.learn and truth and record["verdict"] != "ignore":
            self.matcher.add_learned(record["crop"], truth, record["_fp"])

    # Called with the lock held.
    def forget_tracks(self):
        for t in self.tracks:
            self.finish_capture(t)
        self.tracks = []

    def track(self, track_id) -> Track | None:
        return next((t for t in self.tracks if t.id == track_id), None)

    def _encode(self, frame, full: bool = False) -> bytes:
        """The camera picture for the page (the page draws the outlines itself): a preview
        of STREAM_PREVIEW_PX on its long side, about a tenth of the full picture's bytes,
        which a phone or a Tailscale link can keep up with. `full` keeps the full size
        (at most 1280 wide) for the server's recognizing."""
        h, w = frame.shape[:2]
        if full:
            limit, side, quality = 1280, w, 80
        else:
            limit, side, quality = config.STREAM_PREVIEW_PX, max(h, w), config.STREAM_PREVIEW_QUALITY
        if side > limit:
            scale = limit / side
            frame = cv2.resize(frame, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
        return cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])[1].tobytes()

    def state(self):
        with self.lock:
            totals = {
                "count": len(self.session),
                "value": round(sum(c["price"] or 0 for c in self.session), 2),
                "bins": {},
            }
            for c in self.session:
                totals["bins"][c["bin"]] = totals["bins"].get(c["bin"], 0) + 1
            visible = sorted(
                (t for t in self.tracks if not t.missing or t.status != "recognizing"),
                key=lambda t: t.number,
            )
            if isinstance(self.source, WaitingForCamera) or self.source is None:
                status = "waiting"
            elif isinstance(self.source, BrowserSource) and self.source.gone():
                status = "paused"   # the phone's page is in the background
            elif not self.started:
                status = "starting"
            elif not visible:
                status = "looking"
            elif any(t.status == "recognizing" for t in visible):
                status = "recognizing"
            elif any(t.status == "locked" for t in visible):
                status = "locked"
            else:
                status = (
                    "unsure"
                    if any(t.status == "unsure" for t in visible)
                    else "unknown"
                )
            w, h = self.frame_size or (1, 1)
            return {
                "status": status,
                "frame": {"w": w, "h": h},
                "cards": [
                    {
                        "track": t.id,
                        "number": t.number,
                        "status": t.status,
                        "saved": t.saved,
                        "verdict": t.capture["verdict"] if t.capture else None,
                        "corners": [
                            [round(float(x) / w, 4), round(float(y) / h, 4)]
                            for x, y in t.corners
                        ],
                        "confidence": t.confidence,
                        "distance": t.distance,
                        "margin": t.margin,
                        "card": card_info(
                            t.card, self.foil, self.vault, None if t.fix else t.distance, self.live
                        )
                        if t.card
                        else None,
                        "candidates": [
                            candidate_info(c, d, self.foil, self.vault, self.live)
                            for c, d in t.candidates
                            if t.status in ("unsure", "unknown")
                            and not (t.card and c.id == t.card.id)
                        ][:3],
                    }
                    for t in visible
                ],
                "foil": self.foil,
                "auto": self.auto,
                "mode": self.mode,
                "slots": self.slots,
                "view": {"rotate": self.rotate, "crop": self.crop, "straight": bool(self.straight),
                         "auto_straight": self.auto_straight,
                         "min_card": self.min_card,
                         "straight_samples": len(self._auto_straight.samples),
                         "straight_refused": self._auto_straight.last_refused},
                "camera": camera_info(self._next_source or self.source),
                "owner": self.owner,
                "account": self.account,
                "collect": self.collect,
                "learn": self.learn,
                "captures": self.captures.counts
                | {"open": sum(1 for t in self.tracks if t.capture)},
                # The newest cards only: the page asks several times a second, and a
                # long session would make every answer big. History has the rest.
                "session": self.session[: -SESSION_SHOWN - 1 : -1],
                "session_count": len(self.session),
                "totals": totals,
                "perf": {
                    k: (None if v is None else round(v, 1))
                    for k, v in self.perf.items()
                },
            }


def clean_slots(raw) -> list[list[float]] | None:
    """Slots as the page sends them, [x0, y0, x1, y1] each as shares of the picture,
    tidied up: clamped, corners in order, too-small ones dropped. None if malformed."""
    try:
        slots = []
        for s in raw:
            x0, y0, x1, y1 = (min(1.0, max(0.0, float(v))) for v in s)
            (x0, x1), (y0, y1) = sorted((x0, x1)), sorted((y0, y1))
            if x1 - x0 >= 0.02 and y1 - y0 >= 0.02:
                slots.append([round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)])
        return slots
    except (TypeError, ValueError):
        return None


def camera_info(source) -> dict | None:
    if not isinstance(source, (CameraSource, BrowserSource, RemoteCameraSource)):
        return None
    if hasattr(source, "info"):
        return source.info()
    return {"index": source.index, "name": source.name}


def card_info(card: Card, foil: bool, vault, distance=None, live=None) -> dict:
    price, source = card_price(card, foil, vault, live)
    bin_no, bin_label = choose_bin(card, foil, vault, live)
    return {
        "id": card.id,
        "name": card.name,
        "set": card.set_code.upper(),
        "set_name": card.set_name,
        "number": card.collector_number,
        "rarity": card.rarity,
        "foil": foil,
        "price": price,
        "price_source": source,
        "bin": bin_no,
        "bin_label": bin_label,
        # Scryfall serves the card's picture straight from its id.
        "image": f"https://api.scryfall.com/cards/{card.id}?format=image&version=normal",
        "match": None if distance is None else ("good" if distance <= 60 else "fair"),
    }


def candidate_info(card: Card, distance: int, foil: bool, vault, live=None) -> dict:
    """A possible other answer for a card the scanner isn't sure about."""
    info = card_info(card, foil, vault, distance, live)
    return {
        k: info[k]
        for k in ("id", "name", "set", "set_name", "number", "image", "price", "bin")
    } | {"distance": distance}


# --- Web server ----------------------------------------------------------------------


def make_lights():
    """The light bars: the Pi's own on the Pi, and on the server (MTG_MACHINE_URL) the Pi's,
    reached over the network."""
    return RemoteLights(remote_url()) if remote_url() else Lights()


def create_app(scanner: Scanner, machine: Machine | None = None, lights: Lights | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    # On the server, MTG_MACHINE_URL points at the sorter's Pi, which does the moving.
    machine = machine or (RemoteMachine(remote_url()) if remote_url() else Machine())
    scanner.lights = lights or scanner.lights or make_lights()
    assets.install(app, WEB)  # versioned script and style links, so caches never mix old and new
    logins.install(app, WEB)  # user accounts, once they're on: logging in, and who may do what
    security.install(app, WEB)  # the optional PIN lock, checked before every page (without accounts)
    add_machine_routes(app, machine, WEB)  # the /machine test page
    watcher = add_feed_watch_routes(app, scanner, machine)  # Feed one card, watching the camera
    add_tuning_routes(app, watcher, machine)               # the tuning run round the bins
    add_sort_run_routes(app, watcher, scanner, machine)    # Start sorting: the machine on its own
    add_lights_routes(app, scanner.lights, WEB)  # the /lights page
    add_system_routes(app, scanner, machine, WEB)  # the /maintenance page
    add_collection_routes(app, scanner, WEB)  # the /collection page
    add_deck_routes(app, scanner, WEB)  # the /decks page
    add_upgrade_routes(app, scanner)  # the deck builder's upgrade path (EDHREC)
    add_bins_routes(app, scanner, WEB)  # the /bins page
    add_history_routes(app, scanner, WEB)  # the /history page
    add_wishlist_routes(app, scanner, WEB)  # the /wishlist page and alerts
    add_play_routes(app, scanner, WEB)  # the /play page (games, life counter) and the trade binder
    add_vault_routes(app, scanner, WEB)  # Commander Vault: /cards, Canadian prices, imports
    add_home_routes(app, scanner, machine, WEB)  # the Home page's summary
    add_sets_routes(app, scanner, WEB)  # the /sets page

    @app.get("/settings")
    def settings_page():
        return send_from_directory(WEB, "settings.html")
    live = scanner.live

    def unknown_card():
        return jsonify({"error": "Unknown card"}), 404

    @app.get("/")
    def home():
        return send_from_directory(WEB, "home.html")

    @app.get("/scan")
    def scan_page():
        return send_from_directory(WEB, "index.html")

    @app.get("/static/<path:name>")
    def static_files(name):
        return send_from_directory(WEB, name)

    # The machine's scanner answers every request, except ones from a page whose device is
    # the camera: those name their own scanner (see browser_camera below) in the X-Scanner
    # header (or ?scanner= for the picture stream), so each phone scans on its own table.
    scanners: dict[str, Scanner] = {}
    app.config["scanners"] = scanners

    # With accounts on, someone without the machine permission never gets the machine's
    # scanner: until their phone scans they get a camera-less one of their own (for the
    # Photos tab), so they only ever see and save their own cards.
    desks: dict[str, Scanner] = {}

    def current() -> Scanner:
        token = request.headers.get("X-Scanner") or request.args.get("scanner") or ""
        sc = scanners.get(token)
        if sc is not None:
            return sc
        if accounts.enabled() and not accounts.can("machine"):
            return desk()
        return scanner

    def desk() -> Scanner:
        me = accounts.current() or ""
        sc = desks.get(me)
        if sc is None:
            sc = Scanner(scanner.matcher, scanner.vault, None, scanner.live)
            sc.captures, sc.account = scanner.captures, me
            desks[me] = sc
        return sc

    def refuse(message):
        abort(make_response(jsonify({"error": message, "forbidden": True}), 403))

    def acting() -> Scanner:
        """The scanner a button is pressed for. With accounts on, the machine's scanner
        needs the machine permission and then saves into the cards of whoever pressed
        it; a phone's scanner only answers to the person it belongs to (and admins)."""
        sc = current()
        if not accounts.enabled():
            return sc
        me = accounts.current()
        if sc is scanner:
            if not accounts.can("machine"):
                refuse("The machine is for people with the machine permission: pick This device's camera")
            sc.account = me
        elif sc.account != me and not accounts.can("admin"):
            refuse("That's someone else's scanner")
        return sc

    @app.get("/stream.mjpg")
    def stream():
        """The live picture: a preview unless ?full=1 (the server's RemoteCameraSource)."""
        sc = current()
        full = request.args.get("full") in ("1", "true", "yes")

        def frames():
            last = None
            if full:
                sc.full_viewers += 1
            try:
                while not sc.stopped:
                    jpeg = sc.jpeg_full if full else sc.jpeg
                    if jpeg is not None and jpeg is not last:
                        last = jpeg
                        yield (
                            b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                        )
                    time.sleep(0.04)
            finally:
                if full:
                    sc.full_viewers = max(0, sc.full_viewers - 1)

        return Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.get("/api/state")
    def state():
        return state_for(current())

    def state_for(sc: Scanner):
        s = sc.state()
        s["db_count"] = scanner.matcher.card_count
        s["learned"] = scanner.matcher.learned_count
        rate = f"US$1 = CA${config.USD_TO_CAD:.4f}"
        s["prices"] = (
            f"Commander Vault prices, {scanner.vault.date}"
            if scanner.vault
            else f"Scryfall {'live ' if live else ''}prices in CAD ({rate})"
        )
        s["live"] = bool(live)
        s["bin_names"] = sort_rules.names()
        s["alerts"] = wishlist.load_alerts()
        wanted = wishlist.wanted_names()
        for c in s["cards"]:
            if c["card"]:
                c["card"]["wanted"] = name_key(c["card"]["name"]) in wanted
        s["session"] = [c | {"wanted": name_key(c["name"]) in wanted} for c in s["session"]]
        s["locked"] = security.enabled()
        if accounts.enabled():   # whose cards this scanner saves into
            whose = accounts.public(sc.account or accounts.owner())
            s["saving_to"] = {"username": whose["username"], "name": whose["name"]}
            s["me"] = accounts.current()
        s["on_pi"] = ON_PI
        s["sorter"] = ON_PI or bool(remote_url())   # a machine to run: the Scan page shows Start sorting
        s["scanners"] = [   # who else is scanning right now
            {"name": other.source.name, "owner": other.owner or (accounts.public(other.account)["name"] if other.account else ""),
             "cards": len(other.session)}
            for other in list(scanners.values()) if other is not sc and not other.stopped
        ]
        return jsonify(s)

    @app.post("/api/settings")
    def settings():
        body = request.get_json(force=True)
        sc = acting()
        remember = sc is scanner   # a phone's choices last as long as its page does
        with sc.lock:
            for key in ("foil", "auto", "collect", "learn"):
                if key in body:
                    setattr(sc, key, bool(body[key]))
            if "collect" in body and not sc.collect:
                for t in sc.tracks:
                    sc.finish_capture(t)
            if ("collect" in body or "learn" in body) and remember:
                save_settings(collect=sc.collect, learn=sc.learn)
            if "slots" in body:
                slots = clean_slots(body["slots"])
                if slots is None:
                    return jsonify(
                        {
                            "error": "Slots must be [x0, y0, x1, y1] each, as shares of the picture"
                        }
                    ), 400
                sc.slots = slots
            if body.get("mode") in ("auto", "slots"):
                sc.mode = body["mode"]
            if "slots" in body or "mode" in body:
                sc.forget_tracks()  # the cards on the table get their numbers afresh
                if remember:
                    save_settings(mode=sc.mode, slots=sc.slots)
            if "rotate" in body or "crop" in body:
                rotate = view.clean_rotation(body["rotate"]) if "rotate" in body else None
                crop = body.get("crop", False)
                if crop not in (None, False):
                    crop = view.clean_box(crop)
                    if crop is None:
                        return jsonify({"error": "Crop must be [x0, y0, x1, y1] as shares of the picture"}), 400
                if "rotate" in body and rotate is None:
                    return jsonify({"error": "Rotate must be 0, 90, 180 or 270"}), 400
                sc.set_view(rotate, crop)
                if remember:
                    save_settings(rotate=sc.rotate, crop=sc.crop, slots=sc.slots, straight=sc.straight)
            if "auto_straight" in body:
                sc.auto_straight = bool(body["auto_straight"])
                if remember:
                    save_settings(auto_straight=sc.auto_straight)
            if "min_card" in body:
                raw = body["min_card"]
                if raw == "bed":
                    try:
                        sc.set_min_card_from_bed()
                    except ValueError as e:
                        return jsonify({"error": str(e)}), 400
                elif raw is None:
                    sc.min_card = None
                    sc.forget_tracks()
                else:
                    value = clean_min_card(raw)
                    if value is None:
                        return jsonify({"error": "min_card must be a share of the picture from 0.005 to 0.9, \"bed\" or null"}), 400
                    sc.min_card = value
                    sc.forget_tracks()
                if remember:
                    save_settings(min_card=sc.min_card)
            if "straighten" in body:
                try:
                    raw = body["straighten"]
                    # true: find the card; a list of 4 [x, y] shares: the card's corners by hand
                    sc.set_straight(bool(raw), raw if isinstance(raw, list) else None)
                except ValueError as e:
                    return jsonify({"error": str(e)}), 400
                if remember:
                    save_settings(straight=sc.straight)
            outline = str(body.get("outline", ""))
            if len(outline) == 7 and outline[0] == "#":
                try:
                    r, g, b = (int(outline[i : i + 2], 16) for i in (1, 3, 5))
                    sc.outline = (b, g, r)
                except ValueError:
                    pass
        return state_for(sc)

    @app.get("/api/cameras")
    def cameras():
        cams = list_cameras()
        if remote_url():   # the server: the sorter Pi's camera, over the network
            cams.append({"index": RemoteCameraSource.index, "name": "Sorter's Pi camera", "remote": remote_url()})
        return jsonify(cams)

    @app.post("/api/camera")
    def camera():
        body = request.get_json(force=True)
        if body.get("index") == BrowserSource.index:
            return browser_camera(body)
        if not accounts.can("machine"):
            refuse("Only people with the machine permission can switch the machine's camera")
        current = camera_info(scanner._next_source or scanner.source)
        if body.get("index") == RemoteCameraSource.index:
            if not remote_url():
                return jsonify({"error": "No sorter Pi is set up here (MTG_MACHINE_URL)."}), 400
            if current and current["index"] == RemoteCameraSource.index:
                return state()
            source = RemoteCameraSource(remote_url())
            scanner.use_source(source)
            save_settings(camera={"index": source.index, "name": source.name})
            return state()
        index, name = int(body["index"]), body.get("name")
        if current and current["index"] == index:
            return state()
        try:
            source = CameraSource(index, name)
        except RuntimeError as e:
            return jsonify({"error": f"{e} Is another app using it?"}), 409
        scanner.use_source(source)
        save_settings(camera={"index": source.index, "name": source.name})
        return state()

    # --- Scanning with the camera of the phone or computer that has the page open ---
    # The page picks "This device's camera" and gets a scanner of its own, fed by the
    # pictures it sends to /api/frame. Every phone scans on its own table at the same
    # time, and the machine's camera carries on untouched. The page names its scanner
    # with the token it made up, in the X-Scanner header of everything it asks for.
    # When the page closes (or goes quiet for ten minutes) its scanner is dropped.

    def browser_camera(body):
        token = str(body.get("token") or "")
        if not token:
            return jsonify({"error": "Missing camera token"}), 400
        who = str(body.get("who") or "").strip()[:40]
        sc = scanners.get(token)
        if sc is not None and not sc.stopped and accounts.enabled() and sc.account != accounts.current():
            refuse("That's someone else's scanner")
        if sc is None or sc.stopped:
            source = BrowserSource(token, str(body.get("name") or "")[:40] or None)
            sc = Scanner(scanner.matcher, scanner.vault, source, scanner.live)
            sc.captures = scanner.captures    # one log of collected scans for everyone
            sc.learn = scanner.learn
            sc.account = accounts.current()   # cards go into the phone's person's collection
            sc.on_stop = lambda gone: scanners.pop(token, None) if scanners.get(token) is gone else None
            scanners[token] = sc
            threading.Thread(target=sc.run, name=f"scanner-{token[:8]}", daemon=True).start()
        if "who" in body:
            sc.owner = who
        return state_for(sc)

    def browser_scanner():
        token = request.headers.get("X-Scanner") or request.headers.get("X-Camera-Token") or ""
        sc = scanners.get(token)
        return sc if sc and not sc.stopped and isinstance(sc.source, BrowserSource) else None

    @app.post("/api/frame")
    def frame():
        """One picture from the device's camera (a JPEG, sent as the request body)."""
        sc = browser_scanner()
        if sc is not None and accounts.enabled() and sc.account != accounts.current():
            sc = None
        if sc is None:
            return jsonify({"error": "This device isn't scanning anymore: pick its camera again"}), 409
        img = cv2.imdecode(np.frombuffer(request.get_data(), np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"error": "Couldn't read the picture"}), 400
        sc.source.push(img)
        return "", 204

    @app.post("/api/camera/focus")
    def camera_focus():
        """Focus for the Pi camera: {"cm": null} keeps refocusing by itself, {"cm": 12}
        locks the lens 12 cm away (the scan bed). Kept for next time."""
        if not accounts.can("machine"):
            refuse("Only people with the machine permission can change the machine's camera")
        cm = (request.get_json(force=True, silent=True) or {}).get("cm")
        if cm is not None:
            try:
                cm = float(cm)
            except (TypeError, ValueError):
                return jsonify({"error": "Focus distance must be a number of cm"}), 400
            if not 3 <= cm <= 1000:
                return jsonify({"error": "Focus distance must be between 3 and 1000 cm"}), 400
        source = scanner._next_source or scanner.source
        if not (hasattr(source, "set_focus") and source.set_focus(cm)):   # webcams, demo photos, phones
            return jsonify({"error": "This camera can't change its focus"}), 409
        cameras_mod.focus_cm = cm
        save_settings(focus_cm=cm)
        return state()

    @app.post("/api/camera/release")
    def release_camera():
        """The device stopped scanning: its scanner goes away (its cards are saved already)."""
        body = request.get_json(force=True, silent=True) or {}
        token = str(body.get("token") or "")
        sc = scanners.get(token)
        if sc is not None and accounts.enabled() and sc.account != accounts.current() and not accounts.can("admin"):
            sc = None
        if sc is not None:
            scanners.pop(token, None)
            with sc.lock:
                sc.forget_tracks()
            sc.stop()
        return "", 204

    @app.post("/api/wrong")
    def wrong():
        """The scanner named the wrong card. Kept in the capture log to improve recognition."""
        body = request.get_json(force=True)
        sc = acting()
        with sc.lock:
            t = sc.track(body.get("track"))
            if t and t.capture:
                t.capture["verdict"] = "wrong"
        return state()

    @app.get("/api/search")
    def search():
        text = request.args.get("q", "").strip()
        cards = scanner.matcher.search(text) if len(text) >= 2 else []
        return jsonify([card_info(c, False, scanner.vault, live=live) for c in cards])

    @app.get("/api/printings")
    def printings():
        """Every printing of a card name, newest first, with prices: Scryfall's list when
        online, plus the ones in the database."""
        name = request.args.get("name", "").strip()
        foil = request.args.get("foil") == "1"
        found = {c.id: c for c in (live.printings(name) if live and name else [])}
        for c in scanner.matcher.printings(name):
            found.setdefault(c.id, c)
        return jsonify([card_info(c, foil, scanner.vault, live=live) for c in found.values()])

    @app.post("/api/correct")
    def correct():
        """You picked the card that's really under the camera: save it, and remember the
        right answer for training."""
        body = request.get_json(force=True)
        card = lookup(scanner, body.get("id"))
        if card is None:
            return unknown_card()
        sc = acting()
        with sc.lock:
            t = sc.track(body.get("track"))
            if t:
                if t.capture:
                    t.capture.update(verdict="corrected", correct_id=card.id)
                t.fix = (t.streak_key or "unknown", card)
                # If the wrong card was already saved for it, take that one back out.
                wrong = (
                    next(
                        (e for e in reversed(sc.session) if e["track"] == t.id),
                        None,
                    )
                    if t.saved
                    else None
                )
                if wrong and remove_entry(
                    sc.collection(), wrong["id"], wrong["scanned_at"]
                ):
                    sc.session.remove(wrong)
                t.status, t.card, t.confidence, t.candidates = "locked", card, None, []
            sc._save(card, bool(body.get("foil")), t)
        return state_for(sc)

    # --- Train tab ---

    def training_info():
        include_auto = request.args.get("auto", "0") == "1"
        rows = scanner.captures.rows()
        if request.args.get("show") != "all":
            rows = [
                r for r in rows if true_card(r) is None and r["verdict"] != "ignore"
            ]
        scans = []
        for r in rows[::-1][:120]:
            truth = true_card(r)
            scans.append(
                r | {"true_name": getattr(scanner.matcher.find_card(truth), "name", "") if truth else ""}
            )
        return jsonify(
            {
                "counts": scanner.captures.counts,
                "learned": scanner.matcher.learned_count,
                "ready": len(
                    ready_to_learn(scanner.matcher, scanner.captures, include_auto)
                ),
                "scans": scans,
            }
        )

    @app.get("/api/training")
    def training():
        return training_info()

    @app.post("/api/label")
    def label():
        """Label a collected scan: {crop, id} for the right card, or {crop, verdict}
        with "saved" (the guess was right) or "ignore" (bad picture)."""
        body = request.get_json(force=True)
        changes = (
            {"verdict": "corrected", "correct_id": body["id"]}
            if body.get("id")
            else {"verdict": body["verdict"], "correct_id": ""}
            if body.get("verdict") in ("saved", "ignore")
            else None
        )
        if changes is None:
            return jsonify({"error": "Send a card id, or verdict saved/ignore"}), 400
        with scanner.lock:
            if not scanner.captures.update(body["crop"], **changes):
                return jsonify({"error": "That scan isn't in the log"}), 404
        return training_info()

    @app.post("/api/train")
    def train_now():
        include_auto = bool(request.get_json(force=True).get("include_auto", False))
        with scanner.lock:
            for t in scanner.tracks:  # include the cards on the table right now
                scanner.finish_capture(t)
            result = train(scanner.matcher, scanner.captures, include_auto)
        return jsonify(result)

    @app.post("/api/forget")
    def forget():
        return jsonify({"removed": forget_all(scanner.matcher)})

    @app.get("/captures/<path:name>")
    def capture_file(name):
        return send_from_directory(config.CAPTURES_DIR, name)

    @app.post("/api/add")
    def add():
        body = request.get_json(force=True)
        card = lookup(scanner, body.get("id"))
        if card is None:
            return unknown_card()
        sc = acting()
        with sc.lock:
            sc._save(card, bool(body.get("foil")), sc.track(body.get("track")))
        return state_for(sc)

    @app.post("/api/save_all")
    def save_all():
        """Save every recognized card on the table that isn't saved yet (not the unsure ones)."""
        foil = bool(request.get_json(force=True).get("foil"))
        sc = acting()
        with sc.lock:
            for t in sorted(sc.tracks, key=lambda t: t.number):
                if t.status == "locked" and not t.saved:
                    sc._save(t.card, foil, t)
        return state_for(sc)

    @app.post("/api/undo")
    def undo():
        sc = acting()
        with sc.lock:
            last = sc.session[-1] if sc.session else None
            # The exact card saved last (an import may have added rows after it since).
            path = sc.collection()
            if last and (remove_entry(path, last["id"], last.get("scanned_at", ""))
                         or (not last.get("scanned_at") and remove_last(path))):
                undone = sc.session.pop()
                t = sc.track(undone["track"])
                if t and t.card and t.card.id == undone["id"]:
                    t.saved = False
                    if t.capture and t.capture["verdict"] in ("saved", "auto-saved"):
                        t.capture["verdict"] = ""
        return state_for(sc)

    @app.post("/api/photos")
    def photos():
        results = []
        for f in request.files.getlist("photos"):
            frame = cv2.imdecode(np.frombuffer(f.read(), np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                results.append({"file": f.filename, "error": "Couldn't open this file"})
                continue
            # A photo can show a whole table of cards: report each one.
            found = [
                identify_outlines(scanner.matcher, frame, outlines)
                for outlines in find_cards(frame)
            ]
            cards = [m for m in found if m.card]
            if not found:
                results.append(
                    {"file": f.filename, "error": "No card found in the photo"}
                )
            elif not cards:
                results.append(
                    {
                        "file": f.filename,
                        "error": "Card not recognized"
                        if len(found) == 1
                        else f"None of the {len(found)} cards recognized",
                    }
                )
            for m in cards:
                results.append(
                    {
                        "file": f.filename,
                        "card": card_info(m.card, False, scanner.vault, m.distance, live)
                        | {"confidence": m.confidence},
                    }
                )
        return jsonify(results)

    @app.get("/api/collection.csv")
    def download():
        path = accounts.collection_csv()
        if not path.exists():
            return Response("No cards saved yet.", status=404)
        return send_file(
            path, as_attachment=True, download_name="collection.csv"
        )

    return app


def clean_min_card(value) -> float | None:
    """A smallest-card share of the picture (0.005 to 0.9), or None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return round(value, 4) if 0.005 <= value <= 0.9 else None


def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_settings(**changes):
    try:
        config.DATA_DIR.mkdir(exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(load_settings() | changes))
    except OSError:
        pass


def startup_camera(index: int | None) -> CameraSource:
    """--camera if given; otherwise the camera picked last time on the page (found by
    name, since numbers can change when cameras are plugged in); otherwise the first."""
    cams = list_cameras()
    names = {c["index"]: c["name"] for c in cams}
    if index is None:
        index = cams[0]["index"] if cams else 0
        try:
            last = load_settings()["camera"]
            index = next(c["index"] for c in cams if c["name"] == last["name"])
        except (KeyError, TypeError, StopIteration):
            pass
    cameras_mod.focus_cm = saved_focus()  # the Pi camera opens with the focus picked last time
    try:
        return CameraSource(index, names.get(index))
    except RuntimeError as e:
        raise RuntimeError(f"{e} Try --camera 1, or --demo <folder> to test without one.")


def saved_focus() -> float | None:
    """The Pi camera focus picked on the page: None for auto, else a distance in cm."""
    cm = load_settings().get("focus_cm")
    return float(cm) if isinstance(cm, (int, float)) and 3 <= cm <= 1000 else None


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--camera",
        type=int,
        help="webcam number, -1 for the Pi camera (default: the one picked last time, else the Pi camera or webcam 0)",
    )
    parser.add_argument("--demo", help="folder of photos to use instead of a webcam")
    parser.add_argument(
        "--host", default="127.0.0.1", help="0.0.0.0 to open it from other devices"
    )
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="don't look up today's prices or other printings on Scryfall",
    )
    args = parser.parse_args()

    matcher = Matcher(connect(config.DB_PATH))
    vault = VaultPrices.load(config.VAULT_PRICES)
    rate, rate_date = load_rate()
    print(
        f"US dollar = {rate:.4f} CAD"
        + (f" (Bank of Canada, {rate_date})" if rate_date else " (offline default)")
    )
    if args.demo:
        source = DemoSource(args.demo)
    else:
        try:
            source = startup_camera(args.camera)
        except RuntimeError as e:
            if remote_url():   # the server: no camera of its own, so watch the sorter Pi's
                source = RemoteCameraSource(remote_url())
                print(f"Camera: the sorter's Pi camera, over the network from {remote_url()}")
            else:
                print(f"{e} Starting anyway; trying again every few seconds.")
                source = WaitingForCamera(args.camera)
    if isinstance(source, CameraSource):
        print(
            f"Camera: {source.name}, {source.size[0]}x{source.size[1]} {source.format}"
            + (
                ""
                if source.format in ("MJPG", "PICM")
                else " (not MJPG: expect a low frame rate)"
            )
        )
    scanner = Scanner(matcher, vault, source, None if args.offline else Live())
    if isinstance(source, WaitingForCamera):
        source.on_found = scanner.use_source
    scanner.restore(load_settings())
    scanner.lights = make_lights()
    scanner.lights.start()  # shows the saved color (nothing happens without light bars)
    threading.Thread(target=scanner.run, daemon=True).start()

    print(
        f"Loaded {matcher.card_count} cards ({matcher.learned_count} learned scans). Open http://localhost:{args.port} in your browser."
    )
    if not matcher.card_count:
        print(
            "The card database is empty, so nothing can be recognized yet: restore a backup on the "
            "Maintenance page, or press Download every card there (see README.md)."
        )
    machine = RemoteMachine(remote_url()) if remote_url() else Machine()
    app = create_app(scanner, machine)
    if isinstance(machine, Machine) and ON_PI:
        # The servos to their saved home positions (Machine page: Home), in the background
        # so the page is up straight away.
        threading.Thread(target=home_at_startup, args=(machine,), daemon=True).start()
    # The weekly Canadian price check and card database update (see mtgscanner/vault.py).
    threading.Thread(target=app.config["weekly"].loop, daemon=True).start()
    try:
        app.run(host=args.host, port=args.port, threaded=True)
    finally:
        with scanner.lock:
            scanner.forget_tracks()  # log the cards still on the table


if __name__ == "__main__":
    main()
