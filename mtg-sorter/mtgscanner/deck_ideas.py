"""Deck ideas: Commander decks you could build from the cards you already own (the
"Build a deck" panel on the Decks page).

For each commander you own (and the most played ones you don't), it works out which of
your cards fit: in the commander's colors, on its theme (go wide with tokens, a creature
type like Goblins, +1/+1 counters, the graveyard...), and the jobs every Commander deck
needs (ramp, card draw, removal, a board wipe or two). It then builds the deck greedily,
best cards first, fills the mana base with your lands and basics, and scores how ready
it is to play. The page shows the best ideas; building one makes a saved deck that the
deck builder can then edit, check and upgrade.

Everything comes from the card list (carddb.json, through card_facts) and the
collection CSV, so it works offline. When a deck is built for one commander, EDHREC's
list for it (upgrades.py, cached for a week) also helps pick, and suggests what to buy
for the slots your cards can't fill.

    GET  /api/decks/ideas?style=tokens&colors=R&owned=1
    POST /api/decks/ideas/build {commander, fill: "buy" | "basics" | "empty", spare: bool}
"""

import math
import re
import threading

from flask import jsonify, request

from . import accounts, card_facts
from .ca_prices import BASICS
from .decks import EXTRA_SECTIONS, load_decks, name_key, parse
from .library import qty, read_rows

DECK_SIZE = 99           # the commander is the 100th card
LANDS = 36               # lands in a typical Commander deck (plus ramp)
MAX_NONBASIC = 22        # at most this many of your own nonbasic lands; basics fill the rest
ROLE_TARGETS = {"ramp": 10, "draw": 9, "removal": 8, "wipe": 2}
POPULAR = 150            # commanders you don't own that are looked at too (the most played)
MAX_IDEAS = 40

COLORS = "WUBRG"
BASIC_FOR = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}

# Themes: what a commander asks for (in its rules text) and which cards help it.
# key: (label, words in a commander's text that ask for it, words in a card's text that
# help it, card types that help it).
THEMES = {
    "tokens": ("Go wide with tokens",
               r"create[^.]*creature tokens?|populate|for each creature you control|creatures you control get \+|tokens you control|token creatures",
               r"create[^.]*creature tokens?|populate|creatures you control get \+|for each creature you control|tokens you control", ()),
    "counters": ("+1/+1 counters", r"\+1/\+1 counters?|proliferate", r"\+1/\+1 counters?|proliferate", ()),
    "graveyard": ("Graveyard",
                  r"from your graveyard|cards? in your graveyard|\bmill|dredge|flashback|unearth|escape",
                  r"from your graveyard|cards? in your graveyard|\bmills?\b|dredge|flashback|unearth|escape|surveil", ()),
    "sacrifice": ("Sacrifice",
                  r"sacrifices? (a|another) (creature|permanent)|whenever (a|another) creature (you control )?dies",
                  r"sacrifices? (a|another) (creature|permanent)|whenever (a|another)[^.]*creature[^.]*dies|when[^.]*dies", ()),
    "artifacts": ("Artifacts", r"artifacts? you control|artifact spells?|whenever (an|another|one or more)[^.]*artifacts?[^.]* enters|for each artifact|artifact creatures? you control",
                  r"artifacts? you control|artifact spells?|for each artifact|whenever[^.]*artifact", ("Artifact",)),
    "enchantments": ("Enchantments", r"enchantments? you control|enchantment spells?|whenever (an|another|one or more)[^.]*enchantments?[^.]* enters|for each enchantment|constellation",
                     r"enchantments? you control|enchantment spells?|for each enchantment|whenever[^.]*enchantment|constellation", ("Enchantment",)),
    "spells": ("Instants and sorceries", r"whenever you cast (an|a|your first)[^.]*(instant|sorcery|noncreature)|instant (and|or) sorcery spells|instants? and sorceries|noncreature spells?",
               r"instant or sorcery|noncreature spell|whenever you cast", ("Instant", "Sorcery")),
    "lifegain": ("Life gain", r"whenever you gain life|if you would gain life|lifelink|for each 1 life you gained",
                 r"gain(s)? (\d+ |x )?life|lifelink", ()),
    "landfall": ("Lands matter", r"landfall|whenever a land[^.]*enters|play an additional land",
                 r"landfall|whenever a land[^.]*enters|play an additional land|search your library for[^.]*land", ()),
    "flying": ("Flyers", r"creatures? (you control )?with flying|flying creatures", r"\bflying\b", ()),
    "voltron": ("Equipment and auras", r"\bequip(ped|ment)?\b|\bauras?\b|enchanted creature",
                r"\bequip(ped|ment)?\b|enchanted creature", ("Equipment", "Aura")),
    "attack": ("Attack", r"whenever (you attack|one or more creatures you control attack|a creature you control attacks|another creature you control attacks)|attacking creatures you control|creatures? you control deals? combat damage to a player",
               r"whenever[^.]*attacks|attacking creatures|combat damage to a player|\bhaste\b|double strike|extra combat", ()),
    "blink": ("Enter the battlefield", r"exile[^.]*return (it|that card|them|those cards) to the battlefield|triggers an additional time",
              r"exile[^.]*return (it|that card|them|those cards) to the battlefield|when[^.]* enters", ()),
}
# The deck styles the page offers, in its order.
STYLES = {"tribal": "Creature type", **{k: THEMES[k][0] for k in (
    "tokens", "counters", "attack", "sacrifice", "graveyard", "spells", "artifacts", "enchantments", "lifegain",
    "landfall", "flying", "voltron", "blink")}}
