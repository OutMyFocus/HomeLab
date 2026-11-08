"""Offline tests: fake cards are drawn, photographed at an angle, and recognized."""

import csv

import cv2
import numpy as np
import pytest

from mtgscanner import config
from mtgscanner.collection import add_card
from mtgscanner.database import Card, Matcher, connect
from mtgscanner.sorting import card_price, choose_bin
from mtgscanner.vault_prices import VaultPrices
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
    add_card(path, db.get_card("id1"), foil=True, bin_label="$1 - $10", price=(6.5, "Face to Face Games"))
    rows = list(csv.DictReader(path.open()))
    assert rows[0]["Name"] == "Card 1"
    assert rows[0]["Quantity"] == "1"
    assert rows[0]["Set code"] == "TST"
    assert rows[0]["Collector number"] == "1"
    assert rows[0]["Foil"] == "foil"
    assert rows[0]["Price CAD"] == "6.50"


# Made-up prices in the same shape Commander Vault saves them.
VAULT = VaultPrices({
    "date": "Oct 18, 2026",
    "prices": {
        "Card 0": {"f2f": [12.99, 1, 20.0], "401": [11.0, 1, None]},
        "Card 1": {"401": [0.35, 1, None], "hob": [0.25, 0, 0.5]},
    },
    "printings": {"Card 1|TST|1|0": [3.49, 1, "Hobbiesville"]},
})


def test_vault_exact_printing_wins(db):
    assert card_price(db.get_card("id1"), False, VAULT) == (3.49, "Hobbiesville")


def test_vault_face_to_face_then_cheapest_store(db):
    assert card_price(db.get_card("id0"), False, VAULT) == (12.99, "Face to Face Games")
    assert card_price(db.get_card("id0"), True, VAULT) == (20.0, "Face to Face Games")
    assert card_price(db.get_card("id1"), True, VAULT) == (0.5, "Hobbiesville")


def test_falls_back_to_scryfall_usd_in_cad(db):
    price, source = card_price(db.get_card("id2"), False, VAULT)
    assert price == round(25.00 * config.USD_TO_CAD, 2) and "Scryfall" in source


def test_bins_use_vault_prices(db):
    assert choose_bin(db.get_card("id0"), False, VAULT)[0] == 3  # $12.99 CAD, though Scryfall says $0.10 USD


def test_empty_database_still_runs(tmp_path):
    """A fresh install (the Docker image before a restore or build_db.py) starts and
    says "not recognized" instead of crashing."""
    from mtgscanner.recognize import identify, identify_crop

    matcher = Matcher(connect(tmp_path / "empty.db"))
    assert matcher.card_count == 0 and matcher.learned_count == 0
    assert identify(matcher, fake_card(1)) == (None, 256)
    m = identify_crop(matcher, fake_card(1))
    assert m.card is None and m.candidates == []
    hit = matcher.rank(fingerprint(fake_card(1)))
    assert hit.id == "" and hit.distance == 256
    assert matcher.search("Card") == []


def test_scanner_takes_it_easy_while_the_picture_stands_still(db, monkeypatch):
    """The same picture again and again is looked at only SCAN_IDLE_FPS times a second;
    a change brings the scanner back to every frame."""
    from app import Scanner
    monkeypatch.setattr(config, "SCAN_IDLE_FPS", 2)
    scanner = Scanner(db, None, source=None)
    frames = {"frame": np.full((200, 100, 3), 120, np.uint8)}

    class Source:
        def read(self):
            return frames["frame"]

    scanner.source = Source()
    looked = []
    monkeypatch.setattr(scanner, "process", lambda frame: looked.append(frame))
    for _ in range(5):
        scanner.turn()
    assert len(looked) == 1          # the first look, then nothing changed
    frames["frame"] = np.full((200, 100, 3), 200, np.uint8)
    scanner.turn()
    assert len(looked) == 2          # a change: looked at straight away
    big = np.full((1920, 1080, 3), 60, np.uint8)
    scanner._publish(big)
    assert scanner.jpeg is not None and scanner.jpeg_full is None       # a preview only...
    assert cv2.imdecode(np.frombuffer(scanner.jpeg, np.uint8), cv2.IMREAD_COLOR).shape[0] == config.STREAM_PREVIEW_PX
    scanner.full_viewers = 1
    scanner._publish(big)                                                # ...until someone streams ?full=1
    assert cv2.imdecode(np.frombuffer(scanner.jpeg_full, np.uint8), cv2.IMREAD_COLOR).shape[0] == 1920


