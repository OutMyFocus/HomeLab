"""Offline tests for the last few percent: an outline nudged onto the card's edge, an
outline that leaves the picture, and telling a card from its look-alike printings."""

import time

import cv2
import numpy as np
import pytest

from mtgscanner import printings, recognize
from mtgscanner.database import Hit, Matcher, connect
from mtgscanner.printings import StockPictures
from mtgscanner.recognize import identify_outlines, refine_outline
from mtgscanner.tracking import Track
from mtgscanner.vision import fingerprint
from tests.test_scanner import fake_card, photograph

PHOTO_CORNERS = np.float32([[220, 90], [560, 120], [530, 590], [190, 560]])   # where photograph() puts the card


def printing(symbol: int) -> np.ndarray:
    """One card in two printings: the same busy picture, with another set symbol at the
    right of the type line (0: a disc, 1: a cross). Too small a difference for the
    fingerprint, as with a real card and its reprint."""
    card = fake_card(7)
    rng = np.random.default_rng(5)
    for _ in range(60):
        p = tuple(int(x) for x in rng.integers(30, 450, 2))
        cv2.circle(card, p, int(rng.integers(5, 25)), tuple(int(x) for x in rng.integers(0, 255, 3)), -1)
    cv2.rectangle(card, (400, 365), (450, 395), (120, 120, 120), -1)
    if symbol == 0:
        cv2.circle(card, (425, 380), 10, (200, 200, 200), -1)
    else:
        cv2.line(card, (415, 370), (435, 390), (200, 200, 200), 5)
        cv2.line(card, (415, 390), (435, 370), (200, 200, 200), 5)
    return card


STOCK = {"first": printing(0), "reprint": printing(1), "other": fake_card(1)}


@pytest.fixture
def db(tmp_path):
    conn = connect(tmp_path / "cards.db")
    for card_id, name, set_code in (("first", "Twin", "tst"), ("reprint", "Twin", "rep"), ("other", "Loner", "tst")):
        conn.execute("INSERT INTO cards VALUES (?, ?, ?, 'Test Set', '1', 'rare', '', 1.0, NULL, ?)",
                     (card_id, name, set_code, fingerprint(STOCK[card_id])))
    conn.commit()
    return Matcher(conn)


def stock_pictures(tmp_path, fetched: list | None = None, delay: float = 0.0) -> StockPictures:
    def fetch(card_id):
        time.sleep(delay)
        if fetched is not None:
            fetched.append(card_id)
        return cv2.imencode(".jpg", STOCK[card_id])[1].tobytes()
    return StockPictures(tmp_path / "stock", fetch)


def test_the_fingerprint_cannot_tell_the_printings_apart(db):
    """The premise: both printings sit within a few bits of a photo of either."""
    fp = fingerprint(printing(1))
    assert abs(db.distance_to("first", fp) - db.distance_to("reprint", fp)) <= printings.WINDOW
    assert db.distance_to("nobody", fp) is None
    alike = db.lookalikes("first", fp, printings.WINDOW, printings.MOST)
    assert [card_id for card_id, _ in alike] == ["first", "reprint"]      # the card asked about comes first
    assert db.lookalikes("other", fingerprint(STOCK["other"]), printings.WINDOW, printings.MOST) == []


@pytest.mark.parametrize("which, card_id", [(0, "first"), (1, "reprint")])
@pytest.mark.parametrize("upside_down", [False, True])
def test_the_details_choose_the_printing(db, tmp_path, which, card_id, upside_down):
    db.pictures = stock_pictures(tmp_path)
    m = identify_outlines(db, photograph(printing(which), rotate180=upside_down), [PHOTO_CORNERS])
    assert m.card.id == card_id and m.printing_lead > 0
    assert set(m.lookalikes) == {"first", "reprint"}


def test_without_stock_pictures_the_fingerprint_chooses(db, tmp_path):
    photo = photograph(printing(1))
    m = identify_outlines(db, photo, [PHOTO_CORNERS])                  # --offline: no pictures at all
    assert m.card.name == "Twin" and m.printing_lead == 0 and len(m.lookalikes) == 2

    def no_internet(card_id):
        raise OSError("no route to host")
    db.pictures = StockPictures(tmp_path / "stock", no_internet)
    m = identify_outlines(db, photo, [PHOTO_CORNERS])
    assert m.card.name == "Twin" and m.printing_lead == 0


