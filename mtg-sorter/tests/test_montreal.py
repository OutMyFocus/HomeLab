"""Montreal store prices: Face to Face Games first, then Card Brawlers and L'Univers de la Carte."""

import time

from mtgscanner import ca_prices, config, montreal
from mtgscanner.vault_prices import VaultPrices
from test_scanner import db  # noqa: F401  (db is a fixture)
from test_vault import data_dir, make, shop_for  # noqa: F401  (data_dir is an autouse fixture)

F2F, CB, UDC = (ca_prices.STORES[k][1] for k in ("f2f", "cb", "udc"))


def stores():
    return shop_for(
        {F2F: [{"title": "Sol Ring [499] [Star Trek: Commander] [Non-Foil]", "handle": "sr-st", "price_min": "2.99"},
               {"title": "Sol Ring [263] [Commander 2021] [Non-Foil]", "handle": "sr-c21", "price_min": "3.99"},
               {"title": "Sol Ring [263] [Commander 2021] [Foil]", "handle": "sr-c21-f", "price_min": "12.00"},
               {"title": "Sol Ring Token", "handle": "tok", "price_min": "0.10"}],
         CB: [{"title": "Sol Ring [Commander 2021]", "handle": "cb-sr", "price_min": "0.50"}],
         UDC: [{"title": "Sol Ring [C21 - 263]", "handle": "udc-sr", "price_min": "3.25"},
               {"title": "Sol Ring [3ED - 274]", "handle": "udc-3ed", "price_min": "36.99"}]},
        {"sr-st": [{"title": "NM", "price": 299, "available": True}],
         "sr-c21": [{"title": "NM", "price": 399, "available": True}, {"title": "PL", "price": 250, "available": True}],
         "sr-c21-f": [{"title": "NM", "price": 1200, "available": True}],
         "cb-sr": [{"title": "Near Mint", "price": 250, "available": False}, {"title": "Damaged", "price": 50, "available": True},
                   {"title": "Near Mint Foil", "price": 1100, "available": True}],
         "udc-sr": [{"title": "Near Mint / French / Normal", "price": 200, "available": True},
                    {"title": "Near Mint / English / Normal", "price": 325, "available": True}],
         "udc-3ed": [{"title": "Near Mint / English / Normal", "price": 3699, "available": True}]})


def test_printing_is_read_from_each_stores_titles():
    assert montreal.printing_of("f2f", "Sol Ring [1011] [Borderless] [Secret Lair Drop] [Non-Foil]") == \
        {"number": "1011", "set_name": "Secret Lair Drop"}
    assert montreal.printing_of("udc", "Counterspell (Retro Frame) [DMR - 281]") == {"set": "DMR", "number": "281"}
    assert montreal.printing_of("cb", "Spell Pierce [Zendikar]") == {"set_name": "Zendikar"}
    assert montreal.printing_of("cb", "Spell Pierce (SOA-023) - Secrets of Strixhaven") == \
        {"set": "SOA", "number": "023", "set_name": "Secrets of Strixhaven"}
    assert montreal.same_printing({"set": "C21", "number": "263"}, "c21", "Commander 2021", "263")
    assert not montreal.same_printing({"set": "3ED", "number": "274"}, "C21", "Commander 2021", "263")
    assert not montreal.same_printing({}, "C21", "Commander 2021", "263")   # no clues: not "this printing"


def test_each_store_gives_this_printing_before_a_cheaper_one():
    shop = stores()
    f2f = montreal.store_lookup(shop, "f2f", "Sol Ring", "C21", "Commander 2021", "263")
    assert (f2f["price"], f2f["exact"], f2f["url"]) == (3.99, True, F2F + "/products/sr-c21")   # not the $2.99 Star Trek one
    cheapest = montreal.store_lookup(shop, "f2f", "Sol Ring", "SLD", "Secret Lair Drop", "9999")
    assert (cheapest["price"], cheapest["exact"]) == (2.99, False)
    foil = montreal.store_lookup(shop, "f2f", "Sol Ring", "C21", "Commander 2021", "263", foil=True)
    assert foil["price"] == 12.0
    udc = montreal.store_lookup(shop, "udc", "Sol Ring", "C21", "Commander 2021", "263")
    assert (udc["price"], udc["exact"], udc["in_stock"]) == (3.25, True, True)          # the English copy
    cb = montreal.store_lookup(shop, "cb", "Sol Ring", "C21", "Commander 2021", "263")
    assert (cb["price"], cb["in_stock"]) == (2.5, False)                                  # Near Mint, sold out
    assert montreal.store_lookup(shop, "cb", "Sol Ring", foil=True)["price"] == 11.0
    assert montreal.store_lookup(shop, "f2f", "Mana Crypt") is None


