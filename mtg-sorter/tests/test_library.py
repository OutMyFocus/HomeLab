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


def http_error(code, retry_after=None):
    import requests
    resp = requests.Response()
    resp.status_code = code
    if retry_after is not None:
        resp.headers["Retry-After"] = str(retry_after)
    return requests.HTTPError(str(code), response=resp)


def test_a_busy_scryfall_is_asked_again(live):
    calls, slept, busy = [], [], [True]

    def fetch(url, body=None):
        calls.append(url)
        if busy[0]:
            busy[0] = False
            raise http_error(429, 1)
        return {"data": [scryfall_card(i["id"], "x", usd="1.00") for i in body["identifiers"]]}
    live.fetch, live.sleep = fetch, slept.append
    assert live.fetch_many([f"c{i}" for i in range(160)]) == 160     # every card, despite the 429
    assert len(calls) == 4 and 1.0 in slept
    assert all(s >= 0 for s in slept)


def test_refresh_says_when_scryfall_stopped_part_way(live):
    calls = []

    def fetch(url, body=None):
        calls.append(url)
        if len(calls) > 1:
            raise ConnectionError(url)
        return {"data": [scryfall_card(i["id"], "x", usd="1.00") for i in body["identifiers"]]}
    live.fetch, live.sleep = fetch, lambda s: None
    with pytest.raises(RuntimeError, match="Stopped after 75 of 300"):
        live.fetch_many([f"c{i}" for i in range(300)])
    assert len(calls) == 3                                            # gave up after two failed batches
    assert live.fetch_many([f"c{i}" for i in range(75)]) == 0          # the first 75 are kept


def test_searches_are_spaced_out(live):
    slept = []
    live.fetch, live.sleep = fake_fetch({"/cards/search": {"data": []}}), slept.append
    live.printings("Card 1")
    live.printings("Card 1")
    assert slept and max(slept) > 0.3                                  # about 2 a second, as Scryfall asks


# --- Keeping the collection file safe --------------------------------------------------------

import gzip  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import threading  # noqa: E402

from mtgscanner import collection, history  # noqa: E402
from mtgscanner.collection import COLLECTION_LOCK, COLUMNS, add_card, ensure_columns, remove_entry, remove_last  # noqa: E402


def write_raw(text, encoding="utf-8"):
    config.COLLECTION_CSV.write_bytes(text.encode(encoding))


def line(name, card_id="", qty="1", price="", bin_label="Bulk", at="2026-11-01T10:00:00", source="", number="1",
         foil="normal"):
    return io_csv([name, qty, "TST", "Test Set", number, foil, "rare", card_id, price, "", bin_label, at, source])


def io_csv(values):
    buf = io.StringIO()
    csv.writer(buf).writerow(values)
    return buf.getvalue()


HEADER = io_csv(COLUMNS)


def test_a_csv_saved_by_excel_keeps_its_names(client, db):  # noqa: F811
    write_raw("﻿" + HEADER + line("Old Card", qty="2"))           # "CSV UTF-8" adds a BOM
    assert [r["Name"] for r in library.read_rows(config.COLLECTION_CSV)] == ["Old Card"]
    add_card(config.COLLECTION_CSV, db.get_card("id1"), False, "Bulk", (1.0, ""))
    names = [r["Name"] for r in library.read_rows(config.COLLECTION_CSV)]
    assert names == ["Old Card", "Card 1"]
    assert not config.COLLECTION_CSV.read_bytes().startswith(b"\xef\xbb\xbf")
    assert (config.COLLECTION_CSV.parent / "collection.csv.bak").exists()


def test_a_csv_in_the_old_windows_encoding(client, db):  # noqa: F811
    write_raw(HEADER + line("Séance"), "cp1252")
    assert client.get("/api/collection").status_code == 200
    assert library.read_rows(config.COLLECTION_CSV)[0]["Name"] == "Séance"
    add_card(config.COLLECTION_CSV, db.get_card("id1"), False, "Bulk", (1.0, ""))   # turned into UTF-8 first
    text = config.COLLECTION_CSV.read_bytes().decode("utf-8")
    assert "Séance" in text and "Card 1" in text


