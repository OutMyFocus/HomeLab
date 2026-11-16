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

import cv2
import numpy as np

from . import config
from .database import Card

GONE_AFTER = 8       # frames a card can be missing (a hand over it) before it's forgotten...

# A card that was read keeps its outline while the camera only finds a piece of it (its
# art box, the half beside a thumb): the box on the picture used to jump onto the piece
# and the card to lose its name (Nic, 2026-11-16: "it keeps looking at small sections").
PIECE_SIZE = 0.85        # an outline under this share of the card's size, inside it, is a piece of it
PIECE_RECHECK = 0.5      # seconds between looks at a card only a piece of which shows


def _size(outline: np.ndarray) -> float:
    return float(np.linalg.norm(outline[0] - outline[2]))


def is_piece(outline: np.ndarray, corners: np.ndarray) -> bool:
    """Whether the outline is a part of the card at corners: clearly smaller, and inside it."""
    outline, corners = np.asarray(outline, np.float32), np.asarray(corners, np.float32)
    if _size(outline) >= PIECE_SIZE * _size(corners):
        return False
    center = corners.mean(axis=0)
    roomy = (corners - center) * 1.08 + center      # a piece's corner may sit right on the edge
    return all(cv2.pointPolygonTest(roomy, (float(x), float(y)), False) >= 0 for x, y in outline)


def _carry(corners: np.ndarray, before: np.ndarray, after: np.ndarray) -> np.ndarray | None:
    """Move corners the way an outline moved from one picture (before) to the next (after).
    None when the two outlines aren't the same thing a moment later."""
    size = _size(before)
    if size <= 0 or not 0.87 < _size(after) / size < 1.15:
        return None
    if float(np.linalg.norm(after.mean(axis=0) - before.mean(axis=0))) > 0.25 * size:
        return None
    # The same corner can get another place in the list (a card lying near 45 degrees).
    after = min((np.roll(after, k, axis=0) for k in range(4)), key=lambda a: float(np.abs(a - before).sum()))
    if float(np.abs(after - before).max()) > 0.2 * size:
        return None
    m = cv2.getPerspectiveTransform(before.astype(np.float32), after.astype(np.float32))
    moved = cv2.perspectiveTransform(corners.reshape(1, 4, 2).astype(np.float32), m)[0]
    area, was = cv2.contourArea(moved), cv2.contourArea(corners.astype(np.float32))
    if not np.isfinite(moved).all() or not cv2.isContourConvex(moved) or not 0.75 * was < area < 1.33 * was:
        return None
    return moved


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
    straight_sampled: bool = False  # already gave auto-straighten its one sample
    seen: np.ndarray | None = None  # the outline the camera found when corners was last set
    piece: bool = False             # only a piece of the card shows right now

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
        if self.piece and now - self.checked_time >= PIECE_RECHECK:
            return True     # is the card still there, or is this piece a new card's?
        expected = self.fix[0] if self.fix else (self.card.id if self.card else "unknown")
        if self.streak_key != expected:     # the last check disagreed: settle it quickly
            return True
        return float(np.linalg.norm(self.center - self.checked_at)) > 0.08 * self.size

    def follow(self, outline: np.ndarray):
        """Take this picture's outline for a card that isn't being looked at again right now.

        Normally the card is simply where its outline is. When the outline moved a little
        since the last look, the card's corners move the same way, so the outline that
        matched best stays put on it. When only a piece of a card that was read shows,
        the card keeps its corners (pieces come and go, they say little about where it is)."""
        outline = np.asarray(outline, np.float32)
        if self.seen is not None and not self.piece:
            moved = _carry(self.corners, self.seen, outline)
            if moved is not None:
                self.corners, self.seen = moved, outline
                return
        if self.card is not None and is_piece(outline, self.corners):
            self.piece = True
            return
        self.corners = self.seen = outline
        self.piece = False

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
            # Near where the card was, or a piece of a card that was read (a piece at one
            # end of the card sits further from its middle than a moved card would).
            if d < 0.4 * t.size or (t.card is not None and is_piece(outlines[0], t.corners)):
                options.append((d, t.id, j, t))
    options.sort(key=lambda o: o[:3])
    used_tracks, used_cards, matched = set(), set(), []
    for _, tid, j, t in options:
        if tid in used_tracks or j in used_cards:
            continue
        used_tracks.add(tid)
        used_cards.add(j)
        matched.append((t, cards[j]))
    # A piece of a card that's already known (two of them can show at once) is no new card.
    known = [t for t in tracks if t.card is not None and t.id in used_tracks]
    new = [outlines for j, outlines in enumerate(cards) if j not in used_cards
           and not any(is_piece(outlines[0], t.corners) for t in known)]
    gone = [t for t in tracks if t.id not in used_tracks]
    return matched, new, gone


def free_number(tracks: list[Track]) -> int:
    taken = {t.number for t in tracks}
    return next(n for n in range(1, len(taken) + 2) if n not in taken)
