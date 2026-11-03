"""History, wishlist, alerts and the PIN lock."""

import csv
from datetime import date

import pytest

from app import Scanner, create_app
from mtgscanner import config, history, security, wishlist
from mtgscanner.collection import COLUMNS
from test_scanner import db  # noqa: F401  (db is a fixture)

REMOTE = {"REMOTE_ADDR": "10.0.0.50"}     # a phone on the Wi-Fi, not the Pi itself


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")
    monkeypatch.setattr(config, "USD_TO_CAD", 1.5)
    security._tries.clear()


@pytest.fixture
def client(db):  # noqa: F811
    return create_app(Scanner(db, None, source=None)).test_client()


def write_csv(rows):
    with config.COLLECTION_CSV.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for name, card_id, price, when in rows:
            w.writerow([name, 1, "TST", "Test Set", "1", "normal", "rare", card_id, price, "", "Bulk", when])


# --- History ------------------------------------------------------------------------------

def test_sessions_split_on_half_hour_gaps(client):
    write_csv([("Card 1", "id1", "1.00", "2026-10-30T10:00:00"), ("Card 2", "id2", "30.00", "2026-10-30T10:20:00"),
               ("Card 0", "id0", "0.10", "2026-10-30T11:30:00"), ("Card 3", "id3", "", "not a time")])
    js = client.get("/api/history").get_json()
    assert [s["cards"] for s in js["sessions"]] == [1, 2]          # newest first
    old = js["sessions"][1]
    assert old["value"] == 31.0 and old["top"]["name"] == "Card 2" and old["minutes"] == 20
    assert len(js["days"]) == 30
    assert client.get("/history").status_code == 200


def test_per_day_counts():
    rows = [{"Scanned at": "2026-10-31T09:00:00", "Quantity": "2", "Price CAD": "1.5"}]
    days = history.per_day(rows, 3, date(2026, 10, 31))
    assert days[-1] == {"day": "2026-10-31", "cards": 2, "value": 3.0} and days[0]["cards"] == 0


def test_delete_and_export_a_session(client):
    write_csv([("Card 1", "id1", "1.00", "2026-10-30T10:00:00"), ("Card 2", "id2", "30.00", "2026-10-30T12:00:00")])
    s = client.get("/api/history").get_json()["sessions"][1]
    res = client.post("/api/history/export", json={"start": s["start"], "end": s["end"], "format": "text"})
    assert res.get_data(as_text=True) == "1 Card 1 (TST) 1\n"
    assert "session-2026-10-30-1000" in res.headers["Content-Disposition"]
    js = client.post("/api/history/delete", json={"start": s["start"], "end": s["end"]}).get_json()
    assert [x["cards"] for x in js["sessions"]] == [1]
    assert client.post("/api/history/delete", json={"start": s["start"], "end": s["end"]}).status_code == 404
    assert client.post("/api/history/delete", json={}).status_code == 400


# --- Wishlist and alerts ------------------------------------------------------------------

def test_wishlist_prices_deals_and_owned(client):
    client.post("/api/add", json={"id": "id1"})
    client.post("/api/wishlist/add", json={"name": "Card 2", "target": 40})      # US$25 = $37.50
    js = client.post("/api/wishlist/add", json={"name": "card 1"}).get_json()
    items = {i["display"]: i for i in js["items"]}
    assert items["Card 2"]["price"] == 37.5 and items["Card 2"]["deal"] and not items["Card 2"]["owned"]
    assert items["Card 1"]["owned"] == 1 and not items["Card 1"]["deal"]
    assert js["deals"] == 1 and js["owned"] == 1
    item = items["Card 2"]
    js = client.post("/api/wishlist/update", json={"id": item["id"], "target": 10}).get_json()
    assert not any(i["deal"] for i in js["items"])
    assert client.post("/api/wishlist/update", json={"id": item["id"], "target": "cheap"}).status_code == 400
    client.post("/api/wishlist/add", json={"name": "Card 2", "target": 50})     # same card: updates it
    assert len(wishlist.load_items()) == 2
    js = client.post("/api/wishlist/remove", json={"id": item["id"]}).get_json()
    assert [i["display"] for i in js["items"]] == ["Card 1"]
    assert client.post("/api/wishlist/remove", json={"id": "nope"}).status_code == 404
    assert client.post("/api/wishlist/add", json={"name": " "}).status_code == 400
    js = client.post("/api/wishlist/add", json={"name": "Typo Card"}).get_json()
    assert not next(i for i in js["items"] if i["name"] == "Typo Card")["found"]
    assert client.get("/wishlist").status_code == 200


