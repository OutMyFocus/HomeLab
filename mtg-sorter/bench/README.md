# Scanner test bench

Measures how well the scanner reads cards, on fake photos made from Scryfall's
own card pictures, so a change can be scored before it goes on the sorter.

```
pip install -r requirements.txt
python bench/prepare.py          # once: card list, ~108,000 small pictures, the card database (a few hours)
python bench/bench.py phone 200  # 200 cards x 7 phone scenes
python bench/bench.py machine 200 --split test
```

Everything it downloads goes in `bench/cache/`, which git ignores.

## Scenes

| Phone (`phone`) | What the picture looks like |
|---|---|
| `table` | card on a table: white, grey, black, wood, felt, playmat or a cluttered desk |
| `thumb` | held in the hand, a thumb over one edge |
| `glare` | a bright light shining off the card |
| `foil` | foil rainbow sheen plus glare |
| `sleeve` | in a sleeve, with its shine |
| `dim` | a dark room, noisy picture |
| `far` | card small in the picture |

| Sorter (`machine`) | |
|---|---|
| `bed` | card on the black scan bed |
| `bed_bars` | glare stripes from the light bars |
| `bed_foil` | a foil under the bars |
| `bed_dim` | lights low |
| `bed_white` | the white bed |

`none_phone` and `none_bed` are photos with no card: anything read there is a mistake.
`--split backs` uses the back faces of double-faced cards.

## Splits

`dev` (1000 cards) is for trying ideas. `test` (2000 other cards) is only for the
final score, so the score isn't tuned to the cards it is measured on. About one in
five picked cards is a harder kind on purpose: borderless, showcase, extended art,
full art, old frames, double-faced, split and adventure cards.

## Reading the table

* **sure+right**: read as the right card and sure (the sorter acts on these).
* **right**: the right card at any confidence.
* **printing**: the exact printing (set and number), which sets the price.
* **WRONG**: a different card read as sure or likely. This should stay 0.
* **ms**: time for one picture on this computer (the Pi 5 is about 2 to 3 times slower).

To compare with older code, check it out somewhere and pass `--repo path/to/that/mtg-sorter`.
