"""Recognize the card in a camera frame or photo. Used by both scan.py and app.py."""

from dataclasses import dataclass, field

import cv2
import numpy as np

from . import config, printings
from .database import Card, Hit, Matcher
from .vision import (SIDES_GOOD_FIT, boost_contrast, fill_outlines, find_scored_candidates, fingerprint, grow,
                     tame_glare, warp_card)

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
    lookalikes: tuple[str, ...] = ()    # ids of the printings the fingerprint can't tell apart (this card among them)
    printing_lead: float = 0.0          # how clearly their details chose this one (0: the fingerprint chose)


def confidence_of(distance: int, margin: int) -> str | None:
    """How much to trust a match. None means it isn't a match at all."""
    if distance > config.MAX_MATCH_DISTANCE:
        return None
    if distance <= config.SURE_DISTANCE and margin >= config.SURE_MARGIN:
        return "sure"
    if distance <= config.LIKELY_DISTANCE and margin >= config.LIKELY_MARGIN:
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
        for _, m in identify_card(matcher, frame, outlines):
            if m.distance < best[2]:
                best = (m.corners, m.card, m.distance)
    return best


class Outlines(list):
    """The outlines of one card (find_cards), best first. When its main outline may really
    be two or more cards lying close together, parts holds each of those cards' outlines."""
    parts: list[list[np.ndarray]] = []


def find_cards(frame, min_area: float | None = None, rebuild: bool = True) -> list[Outlines]:
    """Every card in the picture, as a list of outlines per card.

    The detector often outlines the same card more than once (each of its methods
    finds it a little differently), so outlines whose centers sit inside each other
    are grouped as one card. The biggest clean outline of each card comes first. min_area
    is the smallest card to look for, as a share of the picture (config.MIN_CARD_AREA).

    A card whose outline is broken (a thumb over one edge, a card sticking out of the
    picture) is put back together from the sides that show, unless rebuild is off.

    Cards a few mm apart can come out as one card-shaped outline around them all (two
    cards side by side are nearly card-shaped). Such a group also carries the outlines
    of the cards inside it (Outlines.parts); the shape alone can't tell them from a split
    or Room card, so identify_card reads the whole first and the parts only if that fails.
    With rebuild off (the machine's bed, one card at a time) there are no parts.
    """
    scored = find_scored_candidates(frame, config.MIN_CARD_AREA if min_area is None else min_area, rebuild)
    cards = []
    for group in _group(scored):
        outlines = Outlines(c for _, c in group)
        if rebuild:
            outlines.parts = _parts(group)
        cards.append(outlines)
    return cards


def _group(scored: list[tuple[float, np.ndarray]]) -> list[list[tuple[float, np.ndarray]]]:
    """Outlines whose centers sit inside each other, grouped, each group best first."""
    scored = sorted(scored, key=lambda s: cv2.contourArea(s[1]), reverse=True)
    groups: list[list[tuple[float, np.ndarray]]] = []
    for fit, c in scored:
        center = tuple(map(float, c.mean(axis=0)))
        for group in groups:
            if cv2.pointPolygonTest(group[0][1], center, False) >= 0:
                group.append((fit, c))
                break
        else:
            groups.append([(fit, c)])
    # Clean outlines first (biggest first), then the guesses by how well they fit: a
    # shape stretched over a thumb is bigger than the card under it, and must not stand
    # for the card (nor push the real outline out of the ones that get tried).
    def guesses_last(scored_outline) -> float:
        fit = scored_outline[0]
        return 0.0 if fit >= SIDES_GOOD_FIT else 1.0 - fit

    return [sorted(group, key=guesses_last) for group in groups]


# An outline is likely several cards when cards inside it, each at least PART_LEAST of
# it and hardly overlapping each other (PART_OVERLAP of the smaller), cover PART_COVER of it.
PART_LEAST = 0.2           # two cards side by side are half each, four in a square a quarter
PART_COVER = 0.85
PART_OVERLAP = 0.1


def _area(outline: np.ndarray) -> float:
    return abs(float(cv2.contourArea(np.asarray(outline, np.float32))))


def _shared(a: np.ndarray, b: np.ndarray) -> float:
    """The area two (convex) outlines have in common."""
    return float(cv2.intersectConvexConvex(np.asarray(a, np.float32), np.asarray(b, np.float32))[0])


