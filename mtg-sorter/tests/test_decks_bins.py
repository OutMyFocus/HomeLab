"""The Decks page (decklist vs collection) and the Bins page (sorting rules)."""

import pytest

from app import Scanner, create_app
from mtgscanner import config, decks, sort_rules
from mtgscanner.database import Card
from mtgscanner.live import Live
from mtgscanner.sorting import choose_bin
from test_library import fake_fetch, scryfall_card
from test_scanner import db  # noqa: F401  (db is a fixture)


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")
    monkeypatch.setattr(config, "USD_TO_CAD", 1.5)
    sort_rules._cache["rules"] = None
    yield
    sort_rules._cache["rules"] = None


def make_client(db, live=None):  # noqa: F811
    return create_app(Scanner(db, None, source=None, live=live)).test_client()


# --- Decklists -------------------------------------------------------------------------------

def test_parse_understands_common_formats():
    text = """Deck
4 Lightning Bolt
1x Sol Ring (C21) 263
2 Counterspell *F*
Card 1

// a comment
Sideboard
SB: 2 Duress
Duress
1 Fable of the Mirror-Breaker // Reflection of Kiki-Jikiu
4 Lightning Bolt
"""
    got = {(x["section"], x["name"]): x["qty"] for x in decks.parse(text)}
    assert got == {("Main deck", "Lightning Bolt"): 4, ("Main deck", "Sol Ring"): 1, ("Main deck", "Counterspell"): 2,
                   ("Main deck", "Card 1"): 1, ("Sideboard", "Duress"): 3,
                   ("Sideboard", "Fable of the Mirror-Breaker // Reflection of Kiki-Jikiu"): 1,
                   ("Sideboard", "Lightning Bolt"): 4}


def test_check_counts_owned_missing_and_cost(db):  # noqa: F811
    client = make_client(db)
    for _ in range(2):
        client.post("/api/add", json={"id": "id1"})            # 2 x Card 1, US$4.50 each
    res = client.post("/api/decks/check", json={"text": "3 Card 1\n1 Card 2\nSideboard\n1 Card 1\n1 Nonsense Card"}).get_json()
    lines = {(x["section"], x["name"]): x for x in res["lines"]}
    main = lines[("Main deck", "Card 1")]
    assert (main["need"], main["have"], main["missing"]) == (3, 2, 1)
    assert lines[("Sideboard", "Card 1")]["have"] == 0          # the 2 copies are used once
    assert lines[("Main deck", "Card 2")]["cost"] == 37.5         # US$25 x 1.5, from the database
    assert res["unknown"] == ["Nonsense Card"]
    assert res["need"] == 6 and res["have"] == 2 and res["missing"] == 4
    assert res["cost"] == round(37.5 + 2 * 6.75, 2)
    assert main["where"][0]["qty"] == 2


def test_check_prices_missing_cards_from_scryfall(db):  # noqa: F811
    live = Live(fake_fetch({"/cards/collection": lambda body: {"data": [
        scryfall_card("aaaaaaaa-0000-0000-0000-000000000000", "Lightning Bolt", usd="2.00")
        for i in body["identifiers"] if i.get("name", "").lower() == "lightning bolt"]}}))
    res = make_client(db, live).post("/api/decks/check", json={"text": "4 lightning bolt"}).get_json()
    assert res["lines"][0]["name"] == "Lightning Bolt" and res["cost"] == 12.0 and not res["unknown"]


def test_check_needs_a_list(db):  # noqa: F811
    assert make_client(db).post("/api/decks/check", json={"text": "  \n// nothing"}).status_code == 400


def test_save_and_delete_decks(db):  # noqa: F811
    client = make_client(db)
    deck = client.post("/api/decks/save", json={"name": "Burn", "text": "4 Lightning Bolt"}).get_json()["deck"]
    client.post("/api/decks/save", json={"id": deck["id"], "name": "Burn v2", "text": "4 Lightning Bolt\n4 Shock"})
    saved = client.get("/api/decks").get_json()["decks"]
    assert [d["name"] for d in saved] == ["Burn v2"] and "Shock" in saved[0]["text"]
    assert client.post("/api/decks/delete", json={"id": deck["id"]}).status_code == 200
    assert client.get("/api/decks").get_json()["decks"] == []
    assert client.post("/api/decks/delete", json={"id": "nope"}).status_code == 404
    assert client.get("/decks").status_code == 200


# --- Bin rules -------------------------------------------------------------------------------

def card(colors="R", rarity="rare", set_code="dmu"):
    return Card("x", "X", set_code, "Set", "1", rarity, colors, None, None)


