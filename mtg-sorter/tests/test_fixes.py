"""Edge cases found during the test pass: outline accuracy, thresholds, lookups, CSV and API quirks."""

import csv
import io

import cv2
import numpy as np
import pytest

from app import DemoSource, Scanner, card_info, create_app
from mtgscanner import config
from mtgscanner.collection import COLUMNS, add_card, remove_last
from mtgscanner.database import Matcher
from mtgscanner.live import Live
from mtgscanner.recognize import identify_frame
from mtgscanner.sorting import card_price
from mtgscanner.vault_prices import VaultPrices
from mtgscanner.vision import CARD_H, CARD_W, MIN_CARD_AREA, find_card, fingerprint
from test_live import fake_fetch, scryfall_card
from test_scanner import db, fake_card, photograph  # noqa: F401  (db is a fixture)


def place(card, dst, size=(1280, 720), bg=235):
    """Photograph a card at the given 4 corners on a plain table."""
    w, h = size
    src = np.float32([[0, 0], [CARD_W, 0], [CARD_W, CARD_H], [0, CARD_H]])
    m = cv2.getPerspectiveTransform(src, np.float32(dst))
    table = np.full((h, w, 3), bg, np.uint8)
    photo = cv2.warpPerspective(card, m, (w, h), dst=table, borderMode=cv2.BORDER_TRANSPARENT)
    photo = cv2.GaussianBlur(photo, (3, 3), 0) + np.random.default_rng(0).normal(0, 5, photo.shape)
    return np.clip(photo, 0, 255).astype(np.uint8)


def rounded(card, radius=24):
    """Real cards have rounded corners; white shows through them on a white table."""
    out = card.copy()
    mask = np.zeros(card.shape[:2], np.uint8)
    cv2.rectangle(mask, (radius, 0), (CARD_W - radius, CARD_H), 255, -1)
    cv2.rectangle(mask, (0, radius), (CARD_W, CARD_H - radius), 255, -1)
    for cx, cy in [(radius, radius), (CARD_W - radius, radius), (radius, CARD_H - radius), (CARD_W - radius, CARD_H - radius)]:
        cv2.circle(mask, (cx, cy), radius, 255, -1)
    out[mask == 0] = 235
    return out


# --- Finding the card ---------------------------------------------------------------

def test_outline_lands_on_the_card_edge_despite_rounded_corners(db):  # noqa: F811
    """The rough outline cuts across rounded corners; fitting the sides fixes it."""
    truth = [[420, 60], [820, 90], [790, 660], [390, 630]]
    corners, _ = find_card(place(rounded(fake_card(1)), truth))
    assert np.abs(corners - np.float32(truth)).max() < 4, corners


@pytest.mark.parametrize("bg", [245, 170, 25])
def test_white_gray_and_black_tables(db, bg):  # noqa: F811
    _, card, dist = identify_frame(db, place(rounded(fake_card(2)), [[420, 60], [820, 90], [790, 660], [390, 630]], bg=bg))
    assert card is not None and card.id == "id2" and dist <= config.GOOD_MATCH_DISTANCE, dist


def test_small_card_far_from_the_camera(db):  # noqa: F811
    """A card covering 3% of a 1280x720 frame (about 110 pixels wide) is still found."""
    _, card, _ = identify_frame(db, place(fake_card(3), [[580, 270], [690, 270], [690, 420], [580, 420]]))
    assert card is not None and card.id == "id3"
    assert MIN_CARD_AREA <= 0.03


def test_sideways_card(db):  # noqa: F811
    for rotation in (cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE):
        turned = cv2.rotate(fake_card(1), rotation)
        src = np.float32([[0, 0], [CARD_H, 0], [CARD_H, CARD_W], [0, CARD_W]])
        m = cv2.getPerspectiveTransform(src, np.float32([[150, 200], [760, 160], [790, 600], [180, 640]]))
        photo = cv2.warpPerspective(turned, m, (960, 720), dst=np.full((720, 960, 3), 170, np.uint8), borderMode=cv2.BORDER_TRANSPARENT)
        _, card, _ = identify_frame(db, photo)
        assert card is not None and card.id == "id1"


def test_keystone_from_a_phone_held_at_an_angle(db):  # noqa: F811
    _, card, _ = identify_frame(db, place(fake_card(0), [[360, 200], [600, 200], [680, 600], [280, 600]], size=(960, 720)))
    assert card is not None and card.id == "id0"


def test_two_cards_in_one_photo_picks_one_of_them(db):  # noqa: F811
    photo = place(fake_card(0), [[100, 60], [480, 70], [470, 620], [90, 610]])
    photo = cv2.warpPerspective(fake_card(1), cv2.getPerspectiveTransform(
        np.float32([[0, 0], [CARD_W, 0], [CARD_W, CARD_H], [0, CARD_H]]),
        np.float32([[700, 60], [1080, 70], [1070, 620], [690, 610]])), (1280, 720), dst=photo, borderMode=cv2.BORDER_TRANSPARENT)
    _, card, _ = identify_frame(db, photo)
    assert card is not None and card.id in ("id0", "id1")


