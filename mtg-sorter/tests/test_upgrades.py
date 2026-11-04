"""The deck builder's upgrade path: EDHREC's list for a commander, cached, with prices."""

import os
import time
from pathlib import Path

import pytest
import requests

from app import Scanner, create_app
from mtgscanner import config, upgrades
from mtgscanner.live import Live
from test_library import fake_fetch, scryfall_card
from test_scanner import db  # noqa: F401  (db is a fixture)


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "VAULT_PRICES", tmp_path / "vault_prices.json")
    return tmp_path


def page(*groups):
    """A tiny EDHREC commander page: groups of (header, [(name, num_decks, synergy)])."""
    return {"land": 37, "basic": 14, "container": {"json_dict": {"cardlists": [
        {"header": h, "cardviews": [{"name": n, "num_decks": k, "potential_decks": 1000, "synergy": s} for n, k, s in cards]}
        for h, cards in groups]}}}


GISA = page(("Top Cards", [("Gravecrawler", 600, 0.4)]),
            ("Creatures", [("Gravecrawler", 600, 0.4), ("Diregraf Colossus", 450, 0.3)]),
            ("Mana Artifacts", [("Sol Ring", 950, -0.02)]))


def test_slug_matches_edhrec():
    assert upgrades.slug("Atraxa, Praetors' Voice") == "atraxa-praetors-voice"
    assert upgrades.slug("Doctor Doom, King of Latveria") == "doctor-doom-king-of-latveria"
    assert upgrades.slug("Lim-Dûl the Necromancer") == "lim-dul-the-necromancer"
    assert upgrades.slug("Kozilek's Return") == "kozileks-return"
    assert upgrades.slug("Esika, God of the Tree // The Prismatic Bridge") == "esika-god-of-the-tree"


def test_compact_keeps_each_card_once_with_its_share_of_decks():
    out = upgrades.compact(GISA)
    names = [c["n"] for c in out["cards"]]
    assert sorted(names) == ["Diregraf Colossus", "Gravecrawler", "Sol Ring"]
    grave = next(c for c in out["cards"] if c["n"] == "Gravecrawler")
    assert grave == {"n": "Gravecrawler", "inc": 0.6, "syn": 0.4, "cat": "Top Cards"}
    assert out["decks"] == 1000 and out["lands"] == 37


def test_recommendations_are_cached_for_a_week(data_dir):
    calls = []
    def fetch(s):
        calls.append(s)
        return GISA
    first = upgrades.recommendations("Ghoulcaller Gisa", fetch=fetch)
    again = upgrades.recommendations("Ghoulcaller Gisa", fetch=fetch)
    assert calls == ["ghoulcaller-gisa"]
    assert first["source"] == again["source"] == "edhrec"
    assert first["url"] == "https://edhrec.com/commanders/ghoulcaller-gisa"
    # A week later it asks again.
    old = time.time() - upgrades.TTL - 60
    os.utime(upgrades.cache_file("ghoulcaller-gisa"), (old, old))
    upgrades.recommendations("Ghoulcaller Gisa", fetch=fetch)
    assert len(calls) == 2


def test_old_copy_is_used_when_edhrec_is_down(data_dir):
    upgrades.recommendations("Ghoulcaller Gisa", fetch=lambda s: GISA)
    old = time.time() - upgrades.TTL - 60
    os.utime(upgrades.cache_file("ghoulcaller-gisa"), (old, old))
    def down(s):
        raise requests.ConnectionError("no network")
    out = upgrades.recommendations("Ghoulcaller Gisa", fetch=down)
    assert out["source"] == "edhrec" and len(out["cards"]) == 3


def test_no_list_falls_back_with_a_reason():
    def down(s):
        raise requests.ConnectionError("no network")
    assert upgrades.recommendations("Ghoulcaller Gisa", fetch=down)["source"] == "none"
    out = upgrades.recommendations("Some Brand New Legend", fetch=lambda s: None)
    assert out["source"] == "none" and "no decks" in out["error"]
    assert upgrades.recommendations("Ghoulcaller Gisa", online=False)["source"] == "none"


def test_route_prices_the_cards_in_canadian_dollars(db, monkeypatch):  # noqa: F811
    monkeypatch.setattr(upgrades, "fetch_page", lambda s: GISA)
    live = Live(fetch=fake_fetch({"/cards/collection": {"data": [
        scryfall_card("g1", "Gravecrawler", usd="1.00"), scryfall_card("s1", "Sol Ring", usd="2.00")]}}))
    client = create_app(Scanner(db, None, source=None, live=live)).test_client()
    js = client.get("/api/decks/upgrades?commander=Ghoulcaller Gisa").get_json()
    prices = {c["n"]: c.get("p") for c in js["cards"]}
    assert prices["Gravecrawler"] == round(1.00 * config.USD_TO_CAD, 2)
    assert prices["Sol Ring"] == round(2.00 * config.USD_TO_CAD, 2)
    assert prices["Diregraf Colossus"] is None
    assert client.get("/api/decks/upgrades").status_code == 400


def test_decks_page_has_the_upgrade_path():
    text = (Path(__file__).resolve().parent.parent / "webui" / "decks.html").read_text()
    assert 'id="upg"' in text and "/static/upgrades.js" in text