def _parts(group: list[tuple[float, np.ndarray]]) -> list[list[np.ndarray]]:
    """The cards inside a group's main outline, when it looks like several cards lying
    close together (each as a list of outlines, best first), else []."""
    main = group[0][1]
    whole = _area(main) or 1.0
    inside = [(fit, c) for fit, c in group[1:] if _area(c) < 0.9 * whole]
    big = sorted((c for _, c in inside if _shared(main, c) >= PART_LEAST * whole), key=_area, reverse=True)
    for i, first in enumerate(big):
        chosen = [first]
        for c in big[i + 1:]:
            if all(_shared(c, k) <= PART_OVERLAP * min(_area(c), _area(k)) for k in chosen):
                chosen.append(c)
        if len(chosen) >= 2 and sum(_shared(main, k) for k in chosen) >= PART_COVER * whole:
            break
    else:
        return []
    # Each card inside, with the other outlines of it (the masks often agree).
    parts = []
    for group in _group(inside):
        center = tuple(map(float, group[0][1].mean(axis=0)))
        if any(cv2.pointPolygonTest(k, center, False) >= 0 for k in chosen):
            parts.append([c for _, c in group])
    return parts if len(parts) >= 2 else []


def identify_card(matcher: Matcher, frame, outlines: list[np.ndarray],
                  **kw) -> list[tuple[list[np.ndarray], Match]]:
    """Recognize one card from find_cards, as [(outlines, match)]: one card, or, when its
    main outline doesn't read and the cards inside it (Outlines.parts) do, each of those.
    kw is passed on to identify_outlines."""
    match = identify_outlines(matcher, frame, outlines, **kw)
    parts = getattr(outlines, "parts", None)
    if not parts:
        return [(outlines, match)]
    if match.card is not None and _area(match.corners) >= 0.9 * _area(outlines[0]):
        return [(outlines, match)]      # it reads as one card (a split or Room card, say)
    # Nothing read, or only one of the cards inside did: each of them on its own.
    found = [(part, identify_outlines(matcher, frame, part, **kw)) for part in parts]
    if any(m.card is not None for _, m in found):
        return found
    return [(outlines, match)]


def identify_filled(matcher: Matcher, frame, **kw) -> Match | None:
    """The card that fills the whole picture (held close to the camera, its edges at or
    past the picture's), if it reads surely; None otherwise. Only worth a try when no
    card was found or read the usual way: see vision.fill_outlines. kw goes to
    identify_outlines."""
    match = identify_outlines(matcher, frame, fill_outlines(frame.shape), **kw)
    if match.card is None or match.confidence != "sure":
        return None
    return match


def find_card_in_slot(frame, slot: list[float]) -> list[np.ndarray] | None:
    """The card in one slot of the picture (the app's Slots mode).

    slot is [x0, y0, x1, y1] as shares of the frame's width and height. The detector
    looks just inside the slot (plus a little around it) and the card's outlines come
    back as from find_cards. If it can't outline the card (a card in a box, a glossy
    sleeve) but something is clearly there, the slot itself is the outline. None means
    the slot is empty.
    """
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = slot[0] * w, slot[1] * h, slot[2] * w, slot[3] * h
    mx, my = (x1 - x0) * config.SLOT_MARGIN, (y1 - y0) * config.SLOT_MARGIN
    ax, ay = max(0, int(x0 - mx)), max(0, int(y0 - my))
    bx, by = min(w, int(x1 + mx) + 1), min(h, int(y1 + my) + 1)
    if bx - ax < 8 or by - ay < 8:
        return None
    rect = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], np.float32)
    for outlines in find_cards(frame[ay:by, ax:bx], config.SLOT_MIN_CARD, rebuild=False):
        moved = [(o + (ax, ay)).astype(np.float32) for o in outlines]
        if cv2.pointPolygonTest(rect, tuple(map(float, moved[0].mean(axis=0))), False) >= 0:
            return moved
    return [rect] if slot_occupied(frame[int(y0):int(y1) + 1, int(x0):int(x1) + 1]) else None


def slot_occupied(crop) -> bool:
    """Whether anything is in a slot: a card is full of edges (border, text, art),
    plain table or cardboard has almost none."""
    if crop.size == 0:
        return False
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    scale = 160 / max(gray.shape)
    if scale < 1:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return cv2.Canny(gray, 50, 150).mean() / 255 >= config.SLOT_OCCUPIED_EDGES


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