def test_a_card_with_one_printing_fetches_nothing(db, tmp_path):
    fetched = []
    db.pictures = stock_pictures(tmp_path, fetched)
    m = identify_outlines(db, photograph(STOCK["other"]), [PHOTO_CORNERS])
    assert m.card.id == "other" and m.lookalikes == () and fetched == []


def test_the_scan_bed_way_leaves_printings_alone(db, tmp_path):
    fetched = []
    db.pictures = stock_pictures(tmp_path, fetched)
    m = identify_outlines(db, photograph(printing(1)), [PHOTO_CORNERS], refine=False)
    assert m.card.name == "Twin" and m.lookalikes == () and fetched == []


def test_stock_pictures_are_fetched_once_and_kept(tmp_path):
    fetched = []
    pictures = stock_pictures(tmp_path, fetched)
    assert set(pictures.get_all(["first", "reprint"])) == {"first", "reprint"}
    assert set(pictures.get_all(["first", "reprint"])) == {"first", "reprint"}
    assert sorted(fetched) == ["first", "reprint"]
    again = stock_pictures(tmp_path, fetched)                           # after a restart: from the folder
    assert again.get("first") is not None and sorted(fetched) == ["first", "reprint"]


def test_the_live_camera_does_not_wait_for_slow_pictures(db, tmp_path):
    """Pictures that take their time don't hold the camera up: the fingerprint's choice
    stands for this look, and they're there for the next one."""
    db.pictures = stock_pictures(tmp_path, delay=0.4)
    photo = photograph(printing(1))
    start = time.perf_counter()
    m = identify_outlines(db, photo, [PHOTO_CORNERS], wait=0.05)
    assert time.perf_counter() - start < 0.3
    assert m.card.name == "Twin" and m.printing_lead == 0
    deadline = time.time() + 5
    while len(db.pictures.get_all(["first", "reprint"], wait=0)) < 2 and time.time() < deadline:
        time.sleep(0.05)
    m = identify_outlines(db, photo, [PHOTO_CORNERS], wait=0.05)
    assert m.card.id == "reprint" and m.printing_lead > 0


def test_a_picture_that_failed_is_not_asked_for_again_right_away(tmp_path):
    asked = []

    def fetch(card_id):
        asked.append(card_id)
        return None
    pictures = StockPictures(tmp_path / "stock", fetch)
    assert pictures.get("first") is None and pictures.get("first") is None
    assert asked == ["first"]


def _look(card_id: str, lead: float):
    from types import SimpleNamespace
    return SimpleNamespace(card=SimpleNamespace(id=card_id, name="Twin"), corners=PHOTO_CORNERS, distance=20,
                           margin=30, confidence="sure", candidates=[], lookalikes=("first", "reprint"),
                           printing_lead=lead)


def test_a_card_keeps_its_printing_between_looks(db, monkeypatch, tmp_path):
    """A card used to flip between look-alike printings from one look to the next, and
    Auto saved it once for each. Now the clearest look keeps its answer."""
    import app as app_module
    from app import Scanner
    monkeypatch.setattr(app_module, "SETTINGS_FILE", tmp_path / "app_settings.json")
    scanner = Scanner(db, None, source=None)
    monkeypatch.setattr(scanner, "_keep_scan", lambda *a, **k: None)
    frame = np.zeros((720, 960, 3), np.uint8)
    t = Track(id=1, number=1, corners=PHOTO_CORNERS)
    scanner._update(t, [PHOTO_CORNERS], _look("first", 0.05), frame)
    assert t.card.id == "first"
    scanner._update(t, [PHOTO_CORNERS], _look("reprint", 0.02), frame)      # a vaguer look says the other
    assert t.card.id == "first" and t.status == "locked" and t.streak == 2
    scanner._update(t, [PHOTO_CORNERS], _look("reprint", 0.20), frame)      # a clearer look: it changes
    assert t.card.id == "reprint" and not t.saved
    t.saved = True
    scanner._update(t, [PHOTO_CORNERS], _look("first", 0.50), frame)        # saved: it is what was saved
    assert t.card.id == "reprint" and t.saved