def test_a_notes_column_is_kept(client, db):  # noqa: F811
    old = ["Name", "Quantity", "Set code", "Collector number", "Foil", "Notes"]     # older columns, plus Notes
    write_raw(io_csv(old) + io_csv(["Old Card", "3", "ABC", "5", "normal", "from Dad"]))
    add_card(config.COLLECTION_CSV, db.get_card("id1"), False, "Bulk", (1.0, ""))
    read = library.read_rows(config.COLLECTION_CSV)
    assert read[0]["Notes"] == "from Dad" and read[1]["Name"] == "Card 1"
    library.set_quantity(config.COLLECTION_CSV, read[0]["Name"] + "|ABC|5#normal", 2)
    read = library.read_rows(config.COLLECTION_CSV)
    assert read[0]["Notes"] == "from Dad" and read[0]["Quantity"] == "2"


def test_a_csv_without_a_name_column_is_never_rewritten(client):
    write_raw("Card,Count\nSol Ring,1\n")
    before = config.COLLECTION_CSV.read_bytes()
    with pytest.raises(ValueError, match="no Name column"):
        ensure_columns(config.COLLECTION_CSV)
    assert config.COLLECTION_CSV.read_bytes() == before
    assert (config.COLLECTION_CSV.parent / "collection.csv.bak").read_bytes() == before


def test_undo_copes_with_blank_lines(client):
    write_raw(HEADER + line("A", "ida", at="2026-11-01T10:00:00") + "\n" + line("B", "idb", at="2026-11-01T10:01:00")
              + "\n")
    assert remove_entry(config.COLLECTION_CSV, "ida", "2026-11-01T10:00:00")
    assert [r["Name"] for r in library.read_rows(config.COLLECTION_CSV)] == ["B"]
    assert remove_last(config.COLLECTION_CSV)                 # the card, not the blank line after it
    assert library.read_rows(config.COLLECTION_CSV) == []
    assert not list(config.COLLECTION_CSV.parent.glob("*.tmp"))


def blocked_by_the_lock(fn):
    """True if fn waits while another thread holds COLLECTION_LOCK, then runs once it's free."""
    done = threading.Event()
    with COLLECTION_LOCK:
        t = threading.Thread(target=lambda: (fn(), done.set()))
        t.start()
        waited = not done.wait(0.3)
    t.join(5)
    return waited and done.is_set()


def test_every_writer_takes_the_collection_lock(client, db):  # noqa: F811
    path, card = config.COLLECTION_CSV, db.get_card("id1")
    at = add_card(path, card, False, "Bulk", (1.0, ""))
    assert blocked_by_the_lock(lambda: add_card(path, card, False, "Bulk", (1.0, "")))
    assert blocked_by_the_lock(lambda: library.set_quantity(path, "id1#normal", 5))
    assert blocked_by_the_lock(lambda: library.set_foil(path, "id1#normal", True))
    assert blocked_by_the_lock(lambda: library.set_printing(path, "id1#foil", card))
    assert blocked_by_the_lock(lambda: remove_entry(path, "id1", at))
    assert blocked_by_the_lock(lambda: remove_last(path))
    assert blocked_by_the_lock(lambda: collection.append_rows(path, []))


