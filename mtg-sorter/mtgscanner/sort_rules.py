"""Which bin each card goes into, as rules you set on the Bins page (/bins).

Rules are checked top to bottom and the first one that fits the card wins. A rule can
look at the price, the card's color, its rarity, its set and whether it's foil. A card
no rule fits goes to the "anything else" bin.

Wanted cards come before all of that (Nic, 2026-11-08: "input those to go into a specific
bin"): a list of card names, pasted or taken from a deck, and the bin they go to. A card
on the list goes to that bin whatever it's worth. "Only wanted cards" keeps that bin for
them: a card the rules would put there goes to another bin you pick instead. During a
sort run the listed number of copies is pulled (4 Lightning Bolt pulls four), and later
copies are sorted as usual.

Saved in data/sort_rules.json. Without that file the bins are the price bins in
config.py, exactly as before.
"""

import json
from pathlib import Path

from . import config

BINS = [0, 1, 2, 3]                       # the sorter's bins
COLORS = ["W", "U", "B", "R", "G", "M", "C"]
RARITIES = ["common", "uncommon", "rare", "mythic", "special", "bonus"]
MAX_RULES = 30
MAX_WANTED = 500
BASICS = {"plains", "island", "swamp", "mountain", "forest", "wastes"} | {
    f"snow-covered {b}" for b in ("plains", "island", "swamp", "mountain", "forest", "wastes")}
FILE_NAME = "sort_rules.json"

_cache: dict = {"path": None, "mtime": None, "rules": None}


def rules_file() -> Path:
    return config.DATA_DIR / FILE_NAME


def default_rules() -> dict:
    """The price bins from config.py, written as rules."""
    names = {str(config.NO_PRICE_BIN[0]): config.NO_PRICE_BIN[1]}
    rules = []
    for number, label, minimum in config.PRICE_BINS:
        names[str(number)] = label
        rules.append(_rule(number, min_price=minimum))
    for b in BINS:
        names.setdefault(str(b), f"Bin {b}")
    return {"rules": rules, "fallback": config.NO_PRICE_BIN[0], "names": names, "wanted": default_wanted()}


def default_wanted() -> dict:
    """Off. When turned on: bin 2 (under the trapdoors, the surest drop), kept for wanted
    cards only, with the $1-$10 cards that would have gone there sent to bin 3."""
    return {"on": False, "bin": 2, "only": True, "others": 3, "limit": True, "skip_basics": True,
            "source": "", "cards": []}


def name_key(name) -> str:
    """Front face, lowercase (as decks.name_key): "Fire // Ice" matches "fire"."""
    return str(name or "").split(" // ")[0].split("/")[0].strip().lower()


def _rule(bin_no, min_price=None, max_price=None, colors=(), rarities=(), sets=(), foil="any"):
    return {"bin": bin_no, "min_price": min_price, "max_price": max_price, "colors": list(colors),
            "rarities": list(rarities), "sets": list(sets), "foil": foil}


PRESETS = {
    "price": ("By price", "Valuable cards in one bin, $1 to $10 in another, bulk in a third", None),
    "valuable": ("Keep the good stuff", "$5 and up in bin 3, everything else in bin 1", {
        "rules": [_rule(3, min_price=5), _rule(1, min_price=0)], "fallback": 0,
        "names": {"0": "No price", "1": "Under $5", "2": "Not used", "3": "$5 and up"}}),
    "rarity": ("By rarity", "Mythics and rares, uncommons, commons", {
        "rules": [_rule(3, rarities=["mythic", "rare"]), _rule(2, rarities=["uncommon"]),
                  _rule(1, rarities=["common"])], "fallback": 0,
        "names": {"0": "Other (tokens, promos)", "1": "Commons", "2": "Uncommons", "3": "Rares and mythics"}}),
    "color": ("By color", "White and blue, black and red, green and multicolor, colorless", {
        "rules": [_rule(1, colors=["W", "U"]), _rule(2, colors=["B", "R"]), _rule(3, colors=["G", "M"])],
        "fallback": 0,
        "names": {"0": "Colorless and lands", "1": "White and blue", "2": "Black and red", "3": "Green and multicolor"}}),
    "pull": ("Pull valuable, then by color", "$10 and up first, then the rest by color", {
        "rules": [_rule(3, min_price=10), _rule(1, colors=["W", "U", "B"]), _rule(2, colors=["R", "G", "M"])],
        "fallback": 0,
        "names": {"0": "Colorless and lands", "1": "White, blue, black", "2": "Red, green, multicolor",
                  "3": "$10 and up"}}),
}


