"""Which printing is it? Telling a card from its look-alike printings.

The fingerprint (vision.py) knows a card by its overall look. Printings of the same card
that share their art and frame (a card and its reprint in another set) look the same to
it: they sit within a few bits of each other, and camera noise decides between them.
On test photos the scanner named the right card but the wrong printing about one time
in five for such cards, and a printing is what a price belongs to.

What does differ between those printings is small: the set symbol, the line of small
print at the bottom, sometimes the tone of the frame. So when the fingerprint can't
choose, the scan is laid over the stock pictures of the look-alikes, and compared only
where those pictures differ from each other.

The stock pictures come from Scryfall's picture server the first time a card with
look-alikes is seen, and are kept in data/stock. With no internet (or --offline) the
fingerprint's choice stands, as before.
"""

import os
import threading
import time
from collections import OrderedDict
from concurrent import futures
from pathlib import Path

import cv2
import numpy as np
import requests

from . import config
from .vision import CARD_H, CARD_W

PICTURES = "https://cards.scryfall.io/normal/front/{a}/{b}/{id}.jpg"

WINDOW = 15            # printings this many bits from the closest one are its look-alikes
MOST = 8               # look-alikes compared at most (the closest ones)
BLUR = 1.5             # both pictures are softened this much (pixels), like a phone's picture
DIFFER_SHARE = 10      # the percent of the card where the look-alikes differ most is compared...
DIFFER_LEAST = 8.0     # ...as long as they differ at least this much there (0-255 grey)
DIFFER_PIXELS = 200    # fewer differing pixels than this: the pictures are the same, nothing to compare
SHIFT, SHIFT_STEP = 6, 2    # the scan may be this many pixels off the stock picture, each way
# How much the fingerprint still counts: each bit further away costs a look-alike this
# much of its likeness (0-1). Measured on 511 test photos of cards with look-alikes:
# 0.015 picked the right printing in 93% (the fingerprint alone: 80%) and overruled a
# right choice in about 2%; lower overrules more, higher fixes less.
BIT_COST = 0.015
# Scans you taught (Keep learning, the Train tab) come from your own camera, so they show
# a printing the way your camera sees it. They count as a second picture of their
# printing, but only pull its likeness this share of the way toward theirs: a badly lined
# up scan or one with glare must not outweigh the stock pictures.
TAUGHT_PULL = 0.5
TAUGHT_MOST = 3        # taught scans used per printing (the newest)

FETCH_SECONDS = 3.0    # how long one stock picture may take
LIVE_WAIT = 0.5        # how long the live camera waits for stock pictures it hasn't got yet
FAIL_SECONDS = 300     # how long before a picture that couldn't be fetched is tried again
KEEP_IN_MEMORY = 64    # prepared stock pictures (about 330 KB each)
KEEP_ON_DISK = 6000    # stock pictures kept in data/stock (about 60 KB each); the oldest go first


def prepare(picture_bgr: np.ndarray) -> np.ndarray:
    """A card picture as it is compared: card-sized, grey, softened."""
    interp = cv2.INTER_AREA if picture_bgr.shape[0] > CARD_H else cv2.INTER_LINEAR
    grey = cv2.cvtColor(cv2.resize(picture_bgr, (CARD_W, CARD_H), interpolation=interp), cv2.COLOR_BGR2GRAY)
    return cv2.GaussianBlur(grey, (0, 0), BLUR)


