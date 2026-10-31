"""Deck checker: paste a decklist and see which cards you already own, which you're
missing, and what the missing ones would cost (the Decks page, /decks).

Decklists can come from almost anywhere: "4 Lightning Bolt", "4x Lightning Bolt",
"1 Sol Ring (C21) 263", Moxfield's "*F*" foil marks, "SB: 2 Duress", and section lines
like "Sideboard" or "Commander". Decks you save are kept in data/decks.json.
"""

import json
import re
import time
import uuid
from pathlib import Path

from flask import jsonify, request, send_from_directory

from . import config
from .database import Card
from .library import holdings, read_rows
from .live import card_from_scryfall
from .sorting import card_price

SECTIONS = {"deck": "Main deck", "main": "Main deck", "maindeck": "Main deck", "mainboard": "Main deck",
            "sideboard": "Sideboard", "side": "Sideboard", "sb": "Sideboard", "commander": "Commander",
            "commanders": "Commander", "companion": "Companion", "maybeboard": "Maybeboard",
            "maybe": "Maybeboard", "considering": "Maybeboard", "tokens": "Tokens"}
_QTY = re.compile(r"^(\d{1,3})\s*[xX]?\s+(.+)$")
_TAIL = [re.compile(p) for p in (
    r"\s+\*[A-Za-z]+\*", r"\s+#\S.*$", r"\s+\^[^^]*\^", r"\s+\[[^\]]*\]", r"\s+\([A-Za-z0-9]{2,6}\)(\s+\S+)?\s*$",
    r"\s+<[^>]*>")]
MAX_LINES = 500


def name_key(name: str) -> str:
    """Front face, lowercase: how a decklist name is matched to your cards."""
    return name.split(" // ")[0].split("/")[0].strip().lower()


def parse(text: str) -> list[dict]:
    """[{name, qty, section}], with repeated cards added together."""
    found: dict[tuple, dict] = {}
    section = "Main deck"
    for raw in str(text or "").splitlines()[:MAX_LINES]:
        line = raw.strip()
        if not line or line.startswith(("//", "#")):
            if line.lower().lstrip("/# ").rstrip(":") in SECTIONS:
                section = SECTIONS[line.lower().lstrip("/# ").rstrip(":")]
            continue
        bare = line.rstrip(":").strip().lower()
        if bare in SECTIONS or (line.endswith(":") and " " not in bare):
            section = SECTIONS.get(bare, line.rstrip(":").strip().title())
            continue
        line_section = section
        if line.upper().startswith("SB:"):
            line, line_section = line[3:].strip(), "Sideboard"
        m = _QTY.match(line)
        qty, name = (int(m.group(1)), m.group(2)) if m else (1, line)
        for pattern in _TAIL:
            name = pattern.sub("", name)
        name = name.strip()
        if not name or qty < 1:
            continue
        key = (line_section, name_key(name))
        if key in found:
            found[key]["qty"] += qty
        else:
            found[key] = {"name": name, "qty": qty, "section": line_section}
    return list(found.values())


def _cheapest_known(matcher, name: str, vault, live) -> tuple[Card | None, float | None]:
    best, best_price = None, None
    for card in matcher.printings(name) if matcher else []:
        price = card_price(card, False, vault, live)[0]
        if best is None or (price is not None and (best_price is None or price < best_price)):
            best, best_price = card, price
    return best, best_price


