"""The Sets page: how much of each set you own, what's missing, and spare copies to trade.

A set's size is the number of its cards in the card database (build_db.py --sets adds
whole sets), so "complete" means every printing the database knows for that set,
including its extra-numbered variants.
"""

import re

from flask import jsonify, request, send_from_directory

from . import config
from .decks import name_key
from .library import holdings, read_rows, row_foil, qty
from .sorting import card_price

PLAYSET = 4  # copies most players keep of a card; the rest are spares
BASIC_LANDS = {"plains", "island", "swamp", "mountain", "forest", "wastes"}


def number_key(number: str):
    """Collector numbers in the order printed: 2 before 10, 10a after 10."""
    m = re.match(r"(\d+)(.*)", number or "")
    return (0, int(m.group(1)), m.group(2)) if m else (1, 0, number or "")


def owned_by_set(rows: list[dict]) -> dict[str, dict[str, dict]]:
    """{SET: {collector number: {"qty": n, "foil": n}}} from the collection rows."""
    out: dict[str, dict[str, dict]] = {}
    for r in rows:
        code = (r.get("Set code") or "").strip().upper()
        number = (r.get("Collector number") or "").strip()
        if not code or not number:
            continue
        o = out.setdefault(code, {}).setdefault(number, {"qty": 0, "foil": 0})
        o["qty"] += qty(r)
        if row_foil(r):
            o["foil"] += qty(r)
    return out


def _price(card, vault, live):
    return card_price(card, False, vault, live)[0]


def progress(matcher, rows: list[dict], vault=None, live=None) -> list[dict]:
    """Every set in the database: how many of its cards you have, sets you've started first."""
    owned = owned_by_set(rows)
    out = []
    for code, name, total in matcher.sets():
        have = owned.get(code, {})
        n = len(have)
        out.append({"set": code, "name": name or code, "total": total, "owned": min(n, total),
                    "copies": sum(o["qty"] for o in have.values()),
                    "percent": round(100 * min(n, total) / total, 1) if total else 0})
    out.sort(key=lambda s: (-(s["owned"] > 0), -s["percent"], -s["owned"], s["name"]))
    return out


def set_detail(matcher, code: str, rows: list[dict], vault=None, live=None) -> dict | None:
    cards = matcher.set_cards(code)
    if not cards:
        return None
    have = owned_by_set(rows).get(code.upper(), {})
    items = []
    for c in sorted(cards, key=lambda c: number_key(c.collector_number)):
        o = have.get(c.collector_number) or {"qty": 0, "foil": 0}
        price = _price(c, vault, live)
        items.append({"id": c.id, "name": c.name, "number": c.collector_number, "rarity": (c.rarity or "").lower(),
                      "price": price, "qty": o["qty"], "foil": o["foil"],
                      "image": f"https://api.scryfall.com/cards/{c.id}?format=image&version=normal"})
    missing = [i for i in items if not i["qty"]]
    by_rarity: dict[str, dict] = {}
    for i in items:
        r = by_rarity.setdefault(i["rarity"] or "unknown", {"total": 0, "owned": 0})
        r["total"] += 1
        r["owned"] += 1 if i["qty"] else 0
    return {
        "set": code.upper(), "name": cards[0].set_name or code.upper(),
        "total": len(items), "owned": len(items) - len(missing),
        "missing_value": round(sum(i["price"] or 0 for i in missing), 2),
        "owned_value": round(sum((i["price"] or 0) * i["qty"] for i in items if i["qty"]), 2),
        "by_rarity": by_rarity,
        "cards": items,
    }


def spares(items: list[dict], keep: int = PLAYSET, lands: bool = False) -> list[dict]:
    """Cards you have more than `keep` copies of (any printing counts toward the copies
    you keep), most valuable spares first. Basic lands are left out unless asked."""
    by_name: dict[str, list[dict]] = {}
    for it in items:
        by_name.setdefault(name_key(it["name"]), []).append(it)
    out = []
    for key, group in by_name.items():
        if not lands and key in BASIC_LANDS:
            continue
        total = sum(it["qty"] for it in group)
        extra = total - keep
        if extra <= 0:
            continue
        # Keep the best copies, offer the cheapest ones as spares.
        cheap_first = sorted(group, key=lambda it: (it["price"] is None, it["price"] or 0))
        offered, left = [], extra
        for it in cheap_first:
            if left <= 0:
                break
            n = min(left, it["qty"])
            offered.append({k: it[k] for k in ("key", "id", "name", "set", "number", "foil", "price", "image")} | {"spare": n})
            left -= n
        out.append({"name": group[0]["name"], "have": total, "spare": extra, "printings": offered,
                    "value": round(sum((p["price"] or 0) * p["spare"] for p in offered), 2)})
    out.sort(key=lambda s: (-s["value"], -s["spare"], s["name"]))
    return out


def add_sets_routes(app, scanner, web_dir):
    def rows():
        with scanner.lock:
            return read_rows(config.COLLECTION_CSV)

    @app.get("/sets")
    def sets_page():
        return send_from_directory(web_dir, "sets.html")

    @app.get("/api/sets")
    def sets_list():
        return jsonify({"sets": progress(scanner.matcher, rows(), scanner.vault, getattr(scanner, "live", None))})

    @app.get("/api/sets/<code>")
    def sets_one(code):
        found = set_detail(scanner.matcher, code, rows(), scanner.vault, getattr(scanner, "live", None))
        if found is None:
            return jsonify({"error": "That set isn't in the card database"}), 404
        return jsonify(found)

    @app.get("/api/spares")
    def spares_list():
        try:
            keep = max(0, min(99, int(request.args.get("keep", PLAYSET))))
        except ValueError:
            keep = PLAYSET
        items = holdings(rows(), scanner.matcher, scanner.vault, getattr(scanner, "live", None))
        found = spares(items, keep, request.args.get("lands") == "1")
        return jsonify({"keep": keep, "spares": found, "cards": sum(s["spare"] for s in found),
                        "value": round(sum(s["value"] for s in found), 2)})
