"""The weekly Canadian price check (what Commander Vault's weekly check-in did, now on the Pi).

For every card in your collection, your decks, your wishlist and your trade binder it
looks up the Near Mint price at four Canadian stores: Face to Face Games (the main
price), 401 Games, The Mythic Store and Hobbiesville. Valuable, foil and special
printings in the collection also get a price for that exact printing. Everything is
saved to data/vault_prices.json, which the scanner, the bins and every page use (see
vault_prices.py). Last week's main prices are kept as "prev" for the price trends.

The stores all run on Shopify, whose search and product pages answer in JSON, so no
web pages are scraped. Requests are spaced out so a full check takes a while (about
half an hour for 700 cards) and never hammers a store.
"""

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import requests

from . import config

STORES = {
    "f2f": ("Face to Face Games", "https://facetofacegames.com"),
    "401": ("401 Games", "https://store.401games.ca"),
    "myth": ("The Mythic Store", "https://themythicstore.com"),
    "hob": ("Hobbiesville", "https://www.hobbiesville.com"),
}
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux aarch64) mtg-sorter-price-check", "Accept": "application/json"}
SKIP = re.compile(r"art series|art card|oversized|token|displayed|proxy|playmat|sleeve|signed|deck box|booster|"
                  r"bundle|\bdeck\b|japanese|jp\b|\bjpn\b|german|french|italian|spanish|chinese|korean|russian|"
                  r"portuguese|misprint", re.I)
BASICS = {"plains", "island", "swamp", "mountain", "forest", "wastes", "snow-covered plains", "snow-covered island",
          "snow-covered swamp", "snow-covered mountain", "snow-covered forest"}
MAX_PRINTINGS = 400


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).lower().replace("’", "'")).strip()


class Shop:
    """Talks to the stores' Shopify JSON, politely (a short pause before every request)."""

    def __init__(self, get=None, pause: float = 0.25):
        self.session = requests.Session()
        self._get = get or self._http
        self.pause = pause

    def _http(self, url: str):
        r = self.session.get(url, headers=HEADERS, timeout=25)
        r.raise_for_status()
        return r.json()

    def get(self, url: str):
        for attempt in range(3):
            if self.pause:
                time.sleep(self.pause)
            try:
                return self._get(url)
            except Exception:
                if self.pause:
                    time.sleep(1.5 + 2 * attempt)
        return None

    def search(self, host: str, q: str) -> list[dict] | None:
        d = self.get(host + "/search/suggest.json?" + urlencode(
            {"q": q, "resources[type]": "product", "resources[limit]": "10"}))
        if d is None:
            return None
        return ((d.get("resources") or {}).get("results") or {}).get("products") or []

    def variants(self, host: str, handle: str) -> list[tuple[str, float, bool]]:
        d = self.get(f"{host}/products/{handle}.js")
        return [(v.get("title", ""), v["price"] / 100, bool(v.get("available")))
                for v in (d or {}).get("variants", []) if v.get("price")]


def _base(store: str, title: str) -> str:
    if store == "f2f":
        return title.split(" [")[0]
    if store == "myth":
        return re.split(r" \(| \[", title)[0]
    return re.split(r" \(| - ", title)[0]


def _title_foil(store: str, title: str) -> bool:
    if store == "f2f":
        return "[Foil]" in title or ("Foil" in title and "Non-Foil" not in title)
    if store == "401":
        return bool(re.search(r"\(Foil\)|\bFoil\b", title))
    if store == "hob":
        return bool(re.search(r"\bFoil\s*$|\) Foil", title))
    return False   # The Mythic Store: foil is a variant inside the product


def _near_mint(variant_title: str) -> bool:
    return re.match(r"^(nm|near mint)\b", variant_title.strip(), re.I) is not None


def store_price(shop: Shop, store: str, name: str) -> list | None:
    """[Near Mint price, in stock 1/0, foil Near Mint price] at one store; None if the
    store doesn't list the card (or didn't answer)."""
    host = STORES[store][1]
    products = shop.search(host, name.split(" // ")[0])
    if not products:
        return None
    want = {norm(name), norm(name.split(" // ")[0])}
    cands = []
    for p in products:
        title = p.get("title", "")
        base = _base(store, title)
        if (norm(base) not in want and norm(base.split(" // ")[0]) not in want) or SKIP.search(title):
            continue
        try:
            low = float(p.get("price_min") or p.get("price"))
        except (TypeError, ValueError):
            continue
        cands.append((low, p["handle"], _title_foil(store, title)))
    if not cands:
        return None
    cands.sort()
    regular = [c for c in cands if not c[2]][:3]
    foils = [c for c in cands if c[2]][:2]
    if store == "myth":
        regular, foils = cands[:3], []
    opts, foil_opts = [], []
    for _, handle, is_foil in regular + foils:
        for title, price, available in shop.variants(host, handle):
            if not _near_mint(title):
                continue
            foil = is_foil or (store == "myth" and "foil" in title.lower())
            (foil_opts if foil else opts).append((not available, price))
    if not opts and not foil_opts:
        return None
    best = min(opts) if opts else None
    return [best[1] if best else None, 1 if best and not best[0] else 0, min(foil_opts)[1] if foil_opts else None]


