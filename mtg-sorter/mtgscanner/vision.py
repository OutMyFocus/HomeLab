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


# --- A card put back together from its sides -------------------------------
# A card held in the hand has a thumb over one edge; on a table it may touch another
# card or a shadow. Its outline is then no clean 4-cornered shape, and the scanner used
# to settle for a piece inside it instead: the art box, or the half beside the thumb
# (Nic, 2026-11-16: "it keeps looking at small sections of certain cards"). The sides
# the camera does see are still straight, so the card is rebuilt from them.
SIDES_GOOD_FIT = 0.85     # an outline this close to its 4-cornered shape needs no rebuilding
SIDES_POOR_FIT = 0.6      # ...and one further than this is dropped when a rebuilt card is found
SIDES_MIN_FIT_4 = 0.8     # a card rebuilt from 4 sides: this share of it lies on the outline
SIDES_MIN_FIT_3 = 0.64    # ...from 3 sides (the 4th worked out from the card's shape)
SIDES_MOST = 4            # rebuilt cards kept per picture
SIDES_OUT = 0.10          # a rebuilt card may stick out of the picture by this share of its diagonal
CARD_RATIO = 63 / 88      # a card's width over its height


def _distance_map(pts: np.ndarray) -> tuple[np.ndarray, int, int]:
    """How far every spot around an outline is from it: (map, left, top), at half size
    (so in units of 2 pixels). Made once per outline, so each shape tried against it
    costs next to nothing."""
    half = pts.astype(np.intp) // 2
    x0, y0 = (int(v) - 2 for v in half.min(axis=0))
    x1, y1 = (int(v) + 2 for v in half.max(axis=0))
    blank = np.full((y1 - y0 + 1, x1 - x0 + 1), 255, np.uint8)
    blank[half[:, 1] - y0, half[:, 0] - x0] = 0
    return cv2.distanceTransform(blank, cv2.DIST_L2, 3), x0, y0


def _fit(corners: np.ndarray, near: tuple[np.ndarray, int, int]) -> float:
    """The share of a 4-cornered shape's sides that lies on the outline (its distance map)."""
    dist, x0, y0 = near
    q = corners.reshape(4, 2).astype("float32")
    steps = np.linspace(0.04, 0.96, 24, dtype="float32")[:, None]
    samples = np.concatenate([q[i] + (q[(i + 1) % 4] - q[i]) * steps for i in range(4)])
    side = min(np.linalg.norm(q[0] - q[1]), np.linalg.norm(q[1] - q[2]))
    tol = max(2.5, 0.025 * float(side))
    x = np.floor(samples[:, 0] / 2).astype(np.intp) - x0
    y = np.floor(samples[:, 1] / 2).astype(np.intp) - y0
    inside = (x >= 0) & (y >= 0) & (x < dist.shape[1]) & (y < dist.shape[0])
    return float((dist[y[inside], x[inside]] * 2 <= tol).sum() / len(samples))


