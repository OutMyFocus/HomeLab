"""Teach the scanner from your own scans.

The card database starts with one fingerprint per card, made from Scryfall's clean
image. Your camera sees the card differently (lighting, glare, focus, the sleeve).
Training adds the fingerprints of scans you confirmed, by saving them or by picking
the right card, so the next time that card, or another copy, is under your camera
it matches much more closely.
"""

import time

import cv2

from .captures import CaptureLog, true_card
from .database import Matcher
from .vision import fingerprint


def ready_to_learn(matcher: Matcher, captures: CaptureLog, include_auto: bool) -> list[dict]:
    with matcher._lock:
        learned = {r[0] for r in matcher.conn.execute("SELECT scan FROM learned")}
    return [r for r in captures.rows() if r["verdict"] != "ignore" and true_card(r, include_auto) and r["crop"] not in learned]


def train(matcher: Matcher, captures: CaptureLog, include_auto: bool = True) -> dict:
    """Add every confirmed scan not learned yet, and forget scans you've since marked
    wrong or skipped. Returns how many were added and removed."""
    rows = captures.rows()
    new = []
    for row in ready_to_learn(matcher, captures, include_auto):
        img = cv2.imread(str(captures.folder / row["crop"]))
        if img is not None:
            new.append((row["crop"], true_card(row, include_auto), fingerprint(img), time.strftime("%Y-%m-%d %H:%M:%S")))
    unlearn = [(r["crop"],) for r in rows if true_card(r, include_auto) is None or r["verdict"] == "ignore"]
    with matcher._lock:
        before = matcher.conn.total_changes
        matcher.conn.executemany("INSERT OR REPLACE INTO learned VALUES (?, ?, ?, ?)", new)
        added = matcher.conn.total_changes - before
        before = matcher.conn.total_changes
        matcher.conn.executemany("DELETE FROM learned WHERE scan = ?", unlearn)
        removed = matcher.conn.total_changes - before
        # A scan relabeled to a different card: keep its fingerprint pointing at the right one.
        for r in rows:
            if (card := true_card(r, include_auto)) and r["verdict"] != "ignore":
                matcher.conn.execute("UPDATE learned SET card_id = ? WHERE scan = ? AND card_id != ?", (card, r["crop"], card))
        matcher.conn.commit()
    matcher.reload()
    return {"added": added, "removed": removed, "learned": matcher.learned_count}


def forget_all(matcher: Matcher) -> int:
    """Undo all training: back to the plain card database."""
    with matcher._lock:
        n = matcher.conn.execute("DELETE FROM learned").rowcount
        matcher.conn.commit()
    matcher.reload()
    return n
