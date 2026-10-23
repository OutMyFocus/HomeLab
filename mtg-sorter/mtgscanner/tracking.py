"""Follow each card on the table from one camera frame to the next.

The camera sees a whole table of cards at once. Each card gets a Track: a number
shown on the picture, what it was recognized as, and whether it was saved. Cards
are matched between frames by position, so a card keeps its number and its
"saved" mark while it stays where it is.

Recognizing a card takes a few milliseconds, so a card that's already recognized
is only checked again every couple of seconds, or when it moves.
"""

import time
from dataclasses import dataclass, field

import numpy as np

from . import config
from .database import Card

GONE_AFTER = 8       # frames a card can be missing (a hand over it) before it's forgotten...

# How many checks in a row must agree before the answer is shown, by how sure the
# recognizer is of it. A clear match needs fewer looks than a doubtful one.
CHECKS_NEEDED = {"sure": 1, "likely": 2, "unsure": 3, "unknown": 3}
RANK = {"unknown": 0, "unsure": 1, "likely": 2, "sure": 3}


@dataclass
class Track:
    id: int
    number: int                     # shown on the picture and in the list
    corners: np.ndarray
    card: Card | None = None        # the card shown for it, once recognized
    status: str = "recognizing"     # "recognizing", "locked", "unsure" or "unknown"
    distance: int | None = None
    margin: int | None = None
    confidence: str | None = None   # "sure", "likely" or "unsure" for the card shown
    candidates: list = field(default_factory=list)   # [(Card, distance)] other possible cards
    streak_key: str | None = None   # what the last checks found (card id or "unknown")...
    streak: int = 0                 # ...and how many checks in a row
    streak_conf: str = "unknown"    # the best confidence seen during the streak
    missing: int = 0                # frames in a row it wasn't seen
    missing_since: float = 0.0      # and since when (time.monotonic)
    checked_at: np.ndarray | None = None   # where it was when last recognized
    checked_time: float = 0.0       # and when
    saved: bool = False
    capture: dict | None = None     # its collected scan (see captures.py)
    capture_key: str | None = None
    fix: tuple | None = None        # (what it guessed, the Card you said it really is)

    @property
    def center(self) -> np.ndarray:
        return self.corners.mean(axis=0)

    @property
    def size(self) -> float:
        return float(np.linalg.norm(self.corners[0] - self.corners[2]))

    def needs_check(self, now: float | None = None) -> bool:
        if self.status == "recognizing" or self.checked_at is None:
            return True
        now = time.monotonic() if now is None else now
        if now - self.checked_time >= config.RECHECK_SECONDS:
            return True
        expected = self.fix[0] if self.fix else (self.card.id if self.card else "unknown")
        if self.streak_key != expected:     # the last check disagreed: settle it quickly
            return True
        return float(np.linalg.norm(self.center - self.checked_at)) > 0.08 * self.size

    def gone(self, now: float | None = None) -> bool:
        """True once the card has been out of sight long enough to count as taken away:
        GONE_AFTER frames and config.GONE_SECONDS, so neither a hand passing over the
        table nor one dropped frame makes a card lose its number and its saved mark."""
        now = time.monotonic() if now is None else now
        return self.missing > GONE_AFTER and now - self.missing_since >= config.GONE_SECONDS

    def note_check(self, key: str, confidence: str) -> bool:
        """Record one recognition result. Returns True once the answer is settled enough to show."""
        if key == self.streak_key:
            self.streak += 1
            if RANK[confidence] > RANK[self.streak_conf]:
                self.streak_conf = confidence
        else:
            self.streak_key, self.streak, self.streak_conf = key, 1, confidence
        return self.streak >= CHECKS_NEEDED[self.streak_conf]


def pair_up(tracks: list[Track], cards: list[list[np.ndarray]]):
    """Match this frame's cards (outlines per card) to the tracks, closest first.

    Returns (list of (track, outlines), outlines of new cards, tracks not seen).
    """
    options = []
    for t in tracks:
        for j, outlines in enumerate(cards):
            d = float(np.linalg.norm(outlines[0].mean(axis=0) - t.center))
            if d < 0.4 * t.size:
                options.append((d, t.id, j, t))
    options.sort(key=lambda o: o[:3])
    used_tracks, used_cards, matched = set(), set(), []
    for _, tid, j, t in options:
        if tid in used_tracks or j in used_cards:
            continue
        used_tracks.add(tid)
        used_cards.add(j)
        matched.append((t, cards[j]))
    new = [outlines for j, outlines in enumerate(cards) if j not in used_cards]
    gone = [t for t in tracks if t.id not in used_tracks]
    return matched, new, gone


def free_number(tracks: list[Track]) -> int:
    taken = {t.number for t in tracks}
    return next(n for n in range(1, len(taken) + 2) if n not in taken)