def test_another_card_still_replaces_the_one_before(db, monkeypatch, tmp_path):
    """Only look-alike printings are held on to: a different card takes over as before."""
    import app as app_module
    from app import Scanner
    monkeypatch.setattr(app_module, "SETTINGS_FILE", tmp_path / "app_settings.json")
    scanner = Scanner(db, None, source=None)
    monkeypatch.setattr(scanner, "_keep_scan", lambda *a, **k: None)
    frame = np.zeros((720, 960, 3), np.uint8)
    t = Track(id=1, number=1, corners=PHOTO_CORNERS)
    scanner._update(t, [PHOTO_CORNERS], _look("first", 0.05), frame)
    t.saved = True
    other = _look("other", 0.0)
    other.lookalikes = ()
    scanner._update(t, [PHOTO_CORNERS], other, frame)
    assert t.card.id == "other" and not t.saved


def test_the_scan_bed_gets_the_printing_check_but_no_nudging(db, monkeypatch, tmp_path):
    """"Whole cards only" (the machine's bed) gets no nudged outlines before a card reads
    (measured on phone pictures only), but it does get the printing check: the price
    belongs to the printing."""
    import app as app_module
    from app import Scanner
    monkeypatch.setattr(app_module, "SETTINGS_FILE", tmp_path / "app_settings.json")
    asked = []
    real = app_module.identify_outlines

    def spy(matcher, frame, outlines, refine=True, **kw):
        if not isinstance(outlines, app_module.FilledFrame):
            asked.append((refine, kw.get("printing")))
        return real(matcher, frame, outlines, refine=refine, **kw)
    monkeypatch.setattr(app_module, "identify_outlines", spy)
    photo = photograph(printing(0))
    phone = Scanner(db, None, source=None)
    phone.process(photo)
    bed = Scanner(db, None, source=None)
    bed.min_card = 0.05
    bed.process(photo)
    assert asked == [(True, True), (False, True)]
    assert phone.tracks[0].card.name == bed.tracks[0].card.name == "Twin"


def test_an_outline_a_little_off_is_nudged_onto_the_card(db):
    """An outline that cuts a strip off one side and takes in a strip of table on another
    reads further from the card than it should: nudging the sides brings it back."""
    photo = photograph(STOCK["other"])
    off = recognize._nudge(recognize._nudge(PHOTO_CORNERS, 3, -0.05), 0, 0.04)
    before = db.distance_to("other", fingerprint(recognize.warp_card(photo, off)))
    better = refine_outline(db, photo, off, "other")
    assert better is not None
    after = db.distance_to("other", fingerprint(recognize.warp_card(photo, better)))
    assert after < before
    assert np.abs(better - PHOTO_CORNERS).max() < np.abs(off - PHOTO_CORNERS).max()
    assert refine_outline(db, photo, PHOTO_CORNERS, "nobody") is None       # no such card: nothing to aim for


def test_a_nudged_outline_only_counts_when_it_is_sure(db, monkeypatch):
    """Nudging toward a card flatters it, so a nudged outline that still isn't a sure
    match changes nothing."""
    photo = photograph(STOCK["other"])
    monkeypatch.setattr(recognize, "_rank_both_ways", lambda matcher, img: Hit("other", 70, 6))   # three outline sizes
    hits = iter([Hit("other", 70, 6), Hit("other", 62, 6)])       # the closest one looked at again, then the nudged one
    monkeypatch.setattr(recognize, "_rank", lambda matcher, img, plain=None: next(hits))
    monkeypatch.setattr(recognize, "refine_outline", lambda *a: PHOTO_CORNERS + 3)
    m = identify_outlines(db, photo, [PHOTO_CORNERS])
    assert m.distance == 70 and m.confidence == "likely"
    hits = iter([Hit("other", 70, 6), Hit("other", 30, 40)])
    m = identify_outlines(db, photo, [PHOTO_CORNERS])
    assert m.distance == 30 and m.confidence == "sure" and np.allclose(m.corners, PHOTO_CORNERS + 3)


