"""The Home page: the scanner, the machine, the collection and the Pi's health on one screen.

/api/home gathers what each of the other pages knows into one small answer, so a phone
can show everything at a glance without opening every page.
"""

from flask import jsonify, send_from_directory

from . import accounts, config, decks, sort_rules, wishlist
from .history import per_day, sessions
from .library import holdings, make_key, note_value, read_rows, row_foil, row_id, summarize

RECENT = 8  # newest cards shown


def _small(it: dict) -> dict:
    keep = ("key", "id", "name", "set", "number", "foil", "qty", "price", "change", "bin", "image", "rarity")
    return {k: it.get(k) for k in keep}


def recent_cards(rows: list[dict], items: list[dict]) -> list[dict]:
    """The newest saved cards, newest first, each once."""
    by_key = {it["key"]: it for it in items}
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: r.get("Scanned at", ""), reverse=True):
        key = make_key(row_id(r), row_foil(r))
        if key in seen or key not in by_key:
            continue
        seen.add(key)
        out.append(_small(by_key[key]) | {"scanned_at": r.get("Scanned at", "")})
        if len(out) == RECENT:
            break
    return out


def movers(items: list[dict], n: int = 3) -> dict:
    """The cards whose price moved the most since they were scanned (by total value)."""
    moved = [it for it in items if it.get("change")]
    moved.sort(key=lambda it: it["change"] * it["qty"])
    up = [_small(it) for it in reversed(moved[-n:]) if it["change"] > 0]
    down = [_small(it) for it in moved[:n] if it["change"] < 0]
    return {"up": up, "down": down}


def scanner_info(scanner) -> dict:
    s = scanner.state()
    return {
        "status": s["status"],
        "camera": (s["camera"] or {}).get("name"),
        "waiting": s["status"] == "waiting",
        "auto": s["auto"],
        "on_table": len(s["cards"]),
        "session": {"count": s["totals"]["count"], "value": s["totals"]["value"]},
        "fps": s["perf"].get("fps"),
        "db_count": scanner.matcher.card_count,
        "learned": scanner.matcher.learned_count,
    }


def machine_info(machine) -> dict:
    if machine is None:
        return {"servos": False, "feeder": False}
    m = machine.state()
    return {"servos": m["servos"]["ok"], "servo_error": m["servos"]["error"],
            "feeder": m["feeder"]["ok"], "feeder_error": m["feeder"]["error"], "feeding": m["feeder"]["running"]}


def add_home_routes(app, scanner, machine, web_dir):
    @app.get("/api/home")
    def home_state():
        with scanner.lock:
            rows = read_rows(accounts.collection_csv())
        items = holdings(rows, scanner.matcher, scanner.vault, getattr(scanner, "live", None))
        summary = summarize(items)
        by_key = {it["key"]: it for it in items}
        found = sessions(rows)
        last = found[0] if found else None
        days = per_day(rows, 14)
        week = days[-7:]
        names = sort_rules.names()
        wanted = wishlist.wanted_names()
        owned_wanted = {decks.name_key(it["name"]) for it in items} & wanted
        return jsonify({
            "scanner": scanner_info(scanner),
            "machine": machine_info(machine),
            "collection": {
                "cards": summary["cards"], "unique": summary["names"], "value": summary["value"],
                "change": summary["change"], "sets": summary["set_count"], "foils": summary["foils"],
                "unpriced": summary["unpriced"],
                "top": [_small(by_key[k]) for k in summary["top"][:4]],
                "recent": recent_cards(rows, items),
                "movers": movers(items),
                "history": note_value(summary)[-60:],
                "bins": [{"bin": int(b), "name": names.get(str(b), f"Bin {b}"),
                          "cards": (summary["by_bin"].get(str(b)) or {}).get("cards", 0)}
                         for b in sorted((int(x) for x in names), reverse=True)],
            },
            "sessions": {
                "count": len(found),
                "last": None if last is None else {k: v for k, v in last.items() if k != "rows"},
                "week": {"cards": sum(d["cards"] for d in week), "value": round(sum(d["value"] for d in week), 2)},
                "days": days,
            },
            "wishlist": {"items": len(wishlist.load_items()), "owned": len(owned_wanted)},
            "decks": {"count": len(decks.load_decks())},
        })

    @app.get("/home")
    def home_alias():
        return send_from_directory(web_dir, "home.html")
