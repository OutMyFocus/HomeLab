# MTG Card Scanner & Sorter

A machine that looks at your Magic: The Gathering cards, works out which card each one is,
records it in your collection, and drops it into a bin by price.

It has three parts, built in this order:

| Phase | What | Status |
|---|---|---|
| 1. Scanner software | Webcam recognizes cards, saves a collection CSV | **Done (this folder)** |
| 2. Raspberry Pi + camera rig | Same software on a Pi, 3D-printed camera stand + light | Stand designed ([`hardware/`](hardware/)) |
| 3. Feeder & sorter | Motors pull one card at a time and push it into the right bin | After that |

**On your phone:** open the app's address in Safari or Chrome and pick *Add to Home Screen*
(Safari: the Share button). It gets its own icon and opens full screen like an app, with the
page menu along the bottom.

**Looking after it:** Maintenance, under the gear in the menu at the top of every page (under
More on a phone), has the health check-up, updates, restart, backups and logs. It gets a yellow or red dot
when something needs a look. What to do when something goes wrong:
[MAINTENANCE.md](MAINTENANCE.md).

## How recognition works (plain English)

1. **Find the card.** The code looks for edges in the camera picture and finds the
   biggest 4-cornered shape shaped like a card.
2. **Straighten it.** It stretches that shape into a flat, upright rectangle, as if
   the card had been scanned on a flatbed scanner.
3. **Fingerprint it.** It shrinks the image and turns it into two 256-bit "perceptual
   hashes", one of the whole card and one of its art. Similar-looking images get similar
   fingerprints, even with blur, glare or different lighting. The art one is what tells
   apart two different cards with the same frame among the 108,000 printings there are.
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

The scanner can only recognize cards that are in its database, so get every card. The
easiest way is the **Download every card** button on the Maintenance page (it runs in the
background, scanning keeps working, and new cards are recognized as they arrive). From a
terminal it's:

```bash
python build_db.py --all       # every card: an 80 MB list, then 108,000 small pictures, 30-60 minutes
```

To try it out quickly, fetch a few sets, or just the sets of the cards in your collection:

```bash
python build_db.py --sets dmu,one
python build_db.py --mine
```

Set codes are the 3-letter codes on Scryfall (for example `mkm`, `blb`, `fdn`, `cmm`). You
can stop any of these and run it again to resume. Run it again later to add new sets and
**refresh prices** for cards you already have; cards fingerprinted by an older version get
the newer fingerprint at the same time.

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
  **Download CSV** for ManaBox or Moxfield.
- **Photos** tab: drag in photos from your computer or phone (one card or a whole table per
  photo) and add the recognized cards to your collection.
- **Camera picker** (top right of the camera view): switch between webcams by name. The app
  remembers your choice for next time.
- **Auto / Slots** (bottom left of the camera view, or S): by default the scanner looks for
  cards anywhere in the picture. In **Slots** mode you drag a box around each card position
  (a tray, an open box, spots marked on the mat) and it looks only there. A card gets its slot's
  number, and a card the detector can't outline, like one sitting in a box, is still read from
  the slot. **Edit slots** to draw more or remove one (the red ×); slots are kept for next time.
- **Wrong card?** (W): pick the right card by name. It's saved instead, and remembered for training.
- **Other printing?** (P): right card, wrong set. Lists every printing of it (Scryfall's full
  list when online) so you can pick the one you really have.
- **Home** (`/`, the logo on every page): the whole machine at a glance. Whether the camera,
  servo board, feeder and Pi are OK, the collection's value and a value chart, cards scanned in
  the last 14 days, the newest cards, the most valuable ones, the biggest price changes and how
  full each bin is. The scanner itself is at `/scan`.