_WANTS = {k: re.compile(v[1]) for k, v in THEMES.items()}
_HELPS = {k: re.compile(v[2]) for k, v in THEMES.items()}

_RAMP = re.compile(r"add \{|add (one|two|three) mana|add [^.]*mana of any|search your library for (a|an|up to \w+|two)[^.]*lands? card"
                   r"|create[^.]*treasure|put (a|an|up to \w+)[^.]*lands? cards?[^.]* onto the battlefield")
_DRAW = re.compile(r"\bdraws? (a|an|two|three|four|five|x|that many|cards equal|\w+ cards)\b|\binvestigate\b")
_REMOVAL = re.compile(r"(destroy|exile) target (creature|artifact|enchantment|planeswalker|permanent|nonland|nontoken)"
                      r"|deals? (\d+|x) damage to (target creature|any target|target attacking)|counter target (spell|creature spell|noncreature)"
                      r"|return target (creature|nonland permanent|permanent) to its owner'?s hand|target creature gets -\d+/-\d+"
                      r"|fights? (target|another target|up to one target)")
_WIPE = re.compile(r"(destroy|exile) (all|each) (creatures|other creatures|nonland permanents|artifacts|enchantments|creature)"
                   r"|deals? (\d+|x) damage to each creature|all creatures get -|each player sacrifices")
# Plurals that don't just add an s.
_PLURALS = {"Elf": "Elves", "Dwarf": "Dwarves", "Wolf": "Wolves", "Werewolf": "Werewolves", "Fungus": "Fungi",
            "Ox": "Oxen", "Mouse": "Mice", "Octopus": "Octopi", "Thief": "Thieves", "Sorcerer": "Sorcerers"}
# Creature types too common or too vague to build a deck around from one mention.
_NOT_TRIBES = {"Human", "Spirit", "Construct", "Shapeshifter", "Wall", "Thopter", "Servo", "Saproling", "Treasure",
               "Clue", "Food", "Citizen", "Soldier", "Warrior", "Horror", "Elemental", "Beast", "Illusion", "God",
               "Avatar", "Gold", "Incarnation", "Time", "Equipment", "Vehicle", "Aura"}

_lock = threading.Lock()
_cache: dict = {"key": None, "rows": None, "types": None, "info": None}


def front(row: dict, k: str = "t") -> str:
    return str(row.get(k) or "").split(" // ")[0].split("\n//\n")[0]


def is_land(row: dict) -> bool:
    return "Land" in front(row)


def can_lead(row: dict) -> bool:
    """A card that can be a commander (a legendary creature, or says it can be one)."""
    t = front(row)
    return (("Legendary" in t and "Creature" in t) or "can be your commander" in str(row.get("o", ""))) and not row.get("b")


