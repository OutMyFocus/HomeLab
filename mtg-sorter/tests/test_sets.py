"""The Sets page: set completion and spare copies."""

import csv

import pytest

from app import Scanner, create_app
from mtgscanner import config
from mtgscanner.collection import COLUMNS
from mtgscanner.sets import number_key, spares
from test_scanner import db  # noqa: F401  (db is a fixture)


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")


@pytest.fixture
def client(db):  # noqa: F811
    return create_app(Scanner(db, None, source=None)).test_client()


def write_csv(rows):
    """rows: (name, card id, collector number, quantity, foil)"""
    with config.COLLECTION_CSV.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for name, card_id, number, n, foil in rows:
            w.writerow([name, n, "TST", "Test Set", number, "foil" if foil else "normal", "rare", card_id, "1.00", "",
                        "Bulk", "2026-11-01T10:00:00"])


def test_collector_numbers_sort_like_the_set():
    assert sorted(["10", "2", "10a", "1", "★3"], key=number_key) == ["1", "2", "10", "10a", "★3"]


def test_set_completion(client):
    write_csv([("Card 0", "id0", "0", 1, False), ("Card 2", "id2", "2", 3, False), ("Card 2", "id2", "2", 1, True)])
    sets = client.get("/api/sets").get_json()["sets"]
    assert sets == [{"set": "TST", "name": "Test Set", "total": 4, "owned": 2, "copies": 5, "percent": 50.0}]
    d = client.get("/api/sets/tst").get_json()
    assert (d["total"], d["owned"]) == (4, 2)
    assert [c["number"] for c in d["cards"]] == ["0", "1", "2", "3"]
    two = d["cards"][2]
    assert (two["qty"], two["foil"]) == (4, 1)
    assert d["by_rarity"]["rare"] == {"total": 4, "owned": 2}
    assert client.get("/api/sets/zzz").status_code == 404


def test_empty_collection_has_no_started_sets(client):
    sets = client.get("/api/sets").get_json()["sets"]
    assert sets[0]["owned"] == 0 and sets[0]["percent"] == 0


def test_spares_keep_a_playset_and_offer_the_cheapest(client):
    items = [
        {"key": "a#normal", "id": "a", "name": "Bolt", "set": "AAA", "number": "1", "foil": False, "price": 5.0, "image": "", "qty": 3},
        {"key": "b#normal", "id": "b", "name": "Bolt", "set": "BBB", "number": "9", "foil": False, "price": 0.5, "image": "", "qty": 3},
        {"key": "c#normal", "id": "c", "name": "Island", "set": "AAA", "number": "2", "foil": False, "price": 0.1, "image": "", "qty": 20},
        {"key": "d#normal", "id": "d", "name": "Rare", "set": "AAA", "number": "3", "foil": False, "price": 9.0, "image": "", "qty": 1},
    ]
    found = spares(items, keep=4)
    assert [s["name"] for s in found] == ["Bolt"]           # basic lands left out, one Rare isn't spare
    bolt = found[0]
    assert (bolt["have"], bolt["spare"]) == (6, 2)
    assert [(p["set"], p["spare"]) for p in bolt["printings"]] == [("BBB", 2)]   # the cheap printing goes
    assert {s["name"] for s in spares(items, keep=4, lands=True)} == {"Island", "Bolt"}
    assert {s["name"] for s in spares(items, keep=0)} == {"Bolt", "Rare"}


def test_spares_api(client):
    write_csv([("Card 1", "id1", "1", 6, False)])
    js = client.get("/api/spares?keep=4").get_json()
    assert js["keep"] == 4 and js["cards"] == 2
    assert client.get("/api/spares?keep=nope").get_json()["keep"] == 4
    assert client.get("/sets").status_code == 200
