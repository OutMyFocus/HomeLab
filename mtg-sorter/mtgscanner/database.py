"""The card database: every known card with its fingerprint and price.

It's a single SQLite file (data/cards.db) that build_db.py creates.
"""

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

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
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute(SCHEMA)
    return conn


_CARD_COLUMNS = "id, name, set_code, set_name, collector_number, rarity, colors, price_usd, price_usd_foil"

# Lookup table: how many 1-bits are in each possible byte value (0-255).
_POPCOUNT = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint16)


class Matcher:
    """Loads every fingerprint into memory and finds the closest one to a scan."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._lock = threading.Lock()
        rows = conn.execute("SELECT id, fingerprint FROM cards").fetchall()
        if not rows:
            raise RuntimeError("The card database is empty. Run build_db.py first.")
        self.ids = [r[0] for r in rows]
        self.hashes = np.frombuffer(b"".join(r[1] for r in rows), dtype=np.uint8).reshape(len(rows), -1)

    def best_match(self, fp: bytes) -> tuple[str, int]:
        """Return (card id, distance) of the closest card. Smaller distance is better."""
        q = np.frombuffer(fp, dtype=np.uint8)
        dists = _POPCOUNT[np.bitwise_xor(self.hashes, q)].sum(axis=1)
        i = int(dists.argmin())
        return self.ids[i], int(dists[i])

    def get_card(self, card_id: str) -> Card | None:
        """The card with this Scryfall id, or None if it isn't in the database."""
        with self._lock:
            row = self._card_row(card_id)
        return Card(*row) if row else None

    def printings(self, name: str) -> list[Card]:
        """Every printing of this card name in the database."""
        with self._lock:
            rows = self.conn.execute(f"SELECT {_CARD_COLUMNS} FROM cards WHERE name = ? ORDER BY set_name", (name,)).fetchall()
        return [Card(*r) for r in rows]

    def search_names(self, text: str, limit: int = 20) -> list[str]:
        """Card names containing this text (used when there's no internet for Scryfall's search)."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT DISTINCT name FROM cards WHERE name LIKE ? ORDER BY name LIKE ? DESC, name LIMIT ?",
                (f"%{text}%", f"{text}%", limit),
            ).fetchall()
        return [r[0] for r in rows]

    def _card_row(self, card_id: str):
        return self.conn.execute(
            f"SELECT {_CARD_COLUMNS} FROM cards WHERE id = ?",
            (card_id,),
        ).fetchone()
