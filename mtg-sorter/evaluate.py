"""How well does recognition do on the scans you collected?

    python evaluate.py           # summary
    python evaluate.py --list    # also list every card it gets wrong
    python evaluate.py --plain   # without what the Train tab taught it, to compare

Turn on "Collect scans" in app.py and scan normally. Every card you Save tells the
scanner it was right, and every card you correct tells it the right answer. This script runs
the *current* recognition code over all those camera pictures, so after changing
the code (or config.py) you can see whether it got better or worse.

Scans you've trained on will match themselves, so compare against --plain to see
what training adds, and judge code changes with --plain.
"""

import argparse
import statistics

import cv2

from mtgscanner import config
from mtgscanner.captures import CaptureLog, true_card
from mtgscanner.database import Matcher, connect
from mtgscanner.recognize import identify_frame


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="list each scan it gets wrong")
    parser.add_argument("--plain", action="store_true", help="leave out the fingerprints learned in the Train tab")
    args = parser.parse_args()

    log = config.CAPTURES_DIR / "log.csv"
    if not log.exists():
        raise SystemExit('No scans collected yet. Turn on "Collect scans" in app.py first.')
    rows = CaptureLog(config.CAPTURES_DIR).rows()
    matcher = Matcher(connect(config.DB_PATH))
    if args.plain:     # learned fingerprints come after the cards
        ids, hashes = matcher._table
        matcher._table = ids[:matcher.card_count], hashes[:matcher.card_count]

    right, wrong = [], []        # distances, for scans whose true card we know
    confirmed = fixed = still_wrong = no_outline = newly_found = 0
    problems = []
    for row in rows:
        frame = cv2.imread(str(config.CAPTURES_DIR / row["frame"]))
        if frame is None:
            continue
        corners, card, dist = identify_frame(matcher, frame)
        if corners is None:
            no_outline += 1
        got = card.id if card else ""
        name = card.name if card else "nothing"

        if (truth := true_card(row)) and row["verdict"] != "ignore":
            confirmed += 1
            if got == truth:
                right.append(dist)
            else:
                if card:
                    wrong.append(dist)
                real = matcher.get_card(truth)
                problems.append(f"  {row['crop']}: is {real.name} ({real.set_code.upper()}), now finds {name} (distance {dist})")
        elif row["verdict"] == "wrong" and not row["correct_id"]:
            if got == row["card_id"]:
                still_wrong += 1
                wrong.append(dist)
                problems.append(f"  {row['crop']}: still says {row['name']} (distance {dist}), which you marked wrong")
            else:
                fixed += 1
        elif row["result"] == "unknown" and card:
            newly_found += 1

    marked_wrong = sum(r["verdict"] == "wrong" and not r["correct_id"] for r in rows)
    unknown = sum(r["result"] == "unknown" for r in rows)
    print(f"{len(rows)} scans collected ({confirmed} with a known card, {marked_wrong} marked wrong, {unknown} not recognized)")
    print("Using the plain card database.\n" if args.plain else f"Using {matcher.learned_count} learned scans too (try --plain to compare).\n")
    if confirmed:
        print(f"Confirmed cards found correctly: {len(right)} of {confirmed} ({100 * len(right) / confirmed:.0f}%)")
    if marked_wrong:
        print(f"Marked-wrong cards now different:  {fixed} of {marked_wrong}")
    if unknown:
        print(f"Unrecognized scans now matched:    {newly_found} of {unknown} (check these by eye)")
    if no_outline:
        print(f"Scans where no card outline is found now: {no_outline}")

    print(f"\nMatch distance (lower is closer). Cards count as recognized up to {config.MAX_MATCH_DISTANCE}.")
    if right:
        print(f"  correct matches: typical {statistics.median(right):.0f}, worst {max(right)}")
    if wrong:
        print(f"  wrong matches:   best {min(wrong)}, typical {statistics.median(wrong):.0f}")
    if right and wrong:
        if max(right) < min(wrong):
            print(f"  -> Any MAX_MATCH_DISTANCE from {max(right)} to {min(wrong) - 1} separates them in config.py.")
        else:
            print("  -> Right and wrong matches overlap, so a threshold alone can't fix these; better lighting or code changes can.")

    if problems and args.list:
        print("\nScans it gets wrong (pictures are in data/captures):")
        print("\n".join(problems))
    elif problems:
        print(f"\n{len(problems)} scans are still wrong. Run with --list to see them.")


if __name__ == "__main__":
    main()
