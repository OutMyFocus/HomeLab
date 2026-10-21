"""Recognize the card in a camera frame or photo. Used by both scan.py and app.py."""

import cv2

from . import config
from .database import Card, Matcher
from .vision import find_card_candidates, fingerprint, grow, warp_card


def identify_frame(matcher: Matcher, frame):
    """Find and recognize the card in a camera frame or photo.

    Returns (corners, card, distance). corners is None if nothing card-shaped was
    found. card is None if a shape was found but didn't match any known card.
    Every outline the detector proposes is tried, and the best database match wins.
    """
    best = (None, None, 10**9)
    for found in find_card_candidates(frame):
        for factor in (1.0, 1.04, 1.08):
            corners = grow(found, factor)
            card, dist = identify(matcher, warp_card(frame, corners))
            if dist < best[2]:
                best = (corners, card, dist)
    return best


def identify(matcher: Matcher, card_img) -> tuple[Card | None, int]:
    """Return (best matching card, distance). Card is None if nothing is close enough."""
    # The card might be upside down, so try both ways and keep the better match.
    best_id, best_dist = None, 10**9
    for img in (card_img, cv2.rotate(card_img, cv2.ROTATE_180)):
        card_id, dist = matcher.best_match(fingerprint(img))
        if dist < best_dist:
            best_id, best_dist = card_id, dist
    if best_dist > config.MAX_MATCH_DISTANCE:
        return None, best_dist
    return matcher.get_card(best_id), best_dist