- **Page menu**: the same on every page, and short: **Home**, **Scanner**, then **Cards**
  (Collection, Sets, Wishlist, Card lookup, Scan history), **Decks** (Decks, Play), **Machine**
  (Machine, Bins, Lights) and the gear (Settings, Maintenance), each a small drop-down. Press M
  on the scanner to see every page at once. On a phone it's a bar along the bottom: Home,
  Scanner, Cards, Decks and More. With no camera connected, the scanner says so and offers **Scan photos instead**.
- **Collection** (in the menu, or **Whole collection**): everything you've ever saved.
  Search and filter by color, rarity, set, bin, foil and price, sort it, and switch between
  pictures and a list. Tap a card to change how many you have, mark it foil, pick a different
  printing or delete it. **Add a card** adds one you didn't scan. It shows the total value,
  how much it changed since you scanned the cards, a value-over-time chart, a breakdown by
  color, rarity, bin and set, and your 10 most valuable cards. **Refresh prices** gets today's
  Scryfall price for everything. **Export** downloads (or copies) the collection for Moxfield,
  Archidekt, Deckbox, ManaBox, TCGplayer mass entry, a text list, or a
  spreadsheet with prices, either all of it or just the cards your filters show.
  **Sources and imports** (at the bottom) lists where your cards came from. Import a ManaBox
  CSV as its own source, and remove a bad import with all its cards in one step. **For trade**
  on a card puts it in your trade binder.
- **Sets**: how complete each set in the card database is, with a ring per set. Open a set to
  see every card in collector-number order, the missing ones greyed out, what they'd cost today,
  and a count by rarity. **Add the missing cards to my wishlist** or **Copy the missing list**.
  **Spare copies** lists what you have beyond a playset (or however many you keep), cheapest
  printings first, with their value and a list to copy for a trade or a shop. Basic lands are
  left out unless you ask.
- **Decks**: paste a decklist from Moxfield, Archidekt, MTG Arena, MTGO or
  any website. It shows how much of the deck you already own (any printing counts), which cards
  are missing, what they'd cost at today's prices, and which bin your copies are in. **Copy the
  missing cards** gives a shopping list for TCGplayer's Mass Entry or any shop. Save decks to
  check them again later. **Add the missing cards to my wishlist** puts them on your wishlist.
  A Commander deck (one with a `Commander` line, or 90+ cards) also gets the deck builder:
  deck checks (size, singleton, color identity, lands, ramp, draw, removal), the mana curve,
  Canadian prices, which cards you own, need to buy or proxy, suggestions that fit, a playtest
  hand, a game guide when there is one, and **Copy shopping list**.
  Its **Upgrade path** shows how to make the deck the best version of itself, in four steps
  from the fewest swaps to the most (3, then 7, 10 and 20 more). Each swap names the card to
  cut and the card to add, why, and its Canadian price; cards you already own are free and come
  sooner. It compares the deck with what EDHREC's decks for the same commander play (kept on the
  Pi for a week, in data/edhrec/), or with the most played Commander cards when EDHREC can't be
  reached. Set a most-per-card budget, keep Game Changers out, and press **Swap** or **Make
  these swaps** to change the deck.
- **Card lookup**: search every Commander card (the whole database is on the Pi, so it's
  instant), by name, text, type, color or set and number. Filter by role (ramp, draw, removal…),
  see a card's prices at each Canadian store, every printing, how many you own, which of your
  decks it fits, and add it to a deck or your wishlist.
- **Play**: a life counter for the table (life, poison, commander damage, dice and a coin),
  and a games log with win rates by player and by deck.
- **Wishlist**: cards you want, with the most you'd pay. It shows today's price, marks the ones
  at or under your price, and the ones you've already scanned. When a wishlist card is scanned,
  the scanner page shows a pink banner and chimes. **Copy the ones I still need** gives a
  shopping list. Below it, the **trade binder**: cards you'd trade away, with their value, and
  **Copy my trade binder** to send to a friend.
