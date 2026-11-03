"""Decide which bin a card goes into. Set the bins on the Bins page (sort_rules.py);
without saved rules they're the price bins in config.py."""

from . import config, sort_rules
from .database import Card
from .vault_prices import VaultPrices

# Which Scryfall price to use, best first. If a card was never printed in the finish you
# picked (a foil-only promo scanned with Foil off, or an etched foil), the next one is used
# instead of leaving the card without a price.
_FINISH_ORDER = {
    False: [("usd", ""), ("usd_foil", "foil price"), ("usd_etched", "etched price")],
    True: [("usd_foil", ""), ("usd_etched", "etched price"), ("usd", "non-foil price")],
}


def _pick_usd(prices: dict, foil: bool) -> tuple[float | None, str]:
    for key, note in _FINISH_ORDER[foil]:
        try:
            if prices.get(key):
                return float(prices[key]), note
        except (TypeError, ValueError):
            continue
    return None, ""


def card_price(card: Card, foil: bool, vault: VaultPrices | None = None, live=None) -> tuple[float | None, str]:
    """Return (price in CAD, where it came from). Price is None if nobody has one.

    Order: Commander Vault's Canadian price, then today's Scryfall price (if live lookups
    are on and the card has been fetched), then the Scryfall price saved in the database.
    """
    if vault and (found := vault.price(card, foil)):
        return found
    usd, note, source = None, "", ""
    if live and (prices := live.prices(card.id)):
        usd, note = _pick_usd(prices, foil)
        source = "Scryfall today"
    if usd is None:
        usd, note = _pick_usd({"usd": card.price_usd, "usd_foil": card.price_usd_foil}, foil)
        source = "Scryfall"
    if usd is None:
        return None, ""
    rate = config.USD_TO_CAD
    return round(usd * rate, 2), f"{source} US price × {rate:.2f}{', ' + note if note else ''}"


def bin_for(card: Card, foil: bool, price: float | None) -> tuple[int, str]:
    """Return (bin number, bin name) for a card whose price you already know."""
    return sort_rules.pick(card, foil, price)


def bin_for_price(price: float | None) -> tuple[int, str]:
    """The config.py price bins only (ignores the Bins page)."""
    if price is None:
        return config.NO_PRICE_BIN
    for number, label, minimum in config.PRICE_BINS:
        if price >= minimum:
            return number, label
    return config.NO_PRICE_BIN


def choose_bin(card: Card, foil: bool = False, vault: VaultPrices | None = None, live=None) -> tuple[int, str]:
    """Return (bin number, bin label) for this card, by the rules on the Bins page."""
    return bin_for(card, foil, card_price(card, foil, vault, live)[0])
