"""Commander Vault inside the sorter: the card database, the Canadian price check, imports,
sources, the trade binder and the games log."""

import csv
import gzip
import json

import pytest

from app import Scanner, create_app
from mtgscanner import ca_prices, carddb, config, play, vault
from mtgscanner.collection import COLUMNS, ensure_columns
from mtgscanner.live import Live
from test_library import fake_fetch
from test_scanner import db  # noqa: F401  (db is a fixture)


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "VAULT_PRICES", tmp_path / "vault_prices.json")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")
    return tmp_path


def make(db, live=None):  # noqa: F811
    scanner = Scanner(db, None, source=None, live=live)
    return scanner, create_app(scanner).test_client()


def rows():
    with config.COLLECTION_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --- The Commander card database -----------------------------------------------------------

def oracle(name, **extra):
    return {"name": name, "cmc": 2, "type_line": "Creature — Elf", "oracle_text": "Draw a card.", "mana_cost": "{1}{G}",
            "color_identity": ["G"], "rarity": "rare", "legalities": {"commander": "legal"}, "layout": "normal",
            "power": "2", "toughness": "1", "edhrec_rank": 5} | extra


def test_card_rows_keep_what_the_builder_needs():
    row = carddb.card_row(oracle("Elf", game_changer=True))
    assert row == {"n": "Elf", "m": "{1}{G}", "v": 2, "t": "Creature — Elf", "o": "Draw a card.", "ci": "G", "r": "r",
                   "pt": "2/1", "gc": 1, "e": 5}
    assert carddb.card_row(oracle("Banned", legalities={"commander": "banned"}))["b"] == 1
    assert carddb.card_row(oracle("Not legal", legalities={"commander": "not_legal"})) is None
    assert carddb.card_row(oracle("Token", layout="token")) is None
    faces = carddb.card_row({"name": "A // B", "cmc": 3, "type_line": "Creature // Land", "color_identity": ["U"],
                             "rarity": "mythic", "legalities": {"commander": "legal"},
                             "card_faces": [{"name": "A", "mana_cost": "{2}{U}", "type_line": "Creature", "oracle_text": "Fly.",
                                             "power": "3", "toughness": "3"}, {"name": "B", "type_line": "Land"}]})
    assert faces["m"] == "{2}{U}" and faces["pt"] == "3/3" and "A {2}{U}" in faces["o"]


def test_build_and_serve_the_card_database(db, tmp_path):  # noqa: F811
    src = tmp_path / "oracle.jsonl.gz"
    with gzip.open(src, "wt", encoding="utf-8") as f:
        for i in range(1100):
            f.write(json.dumps(oracle(f"Card {i:04}")) + "\n")
        f.write(json.dumps(oracle("Nope", legalities={})) + "\n")
    assert carddb.build(src) == 1100
    assert carddb.info()["cards"] == 1100
    _, client = make(db)
    res = client.get("/api/carddb", headers={"Accept-Encoding": "gzip"})
    assert res.status_code == 200 and res.headers["Content-Encoding"] == "gzip"
    data = json.loads(gzip.decompress(res.data))
    assert data["n"] == 1100 and data["cards"][0]["n"] == "Card 0000"
    assert json.loads(client.get("/api/carddb").data)["n"] == 1100


def test_a_tiny_download_never_replaces_the_database(tmp_path):
    src = tmp_path / "oracle.jsonl.gz"
    with gzip.open(src, "wt", encoding="utf-8") as f:
        f.write(json.dumps(oracle("Only one")) + "\n")
    with pytest.raises(RuntimeError):
        carddb.build(src)
    assert not carddb.db_file().exists()


# --- The Canadian price check --------------------------------------------------------------------

def shop_for(products: dict, variants: dict):
    """A Shop whose stores answer from these dicts: host -> search results, handle -> variants."""
    def get(url):
        for handle, vs in variants.items():
            if f"/products/{handle}.js" in url:
                return {"variants": vs}
        for host, found in products.items():
            if url.startswith(host) and "/search/suggest.json" in url:
                return {"resources": {"results": {"products": found}}}
        raise ConnectionError(url)
    return ca_prices.Shop(get=get, pause=0)


F2F, MYTH = ca_prices.STORES["f2f"][1], ca_prices.STORES["myth"][1]


