"""Playing: the games log with win rates (the Play page, /play, which also has the life
counter) and the trade binder (cards you'd trade away, on the Wishlist page). Both came
from Commander Vault.

Kept in data/games.json and data/trades.json.
"""

import json
import time
import uuid
from pathlib import Path

from flask import jsonify, request, send_from_directory

from . import config
from .database import Card
from .sorting import card_price

MAX_GAMES = 2000
MAX_BINDER = 1000


def games_file() -> Path:
    return config.DATA_DIR / "games.json"


def trades_file() -> Path:
    return config.DATA_DIR / "trades.json"


def _read(path: Path, key: str) -> list[dict]:
    try:
        items = json.loads(path.read_text(encoding="utf-8")).get(key, [])
        return [i for i in items if isinstance(i, dict) and i.get("id")]
    except (OSError, ValueError, AttributeError):
        return []


def _write(path: Path, key: str, items: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({key: items}, indent=1), encoding="utf-8")
    tmp.replace(path)


# --- Games -------------------------------------------------------------------------------------

def load_games() -> list[dict]:
    return sorted(_read(games_file(), "games"), key=lambda g: (g.get("date", ""), g.get("created", "")), reverse=True)


def _clean_game(js: dict) -> dict:
    players = []
    for p in js.get("players") or []:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "").strip()[:40]
        if name:
            players.append({"name": name, "deck": str(p.get("deck") or "").strip()[:80]})
    if len(players) < 2:
        raise ValueError("A game needs at least two players")
    if len(players) > 8:
        raise ValueError("Up to 8 players")
    try:
        winner = int(js.get("winner", 0))
    except (TypeError, ValueError):
        winner = 0
    if not 0 <= winner < len(players):
        raise ValueError("Pick who won")
    try:
        turns = int(js["turns"]) if str(js.get("turns") or "").strip() else None
    except (TypeError, ValueError):
        raise ValueError("Turns has to be a number")
    return {"date": str(js.get("date") or time.strftime("%Y-%m-%d")).strip()[:10], "turns": turns,
            "notes": str(js.get("notes") or "").strip()[:200], "winner": winner, "players": players}


