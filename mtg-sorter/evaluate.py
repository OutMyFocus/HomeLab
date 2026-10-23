"""How well does recognition do on the scans you collected?

    python evaluate.py           # summary
    python evaluate.py --list    # also list every card it gets wrong
    python evaluate.py --plain   # without what the Train tab taught it, to compare

Turn on "Collect scans" in app.py and scan normally. Every card you Save tells the
scanner it was right, and every card you correct tells it the right answer. This script
runs the *current* recognition code over each of those card pictures, so after changing
the code (or config.py) you can see whether it got better or worse.

Scans the scanner auto-saved on its own are NOT counted as truth (they're its guesses),
unless you pass --include-auto. You can also give it your own answers: a CSV file
data/captures/labels.csv with columns  crop,name  (the crop file name from log.csv and
the card's printed name) counts as truth too, by name.

Scans you've trained on will match themselves, so compare against --plain to see
what training adds, and judge code changes with --plain.
"""

import argparse
import csv
import statistics
from collections import Counter

import cv2

from mtgscanner import config
from mtgscanner.captures import CaptureLog, true_card
from mtgscanner.database import Matcher, _name_key, connect
from mtgscanner.recognize import identify_crop

LABELS_CSV = config.CAPTURES_DIR / "labels.csv"


def load_labels() -> dict[str, str]:
    """crop -> card name, from data/captures/labels.csv (optional)."""
    if not LABELS_CSV.exists():
        return {}
    with LABELS_CSV.open(newline="", encoding="utf-8") as f:
        return {r["crop"]: r["name"] for r in csv.DictReader(f) if r.get("crop") and r.get("name")}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="list each scan it gets wrong")
    parser.add_argument("--plain", action="store_true", help="leave out the fingerprints learned in the Train tab")
    parser.add_argument("--include-auto", action="store_true", help="also trust scans Auto-save stored unchecked")
    args = parser.parse_args()

    log = config.CAPTURES_DIR / "log.csv"
    if not log.exists():
        raise SystemExit('No scans collected yet. Turn on "Collect scans" in app.py first.')
    rows = CaptureLog(config.CAPTURES_DIR).rows()
    labels = load_labels()
    matcher = Matcher(connect(config.DB_PATH))
    if args.plain:     # learned fingerprints come after the cards
        ids, hashes, names = matcher._table
        n = matcher.card_count
        matcher._table = ids[:n], hashes[:n], names[:n]
        matcher.learned_count = 0

    # What each scan really shows: your own answers first, then what you saved or corrected.
    truth: dict[str, tuple[str, str]] = {}      # crop -> (kind, value): ("name", name) or ("id", card id)
    for row in rows:
        if row["verdict"] == "ignore":
            continue
        if row["crop"] in labels:
            truth[row["crop"]] = ("name", labels[row["crop"]])
        elif (card_id := true_card(row, include_auto=args.include_auto)):
            truth[row["crop"]] = ("id", card_id)

    right, wrong, unknown = [], [], []
    by_conf = {c: Counter() for c in ("sure", "likely", "unsure")}
    problems = []
    for row in rows:
        if row["crop"] not in truth:
            continue
        img = cv2.imread(str(config.CAPTURES_DIR / row["crop"]))
        if img is None:
            continue
        kind, value = truth[row["crop"]]
        m = identify_crop(matcher, img)
        if kind == "id":
            real = matcher.get_card(value)
            ok = m.card is not None and _name_key(m.card.name) == _name_key(real.name)
            real_text = f"{real.name} ({real.set_code.upper()})"
        else:
            ok = m.card is not None and _name_key(m.card.name) == _name_key(value)
            real_text = value
        if m.card is None:
            unknown.append(m.distance)
            problems.append(f"  {row['crop']}: is {real_text}, found nothing (closest {m.distance}, margin {m.margin})")
            continue
        (right if ok else wrong).append(m)
        by_conf[m.confidence][ok] += 1
        if not ok:
            problems.append(f"  {row['crop']}: is {real_text}, says {m.card.name} ({m.card.set_code.upper()}) "
                            f"distance {m.distance}, margin {m.margin}, {m.confidence}")

    total = len(right) + len(wrong) + len(unknown)
    print(f"{len(rows)} scans collected, {total} with a known answer"
          + (f" ({len(labels)} from labels.csv)" if labels else "")
          + (" (auto-saved guesses trusted)" if args.include_auto else ""))
    print("Using the plain card database.\n" if args.plain else f"Using {matcher.learned_count} learned scans too (try --plain to compare).\n")
    if not total:
        print("Nothing to score yet: save or correct some cards while collecting, or add data/captures/labels.csv.")
        return
    print(f"Right: {len(right)} of {total} ({100 * len(right) / total:.0f}%)   wrong: {len(wrong)}   not recognized: {len(unknown)}")
    locked = by_conf["sure"] + by_conf["likely"]
    if sum(locked.values()):
        print(f"Of the cards it would save on its own (sure + likely): {100 * locked[True] / sum(locked.values()):.0f}% right "
              f"({locked[False]} wrong)")
    for conf in ("sure", "likely", "unsure"):
        c = by_conf[conf]
        if sum(c.values()):
            print(f"  {conf:6}: {c[True]:4} right, {c[False]:3} wrong")

    print(f"\nMatch distance (lower is closer). Cards count as recognized up to {config.MAX_MATCH_DISTANCE}.")
    if right:
        print(f"  right: typical {statistics.median(m.distance for m in right):.0f}, worst {max(m.distance for m in right)}, "
              f"typical margin {statistics.median(m.margin for m in right):.0f}")
    if wrong:
        print(f"  wrong: best {min(m.distance for m in wrong)}, typical {statistics.median(m.distance for m in wrong):.0f}, "
              f"typical margin {statistics.median(m.margin for m in wrong):.0f}")

    if problems and args.list:
        print("\nScans it gets wrong (pictures are in data/captures):")
        print("\n".join(problems))
    elif problems:
        print(f"\n{len(problems)} scans are wrong or unrecognized. Run with --list to see them.")


if __name__ == "__main__":
    main()