- **History**: every scanning session (cards saved within half an hour of each other), with a
  chart of cards scanned per day for the last 30 days, your biggest session and best find. Open a
  session to see its cards, download just that session for ManaBox or Moxfield, or remove
  a session you scanned by mistake.
- **Settings**: the valuable-card alert (a banner and chime on the scanner page when a card
  worth at least $20, or whatever you choose, is saved), the wishlist alert, the sound, and the
  **PIN lock**. With a PIN set, other phones and laptops have to type it before they can see or
  change anything, and they stay unlocked for 30 days. The Pi itself is never locked out.
  Forgot the PIN? On the Pi, delete `data/pin.json`.
  **Prices and card data** shows when the weekly Canadian price check and card database update
  last ran, with buttons to run them now. **Bring in Commander Vault** imports everything from
  a Commander Vault export file (see below).
- **Bins**: choose what goes into each of the sorter's 4 bins, by price, color,
  rarity, set and foil, without editing any code. Pick a ready-made setup (by price, by rarity,
  by color, keep the good stuff, pull valuable then by color) or write your own rules. The
  counts show how your collection would be split before you save. Saved in
  `data/sort_rules.json`; **Back to the original price bins** undoes it.
- **Train** tab: teach the scanner from your own scans (see below).
- **Machine**: move each servo and the feeder by hand, and save the angles that work.
- **Maintenance**: the Pi's health, updates, restart and shut down, Wi-Fi,
  backups and logs. See [MAINTENANCE.md](MAINTENANCE.md).
- **Customize** (the sliders button, or C): light/dark/black theme, accent color, bin colors,
  layout, spacing, font and which details to show. Saved in your browser, and used by every
  page. Settings has a button for it too.

No webcam yet? `python app.py --demo path/to/photos` pretends the photos are a camera.
On the Raspberry Pi, run `python app.py --host 0.0.0.0` and open `http://<the Pi's address>:5000`
from your laptop or phone.

**Scan with your phone's camera.** On the Scan page, the camera menu has **This device's
camera**: the phone (or laptop) you're holding gets a scanner of its own, next to the
machine's, and its cards go into the same collection with your name (typed under
**Scanning as**) in the Source column. Several phones can scan at once. Browsers only allow
the camera on an https address, such as the Tailscale one
([deploy/REMOTE_ACCESS.md](deploy/REMOTE_ACCESS.md)).

**On a home server** (Unraid, or any Docker host): the app comes as a Docker image,
`ghcr.io/outmyfocus/mtg-sorter`, so every device at home shares one collection without the Pi
being on. Setup: [deploy/UNRAID.md](deploy/UNRAID.md).

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

## Accounts: everyone has their own cards

Settings, **Accounts**, Turn on accounts. You become the owner: an admin with every
permission, and every card, deck, wishlist and trade already in the app stays yours
(nothing is moved; a backup is saved in `data/backups/` first). From then on everyone
logs in, and the login replaces the PIN lock.

Add people under **People and permissions**, or make an **invite link** there (for one person, or up to 5 or 20; it runs out after 1, 7 or 30 days) and text it to them: they pick their own username and password and join as a member or viewer. Only a hash of each link is kept, so copy it when it's shown. Each person gets their own collection,
decks, wishlist, alerts, trade binder, games and value history (in `data/users/<username>/`),
and scans from their phone land in their own collection. Pick a role or tick permissions:

