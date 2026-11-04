"""Upgrade paths for Commander decks (the Upgrade path panel in the Decks page's deck builder).

What "best" means here comes from EDHREC: for each commander it knows which cards
thousands of real decks play (how many of them, and how much more than other decks in
those colors). This module fetches that page for a commander, keeps a copy in
data/edhrec/ for a week (and uses the old copy when EDHREC can't be reached), and puts a
Canadian price on each card. The page (webui/upgrades.js) does the rest: it compares the
list with your deck, pairs the weakest cards with better ones, and splits the swaps into
steps, from the fewest changes to the most.

    GET /api/decks/upgrades?commander=Ghoulcaller Gisa
"""

import json
import re
import time
import unicodedata
from pathlib import Path

import requests
from flask import jsonify, request

from . import config
from .live import card_from_scryfall
from .sorting import card_price

PAGE = "https://json.edhrec.com/pages/commanders/{slug}.json"
SITE = "https://edhrec.com/commanders/{slug}"
TTL = 7 * 24 * 3600
MAX_CARDS = 300


def slug(name: str) -> str:
    """EDHREC's page name for a commander: "Atraxa, Praetors' Voice" -> atraxa-praetors-voice."""
    front = str(name or "").split(" // ")[0]
    plain = unicodedata.normalize("NFKD", front).encode("ascii", "ignore").decode().lower()
    plain = re.sub(r"['’\"]", "", plain)
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def cache_file(s: str) -> Path:
    return config.DATA_DIR / "edhrec" / f"{s}.json"


def fetch_page(s: str) -> dict | None:
    """EDHREC's JSON for a commander, or None when EDHREC has no page for it."""
    r = requests.get(PAGE.format(slug=s), timeout=20,
                     headers={"User-Agent": config.USER_AGENT, "Accept": "application/json"})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    js = r.json()
    # A commander EDHREC doesn't know sometimes comes back as a redirect page instead of a 404.
    return js if isinstance(js, dict) and (js.get("container") or {}).get("json_dict") else None


def compact(raw: dict) -> dict:
    """The parts of an EDHREC page the upgrade path needs."""
    cards, decks = {}, 0
    for group in raw["container"]["json_dict"].get("cardlists") or []:
        for v in group.get("cardviews") or []:
            name = v.get("name")
            if not name:
                continue
            total = v.get("potential_decks") or 0
            decks = max(decks, total)
            row = {"n": name, "inc": round((v.get("num_decks") or 0) / total, 3) if total else 0,
                   "syn": round(v.get("synergy") or 0, 3), "cat": group.get("header") or ""}
            if name not in cards or row["inc"] > cards[name]["inc"]:
                cards[name] = row
    rows = sorted(cards.values(), key=lambda r: -(r["inc"] + max(r["syn"], 0)))[:MAX_CARDS]
    return {"decks": decks, "lands": raw.get("land"), "basics": raw.get("basic"), "cards": rows,
            "fetched": time.strftime("%Y-%m-%d")}


def recommendations(commander: str, online: bool = True, fetch=None) -> dict:
    """{source: "edhrec", ...} for the commander, or {source: "none", error} when there's no list."""
    fetch = fetch or fetch_page
    s = slug(commander)
    if not s:
        return {"source": "none", "error": "Set a commander first"}
    path = cache_file(s)
    cached = None
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    fresh = cached and time.time() - path.stat().st_mtime < TTL
    if not fresh and online:
        try:
            raw = fetch(s)
            if raw is None:
                cached = {"missing": True, "fetched": time.strftime("%Y-%m-%d")}
            else:
                cached = compact(raw)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(cached, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
        except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError, OSError):
            pass  # keep the old copy, if there is one
    if not cached:
        return {"source": "none", "error": "Couldn't reach EDHREC, so these suggestions use the most played "
                                            "Commander cards in your colors instead"}
    if cached.get("missing"):
        return {"source": "none", "error": f"EDHREC has no decks for {commander} yet, so these suggestions use "
                                            "the most played Commander cards in your colors instead"}
    return {"source": "edhrec", "url": SITE.format(slug=s), **cached}


def add_prices(cards: list[dict], vault=None, live=None) -> None:
    """Put a CAD price ("p") on each card: the Canadian store price, else Scryfall's US price
    times the exchange rate. Cards nobody has a price for are left without one."""
    if not live:
        return
    found = live.by_names([c["n"] for c in cards])
    for c in cards:
        js = found.get(c["n"].lower()) or found.get(c["n"].split(" // ")[0].lower())
        if js:
            price = card_price(card_from_scryfall(js), False, vault, live)[0]
            if price is not None:
                c["p"] = price


def add_upgrade_routes(app, scanner):
    @app.get("/api/decks/upgrades")
    def decks_upgrades():
        commander = str(request.args.get("commander", "")).strip()[:150]
        if not commander:
            return jsonify({"source": "none", "error": "Set a commander first"}), 400
        live = getattr(scanner, "live", None)
        out = recommendations(commander, online=live is not None)
        if out.get("cards"):
            out["cards"] = [dict(c) for c in out["cards"]]
            try:
                add_prices(out["cards"], scanner.vault, live)
            except Exception:  # prices are a bonus; the list still works without them
                pass
        return jsonify(out)
