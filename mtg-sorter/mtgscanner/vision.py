"""Camera/image side: find the card in a photo, straighten it, and fingerprint it.

How it works:
  1. Find edges in the image and look for the biggest 4-cornered shape (the card).
  2. "Warp" that shape into a flat, upright rectangle, as if scanned on a flatbed.
  3. Compute a perceptual hash: a short fingerprint that stays nearly the same
     when the image is a bit blurry, darker, or slightly shifted.
"""

import cv2
import imagehash
import numpy as np
from PIL import Image

# MTG cards are 63mm x 88mm. We straighten every card to this pixel size.
CARD_W, CARD_H = 488, 680
HASH_SIZE = 16  # 16x16 = 256-bit fingerprint


def fingerprint(card_bgr: np.ndarray) -> bytes:
    """Return the 32-byte fingerprint of an upright, cropped card image."""
    rgb = cv2.cvtColor(card_bgr, cv2.COLOR_BGR2RGB)
    h = imagehash.phash(Image.fromarray(rgb), hash_size=HASH_SIZE)
    return np.packbits(h.hash.flatten()).tobytes()


def fingerprint_pil(img: Image.Image) -> bytes:
    """Same as fingerprint(), but for an image loaded with Pillow (used when building the DB)."""
    h = imagehash.phash(img.convert("RGB"), hash_size=HASH_SIZE)
    return np.packbits(h.hash.flatten()).tobytes()


def _order_corners(pts: np.ndarray) -> np.ndarray:
    """Sort 4 points into: top-left, top-right, bottom-right, bottom-left."""
    pts = pts.reshape(4, 2).astype("float32")
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]], dtype="float32")


