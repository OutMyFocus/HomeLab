"""Deck ideas: Commander decks built from the cards you own (Decks page, Build a deck)."""

import json

import pytest
from test_scanner import db  # noqa: F401  (db is a fixture)

from app import Scanner, create_app
from mtgscanner import card_facts, config, deck_ideas, decks


def card(n, t, o="", ci="", v=2, m="", e=None, **extra):
    row = {"n": n, "t": t, "o": o, "ci": ci, "v": v, "m": m, "lg": "c"}
    if e:
        row["e"] = e
    row.update(extra)
    return row


KRENKO = card("Krenko Test", "Legendary Creature — Goblin Warrior",
              "{T}: Create X 1/1 red Goblin creature tokens, where X is the number of Goblins you control.",
              "R", 3, "{2}{R}{R}", e=300)
PLAIN = card("Plain Lord", "Legendary Creature — Human Knight", "Vigilance", "R", 3, "{2}{R}", e=9000)
BLUE_BOSS = card("Blue Boss", "Legendary Creature — Merfolk", "Whenever you cast an instant or sorcery spell, draw a card.",
                 "U", 3, "{2}{U}", e=5)

GOBLINS = [card(f"Goblin {i}", "Creature — Goblin", "Haste" if i % 2 else "", "R", 1 + i % 4, "{R}", e=2000 + i)
           for i in range(40)]
RAMP = [card(f"Rock {i}", "Artifact", "{T}: Add {C}.", "", 2, "{2}", e=50 + i) for i in range(12)]
DRAW = [card(f"Draw {i}", "Sorcery", "Draw two cards.", "R", 3, "{2}{R}", e=800 + i) for i in range(12)]
REMOVAL = [card(f"Bolt {i}", "Instant", "Bolt {i} deals 3 damage to any target.", "R", 1, "{R}", e=400 + i) for i in range(10)]
WIPES = [card(f"Quake {i}", "Sorcery", "Quake deals 2 damage to each creature.", "R", 3, "{1}{R}{R}", e=3000 + i) for i in range(3)]
FILLER = [card(f"Rock Pile {i}", "Creature — Elemental", "", "R", 4, "{3}{R}", e=20000 + i) for i in range(30)]
BLUE = [card(f"Blue {i}", "Instant", "Draw a card.", "U", 1, "{U}", e=10 + i) for i in range(5)]
LANDS = [card(f"Red Land {i}", "Land", "{T}: Add {R}.", "R", 0, e=600 + i) for i in range(6)]
BANNED = card("Bad Goblin", "Creature — Goblin", "", "R", 1, "{R}", e=1, b=1)
MOUNTAIN = card("Mountain", "Basic Land — Mountain", "({T}: Add {R}.)", "R", 0)
ALL = [KRENKO, PLAIN, BLUE_BOSS, BANNED, MOUNTAIN, *GOBLINS, *RAMP, *DRAW, *REMOVAL, *WIPES, *FILLER, *BLUE, *LANDS]
EXTRA_POOL = [card(f"Shop Card {i}", "Instant", "Shock deals 2 damage to any target.", "R", 1, "{R}", e=100 + i)
              for i in range(80)] + [card("Big Ring", "Legendary Artifact", "Draw a card.", "", 4, "{4}", e=2, gc=1)]


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    (tmp_path / "carddb.json").write_text(json.dumps({"v": 1, "n": len(ALL), "cards": ALL + EXTRA_POOL}))
    card_facts.forget()
    deck_ideas._cache["key"] = None
    yield tmp_path
    card_facts.forget()
    deck_ideas._cache["key"] = None


def mine(*rows, skip=()):
    """What you own: one of each card, plus 30 Mountains."""
    counts = {decks.name_key(r["n"]): 1 for r in rows if r["n"] not in skip}
    counts["mountain"] = 30
    return counts


def test_commander_themes_and_creature_types():
    types = deck_ideas.creature_types(ALL)
    assert "Goblin" in types
    themes, tribes = deck_ideas.wants(KRENKO, types)
    assert "tokens" in themes and tribes == {"Goblin"}
    assert deck_ideas.wants(PLAIN, types) == (set(), set())
    assert "spells" in deck_ideas.wants(BLUE_BOSS, types)[0]


def test_card_jobs():
    assert deck_ideas.roles(RAMP[0]) == {"ramp"}
    assert deck_ideas.roles(DRAW[0]) == {"draw"}
    assert deck_ideas.roles(REMOVAL[0]) == {"removal"}
    assert "wipe" in deck_ideas.roles(WIPES[0])
    assert deck_ideas.roles(LANDS[0]) == {"land"}
    assert deck_ideas.is_tribe(GOBLINS[0], "Goblin") and not deck_ideas.is_tribe(FILLER[0], "Goblin")
    assert deck_ideas.can_lead(KRENKO) and not deck_ideas.can_lead(GOBLINS[0])


def test_basics_split_by_colored_symbols():
    assert deck_ideas.split_basics({"R": 30}, 20) == {"Mountain": 20}
    split = deck_ideas.split_basics({"R": 30, "G": 10}, 20)
    assert sum(split.values()) == 20 and split["Mountain"] > split["Forest"] >= 1
    assert deck_ideas.split_basics({}, 5) == {"Wastes": 5}
    assert deck_ideas.split_basics({"R": 1}, 0) == {}


