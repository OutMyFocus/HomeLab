"""Your collection: every card saved in data/collection.csv, grouped, priced and exported.

The CSV stays the one true list (it's what Commander Vault imports). The Collection page
(/collection) reads it, groups the copies of each printing together, prices them with
today's prices, and can change it: quantities, foil, the printing, deleting, adding a card
by hand. Exports turn it into the formats other sites import (Moxfield, Archidekt,
Deckbox, TCGplayer, plain text).

A proxy (a printed copy standing in for the real card, Proxy column "yes") is kept and
shown like any card, marked PROXY, but it's worth nothing: it's left out of the
collection's value, its charts and the most valuable cards.

The collection's total value is noted once a day in data/price_history.json, for the
value-over-time chart, and each printing's own price in data/card_prices.json, for its price
chart and the cards that moved the most this week.
"""

import csv
import io
import json
import shutil
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Response, jsonify, request, send_from_directory

from . import accounts, config, montreal
from .collection import COLLECTION_LOCK, COLUMNS, add_card, extra_columns, read_text, replace_csv
from .database import Card
from . import sort_rules
from .sorting import bin_for, card_price

HISTORY_FILE_NAME = "price_history.json"
CARD_PRICES_FILE_NAME = "card_prices.json"
CARD_PRICE_DAYS = 400   # about a year of each card's prices is kept
TREND_DAYS = 7          # "this week": the price change since the day closest to a week ago
COLOR_ORDER = ["W", "U", "B", "R", "G", "M", "C"]
COLOR_NAMES = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green",
               "M": "Multicolor", "C": "Colorless", "": "Unknown"}
RARITY_ORDER = ["mythic", "rare", "uncommon", "common", "special", "bonus", ""]

# A card's condition, best first (blank in the file means near mint), and its language
# (blank means English). Codes as Scryfall and most sites write them.
CONDITIONS = {"NM": "Near Mint", "LP": "Lightly Played", "MP": "Moderately Played",
              "HP": "Heavily Played", "DMG": "Damaged"}
LANGUAGES = {"EN": "English", "FR": "French", "DE": "German", "ES": "Spanish", "IT": "Italian",
             "PT": "Portuguese", "JA": "Japanese", "KO": "Korean", "RU": "Russian",
             "ZHS": "Chinese Simplified", "ZHT": "Chinese Traditional", "PH": "Phyrexian"}
# What other apps write for a condition (ManaBox, Moxfield, Deckbox, TCGplayer...).
_CONDITION_WORDS = {
    "m": "NM", "mint": "NM", "nm": "NM", "near mint": "NM", "near_mint": "NM", "nearmint": "NM",
    "lp": "LP", "ex": "LP", "excellent": "LP", "lightly played": "LP", "light played": "LP",
    "light_played": "LP", "lightly_played": "LP", "slightly played": "LP", "good (lightly played)": "LP",
    "mp": "MP", "gd": "MP", "good": "MP", "played": "MP", "moderately played": "MP", "moderately_played": "MP",
    "pl": "MP", "hp": "HP", "heavily played": "HP", "heavily_played": "HP", "heavy played": "HP",
    "po": "DMG", "poor": "DMG", "d": "DMG", "dmg": "DMG", "damaged": "DMG",
}
MAX_TAG = 30
MAX_TAGS = 12


def condition_code(text) -> str:
    """NM, LP, MP, HP or DMG for whatever an app wrote ("near_mint", "Lightly Played"...).
    Blank (or something unknown) is near mint."""
    return _CONDITION_WORDS.get(str(text or "").strip().lower(), "NM")


def language_code(text) -> str:
    """EN, JA, ZHS... for a code or a name ("ja", "Japanese", "zh_CN"). Blank is English."""
    t = str(text or "").strip().lower().replace("-", "_")
    if not t:
        return "EN"
    for code, name in LANGUAGES.items():
        if t in (code.lower(), name.lower()):
            return code
    return {"zh_cn": "ZHS", "zh_hans": "ZHS", "cs": "ZHS", "zh_tw": "ZHT", "zh_hant": "ZHT", "ct": "ZHT",
            "jp": "JA", "kr": "KO", "sp": "ES", "ph": "PH"}.get(t, "EN")


def clean_tag(text) -> str:
    """A tag as it's kept: no commas (they separate tags in the file), one line, not too long."""
    return " ".join(str(text or "").replace(",", " ").split())[:MAX_TAG]


def row_tags(row: dict) -> list[str]:
    return [t for t in (clean_tag(x) for x in str(row.get("Tags") or "").split(",")) if t]


# --- Reading and writing the CSV -----------------------------------------------------

def read_rows(path: Path) -> list[dict]:
    """Every saved row (one per copy scanned, or more with Quantity above 1)."""
    with COLLECTION_LOCK:
        if not path.exists():
            return []
        text = read_text(path)   # copes with a file Excel saved (a BOM, or not UTF-8)
    return [r for r in csv.DictReader(io.StringIO(text)) if (r.get("Name") or "").strip()]


def write_rows(path: Path, rows: list[dict]):
    """Replace the whole file with these rows. Columns added by hand (Notes, say) are kept.
    Hold COLLECTION_LOCK from the read_rows() these rows came from until this returns,
    or a card saved in between is lost."""
    seen: dict = {}
    for r in rows:
        seen.update(dict.fromkeys(r))
    with COLLECTION_LOCK:
        replace_csv(path, COLUMNS + extra_columns(seen), rows)   # all at once: never half a file


