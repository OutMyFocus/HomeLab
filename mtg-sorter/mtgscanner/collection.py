"""Save scanned cards to a CSV file.

The columns use ManaBox's export format (Name, Quantity, Set code, Collector
number, Foil), so ManaBox, Moxfield and most spreadsheet apps read it. The Source
column says where a card came from: blank for cards the scanner saved, or the name of
an import (a ManaBox CSV, or a source brought over from Commander Vault).
"""

import csv
import io
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path

from .database import Card

COLUMNS = ["Name", "Quantity", "Set code", "Set name", "Collector number", "Foil", "Rarity",
           "Scryfall ID", "Price CAD", "Price source", "Bin", "Scanned at", "Source",
           # Filled in on the Collection page (blank: near mint, English, price not known, no tags)
           "Condition", "Language", "Purchase price", "Tags",
           # "yes" for a proxy (a printed copy, not the real card): kept, but worth nothing
           "Proxy"]
# The columns the scanner fills in itself, in order (add_card writes these, the rest blank).
SCANNED_COLUMNS = COLUMNS[:13]

# Every change to a collection file goes through this one lock. Each phone has a scanner
# (and a lock) of its own, so the scanner locks alone let a phone's scan land while the
# Collection page was rewriting the file, and that scan was lost. Take it after a scanner's
# lock, never before one. It's an RLock because the writers below call each other.
COLLECTION_LOCK = threading.RLock()


def read_text(path: Path) -> str:
    """The file's text. Copes with a file saved by Excel: a BOM at the start ("CSV UTF-8"),
    or the old Windows encoding instead of UTF-8."""
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def replace_csv(path: Path, fieldnames: list[str], rows, plain: bool = False):
    """Write the whole file to a temporary file next to it, then swap it in all at once,
    so a reader (or a crash halfway) never sees half a file. `rows` are dicts, or lists
    when plain is True."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with tmp.open("w", newline="", encoding="utf-8") as f:
            if plain:
                csv.writer(f).writerows(rows)
            else:
                w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                w.writeheader()
                w.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def extra_columns(header) -> list[str]:
    """Columns someone added by hand (a Notes column, say), kept after ours."""
    return [h for h in header if h and h not in COLUMNS]


def ensure_columns(path: Path):
    """Rewrite an older CSV (from before a column was added) with today's columns, so new
    rows line up with the header. Does nothing when the header is already current.
    A copy of the file is kept as collection.csv.bak before it is rewritten."""
    with COLLECTION_LOCK:
        if not path.exists():
            return
        data = path.read_bytes()
        try:
            text, recoded = data.decode("utf-8"), False
        except UnicodeDecodeError:   # saved by Excel in the old Windows encoding
            text, recoded = data.decode("cp1252", errors="replace"), True
        bom = text.startswith("﻿")
        text = text.lstrip("﻿")
        header = next(csv.reader(io.StringIO(text)), [])
        if not header or (header[:len(COLUMNS)] == COLUMNS and not bom and not recoded):
            return
        backup = path.with_name(path.name + ".bak")
        shutil.copyfile(path, backup)
        if "Name" not in header:
            raise ValueError(f"{path.name} has no Name column, so cards can't be saved into it. "
                             f"A copy was kept as {backup.name}. Fix the file's first line, "
                             "or restore a backup on the Maintenance page.")
        rows = list(csv.DictReader(io.StringIO(text)))
        replace_csv(path, COLUMNS + extra_columns(header), rows)


def append_rows(path: Path, rows: list[dict]):
    """Add several rows at once (an import). Each row is a dict keyed by COLUMNS."""
    with COLLECTION_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        ensure_columns(path)
        is_new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            if is_new:
                w.writeheader()
            w.writerows(rows)


def _read_lists(path: Path) -> list[list[str]]:
    return list(csv.reader(io.StringIO(read_text(path))))


def remove_last(path: Path) -> bool:
    """Delete the most recently added card. Returns False if the file has no cards."""
    with COLLECTION_LOCK:
        if not path.exists():
            return False
        rows = _read_lists(path)
        while len(rows) > 1 and not any(x.strip() for x in rows[-1]):
            rows.pop()   # blank lines at the end aren't cards
        if len(rows) < 2:
            return False
        replace_csv(path, [], rows[:-1], plain=True)
        return True


def remove_entry(path: Path, card_id: str, scanned_at: str) -> bool:
    """Delete one particular saved card (matched by Scryfall ID and time saved)."""
    with COLLECTION_LOCK:
        if not path.exists():
            return False
        rows = _read_lists(path)
        if not rows:
            return False
        head = rows[0]
        try:
            id_col, at_col = head.index("Scryfall ID"), head.index("Scanned at")
        except ValueError:
            return False
        for i in range(len(rows) - 1, 0, -1):
            r = rows[i]
            if len(r) > max(id_col, at_col) and r[id_col] == card_id and r[at_col] == scanned_at:
                del rows[i]
                replace_csv(path, [], rows, plain=True)
                return True
        return False


def add_card(path: Path, card: Card, foil: bool, bin_label: str, price: tuple[float | None, str],
             origin: str = "", proxy: bool = False) -> str:
    """price is (CAD price, source), as returned by sorting.card_price(). `origin` goes in
    the Source column: who the card came from (a name typed on a phone; blank for the
    machine). proxy: it's a proxy, not the real card (the Proxy column says yes).
    Returns the time it was saved, which remove_entry() uses to find it again."""
    with COLLECTION_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        ensure_columns(path)
        is_new = not path.exists()
        cad, source = price
        scanned_at = datetime.now().isoformat(timespec="seconds")
        with path.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if is_new:
                w.writerow(COLUMNS)
            w.writerow([
                card.name,
                1,
                card.set_code.upper(),
                card.set_name,
                card.collector_number,
                "foil" if foil else "normal",
                card.rarity,
                card.id,
                "" if cad is None else f"{cad:.2f}",
                source,
                bin_label,
                scanned_at,
                origin,
            ] + ["yes" if proxy and c == "Proxy" else "" for c in COLUMNS[len(SCANNED_COLUMNS):]])
    return scanned_at