def quality(row: dict) -> float:
    """How good a card is in Commander, 0 to 1, from how many decks play it (EDHREC rank)."""
    e = row.get("e")
    if not e:
        return 0.0
    return max(0.0, 1 - math.log10(max(1, e)) / math.log10(40000))


def creature_types(rows) -> set[str]:
    out = set()
    for r in rows:
        t = front(r)
        if "Creature" in t and "—" in t:
            out.update(w for w in t.split("—", 1)[1].split() if w[:1].isupper())
    return out


def _mentions(text: str, kind: str) -> bool:
    return re.search(rf"\b({re.escape(kind)}s?|{re.escape(_PLURALS.get(kind, kind))})\b", text) is not None


def plural(kind: str) -> str:
    """Goblin -> Goblins, Elf -> Elves (for labels)."""
    return _PLURALS.get(kind) or (kind if kind.endswith("s") else kind + "s")


def wants(row: dict, types: set[str]) -> tuple[set[str], set[str]]:
    """(themes, creature types) a commander asks for in its rules text."""
    text = str(row.get("o", ""))
    low = text.lower()
    themes = {k for k, rx in _WANTS.items() if rx.search(low)}
    # A creature type named in its text (Krenko names Goblins); the vague ones don't count.
    tribes = {t for t in types if t not in _NOT_TRIBES and t in text and _mentions(text, t)}
    return themes, tribes


def helps(row: dict) -> set[str]:
    """Themes a card helps with (what it does, or what it is)."""
    low = str(row.get("o", "")).lower()
    t = front(row)
    out = {k for k, rx in _HELPS.items() if rx.search(low)}
    for k, v in THEMES.items():
        if any(x in t for x in v[3]):
            out.add(k)
    if "flying" in out and "Creature" not in t:
        out.discard("flying")
    return out


def is_tribe(row: dict, tribe: str) -> bool:
    t, text = front(row), str(row.get("o", ""))
    return ("Creature" in t and tribe in t.split("—", 1)[-1].split()) or "Changeling" in text or (
        tribe in text and _mentions(text, tribe))


def roles(row: dict) -> set[str]:
    if is_land(row):
        return {"land"}
    low = str(row.get("o", "")).lower()
    out = set()
    if _RAMP.search(low) and float(row.get("v") or 0) <= 4:
        out.add("ramp")
    if _DRAW.search(low):
        out.add("draw")
    if _REMOVAL.search(low):
        out.add("removal")
    if _WIPE.search(low):
        out.add("wipe")
    if "Creature" in front(row):
        out.add("creature")
    return out


def _mask(ci: str) -> int:
    return sum(1 << COLORS.index(c) for c in str(ci or "") if c in COLORS)


def _load():
    """The card list, with each card's themes and jobs worked out once (until the file changes)."""
    rows = card_facts.all_rows()
    key = (id(card_facts._db.get("cards")), len(rows))
    with _lock:
        if _cache["key"] == key:
            return _cache["rows"], _cache["types"], _cache["info"]
        by_name, info = {}, {}
        for r in rows:
            if not r.get("n"):
                continue
            by_name.setdefault(name_key(r["n"]), r)
        types = creature_types(by_name.values())
        _cache.update(key=key, rows=by_name, types=types, info=info)
        return by_name, types, info


def _facts(row: dict, info: dict) -> dict:
    """A card's themes, jobs, color mask and quality, kept for next time."""
    k = row["n"]
    if k not in info:
        info[k] = {"helps": helps(row), "roles": roles(row), "mask": _mask(row.get("ci")), "q": quality(row)}
    return info[k]