def row_id(row: dict) -> str:
    """The printing a row is: its Scryfall id, or name|set|number for rows without one."""
    return (row.get("Scryfall ID") or "").strip() or \
        f"{row.get('Name', '')}|{row.get('Set code', '')}|{row.get('Collector number', '')}"


def row_foil(row: dict) -> bool:
    return (row.get("Foil") or "").strip().lower() in ("foil", "etched", "yes", "true", "1")


def row_proxy(row: dict) -> bool:
    return (row.get("Proxy") or "").strip().lower() in ("yes", "true", "1", "proxy")


def qty(row: dict) -> int:
    try:
        return max(1, int(float(row.get("Quantity") or 1)))
    except ValueError:
        return 1


def make_key(card_id: str, foil: bool, proxy: bool = False) -> str:
    """A printing and finish: id#foil or id#normal, with #proxy after it for proxies (they're
    kept apart from the real copies of the same printing)."""
    return f"{card_id}#{'foil' if foil else 'normal'}{'#proxy' if proxy else ''}"


def row_key(row: dict) -> str:
    return make_key(row_id(row), row_foil(row), row_proxy(row))


def split_key(key: str) -> tuple[str, bool, bool]:
    """(card id, foil, proxy) for a key from make_key."""
    key = str(key)
    proxy = key.endswith("#proxy")
    if proxy:
        key = key[:-len("#proxy")]
    card_id, _, finish = key.rpartition("#")
    if not card_id:
        raise ValueError("Unknown card")
    return card_id, finish == "foil", proxy


def _same(row: dict) -> tuple[str, bool, bool]:
    """What split_key gives for the row's own key."""
    return row_id(row), row_foil(row), row_proxy(row)


def _float(text) -> float | None:
    try:
        return float(text) if str(text).strip() else None
    except (TypeError, ValueError):
        return None


def color_group(colors: str | None) -> str:
    """W, U, B, R or G for one color, M for several, C for none, "" if not known."""
    if colors is None:
        return ""
    found = [c for c in str(colors).replace(" ", "").split(",") if c]
    return "C" if not found else found[0] if len(found) == 1 else "M"


# --- The collection, grouped and priced ------------------------------------------------

def holdings(rows: list[dict], matcher, vault=None, live=None) -> list[dict]:
    """One entry per printing and finish, with how many you have and what they're worth."""
    groups: dict[str, dict] = {}
    for r in rows:
        key = row_key(r)
        g = groups.setdefault(key, {"rows": [], "qty": 0, "paid_sum": 0.0, "paid_n": 0, "bought_sum": 0.0,
                                    "bought_n": 0, "cond": {}, "lang": {}, "tags": set()})
        g["rows"].append(r)
        g["qty"] += qty(r)
        if (p := _float(r.get("Price CAD"))) is not None:   # the price of each copy in the row
            g["paid_sum"] += p * qty(r)
            g["paid_n"] += qty(r)
        if (p := _float(r.get("Purchase price"))) is not None and p >= 0:   # what you paid for each
            g["bought_sum"] += p * qty(r)
            g["bought_n"] += qty(r)
        c, lang = condition_code(r.get("Condition")), language_code(r.get("Language"))
        g["cond"][c] = g["cond"].get(c, 0) + qty(r)
        g["lang"][lang] = g["lang"].get(lang, 0) + qty(r)
        g["tags"].update(row_tags(r))

    rules = sort_rules.load()   # once, not once a card
    counting = sort_rules.uses(rules, "copies")
    seen: dict[str, int] = {}
    items = []
    for key, g in groups.items():
        last = g["rows"][-1]
        card_id, foil, proxy = split_key(key)
        card = matcher.find_card(card_id) if matcher else None
        known = card is not None
        if card is None:
            card = Card(card_id, last.get("Name", ""), last.get("Set code", ""), last.get("Set name", ""),
                        last.get("Collector number", ""), last.get("Rarity", ""), None, None, None)
        price, source = card_price(card, foil, vault, live)
        scanned_price = round(g["paid_sum"] / g["paid_n"], 2) if g["paid_n"] else None
        if price is None and scanned_price is not None:
            price, source = scanned_price, "Price when it was scanned"
        copy = None
        if counting:   # which copy the first in this group is, counting the groups before it
            k = sort_rules.name_key(card.name)
            copy = seen.get(k, 0) + 1
            seen[k] = seen.get(k, 0) + g["qty"]
        bin_no, bin_label = bin_for(card, foil, price, rules, copy, live)
        times = [r.get("Scanned at", "") for r in g["rows"] if r.get("Scanned at")]
        set_code = card.set_code.upper()
        paid = round(g["bought_sum"] / g["bought_n"], 2) if g["bought_n"] else None
        conds = sorted(g["cond"].items(), key=lambda kv: (-kv[1], list(CONDITIONS).index(kv[0])))
        items.append({
            "key": key,
            "id": card_id,
            "known": known,
            "name": card.name,
            "set": set_code,
            "set_name": card.set_name or "",
            "number": card.collector_number or "",
            "rarity": (card.rarity or "").lower(),
            "colors": card.colors.split(",") if card.colors else [],
            "color": color_group(card.colors) if known else "",
            "foil": foil,
            # A proxy keeps the real card's price (good to know), but it's worth nothing to you
            "proxy": proxy,
            "qty": g["qty"],
            "price": price,
            "price_source": source,
            "mtl": montreal.first(vault, card.name, foil),  # Face to Face Games, else the next Montreal store
            "value": 0.0 if proxy else None if price is None else round(price * g["qty"], 2),
            "scanned_price": scanned_price,
            "change": None if proxy or price is None or scanned_price is None else round(price - scanned_price, 2),
            # What you paid (each, for the copies you entered it for), and what those copies gained
            "paid": paid,
            "paid_qty": g["bought_n"],
            "gain": None if proxy or price is None or paid is None else round((price - paid) * g["bought_n"], 2),
            "condition": conds[0][0],
            "mixed": len(conds) > 1,   # copies in different conditions
            "language": max(g["lang"].items(), key=lambda kv: kv[1])[0],
            "tags": sorted(g["tags"], key=str.lower),
            "bin": bin_no,
            "bin_label": bin_label,
            "sorted_into": last.get("Bin", ""),
            "first": min(times) if times else "",
            "last": max(times) if times else "",
            "image": f"https://api.scryfall.com/cards/{card_id}?format=image&version=normal" if known or
                     len(card_id) == 36 else "",
            "scryfall": f"https://scryfall.com/card/{card.set_code.lower()}/{card.collector_number}"
                        if card.set_code and card.collector_number else "",
        })
    return items