def test_store_price_picks_near_mint_and_skips_other_products():
    shop = shop_for(
        {F2F: [{"title": "Sol Ring [Commander 2021]", "handle": "sr-c21", "price_min": "2.00"},
               {"title": "Sol Ring [Commander 2021] [Foil]", "handle": "sr-foil", "price_min": "9.00"},
               {"title": "Sol Ring (Oversized) [Promo]", "handle": "big", "price_min": "1.00"},
               {"title": "Sol Ring Token", "handle": "tok", "price_min": "0.10"}]},
        {"sr-c21": [{"title": "NM", "price": 249, "available": False}, {"title": "Near Mint", "price": 299, "available": True},
                    {"title": "Lightly Played", "price": 150, "available": True}],
         "sr-foil": [{"title": "NM", "price": 999, "available": True}],
         "big": [{"title": "NM", "price": 100, "available": True}]})
    assert ca_prices.store_price(shop, "f2f", "Sol Ring") == [2.99, 1, 9.99]   # in stock beats a cheaper sold-out copy
    assert ca_prices.store_price(shop, "f2f", "Mana Crypt") is None


def test_check_saves_prices_and_keeps_last_week_for_trends():
    ca_prices.save({"prices": {"Sol Ring": {"f2f": [1.5, 1, None]}, "Gone Card": {"myth": [4.0, 1, None]}}})
    shop = shop_for({F2F: [{"title": "Sol Ring [C21]", "handle": "sr", "price_min": "2"}], MYTH: []},
                    {"sr": [{"title": "NM", "price": 299, "available": True}]})
    data = ca_prices.check(["Sol Ring"], [], shop=shop, workers=1)
    assert data["prices"]["Sol Ring"] == {"f2f": [2.99, 1, None]}
    assert data["prices"]["Gone Card"] == {"myth": [4.0, 1, None]}   # not answered this week: kept
    assert data["prev"] == {"Sol Ring": 1.5, "Gone Card": 4.0}
    assert json.loads(config.VAULT_PRICES.read_text())["checked"]


def test_main_price_is_face_to_face_first():
    assert ca_prices.main_price({"f2f": [3.0, 0, None], "401": [1.0, 1, None]}) == 3.0
    assert ca_prices.main_price({"401": [2.0, 0, None], "hob": [2.5, 1, None]}) == 2.5


def test_wanted_names_and_valuable_printings():
    collection = [{"Name": "Sol Ring", "Set code": "C21", "Collector number": "263", "Foil": "normal", "Price CAD": "3.00"},
                  {"Name": "Island", "Set code": "FDN", "Collector number": "1", "Foil": "foil"},
                  {"Name": "Bulk", "Set code": "FDN", "Collector number": "9", "Foil": "normal", "Price CAD": "0.10"}]
    names, keys = ca_prices.wanted(collection, ["Arcane Signet", "Forest"], ["Mana Crypt"], ["Bulk"])
    assert names == ["Arcane Signet", "Bulk", "Mana Crypt", "Sol Ring"]
    assert keys == ["Island|FDN|1|1", "Sol Ring|C21|263|0"]


# --- Sources: ManaBox CSVs ---------------------------------------------------------------------------

MANABOX = """Name,Set code,Set name,Collector number,Foil,Rarity,Quantity,ManaBox ID,Scryfall ID,Purchase price,Misprint,Altered,Condition,Language,Purchase price currency
Sol Ring,C21,Commander 2021,263,normal,uncommon,2,1,abc,1.50,false,false,near_mint,en,CAD
"Ajani, Caller of the Pride",M13,Magic 2013,1,foil,mythic,1,2,def,4.00,false,false,near_mint,en,USD
"""


def test_manabox_csv_becomes_its_own_source(db):  # noqa: F811
    _, client = make(db)
    preview = client.post("/api/sources/manabox", json={"csv": MANABOX, "preview": True}).get_json()
    assert (preview["cards"], preview["rows"]) == (3, 2)
    assert not config.COLLECTION_CSV.exists()
    js = client.post("/api/sources/manabox", json={"csv": MANABOX, "name": "New pulls"}).get_json()
    assert js["source"] == "New pulls" and js["cards"] == 3
    got = rows()
    assert [(r["Name"], r["Quantity"], r["Foil"], r["Source"]) for r in got] == [
        ("Sol Ring", "2", "normal", "New pulls"), ("Ajani, Caller of the Pride", "1", "foil", "New pulls")]
    assert got[0]["Price CAD"] == "1.50" and got[1]["Price CAD"] == ""    # a USD purchase price isn't used
    again = client.post("/api/sources/manabox", json={"csv": MANABOX, "name": "New pulls"}).get_json()
    assert again["source"] == "New pulls (2)"
    names = [s["name"] for s in client.get("/api/sources").get_json()["sources"]]
    assert names == ["New pulls", "New pulls (2)"]
    res = client.post("/api/sources/remove", json={"name": "New pulls"}).get_json()
    assert res["removed"] == 2 and [s["name"] for s in res["sources"]] == ["New pulls (2)"]
    assert client.post("/api/sources/manabox", json={"csv": "a,b\n1,2"}).status_code == 400


