"""Settings you can tweak. Start here if you want to change how the scanner behaves."""

import os
from pathlib import Path

# Where data files live (the card database and your collection CSV): the data folder
# next to app.py, or the folder named by MTG_DATA_DIR (the Docker image uses /data).
DATA_DIR = Path(os.environ.get("MTG_DATA_DIR") or Path(__file__).resolve().parent.parent / "data").resolve()
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
# Each card image turns into a fingerprint: 256 bits for the whole card plus 256 for its
# art (vision.py). The distance between two fingerprints is the average number of bits
# that differ in the two (0 means identical). Measured on every card Scryfall has
# (108,000 printings) with simulated phone photos: the right card lands around 20-60,
# while the closest *different* card is rarely under 75 and a thing that isn't a card at
# all is 84 or more. So anything over this is "not a card I know":
MAX_MATCH_DISTANCE = 78
# The scanner also looks at the MARGIN: how many more bits away the closest card
# with a *different* name is. A small margin means two cards look alike to it, so
# the answer is shown as "unsure" (never auto-saved) with the other candidates.
SURE_DISTANCE = 60     # this close, with this much margin, and the card is "sure"...
SURE_MARGIN = 10
LIKELY_DISTANCE = 75   # ...this close with at least LIKELY_MARGIN is "likely", else "unsure"
LIKELY_MARGIN = 5
CANDIDATE_DISTANCE = 90    # other cards no further than this are offered as alternatives
# Scans learned in the Train tab come from your own camera, so they share its light
# and background with every new scan, which can make unrelated cards look a little
# alike. A match to a learned scan therefore has to be closer than this.
MAX_LEARNED_DISTANCE = 60

# The detector's outline often lands a little inside or outside the card's real edge
# (a sleeve adds a margin), and fingerprints are sensitive to that. Each outline is
# tried scaled by these factors; the closest match wins.
OUTLINE_FACTORS = (1.0, 1.04, 1.08)

# How many camera frames in a row must agree on a card before we trust it (used by
# scan.py; app.py needs fewer looks the surer the match is, see tracking.py).
STABLE_FRAMES = 3
# A recognized card that hasn't moved is looked at again this often (seconds).
RECHECK_SECONDS = 2.0
# A card out of sight for this long (a hand over it is shorter) counts as taken away.
GONE_SECONDS = 0.8
# Cards are recognized in parallel; 0 means one thread per CPU core (at most 8).
IDENTIFY_THREADS = 0

# The smallest card the camera looks for, as a share of the whole picture. 0.05 (5%)
# suits a camera close to the card, like the scan station. A camera high above a
# table sees each card at about 1-2% of the picture, so it needs a lower number.
MIN_CARD_AREA = 0.01

# --- Slots mode (app.py) ---------------------------------------------------
# Instead of looking for cards anywhere, the app can look only in boxes you draw on
# the picture, one per card position (a tray, an open box, spots marked on the mat).
# Each slot is searched with a little extra around it, as a share of its size.
SLOT_MARGIN = 0.08
# A card has to fill at least this share of its slot. Smaller shapes in a slot (a
# finger, a corner of the box, a dice) aren't cards.
SLOT_MIN_CARD = 0.15
# When the detector can't outline the card in a slot (a card in a box, a glossy
# sleeve), the slot itself is used as the outline, as long as something is in it.
# That's judged by how much of the slot is edges: plain table or cardboard shows
# almost none (under 0.01), a card shows plenty (0.10 and up).
SLOT_OCCUPIED_EDGES = 0.04

# Camera picture size to ask for. A webcam that can't do it picks its closest size.
# Bigger means sharper pictures of small cards, at a bit more work per frame.
CAMERA_SIZE = (1920, 1080)

# --- The machine: servos and feeder (machine.py) ---------------------------
# Wiring: hardware/ASSEMBLY.md, Stage C. The servos plug into the PCA9685 board, which
# the Pi talks to over I2C. Angles are 0-180 with 90 the middle, where each horn was
# fitted. These are first guesses: find better ones on the Machine page (/machine) and
# press Save there. Saved angles live in data/machine_settings.json and win over these, so
# there's no need to edit this file on the Pi (which would stop automatic updates).
# Seconds a servo keeps holding after a move before it lets go (0 = hold until told).
# Holding against something it can't push past makes a servo hot.
SERVO_HOLD_SECONDS = 1.5
# Parts that keep holding after a move, because they fall back on their own if let go:
# the stop gate drops under its own weight, and it has to stand firm against the card the
# feeder pushes into it. The chute v3 trapdoors hang from hinges at their outer edges, so
# they sag open if their servos let go (set "closed" a hair short of the door's stop, so the
# servo isn't pushing against it: hardware/CHUTE_V3.md).
SERVO_KEEP_HOLDING = ("pins", "door_r", "door_l")

SERVOS = {
    # part: (PCA9685 channel, {position: angle})
    "pins":   (0, {"up": 90, "down": 62}),                   # stop pins: up stops the card
    "chute":  (1, {"centre": 90, "left": 65, "right": 115}),  # tilts the tray to bin 1 or 3
    # chute v3 doors turn 95 degrees through a crank and link (needs Wider servo travel on)
    "door_r": (2, {"closed": 40, "open": 135}),               # right trapdoor (bin 2)
    "door_l": (3, {"closed": 140, "open": 45}),               # left trapdoor (bin 2)
}
# Servo pulse widths in microseconds for 0 and 180 degrees. The first is ServoKit's
# default, which turns an MG90S only about 130-140 real degrees. "Wider servo travel" on
# the Machine page switches to the second for about the full 180 (some cheap servos buzz
# at the very ends of it). 90 is 1500 in both, so horns fitted at 90 stay where they are.
SERVO_PULSE = (750, 2250)
SERVO_PULSE_WIDE = (500, 2500)
# The feeder's N20 motor, through the DRV8833 driver: Pi GPIO17 to IN1, GPIO27 to IN2.
FEEDER_PINS = (17, 27)
# How fast the feeder turns (0-1) and how long one push lasts (seconds).
FEEDER_SPEED = 1.0
FEEDER_SECONDS = 0.6

# --- The light bars (lights.py) --------------------------------------------
# 5 V addressable RGB bars (WS2812, "3-pin ARGB"). Their data wire goes to GPIO10 (pin 19),
# the SPI MOSI pin, so SPI has to be on (the Lights page has a button for it). Color,
# brightness, effect and how many LEDs there are are set on the Lights page (/lights).
LIGHTS_SPI = (0, 0)            # /dev/spidev0.0
LIGHTS_SPI_HZ = 6_400_000      # 8 SPI bits for each LED bit, at the LEDs' 800 kHz
LIGHTS_ORDER = "GRB"           # the order WS2812 LEDs take their colors in
LIGHTS_COUNT = 14              # a 14-LED piece of 60 LEDs/m strip behind the fascia slots; set it on the Lights page
# The bars share the 5 V supply with the Pi, servos and feeder, so the app dims them if
# they'd draw more than this (full white is about 60 mA per LED).
LIGHTS_MAX_AMPS = 1.0
