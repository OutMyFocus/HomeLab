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


# The part of the card the second fingerprint looks at, as shares of its width and height:
# the art box on most frames. The whole-card fingerprint is mostly frame, name box and
# text box, which thousands of cards share, so among every card ever printed two
# different cards can sit close together. The art tells them apart. On frames where the
# art sits elsewhere (full art, old borders) it's still the same region on the stock
# picture and the scan, so it still works as a second opinion.
ART_BOX = (0.08, 0.11, 0.92, 0.56)
FINGERPRINT_BYTES = 64   # 32 for the whole card, then 32 for the art


def _phash(img: Image.Image) -> bytes:
    return np.packbits(imagehash.phash(img, hash_size=HASH_SIZE).hash.flatten()).tobytes()


def fingerprint_pil(img: Image.Image) -> bytes:
    """The 64-byte fingerprint of an upright card picture: the whole card, then its art."""
    img = img.convert("RGB")
    w, h = img.size
    x0, y0, x1, y1 = ART_BOX
    art = img.crop((round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h)))
    return _phash(img) + _phash(art)


# Glare: a foil (or a glossy card under the light bars) shows bright patches that aren't
# on the stock picture, and they pull the fingerprint away from it. tame_glare() paints
# over the brightest patches with what surrounds them before fingerprinting again.
GLARE_LEVEL = 200          # at least this bright (0-255 grey)...
GLARE_PERCENTILE = 97      # ...and in the brightest few percent of the card
GLARE_GROW = 7             # pixels to grow each patch by, so its soft edge goes too


def tame_glare(card_bgr: np.ndarray) -> np.ndarray | None:
    """The card with its glare patches painted over, or None when there's no glare
    worth the trouble (under 0.5 % of the card that bright)."""
    gray = cv2.cvtColor(card_bgr, cv2.COLOR_BGR2GRAY)
    level = max(GLARE_LEVEL, int(np.percentile(gray, GLARE_PERCENTILE)))
    mask = (gray >= level).astype(np.uint8) * 255
    if cv2.countNonZero(mask) < 0.005 * mask.size:
        return None
    mask = cv2.dilate(mask, np.ones((GLARE_GROW, GLARE_GROW), np.uint8))
    return cv2.inpaint(card_bgr, mask, GLARE_GROW, cv2.INPAINT_TELEA)


# Contrast: the bed is dark and a foil's colours come out flat and dim next to the stock
# picture. Evening out the contrast (CLAHE on the lightness only) brings the art back;
# on the Pi's unread cards (2026-11-09) it moved each one 1-4 bits closer to its card.
CONTRAST_CLIP = 2.0
CONTRAST_TILES = 8


def boost_contrast(card_bgr: np.ndarray) -> np.ndarray:
    """The card with its contrast evened out, colours kept."""
    lab = cv2.cvtColor(card_bgr, cv2.COLOR_BGR2LAB)
    clahe = cv2.createCLAHE(clipLimit=CONTRAST_CLIP, tileGridSize=(CONTRAST_TILES, CONTRAST_TILES))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def fingerprint(card_bgr: np.ndarray) -> bytes:
    """Same as fingerprint_pil(), for an upright, cropped card from the camera (OpenCV's BGR)."""
    return fingerprint_pil(Image.fromarray(cv2.cvtColor(card_bgr, cv2.COLOR_BGR2RGB)))


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
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=2)
    yield closed

    # 1b. The same, with thin lines erased: on a table, a seam or a cable touching the
    # card would otherwise join onto its shape.
    yield cv2.morphologyEx(closed, cv2.MORPH_OPEN, np.ones((11, 11), np.uint8))

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


def find_card_candidates(frame_bgr: np.ndarray, min_area_frac: float = 0.05) -> list[np.ndarray]:
    """Return every card-shaped outline (4 corners each) found by any of the methods."""
    if frame_bgr is None or frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3 or min(frame_bgr.shape[:2]) < 16:
        return []   # not a colour picture (a broken upload or a dead camera can hand back junk)
    # Work on a smaller copy for speed, then scale the corners back up.
    scale = min(1.0, 1000 / max(frame_bgr.shape[:2]))
    small = cv2.resize(frame_bgr, None, fx=scale, fy=scale) if scale < 1 else frame_bgr
    min_area = min_area_frac * small.shape[0] * small.shape[1]

    found = []
    for mask in _masks(small):
        # RETR_LIST also returns shapes inside other shapes: a card in a sleeve, or a card
        # whose outline merged with its neighbours on a crowded table.
        # Every point of each outline (CHAIN_APPROX_NONE), so the sides can be fitted exactly.
        contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        # Look at plenty of shapes: on a busy table, dice boxes and sleeves can be bigger than the cards.
        for c in sorted(contours, key=cv2.contourArea, reverse=True)[:60]:
            if cv2.contourArea(c) < min_area:
                break
            # The hull wraps the outline like a rubber band, which smooths over any gaps.
            hull = cv2.convexHull(c)
            for eps in (0.02, 0.04, 0.06):
                approx = cv2.approxPolyDP(hull, eps * cv2.arcLength(hull, True), True)
                if len(approx) == 4:
                    break
            refined = None
            if len(approx) == 4:
                refined = _refine_corners(c, approx)
            else:
                # Not a clean 4-cornered shape (a sleeve's rounded, shiny edge, say). If it
                # nearly fills the tightest rectangle around it, that rectangle is the card.
                (_, _), (rw, rh), _ = rect = cv2.minAreaRect(c)
                if rw * rh == 0 or cv2.contourArea(c) / (rw * rh) < 0.85:
                    continue
                approx = cv2.boxPoints(rect)
            x, y, w, h = cv2.boundingRect(approx)
            if x <= 2 or y <= 2 or x + w >= small.shape[1] - 2 or y + h >= small.shape[0] - 2:
                continue  # touches the photo's edge: the whole background, not a card
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