def test_imports_are_filled_in_from_scryfall(db):  # noqa: F811
    found = {"id": "11111111-2222-3333-4444-555555555555", "name": "Sol Ring", "set": "c21", "set_name": "Commander 2021",
             "collector_number": "263", "rarity": "uncommon", "colors": [], "prices": {"usd": "1.00"}}
    live = Live(fetch=fake_fetch({"/cards/collection": {"data": [found]}}))
    scanner, client = make(db, live)
    client.post("/api/sources/manabox", json={"csv": MANABOX.splitlines()[0] + "\n" + MANABOX.splitlines()[1], "name": "x"})
    r = rows()[0]
    assert (r["Scryfall ID"], r["Set name"], r["Rarity"]) == (found["id"], "Commander 2021", "uncommon")
    assert scanner.matcher.find_card(found["id"]).name == "Sol Ring"     # remembered, so it has a picture


def test_old_csv_gets_the_source_column_without_losing_cards(db):  # noqa: F811
    old = COLUMNS[:-1]
    with config.COLLECTION_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(old)
        w.writerow(["Card 1", 1, "TST", "Test Set", "1", "normal", "rare", "id1", "4.50", "x", "Bin 2", "2026-10-01T10:00:00"])
    ensure_columns(config.COLLECTION_CSV)
    with config.COLLECTION_CSV.open(newline="", encoding="utf-8") as f:
        assert next(csv.reader(f)) == COLUMNS
    _, client = make(db)
    client.post("/api/add", json={"id": "id2"})
    got = rows()
    assert [(r["Name"], r["Source"]) for r in got] == [("Card 1", ""), ("Card 2", "")]


def test_undo_takes_back_the_scanned_card_not_an_import(db):  # noqa: F811
    _, client = make(db)
    client.post("/api/add", json={"id": "id1"})
    client.post("/api/sources/manabox", json={"csv": MANABOX, "name": "Pulls"})
    client.post("/api/undo")
    assert [r["Name"] for r in rows()] == ["Sol Ring", "Ajani, Caller of the Pride"]


# --- Bringing in Commander Vault ------------------------------------------------------------------

EXPORT = {
    "commander_vault": 1,
    "collection": [{"id": "mb-1", "name": "ManaBox scan, Oct 8", "added": "2026-10-08T23:01:44Z",
                    "cards": [{"n": "Sol Ring", "q": 2, "set": "C21", "cn": "263", "f": 0, "pr": 1.25},
                              {"n": "Ingris Stingerquill", "q": 1, "set": "FRA", "cn": "419", "f": 1}]},
                   {"id": "precon", "name": "Wretched Ranks precon", "added": "2026-10-08T12:00:00Z",
                    "cards": [{"n": "Ghoulcaller Gisa", "q": 1}]}],
    "decks": [{"id": "wretched", "name": "Wretched Ranks", "commander": "Ghoulcaller Gisa", "proxied": True,
               "guide": "wretched.html", "list": [["Sol Ring", 1], ["Swamp", 30]]}],
    "trades": {"cards": [{"n": "Ingris Stingerquill", "set": "FRA", "cn": "419", "f": 1, "q": 1}],
               "wants": [{"n": "Mana Crypt", "max": 200}]},
    "games": [{"id": "g1", "date": "2026-10-20", "winner": 1, "players": [{"guest": "Sam", "deck": "Doom"}, {"name": "Nic", "deck": "Vito"}]}],
    "prices": {"date": "Nov 1, 2026", "prices": {"Sol Ring": {"f2f": [2.49, 1, 6.0]}},
               "printings": {"Ingris Stingerquill|FRA|419|1": [299.99, 1, "Face to Face Games"]}},
    "guides": {"wretched.html": '<a href="index.html">Back</a> Guide', "../evil.html": "no"},
}