@pytest.mark.parametrize("shade", [250, 128, 20])
def test_plain_rectangles_are_not_cards(db, shade):  # noqa: F811
    """A sheet of paper, a phone or a sleeve back is card-shaped but matches nothing."""
    blank = np.full((CARD_H, CARD_W, 3), shade, np.uint8)
    _, card, _ = identify_frame(db, place(blank, [[420, 60], [820, 90], [790, 660], [390, 630]], bg=170))
    assert card is None


def test_empty_and_odd_frames_do_not_crash(db):  # noqa: F811
    for frame in (np.zeros((8, 8, 3), np.uint8), np.full((720, 1280, 3), 255, np.uint8),
                  np.random.default_rng(0).integers(0, 255, (480, 640, 3)).astype(np.uint8)):
        corners, card, _ = identify_frame(db, frame)
        assert card is None


def test_thresholds_leave_room_between_right_and_wrong():
    """Scans of the right card land under about 20 bits; unrelated images about 75+."""
    assert config.GOOD_MATCH_DISTANCE < config.MAX_MATCH_DISTANCE < 70


# --- Same art in several printings ---------------------------------------------------

def test_lookalikes_lists_printings_with_the_same_art(db):  # noqa: F811
    db.conn.execute("INSERT INTO cards VALUES ('id1b', 'Card 1', 'rep', 'Reprint', '9', 'rare', '', 1.0, NULL, ?)",
                    (fingerprint(fake_card(1)),))
    db.conn.commit()
    twin = Matcher(db.conn)
    assert twin.lookalikes("id1") == ["id1b"] and twin.lookalikes("id1b") == ["id1"]
    assert twin.lookalikes("id2") == [] and twin.lookalikes("nope") == []
    info = card_info(twin.get_card("id1"), False, None, None, 4, twin)
    assert info["lookalikes"] == 1
    assert card_info(twin.get_card("id1"), False, None, None, None, twin)["lookalikes"] == 0   # picked by hand


# --- Live lookups -------------------------------------------------------------------

def test_failed_lookup_is_retried_but_does_not_block_auto_save(monkeypatch):
    calls = []
    answers = {"n": 0}

    def fetch(url):
        calls.append(url)
        if answers["n"] == 0:
            raise ConnectionError("down")
        return scryfall_card(1, usd="8.00")

    lv = Live(fetch)
    assert lv.card_json("id1") is None and lv.ready("id1")      # failed, but a lookup has finished
    assert lv.card_json("id1") is None and len(calls) == 1      # not retried straight away
    answers["n"] = 1
    monkeypatch.setattr("mtgscanner.live.time.time", lambda: 10**10)   # a minute later
    assert lv.card_json("id1")["prices"]["usd"] == "8.00" and len(calls) == 2


def test_stale_price_is_kept_when_a_refresh_fails(monkeypatch):
    good = {"ok": True}
    def fetch(url):
        if good["ok"]:
            return scryfall_card(1, usd="8.00")
        raise ConnectionError("down")
    lv = Live(fetch)
    lv.card_json("id1")
    good["ok"] = False
    monkeypatch.setattr("mtgscanner.live.time.time", lambda: 10**10)   # hours later: cache expired
    assert lv.card_json("id1")["prices"]["usd"] == "8.00"
    assert lv.prices("id1")["usd"] == "8.00"


def test_bad_rate_answers_fall_back_to_config():
    for answer in ({}, {"observations": []}, {"observations": [{"FXUSDCAD": {"v": "abc"}}]}, None):
        lv = Live(fake_fetch({"bankofcanada": answer}) if answer is not None else fake_fetch({}))
        lv.load_rate()
        assert lv.usd_to_cad() == (config.USD_TO_CAD, "fixed rate in config.py")


# --- Vault prices -------------------------------------------------------------------

def test_vault_rows_with_missing_prices(db):  # noqa: F811
    vault = VaultPrices({"prices": {"Card 1": {"f2f": [None, 1], "401": ["2.50", 1, None]}},
                         "printings": {"Card 2|TST|2|0": [None, 0, "Hobbiesville"], "Card 3|TST|3|0": [1.25]}})
    assert card_price(db.get_card("id1"), False, vault) == (2.5, "401 Games")     # f2f has no price, 401's is a string
    assert card_price(db.get_card("id1"), True, vault)[1].startswith("Scryfall")  # no foil prices at all
    assert card_price(db.get_card("id2"), False, vault)[1].startswith("Scryfall")  # printing row without a price
    assert card_price(db.get_card("id3"), False, vault) == (1.25, "Commander Vault")


# --- Collection CSV -----------------------------------------------------------------

def test_emptied_csv_gets_its_header_back(db, tmp_path):  # noqa: F811
    path = tmp_path / "collection.csv"
    path.write_text("")
    add_card(path, db.get_card("id1"), False, "Bulk", (0.1, "Scryfall"), 1)
    rows = list(csv.DictReader(path.open()))
    assert [r["Name"] for r in rows] == ["Card 1"] and list(rows[0]) == COLUMNS


