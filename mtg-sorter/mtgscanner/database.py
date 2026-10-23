"""The card database: every known card with its fingerprint and price.

It's a single SQLite file (data/cards.db) that build_db.py creates.
"""

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,          -- Scryfall's unique ID for this printing
    name TEXT NOT NULL,
    set_code TEXT NOT NULL,
    set_name TEXT,
    collector_number TEXT,
    rarity TEXT,
    colors TEXT,                  -- e.g. "W,U" (empty for colorless)
    price_usd REAL,               -- NULL if Scryfall has no price
    price_usd_foil REAL,
    fingerprint BLOB NOT NULL     -- 32-byte perceptual hash
);

-- Extra fingerprints taught from your own scans (the Train tab). A card can have
-- several. Kept when build_db.py refreshes the cards.
CREATE TABLE IF NOT EXISTS learned (
    scan TEXT PRIMARY KEY,        -- the picture it came from, in data/captures
    card_id TEXT NOT NULL,
    fingerprint BLOB NOT NULL,
    added TEXT
);
"""


@dataclass
class Card:
    id: str
    name: str
    set_code: str
    set_name: str
    collector_number: str
    rarity: str
    colors: str
    price_usd: float | None
    price_usd_foil: float | None


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    # The app reads from both its camera thread and its web server, so allow sharing.
    conn = sqlite3.connect(path, check_same_thread=False, timeout=60)
    # Write-ahead logging lets the app keep reading while build_db.py adds cards.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


# Lookup table: how many 1-bits are in each possible byte value (0-255). Only used
# with NumPy older than 2.0, which lacks np.bitwise_count.
_POPCOUNT = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint16)


def _distances(hashes: np.ndarray, fp: bytes) -> np.ndarray:
    """Bits that differ between the fingerprint and every row of hashes (uint64 view)."""
    x = np.bitwise_xor(hashes, np.frombuffer(fp, dtype=np.uint64))
    if hasattr(np, "bitwise_count"):
        return np.bitwise_count(x).sum(axis=1, dtype=np.uint32)
    return _POPCOUNT[x.view(np.uint8)].sum(axis=1)


class Matcher:
    """Loads every fingerprint into memory and finds the closest one to a scan."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._lock = threading.Lock()
        self.reload()

    def reload(self):
        """Read the fingerprints again, e.g. after training or after build_db.py added cards."""
        with self._lock:
            rows = self.conn.execute("SELECT id, fingerprint FROM cards").fetchall()
            learned = self.conn.execute(
                "SELECT l.card_id, l.fingerprint FROM learned l JOIN cards c ON c.id = l.card_id").fetchall()
        if not rows:
            raise RuntimeError("The card database is empty. Run build_db.py first.")
        rows += learned
        ids = [r[0] for r in rows]
        # 32-byte fingerprints as 4 x 64-bit numbers: comparing those is much faster.
        hashes = np.frombuffer(b"".join(r[1] for r in rows), dtype=np.uint64).reshape(len(rows), -1)
        self.card_count, self.learned_count = len(rows) - len(learned), len(learned)
        self._table = ids, hashes   # swapped in one step, so a scan never sees half of it

    def add_learned(self, scan: str, card_id: str, fp: bytes):
        """Learn one scan right away (the Keep learning switch), without a full reload."""
        with self._lock:
            self.conn.execute("INSERT OR REPLACE INTO learned VALUES (?, ?, ?, datetime('now', 'localtime'))", (scan, card_id, fp))
            self.conn.commit()
            ids, hashes = self._table
            self._table = ids + [card_id], np.vstack([hashes, np.frombuffer(fp, dtype=np.uint64)])
            self.learned_count += 1

    def best_match(self, fp: bytes) -> tuple[str, int]:
        """Return (card id, distance) of the closest card. Smaller distance is better."""
        ids, hashes = self._table
        dists = _distances(hashes, fp)
        # On a tie, the last one wins: learned scans come after the cards, and what
        # you taught it beats the stock picture.
        i = len(dists) - 1 - int(dists[::-1].argmin())
        if i >= self.card_count and dists[i] > config.MAX_LEARNED_DISTANCE:
            i = int(dists[:self.card_count].argmin())   # not close enough to trust: stock pictures only
        return ids[i], int(dists[i])

    def search(self, text: str, limit: int = 24) -> list[Card]:
        """Cards whose name contains the text, for picking the right card by hand."""
        with self._lock:
            ids = [r[0] for r in self.conn.execute(
                "SELECT id FROM cards WHERE name LIKE ? ORDER BY name LIKE ? DESC, name, set_code LIMIT ?",
                (f"%{text}%", f"{text}%", limit))]
        return [self.get_card(i) for i in ids]

    def get_card(self, card_id: str) -> Card:
        with self._lock:
            row = self._card_row(card_id)
        return Card(*row)

    def _card_row(self, card_id: str):
        return self.conn.execute(
            "SELECT id, name, set_code, set_name, collector_number, rarity, colors, price_usd, price_usd_foil "
            "FROM cards WHERE id = ?",
            (card_id,),
        ).fetchone()
