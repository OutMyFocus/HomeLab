"""Drive the real page in a headless browser: the Live tab, saving, undo, the printing
picker and the Photos tab. Runs only when Playwright and a Chromium are installed:

    pip install playwright && playwright install chromium

The scanner runs with a fake camera (DemoSource over photographed fake cards), so no
hardware or internet is needed.
"""

import os
import threading

import cv2
import pytest
from werkzeug.serving import make_server

from app import DemoSource, Scanner, create_app
from mtgscanner import config
from test_live import fake_fetch, scryfall_card, RATE
from mtgscanner.live import Live
from test_scanner import db, fake_card, photograph  # noqa: F401  (db is a fixture)

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:
            fallback = "/opt/pw-browsers/chromium"
            if not os.path.exists(fallback):
                pytest.skip("No Chromium for Playwright (run: playwright install chromium)")
            b = p.chromium.launch(executable_path=fallback)
        yield b
        b.close()


@pytest.fixture
def site(db, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "STABLE_FRAMES", 2)
    photos = tmp_path / "photos"
    photos.mkdir()
    cv2.imwrite(str(photos / "card1.jpg"), photograph(fake_card(1)))
    reprint = scryfall_card(9, usd="2.00") | {"name": "Card 1", "set": "rep", "set_name": "Reprint Set"}
    live = Live(fake_fetch({"bankofcanada": RATE, "/cards/id1": scryfall_card(1, usd="8.00"), "/cards/id9": reprint,
                            "/cards/search": {"data": [reprint]}, "/cards/autocomplete": {"data": ["Card 1"]}}))
    live.load_rate()
    scanner = Scanner(db, None, DemoSource(str(photos), seconds=3600), live)
    threading.Thread(target=scanner.run, daemon=True).start()
    server = make_server("127.0.0.1", 0, create_app(scanner), threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", scanner
    server.shutdown()


def test_live_tab_save_undo_and_picker(browser, site):
    url, scanner = site
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url)

    # The camera shows Card 1, the page recognizes it and prices it with today's rate.
    page.wait_for_selector("#cardView:not([hidden])", timeout=10000)
    assert page.inner_text("#cardName") == "Card 1"
    assert page.inner_text("#cardPrice") == "$11.20"             # 8.00 USD x 1.40
    assert "Bin 3" in page.inner_text("#cardBin")
    assert "Good match" in page.inner_text("#cardMatch")
    assert "1 USD = 1.4000 CAD" in page.inner_text("#meta")
    assert page.inner_text("#camStatus") == "Card recognized"

    # Space saves it; the session table and totals update; the button says Saved.
    page.keyboard.press("Space")
    page.wait_for_selector("#saveBtn:disabled")
    assert "Saved" in page.inner_text("#saveBtn")
    assert "Card 1" in page.inner_text("#sessionRows")
    assert "1 cards" in page.inner_text("#totals").replace("\n", " ")
    assert config.COLLECTION_CSV.read_text().count("\n") == 2   # header + 1 row

    # Foil toggles with F and reprices (no foil price: falls back to the non-foil one).
    page.keyboard.press("f")
    page.wait_for_selector('#foilBtn[aria-pressed="true"]')
    assert "foil" in page.inner_text("#cardSet")

    # "Wrong printing?" lists the database printing and Scryfall's reprint; picking one swaps the saved row.
    page.click("#printBtn")
    page.wait_for_selector("#printings button[data-id='id9']")
    assert page.locator("#printings button").count() == 2
    page.click("#printings button[data-id='id9']")
    page.wait_for_selector("text=Printing picked by you")
    assert "REP" in page.inner_text("#cardSet")
    assert "REP" in config.COLLECTION_CSV.read_text() and "TST" not in config.COLLECTION_CSV.read_text()

    # Undo empties the session.
    page.click("#undoBtn")
    page.wait_for_selector("#undoBtn:disabled")
    assert "No cards saved yet" in page.inner_text("#sessionRows")
    assert errors == []
    page.close()


def test_photos_tab(browser, site):
    url, scanner = site
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url)
    page.click("button[data-tab='photos']")
    good = cv2.imencode(".jpg", photograph(fake_card(2)))[1].tobytes()
    page.set_input_files("#photoInput", [
        {"name": "good.jpg", "mimeType": "image/jpeg", "buffer": good},
        {"name": "junk.heic", "mimeType": "application/octet-stream", "buffer": b"nope"},
    ])
    page.wait_for_selector("#photoGrid .photo button[data-add]")
    assert "1 of 2 recognized" in page.inner_text("#photoSummary")
    assert "Couldn't open" in page.inner_text("#photoGrid")
    page.click("#addAllBtn")
    page.wait_for_selector("#photoGrid button[data-add]:disabled")
    assert "1 added" in page.inner_text("#photoSummary")
    assert "Card 2" in config.COLLECTION_CSV.read_text()
    assert errors == []
    page.close()