def preset(name: str, wanted: dict | None = None) -> dict:
    """A preset's rules. The wanted list isn't part of a preset: pass the one to keep."""
    if name not in PRESETS:
        raise ValueError(f"Unknown preset: {name}")
    rules = dict(PRESETS[name][2] or default_rules())
    rules["wanted"] = clean_wanted(wanted) if wanted else default_wanted()
    return rules


def _price(v, what):
    if v is None or v == "":
        return None
    try:
        v = round(float(v), 2)
    except (TypeError, ValueError):
        raise ValueError(f"{what} must be a number")
    if v < 0:
        raise ValueError(f"{what} can't be below zero")
    return v


def _bin(v):
    try:
        v = int(v)
    except (TypeError, ValueError):
        raise ValueError("Each rule needs a bin number")
    if v not in BINS:
        raise ValueError(f"Bins go from {BINS[0]} to {BINS[-1]}")
    return v


def clean(data) -> dict:
    """Check rules sent by the page. Raises ValueError with a plain message if something's off."""
    if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
        raise ValueError("Send {rules: [...], fallback, names}")
    if len(data["rules"]) > MAX_RULES:
        raise ValueError(f"At most {MAX_RULES} rules")
    rules = []
    for n, r in enumerate(data["rules"], 1):
        if not isinstance(r, dict):
            raise ValueError(f"Rule {n} isn't a rule")
        lo, hi = _price(r.get("min_price"), f"Rule {n}'s lowest price"), _price(r.get("max_price"), f"Rule {n}'s highest price")
        if lo is not None and hi is not None and hi <= lo:
            raise ValueError(f"Rule {n}: the highest price has to be above the lowest")
        foil = r.get("foil", "any")
        if foil not in ("any", "foil", "normal"):
            raise ValueError(f"Rule {n}: foil must be any, foil or normal")
        rules.append({
            "bin": _bin(r.get("bin")),
            "min_price": lo, "max_price": hi,
            "colors": [c for c in COLORS if c in {str(x).upper() for x in r.get("colors") or []}],
            "rarities": [x for x in RARITIES if x in {str(x).lower() for x in r.get("rarities") or []}],
            "sets": sorted({str(s).strip().upper() for s in r.get("sets") or [] if str(s).strip()})[:50],
            "foil": foil,
        })
    names = {}
    for b in BINS:
        name = str((data.get("names") or {}).get(str(b), "")).strip()[:40]
        names[str(b)] = name or f"Bin {b}"
    return {"rules": rules, "fallback": _bin(data.get("fallback", 0)), "names": names,
            "wanted": clean_wanted(data.get("wanted"))}


def parse_wanted(text) -> list[dict]:
    """[{name, qty}] from a pasted list or decklist ("4 Lightning Bolt", "1x Sol Ring (C21) 263",
    section lines...). The maybeboard is left out; the same card twice is added together."""
    from .decks import parse        # decks imports library, which imports this file
    found: dict[str, dict] = {}
    for row in parse(text):
        if row["section"] == "Maybeboard":
            continue
        key = name_key(row["name"])
        if key in found:
            found[key]["qty"] += row["qty"]
        else:
            found[key] = {"name": row["name"], "qty": row["qty"]}
    return list(found.values())


def clean_wanted(data) -> dict:
    """The wanted list from the page: {on, bin, only, others, limit, skip_basics, source,
    cards: [{name, qty}]} or, instead of cards, text (a pasted list)."""
    w = default_wanted()
    if not isinstance(data, dict):
        return w
    w["on"] = bool(data.get("on", False))
    w["bin"] = _bin(data.get("bin", w["bin"]))
    w["others"] = _bin(data.get("others", w["others"]))
    if 0 in (w["bin"], w["others"]):
        raise ValueError("Wanted cards go to bin 1, 2 or 3 (bin 0 isn't a real bin)")
    for k in ("only", "limit", "skip_basics"):
        if k in data:
            w[k] = bool(data[k])
    w["source"] = str(data.get("source") or "").strip()[:80]
    if data.get("text") is not None:
        cards = parse_wanted(data["text"])
    else:
        cards = []
        for c in data.get("cards") or []:
            if not isinstance(c, dict) or not str(c.get("name") or "").strip():
                continue
            try:
                qty = max(1, min(999, int(c.get("qty") or 1)))
            except (TypeError, ValueError):
                qty = 1
            cards.append({"name": str(c["name"]).strip()[:150], "qty": qty})
    merged: dict[str, dict] = {}
    for c in cards:
        key = name_key(c["name"])
        if key in merged:
            merged[key]["qty"] = min(999, merged[key]["qty"] + c["qty"])
        else:
            merged[key] = dict(c)
    if len(merged) > MAX_WANTED:
        raise ValueError(f"The wanted list can have at most {MAX_WANTED} different cards")
    w["cards"] = list(merged.values())
    if w["on"] and w["only"] and w["others"] == w["bin"]:
        raise ValueError(f"Wanted cards: the other cards can't also go to bin {w['bin']}")
    return w


