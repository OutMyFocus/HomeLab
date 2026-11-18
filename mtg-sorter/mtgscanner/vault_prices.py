"""Canadian store prices (what Commander Vault used to keep).

The weekly price check (ca_prices.py) saves Near Mint prices at Canadian stores in
data/vault_prices.json by itself. The scanner sorts by those CAD prices the same way
the pages show them:

  1. the exact printing (set + collector number + foil), if the check has it
  2. Face to Face Games' price for the card name
  3. otherwise the cheapest other store with the card in stock (401 Games, The Mythic
     Store, Hobbiesville, Card Brawlers, L'Univers de la Carte), or the cheapest one
     at all if none has it in stock

Cards with no store price fall back to Scryfall's USD price converted to CAD.
"""

import json
from pathlib import Path

from .database import Card

STORE_NAMES = {"f2f": "Face to Face Games", "401": "401 Games", "myth": "The Mythic Store", "hob": "Hobbiesville",
               "cb": "Card Brawlers", "udc": "L'Univers de la Carte"}


class VaultPrices:
    def __init__(self, data: dict):
        self.date = data.get("date", "")
        self.by_name = data.get("prices", {})       # name -> {store: [price, in_stock, foil_price]}
        self.by_printing = data.get("printings", {})  # "name|SET|cn|foil" -> [price, in_stock, store]
        if not isinstance(self.by_name, dict):
            self.by_name = {}
        if not isinstance(self.by_printing, dict):
            self.by_printing = {}

    @classmethod
    def load(cls, path: Path) -> "VaultPrices | None":
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if not isinstance(data, dict):
            print(f"data/{path.name} is damaged, using Scryfall prices until the next price check.")
            return None
        return cls(data)

    def price(self, card: Card, foil: bool) -> tuple[float, str] | None:
        """Return (CAD price, store name), or None if the Vault has no price for this card."""
        key = f"{card.name}|{card.set_code.upper()}|{card.collector_number}|{1 if foil else 0}"
        if (row := self.by_printing.get(key)) and _slot(row, 0) is not None:
            return _slot(row, 0), (row[2] if len(row) > 2 and row[2] else "Commander Vault")

        stores = self.by_name.get(card.name) or self.by_name.get(card.name.split(" // ")[0]) or {}
        if not isinstance(stores, dict):
            return None
        slot = 2 if foil else 0
        # The same choice the pages make (ca_prices.main_price, caBest in vault.js): only
        # prices above $0 count, Face to Face Games first, then the cheapest store with the
        # card in stock. Foil prices have no stock flag, so they count as in stock.
        if (price := _slot(stores.get("f2f"), slot)) is not None and price > 0:
            return price, STORE_NAMES["f2f"]
        others = []
        for s, row in stores.items():
            if (price := _slot(row, slot)) is not None and price > 0:
                in_stock = True if foil else bool(_slot(row, 1))
                others.append((not in_stock, price, STORE_NAMES.get(s, s)))
        if not others:
            return None
        _, price, store = min(others)
        return price, store


def _slot(row, i):
    """row[i] as a number, or None if the Vault left it out (a short row, null, or junk)."""
    try:
        value = row[i]
        return None if value is None else float(value)
    except (IndexError, TypeError, ValueError):
        return None
