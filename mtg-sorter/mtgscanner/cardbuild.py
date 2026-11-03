"""Download every card's picture and fingerprint it, from the Maintenance page.

The scanner can only recognize cards it has a fingerprint for (data/cards.db). This
runs build_db.py's --all build in the background inside the app, so nobody has to open
a terminal on the server or the Pi, and reloads the fingerprints as it goes: each batch
of new cards works right away, with no restart.
"""

import threading
import time

# Fewer cards than this and the database is a test build, not every card.
FULL_DATABASE = 50_000


class CardBuild:
    """One build at a time. state() is what the Maintenance page shows."""

    def __init__(self, matcher):
        self.matcher = matcher
        self.lock = threading.Lock()
        self.running = False
        self.message = ""
        self.error = ""
        self.result: dict | None = None
        self.finished_at: float | None = None
        self._stop = threading.Event()

    def state(self) -> dict:
        with self.lock:
            return {"running": self.running, "message": self.message, "error": self.error,
                    "result": self.result, "finished_at": self.finished_at}

    def start(self, everything: bool = True) -> bool:
        with self.lock:
            if self.running:
                return False
            self.running, self.message, self.error, self.result = True, "Starting", "", None
            self._stop.clear()
        threading.Thread(target=self._run, args=(everything,), name="card-build", daemon=True).start()
        return True

    def stop(self):
        self._stop.set()

    def _say(self, text: str):
        with self.lock:
            self.message = text
        print("[cards]", text, flush=True)

    def _run(self, everything: bool):
        import build_db   # next to app.py; imported here so the app starts without its imports
        try:
            source = build_db.cards_from_bulk(self._say) if everything else \
                build_db.cards_from_sets(build_db.collection_sets())
            result = build_db.build(source, progress=self._say, on_batch=self.matcher.reload, stop=self._stop)
            self.matcher.reload()
            stopped = self._stop.is_set()
            with self.lock:
                self.result = result
                self.message = (("Stopped. " if stopped else "Done. ")
                                + f"{result['total']:,} cards in the database"
                                + (f", {result['added']:,} new" if result["added"] else "")
                                + (f", {result['upgraded']:,} given the newer fingerprint" if result["upgraded"] else "")
                                + (f". {result['skipped']:,} pictures didn't download: press it again later to retry"
                                   if result["skipped"] else "") + ".")
        except Exception as e:   # no internet, Scryfall down, disk full: say so on the page
            self.matcher.reload()   # keep whatever got in before it stopped
            with self.lock:
                self.error = f"The card download didn't finish: {e}. Press the button again to carry on where it stopped."
                self.message = ""
            print("[cards]", self.error, flush=True)
        finally:
            with self.lock:
                self.running = False
                self.finished_at = time.time()
