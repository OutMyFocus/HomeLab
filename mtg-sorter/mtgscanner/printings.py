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
        picture = cv2.imread(str(path)) if path.exists() else None
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
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            self._saved += 1
            if self._saved % 200 == 1:      # now and then: don't let the folder grow for ever
                files = sorted(self.folder.glob("*.jpg"), key=lambda f: f.stat().st_mtime)
                for old in files[:max(0, len(files) - KEEP_ON_DISK)]:
                    old.unlink(missing_ok=True)
        except OSError:
            pass    # a full or read-only disk: the picture still serves from memory


def pick_printing(card_bgr: np.ndarray, lookalikes: list[tuple[str, int]],
                  pictures: StockPictures, wait: float = FETCH_SECONDS) -> tuple[str, float] | None:
    """The look-alike the scan is most like, where the look-alikes differ.

    card_bgr is the straightened, upright card from the camera; lookalikes are
    (card id, fingerprint distance), the fingerprint's own choice first. Returns
    (card id, its lead over the runner-up), or None when there is nothing to go on
    (pictures missing or not here within `wait` seconds, or the look-alikes' pictures
    are the same)."""
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
    scan = prepare(card_bgr).astype(np.float32)
    # The scan's pixels for every small shift, each with its average taken off: the same
    # for every look-alike, so made once.
    shifted = []
    for dy in range(-SHIFT, SHIFT + 1, SHIFT_STEP):
        for dx in range(-SHIFT, SHIFT + 1, SHIFT_STEP):
            a = scan[ys + dy, xs + dx]
            a = a - a.mean()
            shifted.append(a / (float(np.linalg.norm(a)) + 1e-6))
    shifted = np.stack(shifted)
    scores = []
    for k, card_id in enumerate(ids):
        b = stack[k][ys, xs]
        b = b - b.mean()
        likeness = float((shifted @ (b / (float(np.linalg.norm(b)) + 1e-6))).max())
        scores.append(likeness - BIT_COST * bits[card_id])
    order = np.argsort(scores)[::-1]
    return ids[int(order[0])], float(scores[order[0]] - scores[order[1]])
