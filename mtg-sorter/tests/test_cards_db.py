"""The card database itself: the two-part fingerprint, older databases, and building it."""

import io
import threading
import time

import cv2
import numpy as np
from PIL import Image

import build_db
from mtgscanner import config, system
from mtgscanner.database import Matcher, connect
from mtgscanner.vision import FINGERPRINT_BYTES, fingerprint, fingerprint_pil
from test_scanner import fake_card
from test_system import client, data  # noqa: F401  (fixtures)
from test_scanner import db  # noqa: F401


def _insert(conn, i, fp, name=None):
    conn.execute("INSERT INTO cards VALUES (?, ?, 'tst', 'Test Set', ?, 'rare', '', 1.0, NULL, ?)",
                 (f"id{i}", name or f"Card {i}", str(i), fp))


def test_fingerprint_is_whole_card_then_art():
    card = fake_card(5)
    fp = fingerprint(card)
    assert len(fp) == FINGERPRINT_BYTES == 64
    rgb = Image.fromarray(cv2.cvtColor(card, cv2.COLOR_BGR2RGB))
    assert fingerprint_pil(rgb) == fp
    # A card whose art differs, with the same frame, differs mostly in the art half.
    other = card.copy()
    cv2.rectangle(other, (60, 100), (420, 360), (10, 200, 30), -1)
    fp2 = fingerprint(other)
    bits = lambda a, b: int(np.unpackbits(np.frombuffer(a, np.uint8) ^ np.frombuffer(b, np.uint8)).sum())
    assert bits(fp[32:], fp2[32:]) > bits(fp[:32], fp2[:32])


def test_older_whole_card_fingerprints_still_match(tmp_path):
    """A database from before the art fingerprint keeps working, mixed with new rows."""
    conn = connect(tmp_path / "cards.db")
    for i in range(4):
        fp = fingerprint(fake_card(i))
        _insert(conn, i, fp[:32] if i % 2 else fp)     # cards 1 and 3 have the old 32-byte one
    conn.commit()
    m = Matcher(conn)
    assert m.old_count == 2
    for i in range(4):
        hit = m.rank(fingerprint(fake_card(i)))
        assert hit.id == f"id{i}" and hit.distance == 0
    # and a learned scan (64 bytes) joins in without a reload
    m.add_learned("scan.jpg", "id1", fingerprint(fake_card(1)))
    assert m.rank(fingerprint(fake_card(1))).id == "id1"


def _scryfall_card(i, usd="1.00"):
    return {"id": f"id{i}", "name": f"Card {i}", "set": "tst", "set_name": "Test Set", "collector_number": str(i),
            "rarity": "rare", "colors": ["G"], "prices": {"usd": usd, "usd_foil": None},
            "image_uris": {"small": f"https://cards.scryfall.io/small/{i}.jpg"}}


def test_build_adds_new_cards_upgrades_old_ones_and_refreshes_prices(tmp_path, monkeypatch):
    path = tmp_path / "cards.db"
    conn = connect(path)
    _insert(conn, 0, fingerprint(fake_card(0)))           # up to date: only its price changes
    _insert(conn, 1, fingerprint(fake_card(1))[:32])      # older fingerprint: fetched again
    conn.commit()
    fetched = []

    def fake_fetch(url):
        fetched.append(url)
        i = int(url.rsplit("/", 1)[1].split(".")[0])
        buf = io.BytesIO()
        Image.fromarray(cv2.cvtColor(fake_card(i), cv2.COLOR_BGR2RGB)).save(buf, "JPEG")
        return fingerprint_pil(Image.open(buf))

    monkeypatch.setattr(build_db, "fetch_fingerprint", fake_fetch)
    source = [_scryfall_card(0, "9.99"), _scryfall_card(1), _scryfall_card(2),
              _scryfall_card(2),                                 # listed twice: counted once
              {**_scryfall_card(3), "digital": True}]          # digital-only cards are left out
    batches = []
    result = build_db.build(iter(source), path, progress=lambda s: None, on_batch=lambda: batches.append(1))
    assert result == {"added": 1, "upgraded": 1, "refreshed": 2, "skipped": 0, "total": 3, "backs": 0}
    assert sorted(u.rsplit("/", 1)[1] for u in fetched) == ["1.jpg", "2.jpg"]
    conn = connect(path)
    rows = dict(conn.execute("SELECT id, length(fingerprint) FROM cards").fetchall())
    assert rows == {"id0": 64, "id1": 64, "id2": 64}
    assert conn.execute("SELECT price_usd FROM cards WHERE id = 'id0'").fetchone()[0] == 9.99


