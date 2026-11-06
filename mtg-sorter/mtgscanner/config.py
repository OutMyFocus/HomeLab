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
# fitted. Find them on the Machine page (/machine) and press Save there. Saved angles
# live in data/machine_settings.json (kept through updates, restarts, the switch to Docker,
# and in backups) and win over these, so there's no need to edit this file on the Pi
# (which would stop automatic updates). The numbers below are Nic's own calibration from
# 2026-11-05, so the machine still has them if that file is ever lost or reset.
# Seconds a servo keeps holding after a move before it lets go (0 = hold until told).
# Holding against something it can't push past makes a servo hot.
SERVO_HOLD_SECONDS = 1.5
# The parts in SERVO_KEEP_HOLDING (below) keep holding, but even they let go after this many seconds with no new
# move, so a part jammed against a stop can't burn out its servo (0 = hold forever).
SERVO_HOLD_LIMIT = 30
# Parts that keep holding after a move, because they fall back on their own if let go:
# the stop gate drops under its own weight, and it has to stand firm against the card the
# feeder pushes into it. The chute v3 trapdoors hang from hinges at their outer edges, so
# they sag open if their servos let go (set "closed" a hair short of the door's stop, so the
# servo isn't pushing against it: hardware/CHUTE_V3.md).
SERVO_KEEP_HOLDING = ("pins", "door_r", "door_l")

SERVOS = {
    # part: (PCA9685 channel, {position: angle})        Nic's calibration, 2026-11-05
    "pins":   (0, {"up": 120, "down": 180}),                 # stop pins: up stops the card
    "chute":  (1, {"centre": 40, "left": 70, "right": 20}),   # tilts the tray to bin 1 or 3
    # chute v3 doors turn 95 degrees through a crank and link (needs Wider servo travel on)
    "door_r": (2, {"closed": 180, "open": 70}),               # right trapdoor (bin 2)
    "door_l": (3, {"closed": 69, "open": 180}),               # left trapdoor (bin 2)
}
# Where each part goes when the app starts (and on the Machine page's Home button), in
# this order: doors shut first so the tray can level out, then the gate up ready for a
# card. Saved angles are used. Turn it off on the Machine page.
SERVO_HOME = {"door_r": "closed", "door_l": "closed", "chute": "centre", "pins": "up"}
HOME_AT_STARTUP = True
SERVO_HOME_SPEED = 60          # degrees a second when homing: a slow sweep, not a jump
# Servo pulse widths in microseconds for 0 and 180 degrees. The first is ServoKit's
# default, which turns an MG90S only about 130-140 real degrees. "Wider servo travel" on
# the Machine page switches to the second for about the full 180 (some cheap servos buzz
# at the very ends of it). 90 is 1500 in both, so horns fitted at 90 stay where they are.
SERVO_PULSE = (750, 2250)
SERVO_PULSE_WIDE = (500, 2500)
SERVO_WIDE_TRAVEL = True       # until the Machine page's switch is saved (the angles above need it)
# The feeder's N20 motor, through the DRV8833 driver: Pi GPIO17 to IN1, GPIO27 to IN2.
FEEDER_PINS = (17, 27)
# How fast the feeder turns (0-1) and how long one push lasts (seconds).
FEEDER_SPEED = 1.0
FEEDER_SECONDS = 1.2
# "Feed one card" on the Machine page runs the motor while watching the camera, and stops
# it the moment a card lands in this box: [x0, y0, x1, y1] as shares of the camera picture
# (after Rotate and Crop), a band across the bed just above the stop teeth. Set it on the
# Machine page; this is only the starting guess. See mtgscanner/feed_watch.py.
FEED_ZONE = (0.2, 0.62, 0.8, 0.70)
FEED_LAND_SHARE = 0.25       # this much of the box looking different = a card is there
FEED_DIFF_LEVEL = 30         # grey levels (0-255) a pixel must change by to count
FEED_MAX_SECONDS = 3.0       # give up (motor off) if no card has landed by then
FEED_SETTLE_SECONDS = 0.8    # then wait this long to see where it came to rest
# After a card lands, the wheels turn backwards this long: the next card, which they drove
# part way out of the slot behind the first (they touch it as soon as the first card's tail
# passes them), goes back into the hopper instead of hanging over the landed card and
# pinning it on the bed. Seen in the 2026-11-05 camera tests. 0 turns it off.
FEED_BACKOFF_SECONDS = 0.25
# Dropping a landed card into a bin (Machine.drop, the Machine page's "Sort to bin" buttons,
# and POST /api/machine/sort_one, which feeds a card first). Bins 1 and 3 are the tilted
# tray's sides; bin 2 is under the trapdoors. The stop pins drop first and the card slides
# onto the level tray (1-2 s, up to 4 s for a foil, 2026-11-06 camera tests), so the pins
# stay down SORT_PINS_SECONDS; then the doors open, or the chute tilts to the side for
# SORT_TILT_SECONDS. The chute is sent its angle again every second so it doesn't sag.
SORT_BINS = {1: "left", 2: "centre", 3: "right"}   # bin number: chute position
SORT_DOOR_BIN = 2             # the bin under the trapdoors
SORT_PINS_SECONDS = 3.0       # pins down this long before the doors open / the tilt goes on
SORT_DOORS_SECONDS = 2.5      # trapdoors open this long
SORT_TILT_SECONDS = 2.0       # bins 1 and 3: tilted this long for the card to slide off
SORT_RETRIES = 1              # drop again this many times if the camera still sees the card
# After a drop, the card counts as gone when less than this share of the picture
# (SORT_CHECK_ZONE, shares like FEED_ZONE: nearly the whole view, slot to tray) still looks
# different from the empty bed before the feed. A card is about a tenth of the view, so a
# card the pins pushed up or turned stays well above this, which the landing band missed.
SORT_CHECK_ZONE = (0.05, 0.05, 0.95, 0.95)
SORT_GONE_SHARE = 0.05

# --- The light bars (lights.py) --------------------------------------------
# 5 V addressable RGB bars (WS2812, "3-pin ARGB"). Their data wire goes to GPIO10 (pin 19),
# the SPI MOSI pin, so SPI has to be on (the Lights page has a button for it). Color,
# brightness, effect and how many LEDs there are are set on the Lights page (/lights).
LIGHTS_SPI = (0, 0)            # /dev/spidev0.0
LIGHTS_SPI_HZ = 6_400_000      # 8 SPI bits for each LED bit, at the LEDs' 800 kHz
LIGHTS_ORDER = "GRB"           # the order WS2812 LEDs take their colors in
LIGHTS_COUNT = 14              # a 14-LED piece of 60 LEDs/m strip behind the fascia slots; set it on the Lights page
# The card light: LEDs chained after the status lights, 5 in each scan bed wall's groove.
# They stay one steady color (white) for the camera and never flash. Set on the Lights page.
LIGHTS_CARD_COUNT = 10
LIGHTS_CARD_BRIGHTNESS = 60    # percent
# The bars share the 5 V supply with the Pi, servos and feeder, so the app dims them if
# they'd draw more than this (full white is about 60 mA per LED).
LIGHTS_MAX_AMPS = 1.0