# An outline a few percent off the card's real edge (the coloured frame inside a black
# border on a dark table, a shadow along one side) reads as the right card, but only
# just, or not surely enough to count. Each side of the outline is then nudged in and
# out, and kept where the picture comes closest to that card's stock picture; the
# result is then looked up among every card again, so it has to win on its own merits.
REFINE_STEPS = (0.04, 0.02, 0.01)      # how far a side is nudged, as a share of the card's size


def _nudge(corners: np.ndarray, side: int, share: float) -> np.ndarray:
    """The outline with one side pushed outward by a share of the card's size across it
    (inward when negative). Sides: 0 top, 1 right, 2 bottom, 3 left of the corner list."""
    a, b = side, (side + 1) % 4
    across = ((corners[(side + 2) % 4] + corners[(side + 3) % 4]) - (corners[a] + corners[b])) / 2
    moved = corners.copy()
    moved[[a, b]] -= across * share
    return moved


def refine_outline(matcher: Matcher, frame, corners: np.ndarray, card_id: str) -> np.ndarray | None:
    """The outline moved to where it reads closest to one card (None: no closer than it is)."""
    def distance(c) -> int | None:
        return matcher.distance_to(card_id, fingerprint(warp_card(frame, c)))

    start = distance(corners)
    if start is None:
        return None
    turned = np.roll(corners, 2, axis=0)        # the card may be upside down
    other = distance(turned)
    best, at = (other, turned) if other < start else (start, corners)
    first = min(start, other)
    for step in REFINE_STEPS:
        for side in range(4):
            tries = [(distance(c), c) for c in (_nudge(at, side, step), _nudge(at, side, -step))]
            d, c = min(tries, key=lambda t: t[0])
            if d < best:
                best, at = d, c
    return at if best < first else None


def identify_outlines(matcher: Matcher, frame, outlines: list[np.ndarray], refine: bool = True,
                      wait: float = printings.LIVE_WAIT, printing: bool | None = None) -> Match:
    """Recognize one card from its outlines.

    With refine, an outline that reads as a card but not surely is nudged onto the card's
    real edge (see refine_outline). With printing (same as refine unless given), a card
    with look-alike printings is told from them by the details that differ (see
    printings.py; `wait` is how long that may wait for stock pictures it hasn't got yet)."""
    if printing is None:
        printing = refine
    best: tuple[np.ndarray, Hit | None] = (outlines[0], None)
    # The outlines are compared plainly first; the slower second looks (more contrast,
    # glare painted over) are only for the one that came closest. Running them on every
    # outline cost a card the scanner doesn't know about 1.3 s of work per look.
    for found in _distinct(outlines):
        for factor in config.OUTLINE_FACTORS:
            corners = grow(found, factor)
            hit = _rank_both_ways(matcher, warp_card(frame, corners))
            if best[1] is None or hit.distance < best[1].distance:
                best = (corners, hit)
            if hit.distance <= GOOD_ENOUGH:
                break
        if best[1].distance <= GOOD_ENOUGH:
            break
    corners, hit = best
    if hit.distance > config.SURE_DISTANCE:
        again = _rank(matcher, warp_card(frame, corners), hit)
        if again.distance < hit.distance:
            hit = again
        if hit.distance > config.MAX_MATCH_DISTANCE and not np.allclose(corners, outlines[0], atol=0.5):
            # Still nothing: the card's main outline, glare repair and all, in case the
            # glare is what put the others ahead of it.
            main = _rank(matcher, warp_card(frame, outlines[0]))
            if main.distance < hit.distance:
                corners, hit = outlines[0], main
    if refine and hit.id and hit.distance <= config.CANDIDATE_DISTANCE and confidence_of(hit.distance, hit.margin) != "sure":
        better = refine_outline(matcher, frame, corners, hit.id)
        if better is not None:
            again = _rank(matcher, warp_card(frame, better))
            # Nudging toward a card flatters it a little (a plain rectangle can be pulled
            # toward a plain card), so the nudged outline only counts when it's sure.
            if again.distance < hit.distance and confidence_of(again.distance, again.margin) == "sure":
                corners, hit = better, again
    if hit.distance > config.MAX_MATCH_DISTANCE:
        corners = outlines[0]       # nothing matched, so the "best" outline means little: keep the card's main one
    match = _match(matcher, corners, hit)
    if match.card is not None and match.confidence != "sure" and _sticks_out(corners, frame.shape):
        # The part outside the picture comes out black, which looks a little like any
        # dark or plain card: an outline that leaves the picture has to be sure, or it's
        # only a guess to offer.
        return Match(corners, None, hit.distance, hit.margin, None, [(match.card, hit.distance), *match.candidates])
    if printing and match.card is not None:
        _choose_printing(matcher, frame, match, wait)
    return match


