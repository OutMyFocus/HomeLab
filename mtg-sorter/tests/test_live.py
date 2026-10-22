"""Live prices and lookups, with Scryfall and the Bank of Canada faked (no internet needed)."""

import csv

import pytest

from app import Scanner, create_app
from mtgscanner import config
from mtgscanner.collection import COLUMNS, add_card
from mtgscanner.database import Card
from mtgscanner.live import Live
from mtgscanner.sorting import card_price, choose_bin
from test_scanner import db  # noqa: F401  (db is a fixture)

RATE = {"observations": [{"d": "2026-10-21", "FXUSDCAD": {"v": "1.4000"}}]}


def scryfall_card(i, **prices):
    return {"id": f"id{i}", "name": f"Card {i}", "set": "tst", "set_name": "Test Set", "collector_number": str(i),
            "rarity": "rare", "prices": {"usd": None, "usd_foil": None, "usd_etched": None} | prices}


def fake_fetch(responses):
    def fetch(url):
        for key, value in responses.items():
            if key in url:
                return value
        raise ConnectionError(url)
    return fetch


@pytest.fixture
def live():
    reprint = scryfall_card(9, usd="2.00") | {"name": "Card 1", "set": "rep", "set_name": "Reprint Set"}
    lv = Live(fake_fetch({
        "bankofcanada": RATE,
        "/cards/id1": scryfall_card(1, usd="8.00"),
        "/cards/id9": reprint,
        "/cards/search": {"data": [reprint]},
        "/cards/autocomplete": {"data": ["Card 1"]},
    }))
    lv.load_rate()
    return lv


def test_live_price_and_rate(db, live):  # noqa: F811
    card = db.get_card("id1")             # the database says $4.50 USD
    assert card_price(card, False, None, live) == (6.3, "Scryfall (USD converted)")   # not fetched yet: DB price
    live.card_json("id1")
    assert card_price(card, False, None, live) == (11.2, "Scryfall today (USD converted)")
    assert live.usd_to_cad() == (1.4, "Bank of Canada, 2026-10-21")


def test_offline_falls_back_to_database_and_fixed_rate(db):  # noqa: F811
    lv = Live(fake_fetch({}))
    lv.load_rate()
    assert lv.card_json("id1") is None and lv.ready("id1")
    assert card_price(db.get_card("id1"), False, None, lv) == (round(4.50 * config.USD_TO_CAD, 2), "Scryfall (USD converted)")


def test_missing_finish_uses_the_other_price(db):  # noqa: F811
    nonfoil_only = db.get_card("id1")
    price, source = card_price(nonfoil_only, True)
    assert price == round(4.50 * config.USD_TO_CAD, 2) and "non-foil price" in source
    foil_only = Card("x", "Promo", "p", "Promos", "1", "rare", "", None, 20.0)
    assert choose_bin(foil_only, False)[0] == 3


def test_etched_price_counts_as_foil(db):  # noqa: F811
    lv = Live(fake_fetch({"/cards/id2": scryfall_card(2, usd_etched="30.00")}))
    lv.card_json("id2")
    price, source = card_price(db.get_card("id2"), True, None, lv)
    assert price == round(30 * config.USD_TO_CAD, 2) and "etched" in source


@pytest.fixture
def scanner(db, live, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    return Scanner(db, None, source=None, live=live)


def test_unknown_id_is_a_404(scanner):
    client = create_app(scanner).test_client()
    assert client.post("/api/add", json={"id": "nope"}).status_code == 404


def test_printings_include_scryfall_reprints(scanner):
    client = create_app(scanner).test_client()
    found = client.get("/api/printings?name=Card 1").get_json()
    assert {c["id"] for c in found} == {"id1", "id9"}
    assert client.get("/api/search?q=Car").get_json() == ["Card 1"]


def test_choosing_a_printing_swaps_the_saved_row(scanner):
    client = create_app(scanner).test_client()
    scanner.card, scanner.status = scanner.matcher.get_card("id1"), "locked"
    client.post("/api/add", json={"id": "id1"})
    state = client.post("/api/choose", json={"id": "id9"}).get_json()   # only on Scryfall, not in the DB
    assert state["picked"] and state["saved"] and state["card"]["set"] == "REP"
    rows = list(csv.DictReader(config.COLLECTION_CSV.open()))
    assert [(r["Set code"], r["Price CAD"], r["Bin number"]) for r in rows] == [("REP", "2.80", "2")]


def test_photo_foil_reprices(scanner):
    client = create_app(scanner).test_client()
    info = client.get("/api/card?id=id1&foil=1").get_json()
    assert info["foil"] and "non-foil price" in info["price_source"]


def test_old_csv_gets_bin_number_column(db, tmp_path):  # noqa: F811
    path = tmp_path / "collection.csv"
    old = COLUMNS[:-1]
    with path.open("w", newline="") as f:
        csv.writer(f).writerows([old, ["Old card"] + [""] * (len(old) - 1)])
    add_card(path, db.get_card("id2"), False, "$10+ (valuable!)", (34.5, "Scryfall"), 3)
    rows = list(csv.DictReader(path.open()))
    assert [r["Bin number"] for r in rows] == ["", "3"]