def add_game(js: dict) -> dict:
    game = _clean_game(js) | {"id": uuid.uuid4().hex[:12], "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
    games = _read(games_file(), "games")
    if len(games) >= MAX_GAMES:
        raise ValueError(f"The log holds up to {MAX_GAMES} games")
    _write(games_file(), "games", games + [game])
    return game


def delete_game(game_id: str) -> bool:
    games = _read(games_file(), "games")
    keep = [g for g in games if g["id"] != game_id]
    if len(keep) == len(games):
        return False
    _write(games_file(), "games", keep)
    return True


def import_games(games: list[dict]) -> int:
    """Games from Commander Vault (players there were people or guests). Returns how many were new."""
    have = _read(games_file(), "games")
    seen = {g.get("vault_id") for g in have}
    added = 0
    for g in games:
        if not isinstance(g, dict) or g.get("id") in seen:
            continue
        players = [{"name": p.get("name") or p.get("guest") or "Player", "deck": p.get("deck", "")}
                   for p in g.get("players") or [] if isinstance(p, dict)]
        try:
            game = _clean_game({**g, "players": players})
        except ValueError:
            continue
        have.append(game | {"id": uuid.uuid4().hex[:12], "vault_id": g.get("id"),
                            "created": str(g.get("created") or time.strftime("%Y-%m-%dT%H:%M:%S"))})
        added += 1
    if added:
        _write(games_file(), "games", have)
    return added


def stats(games: list[dict]) -> dict:
    """Win rates by player and by deck, best first."""
    players, decks = {}, {}
    for g in games:
        for i, p in enumerate(g["players"]):
            won = g["winner"] == i
            a = players.setdefault(p["name"].lower(), {"label": p["name"], "games": 0, "wins": 0})
            a["games"] += 1
            a["wins"] += won
            if p.get("deck"):
                b = decks.setdefault(p["deck"].lower(), {"label": p["deck"], "games": 0, "wins": 0})
                b["games"] += 1
                b["wins"] += won

    def ranked(d):
        return sorted(d.values(), key=lambda r: (-r["wins"] / r["games"], -r["games"], r["label"]))
    return {"players": ranked(players), "decks": ranked(decks)}


# --- Trade binder --------------------------------------------------------------------------------

def load_binder() -> list[dict]:
    return _read(trades_file(), "cards")


def _binder_key(c: dict) -> str:
    return f"{c.get('name', '')}|{str(c.get('set', '')).upper()}|{c.get('number', '')}|{1 if c.get('foil') else 0}"


def add_to_binder(cards: list[dict]) -> int:
    """Add cards to the trade binder (ones already in it are skipped). Returns how many were added."""
    binder = load_binder()
    keys = {_binder_key(c) for c in binder}
    added = 0
    for c in cards:
        name = str(c.get("name") or "").strip()[:150]
        if not name:
            continue
        item = {"name": name, "set": str(c.get("set") or "").upper()[:10], "number": str(c.get("number") or "")[:12],
                "foil": bool(c.get("foil")), "qty": max(1, min(99, int(c.get("qty") or 1))),
                "card_id": str(c.get("card_id") or "")[:40]}
        if _binder_key(item) in keys or len(binder) >= MAX_BINDER:
            continue
        keys.add(_binder_key(item))
        binder.append(item | {"id": uuid.uuid4().hex[:12], "added": time.strftime("%Y-%m-%d")})
        added += 1
    if added:
        _write(trades_file(), "cards", binder)
    return added


def remove_from_binder(item_id: str) -> bool:
    binder = load_binder()
    keep = [c for c in binder if c["id"] != item_id and _binder_key(c) != item_id]
    if len(keep) == len(binder):
        return False
    _write(trades_file(), "cards", keep)
    return True


def binder_priced(scanner) -> list[dict]:
    out = []
    for c in load_binder():
        card = scanner.matcher.find_card(c["card_id"]) if c.get("card_id") else None
        card = card or Card(c.get("card_id") or c["name"], c["name"], c["set"], "", c["number"], "", None, None, None)
        price, source = card_price(card, c["foil"], scanner.vault, getattr(scanner, "live", None))
        out.append(c | {"price": price, "price_source": source, "key": _binder_key(c),
                        "image": f"https://api.scryfall.com/cards/{c['card_id']}?format=image&version=small"
                        if len(c.get("card_id") or "") == 36 else ""})
    return out


# --- Web routes ----------------------------------------------------------------------------------

def add_play_routes(app, scanner, web_dir):
    def body() -> dict:
        js = request.get_json(force=True, silent=True)
        return js if isinstance(js, dict) else {}

    def games_answer():
        games = load_games()
        return jsonify({"games": games, "stats": stats(games)})

    @app.get("/play")
    def play_page():
        return send_from_directory(web_dir, "play.html")

    @app.get("/api/games")
    def games_list():
        return games_answer()

    @app.post("/api/games/add")
    def games_add():
        try:
            add_game(body())
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return games_answer()

    @app.post("/api/games/delete")
    def games_delete():
        if not delete_game(str(body().get("id", ""))):
            return jsonify({"error": "That game isn't in the log"}), 404
        return games_answer()

    def binder_answer():
        cards = binder_priced(scanner)
        return jsonify({"cards": cards, "value": round(sum((c["price"] or 0) * c["qty"] for c in cards), 2)})

    @app.get("/api/trades")
    def trades_list():
        return binder_answer()

    @app.post("/api/trades/add")
    def trades_add():
        """{name, set, number, foil, qty, card_id} for one card, or {cards: [...]}."""
        js = body()
        cards = js["cards"] if isinstance(js.get("cards"), list) else [js]
        add_to_binder([c for c in cards if isinstance(c, dict)])
        return binder_answer()

    @app.post("/api/trades/remove")
    def trades_remove():
        if not remove_from_binder(str(body().get("id", ""))):
            return jsonify({"error": "That card isn't in the trade binder"}), 404
        return binder_answer()
