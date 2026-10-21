"""The scanner as an app in your web browser.

    python app.py                  # webcam 0, then open http://localhost:5000
    python app.py --camera 1       # a different webcam
    python app.py --demo photos/   # no webcam: cycles through the photos in a folder

The page shows the live camera, the card it recognizes with its price and bin, this
session's cards, and a Photos tab where you can drop in pictures to scan. Cards are
saved to data/collection.csv, the same file scan.py uses (ready for Commander Vault).

On the Raspberry Pi, run it with --host 0.0.0.0 and open http://<pi's address>:5000
from your laptop or phone.
"""

import argparse
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, Response, jsonify, request, send_file, send_from_directory

from mtgscanner import config
from mtgscanner.collection import add_card, remove_last
from mtgscanner.database import Card, Matcher, connect
from mtgscanner.recognize import identify_frame
from mtgscanner.sorting import card_price, choose_bin
from mtgscanner.vault_prices import VaultPrices

WEB = Path(__file__).resolve().parent / "webui"


# --- Camera sources -------------------------------------------------------------

class CameraSource:
    def __init__(self, index: int):
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise SystemExit(f"Could not open camera {index}. Try --camera 1, or --demo <folder> to test without one.")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    def read(self):
        ok, frame = self.cap.read()
        return frame if ok else None


class DemoSource:
    """Pretends to be a camera: shows each photo for a few seconds, with a blank gap
    in between (like taking one card away and putting the next one down)."""

    def __init__(self, folder: str, seconds: float = 4.0):
        exts = {".jpg", ".jpeg", ".png", ".webp"}
        self.frames = [cv2.imread(str(p)) for p in sorted(Path(folder).iterdir()) if p.suffix.lower() in exts]
        self.frames = [f for f in self.frames if f is not None]
        if not self.frames:
            raise SystemExit(f"No photos found in {folder}")
        self.seconds = seconds
        self.start = time.time()
        h, w = self.frames[0].shape[:2]
        self.blank = np.full((h, w, 3), 235, np.uint8)

    def read(self):
        time.sleep(0.05)
        t = (time.time() - self.start) % (len(self.frames) * self.seconds)
        i, into = divmod(t, self.seconds)
        return self.blank if into > self.seconds - 1 else self.frames[int(i)]


# --- The scanner, running in the background ----------------------------------------

