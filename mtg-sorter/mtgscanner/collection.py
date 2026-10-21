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
           "Scryfall ID", "Scryfall price USD", "Bin", "Scanned at"]


def add_card(path: Path, card: Card, foil: bool, bin_label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    price = card.price_usd_foil if foil else card.price_usd
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
            "" if price is None else f"{price:.2f}",
            bin_label,
            datetime.now().isoformat(timespec="seconds"),
        ])
