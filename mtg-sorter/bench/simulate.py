"""Fake camera pictures of a card: a phone over a table, or the sorter's bed camera.

Every picture is made from a seed, so the same seed always gives the same picture.
"""

import cv2
import numpy as np

CARD_RATIO = 63 / 88


# ---------------------------------------------------------------- backgrounds
def _noise(rng, h, w, scale, octaves=3):
    out = np.zeros((h, w), np.float32)
    amp = 1.0
    for o in range(octaves):
        s = max(2, int(scale / (2 ** o)))
        small = rng.random((h // s + 2, w // s + 2)).astype(np.float32)
        out += amp * cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)[:h, :w]
        amp *= 0.5
    out -= out.min()
    return out / max(out.max(), 1e-6)


def background(rng, h, w, kind):
    if kind == "white":
        base = np.full((h, w, 3), rng.uniform(200, 245), np.float32)
        base += (_noise(rng, h, w, 200)[..., None] - 0.5) * 20
    elif kind == "grey":
        base = np.full((h, w, 3), rng.uniform(110, 170), np.float32)
        base += (_noise(rng, h, w, 120)[..., None] - 0.5) * 25
    elif kind == "black":
        base = np.full((h, w, 3), rng.uniform(15, 40), np.float32)
        base += (_noise(rng, h, w, 60)[..., None] - 0.5) * 12
    elif kind == "wood":
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        ang = rng.uniform(0, np.pi)
        t = x * np.cos(ang) + y * np.sin(ang)
        warp = _noise(rng, h, w, 300) * 60
        grain = 0.5 + 0.5 * np.sin((t + warp) / rng.uniform(6, 14))
        col = np.array([rng.uniform(40, 70), rng.uniform(80, 110), rng.uniform(130, 170)], np.float32)
        base = col * (0.7 + 0.4 * grain[..., None])
    elif kind == "felt":
        col = np.array([rng.uniform(40, 90), rng.uniform(90, 140), rng.uniform(20, 60)], np.float32)
        if rng.random() < 0.5:
            col = col[[2, 1, 0]]
        base = col * (0.85 + 0.3 * _noise(rng, h, w, 8, 2)[..., None])
    elif kind == "playmat":
        base = np.stack([_noise(rng, h, w, rng.uniform(80, 300), 4) for _ in range(3)], -1) * 255
        base = cv2.GaussianBlur(base, (0, 0), 3)
    elif kind == "clutter":
        base = background(rng, h, w, rng.choice(["wood", "grey", "white"])).astype(np.float32)
        for _ in range(int(rng.integers(3, 8))):
            x0, y0 = int(rng.integers(0, w)), int(rng.integers(0, h))
            x1, y1 = x0 + int(rng.integers(60, w // 2)), y0 + int(rng.integers(60, h // 3))
            cv2.rectangle(base, (x0, y0), (x1, y1), [float(v) for v in rng.uniform(0, 255, 3)], -1)
    elif kind == "bed_black":
        # printed black PLA: fine print lines, a little shine
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        lines = 0.5 + 0.5 * np.sin((x + y) / 2.2)
        base = np.full((h, w, 3), rng.uniform(22, 45), np.float32) + lines[..., None] * 6
    elif kind == "bed_white":
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        lines = 0.5 + 0.5 * np.sin((x - y) / 2.2)
        base = np.full((h, w, 3), rng.uniform(180, 220), np.float32) + lines[..., None] * 8
    else:
        raise ValueError(kind)
    return np.clip(base, 0, 255).astype(np.float32)


# ---------------------------------------------------------------- the card
def card_rgba(card_bgr):
    """The card picture with rounded corners (alpha), as float32."""
    h, w = card_bgr.shape[:2]
    a = np.zeros((h, w), np.uint8)
    r = int(round(0.048 * w))
    cv2.rectangle(a, (r, 0), (w - 1 - r, h - 1), 255, -1)
    cv2.rectangle(a, (0, r), (w - 1, h - 1 - r), 255, -1)
    for cx, cy in ((r, r), (w - 1 - r, r), (r, h - 1 - r), (w - 1 - r, h - 1 - r)):
        cv2.circle(a, (cx, cy), r, 255, -1, cv2.LINE_AA)
    return card_bgr.astype(np.float32), a.astype(np.float32) / 255


def foil_layer(rng, h, w):
    """A rainbow sheen sweeping across the card."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    ang = rng.uniform(0, np.pi)
    t = (x * np.cos(ang) + y * np.sin(ang)) / max(h, w)
    phase = rng.uniform(0, 2 * np.pi)
    freq = rng.uniform(1.5, 4)
    hue = (t * freq * 2 * np.pi + phase)
    rainbow = np.stack([np.sin(hue), np.sin(hue + 2.1), np.sin(hue + 4.2)], -1) * 0.5 + 0.5
    band = np.exp(-((t - rng.uniform(0.2, 0.8)) ** 2) / (2 * rng.uniform(0.05, 0.2) ** 2))
    return rainbow * 255, band


def glare_blob(rng, h, w, strength, size):
    """A soft bright patch (a lamp's reflection)."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = rng.uniform(0.1, 0.9) * w, rng.uniform(0.1, 0.9) * h
    sx, sy = size * w * rng.uniform(0.6, 1.4), size * h * rng.uniform(0.4, 1.0)
    ang = rng.uniform(0, np.pi)
    dx, dy = x - cx, y - cy
    u = dx * np.cos(ang) + dy * np.sin(ang)
    v = -dx * np.sin(ang) + dy * np.cos(ang)
    g = np.exp(-(u ** 2 / (2 * sx ** 2) + v ** 2 / (2 * sy ** 2)))
    return np.clip(g * strength * 1.6, 0, strength)


def bar_glare(rng, h, w, strength):
    """Long bright bands: the reflection of LED light bars on a glossy card."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    out = np.zeros((h, w), np.float32)
    vertical = rng.random() < 0.5
    t = x / w if vertical else y / h
    for _ in range(int(rng.integers(1, 3))):
        c = rng.uniform(0.05, 0.95)
        width = rng.uniform(0.02, 0.07)
        out += np.exp(-((t - c) ** 2) / (2 * width ** 2))
    return np.clip(out, 0, 1) * strength


# ---------------------------------------------------------------- one picture
def compose(rng, card_bgr, frame_hw, bg_kind, *, center, card_len, angle, tilt,
            glare=0.0, glare_size=0.25, bars=0.0, foil=0.0, thumb=False, sleeve=False,
            light=1.0, warm=0.0, shadow=0.0, blur=0.0, motion=0.0, noise=2.0, jpeg=85,
            gradient=0.0):
    """Lay the card on a background and take its picture.

    Returns (picture BGR uint8, card corners in the picture (tl, tr, br, bl))."""
    H, W = frame_hw
    frame = background(np.random.default_rng(7) if bg_kind.startswith("bed") else rng, H, W, bg_kind)
    card, alpha = card_rgba(card_bgr)
    ch, cw = card.shape[:2]

    # card surface effects (in card space)
    if foil > 0:
        rainbow, band = foil_layer(rng, ch, cw)
        grey = card.mean(axis=2, keepdims=True)
        card = card * (1 - 0.25 * foil) + grey * 0.25 * foil          # foils look a bit washed out
        card = card + (rainbow - 128) * 0.35 * foil + band[..., None] * 90 * foil
    if glare > 0:
        g = glare_blob(rng, ch, cw, glare, glare_size)
        card = card * (1 - 0.6 * g[..., None]) + 255 * 0.6 * g[..., None] + g[..., None] * 100
    if bars > 0:
        g = bar_glare(rng, ch, cw, bars)
        card = card + g[..., None] * 200
    card = np.clip(card, 0, 255)

    if sleeve:
        # a clear sleeve: a few pixels bigger, shiny edge, slight haze
        pad = int(0.03 * cw)
        sc = np.zeros((ch + 2 * pad, cw + 2 * pad, 3), np.float32)
        sa = np.zeros(sc.shape[:2], np.float32)
        sc[pad:pad + ch, pad:pad + cw] = card
        sa[pad:pad + ch, pad:pad + cw] = alpha
        haze = rng.uniform(10, 40)
        sc = sc * 0.9 + haze
        edge = np.zeros_like(sa)
        cv2.rectangle(edge, (0, 0), (sc.shape[1] - 1, sc.shape[0] - 1), 1.0, max(2, pad // 2))
        sc = sc * (1 - edge[..., None] * 0.5) + edge[..., None] * 230 * 0.5
        sa = np.maximum(sa, 0.25)
        card, alpha = np.clip(sc, 0, 255), sa
        ch, cw = card.shape[:2]

    # where the card goes: a rectangle of the card's shape, turned and tilted
    long = card_len
    short = long * cw / ch
    rect = np.array([[-short / 2, -long / 2], [short / 2, -long / 2], [short / 2, long / 2], [-short / 2, long / 2]], np.float32)
    a = np.radians(angle)
    rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]], np.float32)
    pts = rect @ rot.T
    # perspective: scale one side of the card down (camera not straight above)
    if tilt:
        t_ang = rng.uniform(0, 2 * np.pi)
        d = np.array([np.cos(t_ang), np.sin(t_ang)], np.float32)
        proj = pts @ d / (long / 2)
        pts = pts * (1 + tilt * proj)[:, None]
    pts += np.array(center, np.float32)
    # keep the whole card in the picture (a little margin)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    shift = np.maximum(0, np.array([0.02 * W, 0.02 * H]) - lo) - np.maximum(0, hi - np.array([0.98 * W, 0.98 * H]))
    pts += shift.astype(np.float32)
    src = np.array([[0, 0], [cw - 1, 0], [cw - 1, ch - 1], [0, ch - 1]], np.float32)
    m = cv2.getPerspectiveTransform(src, pts)
    warped = cv2.warpPerspective(card, m, (W, H), flags=cv2.INTER_AREA if long < ch else cv2.INTER_LINEAR)
    wa = cv2.warpPerspective(alpha, m, (W, H), flags=cv2.INTER_LINEAR)

    if shadow > 0:   # a soft drop shadow under the card
        sh = cv2.GaussianBlur(wa, (0, 0), max(2, long * 0.02))
        sh = np.roll(sh, (int(long * 0.015), int(long * 0.015)), (0, 1))
        frame *= (1 - shadow * sh)[..., None]

    frame = frame * (1 - wa[..., None]) + warped * wa[..., None]

    if thumb:
        # a thumb over one side of the card
        side = int(rng.integers(0, 4))
        p, q = pts[side], pts[(side + 1) % 4]
        at = p + (q - p) * rng.uniform(0.25, 0.75)
        inward = pts.mean(axis=0) - at
        inward /= np.linalg.norm(inward)
        c = at + inward * long * rng.uniform(-0.02, 0.06)
        size = (int(long * rng.uniform(0.09, 0.14)), int(long * rng.uniform(0.18, 0.26)))
        ang_t = np.degrees(np.arctan2(inward[1], inward[0]))
        skin = np.array([rng.uniform(90, 150), rng.uniform(120, 170), rng.uniform(170, 230)], np.float32)
        mask = np.zeros((H, W), np.float32)
        cv2.ellipse(mask, (int(c[0]), int(c[1])), size, ang_t, 0, 360, 1.0, -1, cv2.LINE_AA)
        far = c - inward * long * 0.4
        cv2.line(mask, (int(c[0]), int(c[1])), (int(far[0]), int(far[1])), 1.0, int(size[0] * 1.6), cv2.LINE_AA)
        mask = cv2.GaussianBlur(mask, (0, 0), 2)
        shade = 0.85 + 0.15 * _noise(rng, H, W, 40, 2)
        frame = frame * (1 - mask[..., None]) + (skin * shade[..., None]) * mask[..., None]

    # lighting
    frame *= light
    if gradient:
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        ang_g = rng.uniform(0, 2 * np.pi)
        g = ((x - W / 2) * np.cos(ang_g) + (y - H / 2) * np.sin(ang_g)) / max(H, W)
        frame *= (1 + gradient * g)[..., None]
    if warm:
        frame *= np.array([1 - 0.25 * warm, 1.0, 1 + 0.15 * warm], np.float32)

    # the camera
    if blur > 0:
        frame = cv2.GaussianBlur(frame, (0, 0), blur)
    if motion > 0:
        k = int(motion) * 2 + 1
        kern = np.zeros((k, k), np.float32)
        kern[k // 2, :] = 1
        rotm = cv2.getRotationMatrix2D((k / 2 - 0.5, k / 2 - 0.5), rng.uniform(0, 180), 1)
        kern = cv2.warpAffine(kern, rotm, (k, k))
        frame = cv2.filter2D(frame, -1, kern / max(kern.sum(), 1e-6))
    if noise:
        frame += rng.normal(0, noise, frame.shape).astype(np.float32)
    frame = np.clip(frame, 0, 255).astype(np.uint8)
    ok, enc = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, int(jpeg)])
    return cv2.imdecode(enc, cv2.IMREAD_COLOR), pts


# ---------------------------------------------------------------- scenarios
PHONE_TABLES = ["white", "grey", "black", "wood", "felt", "playmat", "clutter"]
PHONE = ["table", "thumb", "glare", "foil", "sleeve", "dim", "far"]
MACHINE = ["bed", "bed_bars", "bed_foil", "bed_dim", "bed_white"]


def scenario(rng, card_bgr, kind, foil_ok=True):
    """One picture for a named situation. Returns (picture, corners, info dict)."""
    if kind in PHONE:
        portrait = rng.random() < 0.7
        H, W = (1920, 1080) if portrait else (1080, 1920)
        short = min(H, W)
        frac = rng.uniform(0.55, 0.85) if kind != "far" else rng.uniform(0.22, 0.35)
        long = short * frac / CARD_RATIO if portrait else short * frac
        long = min(long, 0.9 * max(H, W))
        margin = long * 0.6
        center = (rng.uniform(margin * CARD_RATIO, W - margin * CARD_RATIO) if W > 2 * margin * CARD_RATIO else W / 2,
                  rng.uniform(margin, H - margin) if H > 2 * margin else H / 2)
        angle = rng.normal(0, 8) + (90 if (not portrait and rng.random() < 0.5) else 0) + (180 if rng.random() < 0.3 else 0)
        kw = dict(center=center, card_len=long, angle=angle, tilt=rng.uniform(0, 0.12),
                  light=rng.uniform(0.8, 1.15), warm=rng.uniform(-0.3, 0.6), shadow=rng.uniform(0, 0.4),
                  blur=rng.uniform(0, 1.6), motion=rng.choice([0, 0, 0, 2, 3]), noise=rng.uniform(1, 5),
                  jpeg=rng.integers(70, 92), gradient=rng.uniform(0, 0.4))
        bg = str(rng.choice(PHONE_TABLES))
        if kind == "thumb":
            kw["thumb"] = True
        elif kind == "glare":
            kw["glare"] = rng.uniform(0.5, 1.0)
            kw["glare_size"] = rng.uniform(0.12, 0.3)
        elif kind == "foil":
            kw["foil"] = rng.uniform(0.5, 1.0)
            kw["glare"] = rng.uniform(0.2, 0.7)
        elif kind == "sleeve":
            kw["sleeve"] = True
            kw["glare"] = rng.uniform(0.0, 0.4)
        elif kind == "dim":
            kw["light"] = rng.uniform(0.35, 0.55)
            kw["noise"] = rng.uniform(5, 10)
            kw["blur"] = rng.uniform(0.8, 2.0)
            kw["warm"] = rng.uniform(0.3, 0.9)
        frame, pts = compose(rng, card_bgr, (H, W), bg, **kw)
        return frame, pts, {"bg": bg}
    # The sorter's bed camera: the camera straight above a fixed spot, card fed in from one
    # side and stopped, so it lies about the same place every time, nearly straight.
    H, W = 1080, 1440
    long = H * rng.uniform(0.80, 0.86)
    center = (W / 2 + rng.normal(0, W * 0.012), H / 2 + rng.normal(0, H * 0.01))
    angle = 90 * int(rng.integers(0, 2)) * 0 + rng.normal(0, 2.0) + (180 if rng.random() < 0.5 else 0)
    bg = "bed_white" if kind == "bed_white" else "bed_black"
    kw = dict(center=center, card_len=long, angle=angle, tilt=rng.uniform(0, 0.03),
              light=rng.uniform(0.85, 1.1), warm=rng.uniform(-0.4, 0.1), shadow=rng.uniform(0, 0.2),
              blur=rng.uniform(0.3, 1.3), motion=0, noise=rng.uniform(2, 5), jpeg=rng.integers(80, 92),
              gradient=rng.uniform(0, 0.3))
    if kind == "bed_bars":
        kw["bars"] = rng.uniform(0.3, 0.8)
    elif kind == "bed_foil":
        kw["foil"] = rng.uniform(0.5, 1.0)
        kw["bars"] = rng.uniform(0.2, 0.6)
    elif kind == "bed_dim":
        kw["light"] = rng.uniform(0.4, 0.6)
        kw["noise"] = rng.uniform(5, 9)
    frame, pts = compose(rng, card_bgr, (H, W), bg, **kw)
    return frame, pts, {"bg": bg, "card_share": float(cv2.contourArea(pts)) / (H * W)}


def empty_bed(rng, kind):
    H, W = 1080, 1440
    bg = "bed_white" if kind == "bed_white" else "bed_black"
    frame = background(np.random.default_rng(7), H, W, bg)
    frame = np.clip(frame + rng.normal(0, 3, frame.shape), 0, 255).astype(np.uint8)
    return frame
