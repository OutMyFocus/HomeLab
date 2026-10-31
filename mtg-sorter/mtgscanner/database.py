"""The card database: every known card with its fingerprint and price.

It's a single SQLite file (data/cards.db) that build_db.py creates.
"""

import sqlite3
import threading
from dataclasses import dataclass, field
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

-- Printings picked by hand that aren't in the cards table (fetched from Scryfall with
-- the "Other printing" picker). No fingerprint of their own; scans taught to them in the
-- Train tab work like any other learned scan.
CREATE TABLE IF NOT EXISTS extra_cards (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    set_code TEXT NOT NULL,
    set_name TEXT,
    collector_number TEXT,
    rarity TEXT,
    colors TEXT,
    price_usd REAL,
    price_usd_foil REAL
);
"""

_COLUMNS = "id, name, set_code, set_name, collector_number, rarity, colors, price_usd, price_usd_foil"


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


@dataclass
class Hit:
    """The closest card to one fingerprint, and how clear-cut that is."""
    id: str
    distance: int                 # bits that differ from the closest fingerprint (0 = identical)
    margin: int                   # how many more bits the closest card with a DIFFERENT name is away
    candidates: list[tuple[str, int]] = field(default_factory=list)   # (id, distance) of the next-closest names


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


def _name_key(name: str) -> str:
    """Printings of the same card count as one answer, whatever the set."""
    return name.split(" // ")[0].strip().lower()


class Matcher:
    """Loads every fingerprint into memory and finds the closest one to a scan."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._lock = threading.Lock()
        self.reload()

    def reload(self):
        """Read the fingerprints again, e.g. after training or after build_db.py added cards."""
        with self._lock:
            rows = self.conn.execute("SELECT id, name, fingerprint FROM cards").fetchall()
            learned = self.conn.execute(
                "SELECT l.card_id, c.name, l.fingerprint FROM learned l JOIN "
                "(SELECT id, name FROM cards UNION ALL SELECT id, name FROM extra_cards) c ON c.id = l.card_id").fetchall()
        if not rows:
            raise RuntimeError("The card database is empty. Run build_db.py first.")
        rows += learned
        ids = [r[0] for r in rows]
        # Every card name gets a number, so "is this the same card?" is an integer compare.
        self._name_numbers: dict[str, int] = {}
        names = np.fromiter((self._name_numbers.setdefault(_name_key(r[1]), len(self._name_numbers)) for r in rows),
                            dtype=np.int32, count=len(rows))
        # 32-byte fingerprints as 4 x 64-bit numbers: comparing those is much faster.
        hashes = np.frombuffer(b"".join(r[2] for r in rows), dtype=np.uint64).reshape(len(rows), -1)
        self.card_count, self.learned_count = len(rows) - len(learned), len(learned)
        self._table = ids, hashes, names   # swapped in one step, so a scan never sees half of it

    def add_learned(self, scan: str, card_id: str, fp: bytes):
        """Learn one scan right away (the Keep learning switch), without a full reload."""
        with self._lock:
            self.conn.execute("INSERT OR REPLACE INTO learned VALUES (?, ?, ?, datetime('now', 'localtime'))", (scan, card_id, fp))
            self.conn.commit()
            row = self._card_row(card_id)
            if row is None:
                return   # a card it doesn't know at all: nothing to learn it as
            ids, hashes, names = self._table
            number = self._name_numbers.setdefault(_name_key(row[1]), len(self._name_numbers))
            self._table = (ids + [card_id], np.vstack([hashes, np.frombuffer(fp, dtype=np.uint64)]),
                           np.append(names, np.int32(number)))
            self.learned_count += 1

    def _closest(self, dists: np.ndarray) -> int:
        # On a tie, the last one wins: learned scans come after the cards, and what
        # you taught it beats the stock picture.
        i = len(dists) - 1 - int(dists[::-1].argmin())
        if i >= self.card_count and dists[i] > config.MAX_LEARNED_DISTANCE:
            i = int(dists[:self.card_count].argmin())   # not close enough to trust: stock pictures only
        return i

    def best_match(self, fp: bytes) -> tuple[str, int]:
        """Return (card id, distance) of the closest card. Smaller distance is better."""
        ids, hashes, _ = self._table
        dists = _distances(hashes, fp)
        i = self._closest(dists)
        return ids[i], int(dists[i])

    def rank(self, fp: bytes, candidates: int = 3) -> Hit:
        """The closest card, how far behind the closest *different* card is (the margin),
        and the next few different cards in case the first guess is wrong."""
        ids, hashes, names = self._table
        dists = _distances(hashes, fp)
        i = self._closest(dists)
        others = dists[names != names[i]]
        margin = int(others.min()) - int(dists[i]) if others.size else 256
        hit = Hit(ids[i], int(dists[i]), margin)
        if candidates:
            k = min(len(dists) - 1, 48)
            top = np.argpartition(dists, k)[:k + 1]
            seen = {int(names[i])}
            for j in top[np.argsort(dists[top], kind="stable")]:
                if int(names[j]) in seen:
                    continue
                seen.add(int(names[j]))
                hit.candidates.append((ids[j], int(dists[j])))
                if len(hit.candidates) >= candidates:
                    break
        return hit

    def search(self, text: str, limit: int = 24) -> list[Card]:
        """Cards whose name contains the text, for picking the right card by hand."""
        with self._lock:
            ids = [r[0] for r in self.conn.execute(
                "SELECT id FROM cards WHERE name LIKE ? ORDER BY name LIKE ? DESC, name, set_code LIMIT ?",
                (f"%{text}%", f"{text}%", limit))]
        return [self.get_card(i) for i in ids]

    def printings(self, name: str) -> list[Card]:
        """Every printing of this exact card name in the database."""
        with self._lock:
            rows = self.conn.execute(f"SELECT {_COLUMNS} FROM cards WHERE name = ? COLLATE NOCASE "
                                     f"UNION SELECT {_COLUMNS} FROM extra_cards WHERE name = ? COLLATE NOCASE "
                                     "ORDER BY set_code", (name, name)).fetchall()
        return [Card(*r) for r in rows]

    def get_card(self, card_id: str) -> Card:
        card = self.find_card(card_id)
        if card is None:
            raise KeyError(card_id)
        return card

    def find_card(self, card_id: str) -> Card | None:
        """The card with this Scryfall id, or None if the database doesn't have it."""
        with self._lock:
            row = self._card_row(card_id)
        return Card(*row) if row else None

    def remember(self, card: Card):
        """Keep a printing that isn't in the cards table (picked from Scryfall by hand)."""
        with self._lock:
            if self.conn.execute("SELECT 1 FROM cards WHERE id = ?", (card.id,)).fetchone():
                return
            self.conn.execute(f"INSERT OR REPLACE INTO extra_cards ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                              (card.id, card.name, card.set_code, card.set_name, card.collector_number,
                               card.rarity, card.colors, card.price_usd, card.price_usd_foil))
            self.conn.commit()

    def _card_row(self, card_id: str):
        return (self.conn.execute(f"SELECT {_COLUMNS} FROM cards WHERE id = ?", (card_id,)).fetchone()
                or self.conn.execute(f"SELECT {_COLUMNS} FROM extra_cards WHERE id = ?", (card_id,)).fetchone())