def test_deck_missing_cards_go_to_the_wishlist(client):
    client.post("/api/wishlist/add", json={"cards": [{"name": "Card 2"}, {"name": "Card 3"}, "junk"]})
    assert {i["name"] for i in wishlist.load_items()} == {"Card 2", "Card 3"}


def test_scanner_marks_wishlist_cards_and_sends_alerts(client):
    client.post("/api/wishlist/add", json={"name": "Card 2"})
    state = client.post("/api/add", json={"id": "id2"}).get_json()
    state = client.get("/api/state").get_json()
    assert state["session"][0]["wanted"] is True
    assert state["alerts"] == {"big_card": 20.0, "sound": True, "wishlist": True}


def test_alert_settings(client):
    js = client.post("/api/alerts", json={"big_card": "50", "sound": False}).get_json()
    assert js == {"big_card": 50.0, "sound": False, "wishlist": True}
    assert client.post("/api/alerts", json={"big_card": ""}).get_json()["big_card"] is None
    assert client.post("/api/alerts", json={"big_card": "-3"}).status_code == 400
    assert client.get("/settings").status_code == 200


# --- PIN lock -------------------------------------------------------------------------------

def test_no_pin_means_no_lock(client):
    assert client.get("/api/collection", environ_base=REMOTE).status_code == 200
    assert client.get("/api/lock", environ_base=REMOTE).get_json() == {"enabled": False, "unlocked": True, "local": False}


def test_pin_locks_other_devices_but_not_the_pi(client):
    assert client.post("/api/lock/set", json={"pin": "12a4"}).status_code == 400
    assert client.post("/api/lock/set", json={"pin": "2468"}).status_code == 200
    phone = client.application.test_client()
    res = phone.get("/collection", environ_base=REMOTE)
    assert res.status_code == 401 and b"is locked" in res.data              # the lock screen
    assert phone.post("/api/add", json={"id": "id1"}, environ_base=REMOTE).get_json()["locked"]
    assert phone.get("/static/style.css", environ_base=REMOTE).status_code == 200
    assert phone.get("/api/health", environ_base=REMOTE).status_code == 200
    assert client.get("/api/state").status_code == 200                     # the Pi itself
    tunnel = {"REMOTE_ADDR": "127.0.0.1", "HTTP_CF_CONNECTING_IP": "1.2.3.4"}
    assert phone.get("/api/state", environ_base=tunnel).status_code == 401  # a tunnel isn't the Pi

    assert phone.post("/api/unlock", json={"pin": "1111"}, environ_base=REMOTE).status_code == 403
    assert phone.post("/api/unlock", json={"pin": "2468"}, environ_base=REMOTE).status_code == 200
    assert phone.get("/api/state", environ_base=REMOTE).status_code == 200  # the cookie works

    phone.post("/api/lock/now", environ_base=REMOTE)
    assert phone.get("/api/state", environ_base=REMOTE).status_code == 401


def test_changing_the_pin_signs_out_other_devices(client):
    client.post("/api/lock/set", json={"pin": "2468"})
    phone = client.application.test_client()
    phone.post("/api/unlock", json={"pin": "2468"}, environ_base=REMOTE)
    client.post("/api/lock/set", json={"pin": "1357"})
    assert phone.get("/api/state", environ_base=REMOTE).status_code == 401
    client.post("/api/lock/remove")
    assert phone.get("/api/state", environ_base=REMOTE).status_code == 200


def test_too_many_wrong_pins_pause(client):
    client.post("/api/lock/set", json={"pin": "2468"})
    for _ in range(security.TRIES):
        assert client.post("/api/unlock", json={"pin": "0000"}, environ_base=REMOTE).status_code == 403
    assert client.post("/api/unlock", json={"pin": "2468"}, environ_base=REMOTE).status_code == 429


def test_pin_is_stored_hashed():
    security.set_pin("2468")
    assert "2468" not in security.pin_file().read_text()
    assert security.right_pin("2468") and not security.right_pin("2469")
