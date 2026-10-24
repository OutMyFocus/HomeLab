"""Live lookups while scanning: today's Scryfall prices, other printings, card search,
and the Bank of Canada's USD to CAD rate.

Recognition itself stays offline (it uses the fingerprints in data/cards.db). This only
adds fresh information on top, and if the internet is down everything quietly falls
back to the prices saved in the database and config.USD_TO_CAD.

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
# Bank of Canada's daily USD/CAD average. Free, no key needed.
FX_URL = "https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?recent=1"

CARD_TTL = 6 * 3600     # how long a fetched card (and its price) stays fresh, in seconds
RATE_TTL = 12 * 3600    # the exchange rate only changes once a day


def get_json(url: str) -> dict:
    resp = requests.get(url, headers=HEADERS, timeout=8)
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
        self._rate: tuple[float, float, str] | None = None        # (fetched at, rate, date)
        self._rate_tried = 0.0
        self._last_request = 0.0
        self._pool = ThreadPoolExecutor(max_workers=2)

    def _get(self, url: str) -> dict | None:
        """Fetch JSON, politely spaced out. Returns None if the internet or Scryfall is down."""
        with self._lock:
            wait = self._last_request + 0.1 - time.time()
            self._last_request = time.time() + max(wait, 0)
        if wait > 0:
            time.sleep(wait)
        try:
            return self.fetch(url)
        except Exception:
            return None

    def _remember(self, js: dict) -> None:
        with self._lock:
            self._cards[js["id"]] = (time.time(), js)

    # --- Cards and prices ------------------------------------------------------------

    def _fresh(self, card_id: str) -> tuple[float, dict | None] | None:
        with self._lock:
            hit = self._cards.get(card_id)
        if hit and time.time() - hit[0] < CARD_TTL:
            return hit
        return None

    def card_json(self, card_id: str) -> dict | None:
        """The card's Scryfall data, fetching it now if it isn't cached. None if offline."""
        if hit := self._fresh(card_id):
            return hit[1]
        js = self._get(f"{API}/cards/{quote(card_id)}")
        with self._lock:
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
        return self._fresh(card_id) is not None

    def prices(self, card_id: str) -> dict | None:
        """Cached Scryfall prices for a card (never waits on the network)."""
        hit = self._fresh(card_id)
        return hit[1].get("prices") if hit and hit[1] else None

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

    # --- Exchange rate ---------------------------------------------------------------

    def _fetch_rate(self) -> None:
        js = self._get(FX_URL)
        try:
            obs = js["observations"][-1]
            rate = float(obs["FXUSDCAD"]["v"])
        except (TypeError, KeyError, IndexError, ValueError):
            return
        with self._lock:
            self._rate = (time.time(), rate, obs.get("d", ""))

    def usd_to_cad(self) -> tuple[float, str]:
        """Return (rate, where it came from). Never waits: a refresh runs in the background."""
        with self._lock:
            rate = self._rate
            stale = (rate is None or time.time() - rate[0] > RATE_TTL) and time.time() - self._rate_tried > 300
            if stale:
                self._rate_tried = time.time()
        if stale:
            self._pool.submit(self._fetch_rate)
        if rate:
            return rate[1], f"Bank of Canada, {rate[2]}"
        return config.USD_TO_CAD, "fixed rate in config.py"

    def load_rate(self) -> None:
        """Fetch the exchange rate now (at startup, so the first card already uses it)."""
        with self._lock:
            self._rate_tried = time.time()
        self._fetch_rate()