def test_undo_skips_blank_lines(db, tmp_path):  # noqa: F811
    path = tmp_path / "collection.csv"
    add_card(path, db.get_card("id1"), False, "Bulk", (0.1, "Scryfall"), 1)
    path.write_text(path.read_text() + "\n\n")
    assert remove_last(path)
    assert list(csv.DictReader(path.open())) == []
    assert not remove_last(path)


# --- The app --------------------------------------------------------------------------

@pytest.fixture
def scanner(db, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    return Scanner(db, None, source=None)


def test_card_picked_by_name_survives_an_empty_camera(scanner):
    """"Find a card by name" with nothing under the camera used to be wiped on the next frame."""
    client = create_app(scanner).test_client()
    for _ in range(20):
        scanner._update(None, None, None)
    assert client.post("/api/choose", json={"id": "id1"}).get_json()["card"]["name"] == "Card 1"
    for _ in range(20):
        scanner._update(None, None, None)
    assert client.get("/api/state").get_json()["card"]["name"] == "Card 1"
    # Put a card down and take it away: now the pick is cleared, like any other card.
    corners = np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])
    for _ in range(config.STABLE_FRAMES):
        scanner._update(corners, scanner.matcher.get_card("id2"), 2)
    assert client.get("/api/state").get_json()["card"]["name"] == "Card 2"
    for _ in range(20):
        scanner._update(None, None, None)
    assert client.get("/api/state").get_json()["card"] is None


def test_saving_then_removing_then_the_same_card_again(scanner):
    """Scanning the same card twice on purpose (two copies) saves it twice."""
    client = create_app(scanner).test_client()
    corners = np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])
    card = scanner.matcher.get_card("id1")
    scanner.auto = True
    for _ in range(config.STABLE_FRAMES + 2):
        scanner._update(corners, card, 2)
    assert client.get("/api/state").get_json()["totals"]["count"] == 1
    for _ in range(20):
        scanner._update(None, None, None)
    for _ in range(config.STABLE_FRAMES + 2):
        scanner._update(corners, card, 2)
    assert client.get("/api/state").get_json()["totals"]["count"] == 2


def test_bad_request_bodies(scanner):
    client = create_app(scanner).test_client()
    assert client.post("/api/settings", data="not json", content_type="application/json").status_code == 200
    assert client.post("/api/settings", json=["foil"]).status_code == 200
    assert client.post("/api/add", json={}).status_code == 404
    assert client.post("/api/add", data="", content_type="application/json").status_code == 404
    assert client.get("/api/card?id=").status_code == 404
    assert client.get("/api/search?q=").get_json() == []
    assert client.get("/api/printings?name=").get_json() == []
    assert client.get("/api/printings?name=Card 1").get_json()[0]["id"] == "id1"


def test_photos_that_are_not_images(scanner):
    client = create_app(scanner).test_client()
    files = [(io.BytesIO(b""), "empty.jpg"), (io.BytesIO(b"not an image"), "IMG_0001.HEIC"),
             (io.BytesIO(cv2.imencode(".png", photograph(fake_card(1)))[1].tobytes()), "card.png")]
    res = client.post("/api/photos", data={"photos": files}, content_type="multipart/form-data").get_json()
    assert "Couldn't open" in res[0]["error"] and "HEIC" in res[1]["error"]
    assert res[2]["card"]["id"] == "id1"
    assert client.post("/api/photos", data={}, content_type="multipart/form-data").get_json() == []


def test_camera_thread_survives_a_bad_frame(scanner, caplog):
    class Flaky:
        n = 0
        def read(self):
            self.n += 1
            return np.zeros((4,), np.uint8) if self.n == 1 else photograph(fake_card(1))
    scanner.source = Flaky()
    scanner.step()   # a 1-D "frame": not a picture at all, raised inside OpenCV before this fix
    scanner.step()
    assert scanner.jpeg is not None


def test_camera_frame_failures_are_logged_not_fatal(scanner, caplog):
    import threading

    def explode():
        raise RuntimeError("camera unplugged")
    scanner.step = explode
    t = threading.Thread(target=scanner.run, daemon=True)
    t.start()
    t.join(0.5)
    assert t.is_alive() and "Skipping a camera frame" in caplog.text


def test_demo_source_needs_a_folder(tmp_path):
    with pytest.raises(SystemExit, match="folder"):
        DemoSource(str(tmp_path / "missing"))
    with pytest.raises(SystemExit, match="No photos"):
        DemoSource(str(tmp_path))
    cv2.imwrite(str(tmp_path / "a.jpg"), photograph(fake_card(0)))
    assert DemoSource(str(tmp_path)).read().shape == (720, 960, 3)


def test_state_reports_prices_source_and_db_size(scanner):
    client = create_app(scanner).test_client()
    s = client.get("/api/state").get_json()
    assert s["db_count"] == 4 and "database" in s["prices"] and s["card"] is None


def test_download_csv(scanner):
    client = create_app(scanner).test_client()
    assert client.get("/api/collection.csv").status_code == 404
    client.post("/api/add", json={"id": "id1"})
    res = client.get("/api/collection.csv")
    assert res.status_code == 200 and b"Card 1" in res.data