PRINTING_NUDGE_OVER = 20    # a match further than this has its outline nudged before choosing its printing


def _choose_printing(matcher: Matcher, frame, match: Match, wait: float):
    """Note the card's look-alike printings (same art and frame, another set) and, with
    stock pictures to go by, choose among them by the details that differ: see
    printings.py. Changes match in place."""
    corners = match.corners
    if match.distance > PRINTING_NUDGE_OVER:
        # Not a close read: the outline is likely a little off, which hides the small
        # details that tell printings apart, and can leave the right printing out of the
        # look-alikes altogether. Lay it onto the card first.
        better = refine_outline(matcher, frame, corners, match.card.id)
        if better is not None:
            corners = better
    card_img = warp_card(frame, corners)
    turned = cv2.rotate(card_img, cv2.ROTATE_180)
    near, far = fingerprint(card_img), fingerprint(turned)
    if (matcher.distance_to(match.card.id, far) or 0) < (matcher.distance_to(match.card.id, near) or 0):
        card_img, near = turned, far            # the card is upside down in the picture
    front, back = (matcher.face_distances(match.card.id, near) if hasattr(matcher, "face_distances")
                   else (None, None))
    if back is not None and front is not None and back < front:
        return      # the back of a double-faced card is up: the stock pictures show fronts
    alike = matcher.lookalikes(match.card.id, near, printings.WINDOW, printings.MOST)
    if len(alike) < 2:
        return
    match.lookalikes = tuple(card_id for card_id, _ in alike)
    if matcher.pictures is None:
        return
    taught = _taught(matcher, match.lookalikes)
    try:
        chosen = printings.pick_printing(card_img, alike, matcher.pictures, wait, taught)
    except Exception as e:      # never let this stop a card being read
        print(f"Printing check skipped after an error: {e!r}")
        return
    if chosen is None:
        return
    card_id, match.printing_lead = chosen
    if card_id != match.card.id:
        match.card = matcher.get_card(card_id)


def _taught(matcher: Matcher, card_ids) -> dict[str, list[np.ndarray]]:
    """The scans you taught for these printings, prepared for printings.pick_printing
    (none when they can't be had: the stock pictures then choose on their own)."""
    found = {}
    try:
        for card_id, scans in matcher.learned_scans(list(card_ids), printings.TAUGHT_MOST).items():
            pictures = [p for p in (matcher.pictures.taught(config.CAPTURES_DIR / scan) for scan in scans)
                        if p is not None]
            if pictures:
                found[card_id] = pictures
    except Exception as e:
        print(f"Taught scans left out of the printing check after an error: {e!r}")
    return found


def _sticks_out(corners: np.ndarray, shape, slack: float = 0.01) -> bool:
    """Whether an outline leaves the picture (by more than a hair)."""
    h, w = shape[:2]
    over = slack * _size(corners)
    return bool(corners.min() < -over or corners[:, 0].max() > w - 1 + over or corners[:, 1].max() > h - 1 + over)


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


def _rank(matcher: Matcher, card_img, plain: Hit | None = None) -> Hit:
    """The closest card to a card picture, looking again with more contrast and without
    glare when it isn't sure. plain: the plain look (_rank_both_ways), if already done."""
    # The card might be upside down, so try both ways and keep the better match.
    best = plain if plain is not None else _rank_both_ways(matcher, card_img)
    if best.distance > config.SURE_DISTANCE:
        # Not sure yet: a dim or foil card often comes closer with its contrast evened out.
        boosted = _rank_both_ways(matcher, boost_contrast(card_img))
        if boosted.distance < best.distance:
            best = boosted
    if best.distance > config.MAX_MATCH_DISTANCE:
        # No match: a foil's glare may be hiding the art. Paint the bright patches over
        # and look again (2026-11-06: 4 of 5 misses on the sorter were foils).
        tamed = tame_glare(card_img)
        if tamed is not None:
            again = _rank_both_ways(matcher, tamed)
            if again.distance < best.distance:
                best = again
    return best


def _rank_both_ways(matcher: Matcher, card_img) -> Hit:
    best: Hit | None = None
    for img in (card_img, cv2.rotate(card_img, cv2.ROTATE_180)):
        hit = matcher.rank(fingerprint(img))
        if best is None or hit.distance < best.distance:
            best = hit
    return best