def test_default_rules_match_the_price_bins(db):  # noqa: F811
    assert [choose_bin(db.get_card(f"id{i}"))[0] for i in range(4)] == [1, 2, 3, 0]
    assert not sort_rules.is_custom()


def test_rules_first_match_wins():
    rules = sort_rules.clean({"rules": [
        {"bin": 3, "min_price": 10},
        {"bin": 2, "colors": ["R", "G"], "rarities": ["rare", "mythic"]},
        {"bin": 1, "sets": ["dmu"], "foil": "foil"},
        {"bin": 1, "max_price": 0.5},
    ], "fallback": 0, "names": {"3": "Valuable"}})
    pick = lambda c, foil, price: sort_rules.pick(c, foil, price, rules)[0]
    assert pick(card(), False, 12) == 3
    assert sort_rules.pick(card(), False, 12, rules)[1] == "Valuable"
    assert pick(card("R"), False, 2) == 2
    assert pick(card("R,G"), False, 2) == 0            # multicolor isn't R or G
    assert pick(card("U", "common"), True, 2) == 1      # DMU foil
    assert pick(card("U", "common", "one"), False, 0.25) == 1
    assert pick(card("U", "common", "one"), False, None) == 0   # no price fits no price rule
    assert pick(card(None), False, 2) == 0               # color unknown: color rules don't fit


@pytest.mark.parametrize("bad", [
    {"rules": [{"bin": 7}]},
    {"rules": [{"bin": 1, "min_price": "lots"}]},
    {"rules": [{"bin": 1, "min_price": 5, "max_price": 2}]},
    {"rules": [{"bin": 1, "foil": "maybe"}]},
    {"rules": "nope"},
])
def test_bad_rules_are_refused(db, bad):  # noqa: F811
    res = make_client(db).post("/api/bins", json=bad)
    assert res.status_code == 400 and res.get_json()["error"]
    assert not sort_rules.is_custom()


def test_save_preview_and_reset_rules(db):  # noqa: F811
    client = make_client(db)
    client.post("/api/add", json={"id": "id2"})   # rare, US$25
    client.post("/api/add", json={"id": "id0"})   # rare, US$0.10
    preview = client.post("/api/bins/preview", json={"preset": "rarity"}).get_json()
    assert preview["preview"]["3"]["cards"] == 2 and not preview["custom"]
    js = client.post("/api/bins", json=preview["rules"]).get_json()
    assert js["custom"] and js["rules"]["names"]["3"] == "Rares and mythics"
    assert choose_bin(db.get_card("id0")) == (3, "Rares and mythics")      # new scans use the rules
    state = client.get("/api/state").get_json()
    assert state["bin_names"]["1"] == "Commons"
    coll = client.get("/api/collection").get_json()
    assert {c["bin"] for c in coll["cards"]} == {3}
    js = client.post("/api/bins/reset").get_json()
    assert not js["custom"] and choose_bin(db.get_card("id0"))[0] == 1
    assert client.get("/bins").status_code == 200


def test_broken_rules_file_falls_back_to_price_bins(db):  # noqa: F811
    sort_rules.rules_file().write_text("{not json")
    assert choose_bin(db.get_card("id2"))[0] == 3


@pytest.mark.parametrize("name", list(sort_rules.PRESETS))
def test_presets_are_valid(name):
    sort_rules.clean(sort_rules.preset(name))


# --- Wanted cards (pull a list out of the bulk into one bin) ------------------------------------

def named(name, colors="R"):
    return Card("x", name, "dmu", "Set", "1", "rare", colors, None, None)


def wanted_rules(**wanted):
    return sort_rules.clean({**sort_rules.default_rules(), "wanted": {"on": True, **wanted}})


def test_wanted_cards_win_over_the_price_rules():
    rules = wanted_rules(bin=3, only=False, text="Commander\n1 Sol Ring (C21) 263\n4x Lightning Bolt\n"
                                                "1 Fire // Ice\nMaybeboard\n1 Ponder")
    assert [c["name"] for c in rules["wanted"]["cards"]] == ["Sol Ring", "Lightning Bolt", "Fire // Ice"]
    assert sort_rules.pick(named("Sol Ring"), False, 0.25, rules)[0] == 3        # bulk price, still wanted
    assert sort_rules.pick(named("Sol Ring"), False, 0.25, rules)[1] == "Wanted cards"
    assert sort_rules.pick(named("Fire // Ice"), False, 0.25, rules)[0] == 3     # front face matches
    assert sort_rules.pick(named("Ponder"), False, 0.25, rules)[0] == 1          # maybeboard left out
    assert sort_rules.pick(named("Other"), False, 4, rules)[0] == 2
    rules["wanted"]["on"] = False
    assert sort_rules.pick(named("Sol Ring"), False, 0.25, rules)[0] == 1


