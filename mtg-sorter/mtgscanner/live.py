"""Live lookups: today's Scryfall prices, other printings and card search.

Recognition itself stays offline (it uses the fingerprints in data/cards.db). This only
adds fresh information on top, and if the internet is down everything quietly falls
back to the prices saved in the database. (The USD to CAD rate comes from exchange.py.)

Scryfall asks apps to stay under 10 requests a second and to cache what they fetch,
so every answer is kept in memory for a few hours.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import requests

from . import config
from .database import Card

API = "https://api.scryfall.com"
HEADERS = {"User-Agent": config.USER_AGENT, "Accept": "application/json"}

CARD_TTL = 6 * 3600     # how long a fetched card (and its price) stays fresh, in seconds
FAIL_TTL = 60           # how long to wait before retrying a lookup that failed (internet blip)
BATCH = 75              # Scryfall's /cards/collection takes up to 75 cards per request


def get_json(url: str, body: dict | None = None) -> dict:
    """GET the url, or POST body to it as JSON."""
    if body is None:
        resp = requests.get(url, headers=HEADERS, timeout=8)
    else:
        resp = requests.post(url, json=body, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _price(card: dict, key: str) -> float | None:
    value = (card.get("prices") or {}).get(key)
    return float(value) if value else None


def card_from_scryfall(js: dict) -> Card:
    """Turn a Scryfall card object into the same Card the database gives."""
    return Card(
        id=js["id"],
        name=js["name"],
        set_code=js["set"],
        set_name=js.get("set_name", ""),
        collector_number=js.get("collector_number", ""),
        rarity=js.get("rarity", ""),
        colors=",".join(js.get("colors") or js.get("color_identity") or []),
        price_usd=_price(js, "usd"),
        price_usd_foil=_price(js, "usd_foil"),
    )


class Live:
    def __init__(self, fetch=get_json):
        self.fetch = fetch
        self._lock = threading.Lock()
        self._cards: dict[str, tuple[float, dict | None]] = {}   # id -> (fetched at, card json or None if it failed)
        self._pending: set[str] = set()
        self._last_request = 0.0
        self._pool = ThreadPoolExecutor(max_workers=2)

    def _get(self, url: str, body: dict | None = None) -> dict | None:
        """Fetch JSON, politely spaced out. Returns None if the internet or Scryfall is down."""
        with self._lock:
            wait = self._last_request + 0.1 - time.time()
            self._last_request = time.time() + max(wait, 0)
        if wait > 0:
            time.sleep(wait)
        try:
            return self.fetch(url) if body is None else self.fetch(url, body)
        except Exception:
            return None

    def _remember(self, js: dict) -> None:
        with self._lock:
            self._cards[js["id"]] = (time.time(), js)

    # --- Cards and prices ------------------------------------------------------------

    def _fresh(self, card_id: str) -> tuple[float, dict | None] | None:
        with self._lock:
            hit = self._cards.get(card_id)
        if hit and time.time() - hit[0] < (CARD_TTL if hit[1] else FAIL_TTL):
            return hit
        return None

    def _cached(self, card_id: str) -> dict | None:
        """The last answer for this card, fresh or not. None if it was never fetched or failed."""
        with self._lock:
            hit = self._cards.get(card_id)
        return hit[1] if hit else None

    def card_json(self, card_id: str) -> dict | None:
        """The card's Scryfall data, fetching it now if it isn't cached. None if offline."""
        if hit := self._fresh(card_id):
            return hit[1]
        js = self._get(f"{API}/cards/{quote(card_id)}")
        with self._lock:
            # Keep the old answer if this refresh failed: stale prices beat no prices.
            if js is None and (old := self._cards.get(card_id)) and old[1]:
                js = old[1]
            self._cards[card_id] = (time.time(), js)
        return js

    def prefetch(self, card_id: str) -> None:
        """Start fetching a card in the background (used by the camera, which can't wait)."""
        if self._fresh(card_id):
            return
        with self._lock:
            if card_id in self._pending:
                return
            self._pending.add(card_id)

        def work():
            try:
                self.card_json(card_id)
            finally:
                with self._lock:
                    self._pending.discard(card_id)
        self._pool.submit(work)

    def ready(self, card_id: str) -> bool:
        """True once a lookup for this card has finished, whether or not it worked."""
        with self._lock:
            return card_id in self._cards

    def prices(self, card_id: str) -> dict | None:
        """Cached Scryfall prices for a card (never waits on the network)."""
        js = self._cached(card_id)
        return js.get("prices") if js else None

    def card(self, card_id: str) -> Card | None:
        js = self.card_json(card_id)
        return card_from_scryfall(js) if js else None

    def printings(self, name: str, limit: int = 400) -> list[Card]:
        """Every paper printing of a card, newest first."""
        q = quote(f'!"{name}" game:paper')
        url = f"{API}/cards/search?q={q}&unique=prints&order=released"
        found = []
        while url and len(found) < limit:
            page = self._get(url)
            if not page:
                break
            for js in page.get("data", []):
                self._remember(js)
                found.append(card_from_scryfall(js))
            url = page.get("next_page")
        return found[:limit]

    def autocomplete(self, text: str) -> list[str]:
        page = self._get(f"{API}/cards/autocomplete?q={quote(text)}")
        return page.get("data", []) if page else []

    def fetch_many(self, card_ids: list[str], progress=None) -> int:
        """Fetch today's prices for many cards at once (the Collection page's Refresh
        prices), 75 per request. Cards fetched in the last few hours are skipped.
        Returns how many cards got fresh prices."""
        todo = [i for i in dict.fromkeys(card_ids) if not self._fresh(i)]
        done = 0
        for start in range(0, len(todo), BATCH):
            chunk = todo[start:start + BATCH]
            page = self._get(f"{API}/cards/collection", {"identifiers": [{"id": i} for i in chunk]})
            if not page:
                break   # offline: keep whatever prices we have
            for js in page.get("data", []):
                self._remember(js)
                done += 1
            if progress:
                progress(min(start + BATCH, len(todo)), len(todo))
        return done

    def cached_count(self) -> int:
        with self._lock:
            return sum(1 for _, js in self._cards.values() if js)