def _side_lines(pts: np.ndarray, min_len: float) -> list[tuple]:
    """The long straight stretches of an outline: (point on it, direction, length, ends)."""
    chain = pts.reshape(-1, 1, 2)
    rough = cv2.approxPolyDP(chain, 0.006 * cv2.arcLength(chain, True), True).reshape(-1, 2).astype("float32")
    stretches = []
    for i in range(len(rough)):
        length = float(np.linalg.norm(rough[(i + 1) % len(rough)] - rough[i]))
        if length >= min_len:
            stretches.append((length, i))
    lines = []
    for length, i in sorted(stretches, reverse=True)[:14]:
        a, b = rough[i], rough[(i + 1) % len(rough)]
        along = (b - a) / length
        # The outline's points along the straight middle of this stretch, close to it.
        rel = pts - a
        t = rel @ along
        off = np.abs(rel[:, 0] * along[1] - rel[:, 1] * along[0])
        near = pts[(t > 0.1 * length) & (t < 0.9 * length) & (off < max(2.5, 0.02 * length))]
        p, d = a, along
        if len(near) >= 6:
            vx, vy, x0, y0 = cv2.fitLine(near, cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
            p, d = np.array([x0, y0], "float32"), np.array([vx, vy], "float32")
        ts = [float((a - p) @ d), float((b - p) @ d)]
        lines.append([p, d, length, min(ts), max(ts)])
    # Stretches of the same side (either side of a thumb) count as one line.
    lines.sort(key=lambda ln: -ln[2])
    merged: list[list] = []
    for p, d, length, t0, t1 in lines:
        for m in merged:
            mid = p + d * (t0 + t1) / 2
            rel = mid - m[0]
            if abs(float(d @ m[1])) > 0.9976 and abs(float(rel[0] * m[1][1] - rel[1] * m[1][0])) < max(3.0, 0.02 * m[2]):
                ends = [float((p + d * t - m[0]) @ m[1]) for t in (t0, t1)]
                m[2] += length
                m[3], m[4] = min(m[3], *ends), max(m[4], *ends)
                break
        else:
            merged.append([p, d, length, t0, t1])
    merged.sort(key=lambda ln: -ln[2])
    return [tuple(m) for m in merged[:8]]


def _on_border(a: np.ndarray, b: np.ndarray, w: int, h: int, near: float = 3.0) -> bool:
    """Whether the stretch from a to b runs along the edge of the picture."""
    return bool((a[0] <= near and b[0] <= near) or (a[1] <= near and b[1] <= near)
                or (a[0] >= w - 1 - near and b[0] >= w - 1 - near) or (a[1] >= h - 1 - near and b[1] >= h - 1 - near))


def _cross(l1, l2) -> np.ndarray | None:
    """Where two lines meet."""
    (p1, d1), (p2, d2) = l1[:2], l2[:2]
    cross = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(cross) < 1e-6:
        return None
    s = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / cross
    return p1 + s * d1


def _cards_from_sides(pts: np.ndarray, near: tuple, min_area: float, shape) -> list[tuple[float, np.ndarray]]:
    """Card-shaped outlines made from the straight stretches of a broken outline, each
    with how well it fits: (fit, corners), best first, two at most."""
    if len(pts) < 40:
        return []
    min_side = (min_area * CARD_RATIO) ** 0.5     # the short side of the smallest card
    # The picture's own border isn't a side of anything.
    h, w = shape[:2]
    lines = [ln for ln in _side_lines(pts, 0.35 * min_side)
             if not _on_border(ln[0] + ln[1] * ln[3], ln[0] + ln[1] * ln[4], w, h)]
    if len(lines) < 3:
        return []
    center = pts.mean(axis=0)

    def angle(l1, l2) -> float:
        return float(np.degrees(np.arccos(min(1.0, abs(float(l1[1] @ l2[1]))))))

    def apart(l1, l2) -> float:     # how far the second line's middle is from the first line
        rel = l2[0] + l2[1] * (l2[3] + l2[4]) / 2 - l1[0]
        return abs(float(rel[0] * l1[1][1] - rel[1] * l1[1][0]))

    pairs = [(i, j) for i in range(len(lines)) for j in range(i + 1, len(lines))
             if angle(lines[i], lines[j]) < 12 and apart(lines[i], lines[j]) >= min_side]
    quads = []      # (fit needed, corners)
    for a, b in pairs:
        la, lb = lines[a], lines[b]
        # 4 sides seen: two pairs of opposite sides.
        for c, d in pairs:
            if c <= a or len({a, b, c, d}) < 4 or angle(la, lines[c]) < 60:
                continue
            lc, ld = lines[c], lines[d]
            quads.append((SIDES_MIN_FIT_4, [_cross(la, lc), _cross(lc, lb), _cross(lb, ld), _cross(ld, la)]))
        # 3 sides seen: the two opposite ones and one across. The 4th is as far from the
        # one across as a card is long (or wide), on the side the outline is on.
        for c, lc in enumerate(lines):
            if c in (a, b) or angle(la, lc) < 60:
                continue
            p1, p2 = _cross(la, lc), _cross(lb, lc)
            if p1 is None or p2 is None:
                continue
            width = float(np.linalg.norm(p2 - p1))
            normal = np.array([-lc[1][1], lc[1][0]], "float32")
            if float((center - lc[0]) @ normal) < 0:
                normal = -normal
            # How far along the two sides the outline goes from the one across.
            reach = max(max(abs(float((ln[0] + ln[1] * t - p) @ ln[1])) for t in ln[3:5])
                        for ln, p in ((la, p1), (lb, p2)))
            for other in (width / CARD_RATIO, width * CARD_RATIO):
                if not 0.45 * other <= reach <= 1.08 * other:
                    continue
                far = (lc[0] + normal * other, lc[1])
                quads.append((SIDES_MIN_FIT_3, [p1, p2, _cross(lb, far), _cross(la, far)]))
    out = []
    for need, quad in quads:
        if any(q is None for q in quad):
            continue
        corners = _order_corners(np.array(quad, "float32"))
        # A card may stick out of the picture a little (held close to the phone): its
        # sides inside the picture still say where it ends.
        slack = SIDES_OUT * float(np.linalg.norm(corners[0] - corners[2]))
        if (corners.min() < -slack or corners[:, 0].max() > w + slack or corners[:, 1].max() > h + slack
                or cv2.contourArea(corners) < min_area or not cv2.isContourConvex(corners)
                or not _looks_like_card(corners, 0.64, 0.8)):
            continue
        fit = _fit(corners, near)
        if fit >= need and all(np.abs(corners - o).max() > 3 for _, o in out):
            out.append((fit, corners))
    out.sort(key=lambda r: -r[0])
    return out[:2]


def find_card_candidates(frame_bgr: np.ndarray, min_area_frac: float = 0.05) -> list[np.ndarray]:
    """Return every card-shaped outline (4 corners each) found by any of the methods."""
    return [corners for _, corners in find_scored_candidates(frame_bgr, min_area_frac, rebuild=False)]


def find_scored_candidates(frame_bgr: np.ndarray, min_area_frac: float = 0.05,
                           rebuild: bool = True) -> list[tuple[float, np.ndarray]]:
    """The same, each with how well it fits the shape it was found on: (fit, corners).
    1.0 is a clean card; under SIDES_GOOD_FIT, something broke the outline and these
    corners are a guess (the shape stretched over a thumb, say). With rebuild off, shapes
    are taken as they are (every fit is 1.0) and no card is put back together from its
    sides: what the machine's camera gets, where nothing covers the card."""
    if frame_bgr is None or frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3 or min(frame_bgr.shape[:2]) < 16:
        return []   # not a colour picture (a broken upload or a dead camera can hand back junk)
    # Work on a smaller copy for speed, then scale the corners back up.
    scale = min(1.0, 1000 / max(frame_bgr.shape[:2]))
    small = cv2.resize(frame_bgr, None, fx=scale, fy=scale) if scale < 1 else frame_bgr
    min_area = min_area_frac * small.shape[0] * small.shape[1]

    found = []
    rebuilt = []   # (how well it fits, corners): whole cards put back together from their sides
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
            corners = None
            if len(approx) == 4:
                refined = _refine_corners(c, approx)
            else:
                # Not a clean 4-cornered shape (a sleeve's rounded, shiny edge, say). If it
                # nearly fills the tightest rectangle around it, that rectangle is the card.
                (_, _), (rw, rh), _ = rect = cv2.minAreaRect(c)
                approx = cv2.boxPoints(rect) if rw * rh and cv2.contourArea(c) / (rw * rh) >= 0.85 else None
            if approx is not None:
                x, y, w, h = cv2.boundingRect(approx)
                if x > 2 and y > 2 and x + w < small.shape[1] - 2 and y + h < small.shape[0] - 2:
                    corners = _order_corners(refined if refined is not None else approx)
                    if not _looks_like_card(corners):
                        corners = None
                # else it touches the photo's edge: the whole background, not a card
            if not rebuild:
                if corners is not None:
                    found.append((1.0, corners / scale))
                continue
            pts = c.reshape(-1, 2).astype("float32")
            near = _distance_map(pts)
            fit = _fit(corners, near) if corners is not None else 0.0
            if fit >= SIDES_GOOD_FIT:
                found.append((fit, corners / scale))   # the shape is a card as it stands
                continue
            # Something breaks the outline (a thumb over one edge, a card touching its
            # neighbour, a shadow): the card's own sides are still straight stretches of
            # it. Put the card back together from those.
            better = _cards_from_sides(pts, near, min_area, small.shape)
            if corners is not None and not (better and fit < SIDES_POOR_FIT):
                found.append((fit, corners / scale))
            rebuilt += [(f, quad / scale) for f, quad in better]
    # The best-fitting rebuilt cards only: a busy table gives plenty of straight lines.
    rebuilt.sort(key=lambda r: -r[0])
    return found + rebuilt[:SIDES_MOST]


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


def _looks_like_card(corners: np.ndarray, least: float = 0.6, most: float = 0.85) -> bool:
    """MTG cards are about 0.72 times as wide as they are tall. Reject other shapes."""
    tl, tr, br, bl = corners
    w = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
    h = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
    ratio = min(w, h) / max(w, h)
    return least < ratio < most


def warp_card(frame_bgr: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """Turn the tilted card into a flat, upright CARD_W x CARD_H image."""
    tl, tr, br, bl = corners
    # If the card is lying sideways (wider than tall), rotate the corner order.
    if np.linalg.norm(tr - tl) > np.linalg.norm(bl - tl):
        corners = np.array([bl, tl, tr, br], dtype="float32")
    dst = np.array([[0, 0], [CARD_W - 1, 0], [CARD_W - 1, CARD_H - 1], [0, CARD_H - 1]], dtype="float32")
    m = cv2.getPerspectiveTransform(corners, dst)
    return cv2.warpPerspective(frame_bgr, m, (CARD_W, CARD_H))
