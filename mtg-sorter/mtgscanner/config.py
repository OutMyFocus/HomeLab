"""Settings you can tweak. Start here if you want to change how the scanner behaves."""

from pathlib import Path

# Where data files live (the card database and your collection CSV).
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "cards.db"
COLLECTION_CSV = DATA_DIR / "collection.csv"

# Scryfall asks every app to identify itself. See https://scryfall.com/docs/api
USER_AGENT = "HomeLabMTGSorter/0.1"

# --- Price bins -----------------------------------------------------------
# Cards go into the FIRST bin whose minimum price they meet, checked top to
# bottom. Prices are in US dollars. Bin numbers line up with the physical bins
# on the sorter later.
PRICE_BINS = [
    # (bin number, label, minimum price)
    (3, "$10+ (valuable!)", 10.00),
    (2, "$1 - $10", 1.00),
    (1, "Bulk (under $1)", 0.00),
]
# Cards Scryfall has no price for (very old or obscure printings).
NO_PRICE_BIN = (0, "Unknown price")

# --- Recognition tuning ---------------------------------------------------
# Each card image turns into a 256-bit "fingerprint". The distance between two
# fingerprints counts the bits that differ (0 means identical). Two unrelated
# cards usually land around 128.
MAX_MATCH_DISTANCE = 90

# How many camera frames in a row must agree on the same card before we trust it.
STABLE_FRAMES = 5