def load() -> dict:
    """The rules in use: data/sort_rules.json if it's there, else the config.py price bins.
    Re-read only when the file changes (it's checked for every card shown)."""
    path = rules_file()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = None
    if _cache["path"] != path or _cache["mtime"] != mtime or _cache["rules"] is None:
        rules = None
        if mtime is not None:
            try:
                rules = clean(json.loads(path.read_text()))
            except (OSError, ValueError):
                rules = None   # a broken file: fall back to the price bins rather than stop sorting
        _cache.update(path=path, mtime=mtime, rules=rules or default_rules())
    return _cache["rules"]


def is_custom() -> bool:
    return rules_file().exists()


def save(data) -> dict:
    rules = clean(data)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = rules_file().with_suffix(".tmp")
    tmp.write_text(json.dumps(rules, indent=1))
    tmp.replace(rules_file())
    _cache["rules"] = None
    return rules


def reset():
    try:
        rules_file().unlink()
    except FileNotFoundError:
        pass
    _cache["rules"] = None


def color_group(colors) -> str:
    found = [c for c in str(colors or "").replace(" ", "").split(",") if c]
    return "C" if not found else found[0] if len(found) == 1 else "M"


def fits(rule: dict, card, foil: bool, price) -> bool:
    if rule["min_price"] is not None and (price is None or price < rule["min_price"]):
        return False
    if rule["max_price"] is not None and (price is None or price >= rule["max_price"]):
        return False
    if rule["colors"] and (card.colors is None or color_group(card.colors) not in rule["colors"]):
        return False
    if rule["rarities"] and (card.rarity or "").lower() not in rule["rarities"]:
        return False
    if rule["sets"] and (card.set_code or "").upper() not in rule["sets"]:
        return False
    if rule["foil"] != "any" and foil != (rule["foil"] == "foil"):
        return False
    return True


def wanted_counts(rules: dict) -> dict[str, int]:
    """{name key: copies wanted} for the wanted list in use (empty when it's off)."""
    w = rules.get("wanted") or {}
    if not w.get("on"):
        return {}
    out = {}
    for c in w.get("cards") or []:
        key = name_key(c["name"])
        if w.get("skip_basics") and key in BASICS:
            continue
        out[key] = out.get(key, 0) + int(c.get("qty") or 1)
    return out


def wanted_for(card, rules: dict, taken: dict | None = None) -> str | None:
    """The wanted list's key for this card if it should be pulled, else None. With `taken`
    ({key: copies pulled so far}, a sort run's count) and "limit" on, a card stops being
    pulled once its listed number of copies has been."""
    if card is None:
        return None
    want = wanted_counts(rules)
    key = name_key(getattr(card, "name", ""))
    if key not in want:
        return None
    if taken is not None and (rules.get("wanted") or {}).get("limit", True) and taken.get(key, 0) >= want[key]:
        return None
    return key


def unread_bin(rules: dict) -> int:
    """Where a card nobody could read goes: the "anything else" bin, unless that's the bin
    kept for wanted cards (then the bin the other cards go to)."""
    w = rules.get("wanted") or {}
    if w.get("on") and w.get("only") and rules["fallback"] == w["bin"] and wanted_counts(rules):
        return w["others"]
    return rules["fallback"]


def wanted_label(rules: dict) -> str:
    """The bin label a wanted card is saved with (what the collection and the run show)."""
    return "Wanted cards"


def pick(card, foil: bool, price, rules: dict | None = None, taken: dict | None = None) -> tuple[int, str]:
    """(bin number, bin name) for this card: a wanted card goes to the wanted bin, any other
    card by the first rule that fits. `taken`: see wanted_for."""
    rules = rules or load()
    w = rules.get("wanted") or {}
    if w.get("on") and wanted_for(card, rules, taken):
        return w["bin"], wanted_label(rules)
    bin_no = rules["fallback"]
    for rule in rules["rules"]:
        if fits(rule, card, foil, price):
            bin_no = rule["bin"]
            break
    if w.get("on") and w.get("only") and bin_no == w["bin"] and wanted_counts(rules):
        bin_no = w["others"]        # that bin is kept for the wanted cards
    return bin_no, rules["names"][str(bin_no)]


def names() -> dict:
    return load()["names"]
