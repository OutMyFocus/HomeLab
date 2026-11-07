"""Straighten the machine camera's picture by itself, from the cards it recognizes.

Nic (2026-11-07): "make sure the straighten is perfect, make the camera 100% automatic".
One card measured once isn't good enough: on the dark bed the detector sometimes puts a
corner on a light bar or the black border's inside, and a single bad outline tilted the
picture 3-4° the wrong way (seen on the Pi). So instead:

- Every card the scanner recognizes for SURE gives a sample: its outline, which matched
  the stock picture closely, so its corners are good. Outlines that don't look like a
  card seen almost straight on (corner angles, proportions), or that reach the picture's
  left or right edge where the light bars glare, are left out.
- Once there are enough samples, the median card shape is worked out: the shape the
  camera gives a card, with each card's own small turn on the bed averaged out. The
  picture is straightened so that shape becomes a perfect 63x88 rectangle.
- A correction bigger than the camera can plausibly need (config.AUTO_STRAIGHT_MAX_*)
  is refused rather than applied, and the warp only changes between cards, never while
  one is being read.

The scanner works in the straightened picture, so a sample's corners are first mapped
back into the picture as the camera gives it (after Rotate and Crop).
"""

from collections import deque

import cv2
import numpy as np

from . import config, view

ASPECT = view.CARD_ASPECT


def _ordered(quad) -> np.ndarray:
    from .vision import _order_corners
    return _order_corners(np.asarray(quad, np.float32).reshape(4, 2))


def _angles(q) -> list[float]:
    out = []
    for i in range(4):
        a, b, c = q[i - 1], q[i], q[(i + 1) % 4]
        u, v = a - b, c - b
        cos = float(np.dot(u, v) / max(1e-6, np.linalg.norm(u) * np.linalg.norm(v)))
        out.append(float(np.degrees(np.arccos(max(-1.0, min(1.0, cos))))))
    return out


def plausible(quad, size) -> bool:
    """A card outline seen nearly straight on, not near the picture's sides."""
    q = _ordered(quad)
    w, h = size
    edge = float(getattr(config, "AUTO_STRAIGHT_EDGE", 0.04))
    if q[:, 0].min() < edge * w or q[:, 0].max() > (1 - edge) * w:
        return False
    if q[:, 1].min() < 0 or q[:, 1].max() > h:
        return False
    if any(abs(a - 90) > float(getattr(config, "AUTO_STRAIGHT_MAX_CORNER", 8.0)) for a in _angles(q)):
        return False
    width = (np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3])) / 2
    height = (np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1])) / 2
    if height < width:                      # lying sideways: not how the sorter's cards come
        return False
    return abs(width / height / ASPECT - 1) <= float(getattr(config, "AUTO_STRAIGHT_MAX_SHAPE", 0.12))


def median_quad(quads) -> np.ndarray:
    """The typical outline: each sample's corners about its own middle, scaled to the same
    size, then the median of each corner, put back at the median middle and size."""
    shapes, centres, sizes = [], [], []
    for q in quads:
        q = _ordered(q)
        c = q.mean(axis=0)
        s = float(np.sqrt(abs(cv2.contourArea(q))))
        if s < 1:
            continue
        shapes.append((q - c) / s)
        centres.append(c)
        sizes.append(s)
    shape = np.median(np.stack(shapes), axis=0)
    return (shape * float(np.median(sizes)) + np.median(np.stack(centres), axis=0)).astype(np.float32)


def correction(setting, size) -> tuple[float, float]:
    """How much a straighten setting changes the picture: (largest edge turn in degrees,
    largest change in an edge's length as a share), measured on a card-shaped box."""
    w, h = size
    ch = 0.5 * h
    cw = ch * ASPECT
    box = np.float32([[w / 2 - cw / 2, h / 2 - ch / 2], [w / 2 + cw / 2, h / 2 - ch / 2],
                      [w / 2 + cw / 2, h / 2 + ch / 2], [w / 2 - cw / 2, h / 2 + ch / 2]])
    m = np.float32(setting["m"]).reshape(3, 3)
    out = cv2.perspectiveTransform(box.reshape(1, 4, 2), m).reshape(4, 2)
    turn, stretch = 0.0, 0.0
    for i in range(4):
        a0, a1 = box[i], box[(i + 1) % 4]
        b0, b1 = out[i], out[(i + 1) % 4]
        da, db = a1 - a0, b1 - b0
        ang = abs(np.degrees(np.arctan2(da[0] * db[1] - da[1] * db[0], float(np.dot(da, db)))))
        turn = max(turn, float(ang))
        stretch = max(stretch, abs(float(np.linalg.norm(db) / np.linalg.norm(da)) - 1))
    return turn, stretch


class AutoStraighten:
    """Collects samples and says when the picture's straightening should change."""

    def __init__(self):
        self.samples = deque(maxlen=int(getattr(config, "AUTO_STRAIGHT_KEEP", 25)))
        self.since = 0              # samples added since the setting was last worked out
        self.size = None
        self.last_refused = None

    def reset(self):
        """Rotate, Crop or a new camera: the old samples belong to another picture."""
        self.samples.clear()
        self.since, self.size = 0, None

    def add(self, corners, current, size) -> bool:
        """A card recognized for sure, with its corners in the picture the scanner sees
        (straightened by `current`, or not). True if it was kept as a sample."""
        q = np.asarray(corners, np.float32).reshape(1, 4, 2)
        if current:
            m = np.float32(current["m"]).reshape(3, 3)
            sw, sh = current["size"]
            if tuple(size) != (sw, sh):
                sx, sy = size[0] / sw, size[1] / sh
                m = np.float32([[sx, 0, 0], [0, sy, 0], [0, 0, 1]]) @ m @ np.float32([[1 / sx, 0, 0], [0, 1 / sy, 0], [0, 0, 1]])
            q = cv2.perspectiveTransform(q, np.linalg.inv(m))
        q = q.reshape(4, 2)
        if self.size is not None and tuple(self.size) != tuple(size):
            self.reset()
        self.size = tuple(size)
        if not plausible(q, size):
            return False
        self.samples.append(q)
        self.since += 1
        return True

    def proposal(self, current):
        """A new straighten setting when enough new samples say the picture should change,
        else None. A setting that would correct more than the camera can plausibly be off
        is refused (kept in last_refused, for the page)."""
        need = int(getattr(config, "AUTO_STRAIGHT_SAMPLES", 8))
        if len(self.samples) < need or self.since < (need if current is None else max(3, need // 2)):
            return None
        self.since = 0
        w, h = self.size
        quad = median_quad(self.samples)
        corners = [[float(x) / w, float(y) / h] for x, y in quad]
        blank = np.zeros((h, w, 3), np.uint8)
        setting = view.straighten_from(blank, corners)
        if setting is None:
            return None
        turn, stretch = correction(setting, (w, h))
        if turn > float(getattr(config, "AUTO_STRAIGHT_MAX_TURN", 3.0)) or \
                stretch > float(getattr(config, "AUTO_STRAIGHT_MAX_STRETCH", 0.08)):
            self.last_refused = {"turn": round(turn, 2), "stretch": round(stretch, 3)}
            return None
        if current:
            a = cv2.perspectiveTransform(quad.reshape(1, 4, 2), np.float32(setting["m"]).reshape(3, 3))
            b = cv2.perspectiveTransform(quad.reshape(1, 4, 2), np.float32(current["m"]).reshape(3, 3))
            if np.abs(a - b).max() < float(getattr(config, "AUTO_STRAIGHT_MIN_MOVE", 0.002)) * h:
                return None         # no real change: keep the picture steady
        return setting
