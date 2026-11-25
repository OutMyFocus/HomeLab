"""What a card is, for the Bins page rules: its type line, mana value, rules text, color
identity, format legality, Game Changer mark and EDHREC rank.

The scanner's own cards.db only knows names, sets, rarity, colors and prices. The rest
comes from the card list in data/carddb.json (carddb.py, built from Scryfall's Oracle
Cards file: Settings, Commander Vault, Update now), looked up by name, or else from a
card Scryfall sent today (live.py) when the app has one cached.

Tokens aren't in carddb.json: a card it doesn't know whose set code is a token set
(T plus the set, like TMH2) counts as a token.
"""

import json
import threading

from . import carddb

# Format: its letter in carddb.json's "lg" (legal) and "bn" (banned) strings.
FORMATS = {"standard": "s", "pioneer": "p", "modern": "m", "legacy": "l", "vintage": "v",
           "pauper": "u", "commander": "c", "brawl": "b", "historic": "h", "premodern": "x",
           "oathbreaker": "o"}

_lock = threading.Lock()
_db: dict = {"mtime": None, "cards": None, "formats": False}


def name_key(name) -> str:
    """Front face, lowercase: "Fire // Ice" is found as "fire"."""
    return str(name or "").split(" // ")[0].split("/")[0].strip().lower()


def _load() -> dict:
    """{name key: carddb row}, read again when the file changes. Empty with no file."""
    path = carddb.db_file()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = None
    with _lock:
        if _db["cards"] is not None and _db["mtime"] == mtime:
            return _db["cards"]
        cards, formats = {}, False
        if mtime is not None:
            try:
                rows = json.loads(path.read_text(encoding="utf-8")).get("cards") or []
            except (OSError, ValueError):
                rows = []
            for r in rows:
                if not isinstance(r, dict) or not r.get("n"):
                    continue
                row = {k: r[k] for k in ("t", "v", "o", "ci", "b", "gc", "e", "lg", "bn") if k in r}
                formats = formats or "lg" in r
                cards.setdefault(r["n"].lower(), row)
                cards.setdefault(name_key(r["n"]), row)
        _db.update(mtime=mtime, cards=cards, formats=formats)
        return cards


def status() -> dict:
    """For the Bins page: how many cards are known, and whether formats are in the list
    (a card list built before formats were added only knows Commander)."""
    cards = _load()
    info = carddb.info()
    return {"cards": info.get("cards") or 0, "built": info.get("built"), "formats": bool(_db["formats"]),
            "have": bool(cards)}


def forget():
    with _lock:
        _db.update(mtime=None, cards=None, formats=False)


def _from_scryfall(js: dict) -> dict:
    faces = js.get("card_faces") or []
    text = js.get("oracle_text")
    if text is None:
        text = "\n//\n".join(f.get("oracle_text", "") for f in faces)
    type_line = js.get("type_line") or " // ".join(f.get("type_line", "") for f in faces)
    legal = js.get("legalities") or {}
    return {
        "type": type_line, "mv": float(js.get("cmc") or 0), "text": text or "",
        "ci": "".join(js.get("color_identity") or []),
        "legal": {f for f in FORMATS if legal.get(f) in ("legal", "restricted")},
        "banned": {f for f in FORMATS if legal.get(f) == "banned"},
        "gc": bool(js.get("game_changer")), "edhrec": js.get("edhrec_rank"),
        "token": js.get("layout") in ("token", "double_faced_token", "emblem") or "Token" in type_line,
        "known": True,
    }


def _from_row(row: dict) -> dict:
    banned = {f for f, c in FORMATS.items() if c in row.get("bn", "")}
    if row.get("b"):
        banned.add("commander")
    if "lg" in row:
        legal = {f for f, c in FORMATS.items() if c in row["lg"]}
    else:
        # an older card list: every card in it is legal in Commander unless it's banned
        legal = None if not row.get("b") else set()
    return {
        "type": row.get("t", ""), "mv": float(row.get("v") or 0), "text": row.get("o", ""),
        "ci": row.get("ci", ""), "legal": legal, "banned": banned, "gc": bool(row.get("gc")),
        "edhrec": row.get("e"), "token": "Token" in row.get("t", ""), "known": True,
    }


def looks_like_token(card) -> bool:
    """Token printings live in their own sets on Scryfall: T plus the set code (TMH2, TCMR)."""
    code = str(getattr(card, "set_code", "") or "").lower()
    return len(code) >= 4 and code.startswith("t") or (getattr(card, "rarity", "") or "").lower() == "token"


def facts(card, live=None) -> dict:
    """What's known about this card. "known" is False when neither the card list nor a
    cached Scryfall answer has it (then only "token" may be true)."""
    js = None
    if live is not None and getattr(card, "id", None):
        try:
            js = live._cached(card.id)
        except Exception:
            js = None
    if js:
        return _from_scryfall(js)
    cards = _load()
    name = str(getattr(card, "name", "") or "")
    row = cards.get(name.lower()) or cards.get(name_key(name))
    if row is not None and not looks_like_token(card):
        out = _from_row(row)
        if out["legal"] is None:
            out["legal"] = {"commander"}
            out["formats_unknown"] = True
        return out
    return {"type": "Token" if looks_like_token(card) else "", "mv": None, "text": "", "ci": None,
            "legal": None, "banned": set(), "gc": False, "edhrec": None, "token": looks_like_token(card),
            "known": False}
