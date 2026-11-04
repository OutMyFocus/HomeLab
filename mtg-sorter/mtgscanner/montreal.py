"""Montreal store prices: Face to Face Games first, then other Montreal stores.

Two places use this:

* The scanner. When a card is recognized the page asks /api/montreal for it, and this
  module checks the Montreal stores right then (a few seconds, saved for 12 hours), so
  you see what the card costs in Montreal today, for that printing when the store has it.
* The collection. Its Montreal column comes from the weekly Canadian price check
  (ca_prices.py), which already asks these stores about every card you own.

Stores the app can read (their Shopify search answers in JSON, like ca_prices.py):

  Face to Face Games      Montreal (and Toronto); always shown first
  Card Brawlers           Montreal, avenue du Parc
  L'Univers de la Carte   Montreal area, online

Montreal stores the app can't read: Carta Magica and L'Expédition run on Crystal
Commerce, which refuses automated requests, and Le Valet d'Coeur sits behind a bot
check. The page shows a link to search each of those in your own browser instead.
"""

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus

from flask import jsonify, request

from .ca_prices import OTHER_LANGUAGE, SKIP, STORES, VARIANT_FOIL, Shop, _base, _near_mint, _title_foil, norm

MONTREAL = ("f2f", "cb", "udc")          # in the order they're shown: Face to Face first
WHERE = {"f2f": "Montreal", "cb": "Montreal", "udc": "Montreal area"}
LINKS = [                                 # Montreal stores you check yourself, by link
    ("Carta Magica", "https://www.cartamagica.com/products/search?q={q}"),
    ("L'Expédition", "https://www.expeditionjeux.com/products/search?q={q}"),
    ("Le Valet d'Coeur", "https://www.levalet.com/"),
]
CACHE_HOURS = 12
MAX_PRODUCTS = 4                          # product pages read per store per card


def _num(n) -> str:
    return str(n or "").strip().lower().lstrip("0") or str(n or "").strip().lower()


def printing_of(store: str, title: str) -> dict:
    """What a store's product title says about the printing: set code, set name, number."""
    if store == "f2f":     # Sol Ring [1011] [Borderless] [Secret Lair Drop] [Non-Foil]
        parts = re.findall(r"\[([^\]]+)\]", title)
        number = next((p for p in parts if re.fullmatch(r"\d+[a-z★]*", p, re.I)), "")
        sets = [p for p in parts if p not in (number, "Foil", "Non-Foil") and not p.endswith("Foil")]
        return {"number": number, "set_name": sets[-1] if sets else ""}
    if store == "udc":     # Counterspell (Retro Frame) [DMR - 281]
        if m := re.search(r"\[([A-Z0-9]{2,6}) - ([^\]]+)\]", title):
            return {"set": m.group(1), "number": m.group(2)}
        return {}
    if store == "cb":      # Spell Pierce [Zendikar], or Spell Pierce (SOA-023) - Secrets of Strixhaven
        if m := re.search(r"\(([A-Z0-9]{2,6})-(\d+[a-z]*)\)\s*-\s*(.+)$", title):
            return {"set": m.group(1), "number": m.group(2), "set_name": m.group(3)}
        if m := re.search(r"\[([^\]]+)\]\s*$", title):
            return {"set_name": m.group(1)}
    return {}


def same_printing(info: dict, set_code: str, set_name: str, number: str) -> bool:
    """True when the title's printing is the scanned card's printing."""
    if info.get("set") and set_code and info["set"].upper() != set_code.upper():
        return False
    if info.get("number") and number and _num(info["number"]) != _num(number):
        return False
    if info.get("set_name") and set_name and norm(info["set_name"]) != norm(set_name):
        return False
    # At least one real clue has to match: a number, or a set (code or name).
    return bool((info.get("number") and number) or (info.get("set") and set_code) or (info.get("set_name") and set_name))