def _masks(small_bgr: np.ndarray):
    """Different ways of separating the card from the background, black and white images.

    No single trick works on every table, so we try several and let the card database
    pick the winner (see find_card_candidates).
    """
    gray = cv2.GaussianBlur(cv2.cvtColor(small_bgr, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    hsv = cv2.cvtColor(cv2.GaussianBlur(small_bgr, (9, 9), 0), cv2.COLOR_BGR2HSV)
    k = np.ones((5, 5), np.uint8)

    # 1. Edges: works on plain backgrounds (white paper, a plain mat).
    edges = cv2.Canny(gray, 10, 50)
    yield cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=2)

    # 2. Low color saturation: a black card border on a colorful surface (wood, a playmat).
    # Nearly black pixels get a random hue and saturation from sensor noise, so count
    # anything dark as unsaturated too, or the border itself falls out of the mask.
    _, sat = cv2.threshold(hsv[..., 1], 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    sat = cv2.bitwise_or(sat, cv2.inRange(hsv[..., 2], 0, 60))
    yield cv2.morphologyEx(cv2.morphologyEx(sat, cv2.MORPH_OPEN, k, iterations=2), cv2.MORPH_CLOSE, k, iterations=3)

    # 3. Darkness: a black border on a lighter surface.
    _, dark = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    yield cv2.morphologyEx(cv2.morphologyEx(dark, cv2.MORPH_OPEN, k, iterations=2), cv2.MORPH_CLOSE, k, iterations=3)


def _refine_corners(contour: np.ndarray, approx: np.ndarray) -> np.ndarray | None:
    """Sharpen a rough 4-corner outline by fitting a straight line to each side.

    Real cards have rounded corners, so the rough outline's vertices land a little
    inside the card. Fitting the straight middle of each edge and intersecting
    neighbouring edges gives the corner the card would have if it were square.
    Returns None if the outline is too degenerate to refine.
    """
    pts = contour.reshape(-1, 2).astype("float32")
    verts = approx.reshape(4, 2).astype("float32")
    lines = []
    for i in range(4):
        a, b = verts[i], verts[(i + 1) % 4]
        length = float(np.linalg.norm(b - a))
        if length < 8:
            return None
        along = (b - a) / length
        rel = pts - a
        t = rel @ along
        off = np.abs(rel[:, 0] * along[1] - rel[:, 1] * along[0])
        # Points along the straight middle 70% of this side, close to it.
        near = pts[(t > 0.15 * length) & (t < 0.85 * length) & (off < max(3.0, 0.03 * length))]
        if len(near) < 4:
            lines.append((a, along))
            continue
        vx, vy, x0, y0 = cv2.fitLine(near, cv2.DIST_L2, 0, 0.01, 0.01).ravel()
        lines.append((np.array([x0, y0], dtype="float32"), np.array([vx, vy], dtype="float32")))
    corners = []
    for i in range(4):
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        cross = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(cross) < 1e-6:
            return None
        s = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / cross
        corners.append(p1 + s * d1)
    corners = np.array(corners, dtype="float32")
    # A refined corner should stay close to the rough one. If a line fit went wild, give up.
    if np.linalg.norm(corners - verts, axis=1).max() > 0.08 * max(cv2.arcLength(approx, True), 1):
        return None
    return corners


# A card must cover at least this fraction of the picture to be considered. 1.5% is a
# card about 115 pixels wide on a 1280x720 webcam, which is about as small as it can
# still be fingerprinted.
MIN_CARD_AREA = 0.015


def find_card_candidates(frame_bgr: np.ndarray, min_area_frac: float = MIN_CARD_AREA) -> list[np.ndarray]:
    """Return every card-shaped outline (4 corners each) found by any of the methods."""
    if frame_bgr is None or frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3 or min(frame_bgr.shape[:2]) < 16:
        return []   # not a colour picture (a dead camera can hand back junk)
    # Work on a smaller copy for speed, then scale the corners back up.
    scale = min(1.0, 1000 / max(frame_bgr.shape[:2]))
    small = cv2.resize(frame_bgr, None, fx=scale, fy=scale) if scale < 1 else frame_bgr
    min_area = min_area_frac * small.shape[0] * small.shape[1]

    found = []
    for mask in _masks(small):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        for c in sorted(contours, key=cv2.contourArea, reverse=True)[:3]:
            if cv2.contourArea(c) < min_area:
                break
            # The hull wraps the outline like a rubber band, which smooths over any gaps.
            hull = cv2.convexHull(c)
            for eps in (0.02, 0.04, 0.06):
                approx = cv2.approxPolyDP(hull, eps * cv2.arcLength(hull, True), True)
                if len(approx) == 4:
                    break
            if len(approx) != 4:
                continue
            x, y, w, h = cv2.boundingRect(approx)
            if x <= 2 or y <= 2 or x + w >= small.shape[1] - 2 or y + h >= small.shape[0] - 2:
                continue  # touches the photo's edge: the whole background, not a card
            refined = _refine_corners(c, approx)
            corners = _order_corners(refined if refined is not None else approx) / scale
            if _looks_like_card(corners):
                found.append(corners)
    return found


def grow(corners: np.ndarray, factor: float) -> np.ndarray:
    """Push the 4 corners outward from the center (factor 1.04 = 4% bigger).

    Detection often lands a little inside the card's real edge, and fingerprints
    are sensitive to that, so the scanner also tries slightly bigger outlines.
    """
    center = corners.mean(axis=0)
    return ((corners - center) * factor + center).astype("float32")


def find_card(frame_bgr: np.ndarray):
    """Find the card in a photo using the first outline found (no database needed).

    Returns (corners, card_image), or (None, None) if no card was found.
    """
    candidates = find_card_candidates(frame_bgr)
    if not candidates:
        return None, None
    return candidates[0], warp_card(frame_bgr, candidates[0])


def _looks_like_card(corners: np.ndarray) -> bool:
    """MTG cards are about 0.72 times as wide as they are tall. Reject other shapes."""
    tl, tr, br, bl = corners
    w = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
    h = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
    ratio = min(w, h) / max(w, h)
    return 0.6 < ratio < 0.85


def warp_card(frame_bgr: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """Turn the tilted card into a flat, upright CARD_W x CARD_H image."""
    tl, tr, br, bl = corners
    # If the card is lying sideways (wider than tall), rotate the corner order.
    if np.linalg.norm(tr - tl) > np.linalg.norm(bl - tl):
        corners = np.array([bl, tl, tr, br], dtype="float32")
    dst = np.array([[0, 0], [CARD_W - 1, 0], [CARD_W - 1, CARD_H - 1], [0, CARD_H - 1]], dtype="float32")
    m = cv2.getPerspectiveTransform(corners, dst)
    return cv2.warpPerspective(frame_bgr, m, (CARD_W, CARD_H))
