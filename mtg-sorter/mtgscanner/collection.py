"""Save scanned cards to a CSV file.

The columns use ManaBox's export format (Name, Quantity, Set code, Collector
number, Foil), so the file can be imported straight into Commander Vault's
Collection tab ("Import a ManaBox CSV"). Each scanning session becomes its own
source there. Moxfield and most spreadsheet apps also read it.
"""

import csv
from datetime import datetime
from pathlib import Path

from .database import Card

COLUMNS = ["Name", "Quantity", "Set code", "Set name", "Collector number", "Foil", "Rarity",
           "Scryfall ID", "Price CAD", "Price source", "Bin", "Scanned at"]


def remove_last(path: Path) -> bool:
    """Delete the most recently added card. Returns False if the file has no cards."""
    if not path.exists():
        return False
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if len(rows) < 2:
        return False
    with path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows[:-1])
    return True


def remove_entry(path: Path, card_id: str, scanned_at: str) -> bool:
    """Delete one particular saved card (matched by Scryfall ID and time saved)."""
    if not path.exists():
        return False
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    for i in range(len(rows) - 1, 0, -1):
        if rows[i][7] == card_id and rows[i][11] == scanned_at:
            del rows[i]
            with path.open("w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows(rows)
            return True
    return False


def add_card(path: Path, card: Card, foil: bool, bin_label: str, price: tuple[float | None, str]) -> str:
    """price is (CAD price, source), as returned by sorting.card_price(). Returns the
    time it was saved, which remove_entry() uses to find it again."""
    path.parent.mkdir(parents=True, exist_ok=True)
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
        ])
    return scanned_at