class StockPictures:
    """The stock picture of any printing, fetched once and kept."""

    def __init__(self, folder: Path, fetch=None):
        self.folder = Path(folder)
        self._fetch = fetch or self._download
        self._lock = threading.Lock()
        self._ready: OrderedDict[str, np.ndarray] = OrderedDict()
        self._failed: dict[str, float] = {}
        self._coming: dict[str, futures.Future] = {}      # pictures being fetched right now
        self._pool = futures.ThreadPoolExecutor(max_workers=MOST, thread_name_prefix="stock")
        self._saved = 0

    @staticmethod
    def _download(card_id: str) -> bytes | None:
        url = PICTURES.format(a=card_id[0], b=card_id[1], id=card_id)
        resp = requests.get(url, headers={"User-Agent": config.USER_AGENT}, timeout=FETCH_SECONDS)
        return resp.content if resp.status_code == 200 else None

    def get(self, card_id: str) -> np.ndarray | None:
        """The prepared stock picture of one printing (None: couldn't get it)."""
        with self._lock:
            if card_id in self._ready:
                self._ready.move_to_end(card_id)
                return self._ready[card_id]
            if time.monotonic() - self._failed.get(card_id, -1e9) < FAIL_SECONDS:
                return None
        path = self.folder / f"{card_id}.jpg"
        picture = _read_whole(path)
        if picture is None:
            try:
                data = self._fetch(card_id)
                picture = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR) if data else None
            except Exception:
                picture = None      # no internet, a timeout: the fingerprint's choice stands
            if picture is None:
                with self._lock:
                    self._failed[card_id] = time.monotonic()
                return None
            self._keep(path, data)
        ready = prepare(picture)
        with self._lock:
            self._ready[card_id] = ready
            while len(self._ready) > KEEP_IN_MEMORY:
                self._ready.popitem(last=False)
        return ready

    def taught(self, path: Path) -> np.ndarray | None:
        """A scan you taught, prepared like a stock picture (None: it can't be read)."""
        key = f"taught:{path}"
        with self._lock:
            if key in self._ready:
                self._ready.move_to_end(key)
                return self._ready[key]
        picture = cv2.imread(str(path)) if Path(path).is_file() else None
        if picture is None:
            return None
        ready = prepare(picture)
        with self._lock:
            self._ready[key] = ready
            while len(self._ready) > KEEP_IN_MEMORY:
                self._ready.popitem(last=False)
        return ready

    def get_all(self, card_ids: list[str], wait: float = FETCH_SECONDS) -> dict[str, np.ndarray]:
        """Several printings at once (fetched side by side), without the ones that failed
        or that didn't arrive within `wait` seconds. Those keep coming in the background
        and are there the next time the card is looked at."""
        with self._lock:
            have = {i: self._ready[i] for i in card_ids if i in self._ready}
            for i in have:
                self._ready.move_to_end(i)
            jobs = {}
            for i in card_ids:
                if i not in have:
                    if i not in self._coming:
                        self._coming[i] = self._pool.submit(self._fetch_one, i)
                    jobs[i] = self._coming[i]
        if jobs:
            futures.wait(jobs.values(), timeout=wait)
            for i, job in jobs.items():
                if job.done() and job.result() is not None:
                    have[i] = job.result()
        return have

    def _fetch_one(self, card_id: str) -> np.ndarray | None:
        try:
            return self.get(card_id)
        finally:
            with self._lock:
                self._coming.pop(card_id, None)

    def _keep(self, path: Path, data: bytes):
        # Written under another name, then renamed: a power cut or a full disk can't leave
        # half a picture under the real name (it would be used for ever, grey below the cut).
        tmp = path.with_suffix(".jpg.tmp")
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(data)
            os.replace(tmp, path)
            self._saved += 1
            if self._saved % 200 == 1:      # now and then: don't let the folder grow for ever
                files = sorted(self.folder.glob("*.jpg"), key=lambda f: f.stat().st_mtime)
                for old in files[:max(0, len(files) - KEEP_ON_DISK)]:
                    old.unlink(missing_ok=True)
        except OSError:
            # A full or read-only disk: the picture still serves from memory.
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass


