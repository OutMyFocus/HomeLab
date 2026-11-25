"""The weekly Canadian price check (what Commander Vault's weekly check-in did, now on the Pi).

For every card in your collection, your decks, your wishlist and your trade binder it
looks up the Near Mint price at Canadian stores: Face to Face Games (the main price,
a Montreal store), 401 Games, The Mythic Store, Hobbiesville, and two more Montreal
stores, Card Brawlers and L'Univers de la Carte (see montreal.py). Valuable, foil and special
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
from urllib.parse import urlencode, urlsplit

import requests

from . import config

STORES = {
    "f2f": ("Face to Face Games", "https://facetofacegames.com"),
    "401": ("401 Games", "https://store.401games.ca"),
    "myth": ("The Mythic Store", "https://themythicstore.com"),
    "hob": ("Hobbiesville", "https://www.hobbiesville.com"),
    "cb": ("Card Brawlers", "https://cardbrawlers.com"),                 # Montreal, avenue du Parc
    "udc": ("L'Univers de la Carte", "https://luniversdelacarte.ca"),     # Montreal area, online
}
# Stores that list one product per printing and put Foil / Non-foil inside it as a variant.
VARIANT_FOIL = {"myth", "cb", "udc"}
# Variants in another language (L'Univers de la Carte sells French copies too).
OTHER_LANGUAGE = re.compile(r"french|fran[cç]ais|japanese|german|italian|spanish|chinese|korean|russian|portuguese", re.I)
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux aarch64) mtg-sorter-price-check", "Accept": "application/json"}
SKIP = re.compile(r"art series|art card|oversized|token|displayed|proxy|playmat|sleeve|signed|deck box|booster|"
                  r"bundle|\bdeck\b|japanese|jp\b|\bjpn\b|german|french|italian|spanish|chinese|korean|russian|"
                  r"portuguese|misprint", re.I)
BASICS = {"plains", "island", "swamp", "mountain", "forest", "wastes", "snow-covered plains", "snow-covered island",
          "snow-covered swamp", "snow-covered mountain", "snow-covered forest"}
MAX_PRINTINGS = 400


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).lower().replace("’", "'")).strip()


def _retry_after(e) -> float | None:
    """How long a store asked us to wait (HTTP 429 and its Retry-After), at most 30 s."""
    try:
        return max(0.0, min(30.0, float(e.response.headers.get("Retry-After") or 5)))
    except (AttributeError, TypeError, ValueError):
        return 5.0


class Shop:
    """Talks to the stores' Shopify JSON, politely (a short pause before every request).

    Only network trouble, a busy store (429) and store errors (5xx) are tried again; a store
    that says "no such page" (404 and the like) is not. A store that fails `limit` requests
    in a row is left alone for `cooldown` seconds, so a store that's down doesn't hold up
    the whole check."""

    def __init__(self, get=None, pause: float = 0.25, tries: int = 3, timeout: float = 25,
                 limit: int = 5, cooldown: float = 300):
        self.session = requests.Session()
        self._get = get or self._http
        self.pause, self.tries, self.timeout = pause, max(1, tries), timeout
        self.limit, self.cooldown = limit, cooldown
        self.sleep = time.sleep
        self.answered = 0             # requests a store answered (the price check counts them)
        self._lock = threading.Lock()
        self._fails: dict[str, int] = {}     # host -> failed requests in a row
        self._down: dict[str, float] = {}    # host -> time it's tried again

    def _http(self, url: str):
        r = self.session.get(url, headers=HEADERS, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def get(self, url: str):
        host = urlsplit(url).netloc
        with self._lock:
            if self._down.get(host, 0) > time.time():
                return None
        for attempt in range(self.tries):
            if self.pause:
                self.sleep(self.pause)
            try:
                got = self._get(url)
            except requests.HTTPError as e:
                code = getattr(e.response, "status_code", 0) or 0
                if code == 429:
                    if attempt + 1 < self.tries:
                        self.sleep(_retry_after(e))
                    continue
                if 0 < code < 500:      # the store answered: it just has no such page
                    self._ok(host, answered=False)
                    return None
            except OSError:             # can't connect, timed out, connection dropped
                pass
            except Exception:           # an answer that isn't JSON (a bot check, a broken page)
                break
            else:
                self._ok(host)
                return got
            if self.pause and attempt + 1 < self.tries:
                self.sleep(1.5 + 2 * attempt)
        with self._lock:
            self._fails[host] = n = self._fails.get(host, 0) + 1
            if n >= self.limit:
                self._down[host] = time.time() + self.cooldown
        return None

    def _ok(self, host: str, answered: bool = True):
        with self._lock:
            self._fails.pop(host, None)
            self._down.pop(host, None)
            if answered:
                self.answered += 1

    def search(self, host: str, q: str) -> list[dict] | None:
        d = self.get(host + "/search/suggest.json?" + urlencode(
            {"q": q, "resources[type]": "product", "resources[limit]": "10"}))
        if d is None:
            return None
        return ((d.get("resources") or {}).get("results") or {}).get("products") or []

    def variants(self, host: str, handle: str) -> list[tuple[str, float, bool]]:
        d = self.get(f"{host}/products/{handle}.js")
        out = []
        for v in (d.get("variants") or [] if isinstance(d, dict) else []):
            try:
                price = float(v.get("price")) / 100
            except (AttributeError, TypeError, ValueError):
                continue   # a variant without a usable price
            if price:
                out.append((str(v.get("title", "")), price, bool(v.get("available"))))
        return out


def _base(store: str, title: str) -> str:
    if store == "f2f":
        return title.split(" [")[0]
    if store == "myth":
        return re.split(r" \(| \[", title)[0]
    if store in ("cb", "udc"):
        return re.split(r" \(| \[| - ", title)[0]
    return re.split(r" \(| - ", title)[0]


def _title_foil(store: str, title: str) -> bool:
    if store == "f2f":
        return "[Foil]" in title or ("Foil" in title and "Non-Foil" not in title)
    if store == "401":
        return bool(re.search(r"\(Foil\)|\bFoil\b", title))
    if store == "hob":
        return bool(re.search(r"\bFoil\s*$|\) Foil", title))
    return False   # The Mythic Store, Card Brawlers, L'Univers de la Carte: foil is a variant inside the product


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
        if p.get("handle"):
            cands.append((low, p["handle"], _title_foil(store, title)))
    if not cands:
        return None
    cands.sort()
    regular = [c for c in cands if not c[2]][:3]
    foils = [c for c in cands if c[2]][:2]
    if store in VARIANT_FOIL:
        regular, foils = cands[:3], []
    opts, foil_opts = [], []
    for _, handle, is_foil in regular + foils:
        for title, price, available in shop.variants(host, handle):
            if not _near_mint(title) or OTHER_LANGUAGE.search(title):
                continue
            foil = is_foil or (store in VARIANT_FOIL and "foil" in title.lower())
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
        if p.get("handle") and (r := nm_variant(host, p["handle"])):
            got.append((r[0], r[1], "Face to Face Games"))
    host = STORES["hob"][1]
    for p in shop.search(host, f"{front} {set_code}-{number}") or []:
        t = p.get("title", "")
        if norm(re.split(r" \(", t)[0]) != norm(front):
            continue
        if f"({set_code.upper()}-{cn})" not in t.replace(f"-{number}", f"-{cn}") or _title_foil("hob", t) != foil:
            continue
        if p.get("handle") and (r := nm_variant(host, p["handle"])):
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
    stores didn't answer for keep last week's price). Returns the new price data, plus
    "failed": how many cards hit an error (those keep last week's price too).

    When no store answered at all (the internet or the stores were down) nothing is saved,
    so last week's prices and trends stay, and the check is tried again later."""
    shop = shop or Shop()
    shop.answered = 0
    old = load()
    old_prices = old.get("prices") if isinstance(old.get("prices"), dict) else {}
    old_prev = old.get("prev") if isinstance(old.get("prev"), dict) else {}
    prices, printings = dict(old_prices), dict(old.get("printings") or {})
    done, failed, errors = [0], [0], []
    total = len(names) + len(keys)
    lock = threading.Lock()

    def tick(what):
        with lock:
            done[0] += 1
            if progress:
                progress(done[0], total, what)

    def fail(e):
        with lock:
            failed[0] += 1
            errors.append(e)

    def one(name):
        try:
            return name, card_prices(shop, name)
        except Exception as e:   # one odd product never stops the whole check
            fail(e)
            return name, {}
        finally:
            tick(name)

    def exact(key):
        try:
            return key, printing_price(shop, key)
        except Exception as e:
            fail(e)
            return key, None
        finally:
            tick(key)

    updated = set()
    with ThreadPoolExecutor(workers) as pool:
        for name, found in pool.map(one, names):
            if found:
                prices[name] = found
                updated.add(name)
        for key, found in pool.map(exact, keys):
            if found:
                printings[key] = found
    if total and failed[0] == total:
        raise RuntimeError(f"every card hit an error ({errors[0]!r})")
    if total and not shop.answered:
        raise RuntimeError(f"No store answered, so the prices from {old.get('date') or 'before'} are kept")
    # Last week's price, for the trends. A card no store answered for this time keeps its
    # old price, so it also keeps the trend it had.
    prev = {}
    for n, stores in old_prices.items():
        p = main_price(stores) if n in updated else old_prev.get(n, main_price(stores))
        if p is not None:
            prev[n] = p
    today = date.today()
    data = {"date": f"{today:%b} {today.day}, {today.year}",
            "checked": time.strftime("%Y-%m-%dT%H:%M:%S"), "condition": "Near Mint",
            "stores": [s[0] for s in STORES.values()], "prices": prices, "printings": printings, "prev": prev}
    save(data)
    return data | {"failed": failed[0]}
