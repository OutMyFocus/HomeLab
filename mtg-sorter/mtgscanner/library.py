"""Your collection: every card saved in data/collection.csv, grouped, priced and exported.

The CSV stays the one true list (it's what Commander Vault imports). The Collection page
(/collection) reads it, groups the copies of each printing together, prices them with
today's prices, and can change it: quantities, foil, the printing, deleting, adding a card
by hand. Exports turn it into the formats other sites import (Moxfield, Archidekt,
Deckbox, TCGplayer, plain text).

The collection's total value is noted once a day in data/price_history.json, for the
value-over-time chart.
"""

import csv
import io
import json
import shutil
import threading
from datetime import date, datetime
from pathlib import Path

from flask import Response, jsonify, request, send_from_directory

from . import accounts, config, montreal
from .collection import COLLECTION_LOCK, COLUMNS, add_card, extra_columns, read_text, replace_csv
from .database import Card
from . import sort_rules
from .sorting import bin_for, card_price

HISTORY_FILE_NAME = "price_history.json"
COLOR_ORDER = ["W", "U", "B", "R", "G", "M", "C"]
COLOR_NAMES = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green",
               "M": "Multicolor", "C": "Colorless", "": "Unknown"}
RARITY_ORDER = ["mythic", "rare", "uncommon", "common", "special", "bonus", ""]


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


def qty(row: dict) -> int:
    try:
        return max(1, int(float(row.get("Quantity") or 1)))
    except ValueError:
        return 1


def make_key(card_id: str, foil: bool) -> str:
    return f"{card_id}#{'foil' if foil else 'normal'}"