def test_lookup_is_face_to_face_first_and_remembered():
    calls = []
    shop = stores()
    get = shop._get
    shop._get = lambda url: calls.append(url) or get(url)
    m = montreal.Montreal(shop=shop)
    found, fresh = m.lookup("Sol Ring", "C21", "Commander 2021", "263")
    assert fresh and [s["key"] for s in sorted(found, key=lambda s: montreal.MONTREAL.index(s["key"]))] == ["f2f", "cb", "udc"]
    n = len(calls)
    again, fresh = m.lookup("Sol Ring", "c21", "commander 2021", "0263")
    assert not fresh and again == found and len(calls) == n


def test_weekly_prices_for_the_collection():
    vault = VaultPrices({"date": "Nov 1, 2026", "prices": {
        "Sol Ring": {"401": [1.0, 1, None], "udc": [3.25, 1, 7.0], "f2f": [3.99, 0, 12.0]},
        "Fire": {"cb": [0.5, 1, None]}}})
    assert [s["key"] for s in montreal.weekly(vault, "Sol Ring")] == ["f2f", "udc"]   # 401 isn't in Montreal
    assert montreal.first(vault, "Sol Ring") == {"price": 3.99, "store": "Face to Face Games"}
    assert montreal.first(vault, "Sol Ring", foil=True) == {"price": 12.0, "store": "Face to Face Games"}
    assert montreal.first(vault, "Fire // Ice") == {"price": 0.5, "store": "Card Brawlers"}
    assert montreal.first(vault, "Mana Crypt") is None and montreal.first(None, "Sol Ring") is None
    assert [l["store"] for l in montreal.links("Fire // Ice")] == ["Carta Magica", "L'Expédition", "Le Valet d'Coeur"]
    assert "q=Fire" in montreal.links("Fire // Ice")[0]["url"]


def test_montreal_endpoint_offline_uses_the_weekly_check(db):  # noqa: F811
    ca_prices.save({"date": "Nov 1, 2026", "prices": {"Sol Ring": {"f2f": [2.49, 1, 6.0], "cb": [2.0, 1, None]}}})
    scanner, client = make(db)
    scanner.vault = VaultPrices.load(config.VAULT_PRICES)
    d = client.get("/api/montreal?name=Sol+Ring&set=C21&number=263").get_json()
    assert d["checked"] == "weekly" and d["date"] == "Nov 1, 2026"
    assert [(s["store"], s["price"]) for s in d["stores"]] == [("Face to Face Games", 2.49), ("Card Brawlers", 2.0)]
    assert len(d["links"]) == 3
    assert client.get("/api/montreal").status_code == 400
    # The collection's Montreal column comes from the same weekly prices.
    from mtgscanner.library import holdings
    rows = [{"Scryfall ID": "x1", "Name": "Sol Ring", "Set code": "C21", "Collector number": "263", "Quantity": "1"}]
    assert holdings(rows, None, scanner.vault)[0]["mtl"] == {"price": 2.49, "store": "Face to Face Games"}


def test_montreal_endpoint_checks_the_stores_live(db):  # noqa: F811
    scanner, client = make(db)
    client.application.config["montreal"].offline = False
    client.application.config["montreal"].shop = stores()
    d = client.get("/api/montreal?name=Sol+Ring&set=C21&set_name=Commander+2021&number=263").get_json()
    assert d["checked"] == "today"
    assert [s["store"] for s in d["stores"]] == ["Face to Face Games", "Card Brawlers", "L'Univers de la Carte"]
    assert d["stores"][0]["exact"] and d["stores"][0]["price"] == 3.99


def test_a_store_that_failed_is_asked_again_soon():
    shop = stores()
    get, broken = shop._get, {"f2f": True}

    def flaky(url):
        if url.startswith(F2F) and broken["f2f"]:
            raise ConnectionError(url)
        return get(url)
    shop._get = flaky
    m = montreal.Montreal(shop=shop)
    missed = []
    found, fresh = m.lookup("Sol Ring", "C21", "Commander 2021", "263", missed=missed)
    assert fresh and [s["key"] for s in found] == ["cb", "udc"] and missed == ["f2f"]
    broken["f2f"] = False
    found, fresh = m.lookup("Sol Ring", "C21", "Commander 2021", "263")
    assert not fresh                                     # within the couple of minutes: not yet
    key = next(iter(m.cache))
    stamp, cached, failed = m.cache[key]
    m.cache[key] = (stamp - montreal.RETRY_SECONDS - 1, cached, failed)
    found, fresh = m.lookup("Sol Ring", "C21", "Commander 2021", "263")
    assert fresh and [s["key"] for s in found] == ["f2f", "cb", "udc"]   # Face to Face is back
    stamp, _, failed = next(iter(m.cache.values()))
    assert failed == () and time.time() - stamp < 5    # a full answer is kept the usual 12 hours


