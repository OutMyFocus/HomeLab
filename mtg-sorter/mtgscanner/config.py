"""Settings you can tweak. Start here if you want to change how the scanner behaves."""

from pathlib import Path

# Where data files live (the card database and your collection CSV).
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "cards.db"
COLLECTION_CSV = DATA_DIR / "collection.csv"
# Canadian prices saved from Commander Vault (optional, see vault_prices.py).
VAULT_PRICES = DATA_DIR / "vault_prices.json"

# Scryfall asks every app to identify itself. See https://scryfall.com/docs/api
USER_AGENT = "HomeLabMTGSorter/0.1"

# --- Price bins -----------------------------------------------------------
# Cards go into the FIRST bin whose minimum price they meet, checked top to
# bottom. Prices are in Canadian dollars. Bin numbers line up with the physical
# bins on the sorter later.
PRICE_BINS = [
    # (bin number, label, minimum price)
    (3, "$10+ (valuable!)", 10.00),
    (2, "$1 - $10", 1.00),
    (1, "Bulk (under $1)", 0.00),
]
# Cards nobody has a price for (tokens, very old or obscure printings).
NO_PRICE_BIN = (0, "Unknown price")

# Cards Commander Vault hasn't priced use Scryfall's USD price, converted with the
# Bank of Canada's rate for the day. This rate is the fallback when that can't be
# fetched (no internet, or app.py --offline). Update it now and then.
USD_TO_CAD = 1.38

# --- Recognition tuning ---------------------------------------------------
# Each card image turns into a 256-bit "fingerprint". The distance between two
# fingerprints counts the bits that differ (0 means identical). Two unrelated
# cards usually land around 128.
MAX_MATCH_DISTANCE = 90
# Matches at or below this distance are shown as "Good match"; above it, "Fair match".
GOOD_MATCH_DISTANCE = 60

# How many camera frames in a row must agree on the same card before we trust it.
STABLE_FRAMES = 5
