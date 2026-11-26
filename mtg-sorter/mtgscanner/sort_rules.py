"""Which bin each card goes into, as rules you set on the Bins page (/bins).

Rules are checked top to bottom and the first one that fits the card wins. Each rule is a
list of conditions and a bin. "All" means every condition must fit, "Any" means one is
enough, and each condition can be turned around with "not" ("not a land"). Two rules
for the same bin work as "this or that", so any mix of AND and OR can be built. A card no
rule fits goes to the "anything else" bin (the catch-all).

What a condition can look at (Nic, 2026-11-25: "full featured selection of cards i can put
in each bin"): the price (CAD), no price, colors, color identity, how many colors, card
type (lands, creatures, tokens...), words in the type line (Elf, Equipment), rarity, set,
mana value, format legality, the name, the rules text, foil, the cards in your decks (or
that fit a deck's colors), your wishlist, copies beyond the first N, EDHREC rank and Game
Changers. The type, mana value, text, identity and formats come from the card list
(card_facts.py).

Wanted cards come before all of that (Nic, 2026-11-08: "input those to go into a specific
bin"): a list of card names, pasted or taken from a deck, and the bin they go to. A card
on the list goes to that bin whatever it's worth. "Only wanted cards" keeps that bin for
them: a card the rules would put there goes to another bin you pick instead. During a
sort run the listed number of copies is pulled (4 Lightning Bolt pulls four), and later
copies are sorted as usual.

Saved in data/sort_rules.json. Without that file the bins are the price bins in
config.py, exactly as before. Rules saved before conditions (min_price, colors, rarities,
sets, foil on the rule itself) are read as the same conditions.
"""

import json
import re
from pathlib import Path

from . import card_facts, config

# The sorter's bins. Mk2 has trays 1 to 4. Bin 0 ("Unknown price", the original price
# bins' catch-all) has no tray: its cards drop into config.SORT_FALLBACK_BIN (sort_run.py).
BINS = [0, 1, 2, 3, 4]
COLORS = ["W", "U", "B", "R", "G", "M", "C"]
RARITIES = ["common", "uncommon", "rare", "mythic", "special", "bonus"]
TYPES = ["Creature", "Instant", "Sorcery", "Artifact", "Enchantment", "Planeswalker", "Land", "Battle",
         "Legendary", "Basic", "Snow", "Kindred", "Token"]
FORMATS = list(card_facts.FORMATS)
COLOR_MODES = ("any", "all", "exact", "within", "group")
FIELDS = ("price", "noprice", "color", "identity", "ncolors", "type", "typeline", "rarity", "set", "mv",
          "format", "name", "text", "foil", "deck", "wishlist", "copies", "edhrec", "gc")
# Conditions that need the card list (type line, mana value...), not only cards.db.
FACT_FIELDS = {"identity", "type", "typeline", "mv", "format", "text", "edhrec", "gc"}
MAX_RULES = 40
MAX_CONDS = 12
MAX_WANTED = 500
MAX_NAMES = 2000            # names in a name list, or a deck's names sent along to the Pi
MAX_OWNED = 50000
BASICS = {"plains", "island", "swamp", "mountain", "forest", "wastes"} | {
    f"snow-covered {b}" for b in ("plains", "island", "swamp", "mountain", "forest", "wastes")}
FILE_NAME = "sort_rules.json"

_cache: dict = {"path": None, "mtime": None, "rules": None}


def rules_file() -> Path:
    return config.DATA_DIR / FILE_NAME


def trays() -> dict:
    """The bins with a tray on the machine this app drives (Mk2: 1 to 4, first machine: 1 to 3)."""
    try:
        from .machine import load_saved, model_of
        model = model_of(load_saved())
    except Exception:
        model = getattr(config, "MACHINE_MODEL", "mk2")
    if model == "mault":
        return config.SORT_BINS_MAULT
    return config.SORT_BINS_MK2 if model == "mk2" else getattr(config, "SORT_BINS", {1: "left", 2: "centre", 3: "right"})


def name_key(name) -> str:
    """Front face, lowercase (as decks.name_key): "Fire // Ice" matches "fire"."""
    return str(name or "").split(" // ")[0].split("/")[0].strip().lower()


# --- Building rules ---------------------------------------------------------------------