def summarize(items: list[dict]) -> dict:
    """Totals and breakdowns for the stats panel."""
    def tally(field, order=None):
        out: dict[str, dict] = {}
        for it in items:
            t = out.setdefault(str(it[field]), {"cards": 0, "value": 0.0})
            t["cards"] += it["qty"]
            t["value"] += it["value"] or 0
        for t in out.values():
            t["value"] = round(t["value"], 2)
        if order:
            out = dict(sorted(out.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else len(order)))
        return out

    sets: dict[str, dict] = {}
    for it in items:
        s = sets.setdefault(it["set"], {"set": it["set"], "name": it["set_name"], "cards": 0, "value": 0.0})
        s["cards"] += it["qty"]
        s["value"] = round(s["value"] + (it["value"] or 0), 2)
    real = [it for it in items if not it.get("proxy")]
    proxies = [it for it in items if it.get("proxy")]
    priced = [it for it in real if it["value"] is not None]
    bought = [it for it in priced if it["paid"] is not None]
    paid = sum(it["paid"] * it["paid_qty"] for it in bought)
    tags: dict[str, dict] = {}
    for it in items:
        for t in it["tags"]:
            x = tags.setdefault(t, {"tag": t, "cards": 0, "value": 0.0})
            x["cards"] += it["qty"]
            x["value"] = round(x["value"] + (it["value"] or 0), 2)
    then = sum((it["scanned_price"] or 0) * it["qty"] for it in priced if it["scanned_price"] is not None)
    now = sum(it["value"] for it in priced if it["scanned_price"] is not None)
    return {
        "cards": sum(it["qty"] for it in items),
        "unique": len(items),
        "names": len({it["name"] for it in items}),
        "value": round(sum(it["value"] for it in priced), 2),
        "unpriced": sum(it["qty"] for it in real if it["value"] is None),
        # Proxies: how many, and what the real cards would cost (none of it in "value")
        "proxies": sum(it["qty"] for it in proxies),
        "proxy_value": round(sum((it["price"] or 0) * it["qty"] for it in proxies), 2),
        "foils": sum(it["qty"] for it in items if it["foil"]),
        "change": round(now - then, 2),
        "by_color": tally("color", COLOR_ORDER),
        "by_rarity": tally("rarity", RARITY_ORDER),
        "by_bin": tally("bin"),
        "sets": sorted(sets.values(), key=lambda s: (-s["cards"], s["set"]))[:12],
        "set_count": len(sets),
        # Only the copies you entered a price paid for
        "paid": round(paid, 2),
        "paid_cards": sum(it["paid_qty"] for it in bought),
        "gain": round(sum(it["gain"] for it in bought), 2),
        "tags": sorted(tags.values(), key=lambda t: (-t["cards"], t["tag"].lower())),
        "by_condition": {c: n for c in CONDITIONS
                         if (n := sum(it["qty"] for it in items if it["condition"] == c))},
        "top": [it["key"] for it in sorted(priced, key=lambda it: -(it["price"] or 0))[:10]],
    }


# --- Value over time --------------------------------------------------------------------

def history_file() -> Path:
    return accounts.user_file(HISTORY_FILE_NAME)


_history_lock = threading.Lock()   # price_history.json: one page load changes it at a time


def load_history() -> dict:
    """Every day noted. {} only when there's no file yet. A file that can't be read is
    copied to price_history.json.bad first; OSError is raised if the file is there but
    can't be opened, so the caller never saves over it."""
    path = history_file()
    try:
        text = path.read_text()
    except FileNotFoundError:
        return {}
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except ValueError:
        pass
    try:
        shutil.copyfile(path, path.with_name(path.name + ".bad"))
    except OSError:
        pass
    return {}


def note_value(summary: dict, today: str | None = None) -> list[dict]:
    """Keep today's total value (one point per day) and return every day noted."""
    today = today or date.today().isoformat()
    point = {"value": summary["value"], "cards": summary["cards"]}
    with _history_lock:
        try:
            days = load_history()
        except OSError:   # can't read it right now: show today, but never save over it
            return [{"day": today} | point] if summary["cards"] else []
        if days.get(today) != point and summary["cards"]:
            days[today] = point
            path = history_file()
            tmp = path.with_name(path.name + ".tmp")   # backups skip .tmp files
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_text(json.dumps(dict(sorted(days.items()))))
                tmp.replace(path)   # all at once, so a reader never sees half a file
            except OSError:
                pass
    return [{"day": d} | p for d, p in sorted(days.items())]


