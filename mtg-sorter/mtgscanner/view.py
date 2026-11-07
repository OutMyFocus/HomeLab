"""Turning and cropping the machine camera's picture, so it shows just the scan bed the
right way up. Set on the scanner page (Rotate, Crop) and kept in app_settings.json.

The picture is turned first, then cropped. The crop is [x0, y0, x1, y1] as shares of
the turned picture; None is the whole picture. Everything after this (finding cards,
slots, the picture on the page) sees only the cropped picture.
"""

import cv2

ROTATIONS = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
MIN_SIZE = 0.05     # a crop narrower or shorter than 5% of the picture is a slip of the mouse


def clean_rotation(raw) -> int | None:
    """0, 90, 180 or 270 (clockwise). None if it isn't one of those."""
    try:
        r = int(raw) % 360
    except (TypeError, ValueError):
        return None
    return r if r in (0, 90, 180, 270) else None


def clean_box(raw) -> list[float] | None:
    """[x0, y0, x1, y1] clamped to 0-1 with corners in order. None if malformed or tiny."""
    try:
        x0, y0, x1, y1 = (min(1.0, max(0.0, float(v))) for v in raw)
    except (TypeError, ValueError):
        return None
    (x0, x1), (y0, y1) = sorted((x0, x1)), sorted((y0, y1))
    if x1 - x0 < MIN_SIZE or y1 - y0 < MIN_SIZE:
        return None
    return [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]


def apply(frame, rotate: int, crop: list[float] | None):
    """The picture turned and cropped."""
    if rotate in ROTATIONS:
        frame = cv2.rotate(frame, ROTATIONS[rotate])
    if crop:
        h, w = frame.shape[:2]
        x0, y0, x1, y1 = round(crop[0] * w), round(crop[1] * h), round(crop[2] * w), round(crop[3] * h)
        if x1 - x0 >= 16 and y1 - y0 >= 16:
            frame = frame[y0:y1, x0:x1]
    return frame


def inside(box, outer):
    """A box given as shares of `outer` (itself shares of the picture), as shares of the picture."""
    if not outer:
        return list(box)
    ox0, oy0, ox1, oy1 = outer
    w, h = ox1 - ox0, oy1 - oy0
    return [ox0 + box[0] * w, oy0 + box[1] * h, ox0 + box[2] * w, oy0 + box[3] * h]


def relative(box, outer):
    """The reverse of inside(): a box in picture shares, as shares of `outer`, clipped to it."""
    if not outer:
        return list(box)
    ox0, oy0, ox1, oy1 = outer
    w, h = ox1 - ox0, oy1 - oy0
    out = [(box[0] - ox0) / w, (box[1] - oy0) / h, (box[2] - ox0) / w, (box[3] - oy0) / h]
    return [min(1.0, max(0.0, v)) for v in out]


def is_whole(box) -> bool:
    return box[0] <= 0.001 and box[1] <= 0.001 and box[2] >= 0.999 and box[3] >= 0.999


def turn_box(box, quarter_turns: int):
    """A box (shares of the picture) after the picture turns 90 degrees clockwise this many times."""
    x0, y0, x1, y1 = box
    for _ in range(quarter_turns % 4):
        # turning clockwise: a point (x, y) lands at (1 - y, x)
        x0, y0, x1, y1 = 1 - y1, x0, 1 - y0, x1
    return [round(v, 4) for v in (x0, y0, x1, y1)]


# --- Straighten: undo the camera's tilt and keystone, measured on a card --------------
#
# The camera looks at the bed from an angle, so a card that lies square on the bed shows
# as a slightly turned trapezoid. Straighten (Scan page, with a card on the bed) finds that
# card and works out the perspective warp that turns it back into an upright rectangle the
# shape of a card, centred where it was and about as big; the whole picture gets the same
# warp. It runs after Rotate and Crop and keeps the picture's size, so the feeder's landing
# zone and the slots stay about where they were. Kept as {"m": 3x3 matrix, "size": [w, h]}.

CARD_ASPECT = 63 / 88       # width / height of a Magic card


def straighten_from(frame, corners=None):
    """The straighten setting for this picture, from the biggest card in it, or None when
    no card is found. `corners` instead gives the card's four corners by hand, as [x, y]
    shares of the picture (any order): for a card whose border the detector can't see
    against a dark bed. Raises nothing."""
    import numpy as np
    from .recognize import find_cards
    from .vision import _order_corners
    fh, fw = frame.shape[:2]
    if corners is not None:
        try:
            pts = np.float32([[float(x) * fw, float(y) * fh] for x, y in corners])
        except (TypeError, ValueError):
            return None
        if pts.shape != (4, 2):
            return None
        quad = _order_corners(pts)
    else:
        try:
            cards = find_cards(frame)
        except Exception:
            return None
        if not cards:
            return None
        quad = _order_corners(np.asarray(cards[0][0], np.float32).reshape(4, 2))   # tl, tr, br, bl
    top, bottom = np.linalg.norm(quad[1] - quad[0]), np.linalg.norm(quad[2] - quad[3])
    left, right = np.linalg.norm(quad[3] - quad[0]), np.linalg.norm(quad[2] - quad[1])
    w, h = (top + bottom) / 2, (left + right) / 2
    if w < 8 or h < 8:
        return None
    aspect = CARD_ASPECT if h >= w else 1 / CARD_ASPECT      # upright card, or lying sideways
    scale = (w * h / aspect) ** 0.5                            # keep its area
    tw, th = aspect * scale, scale
    cx, cy = quad.mean(axis=0)
    target = np.float32([[cx - tw / 2, cy - th / 2], [cx + tw / 2, cy - th / 2],
                         [cx + tw / 2, cy + th / 2], [cx - tw / 2, cy + th / 2]])
    m = cv2.getPerspectiveTransform(quad, target)
    return {"m": [round(float(v), 8) for v in m.reshape(-1)], "size": [int(fw), int(fh)]}


def clean_straighten(raw):
    """A saved straighten setting, or None if it isn't one."""
    try:
        m = [float(v) for v in raw["m"]]
        w, h = (int(v) for v in raw["size"])
    except (TypeError, ValueError, KeyError):
        return None
    if len(m) != 9 or w < 16 or h < 16:
        return None
    return {"m": m, "size": [w, h]}


def straighten(frame, setting):
    """The picture with the straighten warp applied. A picture of another size than the one
    it was measured on (the camera or the crop changed) is scaled to fit the warp."""
    import numpy as np
    if not setting:
        return frame
    fh, fw = frame.shape[:2]
    w, h = setting["size"]
    m = np.float32(setting["m"]).reshape(3, 3)
    if (fw, fh) != (w, h):
        sx, sy = fw / w, fh / h
        m = np.float32([[sx, 0, 0], [0, sy, 0], [0, 0, 1]]) @ m @ np.float32([[1 / sx, 0, 0], [0, 1 / sy, 0], [0, 0, 1]])
    return cv2.warpPerspective(frame, m, (fw, fh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
