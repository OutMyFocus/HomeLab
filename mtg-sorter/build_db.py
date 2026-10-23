"""Download card data and images from Scryfall and build the fingerprint database.

Quick test with a couple of sets (takes about a minute):
    python build_db.py --sets dmu,one

Every card ever printed (a ~500 MB download, then a few hours of image downloads):
    python build_db.py --all

You can stop it at any time and run it again. It skips cards it already has
and only refreshes their prices.
"""

import argparse
import gzip
import io
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator

import ijson
import requests
from PIL import Image

from mtgscanner import config
from mtgscanner.database import connect
from mtgscanner.vision import fingerprint_pil

API = "https://api.scryfall.com"
HEADERS = {"User-Agent": config.USER_AGENT, "Accept": "application/json"}


def cards_from_sets(set_codes: list[str]) -> Iterator[dict]:
    """Yield every printing in the given sets using Scryfall's search API."""
    for code in set_codes:
        url = f"{API}/cards/search?q=e:{code}&unique=prints"
        while url:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            page = resp.json()
            yield from page["data"]
            url = page.get("next_page")
            THROTTLE.wait()  # Scryfall asks for at most 10 requests/second


def cards_from_bulk() -> Iterator[dict]:
    """Download Scryfall's daily 'Default Cards' bulk file and yield each card."""
    info = requests.get(f"{API}/bulk-data/default-cards", headers=HEADERS, timeout=30).json()
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Scryfall now offers the file as gzipped JSON Lines (one card per line); older
    # responses had one big JSON array. Handle both.
    lines = "jsonl_download_uri" in info
    url = info["jsonl_download_uri"] if lines else info["download_uri"]
    size = info.get("compressed_size") or info.get("size") or 0
    bulk_path = config.DATA_DIR / ("default-cards.jsonl.gz" if lines else "default-cards.json")
    print(f"Downloading bulk data ({size / 1e6:.0f} MB)...")
    with requests.get(url, headers=HEADERS, stream=True, timeout=60) as r:
        r.raise_for_status()
        with bulk_path.open("wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    # Read one card at a time, so the whole file never has to fit in memory.
    if lines:
        with gzip.open(bulk_path, "rt", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)
    else:
        with bulk_path.open("rb") as f:
            yield from ijson.items(f, "item", use_float=True)


def image_url(card: dict) -> str | None:
    if "image_uris" in card:
        return card["image_uris"].get("small")
    faces = card.get("card_faces") or []
    if faces and "image_uris" in faces[0]:  # double-faced cards: use the front
        return faces[0]["image_uris"].get("small")
    return None


def price(card: dict, key: str) -> float | None:
    value = card.get("prices", {}).get(key)
    return float(value) if value else None


class Throttle:
    """Lets at most `rate` requests a second through, across all download threads.
    Scryfall asks for 50-100 ms between requests; going faster gets you blocked."""

    def __init__(self, rate: float):
        self.gap, self.next_at, self.lock = 1.0 / rate, 0.0, threading.Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            self.next_at = max(now, self.next_at) + self.gap
            delay = self.next_at - self.gap - now
        if delay > 0:
            time.sleep(delay)


THROTTLE = Throttle(9)
SESSION = requests.Session()
SESSION.headers["User-Agent"] = config.USER_AGENT


def fetch_image(url: str) -> bytes | None:
    """Download one card picture, politely, retrying when Scryfall is busy."""
    for attempt in range(5):
        THROTTLE.wait()
        try:
            resp = SESSION.get(url, timeout=30)
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as e:
            if attempt == 4:
                print(f"  skipped {url}: {e}", file=sys.stderr)
            time.sleep(1 + attempt)
    return None


def fetch_fingerprint(url: str) -> bytes | None:
    try:
        data = fetch_image(url)
        return fingerprint_pil(Image.open(io.BytesIO(data))) if data else None
    except Exception as e:  # one bad image shouldn't stop the whole build
        print(f"  skipped {url}: {e}", file=sys.stderr)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sets", help="comma-separated set codes, e.g. dmu,one,mkm")
    group.add_argument("--all", action="store_true", help="every card on Scryfall")
    args = parser.parse_args()

    conn = connect(config.DB_PATH)
    known = {row[0] for row in conn.execute("SELECT id FROM cards")}
    source = cards_from_bulk() if args.all else cards_from_sets(args.sets.lower().split(","))

    todo = []
    refreshed = 0
    for card in source:
        if card.get("digital") or card.get("layout") == "art_series":
            continue
        if card["id"] in known:
            conn.execute(
                "UPDATE cards SET price_usd = ?, price_usd_foil = ? WHERE id = ?",
                (price(card, "usd"), price(card, "usd_foil"), card["id"]),
            )
            refreshed += 1
        elif url := image_url(card):
            todo.append((card, url))
    conn.commit()
    print(f"Refreshed prices for {refreshed} cards already in the database.")
    print(f"Fingerprinting {len(todo)} new cards...")

    added = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for (card, _), fp in zip(todo, pool.map(fetch_fingerprint, [u for _, u in todo])):
            if fp is None:
                continue
            conn.execute(
                "INSERT INTO cards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    card["id"], card["name"], card["set"], card.get("set_name"),
                    card.get("collector_number"), card.get("rarity"),
                    ",".join(card.get("colors") or card.get("color_identity") or []),
                    price(card, "usd"), price(card, "usd_foil"), fp,
                ),
            )
            added += 1
            if added % 200 == 0:
                conn.commit()
                print(f"  {added}/{len(todo)}")
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    print(f"Done. Added {added} cards. The database now has {total} cards.")


if __name__ == "__main__":
    main()