def store_lookup(shop: Shop, store: str, name: str, set_code: str = "", set_name: str = "",
                 number: str = "", foil: bool = False) -> dict | None:
    """The Near Mint price of a card at one store: that printing if the store has it,
    otherwise its cheapest printing (in stock first). None if the store doesn't list it."""
    label, host = STORES[store]
    front = name.split(" // ")[0]
    products = shop.search(host, front) or []
    # A store's search only gives its top 10, so also search for this exact printing.
    extra = {"f2f": _num(number), "udc": set_code.upper(), "cb": set_name}.get(store) if (number or set_code) else ""
    if extra:
        seen = {p.get("handle") for p in products}
        products += [p for p in shop.search(host, f"{front} {extra}") or [] if p.get("handle") not in seen]
    if not products:
        return None
    want = {norm(name), norm(front)}
    cands = []
    for p in products:
        title = p.get("title", "")
        base = _base(store, title)
        if (norm(base) not in want and norm(base.split(" // ")[0]) not in want) or SKIP.search(title):
            continue
        if store not in VARIANT_FOIL and _title_foil(store, title) != foil:
            continue
        try:
            low = float(p.get("price_min") or p.get("price"))
        except (TypeError, ValueError):
            low = 1e9
        exact = same_printing(printing_of(store, title), set_code, set_name, number)
        cands.append((not exact, low, p["handle"], title, exact))
    if not cands:
        return None
    cands.sort()
    best = None
    for _, _, handle, title, exact in cands[:MAX_PRODUCTS]:
        for vtitle, price, available in shop.variants(host, handle):
            if not _near_mint(vtitle) or OTHER_LANGUAGE.search(vtitle) or price <= 0:
                continue
            if store in VARIANT_FOIL and ("foil" in vtitle.lower()) != foil:
                continue
            rank = (not exact, not available, price)
            if best is None or rank < best[0]:
                best = (rank, {"key": store, "store": label, "where": WHERE.get(store, ""), "price": round(price, 2),
                               "in_stock": bool(available), "exact": exact, "title": title,
                               "url": f"{host}/products/{handle}"})
    return best[1] if best else None


def weekly(vault, name: str, foil: bool = False) -> list[dict]:
    """The Montreal stores' prices for a card name from the weekly price check, in order."""
    if not vault:
        return []
    stores = vault.by_name.get(name) or vault.by_name.get(name.split(" // ")[0]) or {}
    out = []
    for key in MONTREAL:
        row = stores.get(key)
        try:
            price = row[2 if foil else 0] if row else None
            price = None if price is None else round(float(price), 2)
        except (IndexError, TypeError, ValueError):
            price = None
        if price is not None:
            out.append({"key": key, "store": STORES[key][0], "where": WHERE[key], "price": price,
                        "in_stock": bool(row[1]) if len(row) > 1 and not foil else None, "exact": False})
    return out


def first(vault, name: str, foil: bool = False) -> dict | None:
    """The Montreal price the collection shows: Face to Face Games, else the next store."""
    found = weekly(vault, name, foil)
    return {"price": found[0]["price"], "store": found[0]["store"]} if found else None


def links(name: str) -> list[dict]:
    q = quote_plus(name.split(" // ")[0])
    return [{"store": label, "url": url.format(q=q)} for label, url in LINKS]


class Montreal:
    """Checks the Montreal stores for one card at a time, and remembers the answers."""

    def __init__(self, shop: Shop | None = None, offline: bool = False):
        self.shop = shop or Shop(pause=0.15)
        self.offline = offline
        self.cache: dict[tuple, tuple[float, list]] = {}
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(len(MONTREAL))

    def lookup(self, name: str, set_code: str = "", set_name: str = "", number: str = "",
               foil: bool = False) -> tuple[list[dict], bool]:
        """([store prices in Montreal order], whether they were fetched just now or cached)."""
        key = (name, set_code.upper(), norm(set_name), _num(number), foil)
        with self.lock:
            hit = self.cache.get(key)
        if hit and time.time() - hit[0] < CACHE_HOURS * 3600:
            return hit[1], False
        jobs = [self.pool.submit(store_lookup, self.shop, s, name, set_code, set_name, number, foil) for s in MONTREAL]
        found = []
        for job in jobs:
            try:
                if got := job.result(timeout=60):
                    found.append(got)
            except Exception:
                pass
        with self.lock:
            if len(self.cache) > 800:
                self.cache.clear()
            self.cache[key] = (time.time(), found)
        return found, True


def add_montreal_routes(app, scanner, montreal: Montreal | None = None):
    """GET /api/montreal?name=&set=&set_name=&number=&foil=1 for the scanner and collection pages."""
    montreal = montreal or Montreal(offline=getattr(scanner, "live", None) is None)
    app.config["montreal"] = montreal

    @app.get("/api/montreal")
    def montreal_prices():
        a = request.args
        name = (a.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Which card?"}), 400
        foil = a.get("foil") in ("1", "true", "yes")
        vault = getattr(scanner, "vault", None)
        out = {"name": name, "foil": foil, "links": links(name), "date": getattr(vault, "date", "") if vault else ""}
        if montreal.offline:
            return jsonify(out | {"stores": weekly(vault, name, foil), "checked": "weekly"})
        stores, _ = montreal.lookup(name, a.get("set", ""), a.get("set_name", ""), a.get("number", ""), foil)
        if not stores:   # the stores didn't answer: fall back to this week's prices
            return jsonify(out | {"stores": weekly(vault, name, foil), "checked": "weekly"})
        # Keep Face to Face first, whatever order the stores answered in.
        stores.sort(key=lambda s: MONTREAL.index(s["key"]))
        return jsonify(out | {"stores": stores, "checked": "today"})