def test_glare_is_painted_over_before_giving_up(db):
    """A foil's bright patches pull the fingerprint off its card; when nothing matches,
    the patches are painted over and the card looked up again (vision.tame_glare)."""
    from mtgscanner.recognize import identify
    from mtgscanner.vision import tame_glare
    rng = np.random.default_rng(3)
    found = {"tamed": 0}
    for seed in range(4):
        card = fake_card(seed)
        shiny = card.copy()
        for _ in range(3):
            centre = (int(rng.integers(60, CARD_W - 60)), int(rng.integers(60, CARD_H - 60)))
            axes = (int(rng.integers(60, 110)), int(rng.integers(30, 60)))
            cv2.ellipse(shiny, centre, axes, int(rng.integers(0, 180)), 0, 360, (255, 255, 255), -1)
        shiny = cv2.GaussianBlur(shiny, (9, 9), 0)
        assert tame_glare(shiny) is not None
        card_found, distance = identify(db, shiny)
        found["tamed"] += card_found is not None and card_found.id == f"id{seed}"
    assert found["tamed"] >= 3, found


def test_straighten_turns_a_tilted_card_into_an_upright_rectangle(db):
    """Straighten (Scan page) measures the card on the bed and warps the whole picture so
    that card shows square: the camera's small tilt and keystone undone (2026-11-07)."""
    from mtgscanner import view
    from mtgscanner.recognize import find_cards
    from mtgscanner.vision import _order_corners
    card = fake_card(1)
    src = np.float32([[0, 0], [CARD_W, 0], [CARD_W, CARD_H], [0, CARD_H]])
    # like the Pi camera: about 1° of tilt, the bottom edge 3 % wider than the top
    dst = np.float32([[300, 160], [640, 166], [650, 640], [282, 632]])
    table = np.full((800, 960, 3), 170, np.uint8)
    photo = cv2.warpPerspective(card, cv2.getPerspectiveTransform(src, dst), (960, 800),
                                dst=table, borderMode=cv2.BORDER_TRANSPARENT)
    setting = view.straighten_from(photo)
    assert setting is not None and setting["size"] == [960, 800]
    assert view.clean_straighten(setting) == setting
    straight = view.straighten(photo, setting)
    assert straight.shape == photo.shape
    quad = _order_corners(np.asarray(find_cards(straight)[0][0], np.float32).reshape(4, 2))
    xs, ys = quad[:, 0], quad[:, 1]
    assert abs(xs[0] - xs[3]) < 4 and abs(xs[1] - xs[2]) < 4      # upright sides
    assert abs(ys[0] - ys[1]) < 4 and abs(ys[2] - ys[3]) < 4      # level top and bottom
    w, h = xs[1] - xs[0], ys[3] - ys[0]
    assert abs(w / h - view.CARD_ASPECT) < 0.02
    # a picture of another size (a new crop) still gets a sensible warp, not an error
    assert view.straighten(cv2.resize(photo, (480, 400)), setting).shape == (400, 480, 3)
    assert view.straighten_from(np.full((400, 400, 3), 170, np.uint8)) is None    # no card
    # the same from corners given by hand (shares of the picture), for a card the
    # detector can't outline against a dark bed
    by_hand = view.straighten_from(photo, [[x / 960, y / 800] for x, y in dst])
    moved = [cv2.perspectiveTransform(dst.reshape(1, 4, 2), np.float32(x["m"]).reshape(3, 3)) for x in (by_hand, setting)]
    assert np.abs(moved[0] - moved[1]).max() < 2      # the corners land within 2 px of each other
    assert view.straighten_from(photo, [[0.1, 0.1], [0.2]]) is None