def cond(field, **params) -> dict:
    return {"f": field, "not": bool(params.pop("not_", False)), **params}


def rule(bin_no, conds=(), match="all", on=True) -> dict:
    return {"bin": bin_no, "match": match, "on": on, "conds": list(conds)}


def _rule(bin_no, min_price=None, max_price=None, colors=(), rarities=(), sets=(), foil="any"):
    """A rule in the shape rules had before conditions: what the old presets and saved files say."""
    return rule(bin_no, _legacy_conds({"min_price": min_price, "max_price": max_price, "colors": list(colors),
                                       "rarities": list(rarities), "sets": list(sets), "foil": foil}))


def _legacy_conds(r: dict) -> list[dict]:
    out = []
    if r.get("min_price") not in (None, "") or r.get("max_price") not in (None, ""):
        out.append(cond("price", min=r.get("min_price"), max=r.get("max_price")))
    if r.get("colors"):
        out.append(cond("color", mode="group", colors=list(r["colors"])))
    if r.get("rarities"):
        out.append(cond("rarity", values=list(r["rarities"])))
    if r.get("sets"):
        out.append(cond("set", values=list(r["sets"])))
    if r.get("foil") in ("foil", "normal"):
        out.append(cond("foil", not_=r["foil"] == "normal"))
    return out


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


def _price_rules():
    """The original price bins (bin 3 $10+, bin 2 $1-$10, bin 1 bulk), for presets that
    take one kind of card out first and sort the rest by price."""
    return [_rule(3, min_price=10), _rule(2, min_price=1), _rule(1, min_price=0)]


def _names(**special):
    base = {"0": "Unknown price", "1": "Bulk (under $1)", "2": "$1 - $10", "3": "$10+ (valuable!)", "4": "Bin 4"}
    return {**base, **{k.lstrip("b"): v for k, v in special.items()}}


PRESETS = {
    "price": ("By price", "Valuable cards in one bin, $1 to $10 in another, bulk in a third", None),
    "lands": ("Lands in their own bin", "Every land in bin 4, the rest by price", {
        "rules": [rule(4, [cond("type", types=["Land"])])] + _price_rules(), "fallback": 0,
        "names": _names(b4="Lands")}),
    "tokens": ("Tokens out", "Tokens and emblems in bin 4, the rest by price", {
        "rules": [rule(4, [cond("type", types=["Token"])])] + _price_rules(), "fallback": 0,
        "names": _names(b4="Tokens")}),
    "junk": ("Lands and tokens out", "Tokens and basic lands in bin 4, other lands in bin 1, the rest by price", {
        "rules": [rule(4, [cond("type", types=["Token", "Basic"], mode="any")]),
                  rule(3, [cond("price", min=10)]),
                  rule(1, [cond("type", types=["Land"])]),
                  rule(2, [cond("price", min=1)]), rule(1, [cond("price", min=0)])], "fallback": 0,
        "names": _names(b1="Bulk and lands", b4="Tokens and basics")}),
    "decks": ("Cards for my decks", "Any card in one of your saved decks goes to bin 4, the rest by price", {
        "rules": [rule(4, [cond("deck", deck="", how="list")])] + _price_rules(), "fallback": 0,
        "names": _names(b4="For my decks")}),
    "deck_colors": ("Fits my decks' colors", "Cards that fit a saved deck's color identity in bin 4, the rest by price", {
        "rules": [rule(4, [cond("deck", deck="", how="colors"), cond("type", types=["Basic", "Token"], not_=True)])] + _price_rules(), "fallback": 0,
        "names": _names(b4="Fits my decks")}),
    "extras": ("Keep 4, extras out", "Your first 4 copies of a card sort by price, copy 5 and up go to bin 4", {
        "rules": [rule(4, [cond("copies", over=4), cond("type", types=["Basic"], not_=True)])] + _price_rules(),
        "fallback": 0, "names": _names(b4="Extra copies")}),
    "valuable": ("Keep the good stuff", "$5 and up in bin 3, everything else in bin 1", {
        "rules": [_rule(3, min_price=5), _rule(1, min_price=0)], "fallback": 0,
        "names": {"0": "No price", "1": "Under $5", "2": "Not used", "3": "$5 and up", "4": "Not used"}}),
    "rarity": ("By rarity", "Mythics and rares, uncommons, commons", {
        "rules": [_rule(3, rarities=["mythic", "rare"]), _rule(2, rarities=["uncommon"]),
                  _rule(1, rarities=["common"])], "fallback": 0,
        "names": {"0": "Other (tokens, promos)", "1": "Commons", "2": "Uncommons", "3": "Rares and mythics",
                  "4": "Not used"}}),
    "color": ("By color", "White and blue, black and red, green and multicolor, colorless and lands", {
        "rules": [_rule(1, colors=["W", "U"]), _rule(2, colors=["B", "R"]), _rule(3, colors=["G", "M"]),
                  _rule(4, colors=["C"])], "fallback": 0,
        "names": {"0": "Unknown", "1": "White and blue", "2": "Black and red", "3": "Green and multicolor",
                  "4": "Colorless and lands"}}),
    "pull": ("Pull valuable, then by color", "$10 and up first, then the rest by color", {
        "rules": [_rule(3, min_price=10), _rule(1, colors=["W", "U", "B"]), _rule(2, colors=["R", "G", "M"])],
        "fallback": 0,
        "names": {"0": "Colorless and lands", "1": "White, blue, black", "2": "Red, green, multicolor",
                  "3": "$10 and up", "4": "Not used"}}),
}


