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

- **Live** tab: point the camera at a table with as many cards as you like. Every card gets
  a number on the picture and a row in **On the table**, with its price (CAD) and bin. Click a
  row to see that card big. **Save all** (Space) saves every recognized card, or save them one
  at a time with the check button. **Foil** (F) and **Auto-save** (A) are toggles: with
  auto-save on, each card is saved as soon as it's recognized. Spread the cards out so they
  don't overlap. Cards in a pile or cut off at the edge of the picture can't be read.
- **This session**: every card you've saved, with totals per bin, **Undo last**, and
  **Download CSV** to import into Commander Vault.
- **Photos** tab: drag in photos from your computer or phone (one card or a whole table per
  photo) and add the recognized cards to your collection.
- **Camera picker** (top right of the camera view): switch between webcams by name. The app
  remembers your choice for next time.
- **Wrong card?** (W): pick the right card by name. It's saved instead, and remembered for training.
- **Train** tab: teach the scanner from your own scans (see below).
- **Customize** (the sliders button, or C): light/dark/black theme, accent color, bin colors,
  layout, spacing, font and which details to show. Saved in your browser.

No webcam yet? `python app.py --demo path/to/photos` pretends the photos are a camera.
On the Raspberry Pi, run `python app.py --host 0.0.0.0` and open `http://<the Pi's address>:5000`
from your laptop or phone.

## Teach the scanner (Train tab)

Out of the box the scanner knows each card from one clean Scryfall picture. Your camera,
lighting and sleeves make cards look different, so it gets better when it learns from your scans:

1. **Collect.** Turn on **Collect scans** (R). Each card you put down is kept once in
   `data/captures/`: the straightened card, the whole camera picture, and what it guessed.
2. **Confirm.** Saving a card tells it the guess was right. When it's wrong, press
   **Wrong card?** and pick the right one. In the Train tab you can also label scans it
   didn't recognize, confirm guesses, or skip bad pictures.
3. **Train.** With **Keep learning** on (the default), each card you save or correct is
   learned as soon as you take it away. **Train now** catches up on everything else, such as
   scans you labeled in the Train tab. Each confirmed scan becomes an extra fingerprint for its
   card, so that card, and other copies of it, match much more closely from then on.
   **Forget all training** undoes it. It never learns from guesses you didn't check, so its
   mistakes don't become habits.

To measure how recognition is doing (for example after changing `config.py` or the code):

```bash
python evaluate.py --list    # with what it learned
python evaluate.py --plain   # the stock database only, to compare
```

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

### Prices from Commander Vault

The scanner can use the same weekly Canadian Near Mint prices that Commander Vault
collects (Face to Face Games, then 401 Games, The Mythic Store and Hobbiesville). In the
Vault, open **Collection** and press **Save prices for scanner**. Put the saved
`vault_prices.json` in this folder's `data/` folder, and the scanner picks it up automatically.
Prices update weekly, so save a fresh copy now and then. It
uses the exact printing's price when the Vault has one. Cards the Vault hasn't priced fall
back to Scryfall's USD price, converted with the Bank of Canada's exchange rate for the
day. The rate is fetched once a day and saved in `data/usd_cad.json`. Offline, it uses the
last saved rate, or `USD_TO_CAD` in `config.py`. The `data/` folder is never committed, so
your prices stay on your computer.

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
