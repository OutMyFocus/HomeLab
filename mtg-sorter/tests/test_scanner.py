"""Offline tests: fake cards are drawn, photographed at an angle, and recognized."""

import csv

import cv2
import numpy as np
import pytest

from mtgscanner import config
from mtgscanner.collection import add_card
from mtgscanner.database import Card, Matcher, connect
from mtgscanner.sorting import choose_bin
from mtgscanner.vision import CARD_H, CARD_W, find_card, fingerprint
from scan import identify


def fake_card(seed: int) -> np.ndarray:
    """A random 'card': a black border with random colored shapes for art."""
    rng = np.random.default_rng(seed)
    img = np.zeros((CARD_H, CARD_W, 3), np.uint8)
    inner = img[25:-25, 25:-25]
    inner[:] = rng.integers(60, 200, 3)
    for _ in range(12):
        c = tuple(int(x) for x in rng.integers(0, 255, 3))
        p = tuple(int(x) for x in rng.integers(0, 430, 2))
        cv2.circle(inner, p, int(rng.integers(20, 90)), c, -1)
    return img


def photograph(card: np.ndarray, rotate180=False) -> np.ndarray:
    """Place the card tilted on a gray table, with blur and noise, like a camera would see it."""
    if rotate180:
        card = cv2.rotate(card, cv2.ROTATE_180)
    src = np.float32([[0, 0], [CARD_W, 0], [CARD_W, CARD_H], [0, CARD_H]])
    dst = np.float32([[220, 90], [560, 120], [530, 590], [190, 560]])
    m = cv2.getPerspectiveTransform(src, dst)
    table = np.full((720, 960, 3), 170, np.uint8)
    photo = cv2.warpPerspective(card, m, (960, 720), dst=table, borderMode=cv2.BORDER_TRANSPARENT)
    photo = cv2.GaussianBlur(photo, (3, 3), 0)
    noise = np.random.default_rng(0).normal(0, 6, photo.shape)
    return np.clip(photo + noise, 0, 255).astype(np.uint8)


@pytest.fixture
def db(tmp_path):
    conn = connect(tmp_path / "cards.db")
    prices = [0.10, 4.50, 25.00, None]
    for i in range(4):
        conn.execute(
            "INSERT INTO cards VALUES (?, ?, 'tst', 'Test Set', ?, 'rare', '', ?, NULL, ?)",
            (f"id{i}", f"Card {i}", str(i), prices[i], fingerprint(fake_card(i))),
        )
    conn.commit()
    return Matcher(conn)


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_recognizes_tilted_card(db, seed):
    corners, card_img = find_card(photograph(fake_card(seed)))
    assert card_img is not None
    card, dist = identify(db, card_img)
    assert card is not None and card.id == f"id{seed}", dist


def test_recognizes_upside_down_card(db):
    _, card_img = find_card(photograph(fake_card(2), rotate180=True))
    card, _ = identify(db, card_img)
    assert card.id == "id2"


def test_no_card_in_empty_photo():
    corners, card_img = find_card(np.full((480, 640, 3), 170, np.uint8))
    assert card_img is None


def test_unknown_card_is_rejected(db):
    _, card_img = find_card(photograph(fake_card(99)))
    card, dist = identify(db, card_img)
    assert card is None, dist


def test_price_bins(db):
    bins = [choose_bin(db.get_card(f"id{i}"))[0] for i in range(4)]
    assert bins == [1, 2, 3, config.NO_PRICE_BIN[0]]


def test_csv_matches_manabox_columns(db, tmp_path):
    path = tmp_path / "collection.csv"
    add_card(path, db.get_card("id1"), foil=True, bin_label="$1 - $10")
    rows = list(csv.DictReader(path.open()))
    assert rows[0]["Name"] == "Card 1"
    assert rows[0]["Quantity"] == "1"
    assert rows[0]["Set code"] == "TST"
    assert rows[0]["Collector number"] == "1"
    assert rows[0]["Foil"] == "foil"