def preset(name: str, wanted: dict | None = None) -> dict:
    """A preset's rules. The wanted list isn't part of a preset: pass the one to keep."""
    if name not in PRESETS:
        raise ValueError(f"Unknown preset: {name}")
    rules = json.loads(json.dumps(PRESETS[name][2] or default_rules()))
    rules["wanted"] = clean_wanted(wanted) if wanted else default_wanted()
    return clean(rules)


# --- Checking what the page sends -----------------------------------------------------

def _num(v, what, whole=False):
    if v is None or v == "":
        return None
    try:
        v = int(v) if whole else round(float(v), 2)
    except (TypeError, ValueError):
        raise ValueError(f"{what} must be a number")
    if v < 0:
        raise ValueError(f"{what} can't be below zero")
    return v


_price = _num


def _bin(v):
    try:
        v = int(v)
    except (TypeError, ValueError):
        raise ValueError("Each rule needs a bin number")
    if v not in BINS:
        raise ValueError(f"Bins go from {BINS[0]} to {BINS[-1]}")
    return v


def _text(v, n=200) -> str:
    return str(v or "").strip()[:n]


def _range(c, where, whole=False):
    lo, hi = _num(c.get("min"), f"{where}: the lowest", whole), _num(c.get("max"), f"{where}: the highest", whole)
    return lo, hi


def clean_cond(c, where) -> dict:
    if not isinstance(c, dict) or c.get("f") not in FIELDS:
        raise ValueError(f"{where} isn't a condition the sorter knows")
    f = c["f"]
    out = {"f": f, "not": bool(c.get("not", False))}
    if f == "price":
        lo, hi = _range(c, where)
        if lo is not None and hi is not None and hi <= lo:
            raise ValueError(f"{where}: the highest price has to be above the lowest")
        out.update(min=lo, max=hi)
    elif f in ("mv", "ncolors"):
        lo, hi = _range(c, where)
        if lo is not None and hi is not None and hi < lo:
            raise ValueError(f"{where}: the highest has to be at least the lowest")
        out.update(min=lo, max=hi)
    elif f in ("color", "identity"):
        mode = c.get("mode", "any")
        if mode not in COLOR_MODES:
            raise ValueError(f"{where}: pick how the colors should match")
        picked = {str(x).upper() for x in c.get("colors") or []}
        out.update(mode=mode, colors=[x for x in COLORS if x in picked and (x != "M" or mode in ("group", "any"))])
    elif f == "type":
        picked = {str(x).lower() for x in c.get("types") or []}
        out.update(types=[t for t in TYPES if t.lower() in picked], mode="all" if c.get("mode") == "all" else "any")
    elif f in ("typeline", "text"):
        out["text"] = _text(c.get("text"), 120)
    elif f == "rarity":
        picked = {str(x).lower() for x in c.get("values") or []}
        out["values"] = [x for x in RARITIES if x in picked]
    elif f == "set":
        vals = c.get("values") or []
        if isinstance(vals, str):
            vals = re.split(r"[\s,]+", vals)
        out["values"] = sorted({str(s).strip().upper() for s in vals if str(s).strip()})[:80]
    elif f == "format":
        if c.get("format") not in FORMATS:
            raise ValueError(f"{where}: pick a format")
        status = c.get("status", "legal")
        if status not in ("legal", "banned", "not_legal"):
            raise ValueError(f"{where}: legal, banned or not legal")
        out.update(format=c["format"], status=status)
    elif f == "name":
        mode = c.get("mode", "contains")
        if mode not in ("contains", "starts", "list"):
            raise ValueError(f"{where}: pick how the name should match")
        out.update(mode=mode, text=str(c.get("text") or "")[:20000] if mode == "list" else _text(c.get("text"), 120))
    elif f == "deck":
        out.update(deck=_text(c.get("deck"), 60), how="colors" if c.get("how") == "colors" else "list")
        _keep_names(c, out)
        if isinstance(c.get("cis"), list):
            out["cis"] = sorted({"".join(x for x in "WUBRG" if x in str(ci).upper()) for ci in c["cis"]})[:200]
    elif f == "wishlist":
        _keep_names(c, out)
    elif f == "copies":
        n = _num(c.get("over", 4), f"{where}: the number of copies", whole=True)
        out["over"] = 4 if n is None else min(n, 999)
        owned = c.get("owned")
        if isinstance(owned, dict):
            out["owned"] = {str(k)[:150]: int(v) for k, v in list(owned.items())[:MAX_OWNED]
                            if isinstance(v, (int, float)) and v > 0}
    elif f == "edhrec":
        n = _num(c.get("max", 1000), f"{where}: the rank", whole=True)
        out["max"] = 1000 if n is None else n
    return out