def card_prices_file() -> Path:
    return accounts.user_file(CARD_PRICES_FILE_NAME)


_card_prices_lock = threading.Lock()
# The file as last read or written, so a page load doesn't read a year of prices again:
# {path: (modified time, data)}.
_card_prices_cache: dict = {}


def load_card_prices() -> dict:
    """{"days": [day, ...], "prices": {key: [price or None for each day]}}. Empty when
    there's no file yet. A file that can't be read is copied to card_prices.json.bad first;
    OSError is raised if it's there but can't be opened, so it's never saved over."""
    empty = {"days": [], "prices": {}}
    path = card_prices_file()
    try:
        mtime = path.stat().st_mtime_ns
        cached = _card_prices_cache.get(str(path))
        if cached and cached[0] == mtime:
            return cached[1]
        text = path.read_text()
    except FileNotFoundError:
        return empty
    try:
        data = json.loads(text)
        if (isinstance(data, dict) and isinstance(data.get("days"), list) and isinstance(data.get("prices"), dict)
                and all(isinstance(v, list) and len(v) == len(data["days"]) for v in data["prices"].values())):
            _card_prices_cache[str(path)] = (mtime, data)
            return data
    except ValueError:
        pass
    try:
        shutil.copyfile(path, path.with_name(path.name + ".bad"))
    except OSError:
        pass
    return empty


def note_card_prices(items: list[dict], today: str | None = None) -> dict:
    """Keep today's price of every printing you have (one point per day, the newest
    CARD_PRICE_DAYS days) and return all of it, as load_card_prices does."""
    today = today or date.today().isoformat()
    now = {it["key"]: it["price"] for it in items if it.get("price") is not None}
    with _card_prices_lock:
        try:
            data = load_card_prices()
        except OSError:   # can't read it right now: answer with today only, never save over it
            return {"days": [today], "prices": {k: [p] for k, p in now.items()}}
        days, prices = data["days"], data["prices"]
        changed = False
        if not days or days[-1] < today:
            days.append(today)
            for v in prices.values():
                v.append(None)
            changed = True
        if days[-1] == today:   # (a clock set back never rewrites a later day)
            for key, price in now.items():
                row = prices.setdefault(key, [None] * len(days))
                if row[-1] != price:
                    row[-1], changed = price, True
        if len(days) > CARD_PRICE_DAYS:
            cut = len(days) - CARD_PRICE_DAYS
            del days[:cut]
            for key in list(prices):
                del prices[key][:cut]
                if not any(p is not None for p in prices[key]):
                    del prices[key]
        if changed and now:
            path = card_prices_file()
            tmp = path.with_name(path.name + ".tmp")
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_text(json.dumps({"days": days, "prices": prices}, separators=(",", ":")))
                tmp.replace(path)
                _card_prices_cache[str(path)] = (path.stat().st_mtime_ns, data)
            except OSError:
                pass
    return data


def price_trend(data: dict, key: str, days: int = TREND_DAYS) -> dict | None:
    """How much a printing's price moved: today's price against the newest price noted at
    least `days` days ago (or the oldest one, when it's been noted for less time).
    {"change", "pct", "since"}, or None with nothing older than today to compare with."""
    row, noted = data["prices"].get(key), data["days"]
    if not row or row[-1] is None:
        return None
    cutoff = (date.fromisoformat(noted[-1]) - timedelta(days=days)).isoformat()
    older = [(d, p) for d, p in zip(noted[:-1], row[:-1]) if p is not None]
    if not older:
        return None
    before = [x for x in older if x[0] <= cutoff]
    since, base = before[-1] if before else older[0]
    change = round(row[-1] - base, 2)
    return {"change": change, "pct": round(100 * change / base, 1) if base else None, "since": since}


def add_trends(items: list[dict], data: dict) -> list[dict]:
    """Each item gets "trend": its price_trend (None when there's nothing to compare)."""
    for it in items:
        it["trend"] = price_trend(data, it["key"])
    return items


# --- Changes ----------------------------------------------------------------------------

def _matching(rows, card_id, foil, proxy=False):
    return [i for i, r in enumerate(rows) if _same(r) == (card_id, foil, proxy)]


def quantity(path: Path, key: str) -> int:
    """How many copies of this printing and finish the file has now (0 if none)."""
    with COLLECTION_LOCK:
        rows = read_rows(path)
    return sum(qty(rows[i]) for i in _matching(rows, *split_key(key)))


def set_quantity(path: Path, key: str, count: int) -> bool:
    """Keep exactly count copies (0 deletes it). Copies are added or removed newest first."""
    count = max(0, int(count))
    with COLLECTION_LOCK:
        rows = read_rows(path)
        found = _matching(rows, *split_key(key))
        if not found:
            return False
        have = sum(qty(rows[i]) for i in found)
        if count > have:
            extra = dict(rows[found[-1]])
            extra["Quantity"] = str(count - have)
            extra["Scanned at"] = datetime.now().isoformat(timespec="seconds")
            rows.append(extra)
        else:
            drop = have - count
            for i in reversed(found):
                if drop <= 0:
                    break
                n = qty(rows[i])
                if n <= drop:
                    rows[i] = None
                    drop -= n
                else:
                    rows[i]["Quantity"] = str(n - drop)
                    drop = 0
            rows = [r for r in rows if r is not None]
        write_rows(path, rows)
    return True


