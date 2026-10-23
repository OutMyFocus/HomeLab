"""Collect scans to improve recognition later.

While collecting, every card put under the camera is kept once: the straightened card
picture, the whole camera picture, and what the scanner thought it was. Each one
gets a row in data/captures/log.csv once the card is taken away, with a verdict:

  saved       you pressed Save, so the scanner was right
  auto-saved  saved by auto-save (probably right, nobody checked)
  wrong       you pressed "Wrong card"
  corrected   you picked the right card (its id is in correct_id)
  ignore      not a usable picture (skipped in the Train tab)
  (empty)     not saved or marked

The Train tab teaches the scanner from the scans you confirmed (see training.py), and
evaluate.py runs the current recognition code over all of it and reports how it does.
"""

import csv
import time
from pathlib import Path

import cv2

from .database import Card
from .vision import fingerprint, warp_card

COLUMNS = ["time", "camera", "result", "card_id", "name", "set", "number", "distance", "verdict", "correct_id", "crop", "frame"]


def true_card(row: dict, include_auto: bool = True) -> str | None:
    """The card a scan really shows, if you told the scanner (by saving or picking it)."""
    if row.get("correct_id"):
        return row["correct_id"]
    if row["verdict"] == "saved" or (include_auto and row["verdict"] == "auto-saved"):
        return row["card_id"]
    return None


class CaptureLog:
    def __init__(self, folder: Path):
        self.folder = folder
        self.log = folder / "log.csv"
        self._recount(self.rows())

    def rows(self) -> list[dict]:
        if not self.log.exists():
            return []
        with self.log.open(newline="", encoding="utf-8") as f:
            return [{k: row.get(k) or "" for k in COLUMNS} for row in csv.DictReader(f)]

    def update(self, crop: str, **changes) -> dict | None:
        """Change a scan that's already in the log (e.g. label it in the Train tab)."""
        rows = self.rows()
        found = next((r for r in rows if r["crop"] == crop), None)
        if found is None:
            return None
        found.update(changes)
        tmp = self.log.with_suffix(".tmp")
        with tmp.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        tmp.replace(self.log)
        self._recount(rows)
        return found

    def capture(self, frame, corners, card: Card | None, distance: int, camera: str) -> dict:
        """Save the pictures now. The log row is written by finish(), once the verdict is known."""
        day = time.strftime("%Y-%m-%d")
        stamp = time.strftime("%H%M%S") + f"{int(time.time() * 1000) % 1000:03d}"
        (self.folder / day).mkdir(parents=True, exist_ok=True)
        crop, whole = f"{day}/{stamp}_card.jpg", f"{day}/{stamp}_frame.jpg"
        card_img = warp_card(frame, corners)
        cv2.imwrite(str(self.folder / crop), card_img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        h, w = frame.shape[:2]
        if w > 1600:
            frame = cv2.resize(frame, (1600, int(h * 1600 / w)))
        cv2.imwrite(str(self.folder / whole), frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
        return {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "camera": camera,
            "result": "recognized" if card else "unknown",
            "card_id": card.id if card else "",
            "name": card.name if card else "",
            "set": card.set_code.upper() if card else "",
            "number": card.collector_number if card else "",
            "distance": distance,
            "verdict": "",
            "correct_id": "",
            "crop": crop,
            "frame": whole,
            "_fp": fingerprint(card_img),   # kept in memory only, for learning right away
        }

    def finish(self, record: dict):
        new = not self.log.exists()
        self.folder.mkdir(parents=True, exist_ok=True)
        with self.log.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            if new:
                writer.writeheader()
            writer.writerow(record)
        self._count(record)

    def _recount(self, rows: list[dict]):
        self.counts = {"total": 0, "unknown": 0, "saved": 0, "wrong": 0, "corrected": 0, "labeled": 0}
        for row in rows:
            self._count(row)

    def _count(self, row: dict):
        self.counts["total"] += 1
        self.counts["unknown"] += row["result"] == "unknown"
        self.counts["saved"] += row["verdict"] in ("saved", "auto-saved")
        self.counts["wrong"] += row["verdict"] == "wrong"
        self.counts["corrected"] += row["verdict"] == "corrected"
        self.counts["labeled"] += true_card(row) is not None
