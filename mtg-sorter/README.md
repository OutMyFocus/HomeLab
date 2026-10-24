# MTG Card Scanner & Sorter

A machine that looks at your Magic: The Gathering cards, works out which card each one is,
records it in your collection, and drops it into a bin by price.

It has three parts, built in this order:

| Phase | What | Status |
|---|---|---|
| 1. Scanner software | Webcam recognizes cards, saves a collection CSV | **Done (this folder)** |
| 2. Raspberry Pi + camera rig | Same software on a Pi, 3D-printed camera stand + light | Stand designed ([`hardware/`](hardware/)) |
| 3. Feeder & sorter | Motors pull one card at a time and push it into the right bin | After that |

## How recognition works (plain English)

1. **Find the card.** The code looks for edges in the camera picture and finds the
   biggest 4-cornered shape shaped like a card.
2. **Straighten it.** It stretches that shape into a flat, upright rectangle, as if
   the card had been scanned on a flatbed scanner.
3. **Fingerprint it.** It shrinks the image and turns it into a 256-bit "perceptual
   hash". Similar-looking images get similar fingerprints, even with blur or different lighting.
4. **Look it up.** `build_db.py` already downloaded every card image from
   [Scryfall](https://scryfall.com) and fingerprinted it. The scanner finds the closest
   fingerprint. That gives the card name, set, collector number and price.

## Setup (once)

You need [Python 3.11 or newer](https://www.python.org/downloads/). In a terminal, from this folder:

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# Mac / Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

## Build the card database

Start small to try it out. This fetches two sets and takes under a minute:

```bash
python build_db.py --sets dmu,one
```

Set codes are the 3-letter codes on Scryfall (for example `mkm`, `blb`, `fdn`, `cmm`). When
you're happy, fetch every card. It takes a few hours, and you can stop it and run it again
to resume:

```bash
python build_db.py --all
```

Run the same command again later to **refresh prices** for cards you already have.

## Scan cards with the app (easiest)

```bash
python app.py
```

Then open **http://localhost:5000** in your browser. You get:

- **Live** tab: the camera with the card outlined, the recognized card's picture, its
  price (CAD) and which bin it goes in. Press **Save card** (or Space). **Foil** (F) and
  **Auto-save** (A) are toggles: with auto-save on, just swap cards and it saves each one.
- **This session**: every card you've saved, with totals per bin, **Undo last**, and
  **Download CSV** to import into Commander Vault.
- **Photos** tab: drag in photos from your computer or phone (one card per photo) and add
  the recognized cards to your collection.
- **Wrong printing?** Reprints often share the same art, so the camera can land on the
  wrong set (and the wrong price). Click **Wrong printing?** under the card to see every
  printing with its price and pick the one in your hand. If the card was already saved,
  its row is switched. A card the scanner doesn't recognize at all can be looked up with
  **Find a card by name**.

Prices are looked up live: today's Scryfall price, converted at the Bank of Canada's
rate for the day (shown at the top of the page). Recognition itself never needs the
internet. Without a connection, or with `python app.py --offline`, the app uses the
prices saved when you ran `build_db.py` and the fixed `USD_TO_CAD` rate.

No webcam yet? `python app.py --demo path/to/photos` pretends the photos are a camera.
On the Raspberry Pi, run `python app.py --host 0.0.0.0` and open `http://<the Pi's address>:5000`
from your laptop or phone.
To start it on boot and open it from anywhere (Tailscale, or your own domain through
Cloudflare), see [`deploy/REMOTE_ACCESS.md`](deploy/REMOTE_ACCESS.md).

## Scan cards from the command line

```bash
python scan.py
```

Put the card on a **plain, light-colored background** (white paper is perfect, since most
cards have black borders) with even, white light. It also works on a wood table, but
less reliably, especially under warm yellow bulbs. The outline turns green once the card is recognized.

| Key | Does |
|---|---|
| `SPACE` | Save the recognized card to `data/collection.csv` |
| `F` | Toggle foil (uses the foil price) |
| `A` | Auto-save: saves each new card as soon as it's recognized. Swap cards and go. |
| `Q` | Quit |

No webcam yet? Scan photos from your phone instead:

```bash
python scan.py --image card1.jpg card2.jpg --save
```

## Importing into Commander Vault

`data/collection.csv` uses ManaBox's column names (`Name`, `Quantity`, `Set code`,
`Collector number`, `Foil`). Go to Commander Vault, open **Collection**, choose
**Import a ManaBox CSV**, pick the file, and give the batch a name like "Scanner, Oct 21". Each
import becomes its own source, so you can remove a bad session in one step. After
importing, rename or delete `collection.csv` so the next session starts fresh.

## Price bins (CAD)

Edit `PRICE_BINS` in `mtgscanner/config.py`. Defaults:

| Bin | Cards |
|---|---|
| 3 | $10 and up |
| 2 | $1 – $10 |
| 1 | Bulk, under $1 |
| 0 | No price known (most tokens) |

If a card has no price in the finish you picked (a foil-only promo with Foil off, or an
etched foil), the price of its other finish is used and the price source says so.
The CSV's `Bin number` column holds the bin, for the sorter.

### Prices from Commander Vault

The scanner can use the same weekly Canadian Near Mint prices that Commander Vault
collects (Face to Face Games, then 401 Games, The Mythic Store and Hobbiesville). In the
Vault, open **Collection** and press **Save prices for scanner**. Put the saved
`vault_prices.json` in this folder's `data/` folder, and the scanner picks it up automatically.
Prices update weekly, so save a fresh copy now and then. It
uses the exact printing's price when the Vault has one. Cards the Vault hasn't priced fall
back to Scryfall's USD price, converted to CAD. The `data/` folder is never committed,
so your prices stay on your computer.

## Run the tests

```bash
pytest
```

## Known limits (for now)

- **Same art, different set.** Reprints that reuse the exact same art and frame can look
  identical to the camera. The scanner picks one of them, so double-check the set on cards that matter.
- **Foil glare** can hide the card. Tilt your light or use a diffuser.
- **Low-contrast art** (hazy, pale artwork) under warm lighting can fail to match.
  The camera rig's white LED and fixed card position fix most of this.
- **Non-English cards** aren't in the default database.

---

## Hardware roadmap

### Shopping list (about $150–200 CAD to start)

| Part | Why | Approx. |
|---|---|---|
| Raspberry Pi 5 (4 GB) + power supply + 32 GB microSD | The brain. Runs this exact code | $110 |
| Raspberry Pi Camera Module 3 + Pi 5 camera cable (300 mm) | Sharp, autofocus. The Pi 5 needs its own cable | $40 |
| Small LED strip or ring light (5 V) | Even lighting is the #1 factor in accuracy | $10 |
| 2× SG90 / MG90S servos | Bin selector + card pusher | $10 |
| 1× N20 gear motor + rubber wheel, or a 28BYJ-48 stepper + ULN2003 board | Feeder that pulls one card off the stack | $8 |
| Jumper wires, small breadboard | Connections | $10 |
| PLA filament | Printed frame, hopper, bins | (you have a printer) |

### Phase 2: camera rig

- Print the scan station in [`hardware/`](hardware/). It holds the Pi camera 12 cm above a white
  card pocket, with LED light from the sides. The card always lands in the same spot, which makes
  recognition very reliable.
- Install Raspberry Pi OS, copy this folder over, and run `scan.py` as-is.

### Phase 3: feeder and sorter

The usual design people build:

1. **Hopper.** Cards stack face-up in a printed tray.
2. **Feeder.** A rubber wheel touches the top card and spins briefly to push one card out
   through a slot that's only one card thick, so only one gets through.
3. **Camera bay.** The card stops under the camera and the scanner recognizes it.
4. **Sorter.** A servo turns a printed chute, or a "gate" arm, toward bin 0–3, then a
   second wheel or a tilt drops the card in.

When you get there, the code change is small. Where `scan.py` saves a card, it will also
call a `send_to_bin(bin_number)` function that moves the servos with the
[`gpiozero`](https://gpiozero.readthedocs.io) library.
