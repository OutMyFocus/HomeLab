"""Recognize the card in a camera frame or photo. Used by both scan.py and app.py."""

import cv2
import numpy as np

from . import config
from .database import Card, Matcher
from .vision import find_card_candidates, fingerprint, grow, warp_card

GOOD_ENOUGH = 40   # a match this close is certain: stop trying other outlines


def identify_frame(matcher: Matcher, frame):
    """Find and recognize the card in a camera frame or photo.

    Returns (corners, card, distance). corners is None if nothing card-shaped was
    found. card is None if a shape was found but didn't match any known card.
    Every outline the detector proposes is tried, and the best database match wins.
    """
    best = (None, None, 10**9)
    for outlines in find_cards(frame):
        found = identify_outlines(matcher, frame, outlines)
        if found[2] < best[2]:
            best = found
    return best


def find_cards(frame) -> list[list[np.ndarray]]:
    """Every card in the picture, as a list of outlines per card.

    The detector often outlines the same card more than once (each of its methods
    finds it a little differently), so outlines whose centers sit inside each other
    are grouped as one card. The biggest outline of each card comes first.
    """
    candidates = sorted(find_card_candidates(frame, config.MIN_CARD_AREA), key=cv2.contourArea, reverse=True)
    cards: list[list[np.ndarray]] = []
    for c in candidates:
        center = tuple(map(float, c.mean(axis=0)))
        for group in cards:
            if cv2.pointPolygonTest(group[0], center, False) >= 0:
                group.append(c)
                break
        else:
            cards.append([c])
    return cards


def identify_outlines(matcher: Matcher, frame, outlines: list[np.ndarray]) -> tuple[np.ndarray, Card | None, int]:
    """Recognize one card from its outlines. Returns (best corners, card or None, distance)."""
    best = (outlines[0], None, 10**9, None)
    for found in outlines:
        for factor in (1.0, 1.04, 1.08):
            corners = grow(found, factor)
            card_id, dist = _match(matcher, warp_card(frame, corners))
            if dist < best[2]:
                best = (corners, None, dist, card_id)
            if best[2] <= GOOD_ENOUGH:
                break
        if best[2] <= GOOD_ENOUGH:
            break
    corners, _, dist, card_id = best
    if dist > config.MAX_MATCH_DISTANCE:
        return corners, None, dist
    return corners, matcher.get_card(card_id), dist


def identify(matcher: Matcher, card_img) -> tuple[Card | None, int]:
    """Return (best matching card, distance). Card is None if nothing is close enough."""
    best_id, best_dist = _match(matcher, card_img)
    if best_dist > config.MAX_MATCH_DISTANCE:
        return None, best_dist
    return matcher.get_card(best_id), best_dist


def _match(matcher: Matcher, card_img) -> tuple[str, int]:
    # The card might be upside down, so try both ways and keep the better match.
    best_id, best_dist = None, 10**9
    for img in (card_img, cv2.rotate(card_img, cv2.ROTATE_180)):
        card_id, dist = matcher.best_match(fingerprint(img))
        if dist < best_dist:
            best_id, best_dist = card_id, dist
    return best_id, best_dist
