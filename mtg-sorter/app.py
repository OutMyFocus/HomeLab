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
from flask import Flask, Response, jsonify, request, send_file, send_from_directory
from mtgscanner import config
from mtgscanner.camera import CameraSource, list_cameras  # noqa: F401  (tests patch these here)
from mtgscanner.captures import CaptureLog, true_card
from mtgscanner.collection import add_card, remove_entry, remove_last
from mtgscanner.database import Card, Matcher, connect
from mtgscanner.exchange import load_rate
from mtgscanner.recognize import Match, find_card_in_slot, find_cards, identify_outlines
from mtgscanner.sorting import card_price, choose_bin
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


def _smooth(old: float | None, new: float, weight: float = 0.2) -> float:
    """A running average that follows changes gently (for the speed readout)."""
    return new if old is None else old + weight * (new - old)


class Scanner:
    """Looks at every card in the camera picture, all the time, in a background thread."""

    def __init__(self, matcher: Matcher, vault: VaultPrices | None, source):
        self.matcher, self.vault, self.source = matcher, vault, source
        self.lock = threading.Lock()
        self.jpeg = None  # latest camera picture for the page
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
        self.perf = {
            "fps": None,
            "ms_frame": None,
            "ms_find": None,
            "ms_identify": None,
            "frame_age_ms": None,
        }
        self._last_frame_time = None
        workers = config.IDENTIFY_THREADS or min(8, os.cpu_count() or 2)
        self._pool = ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="identify"
        )

    def use_source(self, source):
        """Switch cameras. The background thread makes the swap between frames."""
        with self.lock:
            pending, self._next_source = self._next_source, source
        if pending is not None:  # switched twice before the first one took over
            pending.release()

    def restore(self, saved: dict):
        """Settings kept from last time (see SETTINGS_FILE)."""
        self.collect, self.learn = (
            bool(saved.get("collect")),
            bool(saved.get("learn", True)),
        )
        self.mode = saved["mode"] if saved.get("mode") in ("auto", "slots") else "auto"
        self.slots = clean_slots(saved.get("slots") or []) or []

    def _find(self, frame):
        """Every card in the picture: the outlines of each, and its slot number (None in Auto mode)."""
        if self.mode != "slots" or not self.slots:
            cards = find_cards(frame)
            return cards, [None] * len(cards)
        found = [
            (find_card_in_slot(frame, slot), n) for n, slot in enumerate(self.slots, 1)
        ]
        return [c for c, _ in found if c], [n for c, n in found if c]

    def run(self):
        while True:
            with self.lock:
                new, self._next_source = self._next_source, None
                if new is not None:
                    self.forget_tracks()
            if new is not None:
                old, self.source = self.source, new
                if hasattr(old, "release"):
                    old.release()
            frame = self.source.read()
            if frame is None:
                time.sleep(0.2)
                continue
            self.process(frame)

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
            self.jpeg = self._encode(frame)
            self._note_speed(t0, t1, t2)

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
        t.candidates, t.checked_at, t.checked_time = (
            result.candidates,
            result.corners.mean(axis=0),
            time.monotonic(),
        )
        key = card.id if card else "unknown"
        settled = t.note_check(key, result.confidence or "unknown")
        fixed = t.fix[1] if t.fix and t.fix[0] == key else None
        if not settled:
            return  # a card already decided stays on screen until the new answer is sure
        self._keep_scan(t, frame, result.corners, card, result.distance)
        shown = fixed or card
        if shown is None:
            if t.status != "unknown":
                t.saved = False
            t.status, t.card, t.confidence = "unknown", None, None
            return
        if t.card is None or t.card.id != shown.id:
            t.saved = False  # a different card than before
        t.card = shown
        if fixed:
            t.status, t.confidence = "locked", None  # you told it; no doubt about it
        elif t.streak_conf == "unsure":
            t.status, t.confidence = (
                "unsure",
                "unsure",
            )  # a guess, with the alternatives, never auto-saved
        else:
            t.status, t.confidence = "locked", t.streak_conf
        if self.auto and t.status == "locked" and not t.saved:
            self._save(shown, self.foil, t, auto=True)

    # Called with the lock held.
    def _save(
        self, card: Card, foil: bool, track: Track | None = None, auto: bool = False
    ):
        bin_no, bin_label = choose_bin(card, foil, self.vault)
        price = card_price(card, foil, self.vault)
        scanned_at = add_card(config.COLLECTION_CSV, card, foil, bin_label, price)
        self.session.append(
            card_info(card, foil, self.vault)
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

    def _encode(self, frame) -> bytes:
        """The camera picture for the page (the page draws the outlines itself)."""
        h, w = frame.shape[:2]
        if w > 1280:
            frame = cv2.resize(
                frame, (1280, int(h * 1280 / w)), interpolation=cv2.INTER_AREA
            )
        return cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()

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
            if not self.started:
                status = (
                    "waiting" if isinstance(self.source, WaitingForCamera) else "starting"
                )
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
                            t.card, self.foil, self.vault, None if t.fix else t.distance
                        )
                        if t.card
                        else None,
                        "candidates": [
                            candidate_info(c, d, self.foil, self.vault)
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
                "camera": camera_info(self._next_source or self.source),
                "collect": self.collect,
                "learn": self.learn,
                "captures": self.captures.counts
                | {"open": sum(1 for t in self.tracks if t.capture)},
                "session": self.session[::-1],
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
    if not isinstance(source, CameraSource):
        return None
    if hasattr(source, "info"):
        return source.info()
    return {"index": source.index, "name": source.name}


def card_info(card: Card, foil: bool, vault, distance=None) -> dict:
    price, source = card_price(card, foil, vault)
    bin_no, bin_label = choose_bin(card, foil, vault)
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


def candidate_info(card: Card, distance: int, foil: bool, vault) -> dict:
    """A possible other answer for a card the scanner isn't sure about."""
    info = card_info(card, foil, vault, distance)
    return {
        k: info[k]
        for k in ("id", "name", "set", "set_name", "number", "image", "price", "bin")
    } | {"distance": distance}


# --- Web server ----------------------------------------------------------------------


def create_app(scanner: Scanner) -> Flask:
    app = Flask(__name__, static_folder=None)

    @app.get("/")
    def index():
        return send_from_directory(WEB, "index.html")

    @app.get("/static/<path:name>")
    def static_files(name):
        return send_from_directory(WEB, name)

    @app.get("/stream.mjpg")
    def stream():
        def frames():
            last = None
            while True:
                jpeg = scanner.jpeg
                if jpeg is not None and jpeg is not last:
                    last = jpeg
                    yield (
                        b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                    )
                time.sleep(0.04)

        return Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.get("/api/state")
    def state():
        s = scanner.state()
        s["db_count"] = scanner.matcher.card_count
        s["learned"] = scanner.matcher.learned_count
        rate = f"US$1 = CA${config.USD_TO_CAD:.4f}"
        s["prices"] = (
            f"Commander Vault prices, {scanner.vault.date}"
            if scanner.vault
            else f"Scryfall prices in CAD ({rate})"
        )
        return jsonify(s)

    @app.post("/api/settings")
    def settings():
        body = request.get_json(force=True)
        with scanner.lock:
            for key in ("foil", "auto", "collect", "learn"):
                if key in body:
                    setattr(scanner, key, bool(body[key]))
            if "collect" in body and not scanner.collect:
                for t in scanner.tracks:
                    scanner.finish_capture(t)
            if "collect" in body or "learn" in body:
                save_settings(collect=scanner.collect, learn=scanner.learn)
            if "slots" in body:
                slots = clean_slots(body["slots"])
                if slots is None:
                    return jsonify(
                        {
                            "error": "Slots must be [x0, y0, x1, y1] each, as shares of the picture"
                        }
                    ), 400
                scanner.slots = slots
            if body.get("mode") in ("auto", "slots"):
                scanner.mode = body["mode"]
            if "slots" in body or "mode" in body:
                scanner.forget_tracks()  # the cards on the table get their numbers afresh
                save_settings(mode=scanner.mode, slots=scanner.slots)
            outline = str(body.get("outline", ""))
            if len(outline) == 7 and outline[0] == "#":
                try:
                    r, g, b = (int(outline[i : i + 2], 16) for i in (1, 3, 5))
                    scanner.outline = (b, g, r)
                except ValueError:
                    pass
        return state()

    @app.get("/api/cameras")
    def cameras():
        return jsonify(list_cameras())

    @app.post("/api/camera")
    def camera():
        body = request.get_json(force=True)
        index, name = int(body["index"]), body.get("name")
        current = camera_info(scanner._next_source or scanner.source)
        if current and current["index"] == index:
            return state()
        try:
            source = CameraSource(index, name)
        except RuntimeError as e:
            return jsonify({"error": f"{e} Is another app using it?"}), 409
        scanner.use_source(source)
        save_settings(camera={"index": source.index, "name": source.name})
        return state()

    @app.post("/api/wrong")
    def wrong():
        """The scanner named the wrong card. Kept in the capture log to improve recognition."""
        body = request.get_json(force=True)
        with scanner.lock:
            t = scanner.track(body.get("track"))
            if t and t.capture:
                t.capture["verdict"] = "wrong"
        return state()

    @app.get("/api/search")
    def search():
        text = request.args.get("q", "").strip()
        cards = scanner.matcher.search(text) if len(text) >= 2 else []
        return jsonify([card_info(c, False, scanner.vault) for c in cards])

    @app.post("/api/correct")
    def correct():
        """You picked the card that's really under the camera: save it, and remember the
        right answer for training."""
        body = request.get_json(force=True)
        card = scanner.matcher.get_card(body["id"])
        with scanner.lock:
            t = scanner.track(body.get("track"))
            if t:
                if t.capture:
                    t.capture.update(verdict="corrected", correct_id=card.id)
                t.fix = (t.streak_key or "unknown", card)
                # If the wrong card was already saved for it, take that one back out.
                wrong = (
                    next(
                        (e for e in reversed(scanner.session) if e["track"] == t.id),
                        None,
                    )
                    if t.saved
                    else None
                )
                if wrong and remove_entry(
                    config.COLLECTION_CSV, wrong["id"], wrong["scanned_at"]
                ):
                    scanner.session.remove(wrong)
                t.status, t.card, t.confidence, t.candidates = "locked", card, None, []
            scanner._save(card, bool(body.get("foil")), t)
        return state()

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
                r | {"true_name": scanner.matcher.get_card(truth).name if truth else ""}
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
        card = scanner.matcher.get_card(body["id"])
        with scanner.lock:
            scanner._save(
                card, bool(body.get("foil")), scanner.track(body.get("track"))
            )
        return state()

    @app.post("/api/save_all")
    def save_all():
        """Save every recognized card on the table that isn't saved yet (not the unsure ones)."""
        foil = bool(request.get_json(force=True).get("foil"))
        with scanner.lock:
            for t in sorted(scanner.tracks, key=lambda t: t.number):
                if t.status == "locked" and not t.saved:
                    scanner._save(t.card, foil, t)
        return state()

    @app.post("/api/undo")
    def undo():
        with scanner.lock:
            if scanner.session and remove_last(config.COLLECTION_CSV):
                undone = scanner.session.pop()
                t = scanner.track(undone["track"])
                if t and t.card and t.card.id == undone["id"]:
                    t.saved = False
                    if t.capture and t.capture["verdict"] in ("saved", "auto-saved"):
                        t.capture["verdict"] = ""
        return state()

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
                        "card": card_info(m.card, False, scanner.vault, m.distance)
                        | {"confidence": m.confidence},
                    }
                )
        return jsonify(results)

    @app.get("/api/collection.csv")
    def download():
        if not config.COLLECTION_CSV.exists():
            return Response("No cards saved yet.", status=404)
        return send_file(
            config.COLLECTION_CSV, as_attachment=True, download_name="collection.csv"
        )

    return app


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
    try:
        return CameraSource(index, names.get(index))
    except RuntimeError as e:
        raise RuntimeError(f"{e} Try --camera 1, or --demo <folder> to test without one.")


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
    scanner = Scanner(matcher, vault, source)
    if isinstance(source, WaitingForCamera):
        source.on_found = scanner.use_source
    scanner.restore(load_settings())
    threading.Thread(target=scanner.run, daemon=True).start()

    print(
        f"Loaded {matcher.card_count} cards ({matcher.learned_count} learned scans). Open http://localhost:{args.port} in your browser."
    )
    try:
        create_app(scanner).run(host=args.host, port=args.port, threaded=True)
    finally:
        with scanner.lock:
            scanner.forget_tracks()  # log the cards still on the table


if __name__ == "__main__":
    main()