def split_key(key: str) -> tuple[str, bool]:
    card_id, _, finish = str(key).rpartition("#")
    if not card_id:
        raise ValueError("Unknown card")
    return card_id, finish == "foil"


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
        key = make_key(row_id(r), row_foil(r))
        g = groups.setdefault(key, {"rows": [], "qty": 0, "paid_sum": 0.0, "paid_n": 0})
        g["rows"].append(r)
        g["qty"] += qty(r)
        if (p := _float(r.get("Price CAD"))) is not None:   # the price of each copy in the row
            g["paid_sum"] += p * qty(r)
            g["paid_n"] += qty(r)

    rules = sort_rules.load()   # once, not once a card
    items = []
    for key, g in groups.items():
        last = g["rows"][-1]
        card_id, foil = split_key(key)
        card = matcher.find_card(card_id) if matcher else None
        known = card is not None
        if card is None:
            card = Card(card_id, last.get("Name", ""), last.get("Set code", ""), last.get("Set name", ""),
                        last.get("Collector number", ""), last.get("Rarity", ""), None, None, None)
        price, source = card_price(card, foil, vault, live)
        scanned_price = round(g["paid_sum"] / g["paid_n"], 2) if g["paid_n"] else None
        if price is None and scanned_price is not None:
            price, source = scanned_price, "Price when it was scanned"
        bin_no, bin_label = bin_for(card, foil, price, rules)
        times = [r.get("Scanned at", "") for r in g["rows"] if r.get("Scanned at")]
        set_code = card.set_code.upper()
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
            "qty": g["qty"],
            "price": price,
            "price_source": source,
            "mtl": montreal.first(vault, card.name, foil),  # Face to Face Games, else the next Montreal store
            "value": None if price is None else round(price * g["qty"], 2),
            "scanned_price": scanned_price,
            "change": None if price is None or scanned_price is None else round(price - scanned_price, 2),
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
    priced = [it for it in items if it["value"] is not None]
    then = sum((it["scanned_price"] or 0) * it["qty"] for it in priced if it["scanned_price"] is not None)
    now = sum(it["value"] for it in priced if it["scanned_price"] is not None)
    return {
        "cards": sum(it["qty"] for it in items),
        "unique": len(items),
        "names": len({it["name"] for it in items}),
        "value": round(sum(it["value"] for it in priced), 2),
        "unpriced": sum(it["qty"] for it in items if it["value"] is None),
        "foils": sum(it["qty"] for it in items if it["foil"]),
        "change": round(now - then, 2),
        "by_color": tally("color", COLOR_ORDER),
        "by_rarity": tally("rarity", RARITY_ORDER),
        "by_bin": tally("bin"),
        "sets": sorted(sets.values(), key=lambda s: (-s["cards"], s["set"]))[:12],
        "set_count": len(sets),
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


# --- Changes ----------------------------------------------------------------------------

def _matching(rows, card_id, foil):
    return [i for i, r in enumerate(rows) if row_id(r) == card_id and row_foil(r) == foil]


def quantity(path: Path, key: str) -> int:
    """How many copies of this printing and finish the file has now (0 if none)."""
    card_id, foil = split_key(key)
    with COLLECTION_LOCK:
        rows = read_rows(path)
    return sum(qty(rows[i]) for i in _matching(rows, card_id, foil))


def set_quantity(path: Path, key: str, count: int) -> bool:
    """Keep exactly count copies (0 deletes it). Copies are added or removed newest first."""
    card_id, foil = split_key(key)
    count = max(0, int(count))
    with COLLECTION_LOCK:
        rows = read_rows(path)
        found = _matching(rows, card_id, foil)
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
        card_id, foil = split_key(key)
        keys[(card_id, foil)] = (key, int(count))
    with COLLECTION_LOCK:
        rows = read_rows(path)
        have: dict[tuple, int] = {}
        for r in rows:
            k = (row_id(r), row_foil(r))
            if k in keys:
                have[k] = have.get(k, 0) + qty(r)
        changed = {key: have.get(k, 0) for k, (key, count) in keys.items() if have.get(k, 0) not in (count, 0)}
        if changed:
            return 0, changed
        keep = [r for r in rows if (row_id(r), row_foil(r)) not in keys]
        if len(keep) != len(rows):
            write_rows(path, keep)
    return len(have), {}


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
    card_id, was = split_key(key)
    with COLLECTION_LOCK:
        rows = read_rows(path)
        found = _matching(rows, card_id, was)
        for i in found:
            rows[i]["Foil"] = "foil" if foil else "normal"
            _set_price(rows[i], price)
        if found:
            write_rows(path, rows)
    return bool(found)


def set_printing(path: Path, key: str, card: Card, price: tuple[float | None, str] | None = None) -> bool:
    """These copies are really another printing (same card, different set). price: (CAD,
    source) for that printing, or None to keep the saved price."""
    card_id, foil = split_key(key)
    with COLLECTION_LOCK:
        rows = read_rows(path)
        found = _matching(rows, card_id, foil)
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


def export_manabox(items):
    return _csv(["Name", "Set code", "Set name", "Collector number", "Foil", "Rarity", "Quantity", "Scryfall ID"],
                [[i["name"], i["set"], i["set_name"], i["number"], "foil" if i["foil"] else "normal",
                  i["rarity"], i["qty"], i["id"] if i["known"] or len(i["id"]) == 36 else ""] for i in items])


def export_moxfield(items):
    return _csv(["Count", "Tradelist Count", "Name", "Edition", "Condition", "Language", "Foil", "Tags",
                 "Last Modified", "Collector Number", "Alter", "Proxy", "Purchase Price"],
                [[i["qty"], 0, i["name"], i["set"].lower(), "Near Mint", "English", "foil" if i["foil"] else "",
                  "", "", i["number"], "False", "False", "" if i["price"] is None else f"{i['price']:.2f}"]
                 for i in items])


def export_archidekt(items):
    return _csv(["Quantity", "Name", "Finish", "Condition", "Language", "Edition Name", "Edition Code",
                 "Collector Number", "Scryfall ID", "Purchase Price"],
                [[i["qty"], i["name"], "Foil" if i["foil"] else "Normal", "NM", "EN", i["set_name"], i["set"].lower(),
                  i["number"], i["id"] if len(i["id"]) == 36 else "",
                  "" if i["price"] is None else f"{i['price']:.2f}"] for i in items])


def export_deckbox(items):
    return _csv(["Count", "Tradelist Count", "Name", "Edition", "Card Number", "Condition", "Language", "Foil",
                 "Signed", "Artist Proof", "Altered Art", "Misprint", "Promo", "Textless", "My Price"],
                [[i["qty"], 0, i["name"], i["set_name"], i["number"], "Near Mint", "English",
                  "foil" if i["foil"] else "", "", "", "", "", "", "",
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
    return _csv(["Name", "Set", "Set name", "Number", "Rarity", "Foil", "Quantity", "Price CAD", "Value CAD",
                 "Price when scanned", "Price source", "Bin now", "First scanned"],
                [[i["name"], i["set"], i["set_name"], i["number"], i["rarity"], "yes" if i["foil"] else "",
                  i["qty"], "" if i["price"] is None else f"{i['price']:.2f}",
                  "" if i["value"] is None else f"{i['value']:.2f}",
                  "" if i["scanned_price"] is None else f"{i['scanned_price']:.2f}",
                  i["price_source"], i["bin_label"], i["first"]] for i in items])


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
            card_id, was_foil = split_key(key)
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
        except (ValueError, TypeError) as e:
            return jsonify({"error": str(e) or "Bad request"}), 400
        with scanner.lock, COLLECTION_LOCK:
            deleted, changed = delete_many(accounts.collection_csv(), seen)
        if changed:
            return jsonify({"error": f"{len(changed)} of these changed since the page loaded (more were saved, "
                                     "or some taken away). Nothing was deleted: have another look, then try again.",
                            "changed": changed}), 409
        res = everything()
        res.headers["X-Deleted"] = str(deleted)
        return res

    @app.post("/api/collection/add")
    def collection_add():
        """Add a card by hand (one you didn't scan): {id, foil, qty}."""
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
                add_card(accounts.collection_csv(), card, foil, bin_for(card, foil, price[0])[1], price)
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
