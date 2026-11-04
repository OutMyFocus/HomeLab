"""The Decks page's Upgrade this deck panel: EDHREC's cards for a commander, with prices."""

import time

import pytest
import requests

from app import Scanner, create_app
from mtgscanner import config, upgrades
from test_scanner import db  # noqa: F401  (db is a fixture)


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")
    monkeypatch.setattr(config, "USD_TO_CAD", 1.5)


def page(*lists):
    return {"container": {"json_dict": {"cardlists": [
        {"tag": tag, "header": header, "cardviews": [
            {"name": n, "num_decks": used, "potential_decks": 1000, "synergy": syn} for n, used, syn in cards]}
        for tag, header, cards in lists]}}}


EDHREC = page(
    ("newcards", "New Cards", [("Brand New", 50, .1)]),
    ("creatures", "Creatures", [("Big Bird", 600, .3), ("Sol Ring", 850, 0)]),
    ("manaartifacts", "Mana Artifacts", [("Sol Ring", 850, 0), ("Arcane Signet", 790, -.01)]),
    ("lands", "Lands", [("Command Tower", 920, 0)]),
)


def test_slug_matches_edhrec():
    assert upgrades.slug("Atraxa, Praetors' Voice") == "atraxa-praetors-voice"
    assert upgrades.slug("Lim-Dûl the Necromancer") == "lim-dul-the-necromancer"
    assert upgrades.slug("Esika, God of the Tree // The Prismatic Bridge") == "esika-god-of-the-tree"


def test_summary_keeps_each_card_once_and_skips_new_cards():
    data = upgrades.summarize(EDHREC)
    names = [c["n"] for c in data["cards"]]
    assert names == ["Command Tower", "Sol Ring", "Arcane Signet", "Big Bird"]   # most played first
    assert data["decks"] == 1000
    assert data["cards"][0] == {"n": "Command Tower", "inc": .92, "syn": 0, "list": "Lands"}


def test_answers_are_cached_and_an_old_one_is_used_when_edhrec_is_down():
    calls = []
    def fetch(s):
        calls.append(s)
        return EDHREC
    first = upgrades.for_commander("Atraxa, Praetors' Voice", fetch=fetch, pricer=lambda names: {"Sol Ring": 1.0})
    assert calls == ["atraxa-praetors-voice"] and first["url"].endswith("/commanders/atraxa-praetors-voice")
    upgrades.for_commander("Atraxa, Praetors' Voice", fetch=fetch, pricer=None)
    assert len(calls) == 1   # from the cache

    cache = upgrades._read_cache()
    cache["atraxa-praetors-voice"]["fetched"] = time.time() - upgrades.TTL - 1
    upgrades._write_cache(cache)
    def down(s):
        raise requests.ConnectionError("down")
    old = upgrades.for_commander("Atraxa, Praetors' Voice", fetch=down, pricer=None)
    assert old["stale"] and len(old["cards"]) == 4
    with pytest.raises(LookupError):
        upgrades.for_commander("Someone Else", fetch=down, pricer=None)


def test_prices_turn_into_cad():
    data = upgrades.for_commander("Atraxa, Praetors' Voice", fetch=lambda s: EDHREC,
                                  pricer=lambda names: {"Sol Ring": 2.0})
    cards = {c["n"]: c for c in upgrades.priced(data)["cards"]}
    assert cards["Sol Ring"]["p"] == 3.0 and cards["Big Bird"]["p"] is None
    assert "usd" not in cards["Sol Ring"]


def test_cheapest_usd_asks_scryfall_in_batches():
    urls = []
    def get(url):
        urls.append(url)
        return {"data": [{"name": "Fire // Ice", "prices": {"usd": "0.25"}}]}
    names = [f"Card {i}" for i in range(40)]
    found = upgrades.cheapest_usd(names, get=get)
    assert len(urls) == 2 and "prefer%3Ausd-low" in urls[0]
    assert found == {"Fire // Ice": .25, "Fire": .25}


def test_route_needs_a_commander_and_says_when_offline(db):  # noqa: F811
    client = create_app(Scanner(db, None, source=None, live=None)).test_client()
    assert client.get("/api/decks/upgrades").status_code == 400
    r = client.get("/api/decks/upgrades?commander=Atraxa")
    assert r.status_code == 503 and "offline" in r.get_json()["error"]
    # Saved answers still work offline.
    upgrades.for_commander("Atraxa", fetch=lambda s: EDHREC, pricer=lambda names: {"Sol Ring": 2.0})
    js = client.get("/api/decks/upgrades?commander=Atraxa").get_json()
    assert js["decks"] == 1000 and any(c["p"] == 3.0 for c in js["cards"])


def test_decks_page_has_the_upgrade_panel(db):  # noqa: F811
    html = create_app(Scanner(db, None, source=None)).test_client().get("/decks").get_data(as_text=True)
    assert 'id="upgrades"' in html and 'src="/static/upgrades.js"' in html
