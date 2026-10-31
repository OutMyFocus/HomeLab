"""Which bin each card goes into, as rules you set on the Bins page (/bins).

Rules are checked top to bottom and the first one that fits the card wins. A rule can
look at the price, the card's color, its rarity, its set and whether it's foil. A card
no rule fits goes to the "anything else" bin.

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
    return {"rules": rules, "fallback": config.NO_PRICE_BIN[0], "names": names}


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


def preset(name: str) -> dict:
    if name not in PRESETS:
        raise ValueError(f"Unknown preset: {name}")
    return PRESETS[name][2] or default_rules()


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
    return {"rules": rules, "fallback": _bin(data.get("fallback", 0)), "names": names}


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


def pick(card, foil: bool, price, rules: dict | None = None) -> tuple[int, str]:
    """(bin number, bin name) for this card, by the first rule that fits."""
    rules = rules or load()
    for rule in rules["rules"]:
        if fits(rule, card, foil, price):
            return rule["bin"], rules["names"][str(rule["bin"])]
    return rules["fallback"], rules["names"][str(rules["fallback"])]


def names() -> dict:
    return load()["names"]