def _keep_names(c, out):
    """Deck and wishlist conditions sent to the Pi carry their names (the Pi hasn't got the
    server's decks or wishlist): see resolve."""
    if isinstance(c.get("names"), list):
        out["names"] = sorted({name_key(n) for n in c["names"] if str(n).strip()})[:MAX_NAMES * 5]


def clean_rule(r, n) -> dict:
    if not isinstance(r, dict):
        raise ValueError(f"Rule {n} isn't a rule")
    conds = r.get("conds")
    if conds is None:
        # A rule saved before conditions: its price, colors, rarities, sets and foil.
        lo, hi = _price(r.get("min_price"), f"Rule {n}'s lowest price"), _price(r.get("max_price"), f"Rule {n}'s highest price")
        if lo is not None and hi is not None and hi <= lo:
            raise ValueError(f"Rule {n}: the highest price has to be above the lowest")
        if r.get("foil", "any") not in ("any", "foil", "normal"):
            raise ValueError(f"Rule {n}: foil must be any, foil or normal")
        conds = _legacy_conds(r)
    if not isinstance(conds, list):
        raise ValueError(f"Rule {n}'s conditions aren't a list")
    if len(conds) > MAX_CONDS:
        raise ValueError(f"Rule {n}: at most {MAX_CONDS} conditions")
    return {"bin": _bin(r.get("bin")), "match": "any" if r.get("match") == "any" else "all",
            "on": bool(r.get("on", True)),
            "conds": [clean_cond(c, f"Rule {n}, condition {i}") for i, c in enumerate(conds, 1)]}


def clean(data) -> dict:
    """Check rules sent by the page. Raises ValueError with a plain message if something's off."""
    if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
        raise ValueError("Send {rules: [...], fallback, names}")
    if len(data["rules"]) > MAX_RULES:
        raise ValueError(f"At most {MAX_RULES} rules")
    rules = [clean_rule(r, n) for n, r in enumerate(data["rules"], 1)]
    names = {}
    for b in BINS:
        name = str((data.get("names") or {}).get(str(b), "")).strip()[:40]
        names[str(b)] = name or (config.NO_PRICE_BIN[1] if b == config.NO_PRICE_BIN[0] else f"Bin {b}")
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
        raise ValueError(f"Wanted cards go to bin 1 to {BINS[-1]} (bin 0 isn't a real bin)")
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


# --- Saved rules ----------------------------------------------------------------------

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
    _forget()
    return rules


def reset():
    try:
        rules_file().unlink()
    except FileNotFoundError:
        pass
    _forget()


def _forget():
    """Read the rules again next time (they were saved or reset), and count them again."""
    global _counted
    _cache["rules"] = None
    _counted = None


