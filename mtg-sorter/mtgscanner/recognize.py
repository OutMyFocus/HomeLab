"""Recognize the card in a camera frame or photo. Used by both scan.py and app.py."""

from dataclasses import dataclass, field

import cv2
import numpy as np

from . import config
from .database import Card, Hit, Matcher
from .vision import find_card_candidates, fingerprint, grow, warp_card

GOOD_ENOUGH = 40   # a match this close is certain: stop trying other outlines

# How sure the scanner is, from least to most.
CONFIDENCE_RANK = {"unknown": 0, "unsure": 1, "likely": 2, "sure": 3}


@dataclass
class Match:
    """What one card on the table was recognized as."""
    corners: np.ndarray                 # the outline that matched best
    card: Card | None                   # None: nothing in the database is close enough
    distance: int                       # fingerprint distance of the best match (lower is closer)
    margin: int = 0                     # lead over the closest card with a different name
    confidence: str | None = None       # "sure", "likely" or "unsure" (None when card is None)
    candidates: list[tuple[Card, int]] = field(default_factory=list)   # other possible cards, closest first


def confidence_of(distance: int, margin: int) -> str | None:
    """How much to trust a match. None means it isn't a match at all."""
    if distance > config.MAX_MATCH_DISTANCE:
        return None
    if distance <= config.SURE_DISTANCE and margin >= config.SURE_MARGIN:
        return "sure"
    if margin >= config.LIKELY_MARGIN:
        return "likely"
    return "unsure"


def identify_frame(matcher: Matcher, frame):
    """Find and recognize the card in a camera frame or photo.

    Returns (corners, card, distance). corners is None if nothing card-shaped was
    found. card is None if a shape was found but didn't match any known card.
    Every outline the detector proposes is tried, and the best database match wins.
    """
    best = (None, None, 10**9)
    for outlines in find_cards(frame):
        m = identify_outlines(matcher, frame, outlines)
        if m.distance < best[2]:
            best = (m.corners, m.card, m.distance)
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


def _size(outline: np.ndarray) -> float:
    return float(np.linalg.norm(outline[0] - outline[2]))


def _distinct(outlines: list[np.ndarray], limit: int = 4) -> list[np.ndarray]:
    """The outlines worth trying: not nearly the same as one already kept (the masks
    often agree), and not a small shape inside the card (a text box or the art)."""
    kept: list[np.ndarray] = []
    biggest = _size(outlines[0]) or 1.0
    for o in outlines:
        size = _size(o) or 1.0
        if size < 0.7 * biggest:
            continue
        if all(np.abs(o - k).max() > 0.015 * size for k in kept):
            kept.append(o)
        if len(kept) >= limit:
            break
    return kept or [outlines[0]]


def identify_outlines(matcher: Matcher, frame, outlines: list[np.ndarray]) -> Match:
    """Recognize one card from its outlines."""
    best: tuple[np.ndarray, Hit | None] = (outlines[0], None)
    for found in _distinct(outlines):
        for factor in config.OUTLINE_FACTORS:
            corners = grow(found, factor)
            hit = _rank(matcher, warp_card(frame, corners))
            if best[1] is None or hit.distance < best[1].distance:
                best = (corners, hit)
            if hit.distance <= GOOD_ENOUGH:
                break
        if best[1].distance <= GOOD_ENOUGH:
            break
    corners, hit = best
    if hit.distance > config.MAX_MATCH_DISTANCE:
        corners = outlines[0]       # nothing matched, so the "best" outline means little: keep the card's main one
    return _match(matcher, corners, hit)


def _match(matcher: Matcher, corners, hit: Hit) -> Match:
    conf = confidence_of(hit.distance, hit.margin)
    candidates = [(matcher.get_card(i), d) for i, d in hit.candidates if d <= config.CANDIDATE_DISTANCE]
    if conf is None:
        # Not close enough to call it, but the best guess may still help you pick: offer it first.
        if hit.distance <= config.CANDIDATE_DISTANCE:
            candidates.insert(0, (matcher.get_card(hit.id), hit.distance))
        return Match(corners, None, hit.distance, hit.margin, None, candidates)
    return Match(corners, matcher.get_card(hit.id), hit.distance, hit.margin, conf, candidates)


def identify_crop(matcher: Matcher, card_img) -> Match:
    """Recognize an already straightened card picture (a collected scan, say), with
    the same confidence and candidates as a live card gets."""
    return _match(matcher, None, _rank(matcher, card_img))


def identify(matcher: Matcher, card_img) -> tuple[Card | None, int]:
    """Return (best matching card, distance). Card is None if nothing is close enough."""
    hit = _rank(matcher, card_img)
    if hit.distance > config.MAX_MATCH_DISTANCE:
        return None, hit.distance
    return matcher.get_card(hit.id), hit.distance


def _rank(matcher: Matcher, card_img) -> Hit:
    # The card might be upside down, so try both ways and keep the better match.
    best: Hit | None = None
    for img in (card_img, cv2.rotate(card_img, cv2.ROTATE_180)):
        hit = matcher.rank(fingerprint(img))
        if best is None or hit.distance < best.distance:
            best = hit
    return best