def owned_counts(rows: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        k = name_key(r.get("Name", ""))
        if k:
            out[k] = out.get(k, 0) + qty(r)
    return out


def in_other_decks(skip: str = "") -> dict[str, int]:
    """How many copies of each card your saved decks already use (for "spare cards only")."""
    used: dict[str, int] = {}
    for d in load_decks():
        if d.get("id") == skip or d.get("proxied"):
            continue
        for line in parse(d.get("text", "")):
            if line["section"] in EXTRA_SECTIONS or line["section"] == "Sideboard":
                continue
            k = name_key(line["name"])
            used[k] = used.get(k, 0) + line["qty"]
    return used


class Collection:
    """Your cards that are in the card list, with their themes and jobs."""

    def __init__(self, counts: dict[str, int], used: dict[str, int] | None = None):
        self.db, self.types, self.info = _load()
        self.cards = []   # (row, facts) for each nonbasic card you own (spare copies only, with used)
        for k, n in counts.items():
            if k in BASICS or n - (used or {}).get(k, 0) < 1:
                continue
            row = self.db.get(k)
            if row and not row.get("b"):
                self.cards.append((row, _facts(row, self.info)))
        self.names = {name_key(r["n"]) for r, _ in self.cards}

    def leaders(self):
        return [r for r, _ in self.cards if can_lead(r)]


def score_card(row, f, themes, tribes, edhrec=None) -> tuple[float, bool]:
    """(score, on theme) of a card for a commander."""
    hits = len(f["helps"] & themes)
    tribe = any(is_tribe(row, t) for t in tribes)
    on = bool(hits or tribe)
    s = f["q"] * 2 + min(hits, 3) * 1.2 + (2.5 if tribe else 0)
    if "creature" in f["roles"] and (tribes or themes & {"tokens", "attack", "counters", "sacrifice", "flying", "blink"}):
        s += 0.3
    if edhrec:
        e = edhrec.get(name_key(row["n"]))
        if e:
            s += 3 * e["inc"] + 2 * max(e["syn"], 0)
            on = on or e["syn"] > 0.15
    return s, on


def build(leader: dict, coll: Collection, edhrec: dict | None = None) -> dict:
    """The best deck your cards make for this commander."""
    themes, tribes = wants(leader, coll.types)
    mask = _mask(leader.get("ci"))
    lead_key = name_key(leader["n"])
    pool = []
    for row, f in coll.cards:
        if f["mask"] & ~mask or name_key(row["n"]) == lead_key:
            continue
        s, on = score_card(row, f, themes, tribes, edhrec)
        pool.append((s, row, f, on))
    pool.sort(key=lambda x: (-x[0], x[1]["n"]))
    lands = [x for x in pool if "land" in x[2]["roles"]][:MAX_NONBASIC]
    spells = [x for x in pool if "land" not in x[2]["roles"]]
    room = DECK_SIZE - LANDS
    picked, got = [], {k: 0 for k in ROLE_TARGETS}
    for role, target in ROLE_TARGETS.items():      # the jobs first, best cards first
        for x in spells:
            if got[role] >= target or len(picked) >= room:
                break
            if role in x[2]["roles"] and x not in picked:
                picked.append(x)
                for r2 in x[2]["roles"] & set(ROLE_TARGETS):
                    got[r2] += 1
    for x in spells:                                # then the best of the rest
        if len(picked) >= room:
            break
        if x not in picked:
            picked.append(x)
            for r2 in x[2]["roles"] & set(ROLE_TARGETS):
                got[r2] += 1
    picked.sort(key=lambda x: (-x[0], x[1]["n"]))
    # The mana base: your lands, then basics split by the colored symbols on the spells.
    pips = {c: 0 for c in COLORS if mask & _mask(c)}
    for _, row, _, _ in picked:
        for c in pips:
            pips[c] += str(row.get("m", "")).count("{" + c + "}") + str(row.get("m", "")).count("/" + c + "}")
    basics_n = LANDS - len(lands)
    basics = split_basics(pips, basics_n)
    on = sum(1 for x in picked if x[3])
    q = sum(x[2]["q"] for x in picked) / len(picked) if picked else 0
    # Cards that pull their weight: on theme, or played in a fair share of decks.
    useful = sum(1 for x in picked if x[3] or x[2]["q"] >= 0.2)
    power = sum(x[0] for x in picked) / room   # empty slots count as nothing
    fit = fit_score(useful, room, got, q, power)
    return {"commander": leader["n"], "ci": leader.get("ci", ""), "themes": [THEMES[k][0] for k in sorted(themes)],
            "tags": [plural(t) for t in sorted(tribes)] + [THEMES[k][0] for k in sorted(themes)],
            "theme_keys": sorted(themes) + (["tribal"] if tribes else []), "tribes": sorted(tribes),
            "cards": [{"n": x[1]["n"], "m": x[1].get("m", ""), "roles": sorted(x[2]["roles"] - {"creature"}), "on": x[3],
                       "type": type_group(x[1])} for x in picked],
            "lands": [x[1]["n"] for x in lands], "basics": basics, "open": room - len(picked),
            "roles": got, "on_theme": on, "fit": fit, "power": round(power, 2), "owned_leader": lead_key in coll.names}


def split_basics(pips: dict[str, int], n: int) -> dict[str, int]:
    """n basic lands split by how many colored symbols each color has (at least 1 each)."""
    if n <= 0:
        return {}
    if not pips:
        return {"Wastes": n}
    total = sum(pips.values()) or len(pips)
    share = {c: max(1, round(n * (pips[c] or (total / len(pips))) / total)) for c in pips}
    while sum(share.values()) > n:
        c = max(share, key=lambda c: share[c])
        share[c] -= 1
    while sum(share.values()) < n:
        c = max(pips, key=lambda c: pips[c] - share[c] * total / n)
        share[c] += 1
    return {BASIC_FOR[c]: k for c, k in share.items() if k > 0}


def fit_score(filled, room, got, q, power) -> int:
    """How ready the deck is, 0 to 100: good cards of yours fill it, they work with the
    commander (power: the average card score, where theme and creature type count most),
    the jobs are covered and the cards are strong ones."""
    cover = min(1, filled / room)
    synergy = min(1, power / 3)
    jobs = sum(min(1, got[k] / t) for k, t in ROLE_TARGETS.items()) / len(ROLE_TARGETS)
    good = min(1, q / 0.45)
    return round(100 * (0.35 * cover + 0.35 * synergy + 0.15 * jobs + 0.15 * good))


def type_group(row) -> str:
    t = front(row)
    for k in ("Creature", "Planeswalker", "Battle", "Instant", "Sorcery", "Artifact", "Enchantment", "Land"):
        if k in t:
            return k
    return "Other"


def ideas(counts: dict[str, int], style: str = "", colors: str = "", owned_only: bool = False,
          used: dict[str, int] | None = None) -> dict:
    """The best commander decks your cards make, best first."""
    coll = Collection(counts, used)
    if not coll.db:
        return {"ideas": [], "error": "The card list isn't on this computer yet. Settings, Prices and card data, Update now."}
    leaders = {r["n"]: r for r in coll.leaders()}
    if not owned_only:
        popular = sorted((r for r in coll.db.values() if can_lead(r) and r.get("e")), key=lambda r: r["e"])
        for r in popular[:POPULAR]:
            leaders.setdefault(r["n"], r)
    want = _mask(colors)
    out = []
    for r in leaders.values():
        if colors and _mask(r.get("ci")) != want:
            continue
        d = build(r, coll)
        if style and style not in d["theme_keys"]:
            continue
        d["key"] = [c["n"] for c in d.pop("cards") if c["on"]][:5]   # a taste of the deck
        d.pop("lands")
        out.append(d)
    # Best first; a commander you own goes first when two are as good.
    out.sort(key=lambda d: (-d["fit"], not d["owned_leader"], -d["power"], d["commander"]))
    return {"ideas": out[:MAX_IDEAS], "cards": len(coll.cards), "commanders": len(coll.leaders()),
            "styles": STYLES}


def deck_text(d: dict, extra: list[str] | None = None) -> str:
    lines = ["Commander", f"1 {d['commander']}", "", "Deck"]
    groups: dict[str, list[str]] = {}
    for c in d["cards"]:
        groups.setdefault(c["type"], []).append(c["n"])
    for g in ("Creature", "Planeswalker", "Battle", "Instant", "Sorcery", "Artifact", "Enchantment", "Other"):
        lines += [f"1 {n}" for n in groups.get(g, [])]
    lines += [f"1 {n}" for n in d["lands"]]
    lines += [f"{k} {n}" for n, k in d["basics"].items()]
    if extra:
        lines += ["", "// To get (not in your collection yet)"] + [f"1 {n}" for n in extra]
    return "\n".join(lines) + "\n"


def edhrec_list(commander: str, online: bool) -> tuple[dict, list[dict]]:
    """EDHREC's picks for a commander ({name key: card}, the list in order), or empty."""
    from .upgrades import recommendations
    rec = recommendations(commander, online=online)   # copes with EDHREC being down itself
    cards = rec.get("cards") or []
    return {name_key(c["n"]): c for c in cards}, cards


def build_for(commander: str, counts: dict[str, int], fill: str = "buy", used=None, online: bool = True) -> dict:
    coll = Collection(counts, used)
    row = coll.db.get(name_key(commander))
    if not row:
        return {"error": f"Couldn't find {commander} in the card list"}
    if not can_lead(row):
        return {"error": f"{row['n']} can't be a commander"}
    edhrec, ranked = edhrec_list(row["n"], online)
    d = build(row, coll, edhrec or None)
    extra: list[str] = []
    if d["open"] and fill == "buy":
        mask = _mask(row.get("ci"))
        have = coll.names | {name_key(c["n"]) for c in d["cards"]} | {name_key(row["n"])}
        picks = [c["n"] for c in ranked if name_key(c["n"]) not in have and c.get("cat") != "Lands"]
        if not picks:   # no EDHREC list: the most played cards in its colors instead
            picks = [r["n"] for r in sorted((r for r in coll.db.values() if r.get("e") and not r.get("b")
                     and not is_land(r) and not _mask(r.get("ci")) & ~mask), key=lambda r: r["e"])
                     if name_key(r["n"]) not in have]
        for n in picks:
            r = coll.db.get(name_key(n))
            # Game Changers (The One Ring, Rhystic Study...) are left for you to choose.
            if not r or is_land(r) or r.get("b") or r.get("gc") or _mask(r.get("ci")) & ~mask:
                continue
            extra.append(r["n"])
            if len(extra) >= d["open"]:
                break
        d["cards"] += [{"n": n, "m": coll.db[name_key(n)].get("m", ""), "roles": sorted(roles(coll.db[name_key(n)]) - {"creature"}), "on": True,
                        "type": type_group(coll.db[name_key(n)]), "buy": True} for n in extra]
    elif d["open"] and fill == "basics":
        pips = {c: 1 for c in COLORS if _mask(row.get("ci")) & _mask(c)}
        more = split_basics(pips, d["open"])
        for n, k in more.items():
            d["basics"][n] = d["basics"].get(n, 0) + k
    d["buy"] = extra
    d["edhrec"] = bool(edhrec)
    # Bought cards go in the deck itself (the builder marks them BUY); text keeps them grouped.
    owned_cards = [c for c in d["cards"] if not c.get("buy")]
    d["text"] = deck_text({**d, "cards": owned_cards}, extra)
    return d


def add_idea_routes(app, scanner):
    def counts():
        with scanner.lock:
            rows = read_rows(accounts.collection_csv())
        return owned_counts(rows)

    @app.get("/api/decks/ideas")
    def decks_ideas():
        a = request.args
        used = in_other_decks() if a.get("spare") == "1" else None
        return jsonify(ideas(counts(), style=str(a.get("style", ""))[:20], colors=str(a.get("colors", ""))[:5].upper(),
                             owned_only=a.get("owned") == "1", used=used))

    @app.post("/api/decks/ideas/build")
    def decks_ideas_build():
        js = request.get_json(force=True, silent=True) or {}
        commander = str(js.get("commander", "")).strip()[:150]
        if not commander:
            return jsonify({"error": "Pick a commander first"}), 400
        fill = js.get("fill") if js.get("fill") in ("buy", "basics", "empty") else "buy"
        used = in_other_decks() if js.get("spare") else None
        out = build_for(commander, counts(), fill=fill, used=used, online=getattr(scanner, "live", None) is not None)
        return jsonify(out), (400 if out.get("error") else 200)