def test_straighten_setting_from_the_scan_page(db, monkeypatch, tmp_path):
    import app as app_module
    from app import Scanner, create_app
    monkeypatch.setattr(app_module, "SETTINGS_FILE", tmp_path / "app_settings.json")
    scanner = Scanner(db, None, source=None)
    client = create_app(scanner).test_client()
    r = client.post("/api/settings", json={"straighten": True})
    assert r.status_code == 400 and "picture" in r.get_json()["error"]
    scanner._last_view = np.full((400, 400, 3), 170, np.uint8)
    r = client.post("/api/settings", json={"straighten": True})
    assert r.status_code == 400 and "No card" in r.get_json()["error"]
    # a card turned 5° on the table: far more than the camera can be off, so refused
    scanner._last_view = photograph(fake_card(2))
    r = client.post("/api/settings", json={"straighten": True})
    assert r.status_code == 400 and "doesn't look right" in r.get_json()["error"]
    # a card as the Pi camera shows it: about 1° tilt and a little keystone
    src = np.float32([[0, 0], [CARD_W, 0], [CARD_W, CARD_H], [0, CARD_H]])
    dst = np.float32([[300, 160], [640, 166], [650, 640], [282, 632]])
    scanner._last_view = cv2.warpPerspective(fake_card(2), cv2.getPerspectiveTransform(src, dst), (960, 720),
                                             dst=np.full((720, 960, 3), 170, np.uint8), borderMode=cv2.BORDER_TRANSPARENT)
    s = client.post("/api/settings", json={"straighten": True}).get_json()
    assert s["view"]["straight"] is True and scanner.straight
    assert app_module.load_settings()["straight"]["size"] == [960, 720]
    fresh = Scanner(db, None, source=None)
    fresh.restore(app_module.load_settings())
    assert fresh.straight == scanner.straight          # kept for next time
    s = client.post("/api/settings", json={"straighten": [[0.2, 0.1], [0.8, 0.1], [0.82, 0.9], [0.18, 0.9]]}).get_json()
    assert s["view"]["straight"] is True
    s = client.post("/api/settings", json={"rotate": 90}).get_json()
    assert s["view"]["straight"] is False              # a new rotation needs a new straighten
    assert client.post("/api/settings", json={"straighten": False}).get_json()["view"]["straight"] is False


