"""One app for the sorter: the server keeps the cards and the settings, the Pi follows it.

The app runs twice. The server (tower, the public site) is the main copy. The sorter's Pi
runs the same image because it has the camera, the servos and the feeder, and it keeps a
data folder of its own. The server already drives the Pi's machine and lights
(remote_machine.py) and sends its Bins rules with each sort run, but the run itself happens
on the Pi, so every card it sorted was saved into the Pi's collection, and anyone opening
the Pi's own address saw the Pi's collection and settings instead of the server's.

Two things here put an end to that:

Cards. Every SYNC_SECONDS the server asks the Pi for the cards saved since its last ask
(GET /api/machine/saved, which the machine key opens like the rest of /api/machine) and
adds them to its own collection: the Pi owner's cards to the server's owner, another Pi
account's cards to the same username on the server (or the owner when there is none).
The very first ask only notes where the Pi's collection ends, so what the Pi held before
the link isn't copied. Where it got to is kept in data/pi_sync.json.

Pages. Each ask tells the Pi the server's public address (MTG_PUBLIC_URL, or the address
the server is reached at through its Cloudflare tunnel). While the server keeps asking,
the Pi's pages send the browser on to that address, so http://<the Pi>:5000 opens the
site. Only pages move: the API, the camera stream and the Pi's own screen stay as they
are, and if the server stops asking (it's down), the Pi's own pages come back by
themselves. Add ?stay=1 to a Pi address to stay on the Pi in that browser.
"""

import csv
import io
import json
import logging
import os
import threading
import time
from datetime import datetime
from urllib.parse import urlsplit

import requests
from flask import jsonify, redirect, request

from . import accounts, config, machine_account
from .collection import COLLECTION_LOCK, COLUMNS, append_rows, read_text
from .remote_machine import KEY_HEADER, remote_url

log = logging.getLogger(__name__)

SYNC_SECONDS = 15        # how often the server asks the Pi for new cards
MAX_ROWS = 2000          # cards in one answer; the next ask carries on from there
SITE_HEADER = "X-Main-Site"
FOLLOW_SECONDS = 10 * 60  # the Pi sends pages to the server only if it asked this recently
STAY_COOKIE = "mtg_stay_on_pi"
# What stays on the Pi: the API (the server drives the machine through it), the live
# stream, files, and the scans the training page shows.
NOT_PAGES = ("/api/", "/static/", "/captures/", "/stream", "/favicon")


def state_file():
    return config.DATA_DIR / "pi_sync.json"


def site_file():
    return config.DATA_DIR / "main_site.json"


