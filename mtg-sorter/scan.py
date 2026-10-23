"""Scan cards with a webcam (or from photos) and save them to your collection.

Webcam mode:
    python scan.py
    python scan.py --camera 1      # if you have more than one camera

    Hold a card under the camera on a plain background (white paper works best).
    Keys:  SPACE = save card   F = toggle foil   A = toggle auto-save   Q = quit

Photo mode (no webcam needed, good for testing):
    python scan.py --image my_card_photo.jpg
"""

import argparse

import cv2

from mtgscanner import config
from mtgscanner.collection import add_card
from mtgscanner.database import Card, Matcher, connect
from mtgscanner.exchange import load_rate
from mtgscanner.sorting import card_price, choose_bin
from mtgscanner.vault_prices import VaultPrices
from mtgscanner.recognize import identify, identify_frame

# Canadian prices from Commander Vault, loaded in main() if data/vault_prices.json exists.
VAULT: VaultPrices | None = None


def describe(card: Card, foil: bool) -> str:
    price, source = card_price(card, foil, VAULT)
    price_txt = "no price" if price is None else f"${price:.2f} CAD ({source})"
    return f"{card.name} [{card.set_code.upper()} #{card.collector_number}]{' FOIL' if foil else ''} - {price_txt}"


def scan_images(matcher: Matcher, paths: list[str], foil: bool, save: bool) -> None:
    for path in paths:
        frame = cv2.imread(path)
        if frame is None:
            print(f"{path}: could not open image")
            continue
        corners, card, dist = identify_frame(matcher, frame)
        if corners is None:
            print(f"{path}: no card found in photo")
            continue
        if card is None:
            print(f"{path}: card not recognized (closest distance {dist})")
            continue
        bin_no, bin_label = choose_bin(card, foil, VAULT)
        print(f"{path}: {describe(card, foil)} -> bin {bin_no} ({bin_label})  [distance {dist}]")
        if save:
            add_card(config.COLLECTION_CSV, card, foil, bin_label, card_price(card, foil, VAULT))


def scan_webcam(matcher: Matcher, camera: int) -> None:
    cap = cv2.VideoCapture(camera)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera {camera}. Try --camera 1")

    foil = False
    auto = False
    streak_id, streak = None, 0  # how many frames in a row we've seen the same card
    saved_this_card = False
    frames_without_card = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        corners, card, dist = identify_frame(matcher, frame)
        locked: Card | None = None

        if corners is not None:
            frames_without_card = 0
            card_id = card.id if card else None
            streak = streak + 1 if card_id == streak_id else 1
            streak_id = card_id
            if card and streak >= config.STABLE_FRAMES:
                locked = card
            color = (0, 255, 0) if locked else (0, 200, 255)
            cv2.polylines(frame, [corners.astype(int)], True, color, 3)
        else:
            frames_without_card += 1
            streak_id, streak = None, 0
            if frames_without_card > 10:  # card was removed, so the next one can be saved
                saved_this_card = False

        if locked:
            bin_no, bin_label = choose_bin(locked, foil, VAULT)
            lines = [describe(locked, foil), f"-> BIN {bin_no}: {bin_label}"]
            if saved_this_card:
                lines.append("saved!")
            if auto and not saved_this_card:
                add_card(config.COLLECTION_CSV, locked, foil, bin_label, card_price(locked, foil, VAULT))
                saved_this_card = True
                print(f"saved: {describe(locked, foil)} -> bin {bin_no}")
        else:
            lines = ["Looking for a card..." if corners is None else "Recognizing..."]
        lines.append(f"[SPACE] save  [F] foil: {'on' if foil else 'off'}  [A] auto: {'on' if auto else 'off'}  [Q] quit")

        for i, text in enumerate(lines):
            y = 30 + 30 * i
            cv2.putText(frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
            cv2.putText(frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imshow("MTG Scanner", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("f"):
            foil = not foil
        elif key == ord("a"):
            auto = not auto
        elif key == ord(" ") and locked and not saved_this_card:
            bin_no, bin_label = choose_bin(locked, foil, VAULT)
            add_card(config.COLLECTION_CSV, locked, foil, bin_label, card_price(locked, foil, VAULT))
            saved_this_card = True
            print(f"saved: {describe(locked, foil)} -> bin {bin_no}")

    cap.release()
    cv2.destroyAllWindows()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", nargs="+", help="scan photo file(s) instead of using the webcam")
    parser.add_argument("--camera", type=int, default=0, help="webcam number (default 0)")
    parser.add_argument("--foil", action="store_true", help="photo mode: treat cards as foil")
    parser.add_argument("--save", action="store_true", help="photo mode: add recognized cards to the collection CSV")
    args = parser.parse_args()

    global VAULT
    matcher = Matcher(connect(config.DB_PATH))
    print(f"Loaded {matcher.card_count} cards from the database.")
    VAULT = VaultPrices.load(config.VAULT_PRICES)
    load_rate()
    if VAULT:
        print(f"Using Commander Vault prices from {VAULT.date}.")
    else:
        print("No Commander Vault prices found (data/vault_prices.json), using Scryfall prices.")
    if args.image:
        scan_images(matcher, args.image, args.foil, args.save)
    else:
        scan_webcam(matcher, args.camera)


if __name__ == "__main__":
    main()
