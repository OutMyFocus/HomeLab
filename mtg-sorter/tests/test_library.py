"""The Collection page's API, live prices and the printing picker (Scryfall faked, no internet)."""

import csv

import pytest

from app import Scanner, create_app
from mtgscanner import config, library
from mtgscanner.database import Card
from mtgscanner.live import Live
from mtgscanner.sorting import card_price
from test_scanner import db  # noqa: F401  (db is a fixture)

REPRINT = "11111111-2222-3333-4444-555555555555"


def scryfall_card(card_id, name, **prices):
    return {"id": card_id, "name": name, "set": "rep", "set_name": "Reprint Set", "collector_number": "7",
            "rarity": "mythic", "colors": ["R", "G"],
            "prices": {"usd": None, "usd_foil": None, "usd_etched": None} | prices}


def fake_fetch(responses, calls=None):
    def fetch(url, body=None):
        if calls is not None:
            calls.append((url, body))
        for key, value in responses.items():
            if key in url:
                return value(body) if callable(value) else value
        raise ConnectionError(url)
    return fetch


@pytest.fixture
def live():
    reprint = scryfall_card(REPRINT, "Card 1", usd="2.00")
    return Live(fake_fetch({
        "/cards/collection": lambda body: {"data": [scryfall_card(i["id"], "x", usd="9.00")
                                                    for i in body["identifiers"] if i["id"] == "id1"]},
        f"/cards/{REPRINT}": reprint,
        "/cards/id1": scryfall_card("id1", "Card 1", usd="8.00"),
        "/cards/search": {"data": [reprint]},
    }))


@pytest.fixture
def client(db, live, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "USD_TO_CAD", 1.5)
    scanner = Scanner(db, None, source=None, live=live)
    return create_app(scanner).test_client()


def rows():
    return list(csv.DictReader(config.COLLECTION_CSV.open()))


# --- Prices ------------------------------------------------------------------------------

def test_live_price_beats_the_database(db, live, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "USD_TO_CAD", 1.5)
    card = db.get_card("id1")                      # the database says US$4.50
    assert card_price(card, False, None, live)[0] == 6.75
    live.card_json("id1")                          # today Scryfall says US$8.00
    price, source = card_price(card, False, None, live)
    assert price == 12.0 and source.startswith("Scryfall today")


def test_offline_keeps_database_prices(db, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "USD_TO_CAD", 1.5)
    lv = Live(fake_fetch({}))
    assert lv.card_json("id1") is None and lv.ready("id1")
    assert card_price(db.get_card("id1"), False, None, lv)[0] == 6.75
    assert lv.fetch_many(["id1", "id2"]) == 0


def test_foil_without_a_foil_price_uses_the_normal_one(db):  # noqa: F811
    price, source = card_price(db.get_card("id1"), True)
    assert price is not None and "non-foil price" in source


def test_fetch_many_batches_and_skips_fresh_cards(live):
    calls = []
    live.fetch = fake_fetch({"/cards/collection": lambda body: {"data": []}}, calls)
    live.fetch_many([f"c{i}" for i in range(160)])
    assert [len(b["identifiers"]) for _, b in calls] == [75, 75, 10]


# --- Printing picker -----------------------------------------------------------------------

def test_printings_lists_scryfall_and_database(client):
    found = client.get("/api/printings?name=Card 1").get_json()
    assert {c["id"] for c in found} == {"id1", REPRINT}


def test_picking_a_printing_the_database_lacks(client, db):  # noqa: F811
    state = client.post("/api/add", json={"id": REPRINT}).get_json()
    assert state["session"][0]["set"] == "REP"
    assert db.find_card(REPRINT).set_name == "Reprint Set"      # remembered for next time
    assert client.post("/api/add", json={"id": "nope"}).status_code == 404


# --- Collection page -----------------------------------------------------------------------

def test_collection_groups_copies(client):
    for card_id, foil in [("id1", False), ("id1", False), ("id1", True), ("id2", False)]:
        client.post("/api/add", json={"id": card_id, "foil": foil})
    js = client.get("/api/collection").get_json()
    by_key = {c["key"]: c for c in js["cards"]}
    assert by_key["id1#normal"]["qty"] == 2 and by_key["id1#foil"]["qty"] == 1
    assert by_key["id1#normal"]["value"] == round(2 * by_key["id1#normal"]["price"], 2)
    s = js["summary"]
    assert s["cards"] == 4 and s["unique"] == 3 and s["names"] == 2
    assert s["top"][0] == "id2#normal"
    assert js["history"][-1]["cards"] == 4
    assert client.get("/collection").status_code == 200