def _read_whole(path: Path) -> np.ndarray | None:
    """A kept stock picture, or None when there's none or it was cut short (it is then
    removed, so it's fetched again)."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    picture = None
    # A whole JPEG ends with its end marker (FF D9), give or take some padding.
    if data.rstrip(b"\0 \r\n").endswith(b"\xff\xd9"):
        picture = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if picture is None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    return picture


def pick_printing(card_bgr: np.ndarray, lookalikes: list[tuple[str, int]],
                  pictures: StockPictures, wait: float = FETCH_SECONDS,
                  taught: dict[str, list[np.ndarray]] | None = None) -> tuple[str, float] | None:
    """The look-alike the scan is most like, where the look-alikes differ.

    card_bgr is the straightened, upright card from the camera; lookalikes are
    (card id, fingerprint distance), the fingerprint's own choice first. taught holds
    scans you taught for some of them (prepared, see StockPictures.taught), which weigh
    in next to their stock picture (TAUGHT_PULL). Returns (card id, its lead over the
    runner-up), or None when there is nothing to go on (pictures missing or not here
    within `wait` seconds, or the look-alikes' pictures are the same)."""
    stock = pictures.get_all([card_id for card_id, _ in lookalikes], wait)
    if lookalikes[0][0] not in stock or len(stock) < 2:
        return None
    ids = [card_id for card_id, _ in lookalikes if card_id in stock]
    bits = {card_id: distance for card_id, distance in lookalikes}
    stack = np.stack([stock[i] for i in ids]).astype(np.float32)
    spread = stack.std(axis=0)
    level = max(DIFFER_LEAST, float(np.percentile(spread, 100 - DIFFER_SHARE)))
    differ = cv2.dilate((spread >= level).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    edge = SHIFT + 2
    differ[:edge] = differ[-edge:] = False
    differ[:, :edge] = differ[:, -edge:] = False
    if int(differ.sum()) < DIFFER_PIXELS:
        return None
    ys, xs = np.nonzero(differ)
    scan = align(prepare(card_bgr), stock[ids[0]]).astype(np.float32)
    # The scan's pixels for every small shift, each with its average taken off: the same
    # for every look-alike, so made once.
    shifted = []
    for dy in range(-SHIFT, SHIFT + 1, SHIFT_STEP):
        for dx in range(-SHIFT, SHIFT + 1, SHIFT_STEP):
            a = scan[ys + dy, xs + dx]
            a = a - a.mean()
            shifted.append(a / (float(np.linalg.norm(a)) + 1e-6))
    shifted = np.stack(shifted)

    def like(picture: np.ndarray) -> float:
        b = picture[ys, xs].astype(np.float32)
        b = b - b.mean()
        return float((shifted @ (b / (float(np.linalg.norm(b)) + 1e-6))).max())

    scores = []
    for k, card_id in enumerate(ids):
        likeness = like(stack[k])
        own = [like(_upright(t, stack[k])) for t in (taught or {}).get(card_id, [])]
        if own and max(own) > likeness:
            likeness += TAUGHT_PULL * (max(own) - likeness)
        scores.append(likeness - BIT_COST * bits[card_id])
    order = np.argsort(scores)[::-1]
    return ids[int(order[0])], float(scores[order[0]] - scores[order[1]])


# The outline the camera found is often a few pixels off the card's real edge, more than
# SHIFT makes up for where it's also a touch too big or turned, and the details that tell
# look-alike printings apart (the set symbol, the small print) are only a few pixels
# across. So the scan is first laid exactly over the stock picture (OpenCV's ECC image
# alignment, at half size). Only the look-alikes' shared look is used for that, so it
# favours none of them.
ALIGN_SCALE = 0.5
ALIGN_STEPS = 40
ALIGN_MOST_MOVE = 0.06     # an alignment that moves the card more than this share of it is ignored


def align(scan: np.ndarray, stock: np.ndarray) -> np.ndarray:
    """The prepared scan moved (shifted, turned, scaled, tilted a little) to lie exactly
    over a prepared stock picture of the same size. The scan as it was when that fails."""
    try:
        small = [cv2.resize(p, None, fx=ALIGN_SCALE, fy=ALIGN_SCALE, interpolation=cv2.INTER_AREA).astype(np.float32)
                 for p in (scan, stock)]
        warp = np.eye(3, dtype=np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, ALIGN_STEPS, 1e-4)
        _, warp = cv2.findTransformECC(small[1], small[0], warp, cv2.MOTION_HOMOGRAPHY, criteria, None, 3)
    except cv2.error:
        return scan
    up = np.diag([1 / ALIGN_SCALE, 1 / ALIGN_SCALE, 1]).astype(np.float32)
    warp = up @ warp @ np.linalg.inv(up)
    h, w = scan.shape[:2]
    box = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float32).reshape(-1, 1, 2)
    moved = cv2.perspectiveTransform(box, warp).reshape(-1, 2)
    if np.abs(moved - box.reshape(-1, 2)).max() > ALIGN_MOST_MOVE * h:
        return scan
    return cv2.warpPerspective(scan, warp, (w, h), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
                               borderMode=cv2.BORDER_REPLICATE)


def _upright(scan: np.ndarray, stock: np.ndarray) -> np.ndarray:
    """A taught scan turned the way up its stock picture is (it may have been kept
    upside down)."""
    turned = cv2.rotate(scan, cv2.ROTATE_180)
    small = [cv2.resize(p, (61, 85), interpolation=cv2.INTER_AREA).astype(np.float32).ravel()
             for p in (scan, turned, stock)]
    a, b, ref = (v - v.mean() for v in small)
    return turned if float(b @ ref) > float(a @ ref) else scan