def check(text: str, rows: list[dict], matcher, vault=None, live=None) -> dict:
    """Compare a decklist with the collection."""
    wanted = parse(text)
    owned: dict[str, list[dict]] = {}
    for item in holdings(rows, matcher, vault, live):
        owned.setdefault(name_key(item["name"]), []).append(item)
    # Cards needed in several sections (main and sideboard) share the copies you own.
    left = {k: sum(i["qty"] for i in v) for k, v in owned.items()}
    lookups = {}
    short = [w["name"] for w in wanted if left.get(name_key(w["name"]), 0) < w["qty"]]
    if live and short:
        lookups = live.by_names(short)
    lines = []
    for w in wanted:
        key = name_key(w["name"])
        have = min(w["qty"], left.get(key, 0))
        left[key] = left.get(key, 0) - have
        mine = owned.get(key, [])
        card, price = None, None
        if mine:
            first = max(mine, key=lambda i: i["qty"])
            image, display, found = first["image"], first["name"], True
        else:
            image, display, found = "", w["name"], False
        if have < w["qty"]:
            js = lookups.get(w["name"].lower()) or lookups.get(key)
            if js:
                card = card_from_scryfall(js)
                price = card_price(card, False, vault, live)[0]
            if card is None or price is None:
                db_card, db_price = _cheapest_known(matcher, w["name"], vault, live)
                if db_card and (card is None or db_price is not None):
                    card, price = db_card, db_price
            if card:
                found, display = True, card.name
                image = image or f"https://api.scryfall.com/cards/{card.id}?format=image&version=normal"
        missing = w["qty"] - have
        lines.append({
            "name": display, "asked": w["name"], "section": w["section"], "need": w["qty"], "have": have,
            "missing": missing, "found": found, "image": image,
            "price": price if missing else None,
            "cost": round(price * missing, 2) if missing and price is not None else None,
            "where": [{"set": i["set"], "number": i["number"], "foil": i["foil"], "qty": i["qty"],
                       "bin": i["bin"], "sorted_into": i["sorted_into"]} for i in mine],
        })
    need = sum(x["need"] for x in lines)
    have = sum(x["have"] for x in lines)
    return {
        "lines": lines,
        "need": need,
        "have": have,
        "missing": need - have,
        "cost": round(sum(x["cost"] or 0 for x in lines), 2),
        "unpriced": sum(x["missing"] for x in lines if x["missing"] and x["cost"] is None),
        "unknown": [x["asked"] for x in lines if not x["found"]],
        "percent": round(100 * have / need) if need else 0,
    }


# --- Saved decks ---------------------------------------------------------------------------

def decks_file() -> Path:
    return config.DATA_DIR / "decks.json"


def load_decks() -> list[dict]:
    try:
        decks = json.loads(decks_file().read_text()).get("decks", [])
        return [d for d in decks if isinstance(d, dict) and d.get("id")]
    except (OSError, ValueError, AttributeError):
        return []


def _write(decks):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = decks_file().with_suffix(".tmp")
    tmp.write_text(json.dumps({"decks": decks}, indent=1))
    tmp.replace(decks_file())


def save_deck(name: str, text: str, deck_id: str | None = None) -> dict:
    name = (str(name or "").strip() or "Untitled deck")[:80]
    text = str(text or "")[:40000]
    decks = load_decks()
    deck = next((d for d in decks if d["id"] == deck_id), None) if deck_id else None
    if deck is None:
        deck = {"id": uuid.uuid4().hex[:12]}
        decks.append(deck)
    deck.update(name=name, text=text, updated=time.strftime("%Y-%m-%d %H:%M"))
    _write(decks)
    return deck


def delete_deck(deck_id: str) -> bool:
    decks = load_decks()
    keep = [d for d in decks if d["id"] != deck_id]
    if len(keep) == len(decks):
        return False
    _write(keep)
    return True


# --- Web routes ------------------------------------------------------------------------------

def add_deck_routes(app, scanner, web_dir):
    def body() -> dict:
        js = request.get_json(force=True, silent=True)
        return js if isinstance(js, dict) else {}

    @app.get("/decks")
    def decks_page():
        return send_from_directory(web_dir, "decks.html")

    @app.get("/api/decks")
    def decks_list():
        return jsonify({"decks": load_decks()})

    @app.post("/api/decks/check")
    def decks_check():
        text = str(body().get("text", ""))
        if not parse(text):
            return jsonify({"error": "Paste a decklist first: one card per line, like 4 Lightning Bolt"}), 400
        with scanner.lock:
            rows = read_rows(config.COLLECTION_CSV)
        return jsonify(check(text, rows, scanner.matcher, scanner.vault, getattr(scanner, "live", None)))

    @app.post("/api/decks/save")
    def decks_save():
        js = body()
        deck = save_deck(js.get("name"), js.get("text"), js.get("id"))
        return jsonify({"deck": deck, "decks": load_decks()})

    @app.post("/api/decks/delete")
    def decks_delete():
        if not delete_deck(str(body().get("id", ""))):
            return jsonify({"error": "That deck isn't saved"}), 404
        return jsonify({"decks": load_decks()})