def _double_faced(i: int) -> dict:
    card = _scryfall_card(i)
    del card["image_uris"]
    card["name"] = f"Card {i} // Back {i}"
    card["card_faces"] = [{"image_uris": {"small": f"https://cards.scryfall.io/small/{i}.jpg"}},
                          {"image_uris": {"small": f"https://cards.scryfall.io/small/{i + 50}.jpg"}}]
    return card


def test_double_faced_cards_read_on_either_face(tmp_path, monkeypatch):
    """A double-faced card's back gets its own fingerprint, so the card reads whichever
    face is up; a database built before that gets the backs on its next build."""
    path = tmp_path / "cards.db"
    conn = connect(path)
    _insert(conn, 4, fingerprint(fake_card(4)))   # in the database already, from before backs were read
    conn.commit()
    fetched = []

    def fake_fetch(url):
        fetched.append(url)
        i = int(url.rsplit("/", 1)[1].split(".")[0])
        return fingerprint(fake_card(i))

    monkeypatch.setattr(build_db, "fetch_fingerprint", fake_fetch)
    result = build_db.build(iter([_double_faced(3), {**_double_faced(4)}]), path, progress=lambda s: None)
    assert result["added"] == 1 and result["backs"] == 2
    assert sorted(u.rsplit("/", 1)[1] for u in fetched) == ["3.jpg", "53.jpg", "54.jpg"]
    matcher = Matcher(connect(path))
    assert matcher.card_count == 2 and matcher.back_count == 2
    hit = matcher.rank(fingerprint(fake_card(53)))        # the back of card 3, face up
    assert hit.id == "id3" and hit.distance == 0
    front, back = matcher.face_distances("id3", fingerprint(fake_card(53)))
    assert back == 0 and front > 0
    assert matcher.distance_to("id3", fingerprint(fake_card(53))) == 0
    # Built again: nothing more to fetch.
    fetched.clear()
    build_db.build(iter([_double_faced(3), _double_faced(4)]), path, progress=lambda s: None)
    assert fetched == []


def test_search_waits_out_too_many_requests(monkeypatch):
    calls = []

    class Resp:
        def __init__(self, code, body=None):
            self.status_code, self._body = code, body

        def json(self):
            return self._body

        def raise_for_status(self):
            assert self.status_code < 400

    answers = [Resp(429), Resp(200, {"data": [{"id": "a"}], "next_page": None})]
    monkeypatch.setattr(build_db.requests, "get", lambda url, **kw: calls.append(url) or answers.pop(0))
    monkeypatch.setattr(build_db.time, "sleep", lambda s: None)
    monkeypatch.setattr(build_db, "SEARCH_THROTTLE", build_db.Throttle(1000))
    assert [c["id"] for c in build_db.cards_from_sets(["tst"])] == ["a"]
    assert len(calls) == 2


def test_maintenance_downloads_every_card_and_reloads(client, monkeypatch):  # noqa: F811
    """The check-up says the database is too small, and its button builds it in the background."""
    checks = {c["id"]: c for c in client.get("/api/system").get_json()["checks"]}
    assert checks["cards"]["state"] == "warn" and checks["cards"]["action"] == "cards_build"
    release = threading.Event()

    def fake_bulk(say):
        say("Downloading the list of every card")
        release.wait(5)
        return iter([])

    monkeypatch.setattr(build_db, "cards_from_bulk", fake_bulk)
    monkeypatch.setattr(build_db, "build", lambda source, **kw: {"added": 5, "upgraded": 0, "refreshed": 4,
                                                                  "skipped": 0, "total": 9})
    r = client.post("/api/system/cards", json={})
    assert r.status_code == 200 and "Downloading every card" in r.get_json()["message"]
    assert client.get("/api/system/cards").get_json()["running"]
    assert "already" in client.post("/api/system/cards", json={}).get_json()["message"]
    release.set()
    for _ in range(100):
        state = client.get("/api/system/cards").get_json()
        if not state["running"]:
            break
        time.sleep(0.05)
    assert state["message"].startswith("Done. 9 cards") and not state["error"]
