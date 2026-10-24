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
           "Scryfall ID", "Price CAD", "Price source", "Bin", "Scanned at", "Bin number"]


def _upgrade_header(path: Path) -> None:
    """Files saved before "Bin number" existed get the new column (left empty for old rows)."""
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows or rows[0] == COLUMNS:
        return
    width = len(COLUMNS)
    rows = [COLUMNS] + [r + [""] * (width - len(r)) for r in rows[1:]]
    with path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


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


def add_card(path: Path, card: Card, foil: bool, bin_label: str, price: tuple[float | None, str],
             bin_number: int | str = "") -> None:
    """price is (CAD price, source), as returned by sorting.card_price()."""
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    if not is_new:
        _upgrade_header(path)
    cad, source = price
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
            datetime.now().isoformat(timespec="seconds"),
            bin_number,
        ])
