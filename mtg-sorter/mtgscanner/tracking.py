"""Follow each card on the table from one camera frame to the next.

The camera sees a whole table of cards at once. Each card gets a Track: a number
shown on the picture, what it was recognized as, and whether it was saved. Cards
are matched between frames by position, so a card keeps its number and its
"saved" mark while it stays where it is.

Recognizing a card takes a few milliseconds, so a card that's already recognized
is only checked again every few frames, or when it moves.
"""

from dataclasses import dataclass

import numpy as np

from .database import Card

RECHECK_EVERY = 10   # frames between checks of a card that's already recognized
GONE_AFTER = 8       # frames a card can be missing (a hand over it) before it's forgotten


@dataclass
class Track:
    id: int
    number: int                     # shown on the picture and in the list
    corners: np.ndarray
    card: Card | None = None        # the card shown for it, once recognized
    status: str = "recognizing"     # "recognizing", "locked" or "unknown"
    distance: int | None = None
    streak_key: str | None = None   # what the last checks found (card id or "unknown")...
    streak: int = 0                 # ...and how many checks in a row
    missing: int = 0                # frames in a row it wasn't seen
    since_check: int = 0            # frames since it was last recognized
    checked_at: np.ndarray | None = None   # where it was then
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

    def needs_check(self) -> bool:
        if self.status != "locked" or self.since_check >= RECHECK_EVERY or self.checked_at is None:
            return True
        expected = self.fix[0] if self.fix else self.card.id
        if self.streak_key != expected:     # the last check disagreed: settle it quickly
            return True
        return float(np.linalg.norm(self.center - self.checked_at)) > 0.08 * self.size


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
