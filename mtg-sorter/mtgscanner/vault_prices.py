"""Canadian prices from Commander Vault.

Commander Vault checks Near Mint prices at Canadian stores every week. Save its
price data as data/vault_prices.json and the scanner sorts by those CAD prices
the same way the Vault does:

  1. the exact printing (set + collector number + foil), if the Vault has it
  2. Face to Face Games' price for the card name
  3. the cheapest other store (401 Games, The Mythic Store, Hobbiesville)

Cards the Vault hasn't priced fall back to Scryfall's USD price converted to CAD.
"""

import json
from pathlib import Path

from .database import Card

STORE_NAMES = {"f2f": "Face to Face Games", "401": "401 Games", "myth": "The Mythic Store", "hob": "Hobbiesville"}


class VaultPrices:
    def __init__(self, data: dict):
        self.date = data.get("date", "")
        self.by_name = data.get("prices", {})       # name -> {store: [price, in_stock, foil_price]}
        self.by_printing = data.get("printings", {})  # "name|SET|cn|foil" -> [price, in_stock, store]

    @classmethod
    def load(cls, path: Path) -> "VaultPrices | None":
        if not path.exists():
            return None
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def price(self, card: Card, foil: bool) -> tuple[float, str] | None:
        """Return (CAD price, store name), or None if the Vault has no price for this card."""
        key = f"{card.name}|{card.set_code.upper()}|{card.collector_number}|{1 if foil else 0}"
        if (row := self.by_printing.get(key)) and _slot(row, 0) is not None:
            return _slot(row, 0), (row[2] if len(row) > 2 and row[2] else "Commander Vault")

        stores = self.by_name.get(card.name) or self.by_name.get(card.name.split(" // ")[0]) or {}
        slot = 2 if foil else 0
        if (f2f := stores.get("f2f")) and _slot(f2f, slot) is not None:
            return _slot(f2f, slot), STORE_NAMES["f2f"]
        others = [(_slot(row, slot), STORE_NAMES.get(s, s)) for s, row in stores.items() if _slot(row, slot) is not None]
        return min(others) if others else None


def _slot(row, i):
    """row[i] as a number, or None if the Vault left it out (a short row, null, or junk)."""
    try:
        value = row[i]
        return None if value is None else float(value)
    except (IndexError, TypeError, ValueError):
        return None