def delete_many(path: Path, seen: dict[str, int]) -> tuple[int, dict[str, int]]:
    """Delete every copy of these printings in one go. seen maps each key to the count the
    page showed. If any of them has a different count now (more were saved since, or some
    were taken away elsewhere), nothing is deleted, so no card goes unseen. Returns
    (how many printings were deleted, {key: count now} for the ones that changed)."""
    keys = {}
    for key, count in seen.items():
        keys[split_key(key)] = (key, int(count))
    with COLLECTION_LOCK:
        rows = read_rows(path)
        have: dict[tuple, int] = {}
        for r in rows:
            k = _same(r)
            if k in keys:
                have[k] = have.get(k, 0) + qty(r)
        changed = {key: have.get(k, 0) for k, (key, count) in keys.items() if have.get(k, 0) not in (count, 0)}
        if changed:
            return 0, changed
        keep = [r for r in rows if _same(r) not in keys]
        if len(keep) != len(rows):
            write_rows(path, keep)
    return len(have), {}


def set_details(path: Path, keys: list[str], condition: str | None = None, language: str | None = None,
                paid: float | None | bool = False, tags: list[str] | None = None,
                add_tag: str = "", remove_tag: str = "", proxy: bool | None = None) -> int:
    """Change every copy of these printings at once: their condition, language, the price
    paid for each (None clears it; False leaves it), their tags (a whole new list), add
    or take off one tag, or mark them proxies (proxy True) or real cards (False). Returns
    how many printings were found."""
    wanted = set()
    for key in keys:
        wanted.add(split_key(key))
    with COLLECTION_LOCK:
        rows = read_rows(path)
        found = set()
        for r in rows:
            k = _same(r)
            if k not in wanted:
                continue
            found.add(k)
            if condition is not None:
                r["Condition"] = "" if condition == "NM" else condition
            if language is not None:
                r["Language"] = "" if language == "EN" else language
            if paid is not False:
                r["Purchase price"] = "" if paid is None else f"{paid:.2f}"
            if tags is not None or add_tag or remove_tag:
                have = tags if tags is not None else row_tags(r)
                have = [t for t in have if t.lower() != remove_tag.lower()] if remove_tag else list(have)
                if add_tag and add_tag.lower() not in (t.lower() for t in have):
                    have.append(add_tag)
                r["Tags"] = ", ".join(have[:MAX_TAGS])
            if proxy is not None:
                r["Proxy"] = "yes" if proxy else ""
        if found:
            write_rows(path, rows)
    return len(found)


def change_quantity(path: Path, key: str, step: int) -> int | None:
    """One more (step 1) or one fewer (step -1) copy than the file has right now, not
    than the page last showed, so copies saved since are kept. Returns the new count,
    or None if the card isn't in the collection."""
    with COLLECTION_LOCK:
        have = quantity(path, key)
        if not have:
            return None
        count = max(0, have + int(step))
        set_quantity(path, key, count)
    return count


def _set_price(row: dict, price: tuple[float | None, str] | None):
    """A correction prices the copies again, as the printing or finish they really are, so
    the old printing's price doesn't show as a price change."""
    if price is not None:
        cad, source = price
        row["Price CAD"] = "" if cad is None else f"{cad:.2f}"
        row["Price source"] = source if cad is not None else ""


def set_foil(path: Path, key: str, foil: bool, price: tuple[float | None, str] | None = None) -> bool:
    """price: (CAD, source) for the new finish, or None to keep the saved price."""
    card_id, was, proxy = split_key(key)
    with COLLECTION_LOCK:
        rows = read_rows(path)
        found = _matching(rows, card_id, was, proxy)
        for i in found:
            rows[i]["Foil"] = "foil" if foil else "normal"
            _set_price(rows[i], price)
        if found:
            write_rows(path, rows)
    return bool(found)


def set_printing(path: Path, key: str, card: Card, price: tuple[float | None, str] | None = None) -> bool:
    """These copies are really another printing (same card, different set). price: (CAD,
    source) for that printing, or None to keep the saved price."""
    with COLLECTION_LOCK:
        rows = read_rows(path)
        found = _matching(rows, *split_key(key))
        for i in found:
            rows[i].update({"Name": card.name, "Set code": card.set_code.upper(), "Set name": card.set_name,
                            "Collector number": card.collector_number, "Rarity": card.rarity,
                            "Scryfall ID": card.id})
            _set_price(rows[i], price)
        if found:
            write_rows(path, rows)
    return bool(found)


# --- Exports ------------------------------------------------------------------------------

def _csv(header: list[str], lines: list[list]) -> str:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(header)
    w.writerows(lines)
    return out.getvalue()


def _cond(i) -> str:
    return i.get("condition") or "NM"


def _lang(i) -> str:
    return i.get("language") or "EN"


def _bought(i) -> str:
    """What you paid for each copy, else today's price (what other sites take as its cost)."""
    p = i["paid"] if i.get("paid") is not None else i["price"]
    return "" if p is None else f"{p:.2f}"


MANABOX_CONDITIONS = {"NM": "near_mint", "LP": "excellent", "MP": "good", "HP": "played", "DMG": "poor"}
DECKBOX_CONDITIONS = {"NM": "Near Mint", "LP": "Good (Lightly Played)", "MP": "Played", "HP": "Heavily Played",
                      "DMG": "Poor"}
ARCHIDEKT_CONDITIONS = {"NM": "NM", "LP": "LP", "MP": "MP", "HP": "HP", "DMG": "D"}