def uses(rules: dict, *fields) -> bool:
    """Whether any rule that's on has a condition on one of these fields."""
    return any(c["f"] in fields for r in rules.get("rules", []) if r.get("on", True) for c in r.get("conds", []))


# --- Deciding -------------------------------------------------------------------------

def color_group(colors) -> str:
    found = [c for c in str(colors or "").replace(" ", "").split(",") if c]
    return "C" if not found else found[0] if len(found) == 1 else "M"


def _color_set(colors) -> set | None:
    if colors is None:
        return None
    return {c for c in str(colors).upper() if c in "WUBRG"}


def _colors_fit(mode, picked, have: set) -> bool:
    want = {c for c in picked if c in "WUBRG"}
    if mode == "group":
        g = "C" if not have else next(iter(have)) if len(have) == 1 else "M"
        return g in picked
    if mode == "any":
        return bool(have & want) or ("C" in picked and not have) or ("M" in picked and len(have) >= 2)
    if mode == "all":
        if "C" in picked and have:
            return False
        return want <= have and (bool(want) or "C" in picked)
    if mode == "exact":
        return have == want
    return have <= want                                      # "within": all its colors are among these


_WORDS = re.compile(r"[A-Za-z]+")


class Ask:
    """One card being sorted, with what the conditions might look up about it (fetched
    only when a condition needs it)."""

    def __init__(self, card, foil, price, copy=None, live=None):
        self.card, self.foil, self.price, self.copy, self.live = card, bool(foil), price, copy, live
        self._facts = None
        self.key = name_key(getattr(card, "name", ""))

    @property
    def facts(self) -> dict:
        if self._facts is None:
            self._facts = card_facts.facts(self.card, self.live)
        return self._facts

    def colors(self) -> set | None:
        return _color_set(getattr(self.card, "colors", None))

    def identity(self) -> set | None:
        ci = self.facts.get("ci")
        return _color_set(ci) if ci is not None else self.colors()

    def type_words(self) -> set:
        return {w.lower() for w in _WORDS.findall(self.facts.get("type") or "")}


def _in_range(v, lo, hi, top_excluded=False) -> bool:
    if v is None:
        return False
    if lo is not None and v < lo:
        return False
    if hi is not None and (v >= hi if top_excluded else v > hi):
        return False
    return True


def _test(c: dict, a: Ask) -> bool:
    """Whether the card fits one condition (before "not")."""
    f = c["f"]
    if f == "price":
        return _in_range(a.price, c.get("min"), c.get("max"), top_excluded=True)
    if f == "noprice":
        return a.price is None
    if f == "foil":
        return a.foil
    if f == "rarity":
        return not c["values"] or (getattr(a.card, "rarity", "") or "").lower() in c["values"]
    if f == "set":
        return not c["values"] or (getattr(a.card, "set_code", "") or "").upper() in c["values"]
    if f in ("color", "identity", "ncolors"):
        have = a.colors() if f != "identity" else a.identity()
        if have is None:
            return False
        if f == "ncolors":
            return _in_range(len(have), c.get("min"), c.get("max"))
        return not c["colors"] or _colors_fit(c["mode"], c["colors"], have)
    if f == "name":
        name = str(getattr(a.card, "name", "") or "").lower()
        if c["mode"] == "list":
            return a.key in _name_list(c["text"])
        text = c["text"].lower()
        return name.startswith(text) if c["mode"] == "starts" else text in name
    if f == "wishlist":
        return a.key in (_name_set(c["names"]) if "names" in c else _wishlist())
    if f == "deck":
        return _deck_fits(c, a)
    if f == "copies":
        return a.copy is not None and a.copy > c["over"]
    # The rest needs the card list.
    facts = a.facts
    if f == "type":
        if not c["types"]:
            return True
        words = a.type_words()

        def has(t):
            if t == "Token":
                return facts.get("token", False)
            if t == "Kindred":
                return "kindred" in words or "tribal" in words
            return t.lower() in words
        return all(map(has, c["types"])) if c["mode"] == "all" else any(map(has, c["types"]))
    if f == "typeline":
        bits = [b.strip().lower() for b in c["text"].split(",") if b.strip()]
        line = (facts.get("type") or "").lower()
        return bool(line) and (not bits or any(b in line for b in bits))
    if f == "mv":
        return _in_range(facts.get("mv"), c.get("min"), c.get("max"))
    if f == "text":
        return bool(c["text"]) and c["text"].lower() in (facts.get("text") or "").lower()
    if f == "format":
        fmt, status = c["format"], c["status"]
        if status == "banned":
            return fmt in facts.get("banned", ())
        legal = facts.get("legal")
        if legal is None or (facts.get("formats_unknown") and fmt != "commander"):
            return False            # not known: fits neither legal nor not legal
        return (fmt in legal) == (status == "legal")
    if f == "edhrec":
        rank = facts.get("edhrec")
        return rank is not None and rank <= c["max"]
    if f == "gc":
        return bool(facts.get("gc"))
    return False


