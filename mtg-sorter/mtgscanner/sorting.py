"""Decide which bin a card goes into. Change the bins in config.py."""

from . import config
from .database import Card
from .vault_prices import VaultPrices


def card_price(card: Card, foil: bool, vault: VaultPrices | None = None) -> tuple[float | None, str]:
    """Return (price in CAD, where it came from). Price is None if nobody has one."""
    if vault and (found := vault.price(card, foil)):
        return found
    usd = card.price_usd_foil if foil else card.price_usd
    if usd is None:
        return None, ""
    return round(usd * config.USD_TO_CAD, 2), f"Scryfall US price × {config.USD_TO_CAD:.2f}"


def choose_bin(card: Card, foil: bool = False, vault: VaultPrices | None = None) -> tuple[int, str]:
    """Return (bin number, bin label) for this card, based on its price."""
    price, _ = card_price(card, foil, vault)
    if price is None:
        return config.NO_PRICE_BIN
    for number, label, minimum in config.PRICE_BINS:
        if price >= minimum:
            return number, label
    return config.NO_PRICE_BIN