def export_manabox(items):
    return _csv(["Name", "Set code", "Set name", "Collector number", "Foil", "Rarity", "Quantity", "Scryfall ID",
                 "Condition", "Language", "Purchase price", "Purchase price currency"],
                [[i["name"], i["set"], i["set_name"], i["number"], "foil" if i["foil"] else "normal",
                  i["rarity"], i["qty"], i["id"] if i["known"] or len(i["id"]) == 36 else "",
                  MANABOX_CONDITIONS[_cond(i)], _lang(i).lower(),
                  "" if i.get("paid") is None else f"{i['paid']:.2f}", "" if i.get("paid") is None else "CAD"]
                 for i in items])


def export_moxfield(items):
    return _csv(["Count", "Tradelist Count", "Name", "Edition", "Condition", "Language", "Foil", "Tags",
                 "Last Modified", "Collector Number", "Alter", "Proxy", "Purchase Price"],
                [[i["qty"], 0, i["name"], i["set"].lower(), CONDITIONS[_cond(i)], LANGUAGES[_lang(i)],
                  "foil" if i["foil"] else "", ", ".join(i.get("tags") or []), "", i["number"], "False",
                  "True" if i.get("proxy") else "False",
                  _bought(i)] for i in items])


def export_archidekt(items):
    return _csv(["Quantity", "Name", "Finish", "Condition", "Language", "Edition Name", "Edition Code",
                 "Collector Number", "Scryfall ID", "Purchase Price", "Tags"],
                [[i["qty"], i["name"], "Foil" if i["foil"] else "Normal", ARCHIDEKT_CONDITIONS[_cond(i)], _lang(i),
                  i["set_name"], i["set"].lower(), i["number"], i["id"] if len(i["id"]) == 36 else "",
                  _bought(i), ", ".join(i.get("tags") or [])] for i in items])


def export_deckbox(items):
    return _csv(["Count", "Tradelist Count", "Name", "Edition", "Card Number", "Condition", "Language", "Foil",
                 "Signed", "Artist Proof", "Altered Art", "Misprint", "Promo", "Textless", "My Price"],
                [[i["qty"], 0, i["name"], i["set_name"], i["number"], DECKBOX_CONDITIONS[_cond(i)],
                  LANGUAGES[_lang(i)], "foil" if i["foil"] else "", "", "", "", "", "", "",
                  "" if i["price"] is None else f"${i['price']:.2f}"] for i in items])


def export_tcgplayer(items):
    return "".join(f"{i['qty']} {i['name']} [{i['set']}]\n" for i in items)


def export_text(items):
    return "".join(f"{i['qty']} {i['name']} ({i['set']}) {i['number']}{' *F*' if i['foil'] else ''}\n"
                   for i in items)


def export_names(items):
    counts: dict[str, int] = {}
    for i in items:
        counts[i["name"]] = counts.get(i["name"], 0) + i["qty"]
    return "".join(f"{n} {name}\n" for name, n in sorted(counts.items()))


def export_prices(items):
    """A spreadsheet of everything with today's prices (opens in Excel or Google Sheets)."""
    money = lambda v: "" if v is None else f"{v:.2f}"   # noqa: E731
    return _csv(["Name", "Set", "Set name", "Number", "Rarity", "Foil", "Quantity", "Price CAD", "Value CAD",
                 "Price when scanned", "Paid each", "Gain on what you paid", "Condition", "Language", "Tags",
                 "Price source", "Bin now", "First scanned", "Proxy"],
                [[i["name"], i["set"], i["set_name"], i["number"], i["rarity"], "yes" if i["foil"] else "",
                  i["qty"], money(i["price"]), money(i["value"]), money(i["scanned_price"]),
                  money(i.get("paid")), money(i.get("gain")), _cond(i), _lang(i), ", ".join(i.get("tags") or []),
                  i["price_source"], i["bin_label"], i["first"], "yes" if i.get("proxy") else ""] for i in items])


# id: (what the menu says, what it's for, file extension, function)
EXPORTS = {
    "moxfield": ("Moxfield", "Moxfield: Collection, Import, CSV", "csv", export_moxfield),
    "archidekt": ("Archidekt", "Archidekt: Collection, Import, pick the CSV", "csv", export_archidekt),
    "deckbox": ("Deckbox", "Deckbox: Inventory, Import", "csv", export_deckbox),
    "manabox": ("ManaBox / Commander Vault", "ManaBox, or Commander Vault's Import a ManaBox CSV", "csv",
                export_manabox),
    "tcgplayer": ("TCGplayer mass entry", "Paste into TCGplayer's Mass Entry box", "txt", export_tcgplayer),
    "text": ("Text list", "1 Card (SET) 123: pastes into Moxfield, Archidekt, MTGA-style lists", "txt",
             export_text),
    "names": ("Names only", "One line per card name with how many you have", "txt", export_names),
    "prices": ("Spreadsheet with prices", "Opens in Excel or Google Sheets", "csv", export_prices),
}


def export(items: list[dict], fmt: str) -> tuple[str, str, str]:
    """Returns (text, file name, mime type)."""
    if fmt not in EXPORTS:
        raise ValueError(f"Unknown export format: {fmt}")
    _, _, ext, fn = EXPORTS[fmt]
    items = sorted(items, key=lambda i: (i["name"].lower(), i["set"], i["number"], i["foil"]))
    mime = "text/csv" if ext == "csv" else "text/plain"
    return fn(items), f"collection-{fmt}-{date.today().isoformat()}.{ext}", mime


# --- Finding a card by id ----------------------------------------------------------------