def fits(rule: dict, card_or_ask, foil=False, price=None) -> bool:
    """Whether the card fits the rule: every condition ("all") or one of them ("any"). A
    rule with no conditions fits every card."""
    a = card_or_ask if isinstance(card_or_ask, Ask) else Ask(card_or_ask, foil, price)
    conds = rule.get("conds") or []
    if not conds:
        return True
    results = (_test(c, a) != c.get("not", False) for c in conds)
    return any(results) if rule.get("match") == "any" else all(results)


_lists: dict = {}


def _name_list(text: str) -> frozenset:
    """The names in a name list (one per line), as name keys. Kept for the last few lists."""
    hit = _lists.get(text)
    if hit is None:
        hit = frozenset(k for k in (name_key(line) for line in text.splitlines()) if k)
        if len(_lists) > 20:
            _lists.clear()
        _lists[text] = hit
    return hit


def _wishlist() -> frozenset:
    try:
        from .wishlist import wanted_names
        return wanted_names()
    except Exception:
        return frozenset()


_decks: dict = {"key": None, "info": None}


def deck_info() -> dict:
    """{deck id: {"name", "names" (name keys of every card but the maybeboard), "ci" (its
    color identity: the commander's, else every card's)}}. Kept until decks.json changes."""
    from . import decks
    try:
        path = decks.decks_file()
        key = (str(path), path.stat().st_mtime if path.exists() else None, card_facts._db["mtime"])
    except Exception:
        return {}
    if _decks["key"] == key and _decks["info"] is not None:
        return _decks["info"]
    out = {}
    for d in decks.load_decks():
        rows = [r for r in decks.parse(d.get("text") or "") if r["section"] not in ("Maybeboard", "Tokens")]
        commanders = [r["name"] for r in rows if r["section"] == "Commander"] or [r["name"] for r in rows]
        ci = set()
        for n in commanders:
            got = card_facts.facts(_Named(n)).get("ci")
            ci |= set(got or "")
        out[d["id"]] = {"name": d.get("name") or "Untitled deck", "names": frozenset(name_key(r["name"]) for r in rows),
                        "ci": "".join(c for c in "WUBRG" if c in ci)}
    _decks.update(key=key, info=out)
    return out


class _Named:
    def __init__(self, name):
        self.name, self.id, self.set_code, self.rarity = name, None, "", ""


def _chosen_decks(c: dict) -> list[dict]:
    """The decks a deck condition means: the one picked, or every saved deck ("")."""
    decks = deck_info()
    return [decks[c["deck"]]] if c["deck"] in decks else list(decks.values()) if not c["deck"] else []


def _deck_fits(c: dict, a: Ask) -> bool:
    if c["how"] == "list":
        if "names" in c:                     # sent along with the rules (the Pi has no decks)
            return a.key in _name_set(c["names"])
        return any(a.key in d["names"] for d in _chosen_decks(c))
    have = a.identity()
    if have is None or not a.facts.get("known"):
        return False
    cis = c["cis"] if "cis" in c else [d["ci"] for d in _chosen_decks(c) if d["names"]]
    return any(have <= set(ci) for ci in cis)


_sets: dict = {}


def _name_set(names: list) -> frozenset:
    hit = _sets.get(id(names))
    if hit is None or hit[0] is not names:
        if len(_sets) > 20:
            _sets.clear()
        hit = _sets[id(names)] = (names, frozenset(names))
    return hit[1]