| Permission | Lets them |
|---|---|
| Scan | scan into their own collection with their phone's camera or photos |
| Edit | change their own collection, decks, wishlist, trades and games |
| Machine | run the sorting machine (Machine, Lights, Bins, the machine's camera, training); the machine saves into the cards of whoever is using it |
| Admin | everything, plus Maintenance, price checks and the accounts |

Member = Scan + Edit, Viewer = look only. The card database, prices, bins and the machine
are shared. Requests from the Pi or server itself always count as the owner. Locked out?
Delete `data/users.json` and the login is gone (everyone's cards stay; turn accounts on
again to get them back).

## Commander Vault is part of the app now

Everything Commander Vault did lives here: collection sources, decks with the deck builder,
card lookup, the wishlist, the trade binder, games and the weekly Canadian prices. To move
your Vault data over once, export it from the Vault, then on the **Settings** page under
**Bring in Commander Vault** pick the file and press **Import**. Each Vault collection batch
becomes its own source on the Collection page, decks keep their guides, and the latest
prices come along so you don't wait for the first weekly check. Anything already brought in is
skipped, so importing twice is safe.

Cards come in through `data/collection.csv`, which uses ManaBox's column names (`Name`,
`Quantity`, `Set code`, `Collector number`, `Foil`, plus `Source`). ManaBox and Moxfield can
read it directly.

## Price bins (CAD)

Set the bins on the **Bins** page. Until you save rules there, the bins are `PRICE_BINS`
in `mtgscanner/config.py`. Defaults:

| Bin | Cards |
|---|---|
| 3 | $10 and up |
| 2 | $1 – $10 |
| 1 | Bulk, under $1 |
| 0 | No price known (most tokens) |

### Canadian prices

Once a week the app checks the Near Mint price of every card in your collection, decks,
wishlist and trade binder at Face to Face Games (the main price), then 401 Games, The Mythic
Store, Hobbiesville, Card Brawlers and L'Univers de la Carte, and saves them in `data/vault_prices.json`. Valuable cards (foils,
special numbers, $1.50 and up) also get their exact printing's price. The same week it
updates the Commander card database (`data/carddb.json`, from Scryfall's bulk data) that Card
lookup and the deck builder use. **Settings, Prices and card data** runs either one now. Cards
the stores haven't priced fall
back to Scryfall's USD price, converted with the Bank of Canada's exchange rate for the
day. While the app runs it also checks Scryfall for today's price of each card it
recognizes (start it with `--offline` to skip that and use the database's prices). The rate is fetched once a day and saved in `data/usd_cad.json`. Offline, it uses the
last saved rate, or `USD_TO_CAD` in `config.py`. The `data/` folder is never committed, so
your prices stay on your computer.

### Montreal prices

When the scanner recognizes a card, the card panel shows what it costs in Montreal today:
Face to Face Games first, then Card Brawlers and L'Univers de la Carte. Each store's price
is for that exact printing when the store has it ("this printing"), otherwise its cheapest
copy ("cheapest"), and each one links to the store's page. Answers are kept for 12 hours.
The Collection has a **Montreal** column (Face to Face Games' price, or the next Montreal
store's) from the weekly price check, and each card's details list every Montreal store.

Carta Magica and L'Expédition run on Crystal Commerce, which refuses automated requests, and
Le Valet d'Coeur sits behind a bot check, so the app can't read their prices. The card panel
links to a search for the card on each of those sites instead. See `mtgscanner/montreal.py`.

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

### RGB light bars (optional)

The app can drive 5 V addressable RGB bars (WS2812, sold as "3-pin ARGB" for PC cases)
from the **Lights** page (`/lights`): on/off, color, brightness, effects (solid, breathe,
rainbow, sweep), and a short flash when a card is saved, valuable or on your wishlist,
unsure, or not recognized. The page shows a live preview, so it works on a PC too.

Wiring, in short (the Lights page has the full notes):

- **5V** and **GND** from the bars to the 5 V supply. **Never 12 V.**
- **Data** to **GPIO10, pin 19** on the Pi (the SPI MOSI pin). The bars and the Pi share a ground.
- SPI has to be on: press **Turn SPI on** on the Lights page (or run `deploy/setup.sh`), then reboot.

Full white is about 60 mA per LED, so the app dims the bars to stay under 1 A
(`LIGHTS_MAX_AMPS` in `mtgscanner/config.py`) and starts at 30% brightness. The Pi 5 can't
use the usual `rpi_ws281x` library, so the colors go out over SPI with no extra package.
