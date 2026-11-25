"""The Bins page rule builder: conditions, all/any, not, presets, and sending rules to the Pi."""

import json

import pytest

from app import Scanner, create_app
from mtgscanner import card_facts, config, decks, sort_rules
from mtgscanner.database import Card
from test_scanner import db  # noqa: F401  (db is a fixture)


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")
    monkeypatch.setattr(config, "USD_TO_CAD", 1.5)
    sort_rules._cache["rules"] = None
    card_facts.forget()
    sort_rules._decks.update(key=None, info=None)
    rows = [
        {"n": "Forest", "v": 0, "t": "Basic Land — Forest", "o": "({T}: Add {G}.)", "ci": "G", "lg": "spmlvucbhxo"},
        {"n": "Command Tower", "v": 0, "t": "Land", "o": "{T}: Add one mana of any color in your commander's color identity.",
         "ci": "", "lg": "lvcbo"},
        {"n": "Llanowar Elves", "v": 1, "t": "Creature — Elf Druid", "o": "{T}: Add {G}.", "ci": "G", "lg": "mlvucbx", "e": 40},
        {"n": "Lightning Bolt", "v": 1, "t": "Instant", "o": "Lightning Bolt deals 3 damage to any target.", "ci": "R",
         "lg": "mlvucx", "e": 20},
        {"n": "Sol Ring", "v": 1, "t": "Artifact", "o": "{T}: Add {C}{C}.", "ci": "", "lg": "vco", "bn": "l", "gc": 1, "e": 1},
        {"n": "Niv-Mizzet, Parun", "v": 6, "t": "Legendary Creature — Dragon Wizard", "o": "Flying", "ci": "UR", "lg": "mlvcb"},
        {"n": "Fire // Ice", "v": 4, "t": "Instant // Instant", "o": "Fire deals 2 damage", "ci": "UR", "lg": "mlvc"},
    ]
    (tmp_path / "carddb.json").write_text(json.dumps({"v": 1, "n": len(rows), "cards": rows}))
    yield
    sort_rules._cache["rules"] = None
    card_facts.forget()


def card(name, colors="", set_code="dmu", rarity="common"):
    return Card("x", name, set_code, "Set", "1", rarity, colors, None, None)


def rules_of(*rules, fallback=0):
    return sort_rules.clean({"rules": list(rules), "fallback": fallback})


def go(rules, c, foil=False, price=1.0, copy=None):
    return sort_rules.pick(c, foil, price, rules, copy=copy)[0]


def test_lands_and_tokens_get_their_own_bins():
    rules = rules_of({"bin": 4, "conds": [{"f": "type", "types": ["Token"]}]},
                     {"bin": 3, "conds": [{"f": "type", "types": ["Land"]}]}, fallback=1)
    assert go(rules, card("Forest", "G")) == 3
    assert go(rules, card("Command Tower")) == 3
    assert go(rules, card("Soldier", "W", "tdmu", "common")) == 4       # a token set: T + the set
    assert go(rules, card("Lightning Bolt", "R")) == 1
    assert go(rules, card("Some card nobody knows", "R")) == 1         # not in the card list: no type


def test_all_any_and_not():
    green_not_land = {"bin": 2, "conds": [{"f": "color", "mode": "any", "colors": ["G"]},
                                          {"f": "type", "types": ["Land"], "not": True}]}
    cheap_or_red = {"bin": 3, "match": "any", "conds": [{"f": "price", "max": 0.5}, {"f": "color", "colors": ["R"]}]}
    rules = rules_of(green_not_land, cheap_or_red)
    assert go(rules, card("Llanowar Elves", "G")) == 2
    assert go(rules, card("Forest", "G"), price=0.1) == 3                # a land: not rule 1, cheap: rule 2
    assert go(rules, card("Lightning Bolt", "R"), price=4) == 3
    assert go(rules, card("Sol Ring"), price=4) == 0
    off = rules_of({**green_not_land, "on": False})
    assert go(off, card("Llanowar Elves", "G")) == 0                       # a rule turned off is skipped


@pytest.mark.parametrize("mode,picked,colors,fits", [
    ("any", ["U", "R"], "R", True), ("any", ["U"], "R", False), ("any", ["C"], "", True), ("any", ["M"], "U,R", True),
    ("all", ["U", "R"], "U,R", True), ("all", ["U", "R"], "R", False), ("all", ["U", "R"], "U,R,G", True),
    ("exact", ["U", "R"], "U,R,G", False), ("exact", ["U", "R"], "U,R", True), ("exact", ["C"], "", True),
    ("within", ["U", "R"], "R", True), ("within", ["U", "R"], "", True), ("within", ["U", "R"], "R,G", False),
    ("group", ["R"], "R", True), ("group", ["R"], "U,R", False), ("group", ["M"], "U,R", True),
])
def test_color_modes(mode, picked, colors, fits):
    rules = rules_of({"bin": 2, "conds": [{"f": "color", "mode": mode, "colors": picked}]})
    assert (go(rules, card("A", colors)) == 2) is fits