def test_quantity_foil_printing_and_delete(client):
    client.post("/api/add", json={"id": "id1"})
    client.post("/api/collection/edit", json={"key": "id1#normal", "qty": 3})
    assert sum(int(r["Quantity"]) for r in rows()) == 3
    client.post("/api/collection/edit", json={"key": "id1#normal", "qty": 1})
    assert sum(int(r["Quantity"]) for r in rows()) == 1
    client.post("/api/collection/edit", json={"key": "id1#normal", "foil": True})
    assert rows()[0]["Foil"] == "foil"
    js = client.post("/api/collection/edit", json={"key": "id1#foil", "printing": REPRINT}).get_json()
    assert [c["set"] for c in js["cards"]] == ["REP"]
    client.post("/api/collection/edit", json={"key": f"{REPRINT}#foil", "delete": True})
    assert rows() == []
    assert client.post("/api/collection/edit", json={"key": "id1#normal", "qty": 2}).status_code == 404
    assert client.post("/api/collection/edit", json={"key": "", "qty": 2}).status_code == 400


def test_add_by_hand(client):
    js = client.post("/api/collection/add", json={"id": "id2", "qty": 4, "foil": True}).get_json()
    assert js["cards"][0]["qty"] == 4 and js["cards"][0]["foil"]


def test_rows_without_scryfall_id_still_work(client):
    config.COLLECTION_CSV.write_text("Name,Quantity,Set code,Collector number,Foil\nOld Card,2,ABC,5,normal\n\n")
    js = client.get("/api/collection").get_json()
    item = js["cards"][0]
    assert item["name"] == "Old Card" and item["qty"] == 2 and item["price"] is None
    client.post("/api/collection/edit", json={"key": item["key"], "qty": 1})
    assert rows()[0]["Quantity"] == "1"


@pytest.mark.parametrize("fmt", list(library.EXPORTS))
def test_exports(client, fmt):
    client.post("/api/add", json={"id": "id1", "foil": True})
    client.post("/api/add", json={"id": "id2"})
    res = client.get(f"/api/collection/export?format={fmt}")
    assert res.status_code == 200 and "attachment" in res.headers["Content-Disposition"]
    text = res.get_data(as_text=True)
    assert "Card 1" in text and "Card 2" in text
    only = client.post("/api/collection/export", json={"format": fmt, "keys": ["id2#normal"]}).get_data(as_text=True)
    assert "Card 2" in only and "Card 1" not in only


def test_export_formats_look_right(client):
    client.post("/api/add", json={"id": "id1", "foil": True})
    text = client.get("/api/collection/export?format=text").get_data(as_text=True)
    assert text == "1 Card 1 (TST) 1 *F*\n"
    assert client.get("/api/collection/export?format=tcgplayer").get_data(as_text=True) == "1 Card 1 [TST]\n"
    mox = list(csv.DictReader(client.get("/api/collection/export?format=moxfield").get_data(as_text=True).splitlines()))
    assert mox[0]["Count"] == "1" and mox[0]["Edition"] == "tst" and mox[0]["Foil"] == "foil"
    assert client.get("/api/collection/export?format=nope").status_code == 400


def test_refresh_prices_in_the_background(client):
    client.post("/api/collection/add", json={"id": REPRINT})
    res = client.post("/api/collection/refresh").get_json()
    assert "refresh" in res
    for _ in range(100):
        state = client.get("/api/collection/refresh").get_json()["refresh"]
        if not state["running"]:
            break
    assert not state["running"] and state["total"] == 1


def test_refresh_needs_live_prices(db, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    client = create_app(Scanner(db, None, source=None)).test_client()
    assert client.post("/api/collection/refresh").status_code == 400


def test_value_history_keeps_one_point_per_day(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    library.note_value({"value": 10.0, "cards": 2}, "2026-10-30")
    library.note_value({"value": 12.0, "cards": 3}, "2026-10-31")
    days = library.note_value({"value": 15.0, "cards": 4}, "2026-10-31")
    assert days == [{"day": "2026-10-30", "value": 10.0, "cards": 2}, {"day": "2026-10-31", "value": 15.0, "cards": 4}]


def test_color_groups():
    assert [library.color_group(c) for c in ["", "R", "R,G", None]] == ["C", "R", "M", ""]
    card = Card("x", "X", "s", "S", "1", "rare", "U", 1.0, None)
    assert card.colors == "U"