def _read_json(path) -> dict:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_json(path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    os.replace(tmp, path)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def clean_site(url) -> str | None:
    """An http(s) address with nothing after the host, or None."""
    try:
        parts = urlsplit(str(url or "").strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.netloc or "@" in parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


# --- the Pi's side ---------------------------------------------------------------------------

def _row_key(row: dict) -> str:
    return "|".join(str(row.get(k, "")) for k in ("user", "Scryfall ID", "Foil", "Scanned at", "n"))


def _collections():
    """(Pi username or "" for the owner, collection file) for each collection on this Pi."""
    seen = set()
    for username in (accounts.usernames() or [None]):
        path = accounts.collection_csv(username)
        if path in seen:
            continue
        seen.add(path)
        yield ("" if path == config.COLLECTION_CSV else username), path


def saved_since(after: str | None, limit: int = MAX_ROWS) -> dict:
    """The cards saved on this Pi at or after `after` (an ISO time from this Pi's clock),
    oldest first. Cards saved in the same second are told apart by `n`, their place in that
    second. A cut at `limit` never splits a second, so the next ask can start at the last one."""
    rows = []
    picks = machine_account.changes()   # whose account the server had the machine scan into, when
    with COLLECTION_LOCK:
        for user, path in _collections():
            if not path.exists():
                continue
            counts = {}
            for row in csv.DictReader(io.StringIO(read_text(path))):
                at = (row.get("Scanned at") or "").strip()
                if not at or (after and at < after) or not (row.get("Name") or "").strip():
                    continue
                same = (row.get("Scryfall ID", ""), row.get("Foil", ""), at)
                counts[same] = counts.get(same, 0) + 1
                rows.append({k: row.get(k, "") or "" for k in COLUMNS} | {"user": user, "n": counts[same]}
                            | ({"for": machine_account.meant_for(at, picks)} if not user and picks else {}))
    rows.sort(key=lambda r: r["Scanned at"])
    more = False
    if len(rows) > limit:
        cut = rows[limit - 1]["Scanned at"]
        if cut == after:   # that second alone fills the answer: take the next one too, or the
            cut = next((r["Scanned at"] for r in rows if r["Scanned at"] > cut), cut)   # asks go round
        keep = [r for r in rows if r["Scanned at"] <= cut]
        more, rows = len(keep) < len(rows), keep
    for r in rows:
        r["key"] = _row_key(r)
    return {"now": _now(), "rows": rows, "more": more}


def heard_from_server(site: str | None):
    """The server asked: remember its address, so the Pi's pages can send people there."""
    site = clean_site(site)
    if not site:
        return
    old = _read_json(site_file())
    now = time.time()
    if old.get("site") != site or now - float(old.get("seen") or 0) > 60:
        try:
            _write_json(site_file(), {"site": site, "seen": now})
        except OSError:
            pass
    _seen.update(site=site, seen=now)


_seen: dict = {}


def main_site() -> str | None:
    """The server's address while it keeps asking (FOLLOW_SECONDS), else None."""
    if not _seen:
        _seen.update(_read_json(site_file()))
    site = clean_site(_seen.get("site"))
    if site and time.time() - float(_seen.get("seen") or 0) < FOLLOW_SECONDS:
        return site
    return None


def _send_to_server():
    """Before every request on the Pi: a page goes to the server's site instead."""
    if remote_url() or request.method != "GET" or request.path.startswith(NOT_PAGES):
        return None
    if request.path.endswith((".mjpg", ".json", ".csv", ".js", ".css", ".png", ".svg", ".ico")):
        return None
    from . import security
    if security.is_local():          # the Pi's own screen (or ssh) keeps the Pi's pages
        return None
    if request.args.get("stay") == "1":
        return None                  # the page shows; the cookie below keeps it so
    if request.cookies.get(STAY_COOKIE) == "1":
        return None
    site = main_site()
    if not site or urlsplit(site).netloc.lower() == request.host.lower():
        return None
    return redirect(site + request.full_path.rstrip("?"), 302)


def _remember_stay(response):
    if request.args.get("stay") == "1" and not remote_url():
        response.set_cookie(STAY_COOKIE, "1", httponly=True, samesite="Lax")   # until the browser closes
    return response


# --- the server's side -----------------------------------------------------------------------

def public_url() -> str | None:
    """The server's address for people: MTG_PUBLIC_URL, else the one it was last reached at
    through its Cloudflare tunnel (learned from page requests, see learn_site)."""
    return clean_site(os.environ.get("MTG_PUBLIC_URL")) or clean_site(_read_json(state_file()).get("site"))


def learn_site():
    """A page reached through the Cloudflare tunnel: that's the address people use."""
    if not remote_url() or "CF-Connecting-IP" not in request.headers:
        return
    site = clean_site("https://" + request.host)
    if not site or site == _learned.get("site"):
        return
    _learned["site"] = site
    with _state_lock:
        s = _read_json(state_file())
        if s.get("site") != site:
            s["site"] = site
            try:
                _write_json(state_file(), s)
            except OSError:
                pass


_learned: dict = {}
_state_lock = threading.Lock()


class PiSync:
    """The server copying the cards the Pi saves into its own collections."""

    def __init__(self, url: str, key: str | None = None):
        self.url = url.rstrip("/")
        self.key = key if key is not None else (os.environ.get("MTG_MACHINE_KEY") or "").strip()
        self.http = requests.Session()
        self.error: str | None = None
        self.last_try: float | None = None
        self._stop = threading.Event()
        self._wake = threading.Event()

    def _ask(self, after: str | None) -> dict:
        headers = {KEY_HEADER: self.key} if self.key else {}
        site = public_url()
        if site:
            headers[SITE_HEADER] = site
        headers[machine_account.HEADER] = machine_account.header_value()
        params = {"after": after} if after else {"start": "1"}
        try:
            r = self.http.get(self.url + "/api/machine/saved", params=params, headers=headers, timeout=(2, 20))
        except requests.RequestException:
            raise RuntimeError(f"Can't reach the sorter's Pi at {self.url}.")
        if r.status_code in (401, 403):
            raise RuntimeError("The sorter's Pi refused (it has a PIN or accounts on): put its "
                               "data/machine_key in MTG_MACHINE_KEY on this server.")
        if r.status_code == 404:
            raise RuntimeError("The sorter's Pi runs an older version of the app: update it.")
        try:
            data = r.json()
        except ValueError:
            data = None
        if r.status_code != 200 or not isinstance(data, dict):
            raise RuntimeError(f"The sorter's Pi answered with an error ({r.status_code}).")
        return data

    @staticmethod
    def _target(user: str, meant_for: str = ""):
        """Where a Pi account's cards go here: the account the machine was scanning into when
        the Pi saved it (machine_account.py), else the same username if it exists, else the
        owner."""
        if meant_for and accounts.enabled() and accounts.get(meant_for):
            return accounts.collection_csv(meant_for)
        if user and accounts.enabled() and accounts.get(user):
            return accounts.collection_csv(user)
        return accounts.collection_csv(accounts.owner() if accounts.enabled() else None)

    def sync_once(self) -> int:
        """Ask the Pi once and add what's new. Returns how many cards were added."""
        self.last_try = time.time()
        with _state_lock:
            s = _read_json(state_file())
        if s.get("pi") != self.url:      # a different Pi (or the first time): start from now
            s = {"site": s.get("site"), "pi": self.url, "after": None, "keys": [], "copied": 0}
        added, asks = 0, 0
        while True:
            data = self._ask(s.get("after"))
            if not s.get("after"):       # the first ask: only where the Pi's collection ends
                s["after"] = data.get("now") or _now()
                s["keys"] = [str(k) for k in data.get("keys") or []]   # saved in that same second
                break
            done = set(s.get("keys") or [])
            new = [r for r in data.get("rows") or [] if isinstance(r, dict) and r.get("key") not in done]
            by_file: dict = {}
            for r in new:
                by_file.setdefault(self._target(str(r.get("user") or ""), str(r.get("for") or "")), []).append(
                    {k: str(r.get(k, "") or "") for k in COLUMNS})
            for path, rows in by_file.items():
                append_rows(path, rows)
            added += len(new)
            rows = [r for r in data.get("rows") or [] if isinstance(r, dict)]
            if rows:
                # The next ask starts at the last second again (more may be saved in it), so
                # remember that second's cards, all of which are here by now.
                last = max(str(r.get("Scanned at", "")) for r in rows)
                s["after"] = last
                s["keys"] = sorted({str(r.get("key")) for r in rows if r.get("Scanned at") == last})
            asks += 1
            if not data.get("more") or asks >= 50:
                break
        s["copied"] = int(s.get("copied") or 0) + added
        s["checked"] = _now()
        if added:
            s["last_card"] = _now()
            log.info("Copied %d card(s) the sorter's Pi saved into the collection here", added)
        with _state_lock:
            site = _read_json(state_file()).get("site")   # learn_site may have written meanwhile
            _write_json(state_file(), s | ({"site": site} if site else {}))
        return added

    def loop(self):
        while not self._stop.is_set():
            try:
                self.sync_once()
                self.error = None
            except Exception as e:   # the Pi being off mustn't stop the loop
                self.error = str(e) or "Copying from the sorter's Pi failed"
            self._wake.wait(SYNC_SECONDS)
            self._wake.clear()

    def start(self):
        threading.Thread(target=self.loop, name="pi-sync", daemon=True).start()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def poke(self):
        """Ask the Pi now rather than at the next turn (the machine's account was changed)."""
        self._wake.set()

    def state(self) -> dict:
        s = _read_json(state_file())
        return {"pi": self.url, "ok": self.error is None, "error": self.error, "copied": int(s.get("copied") or 0),
                "checked": s.get("checked"), "last_card": s.get("last_card"), "site": public_url()}


_sync: PiSync | None = None


def sync_check() -> dict | None:
    """The Maintenance page's line for the link (on the server only)."""
    from .system import check
    if _sync is None:
        return None
    s = _sync.state()
    if s["ok"]:
        last = f" The last one came at {s['last_card'][11:16]}." if s.get("last_card") else ""
        site = (f" Opening the Pi's address sends you to {s['site']}." if s.get("site")
                else " Set MTG_PUBLIC_URL so the Pi's address sends you here.")
        return check("pisync", "Cards from the sorter", "ok",
                     f"Cards the sorter saves are copied here ({s['copied']} so far).{last}{site}")
    state = "off" if s["error"].startswith("Can't reach") else "warn"   # the Pi being off is normal
    return check("pisync", "Cards from the sorter", state, "Not copying the sorter's cards right now: " + s["error"],
                 "Cards wait on the Pi and come over once it answers again.")


def poke():
    """The server: tell the Pi what changed (whose account the machine scans into) now."""
    if _sync is not None:
        _sync.poke()


def start() -> PiSync | None:
    """On the server (MTG_MACHINE_URL set): start copying the Pi's cards. Once, from main()."""
    global _sync
    if remote_url() and _sync is None:
        _sync = PiSync(remote_url())
        _sync.start()
    return _sync


def install(app):
    """The Pi answers the server's asks, and sends its pages to the server while the server
    keeps asking. Registered before the login checks, so a page goes to the server before
    the Pi would ask anyone to log in."""

    @app.before_request
    def follow_the_server():
        if remote_url():
            learn_site()
            return None
        return _send_to_server()

    app.after_request(_remember_stay)

    @app.get("/api/machine/saved")
    def saved_cards():
        if remote_url():   # the server keeps the cards; only a Pi answers this
            return jsonify({"error": "Only the sorter's Pi answers this."}), 404
        # past the login checks: the server (its machine key) says where people should go
        heard_from_server(request.headers.get(SITE_HEADER))
        if machine_account.HEADER in request.headers:   # an older server doesn't say
            machine_account.heard(request.headers.get(machine_account.HEADER))
        if request.args.get("start") == "1":   # the server's first ask: where the collection ends
            now = _now()
            ending = [r["key"] for r in saved_since(now)["rows"] if r["Scanned at"] == now]
            return jsonify({"now": now, "rows": [], "keys": ending, "more": False})
        return jsonify(saved_since(request.args.get("after") or None))

    @app.get("/api/pi_sync")
    def pi_sync_state():
        return jsonify(_sync.state() if _sync else {"pi": None})

