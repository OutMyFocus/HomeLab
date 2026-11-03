"""Download card data and images from Scryfall and build the fingerprint database.

Every card ever printed (an 80 MB download, then about 108,000 small card pictures;
30-60 minutes on a home connection). This is what the scanner needs to know any card:
    python build_db.py --all

Only the sets in your collection, or a few sets by code (a few minutes):
    python build_db.py --mine
    python build_db.py --sets dmu,one

The Maintenance page has a button that runs --all for you. You can stop it at any time
and run it again: it skips cards it already has (and only refreshes their prices), and
cards fingerprinted by an older version get their pictures fetched again so they get
the newer fingerprint (whole card + art, see mtgscanner/vision.py).
"""

import argparse
import csv
import gzip
import io
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Iterator

import requests
from PIL import Image

from mtgscanner import config
from mtgscanner.database import connect
from mtgscanner.vision import FINGERPRINT_BYTES, fingerprint_pil

API = "https://api.scryfall.com"
HEADERS = {"User-Agent": config.USER_AGENT, "Accept": "application/json"}
IMAGE_THREADS = 12


class Throttle:
    """Lets at most `rate` requests a second through, across all threads."""

    def __init__(self, rate: float):
        self.gap, self.next_at, self.lock = 1.0 / rate, 0.0, threading.Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            self.next_at = max(now, self.next_at) + self.gap
            delay = self.next_at - self.gap - now
        if delay > 0:
            time.sleep(delay)


# Scryfall allows 2 searches a second (https://scryfall.com/docs/api/rate-limits) and
# bans apps that keep going over. Its picture server (*.scryfall.io) has no limit.
SEARCH_THROTTLE = Throttle(1.8)
SESSION = requests.Session()
SESSION.headers["User-Agent"] = config.USER_AGENT
SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=IMAGE_THREADS + 4))


def _api_get(url: str) -> requests.Response:
    """One search request, waiting out Scryfall's "too many requests" answers."""
    for attempt in range(6):
        SEARCH_THROTTLE.wait()
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 429:          # Scryfall blocks for 30 seconds after one of these
            time.sleep(31)
            continue
        if resp.status_code >= 500:
            time.sleep(2 * (attempt + 1))
            continue
        return resp
    resp.raise_for_status()
    return resp


def cards_from_sets(set_codes: list[str]) -> Iterator[dict]:
    """Yield every printing in the given sets using Scryfall's search API."""
    for code in set_codes:
        url = f"{API}/cards/search?q=e:{code}&unique=prints&include_extras=true&include_variations=true"
        while url:
            resp = _api_get(url)
            if resp.status_code == 404:   # Scryfall's way of saying "no cards match"
                print(f"No set with the code '{code}' on Scryfall, skipped. Set codes are the short "
                      "codes in each set's URL, like dmu or mkm.", file=sys.stderr)
                break
            resp.raise_for_status()
            page = resp.json()
            yield from page["data"]
            url = page.get("next_page")


def cards_from_bulk(progress: Callable[[str], None] = print) -> Iterator[dict]:
    """Download Scryfall's daily 'Default Cards' bulk file and yield each card."""
    info = requests.get(f"{API}/bulk-data/default-cards", headers=HEADERS, timeout=30).json()
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Scryfall now offers the file as gzipped JSON Lines (one card per line); older
    # responses had one big JSON array. Handle both.
    lines = "jsonl_download_uri" in info
    url = info["jsonl_download_uri"] if lines else info["download_uri"]
    size = info.get("compressed_size") or info.get("size") or 0
    bulk_path = config.DATA_DIR / (".default-cards.jsonl.gz" if lines else ".default-cards.json")
    progress(f"Downloading the list of every card ({size / 1e6:.0f} MB)")
    try:
        with SESSION.get(url, stream=True, timeout=60) as r:
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
            import ijson
            with bulk_path.open("rb") as f:
                yield from ijson.items(f, "item", use_float=True)
    finally:
        bulk_path.unlink(missing_ok=True)


def collection_sets() -> list[str]:
    """Set codes of every card in the collection files (everyone's, with accounts on)."""
    codes = set()
    for path in [config.COLLECTION_CSV, *config.DATA_DIR.glob("users/*/collection.csv")]:
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8") as f:
            codes.update((row.get("Set code") or "").strip().lower() for row in csv.DictReader(f))
    codes.discard("")
    return sorted(codes)


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