def test_an_outline_that_leaves_the_picture_has_to_be_sure(db, monkeypatch):
    """What's outside the picture comes out black, which looks a little like any dark
    card: such an outline is only offered as a guess unless the match is sure."""
    photo = photograph(STOCK["other"])
    outside = PHOTO_CORNERS + np.float32([500, 0])           # its right side is past the picture's edge
    monkeypatch.setattr(recognize, "refine_outline", lambda *a: None)
    for look in ("_rank", "_rank_both_ways"):
        monkeypatch.setattr(recognize, look, lambda matcher, img, plain=None: Hit("other", 70, 6))
    m = identify_outlines(db, photo, [outside])
    assert m.card is None and m.candidates[0][0].id == "other"
    assert identify_outlines(db, photo, [PHOTO_CORNERS]).card.id == "other"      # inside the picture: as before
    for look in ("_rank", "_rank_both_ways"):
        monkeypatch.setattr(recognize, look, lambda matcher, img, plain=None: Hit("other", 30, 40))
    assert identify_outlines(db, photo, [outside]).card.id == "other"            # sure: it counts


def _camera(which: int, seed: int) -> np.ndarray:
    """A photo of one printing under a light that leaves the same X-shaped glint over
    the set symbol every time: next to the stock pictures, a disc with that glint looks
    more like the cross."""
    card = printing(which)
    for a, b in (((410, 368), (440, 393)), ((410, 393), (440, 368))):
        cv2.line(card, a, b, (235, 235, 235), 3)
    photo = photograph(card)
    noise = np.random.default_rng(seed).normal(0, 5, photo.shape)
    return np.clip(photo + noise, 0, 255).astype(np.uint8)


def _teach(db, monkeypatch, tmp_path, photo, card_id: str, upside_down: bool = False):
    """Keep learning: the scan is kept in data/captures and learned as card_id."""
    from mtgscanner import config
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")
    crop = recognize.warp_card(photo, PHOTO_CORNERS)
    if upside_down:                                      # kept the way the card lay
        crop = cv2.rotate(crop, cv2.ROTATE_180)
    (tmp_path / "captures" / "day").mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(tmp_path / "captures" / "day" / f"{card_id}_card.jpg"), crop)
    db.add_learned(f"day/{card_id}_card.jpg", card_id, fingerprint(crop))


@pytest.mark.parametrize("upside_down", [False, True])
def test_a_taught_printing_is_how_your_camera_sees_it(db, tmp_path, monkeypatch, upside_down):
    """The stock pictures can pick the wrong printing for your camera (here a glint over
    the set symbol). Once you have taught it the right one, your own scan of it counts
    too: copies of that printing read right, and the other printing still reads as itself."""
    db.pictures = stock_pictures(tmp_path)
    assert identify_outlines(db, _camera(0, 1), [PHOTO_CORNERS]).card.id == "reprint"     # wrong, before teaching
    _teach(db, monkeypatch, tmp_path, _camera(0, 2), "first", upside_down)
    for seed in (3, 4):
        assert identify_outlines(db, _camera(0, seed), [PHOTO_CORNERS]).card.id == "first"
        assert identify_outlines(db, _camera(1, seed), [PHOTO_CORNERS]).card.id == "reprint"


def test_a_taught_printing_does_not_take_over_the_other_one(db, tmp_path, monkeypatch):
    """With a printing taught, the stock pictures still choose right where they did."""
    db.pictures = stock_pictures(tmp_path)
    _teach(db, monkeypatch, tmp_path, photograph(printing(0)), "first")
    for which, card_id in ((0, "first"), (1, "reprint")):
        m = identify_outlines(db, photograph(printing(which)), [PHOTO_CORNERS])
        assert m.card.id == card_id and m.printing_lead > 0


def test_a_stock_picture_cut_short_is_fetched_again(tmp_path):
    """A power cut while a stock picture was being kept left half of it, grey below the
    cut, and it was used for ever. Now it's fetched again, and kept whole."""
    fetched = []
    pictures = stock_pictures(tmp_path, fetched)
    whole = cv2.imencode(".jpg", STOCK["first"])[1].tobytes()
    (tmp_path / "stock").mkdir()
    (tmp_path / "stock" / "first.jpg").write_bytes(whole[:len(whole) // 3])
    assert pictures.get("first") is not None and fetched == ["first"]
    assert (tmp_path / "stock" / "first.jpg").read_bytes() == whole
    assert list((tmp_path / "stock").glob("*.tmp")) == []
    again = stock_pictures(tmp_path, fetched)          # after a restart: the kept one is whole
    assert again.get("first") is not None and fetched == ["first"]