def _camera_quad(centre, turn_deg, size=400.0):
    """A card as the Pi camera shows it: 3 % squashed, bottom 1.5 % wider than the top,
    1° tilted, plus the card's own turn on the bed."""
    w, h = size * 63 / 88, size * 0.97
    q = np.float32([[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2 * 1.015, h / 2], [-w / 2 * 1.015, h / 2]])
    a = np.radians(1.0 + turn_deg)
    rot = np.float32([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    return q @ rot.T + np.float32(centre)


def test_auto_straighten_learns_the_camera_from_many_cards(monkeypatch):
    """Each sure card is a sample; the median of their shapes, with each card's own turn
    averaged out and a bad outline left out, straightens the picture (Nic: make the
    camera 100 % automatic, and perfect)."""
    from mtgscanner import auto_straighten, view
    rng = np.random.default_rng(5)
    auto = auto_straighten.AutoStraighten()
    size = (1080, 1600)
    turns = rng.normal(0, 1.2, 9)
    for i, turn in enumerate(turns):
        assert auto.add(_camera_quad((540 + rng.normal(0, 8), 900), turn), None, size)
        if i < 7:
            assert auto.proposal(None) is None          # not enough cards yet
    # an outline that caught a light bar: far off square, left out
    bad = _camera_quad((540, 900), 0)
    bad[1] += (60, -40)
    assert not auto.add(bad, None, size)
    assert not auto.add(_camera_quad((20, 900), 0), None, size)     # at the picture's edge
    setting = auto.proposal(None)
    assert setting is not None
    m = np.float32(setting["m"]).reshape(3, 3)
    straight = cv2.perspectiveTransform(_camera_quad((540, 900), 0).reshape(1, 4, 2), m).reshape(4, 2)
    left, right = straight[3] - straight[0], straight[2] - straight[1]
    top = straight[1] - straight[0]
    tilt = max(abs(np.degrees(np.arctan2(v[0], v[1]))) for v in (left, right))
    assert tilt < 0.6, tilt                                    # sides upright within 0.6°
    assert abs(np.degrees(np.arctan2(top[1], top[0]))) < 0.6
    width = (np.linalg.norm(top) + np.linalg.norm(straight[2] - straight[3])) / 2
    height = (np.linalg.norm(left) + np.linalg.norm(right)) / 2
    assert abs(width / height - view.CARD_ASPECT) < 0.01

    # the next samples come from the straightened picture: mapped back, they agree, so
    # nothing changes (the picture stays steady)
    for turn in rng.normal(0, 1.2, 5):
        q = cv2.perspectiveTransform(_camera_quad((540, 900), turn).reshape(1, 4, 2), m).reshape(4, 2)
        assert auto.add(q, setting, size)
    assert auto.proposal(setting) is None


def test_auto_straighten_refuses_a_correction_the_camera_cannot_need(monkeypatch):
    from mtgscanner import auto_straighten
    auto = auto_straighten.AutoStraighten()
    for _ in range(8):
        auto.add(_camera_quad((540, 900), 6.0), None, (1080, 1600))   # every card 7° off
    assert auto.proposal(None) is None and auto.last_refused["turn"] > 3


def test_auto_straighten_waits_for_the_bed_to_be_clear(db, monkeypatch, tmp_path):
    import app as app_module
    from app import Scanner
    from mtgscanner.tracking import Track
    monkeypatch.setattr(app_module, "SETTINGS_FILE", tmp_path / "app_settings.json")
    scanner = Scanner(db, None, source=None)

    class Source:
        def read(self):
            return np.full((300, 200, 3), 120, np.uint8)
    scanner.source = Source()
    monkeypatch.setattr(scanner, "process", lambda frame: None)
    new = {"m": [1.0, 0.01, 0, 0, 1.0, 0, 0, 0, 1.0], "size": [200, 300]}
    scanner._pending_straight = new
    scanner.tracks = [Track(id=1, number=1, corners=np.float32([[0, 0], [10, 0], [10, 10], [0, 10]]))]
    scanner.turn()
    assert scanner.straight is None                         # a card is being read: wait
    scanner.tracks = []
    scanner.turn()
    assert scanner.straight == new and app_module.load_settings()["straight"] == new


def test_auto_straighten_takes_one_sample_per_card(db, monkeypatch, tmp_path):
    """A card sitting on the bed is recognized over and over; it must count once, or one
    card (with its own skew) sets the whole picture (seen on the Pi, 2026-11-08)."""
    import app as app_module
    from types import SimpleNamespace
    from app import Scanner
    from mtgscanner.tracking import Track
    monkeypatch.setattr(app_module, "SETTINGS_FILE", tmp_path / "app_settings.json")
    scanner = Scanner(db, None, source=None)
    scanner.auto_straight = True
    monkeypatch.setattr(scanner, "_keep_scan", lambda *a, **k: None)
    frame = np.zeros((1600, 1080, 3), np.uint8)
    corners = _camera_quad((540, 900), 0)
    card = SimpleNamespace(id="x")
    result = SimpleNamespace(card=card, corners=corners, distance=5, margin=20,
                             confidence="sure", candidates=[])
    t = Track(id=1, number=1, corners=corners)
    for _ in range(6):
        try:
            scanner._update(t, [corners], result, frame)
        except Exception:
            pass                       # only the sampling matters here
    assert len(scanner._auto_straight.samples) == 1