def test_import_everything_from_commander_vault(db):  # noqa: F811
    scanner, client = make(db)
    did = client.post("/api/vault/import", json=EXPORT).get_json()["imported"]
    assert did == {"sources": 2, "cards": 4, "decks": 1, "wishlist": 1, "trade": 1, "games": 1, "prices": 1, "guides": 1}
    got = rows()
    assert [(r["Name"], r["Quantity"], r["Source"], r["Scanned at"]) for r in got] == [
        ("Sol Ring", "2", "ManaBox scan, Oct 8", "2026-10-08T23:01:44"),
        ("Ingris Stingerquill", "1", "ManaBox scan, Oct 8", "2026-10-08T23:01:44"),
        ("Ghoulcaller Gisa", "1", "Wretched Ranks precon", "2026-10-08T12:00:00")]
    assert got[0]["Price CAD"] == "1.25"
    deck = client.get("/api/decks").get_json()["decks"][0]
    assert deck["name"] == "Wretched Ranks" and deck["proxied"] and deck["guide"] == "/guides/wretched.html"
    assert deck["text"].splitlines()[:4] == ["Commander", "1 Ghoulcaller Gisa", "", "Deck"]
    assert "Back" in client.get("/guides/wretched.html").get_data(as_text=True)
    assert 'href="/decks"' in client.get("/guides/wretched.html").get_data(as_text=True)
    assert scanner.vault and scanner.vault.date == "Nov 1, 2026"   # the scanner sorts by these prices right away
    binder = client.get("/api/trades").get_json()
    assert binder["cards"][0]["name"] == "Ingris Stingerquill" and binder["value"] == 299.99
    assert client.get("/api/wishlist").get_json()["items"][0]["target"] == 200
    games = client.get("/api/games").get_json()
    assert games["games"][0]["players"][0]["name"] == "Sam" and games["stats"]["players"][0]["label"] == "Nic"
    # Twice is safe: nothing new comes in.
    again = client.post("/api/vault/import", json=EXPORT).get_json()["imported"]
    assert again["sources"] == again["decks"] == again["games"] == again["trade"] == again["prices"] == 0
    assert len(rows()) == 3
    assert client.post("/api/vault/import", json={"hello": 1}).status_code == 400


def test_vault_prices_endpoint_and_status(db):  # noqa: F811
    _, client = make(db)
    client.post("/api/vault/import", json=EXPORT)
    prices = client.get("/api/vault/prices").get_json()
    assert prices["prices"]["Sol Ring"]["f2f"][0] == 2.49
    st = client.get("/api/vault").get_json()
    assert st["prices"]["cards"] == 1 and st["prices"]["imported"] and st["offline"]
    assert client.post("/api/vault/run", json={"job": "prices"}).status_code == 400   # offline


def test_weekly_jobs_come_due(db):  # noqa: F811
    scanner, _ = make(db)
    weekly = vault.Weekly(scanner)
    assert weekly.due() == "carddb"
    (config.DATA_DIR / "carddb.json").write_text("{}")
    assert weekly.due() == "prices"
    ca_prices.save({"prices": {"Sol Ring": {}}, "checked": "2026-01-01T00:00:00"})
    assert weekly.due() == "prices"      # older than a week
    from datetime import datetime
    ca_prices.save({"prices": {"Sol Ring": {}}, "checked": datetime.now().isoformat(timespec="seconds")})
    assert weekly.due() is None


# --- Games and the trade binder -------------------------------------------------------------------

def test_games_log_and_win_rates(db):  # noqa: F811
    _, client = make(db)
    for winner in (0, 0, 1):
        js = client.post("/api/games/add", json={"date": "2026-11-01", "turns": "9", "winner": winner,
                                                 "players": [{"name": "Nic", "deck": "Vito"}, {"name": "Sam", "deck": ""}]}).get_json()
    assert len(js["games"]) == 3
    assert js["stats"]["players"][0] == {"label": "Nic", "games": 3, "wins": 2}
    assert js["stats"]["decks"] == [{"label": "Vito", "games": 3, "wins": 2}]
    assert client.post("/api/games/add", json={"players": [{"name": "Solo"}]}).status_code == 400
    js = client.post("/api/games/delete", json={"id": js["games"][0]["id"]}).get_json()
    assert len(js["games"]) == 2


def test_trade_binder(db):  # noqa: F811
    _, client = make(db)
    js = client.post("/api/trades/add", json={"name": "Card 1", "set": "tst", "number": "1", "qty": 2, "card_id": "id1"}).get_json()
    assert js["cards"][0]["set"] == "TST" and js["value"] == pytest.approx(2 * js["cards"][0]["price"])
    js = client.post("/api/trades/add", json={"name": "Card 1", "set": "TST", "number": "1"}).get_json()
    assert len(js["cards"]) == 1                      # already in it
    js = client.post("/api/trades/remove", json={"id": js["cards"][0]["key"]}).get_json()
    assert js["cards"] == []
    assert play.load_binder() == []


def test_new_pages_load(db):  # noqa: F811
    _, client = make(db)
    for page, script in (("/cards", "cards.js"), ("/play", "play.js"), ("/decks", "builder.js")):
        html = client.get(page).get_data(as_text=True)
        assert f'src="/static/{script}"' in html, page
        assert client.get(f"/static/{script}").status_code == 200
    assert client.get("/api/carddb").status_code == 404     # not built yet: says how to get it
