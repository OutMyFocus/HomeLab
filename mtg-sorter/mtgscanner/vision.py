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


def find_card(frame_bgr: np.ndarray, min_area_frac: float = 0.05):
    """Find the card in a photo.

    Returns (corners, card_image), or (None, None) if no card was found.
    corners is a 4x2 array, handy for drawing an outline on screen.
    """
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    # Black-bordered cards on a dark surface give faint edges, so use low thresholds
    # and then "close" small gaps so the card's outline becomes one connected shape.
    edges = cv2.Canny(gray, 10, 50)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = min_area_frac * frame_bgr.shape[0] * frame_bgr.shape[1]

    for c in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
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
        corners = _order_corners(approx)
        if _looks_like_card(corners):
            return corners, warp_card(frame_bgr, corners)
    return None, None


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
