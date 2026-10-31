"""Wishlist and alerts (the Wishlist page, /wishlist, and the Settings page's alerts).

Wishlist: cards you want, each with an optional price you'd pay. The page shows today's
price and flags a card when it drops to your price, or when you've scanned one. While
scanning, a card on the wishlist is marked on the scanner page.

Alerts: the scanner page can chime and flash when a card worth more than a set amount
is saved, or when a wishlist card shows up. Kept in data/alerts.json so every phone
and laptop gets the same alerts.
"""

import json
import time
import uuid
from pathlib import Path

from flask import jsonify, request, send_from_directory

from . import config
from .decks import _cheapest_known, name_key
from .library import holdings, read_rows
from .live import card_from_scryfall
from .sorting import card_price

DEFAULT_ALERTS = {"big_card": 20.0, "sound": True, "wishlist": True}
MAX_ITEMS = 500
_cache: dict = {"mtime": None, "path": None, "names": frozenset()}


def wishlist_file() -> Path:
    return config.DATA_DIR / "wishlist.json"


def alerts_file() -> Path:
    return config.DATA_DIR / "alerts.json"


def _read(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def _write(path: Path, data):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(path)


def load_items() -> list[dict]:
    data = _read(wishlist_file(), {})
    items = data.get("items", []) if isinstance(data, dict) else []
    return [i for i in items if isinstance(i, dict) and i.get("id") and i.get("name")]


def save_items(items):
    _write(wishlist_file(), {"items": items})


def wanted_names() -> frozenset:
    """Lowercase front-face names on the wishlist (cached until the file changes)."""
    path = wishlist_file()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = None
    if _cache["path"] != path or _cache["mtime"] != mtime:
        _cache.update(path=path, mtime=mtime, names=frozenset(name_key(i["name"]) for i in load_items()))
    return _cache["names"]


def _target(v):
    if v is None or v == "":
        return None
    try:
        v = round(float(v), 2)
    except (TypeError, ValueError):
        raise ValueError("The price has to be a number")
    if v < 0:
        raise ValueError("The price can't be below zero")
    return v


def add(name: str, target=None, foil=False, note="") -> dict:
    name = str(name or "").strip()[:150]
    if not name:
        raise ValueError("Which card? Type its name")
    items = load_items()
    if len(items) >= MAX_ITEMS:
        raise ValueError(f"The wishlist holds up to {MAX_ITEMS} cards")
    for i in items:
        if name_key(i["name"]) == name_key(name) and bool(i.get("foil")) == bool(foil):
            if target not in (None, ""):
                i["target"] = _target(target)
            save_items(items)
            return i
    item = {"id": uuid.uuid4().hex[:12], "name": name, "target": _target(target), "foil": bool(foil),
            "note": str(note or "")[:200], "added": time.strftime("%Y-%m-%d")}
    items.append(item)
    save_items(items)
    return item


def update(item_id: str, **changes) -> bool:
    items = load_items()
    for i in items:
        if i["id"] == item_id:
            if "target" in changes:
                i["target"] = _target(changes["target"])
            if "note" in changes:
                i["note"] = str(changes["note"] or "")[:200]
            if "foil" in changes:
                i["foil"] = bool(changes["foil"])
            save_items(items)
            return True
    return False


def remove(item_id: str) -> bool:
    items = load_items()
    keep = [i for i in items if i["id"] != item_id]
    if len(keep) == len(items):
        return False
    save_items(keep)
    return True


def priced(items, rows, matcher, vault=None, live=None) -> list[dict]:
    """Each wishlist card with today's price, how many you own, and any alert."""
    owned: dict[str, int] = {}
    for h in holdings(rows, matcher, vault, live):
        owned[name_key(h["name"])] = owned.get(name_key(h["name"]), 0) + h["qty"]
    found = live.by_names([i["name"] for i in items]) if live and items else {}
    out = []
    for i in items:
        card, price = None, None
        if js := found.get(i["name"].lower()) or found.get(name_key(i["name"])):
            card = card_from_scryfall(js)
            price = card_price(card, i.get("foil", False), vault, live)[0]
        if price is None:
            db_card, db_price = _cheapest_known(matcher, i["name"], vault, live)
            if db_card is not None:
                card = card or db_card
                price = db_price if not i.get("foil") else card_price(db_card, True, vault, live)[0]
        have = owned.get(name_key(i["name"]), 0)
        target = i.get("target")
        out.append(i | {
            "display": card.name if card else i["name"],
            "found": card is not None,
            "price": price,
            "image": f"https://api.scryfall.com/cards/{card.id}?format=image&version=normal" if card else "",
            "set": card.set_code.upper() if card else "",
            "owned": have,
            "deal": target is not None and price is not None and price <= target,
        })
    return out


def load_alerts() -> dict:
    saved = _read(alerts_file(), {})
    return DEFAULT_ALERTS | (saved if isinstance(saved, dict) else {})


def save_alerts(js: dict) -> dict:
    alerts = load_alerts()
    if "big_card" in js:
        alerts["big_card"] = _target(js["big_card"])
    for k in ("sound", "wishlist"):
        if k in js:
            alerts[k] = bool(js[k])
    _write(alerts_file(), alerts)
    return alerts


def add_wishlist_routes(app, scanner, web_dir):
    def body() -> dict:
        js = request.get_json(force=True, silent=True)
        return js if isinstance(js, dict) else {}

    def answer():
        with scanner.lock:
            rows = read_rows(config.COLLECTION_CSV)
        items = priced(load_items(), rows, scanner.matcher, scanner.vault, getattr(scanner, "live", None))
        return jsonify({"items": items, "deals": sum(1 for i in items if i["deal"]),
                        "owned": sum(1 for i in items if i["owned"])})

    def act(fn):
        try:
            if fn() is False:
                return jsonify({"error": "That card isn't on the wishlist"}), 404
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return answer()

    @app.get("/wishlist")
    def wishlist_page():
        return send_from_directory(web_dir, "wishlist.html")

    @app.get("/api/wishlist")
    def wishlist():
        return answer()

    @app.post("/api/wishlist/add")
    def wishlist_add():
        """{name, target, foil} for one card, or {cards: [{name, qty}]} (a deck's missing cards)."""
        js = body()
        if isinstance(js.get("cards"), list):
            return act(lambda: [add(c.get("name")) for c in js["cards"] if isinstance(c, dict)])
        return act(lambda: add(js.get("name"), js.get("target"), js.get("foil"), js.get("note", "")))

    @app.post("/api/wishlist/update")
    def wishlist_update():
        js = body()
        changes = {k: js[k] for k in ("target", "note", "foil") if k in js}
        return act(lambda: update(str(js.get("id", "")), **changes))

    @app.post("/api/wishlist/remove")
    def wishlist_remove():
        return act(lambda: remove(str(body().get("id", ""))))

    @app.get("/api/alerts")
    def alerts():
        return jsonify(load_alerts())

    @app.post("/api/alerts")
    def alerts_save():
        try:
            return jsonify(save_alerts(body()))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