def test_identity_mana_value_text_type_line_and_rank():
    rules = rules_of({"bin": 1, "conds": [{"f": "identity", "mode": "within", "colors": ["U", "R"]},
                                          {"f": "type", "types": ["Instant"], "not": True}]},
                     {"bin": 2, "conds": [{"f": "mv", "min": 4}]},
                     {"bin": 3, "conds": [{"f": "text", "text": "damage"}]},
                     {"bin": 4, "conds": [{"f": "typeline", "text": "elf, goblin"}]})
    assert go(rules, card("Niv-Mizzet, Parun", "U,R")) == 1
    assert go(rules, card("Fire // Ice", "U,R")) == 2                    # an instant: skips rule 1; mana value 4
    assert go(rules, card("Lightning Bolt", "R")) == 3
    assert go(rules, card("Llanowar Elves", "G")) == 4
    ranked = rules_of({"bin": 2, "conds": [{"f": "edhrec", "max": 25}]}, {"bin": 3, "conds": [{"f": "gc"}]})
    assert go(ranked, card("Lightning Bolt", "R")) == 2 and go(ranked, card("Llanowar Elves", "G")) == 0
    assert go(rules_of({"bin": 3, "conds": [{"f": "gc"}]}), card("Sol Ring")) == 3


def test_format_legality():
    modern = rules_of({"bin": 2, "conds": [{"f": "format", "format": "modern", "status": "legal"}]},
                      {"bin": 3, "conds": [{"f": "format", "format": "legacy", "status": "banned"}]},
                      {"bin": 4, "conds": [{"f": "format", "format": "pauper", "status": "not_legal"}]})
    assert go(modern, card("Lightning Bolt", "R")) == 2
    assert go(modern, card("Sol Ring")) == 3
    assert go(modern, card("Command Tower")) == 4
    assert go(modern, card("Unknown thing")) == 0                    # not known: neither legal nor not
    with pytest.raises(ValueError):
        rules_of({"bin": 2, "conds": [{"f": "format", "format": "chess"}]})


def test_name_rarity_set_foil_and_no_price():
    rules = rules_of({"bin": 1, "conds": [{"f": "name", "mode": "list", "text": "Sol Ring\nFire // Ice"}]},
                     {"bin": 2, "conds": [{"f": "name", "mode": "contains", "text": "bolt"}]},
                     {"bin": 3, "conds": [{"f": "foil"}, {"f": "rarity", "values": ["rare", "mythic"]}]},
                     {"bin": 4, "conds": [{"f": "noprice"}]},
                     {"bin": 3, "conds": [{"f": "set", "values": "one, mom"}]})
    assert go(rules, card("Sol Ring")) == 1 and go(rules, card("Fire", "U,R")) == 1
    assert go(rules, card("Lightning Bolt", "R")) == 2
    assert go(rules, card("X", "R", rarity="rare"), foil=True) == 3
    assert go(rules, card("X", "R", rarity="rare"), foil=False) == 0
    assert go(rules, card("X", "R"), price=None) == 4
    assert go(rules, card("X", "R", set_code="mom")) == 3


def test_copies_beyond_four():
    rules = rules_of({"bin": 4, "conds": [{"f": "copies", "over": 4}]}, fallback=1)
    assert [go(rules, card("Lightning Bolt", "R"), copy=n) for n in range(1, 7)] == [1, 1, 1, 1, 4, 4]
    assert go(rules, card("Lightning Bolt", "R")) == 1                    # not known which copy: not an extra


def test_decks_by_list_and_by_colors():
    decks.save_deck("Izzet", "Commander\n1 Niv-Mizzet, Parun\nDeck\n4 Lightning Bolt\n1 Sol Ring", create=True)
    decks.save_deck("Elves", "4 Llanowar Elves\n10 Forest", create=True)
    in_deck = rules_of({"bin": 4, "conds": [{"f": "deck", "deck": "", "how": "list"}]})
    assert go(in_deck, card("Lightning Bolt", "R")) == 4 and go(in_deck, card("Llanowar Elves", "G")) == 4
    assert go(in_deck, card("Fire // Ice", "U,R")) == 0
    izzet = next(k for k, d in sort_rules.deck_info().items() if d["name"] == "Izzet")
    assert sort_rules.deck_info()[izzet]["ci"] == "UR"                     # the commander's colors
    colors = rules_of({"bin": 3, "conds": [{"f": "deck", "deck": izzet, "how": "colors"}]})
    assert go(colors, card("Fire // Ice", "U,R")) == 3 and go(colors, card("Sol Ring")) == 3
    assert go(colors, card("Llanowar Elves", "G")) == 0
    any_deck = rules_of({"bin": 3, "conds": [{"f": "deck", "deck": "", "how": "colors"}]})
    assert go(any_deck, card("Llanowar Elves", "G")) == 3                 # fits the elves deck (green)
    assert go(any_deck, card("Weird", "U,G")) == 0                         # fits no one deck