def test_build_picks_on_theme_cards_in_colors_and_fills_to_99():
    coll = deck_ideas.Collection(mine(*ALL))
    d = deck_ideas.build(KRENKO, coll)
    names = {c["n"] for c in d["cards"]}
    assert not any(n.startswith("Blue") for n in names)           # off color
    assert "Bad Goblin" not in names and "Krenko Test" not in names   # banned, and the commander itself
    assert sum(g["n"] in names for g in GOBLINS) == 34             # every slot the jobs leave goes to a Goblin
    assert not any(n.startswith("Rock Pile") for n in names)       # off-theme filler stays out
    assert d["roles"]["ramp"] == 10 and d["roles"]["removal"] == 8 and d["roles"]["wipe"] == 2
    total = len(d["cards"]) + len(d["lands"]) + sum(d["basics"].values())
    assert total == 99 and d["open"] == 0
    assert len(d["lands"]) + sum(d["basics"].values()) == deck_ideas.LANDS
    assert d["tribes"] == ["Goblin"] and d["on_theme"] == 34


def test_ideas_rank_the_goblin_commander_first_and_filter():
    out = deck_ideas.ideas(mine(*ALL, skip={"Blue Boss"}))
    names = [i["commander"] for i in out["ideas"]]
    assert names[0] == "Krenko Test"
    assert names.index("Krenko Test") < names.index("Plain Lord")
    assert "Blue Boss" in names                                    # popular, even though you don't own it
    boss = next(i for i in out["ideas"] if i["commander"] == "Blue Boss")
    assert not boss["owned_leader"] and boss["open"] > 0
    assert all(k.startswith("Goblin") for k in out["ideas"][0]["key"])
    assert [i["commander"] for i in deck_ideas.ideas(mine(*ALL), owned_only=True)["ideas"]][:2] == ["Krenko Test", "Plain Lord"]
    assert "Blue Boss" not in [i["commander"] for i in deck_ideas.ideas(mine(*ALL, skip={"Blue Boss"}), owned_only=True)["ideas"]]
    assert [i["commander"] for i in deck_ideas.ideas(mine(*ALL), style="tribal")["ideas"]] == ["Krenko Test"]
    assert [i["commander"] for i in deck_ideas.ideas(mine(*ALL), colors="U")["ideas"]] == ["Blue Boss"]


def test_build_for_fills_open_slots_with_cards_to_get():
    few = mine(KRENKO, *GOBLINS[:10], *RAMP[:5])
    d = deck_ideas.build_for("krenko test", few, fill="buy", online=False)
    assert d["open"] > 0 and len(d["buy"]) == d["open"]
    assert "Big Ring" not in d["buy"]                              # no Game Changers picked for you
    assert all(n.startswith(("Shop Card", "Bolt", "Draw", "Quake", "Rock", "Goblin")) for n in d["buy"])
    assert not set(d["buy"]) & {c["n"] for c in d["cards"] if not c.get("buy")}
    parsed = decks.parse(d["text"])
    assert [x["name"] for x in parsed if x["section"] == "Commander"] == ["Krenko Test"]
    assert sum(x["qty"] for x in parsed if x["section"] == "Main deck") == 99
    empty = deck_ideas.build_for("Krenko Test", few, fill="empty", online=False)
    assert sum(x["qty"] for x in decks.parse(empty["text"]) if x["section"] == "Main deck") == 99 - empty["open"]
    lands = deck_ideas.build_for("Krenko Test", few, fill="basics", online=False)
    assert sum(x["qty"] for x in decks.parse(lands["text"]) if x["section"] == "Main deck") == 99
    assert "error" in deck_ideas.build_for("Goblin 1", few, online=False)
    assert "error" in deck_ideas.build_for("No Such Card", few, online=False)


def test_spare_cards_leave_out_cards_in_your_other_decks():
    decks.save_deck("Old goblins", "Commander\n1 Krenko Test\nDeck\n" + "\n".join(f"1 {g['n']}" for g in GOBLINS[:20]))
    used = deck_ideas.in_other_decks()
    assert used["goblin 0"] == 1 and used["krenko test"] == 1
    coll = deck_ideas.Collection(mine(*ALL), used)
    assert "goblin 0" not in coll.names and "goblin 25" in coll.names


def test_routes(db):  # noqa: F811
    client = create_app(Scanner(db, None, source=None)).test_client()
    config.COLLECTION_CSV.write_text("Name,Quantity\n" + "\n".join(f"{r['n']},1" for r in [KRENKO, *GOBLINS, *RAMP]) + "\n")
    out = client.get("/api/decks/ideas?owned=1").get_json()
    assert out["ideas"][0]["commander"] == "Krenko Test" and out["cards"] == 1 + len(GOBLINS) + len(RAMP)
    assert client.post("/api/decks/ideas/build", json={}).status_code == 400
    built = client.post("/api/decks/ideas/build", json={"commander": "Krenko Test", "fill": "empty"}).get_json()
    assert built["commander"] == "Krenko Test" and "1 Goblin 0" in built["text"]
