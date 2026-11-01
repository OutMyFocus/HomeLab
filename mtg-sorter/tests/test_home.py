"""The Home page, the scanner's new address, and the shared page menu."""

import csv
import re
from datetime import datetime, timedelta

import pytest

from app import SESSION_SHOWN, WEB, Scanner, WaitingForCamera, create_app
from mtgscanner import config
from mtgscanner.collection import COLUMNS
from test_scanner import db  # noqa: F401  (db is a fixture)


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")


@pytest.fixture
def scanner(db):  # noqa: F811
    return Scanner(db, None, source=None)


@pytest.fixture
def client(scanner):
    return create_app(scanner).test_client()


def write_csv(rows):
    with config.COLLECTION_CSV.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for name, card_id, scanned, now, when in rows:
            w.writerow([name, 1, "TST", "Test Set", "1", "normal", "rare", card_id, scanned, "", "Bulk", when])


def test_home_is_the_dashboard_and_the_scanner_moved(client):
    home = client.get("/").get_data(as_text=True)
    assert 'src="/static/home.js"' in home
    scan = client.get("/scan").get_data(as_text=True)
    assert 'src="/static/app.js"' in scan


def test_every_page_has_the_shared_menu(client):
    for page in ["/", "/scan", "/collection", "/decks", "/wishlist", "/history", "/bins", "/machine",
                 "/maintenance", "/settings"]:
        html = client.get(page).get_data(as_text=True)
        assert 'src="/static/shell.js"' in html, page
        assert 'src="/static/look.js"' in html or "mtg-scanner-look" in html, page   # the saved theme


def test_menu_links_go_to_real_pages(client):
    links = re.findall(r'href: "(/[a-z]*)"', (WEB / "shell.js").read_text())
    assert "/" in links and "/scan" in links and len(links) == 10
    for href in links:
        assert client.get(href).status_code == 200, href


def test_home_summary_with_an_empty_collection(client):
    js = client.get("/api/home").get_json()
    assert js["collection"]["cards"] == 0
    assert js["collection"]["recent"] == []
    assert js["sessions"]["last"] is None
    assert len(js["sessions"]["days"]) == 14
    assert js["machine"]["servos"] in (True, False)
    assert [b["bin"] for b in js["collection"]["bins"]] == sorted((b["bin"] for b in js["collection"]["bins"]), reverse=True)


def test_home_summary_counts_the_collection(client):
    now = datetime.now()
    write_csv([
        ("Card 1", "id1", "4.00", None, (now - timedelta(days=2)).isoformat(timespec="seconds")),
        ("Card 2", "id2", "20.00", None, (now - timedelta(minutes=5)).isoformat(timespec="seconds")),
        ("Card 2", "id2", "20.00", None, (now - timedelta(minutes=4)).isoformat(timespec="seconds")),
    ])
    js = client.get("/api/home").get_json()
    c = js["collection"]
    assert c["cards"] == 3
    assert [r["name"] for r in c["recent"]] == ["Card 2", "Card 1"]   # newest first, each once
    assert js["sessions"]["count"] == 2
    assert js["sessions"]["week"]["cards"] == 3
    assert js["sessions"]["last"]["cards"] == 2 and "rows" not in js["sessions"]["last"]
    assert c["history"][-1]["cards"] == 3     # noted for the value chart


def test_home_says_when_there_is_no_camera(db):  # noqa: F811
    scanner = Scanner(db, None, source=WaitingForCamera(None))
    js = create_app(scanner).test_client().get("/api/home").get_json()
    assert js["scanner"]["waiting"] is True
    assert js["scanner"]["camera"] is None


def test_scanner_state_lists_only_the_newest_cards(client, scanner):
    for i in range(SESSION_SHOWN + 5):
        client.post("/api/add", json={"id": "id1", "foil": False})
    s = client.get("/api/state").get_json()
    assert s["session_count"] == SESSION_SHOWN + 5
    assert len(s["session"]) == SESSION_SHOWN
    assert s["totals"]["count"] == SESSION_SHOWN + 5
    assert s["session"][0]["scanned_at"] == scanner.session[-1]["scanned_at"]