def card_prices(shop: Shop, name: str) -> dict:
    """{store: [price, in stock, foil price]} for every store that lists the card."""
    out = {}
    for store in STORES:
        if (got := store_price(shop, store, name)) is not None:
            out[store] = got
    return out


def printing_price(shop: Shop, key: str) -> list | None:
    """[price, in stock, store name] for one exact printing, key "name|SET|number|foil".
    Face to Face Games and Hobbiesville put the set and number in their titles."""
    name, set_code, number, foil = key.split("|")
    foil, front, cn = foil == "1", name.split(" // ")[0], number.lstrip("0") or number
    got = []

    def nm_variant(host, handle):
        vs = [(not av, price) for title, price, av in shop.variants(host, handle) if _near_mint(title) and price > 0]
        return min(vs) if vs else None

    host = STORES["f2f"][1]
    for p in shop.search(host, f"{front} {cn}") or []:
        t = p.get("title", "")
        if norm(t.split(" [")[0].split(" // ")[0]) != norm(front):
            continue
        nums = re.findall(r"\[(\d+[a-z★]*)\]", t)
        if not nums or nums[0].lstrip("0") != cn or _title_foil("f2f", t) != foil:
            continue
        if r := nm_variant(host, p["handle"]):
            got.append((r[0], r[1], "Face to Face Games"))
    host = STORES["hob"][1]
    for p in shop.search(host, f"{front} {set_code}-{number}") or []:
        t = p.get("title", "")
        if norm(re.split(r" \(", t)[0]) != norm(front):
            continue
        if f"({set_code.upper()}-{cn})" not in t.replace(f"-{number}", f"-{cn}") or _title_foil("hob", t) != foil:
            continue
        if r := nm_variant(host, p["handle"]):
            got.append((r[0], r[1], "Hobbiesville"))
    if not got:
        return None
    best = min(got)
    return [best[1], 0 if best[0] else 1, best[2]]


def main_price(stores: dict) -> float | None:
    """The one price shown for a card: Face to Face Games, else the cheapest in stock."""
    if (f2f := stores.get("f2f")) and f2f[0]:
        return f2f[0]
    opts = [(not row[1], row[0]) for row in stores.values() if row and row[0]]
    return min(opts)[1] if opts else None


# --- Which cards to check ---------------------------------------------------------------

def wanted(rows: list[dict], deck_names: list[str], wish_names: list[str], trade_names: list[str]):
    """(card names, exact-printing keys) to price this week."""
    names = {r.get("Name", "").strip() for r in rows} | set(deck_names) | set(wish_names) | set(trade_names)
    names = sorted(n for n in names if n and norm(n) not in BASICS)
    keys = []
    for r in rows:
        name, set_code, number = r.get("Name", "").strip(), (r.get("Set code") or "").upper(), r.get("Collector number", "")
        if not (name and set_code and number) or set_code.startswith("T"):
            continue
        foil = (r.get("Foil") or "").lower() in ("foil", "etched", "yes", "true", "1")
        try:
            paid = float(r.get("Price CAD") or 0)
        except ValueError:
            paid = 0
        if paid >= 1.5 or foil or re.search(r"[a-z★]", number, re.I):
            keys.append(f"{name}|{set_code}|{number}|{1 if foil else 0}")
    return names, sorted(set(keys))[:MAX_PRINTINGS]


def load(path: Path | None = None) -> dict:
    try:
        return json.loads((path or config.VAULT_PRICES).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(data: dict, path: Path | None = None):
    path = path or config.VAULT_PRICES
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def check(names: list[str], keys: list[str], shop: Shop | None = None, progress=None, workers: int = 4) -> dict:
    """Price every name and printing, and save the result over the old prices (cards the
    stores didn't answer for keep last week's price). Returns the new price data."""
    shop = shop or Shop()
    old = load()
    prices, printings = dict(old.get("prices") or {}), dict(old.get("printings") or {})
    prev = {n: p for n, s in prices.items() if (p := main_price(s)) is not None}
    done = [0]
    total = len(names) + len(keys)
    lock = threading.Lock()

    def tick(what):
        with lock:
            done[0] += 1
            if progress:
                progress(done[0], total, what)

    def one(name):
        found = card_prices(shop, name)
        tick(name)
        return name, found

    with ThreadPoolExecutor(workers) as pool:
        for name, found in pool.map(one, names):
            if found:
                prices[name] = found
        def exact(key):
            found = printing_price(shop, key)
            tick(key)
            return key, found

        for key, found in pool.map(exact, keys):
            if found:
                printings[key] = found
    today = date.today()
    data = {"date": f"{today:%b} {today.day}, {today.year}",
            "checked": time.strftime("%Y-%m-%dT%H:%M:%S"), "condition": "Near Mint",
            "stores": [s[0] for s in STORES.values()], "prices": prices, "printings": printings, "prev": prev}
    save(data)
    return data