def test_a_slow_store_doesnt_hold_up_the_scanner():
    import threading
    shop, release = stores(), threading.Event()
    get = shop._get
    shop._get = lambda url: (release.wait(5), get(url))[1] if url.startswith(F2F) else get(url)
    m = montreal.Montreal(shop=shop, deadline=0.3)
    start = time.time()
    missed = []
    found, _ = m.lookup("Sol Ring", "C21", "Commander 2021", "263", missed=missed)
    release.set()
    assert time.time() - start < 3
    assert [s["key"] for s in found] == ["cb", "udc"] and missed == ["f2f"]


def test_missing_store_shows_its_weekly_price(db):  # noqa: F811
    ca_prices.save({"date": "Nov 1, 2026", "prices": {"Sol Ring": {"f2f": [2.49, 1, 6.0], "cb": [2.0, 1, None]}}})
    scanner, client = make(db)
    scanner.vault = VaultPrices.load(config.VAULT_PRICES)
    m = client.application.config["montreal"]
    shop = stores()
    get = shop._get
    shop._get = lambda url: (_ for _ in ()).throw(ConnectionError(url)) if url.startswith(F2F) else get(url)
    m.offline, m.shop = False, shop
    d = client.get("/api/montreal?name=Sol+Ring&set=C21&set_name=Commander+2021&number=263").get_json()
    assert d["checked"] == "today"
    assert [(s["key"], s.get("checked")) for s in d["stores"]] == [("f2f", "weekly"), ("cb", None), ("udc", None)]
    assert d["stores"][0]["price"] == 2.49


# --- The USD to CAD rate ------------------------------------------------------------------------

class Rate:
    def __init__(self, rate="1.3900", fail=False):
        self.rate, self.fail, self.calls = rate, fail, 0

    def __call__(self, url, **kw):
        import requests
        self.calls += 1
        if self.fail:
            raise requests.ConnectionError("offline")
        rate = self.rate

        class R:
            def json(self):
                return {"observations": [{"d": "2026-11-17", "FXUSDCAD": {"v": rate}}]}
        return R()


def test_exchange_rate_is_kept_for_a_day(tmp_path, monkeypatch):
    import json
    from mtgscanner import exchange
    monkeypatch.setattr(exchange, "CACHE", tmp_path / "usd_cad.json")
    monkeypatch.setattr(config, "USD_TO_CAD", 1.35)
    fake = Rate()
    monkeypatch.setattr(exchange.requests, "get", fake)
    assert exchange.load_rate() == (1.39, "2026-11-17") and config.USD_TO_CAD == 1.39
    assert exchange.load_rate() == (1.39, "2026-11-17") and fake.calls == 1        # fresh: not fetched again
    saved = json.loads(exchange.CACHE.read_text())
    exchange.CACHE.write_text(json.dumps(saved | {"fetched": saved["fetched"] - 3 * 86400}))
    fake.rate = "1.4100"
    assert exchange.load_rate()[0] == 1.41 and fake.calls == 2                       # a day old: fetched again
    exchange.CACHE.write_text(json.dumps(saved | {"fetched": 0}))
    fake.fail = True
    assert exchange.load_rate()[0] == 1.39                                           # offline: the saved rate


def test_a_damaged_rate_file_never_stops_the_app(tmp_path, monkeypatch):
    from mtgscanner import exchange
    monkeypatch.setattr(exchange, "CACHE", tmp_path / "usd_cad.json")
    monkeypatch.setattr(config, "USD_TO_CAD", 1.35)
    monkeypatch.setattr(exchange.requests, "get", Rate(fail=True))
    for junk in ("null", "[]", '{"fetched": "x"}', '{"fetched": 1}', '{"rate": "x", "fetched": 1}', "{bad"):
        exchange.CACHE.write_text(junk)
        assert exchange.load_rate() == (1.35, ""), junk
    monkeypatch.setattr(exchange.requests, "get", Rate())
    exchange.CACHE.write_text("null")
    assert exchange.load_rate()[0] == 1.39 and exchange.CACHE.read_text().startswith("{")