def lookup(scanner, card_id: str) -> Card | None:
    """A card from the database, or from Scryfall if it's a printing the database doesn't
    have (then it's remembered, so the collection and training know it later)."""
    card_id = str(card_id or "")
    card = scanner.matcher.find_card(card_id) if card_id else None
    live = getattr(scanner, "live", None)
    if card is None and live and card_id and (card := live.card(card_id)):
        scanner.matcher.remember(card)
    elif card is not None and live:
        live.card_json(card_id)  # today's price, fetched before any lock is taken
    return card


# --- Web routes ---------------------------------------------------------------------------

def add_collection_routes(app, scanner, web_dir):
    """The Collection page and its API, added to the scanner app."""
    refresh = {"running": False, "done": 0, "total": 0, "updated": 0, "error": ""}
    refresh_lock = threading.Lock()

    def current() -> list[dict]:
        with scanner.lock:
            rows = read_rows(accounts.collection_csv())
        return holdings(rows, scanner.matcher, scanner.vault, getattr(scanner, "live", None))

    def everything():
        items = current()
        add_trends(items, note_card_prices(items))
        summary = summarize(items)
        live = getattr(scanner, "live", None)
        return jsonify({
            "cards": items,
            "summary": summary,
            "history": note_value(summary),
            "live": bool(live),
            "refresh": dict(refresh),
            "prices": (f"Commander Vault prices, {scanner.vault.date}" if scanner.vault else
                       f"Scryfall {'live ' if live else ''}prices, US$1 = CA${config.USD_TO_CAD:.4f}"),
            "exports": [{"id": k, "label": v[0], "hint": v[1]} for k, v in EXPORTS.items()],
            "bins": [{"bin": int(n), "label": label} for n, label in sort_rules.names().items()],
            # As [code, name] lists: jsonify would put a dict's keys in A-Z order
            "conditions": list(CONDITIONS.items()),
            "languages": list(LANGUAGES.items()),
        })

    def body() -> dict:
        js = request.get_json(force=True, silent=True)
        return js if isinstance(js, dict) else {}

    @app.get("/collection")
    def collection_page():
        return send_from_directory(web_dir, "collection.html")

    @app.get("/api/collection")
    def collection():
        return everything()

    @app.get("/api/collection/price-history")
    def collection_price_history():
        """One printing's noted prices: {key, points: [{day, price}], trend}."""
        key = request.args.get("key", "")
        try:
            data = load_card_prices()
        except OSError:
            data = {"days": [], "prices": {}}
        row = data["prices"].get(key) or []
        points = [{"day": d, "price": p} for d, p in zip(data["days"], row) if p is not None]
        return jsonify({"key": key, "points": points, "trend": price_trend(data, key) if row else None})

    def whole(value, low, high, what) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value != int(value) \
                or not low <= value <= high:
            raise ValueError(f"{what} must be a whole number from {low} to {high}")
        return int(value)

    @app.post("/api/collection/edit")
    def collection_edit():
        """Change one printing: {key, step} (one more or fewer than there are now) /
        {key, qty} / {key, foil} / {key, printing: id} / {key, delete: true, seen}.
        With seen (the count the page showed), a delete is refused when more copies were
        saved since, so they aren't deleted unseen."""
        js = body()
        key = str(js.get("key", ""))
        live = getattr(scanner, "live", None)
        try:
            card_id, was_foil, _ = split_key(key)
            new_card = lookup(scanner, js["printing"]) if js.get("printing") else None
            if js.get("printing") and new_card is None:
                return jsonify({"error": "Couldn't find that printing"}), 404
            # The corrected copies get the price of what they really are (see _set_price).
            if new_card:
                new_price = card_price(new_card, was_foil, scanner.vault, live)
            elif "foil" in js and bool(js["foil"]) != was_foil:
                known = scanner.matcher.find_card(card_id)
                new_price = card_price(known, bool(js["foil"]), scanner.vault, live) if known else (None, "")
            else:
                new_price = None
            with scanner.lock, COLLECTION_LOCK:
                path = accounts.collection_csv()
                if js.get("delete"):
                    if js.get("seen") is not None:
                        seen = whole(js["seen"], 0, 1_000_000, "seen")
                        have = quantity(path, key)
                        if have and have != seen:
                            return jsonify({"error": f"You have {have} of these now, not {seen}: more were "
                                                     "saved since the page loaded. Have another look, then "
                                                     "delete again.", "qty": have}), 409
                    ok = set_quantity(path, key, 0)
                elif "step" in js:
                    ok = change_quantity(path, key, whole(js["step"], -100, 100, "The step")) is not None
                elif "qty" in js:
                    ok = set_quantity(path, key, int(js["qty"]))
                elif "foil" in js:
                    ok = set_foil(path, key, bool(js["foil"]), new_price)
                elif new_card:
                    ok = set_printing(path, key, new_card, new_price)
                else:
                    return jsonify({"error": "Nothing to change"}), 400
        except (ValueError, TypeError) as e:
            return jsonify({"error": str(e) or "Bad request"}), 400
        if not ok:
            return jsonify({"error": "That card isn't in the collection any more"}), 404
        return everything()

    @app.post("/api/collection/delete")
    def collection_delete():
        """Delete many printings at once (the Collection page's Select): {cards: {key: seen}},
        seen being how many the page showed. Refused, with nothing deleted, when any of
        them has more or fewer copies now."""
        js = body()
        cards = js.get("cards")
        if not isinstance(cards, dict) or not cards or len(cards) > 20_000:
            return jsonify({"error": "Pick some cards to delete"}), 400
        try:
            seen = {str(k): whole(v, 0, 1_000_000, "seen") for k, v in cards.items()}
            for k in seen:
                split_key(k)
        except (ValueError, TypeError):
            # A message of its own, not the exception's text (that stays out of answers)
            return jsonify({"error": "Each card needs its key and how many the page showed (a whole number)"}), 400
        with scanner.lock, COLLECTION_LOCK:
            deleted, changed = delete_many(accounts.collection_csv(), seen)
        if changed:
            return jsonify({"error": f"{len(changed)} of these changed since the page loaded (more were saved, "
                                     "or some taken away). Nothing was deleted: have another look, then try again.",
                            "changed": changed}), 409
        res = everything()
        res.headers["X-Deleted"] = str(deleted)
        return res

    @app.post("/api/collection/details")
    def collection_details():
        """Condition, language, price paid, tags and proxy, for one card or many (Select):
        {keys: [...], condition: "LP", language: "JA", paid: 4.5 (null clears it),
        tags: [...] (the whole list), add_tag: "...", remove_tag: "...",
        proxy: true (they're proxies) or false (real cards)}."""
        js = body()
        keys = js.get("keys")
        if not isinstance(keys, list) or not keys or len(keys) > 20_000:
            return jsonify({"error": "Pick some cards first"}), 400
        change: dict = {}
        if js.get("condition") is not None:
            if str(js["condition"]).upper() not in CONDITIONS:
                return jsonify({"error": "The condition is one of " + ", ".join(CONDITIONS)}), 400
            change["condition"] = str(js["condition"]).upper()
        if js.get("language") is not None:
            if str(js["language"]).upper() not in LANGUAGES:
                return jsonify({"error": "Unknown language"}), 400
            change["language"] = str(js["language"]).upper()
        if "paid" in js:
            p = js["paid"]
            if p in (None, ""):
                change["paid"] = None
            elif isinstance(p, bool) or not isinstance(p, (int, float)) or not 0 <= p <= 1_000_000:
                return jsonify({"error": "The price paid is a number of dollars, like 4.50"}), 400
            else:
                change["paid"] = round(float(p), 2)
        if js.get("tags") is not None:
            if not isinstance(js["tags"], list):
                return jsonify({"error": "Tags are a list"}), 400
            seen, tags = set(), []
            for t in map(clean_tag, js["tags"]):
                if t and t.lower() not in seen:
                    seen.add(t.lower())
                    tags.append(t)
            change["tags"] = tags[:MAX_TAGS]
        for k in ("add_tag", "remove_tag"):
            if js.get(k):
                change[k] = clean_tag(js[k])
        if js.get("proxy") is not None:
            if not isinstance(js["proxy"], bool):
                return jsonify({"error": "proxy is true or false"}), 400
            change["proxy"] = js["proxy"]
        if not change:
            return jsonify({"error": "Nothing to change"}), 400
        try:
            with scanner.lock, COLLECTION_LOCK:
                found = set_details(accounts.collection_csv(), [str(k) for k in keys], **change)
        except ValueError:
            return jsonify({"error": "Unknown card"}), 400
        if not found:
            return jsonify({"error": "Those cards aren't in the collection any more"}), 404
        return everything()

    @app.post("/api/collection/add")
    def collection_add():
        """Add a card by hand (one you didn't scan): {id, foil, qty, proxy}."""
        js = body()
        card = lookup(scanner, js.get("id"))
        if card is None:
            return jsonify({"error": "Unknown card"}), 404
        try:
            count = min(100, max(1, int(js.get("qty", 1))))
        except (TypeError, ValueError):
            return jsonify({"error": "Quantity must be a number"}), 400
        foil = bool(js.get("foil"))
        live = getattr(scanner, "live", None)
        price = card_price(card, foil, scanner.vault, live)
        with scanner.lock:
            for _ in range(count):
                add_card(accounts.collection_csv(), card, foil, bin_for(card, foil, price[0])[1], price,
                         proxy=bool(js.get("proxy")))
        return everything()

    @app.post("/api/collection/refresh")
    def collection_refresh():
        """Fetch today's Scryfall price for every card in the collection, in the background."""
        live = getattr(scanner, "live", None)
        if not live:
            return jsonify({"error": "Live prices are off (the app was started with --offline)"}), 400
        with refresh_lock:
            if refresh["running"]:
                return jsonify({"refresh": dict(refresh)})
            ids = [i["id"] for i in current() if len(i["id"]) == 36]
            refresh.update(running=True, done=0, total=len(ids), updated=0, error="")

        def progress(done, total):
            refresh.update(done=done, total=total)

        def work():
            try:
                refresh["updated"] = live.fetch_many(ids, progress)
                if ids and not refresh["updated"] and live.cached_count() == 0:
                    refresh["error"] = "Couldn't reach Scryfall. Is the internet working?"
            except Exception as e:  # never leave it stuck on "running"
                refresh["error"] = str(e)
            finally:
                refresh.update(running=False, done=refresh["total"])

        threading.Thread(target=work, daemon=True).start()
        return jsonify({"refresh": dict(refresh)})

    @app.get("/api/collection/refresh")
    def collection_refresh_state():
        return jsonify({"refresh": dict(refresh)})

    @app.route("/api/collection/export", methods=["GET", "POST"])
    def collection_export():
        """Download the collection in another site's format. POST {format, keys} exports
        only those cards (what the page's filters show)."""
        js = body() if request.method == "POST" else {}
        fmt = str(js.get("format") or request.args.get("format", "moxfield"))
        items = current()
        if isinstance(js.get("keys"), list):
            keep = set(map(str, js["keys"]))
            items = [i for i in items if i["key"] in keep]
        try:
            text, name, mime = export(items, fmt)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return Response(text, mimetype=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})