def test_scans_saved_during_edits_are_kept(client, db):  # noqa: F811
    # A phone saving cards (under its own scanner's lock) while the Collection page edits.
    path = config.COLLECTION_CSV
    add_card(path, db.get_card("id2"), False, "Bulk", (1.0, ""))
    add_card(path, db.get_card("id1"), False, "Bulk", (1.0, ""))

    def scan():
        for _ in range(40):
            add_card(path, db.get_card("id1"), False, "Bulk", (1.0, ""))

    def edit():
        for n in range(40):
            library.set_quantity(path, "id2#normal", 1 + n % 3)

    threads = [threading.Thread(target=scan), threading.Thread(target=edit)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert library.quantity(path, "id1#normal") == 41


# --- Prices when scanned -------------------------------------------------------------------

def test_price_when_scanned_is_per_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    rows = [{"Name": "X", "Quantity": "10", "Set code": "ZZZ", "Collector number": "1", "Foil": "normal",
             "Price CAD": "1.00"},
            {"Name": "X", "Quantity": "1", "Set code": "ZZZ", "Collector number": "1", "Foil": "normal",
             "Price CAD": "12.00"},
            {"Name": "X", "Quantity": "5", "Set code": "ZZZ", "Collector number": "1", "Foil": "normal",
             "Price CAD": ""}]                                        # copies without a price don't count
    item = library.holdings(rows, None)[0]
    assert item["scanned_price"] == 2.0 and item["qty"] == 16
    assert item["value"] == 32.0 and item["price_source"] == "Price when it was scanned"


def test_correcting_the_printing_or_finish_prices_it_again(client):
    client.post("/api/add", json={"id": "id1"})
    js = client.post("/api/collection/edit", json={"key": "id1#normal", "printing": REPRINT}).get_json()
    item = js["cards"][0]
    assert item["set"] == "REP" and item["change"] == 0 and item["scanned_price"] == item["price"]
    js = client.post("/api/collection/edit", json={"key": f"{REPRINT}#normal", "foil": True}).get_json()
    item = js["cards"][0]
    assert item["foil"] and not item["change"] and js["summary"]["change"] == 0


def test_bins_are_the_same_with_the_rules_looked_up_once(client, db):  # noqa: F811
    from mtgscanner import sort_rules
    from mtgscanner.sorting import bin_for
    for card_id in ("id0", "id1", "id2"):
        client.post("/api/add", json={"id": card_id})
    for wanted in (False, True):
        sort_rules.save({**sort_rules.default_rules(),
                         "wanted": {"on": wanted, "bin": 3, "only": False, "text": "1 Card 2"}})
        for item in client.get("/api/collection").get_json()["cards"]:
            card = db.get_card(item["id"])
            assert item["bin"] == bin_for(card, item["foil"], item["price"])[0]


# --- The +/- buttons and delete -------------------------------------------------------------

def test_steps_count_from_what_the_file_has_now(client, db):  # noqa: F811
    client.post("/api/add", json={"id": "id1"})                 # the page shows 1
    for _ in range(2):                                          # the machine saves 2 more meanwhile
        add_card(config.COLLECTION_CSV, db.get_card("id1"), False, "Bulk", (1.0, ""))
    js = client.post("/api/collection/edit", json={"key": "id1#normal", "step": 1}).get_json()
    assert js["cards"][0]["qty"] == 4
    client.post("/api/collection/edit", json={"key": "id1#normal", "step": 1})
    client.post("/api/collection/edit", json={"key": "id1#normal", "step": 1})      # a double tap: both count
    assert library.quantity(config.COLLECTION_CSV, "id1#normal") == 6
    js = client.post("/api/collection/edit", json={"key": "id1#normal", "step": -1}).get_json()
    assert js["cards"][0]["qty"] == 5
    for bad in (1.5, True, 101, "1"):
        assert client.post("/api/collection/edit", json={"key": "id1#normal", "step": bad}).status_code == 400
    assert client.post("/api/collection/edit", json={"key": "id9#normal", "step": 1}).status_code == 404


def test_delete_refuses_copies_the_page_hasnt_shown(client, db):  # noqa: F811
    client.post("/api/add", json={"id": "id1"})
    add_card(config.COLLECTION_CSV, db.get_card("id1"), False, "Bulk", (1.0, ""))
    res = client.post("/api/collection/edit", json={"key": "id1#normal", "delete": True, "seen": 1})
    assert res.status_code == 409 and res.get_json()["qty"] == 2
    assert library.quantity(config.COLLECTION_CSV, "id1#normal") == 2
    js = client.post("/api/collection/edit", json={"key": "id1#normal", "delete": True, "seen": 2}).get_json()
    assert js["cards"] == []


# --- Value over time -------------------------------------------------------------------------

def test_a_damaged_value_history_is_kept_aside(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    library.history_file().write_text('{"2026-10-30": {"val')
    library.note_value({"value": 5.0, "cards": 1}, "2026-10-31")
    assert (tmp_path / "price_history.json.bad").read_text() == '{"2026-10-30": {"val'
    assert list(library.load_history()) == ["2026-10-31"]


def test_a_history_that_cant_be_read_is_never_saved_over(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    library.note_value({"value": 10.0, "cards": 2}, "2026-10-30")
    before = library.history_file().read_text()
    real = type(library.history_file()).read_text

    def refuse(self, *a, **k):
        if self.name == "price_history.json":
            raise PermissionError("busy")
        return real(self, *a, **k)

    with monkeypatch.context() as m:
        m.setattr(type(library.history_file()), "read_text", refuse)
        days = library.note_value({"value": 12.0, "cards": 3}, "2026-10-31")
    assert days == [{"day": "2026-10-31", "value": 12.0, "cards": 3}]
    assert library.history_file().read_text() == before


def test_page_loads_at_the_same_time_keep_every_day(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    library.history_file().write_text(json.dumps({f"2026-01-{d:02d}": {"value": 1.0, "cards": 1} for d in range(1, 29)}))
    start = threading.Barrier(4)

    def load(n):
        start.wait()
        for i in range(10):
            library.note_value({"value": float(n * 100 + i), "cards": 5}, "2026-11-18")

    threads = [threading.Thread(target=load, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(library.load_history()) == 29
    assert not list(tmp_path.glob("*.tmp"))


# --- History: imports aren't sessions ------------------------------------------------------

def test_imports_are_not_scanning_sessions(client, db):  # noqa: F811
    from datetime import datetime
    now = datetime.now().isoformat(timespec="seconds")
    write_raw(HEADER + "".join(line(f"Imported {i}", qty="100", bin_label="", at=now, source="My ManaBox", number=str(i))
                               for i in range(3)))
    add_card(config.COLLECTION_CSV, db.get_card("id1"), False, "Bulk", (1.0, ""))
    add_card(config.COLLECTION_CSV, db.get_card("id2"), False, "Bulk", (1.0, ""), origin="Sam")   # a phone
    js = client.get("/api/history").get_json()
    assert js["total_sessions"] == 1 and js["sessions"][0]["cards"] == 2
    assert js["days"][-1]["cards"] == 2
    s = js["sessions"][0]
    client.post("/api/history/delete", json={"start": s["start"], "end": s["end"]})
    assert [r["Name"] for r in library.read_rows(config.COLLECTION_CSV)] == ["Imported 0", "Imported 1", "Imported 2"]
    assert not history._scanned({"Source": "My ManaBox", "Bin": ""})


# --- Big answers are sent gzipped ------------------------------------------------------------

def test_big_json_is_gzipped_and_streams_are_left_alone(client):
    app = client.application
    big = json.dumps({"x": "y" * 100_000})

    @app.get("/test-stream")
    def test_stream():
        return app.response_class((c for c in [big]), mimetype="application/json")

    @app.get("/test-already")
    def test_already():
        return app.response_class(gzip.compress(big.encode()), mimetype="application/json",
                                  headers={"Content-Encoding": "gzip"})

    write_raw(HEADER + "".join(line(f"Card number {i}", number=str(i)) for i in range(300)))
    plain = client.get("/api/collection")
    assert "Content-Encoding" not in plain.headers                # the browser didn't ask for it
    zipped = client.get("/api/collection", headers={"Accept-Encoding": "gzip, deflate"})
    assert zipped.headers["Content-Encoding"] == "gzip" and "Accept-Encoding" in zipped.headers["Vary"]
    assert int(zipped.headers["Content-Length"]) == len(zipped.data) < len(plain.data)
    assert json.loads(gzip.decompress(zipped.data))["summary"]["cards"] == 300
    small = client.get("/api/history", headers={"Accept-Encoding": "gzip"})
    assert "Content-Encoding" not in small.headers                # small answers aren't worth it
    res = client.get("/test-stream", headers={"Accept-Encoding": "gzip"})
    assert "Content-Encoding" not in res.headers and res.get_data(as_text=True) == big
    res = client.get("/test-already", headers={"Accept-Encoding": "gzip"})
    assert gzip.decompress(res.data).decode() == big                # not gzipped twice


# --- Select many (bulk delete) -------------------------------------------------------------

def test_delete_many_at_once(client):
    for card_id, foil in [("id1", False), ("id1", False), ("id1", True), ("id2", False)]:
        client.post("/api/add", json={"id": card_id, "foil": foil})
    res = client.post("/api/collection/delete", json={"cards": {"id1#normal": 2, "id2#normal": 1}})
    assert res.status_code == 200 and res.headers["X-Deleted"] == "2"
    assert [c["key"] for c in res.get_json()["cards"]] == ["id1#foil"]
    assert [(r["Scryfall ID"], r["Foil"]) for r in rows()] == [("id1", "foil")]


def test_delete_many_refuses_when_more_were_saved_since(client):
    client.post("/api/add", json={"id": "id1"})
    client.post("/api/add", json={"id": "id2"})
    client.post("/api/add", json={"id": "id2"})          # saved after the page showed 1
    res = client.post("/api/collection/delete", json={"cards": {"id1#normal": 1, "id2#normal": 1}})
    assert res.status_code == 409 and res.get_json()["changed"] == {"id2#normal": 2}
    assert len(rows()) == 3                              # nothing deleted, not even id1


def test_delete_many_bad_requests(client):
    assert client.post("/api/collection/delete", json={}).status_code == 400
    assert client.post("/api/collection/delete", json={"cards": {"id1#normal": -1}}).status_code == 400
    assert client.post("/api/collection/delete", json={"cards": {"#normal": 1}}).status_code == 400
    # a card that's already gone is fine: there's nothing left to delete
    assert client.post("/api/collection/delete", json={"cards": {"id9#normal": 1}}).status_code == 200


def test_delete_many_needs_the_edit_permission():
    from mtgscanner import logins
    assert logins.needed("POST", "/api/collection/delete") == "edit"