def resolve(rules: dict, collection: Path | None = None) -> dict:
    """The rules with what they need from this computer written into them, for a sort run
    on the Pi (which hasn't got the server's decks or wishlist): each deck condition gets
    its decks' names, or each deck's colors, the wishlist its names, and "copies" the
    number of each card already in the collection. Conditions that already carry them
    are left alone."""
    out = json.loads(json.dumps(rules))
    for r in out.get("rules", []):
        for c in r.get("conds", []):
            if c["f"] == "deck" and "names" not in c and "cis" not in c:
                chosen = _chosen_decks(c)
                if c["how"] == "list":
                    c["names"] = sorted(set().union(*(d["names"] for d in chosen)))
                else:
                    c["cis"] = sorted({d["ci"] for d in chosen if d["names"]})
            elif c["f"] == "wishlist" and "names" not in c:
                c["names"] = sorted(_wishlist())
            elif c["f"] == "copies" and "owned" not in c and collection is not None:
                c["owned"] = dict(owned_counts(collection))
    return out


def owned_before(rules: dict, collection: Path | None = None) -> dict[str, int]:
    """{name key: copies} a sort run counts from: what the rules carry (resolve), else
    the collection file. Empty when no rule counts copies."""
    for r in rules.get("rules", []):
        for c in r.get("conds", []):
            if c["f"] == "copies" and isinstance(c.get("owned"), dict):
                return c["owned"]
    if uses(rules, "copies") and collection is not None:
        return dict(owned_counts(collection))
    return {}


_owned: dict = {"key": None, "counts": None}


def owned_counts(path: Path) -> dict[str, int]:
    """{name key: copies} in a collection file (cached until it changes)."""
    try:
        key = (str(path), path.stat().st_mtime)
    except OSError:
        return {}
    if _owned["key"] == key:
        return _owned["counts"]
    from .library import qty, read_rows
    counts: dict[str, int] = {}
    for r in read_rows(path):
        k = name_key(r.get("Name"))
        counts[k] = counts.get(k, 0) + qty(r)
    _owned.update(key=key, counts=counts)
    return counts


# The last wanted list counted, as (its "wanted" dict, a signature of it, the counts): the
# collection's bins and a sort run ask once per card, with the same rules every time. The
# dict itself is kept, so its id can't be taken by another dict meanwhile.
_counted: tuple | None = None


def wanted_counts(rules: dict) -> dict[str, int]:
    """{name key: copies wanted} for the wanted list in use (empty when it's off). The
    answer is shared: don't change it."""
    global _counted
    w = rules.get("wanted") or {}
    if not w.get("on"):
        return {}
    cards = w.get("cards") or []
    sign = (id(cards), len(cards), bool(w.get("skip_basics")))
    last = _counted
    if last is not None and last[0] is w and last[1] == sign:
        return last[2]
    out = {}
    for c in w.get("cards") or []:
        key = name_key(c["name"])
        if w.get("skip_basics") and key in BASICS:
            continue
        out[key] = out.get(key, 0) + int(c.get("qty") or 1)
    _counted = (w, sign, out)
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


def rule_for(card, foil: bool, price, rules: dict, copy=None, live=None) -> int | None:
    """The number (from 1) of the first rule that's on and fits, or None."""
    a = Ask(card, foil, price, copy, live)
    for i, r in enumerate(rules["rules"], 1):
        if r.get("on", True) and fits(r, a):
            return i
    return None


def pick(card, foil: bool, price, rules: dict | None = None, taken: dict | None = None,
         copy: int | None = None, live=None) -> tuple[int, str]:
    """(bin number, bin name) for this card: a wanted card goes to the wanted bin, any other
    card by the first rule that fits. `taken`: see wanted_for. `copy`: which copy of this
    card it is (1 for the first you own), for "copies beyond N"; None if not known."""
    rules = rules or load()
    w = rules.get("wanted") or {}
    if w.get("on") and wanted_for(card, rules, taken):
        return w["bin"], wanted_label(rules)
    n = rule_for(card, foil, price, rules, copy, live)
    bin_no = rules["rules"][n - 1]["bin"] if n else rules["fallback"]
    if w.get("on") and w.get("only") and bin_no == w["bin"] and wanted_counts(rules):
        bin_no = w["others"]        # that bin is kept for the wanted cards
    return bin_no, rules["names"][str(bin_no)]


def names() -> dict:
    return load()["names"]
