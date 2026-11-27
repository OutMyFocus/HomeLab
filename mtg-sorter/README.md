# SortR: MTG Card Scanner & Sorter

SortR (the app's name) is a machine that looks at your Magic: The Gathering cards, works out which card each one is,
records it in your collection, and drops it into a bin by price.

It has three parts, built in this order:

| Phase | What | Status |
|---|---|---|
| 1. Scanner software | Webcam recognizes cards, saves a collection CSV | **Done (this folder)** |
| 2. Raspberry Pi + camera rig | Same software on a Pi 5 with Camera Module 3 and light bars | **Done** (the Pi can run the same Docker image as the server: [`deploy/PI_DOCKER.md`](deploy/PI_DOCKER.md)) |
| 3. Feeder & sorter, Mk1 | Feeder, scan bed, tilting tray and trapdoors in the enclosure | Built and tested; out of service since its tilting bed broke on 2026-11-09 |
| 4. Sorter Mk2 | Screwless rebuild: slide-in modules, 4 bins, 450-card magazine | Built and run; retired on 2026-11-26 in favour of the Mault sorter. Kept for reference: [`hardware/mk2/MK2.md`](hardware/mk2/MK2.md) |
| 5. Mault sorter | The open Mault design (two modules, 4 bins + end bin), driven by the Pi and SortR with the Mk2's electronics | **Current machine**, being printed: [`hardware/mault/MAULT.md`](hardware/mault/MAULT.md). Servo moves and test buttons are in; full sort runs follow once it is built |

**How it was built:** the week-by-week development log is in [DEVLOG.md](DEVLOG.md).

**On your phone:** open the app's address in Safari or Chrome and pick *Add to Home Screen*
(Safari: the Share button). It gets its own icon and opens full screen like an app, with the
page menu along the bottom.

**Looking after it:** Maintenance, at the bottom of the sidebar on every page (under
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
5. **Tell the printings apart.** A card and its reprint with the same art and frame look
   alike to the fingerprint. For those, the scan is laid over Scryfall's pictures of each
   printing and compared only where they differ (the set symbol, the small print at the
   bottom). The pictures are fetched the first time such a card is seen and kept in
   `data/stock/` (a cache: safe to delete). With `--offline`, or on the sorter's scan bed
   ("Whole cards only"), the fingerprint's choice stands.

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
terminal it's this, but then the app needs a restart to see the new cards (see below):

```bash
python build_db.py --all       # every card: an 80 MB list, then 108,000 small pictures, 30-60 minutes
```

To try it out quickly, fetch a few sets, or just the sets of the cards in your collection:

```bash
python build_db.py --sets dmu,one
python build_db.py --mine
```

When one of these finishes, restart the app (Maintenance → **Restart app**, or `mtg restart`
on the Pi) so the scanner picks up the new cards. The button does that by itself as it goes.

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
  auto-save on, each card is saved as soon as it's recognized. **Proxies** (X) saves every card
  as a proxy while it's on (handy for a proxy deck). Spread the cards out so they
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
- **Home** (`/`, the logo on every page): the whole machine at a glance. The collection's value
  with its best cards fanned out, whether the camera, servo board, feeder and Pi are OK, a value
  chart (7 days, 30 days or all; hover or drag a finger along it for any day), your colors as a
  donut (by value or by cards; tap one to filter the Collection), cards scanned in the last 14
  days, **Insights** (what stands out: how much the value moved, this week against last week,
  how much of the value sits in bin 3, cards whose price jumped, wishlist cards you already
  own), the newest cards, the most valuable ones, the biggest price changes and each bin's cards
  and value. The scanner itself is at `/scan`.
- **Page menu**: on a computer, a sidebar with every page in its group: **Home**, **Scanner**,
  then **Cards** (Collection, Sets, Wishlist, News, Card lookup, Scan history), **Decks** (Decks,
  Play), **Machine** (Machine, Bins, Lights) and **Settings** (Settings, Maintenance). Its
  bottom shows SortR's health (green, or what needs a look) and the light/dark switch; the
  button next to them shrinks it to icons (it does that by itself on a tablet). On a phone it's a
  bar along the bottom: Home, Scanner, Cards, Decks and More. The bar at the top names the page.
- **Search everything** (Ctrl K, ⌘ K on a Mac, the search box at the top, or M on the scanner):
  one box for the cards you own (with their picture and price), every page, and actions like
  Start scanning, Add a card, Export, New deck or Switch light or dark. Anything else you type
  can be looked up in Card lookup. With no camera connected, the scanner says so and offers **Scan photos instead**.
- **Light or dark**: the moon/sun button at the top switches between matching your device,
  dark and light. The scanner's **Customize** (C) still has the rest: accent color, black
  (OLED) theme, bin colors, font, text size and corners. If SortR can't be reached (it's
  restarting, or the Wi-Fi dropped), a red bar says so at the top until it's back.
- **Collection** (in the menu, or **Whole collection**): everything you've ever saved.
  Search and filter by color, rarity, set, bin, foil and price, sort it, and switch between
  pictures, a list and a **binder** (9-pocket pages, two side by side on a computer: turn them
  with the arrows, the arrow keys or a swipe). On a phone the filters fold behind **Filters**;
  each filter shows as a chip you can take off, and the page's address keeps them, so Back or a
  bookmark comes back to the same cards. **Select** (S) ticks several cards to put in the trade
  binder, export or delete together. In a card's details, the arrows (or ← →, or a swipe on
  the picture) go to the next card. Each card also keeps its **condition** (NM to damaged),
  **language**, what you **paid** for each copy (the page then shows what they gained, card by card
  and in total) and **tags** of your own (Binder 2, Cube, To sell...), all in `collection.csv`, with
  filters, sorts and a breakdown for them. With **Select**, **Tag, condition…** changes all the
  picked cards at once. ManaBox imports bring their condition, language and purchase price, and the
  Moxfield, Archidekt, Deckbox and ManaBox exports send them back out. Tap a card to change how many you have, mark it foil, pick a different
  printing or delete it. **Proxy** marks it as a proxy (Select can mark many at once): proxies are
  kept and shown with a PROXY badge, but left out of the value, its charts, the most valuable
  cards, set completion, spares and the wishlist. **Add a card** adds one you didn't scan. It shows the total value,
  how much it changed since you scanned the cards, a value-over-time chart, a breakdown by
  color, rarity, bin and set, and your 10 most valuable cards. Each printing's price is also noted
  once a day (`data/card_prices.json`, about a year kept), so a card's page shows a small price
  chart and how much it moved this week, the list sorts by **Price went up/down most this week**,
  and Home's **Price changes** shows this week's biggest movers. **Refresh prices** gets today's
  Scryfall price for everything. **Export** downloads (or copies) the collection for Moxfield,
  Archidekt, Deckbox, ManaBox, TCGplayer mass entry, a text list, or a
  spreadsheet with prices, either all of it or just the cards your filters show.
  **Sources and imports** (at the bottom) lists where your cards came from. Import a ManaBox
  CSV as its own source, and remove a bad import with all its cards in one step. **For trade**
  on a card puts it in your trade binder.