def test_wanted_only_bin_sends_the_other_cards_elsewhere():
    rules = wanted_rules(bin=2, only=True, others=3, text="1 Sol Ring")
    assert sort_rules.pick(named("Sol Ring"), False, 0.25, rules)[0] == 2
    assert sort_rules.pick(named("Other"), False, 4, rules) == (3, "$10+ (valuable!)")      # $1-$10 kept out of bin 2
    assert sort_rules.pick(named("Other"), False, 0.25, rules)[0] == 1
    empty = wanted_rules(bin=2, only=True, others=3, text="")
    assert sort_rules.pick(named("Other"), False, 4, empty)[0] == 2              # empty list: bin 2 as usual
    with pytest.raises(ValueError):
        wanted_rules(bin=2, only=True, others=2, text="1 Sol Ring")
    with pytest.raises(ValueError):
        wanted_rules(bin=0, text="1 Sol Ring")


def test_wanted_copies_and_basic_lands():
    rules = wanted_rules(bin=3, only=False, text="2 Lightning Bolt\n30 Forest")
    taken = {}
    for want in (3, 3, 1):          # two copies pulled, the third sorted by price
        key = sort_rules.wanted_for(named("Lightning Bolt"), rules, taken)
        assert sort_rules.pick(named("Lightning Bolt"), False, 0.25, rules, taken)[0] == want
        if key:
            taken[key] = taken.get(key, 0) + 1
    assert sort_rules.pick(named("Forest", ""), False, 0.1, rules)[0] == 1        # basics skipped
    rules["wanted"]["skip_basics"] = False
    assert sort_rules.pick(named("Forest", ""), False, 0.1, rules)[0] == 3
    rules["wanted"]["limit"] = False
    assert sort_rules.pick(named("Lightning Bolt"), False, 0.25, rules, {"lightning bolt": 9})[0] == 3


def test_presets_keep_the_wanted_list():
    rules = sort_rules.preset("rarity", {"on": True, "bin": 3, "only": False, "text": "1 Sol Ring"})
    assert rules["wanted"]["cards"] == [{"name": "Sol Ring", "qty": 1}] and rules["names"]["1"] == "Commons"
    assert sort_rules.preset("rarity")["wanted"]["on"] is False


def test_wanted_list_from_a_deck_and_the_bins_page(db):  # noqa: F811
    client = make_client(db)
    client.post("/api/add", json={"id": "id0"})   # Card 0, US$0.10: bulk
    deck = client.post("/api/decks/save", json={"name": "Pauper", "text": "1 Card 0\n4 Lightning Bolt"}).get_json()["deck"]
    js = client.get("/api/bins").get_json()
    assert js["decks"] == [{"id": deck["id"], "name": "Pauper"}] and js["rules"]["wanted"]["on"] is False
    listed = client.post("/api/bins/wanted/list", json={"deck": deck["id"]}).get_json()
    assert listed == {"text": "1 Card 0\n4 Lightning Bolt", "source": "Pauper"}
    assert client.post("/api/bins/wanted/list", json={"deck": "nope"}).status_code == 404
    # the Bins page preview, not saved: Card 0 moves out of bin 1 into bin 3
    rules = {**js["rules"], "wanted": {**js["rules"]["wanted"], "on": True, "bin": 3, "only": False,
                                         "text": listed["text"]}}
    pv = client.post("/api/bins/preview", json=rules).get_json()
    assert pv["preview"]["3"]["cards"] == 1 and pv["preview"]["1"]["cards"] == 0
    assert pv["wanted"]["cards"] == 5 and pv["wanted"]["found"] == 1
    assert pv["wanted"]["missing"] == [{"name": "Lightning Bolt", "qty": 4}]
    assert not sort_rules.is_custom()
    # the deck page's Pull from my bulk: changes the wanted list only
    js = client.post("/api/bins/wanted", json={"on": True, "deck": deck["id"]}).get_json()
    assert js["custom"] and js["rules"]["wanted"]["source"] == "Pauper" and js["rules"]["wanted"]["bin"] == 2
    assert js["rules"]["rules"] == sort_rules.default_rules()["rules"]
    assert choose_bin(db.get_card("id0"))[0] == 2                       # new scans use it too
    bad = client.post("/api/bins/wanted", json={"others": 2})           # bin 2 can't be both
    assert bad.status_code == 400 and bad.get_json()["error"]