def fetch_image(url: str) -> bytes | None:
    """Download one card picture, retrying when the server is busy."""
    for attempt in range(5):
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


def build(source: Iterator[dict], db_path: Path | None = None, progress: Callable[[str], None] = print,
          on_batch: Callable[[], None] | None = None, stop: threading.Event | None = None) -> dict:
    """Fingerprint every card from source that the database doesn't have yet (or has
    only an older fingerprint for), and refresh the prices of the rest.

    progress gets a line of plain text now and then; on_batch is called every few
    thousand cards (the app reloads its fingerprints then, so new cards work right away).
    Returns {"added", "upgraded", "refreshed", "total", "skipped"}.
    """
    conn = connect(db_path or config.DB_PATH)
    known = {row[0]: len(row[1]) for row in conn.execute("SELECT id, fingerprint FROM cards")}
    todo, refreshed, seen = [], 0, set()
    for card in source:
        if card.get("digital") or card.get("layout") == "art_series" or card["id"] in seen:
            continue   # (a search can list the same printing twice)
        seen.add(card["id"])
        have = known.get(card["id"])
        if have is not None:
            conn.execute("UPDATE cards SET price_usd = ?, price_usd_foil = ? WHERE id = ?",
                         (price(card, "usd"), price(card, "usd_foil"), card["id"]))
            refreshed += 1
        if (have is None or have < FINGERPRINT_BYTES) and (url := image_url(card)):
            todo.append((card, url, have is not None))
    conn.commit()
    progress(f"Refreshed prices for {refreshed:,} cards already in the database. "
             f"Fingerprinting {len(todo):,} cards.")

    added = upgraded = skipped = 0
    started = time.monotonic()

    def fingerprints():
        # A small window of downloads in flight, so a stop takes effect quickly and
        # 100,000 cards never sit in memory at once.
        with ThreadPoolExecutor(max_workers=IMAGE_THREADS) as pool:
            for i in range(0, len(todo), 500):
                if stop is not None and stop.is_set():
                    return
                chunk = todo[i:i + 500]
                yield from zip(chunk, pool.map(fetch_fingerprint, [u for _, u, _ in chunk]))

    for n, ((card, _, upgrade), fp) in enumerate(fingerprints(), 1):
        if fp is None:
            skipped += 1
        elif upgrade:
            conn.execute("UPDATE cards SET fingerprint = ? WHERE id = ?", (fp, card["id"]))
            upgraded += 1
        else:
            conn.execute(
                "INSERT OR REPLACE INTO cards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    card["id"], card["name"], card["set"], card.get("set_name"),
                    card.get("collector_number"), card.get("rarity"),
                    ",".join(card.get("colors") or card.get("color_identity") or []),
                    price(card, "usd"), price(card, "usd_foil"), fp,
                ),
            )
            added += 1
        if n % 500 == 0 or n == len(todo):
            conn.commit()
            rate = n / max(time.monotonic() - started, 0.1)
            left = (len(todo) - n) / rate / 60
            progress(f"Fingerprinted {n:,} of {len(todo):,} cards"
                     + (f", about {left:.0f} min left" if n < len(todo) and left >= 1 else ""))
        if on_batch and n % 5000 == 0:
            on_batch()
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    conn.close()
    return {"added": added, "upgraded": upgraded, "refreshed": refreshed, "skipped": skipped, "total": total}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sets", help="comma-separated set codes, e.g. dmu,one,mkm")
    group.add_argument("--mine", action="store_true", help="the sets of the cards in your collection")
    group.add_argument("--all", action="store_true", help="every card on Scryfall")
    args = parser.parse_args()

    if args.all:
        source = cards_from_bulk()
    else:
        codes = collection_sets() if args.mine else [c.strip().lower() for c in args.sets.split(",") if c.strip()]
        if not codes:
            parser.error("No set codes: --sets needs at least one (e.g. --sets dmu,one), "
                         "and --mine needs cards in the collection")
        print(f"Sets: {', '.join(codes)}")
        source = cards_from_sets(codes)
    done = build(source)
    print(f"Done. Added {done['added']:,} cards, gave {done['upgraded']:,} the newer fingerprint"
          + (f", skipped {done['skipped']:,} whose picture didn't download" if done["skipped"] else "")
          + f". The database now has {done['total']:,} cards.")


if __name__ == "__main__":
    main()