def test_resolve_writes_in_what_the_pi_has_not_got(tmp_path):
    decks.save_deck("Izzet", "Commander\n1 Niv-Mizzet, Parun\nDeck\n4 Lightning Bolt", create=True)
    decks.save_deck("Elves", "4 Llanowar Elves", create=True)
    csv = tmp_path / "coll.csv"
    csv.write_text("Name,Quantity\nLightning Bolt,3\nForest,1\n")
    rules = rules_of({"bin": 4, "conds": [{"f": "deck", "deck": "", "how": "list"}]},
                     {"bin": 3, "conds": [{"f": "deck", "deck": "", "how": "colors"}]},
                     {"bin": 2, "conds": [{"f": "copies", "over": 4}]})
    sent = sort_rules.clean(json.loads(json.dumps(sort_rules.resolve(rules, csv))))   # as the Pi reads it
    conds = [r["conds"][0] for r in sent["rules"]]
    assert set(conds[0]["names"]) == {"niv-mizzet, parun", "lightning bolt", "llanowar elves"}
    assert conds[1]["cis"] == ["G", "UR"]
    assert sort_rules.owned_before(sent) == {"lightning bolt": 3, "forest": 1}
    (config.DATA_DIR / "decks.json").unlink()                              # the Pi has no decks
    sort_rules._decks.update(key=None, info=None)
    assert go(sent, card("Llanowar Elves", "G")) == 4
    assert go(sent, card("Fire // Ice", "U,R")) == 3
    assert go(sent, card("Lightning Bolt", "R"), copy=5) == 4             # in a deck comes first


@pytest.mark.parametrize("name", list(sort_rules.PRESETS))
def test_every_preset_is_valid_and_uses_real_bins(name):
    rules = sort_rules.clean(sort_rules.preset(name))
    assert {r["bin"] for r in rules["rules"]} <= set(sort_rules.BINS)


def test_old_saved_rules_still_work():
    old = {"rules": [{"bin": 3, "min_price": 10, "max_price": None, "colors": [], "rarities": [], "sets": [], "foil": "any"},
                     {"bin": 2, "colors": ["R", "G"], "rarities": ["rare"], "foil": "normal"}], "fallback": 0}
    rules = sort_rules.clean(old)
    assert rules["rules"][1]["conds"] == [{"f": "color", "not": False, "mode": "group", "colors": ["R", "G"]},
                                          {"f": "rarity", "not": False, "values": ["rare"]},
                                          {"f": "foil", "not": True}]
    assert go(rules, card("X", "R", rarity="rare"), price=20) == 3
    assert go(rules, card("X", "R", rarity="rare"), price=2) == 2
    assert go(rules, card("X", "R", rarity="rare"), foil=True, price=2) == 0


@pytest.mark.parametrize("bad", [
    {"rules": [{"bin": 1, "conds": [{"f": "nope"}]}]},
    {"rules": [{"bin": 1, "conds": [{"f": "price", "min": 5, "max": 2}]}]},
    {"rules": [{"bin": 1, "conds": [{"f": "mv", "min": "lots"}]}]},
    {"rules": [{"bin": 1, "conds": [{"f": "color", "mode": "rainbow"}]}]},
    {"rules": [{"bin": 1, "conds": [{"f": "price"}] * 13}]},
    {"rules": [{"bin": 5}]},
])
def test_bad_rules_are_refused(bad):
    with pytest.raises(ValueError):
        sort_rules.clean(bad)


def test_bins_page_counts_rules_and_offers_bin_4(db, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "MACHINE_MODEL", "mk2")      # the tests start on the first machine
    client = create_app(Scanner(db, None, source=None)).test_client()
    for i in range(3):
        client.post("/api/add", json={"id": "id0"})
    js = client.post("/api/bins/preview", json={"rules": [{"bin": 4, "conds": [{"f": "copies", "over": 1}]}],
                                                "fallback": 1}).get_json()
    assert js["trays"] == [1, 2, 3, 4]
    assert js["preview"]["1"]["cards"] == 1 and js["preview"]["4"]["cards"] == 2
    assert js["rule_hits"] == [2]
    assert js["facts"]["have"] and "modern" in js["formats"] and "Land" in js["types"]
    saved = client.post("/api/bins", json=js["rules"]).get_json()
    assert saved["custom"] and saved["rules"]["rules"][0]["conds"][0]["over"] == 1