class Scanner:
    def __init__(self, matcher: Matcher, vault: VaultPrices | None, source):
        self.matcher, self.vault, self.source = matcher, vault, source
        self.lock = threading.Lock()
        self.jpeg = None             # latest camera picture, with the outline drawn on
        self.status = "starting"     # "looking", "recognizing", "locked", "unknown"
        self.card: Card | None = None
        self.distance = None
        self.foil = False
        self.auto = False
        self.saved_this_card = False
        self.session: list[dict] = []
        self._streak_id, self._streak, self._empty = None, 0, 0

    def run(self):
        while True:
            frame = self.source.read()
            if frame is None:
                time.sleep(0.2)
                continue
            corners, card, dist = identify_frame(self.matcher, frame)
            with self.lock:
                self._update(corners, card, dist)
                shown = frame.copy()
                if corners is not None:
                    color = (46, 119, 232) if self.status == "locked" else (200, 200, 200)
                    cv2.polylines(shown, [corners.astype(int)], True, color, max(2, shown.shape[1] // 300))
                h, w = shown.shape[:2]
                if w > 960:
                    shown = cv2.resize(shown, (960, int(h * 960 / w)))
                self.jpeg = cv2.imencode(".jpg", shown, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()

    def _update(self, corners, card, dist):
        if corners is None:
            self._empty += 1
            self._streak_id, self._streak = None, 0
            if self._empty > 8:    # card taken away: the next one can be saved
                self.status, self.card, self.distance, self.saved_this_card = "looking", None, None, False
            return
        self._empty = 0
        card_id = card.id if card else None
        self._streak = self._streak + 1 if card_id == self._streak_id else 1
        self._streak_id = card_id
        self.distance = dist
        if card is None:
            self.status, self.card = ("unknown" if self._streak >= config.STABLE_FRAMES else "recognizing"), None
        elif self._streak >= config.STABLE_FRAMES:
            if self.card is None or self.card.id != card.id:
                self.saved_this_card = False
            self.status, self.card = "locked", card
            if self.auto and not self.saved_this_card:
                self._save(card, self.foil)
                self.saved_this_card = True
        else:
            self.status = "recognizing"

    # Called with the lock held.
    def _save(self, card: Card, foil: bool):
        bin_no, bin_label = choose_bin(card, foil, self.vault)
        price = card_price(card, foil, self.vault)
        add_card(config.COLLECTION_CSV, card, foil, bin_label, price)
        self.session.append(card_info(card, foil, self.vault) | {"time": time.strftime("%H:%M:%S")})

    def state(self):
        with self.lock:
            totals = {"count": len(self.session), "value": round(sum(c["price"] or 0 for c in self.session), 2), "bins": {}}
            for c in self.session:
                totals["bins"][c["bin"]] = totals["bins"].get(c["bin"], 0) + 1
            return {
                "status": self.status,
                "card": card_info(self.card, self.foil, self.vault, self.distance) if self.card else None,
                "saved": self.saved_this_card,
                "foil": self.foil,
                "auto": self.auto,
                "session": self.session[::-1],
                "totals": totals,
            }


def card_info(card: Card, foil: bool, vault, distance=None) -> dict:
    price, source = card_price(card, foil, vault)
    bin_no, bin_label = choose_bin(card, foil, vault)
    return {
        "id": card.id,
        "name": card.name,
        "set": card.set_code.upper(),
        "set_name": card.set_name,
        "number": card.collector_number,
        "rarity": card.rarity,
        "foil": foil,
        "price": price,
        "price_source": source,
        "bin": bin_no,
        "bin_label": bin_label,
        # Scryfall serves the card's picture straight from its id.
        "image": f"https://api.scryfall.com/cards/{card.id}?format=image&version=normal",
        "match": None if distance is None else ("good" if distance <= 60 else "fair"),
    }


# --- Web server ----------------------------------------------------------------------

def create_app(scanner: Scanner) -> Flask:
    app = Flask(__name__, static_folder=None)

    @app.get("/")
    def index():
        return send_from_directory(WEB, "index.html")

    @app.get("/static/<path:name>")
    def static_files(name):
        return send_from_directory(WEB, name)

    @app.get("/stream.mjpg")
    def stream():
        def frames():
            while True:
                jpeg = scanner.jpeg
                if jpeg:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                time.sleep(0.08)
        return Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.get("/api/state")
    def state():
        s = scanner.state()
        s["db_count"] = len(scanner.matcher.ids)
        s["prices"] = f"Commander Vault prices, {scanner.vault.date}" if scanner.vault else "Scryfall prices (USD converted)"
        return jsonify(s)

    @app.post("/api/settings")
    def settings():
        body = request.get_json(force=True)
        with scanner.lock:
            for key in ("foil", "auto"):
                if key in body:
                    setattr(scanner, key, bool(body[key]))
        return state()

    @app.post("/api/add")
    def add():
        body = request.get_json(force=True)
        card = scanner.matcher.get_card(body["id"])
        with scanner.lock:
            scanner._save(card, bool(body.get("foil")))
            if scanner.card and scanner.card.id == card.id:
                scanner.saved_this_card = True
        return state()

    @app.post("/api/undo")
    def undo():
        with scanner.lock:
            if scanner.session and remove_last(config.COLLECTION_CSV):
                scanner.session.pop()
                scanner.saved_this_card = False
        return state()

    @app.post("/api/photos")
    def photos():
        results = []
        for f in request.files.getlist("photos"):
            frame = cv2.imdecode(np.frombuffer(f.read(), np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                results.append({"file": f.filename, "error": "Couldn't open this file"})
                continue
            corners, card, dist = identify_frame(scanner.matcher, frame)
            if corners is None:
                results.append({"file": f.filename, "error": "No card found in the photo"})
            elif card is None:
                results.append({"file": f.filename, "error": "Card not recognized"})
            else:
                results.append({"file": f.filename, "card": card_info(card, False, scanner.vault, dist)})
        return jsonify(results)

    @app.get("/api/collection.csv")
    def download():
        if not config.COLLECTION_CSV.exists():
            return Response("No cards saved yet.", status=404)
        return send_file(config.COLLECTION_CSV, as_attachment=True, download_name="collection.csv")

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--camera", type=int, default=0, help="webcam number (default 0)")
    parser.add_argument("--demo", help="folder of photos to use instead of a webcam")
    parser.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to open it from other devices")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    matcher = Matcher(connect(config.DB_PATH))
    vault = VaultPrices.load(config.VAULT_PRICES)
    source = DemoSource(args.demo) if args.demo else CameraSource(args.camera)
    scanner = Scanner(matcher, vault, source)
    threading.Thread(target=scanner.run, daemon=True).start()

    print(f"Loaded {len(matcher.ids)} cards. Open http://localhost:{args.port} in your browser.")
    create_app(scanner).run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