- **Sets**: how complete each set in the card database is, with a ring and the set's symbol per set. Open a set to
  see every card in collector-number order, the missing ones greyed out, what they'd cost today,
  and a count by rarity. **Add the missing cards to my wishlist** or **Copy the missing list**.
  **Spare copies** lists what you have beyond a playset (or however many you keep), cheapest
  printings first, with their value and a list to copy for a trade or a shop. Basic lands are
  left out unless you ask.
- **News**: Magic news in one place. Articles from the official site (magic.wizards.com) and
  community sites (MTGGoldfish, EDHREC, Hipsters of the Coast; MTG Arena Zone and r/magicTCG can
  be turned on under **Sources**), sets coming out soon or just out (from Scryfall), the newest
  previewed cards, and a red banner when Wizards posts a ban list announcement. Filter by
  Official, Bans, Previews or Arena, or search. The news is fetched every 30 minutes and saved in
  `data/news_cache.json`, so it still shows when the internet is down; `--offline` turns
  fetching off.
- **Decks**: paste a decklist from Moxfield, Archidekt, MTG Arena, MTGO or
  any website. It shows how much of the deck you already own (any printing counts), which cards
  are missing, what they'd cost at today's prices, and which bin your copies are in. **Copy the
  missing cards** gives a shopping list for TCGplayer's Mass Entry or any shop. Save decks to
  check them again later. **Add the missing cards to my wishlist** puts them on your wishlist.
  **Pictures** shows the deck as card pictures, with the cards you still need dimmed and
  marked. Basic lands always count as owned and are never on the shopping list.
  A 60-card deck (40 or more, no commander) gets the deck builder too, with its own checks: deck
  size, sideboard of 15 at most, 4 copies at most, and which formats (Standard, Pioneer, Modern,
  Legacy, Vintage, Pauper) every card is legal in.
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
  **Build a deck from your cards** (top of the Decks page) suggests Commander decks your
  collection can make, best first: for each commander you own, and the most played ones you
  don't, it picks your cards that fit its colors and theme (a creature type like Goblins, go wide
  with tokens, +1/+1 counters, the graveyard...), covers ramp, card draw, removal and board wipes,
  and fills the mana base with your lands and basics. Each idea shows how ready it is to play.
  Filter by style or colors, only commanders you own, or only spare cards (not already in your
  other decks), or type any commander's name. Open one to see the whole list and choose what goes
  in the slots your cards can't fill (EDHREC's picks to get, more lands, or leave them open);
  **Build this deck** saves it and opens it in the deck builder to change anything.
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
- **Bins**: choose what goes into each of the sorter's bins with a rule builder, without
  editing any code. A rule is any mix of conditions (all or any of them, each one can be
  turned around with NOT): price, no price, foil, extra copies beyond the first N, card type
  (lands, tokens, creatures...), words in the type line, color, color identity, number of
  colors, mana value, rarity, set, name, rules text, format legality, the cards in your decks
  or that fit a deck's colors, your wishlist, EDHREC rank and Game Changers. Rules are checked
  from the top; the catch-all bin gets the rest and the cards it can't read. Type, mana value,
  text and formats come from the card list (Settings, Update now). Bin 0 (the original price
  bins' "Unknown price") has no tray and drops into another bin; the page says which. Pick a
  ready-made setup (by price, lands in their own bin, tokens out, lands and tokens out, cards
  for my decks, fits my decks' colors, keep 4 and extras out, by rarity, by color...) or
  write your own rules. The
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
again to get them back). `data/users.json.bak` next to it is a copy from the last save,
which the app uses by itself if `users.json` gets damaged. If neither can be read, the pages
say "users.json is damaged, so nobody can log in" and only the Pi or server itself gets in:
put back `users.json` from a backup, or delete it to turn accounts off.

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

- **Same art, different set.** Reprints that reuse the exact same art and frame differ only
  in small details. The scanner compares those (step 5 above) and gets most of them right,
  not all: double-check the set on cards that matter.
- **Foil glare** can hide the card. Tilt your light or use a diffuser.
- **Low-contrast art** (hazy, pale artwork) under warm lighting can fail to match.
  The camera rig's white LED and fixed card position fix most of this.
- **Non-English cards** aren't in the default database.

---

## Hardware

The parts list is [SHOPPING.md](SHOPPING.md): a Raspberry Pi 5 with Camera Module 3, four
MG90S servos on a PCA9685 servo board (with its own 5 V supply, apart from the Pi's), and the
feeder motor and its driver. The current machine is the Mault sorter: how the same electronics
fit it is in [`hardware/mault/MAULT.md`](hardware/mault/MAULT.md). The machine before it, the
Sorter Mk2, is in [`hardware/mk2/MK2.md`](hardware/mk2/MK2.md).

On the Sorter Mk2 and the first machine, **Machine → Start sorting** feeds each card, scans it,
and drops it into its bin (on the Mault sorter the bin and feed test buttons work; full runs follow) ([`mtgscanner/machine.py`](mtgscanner/machine.py) moves the parts,
[`mtgscanner/sort_run.py`](mtgscanner/sort_run.py) runs the sort).

**Machine → Machine health** (`/machine/health`) shows everything the sorter reports in one
place, live: the Pi's temperature, power and throttling, the camera, where each servo is and
when it last moved (with saved angles outside 10-170° flagged), every feeder pulse and what each
fed card did, the bin-full and bin-in sensors, the lights and power relay, recent scans and
misreads, and the jams and errors since the app started. The same data is JSON at
`/api/machine/health` (`?download=1` saves it as a file). On the server it comes from the Pi
through `MTG_MACHINE_URL` ([`mtgscanner/health.py`](mtgscanner/health.py)).

### Phase 2: camera rig

- Print the scan station in [`hardware/`](hardware/). It holds the Pi camera 12 cm above a white
  card pocket, with LED light from the sides. The card always lands in the same spot, which makes
  recognition very reliable.
- Install Raspberry Pi OS, copy this folder over, and run `scan.py` as-is.

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
