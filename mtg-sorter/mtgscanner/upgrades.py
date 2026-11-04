"""Deck upgrades: the cards other players run with a commander, from EDHREC.

The Decks page uses this for its "Upgrade this deck" panel. For a commander it gets
EDHREC's commander page (every card people play with it, and in what share of decks)
and the lowest price of each card on Scryfall (in CAD), so the page can line up swaps
from the fewest to the most. Answers are kept in data/edhrec_cache.json for three days, and an old
answer is used when EDHREC can't be reached.
"""

import json
import re
import threading
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote

import requests
from flask import jsonify, request

from . import config

URL = "https://json.edhrec.com/pages/commanders/{}.json"
PAGE = "https://edhrec.com/commanders/{}"
TTL = 3 * 24 * 3600
KEEP = 40                     # commanders kept in the cache file
SKIP_LISTS = {"newcards"}     # "New Cards" is what's trending, not what's proven
_lock = threading.Lock()


def slug(name: str) -> str:
    """EDHREC's name for a commander's page: "Atraxa, Praetors' Voice" -> atraxa-praetors-voice."""
    name = name.split(" // ")[0]
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^a-z0-9 -]", "", name.lower())
    return re.sub(r"[\s-]+", "-", name).strip("-")


def cache_file() -> Path:
    return config.DATA_DIR / "edhrec_cache.json"


def _read_cache() -> dict:
    try:
        data = json.loads(cache_file().read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_cache(data: dict) -> None:
    if len(data) > KEEP:
        for k in sorted(data, key=lambda k: data[k].get("fetched", 0))[:len(data) - KEEP]:
            del data[k]
    try:
        cache_file().parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_file().with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(cache_file())
    except OSError:
        pass


def fetch_edhrec(s: str) -> dict:
    resp = requests.get(URL.format(s), timeout=12, headers={"User-Agent": config.USER_AGENT})
    resp.raise_for_status()
    return resp.json()


def summarize(js: dict) -> dict:
    """The parts of EDHREC's page the Decks page needs: each card's share of decks and synergy."""
    lists = (js.get("container") or {}).get("json_dict", {}).get("cardlists", [])
    cards: dict[str, dict] = {}
    decks = 0
    for cl in lists:
        tag = cl.get("tag", "")
        if tag in SKIP_LISTS:
            continue
        for cv in cl.get("cardviews", []):
            name, used, pot = cv.get("name"), cv.get("num_decks") or 0, cv.get("potential_decks") or 0
            if not name or not pot:
                continue
            decks = max(decks, pot)
            if name not in cards:
                cards[name] = {"n": name, "inc": round(used / pot, 4), "syn": round(cv.get("synergy") or 0, 4),
                               "list": cl.get("header", "")}
    return {"decks": decks, "cards": sorted(cards.values(), key=lambda c: -c["inc"])}


def cheapest_usd(names: list[str], get=None) -> dict[str, float]:
    """{name: the lowest US price of any printing}, from Scryfall's search, 35 names a request."""
    from .live import API, get_json
    get = get or get_json
    out: dict[str, float] = {}
    for start in range(0, len(names), 35):
        chunk = [n.replace('"', "") for n in names[start:start + 35]]
        q = "prefer:usd-low (" + " or ".join(f'!"{n}"' for n in chunk) + ")"
        url = f"{API}/cards/search?unique=cards&q={quote(q)}"
        try:
            page = get(url)
        except (requests.RequestException, ValueError):
            continue
        for js in page.get("data", []):
            usd = (js.get("prices") or {}).get("usd") or (js.get("prices") or {}).get("usd_foil")
            if usd:
                out[js["name"]] = float(usd)
                out.setdefault(js["name"].split(" // ")[0], float(usd))
        time.sleep(0.1)   # Scryfall asks for 10 requests a second at most
    return out


def for_commander(name: str, fetch=fetch_edhrec, pricer=cheapest_usd) -> dict:
    """{commander, slug, url, decks, cards: [{n, inc, syn, list}], fetched, stale?}."""
    s = slug(name)
    if not s:
        raise ValueError("No commander")
    with _lock:
        cache = _read_cache()
    hit = cache.get(s)
    if hit and time.time() - hit.get("fetched", 0) < TTL:
        return hit
    try:
        data = summarize(fetch(s))
        if pricer:
            usd = pricer([c["n"] for c in data["cards"]])
            for c in data["cards"]:
                if c["n"] in usd:
                    c["usd"] = usd[c["n"]]
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as e:
        if hit:
            return {**hit, "stale": True}
        raise LookupError(f"EDHREC didn't answer for {name}") from e
    if not data["cards"]:
        raise LookupError(f"EDHREC has no decks for {name}")
    data.update(commander=name, slug=s, url=PAGE.format(s), fetched=time.time())
    with _lock:
        cache = _read_cache()
        cache[s] = data
        _write_cache(cache)
    return data


def priced(data: dict) -> dict:
    """The answer for the page: each card's price in CAD ("p") from its US price."""
    rate = config.USD_TO_CAD
    return {**data, "cards": [{k: v for k, v in c.items() if k != "usd"} | {"p": round(c["usd"] * rate, 2) if c.get("usd") else None}
                              for c in data["cards"]]}


def _offline(s):
    raise requests.ConnectionError("offline")


def add_upgrade_routes(app, scanner):
    @app.get("/api/decks/upgrades")
    def deck_upgrades():
        name = str(request.args.get("commander", "")).strip()[:150]
        if not name:
            return jsonify({"error": "Set a commander first"}), 400
        live = getattr(scanner, "live", None)
        try:
            if live is None:   # --offline: only what's saved already
                if not _read_cache().get(slug(name)):
                    return jsonify({"error": "Upgrades need the internet (the app is running offline)"}), 503
                data = for_commander(name, fetch=_offline, pricer=None)
            else:
                data = for_commander(name)
        except LookupError as e:
            return jsonify({"error": str(e)}), 502
        return jsonify(priced(data))
