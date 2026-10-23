"""Settings you can tweak. Start here if you want to change how the scanner behaves."""

from pathlib import Path

# Where data files live (the card database and your collection CSV).
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "cards.db"
COLLECTION_CSV = DATA_DIR / "collection.csv"
# Canadian prices saved from Commander Vault (optional, see vault_prices.py).
VAULT_PRICES = DATA_DIR / "vault_prices.json"
# Scans kept to improve recognition (turn on "Collect scans" in the app).
CAPTURES_DIR = DATA_DIR / "captures"

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

# Used only for cards Commander Vault hasn't priced: Scryfall's USD price is
# converted with this rate. The apps replace it with the Bank of Canada's rate
# for the day (see exchange.py); this number is only used offline.
USD_TO_CAD = 1.38

# --- Recognition tuning ---------------------------------------------------
# Each card image turns into a 256-bit "fingerprint". The distance between two
# fingerprints counts the bits that differ (0 means identical). Two unrelated
# cards usually land around 128.
MAX_MATCH_DISTANCE = 90
# Scans learned in the Train tab come from your own camera, so they share its light
# and background with every new scan, which can make unrelated cards look a little
# alike. A match to a learned scan therefore has to be closer than this.
MAX_LEARNED_DISTANCE = 60

# How many camera frames in a row must agree on the same card before we trust it.
STABLE_FRAMES = 5

# The smallest card the camera looks for, as a share of the whole picture. 0.05 (5%)
# suits a camera close to the card, like the scan station. A camera high above a
# table sees each card at about 1-2% of the picture, so it needs a lower number.
MIN_CARD_AREA = 0.01

# Camera picture size to ask for. A webcam that can't do it picks its closest size.
# Bigger means sharper pictures of small cards, at a bit more work per frame.
CAMERA_SIZE = (1920, 1080)
