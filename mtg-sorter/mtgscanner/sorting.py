"""Decide which bin a card goes into. Change the bins in config.py."""

from . import config
from .database import Card


def choose_bin(card: Card, foil: bool = False) -> tuple[int, str]:
    """Return (bin number, bin label) for this card, based on its price."""
    price = card.price_usd_foil if foil else card.price_usd
    if price is None:
        return config.NO_PRICE_BIN
    for number, label, minimum in config.PRICE_BINS:
        if price >= minimum:
            return number, label
    return config.NO_PRICE_BIN
