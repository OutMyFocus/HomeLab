"""Whose account the machine scans into.

Nic (2026-11-27): "when I'm scanning cards with my machine, can I choose whose account
I'm scanning the cards under?" Before this, the machine's cards went to whoever pressed
something on the server's machine scanner last, and every card a sort run saved on the
Pi landed in the server owner's collection (pi_sync.py: the Pi owner's cards go to the
server's owner).

Now an admin picks one account on the Machine page (or the Scan page, on the machine's
camera): "Machine scans go into". It's kept on the server in data/machine_account.json
and covers everything the machine saves from then on:

- the server's machine scanner (the Scan page on the machine's camera) saves into it;
- a sort run started on the server uses that account's decks, wishlist and copies for
  its Bins rules, and the Pi is told the account when the run starts;
- every ask for new cards (pi_sync.py) tells the Pi the account too. The Pi writes down
  when it changed (data/scan_for.json, by its own clock, the same clock its cards are
  stamped with), and tags each card it saved in its owner's collection with the account
  it was meant for at that second. The server then files the card under that account
  (or the owner when there's no such account any more).

Nobody picked yet (or the picked account was removed) means the old way: the owner, and
the server's machine scanner saves for whoever pressed.
"""

import json
import os
import threading
from datetime import datetime

from flask import abort, jsonify, make_response, request

from . import accounts, config

HEADER = "X-Scan-For"     # the server telling the Pi whose account the machine scans into
NOBODY = "*"              # ...and that nobody is picked (the owner); no username has a *
KEEP = 200                # changes the Pi remembers (the oldest are dropped)

_lock = threading.Lock()
# Called with the newly picked account (app.py points the machine's scanner at it at once,
# so Auto-save doesn't wait for the next button press).
listeners: list = []


def _read(path) -> dict:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    os.replace(tmp, path)


def clean(name) -> str:
    return str(name or "").strip()[:40]


# --- the server's side: the choice ----------------------------------------------------------

def choice_file():
    return config.DATA_DIR / "machine_account.json"


def picked() -> str:
    """The account picked for the machine, "" when none is (or it no longer exists)."""
    if not accounts.enabled():
        return ""
    user = clean(_read(choice_file()).get("user"))
    return user if accounts.get(user) else ""


def chosen() -> str | None:
    """The account the machine's cards go into: the one picked, else the owner."""
    if not accounts.enabled():
        return None
    return picked() or accounts.owner()


def header_value() -> str:
    """What the server tells the Pi with every ask and every sort run."""
    return picked() or NOBODY


def for_machine(presser: str | None) -> str | None:
    """The account the server's machine scanner saves into when `presser` uses it."""
    return picked() or presser


def pick(user) -> str:
    """Pick the account (an existing username; "" goes back to the owner)."""
    user = clean(user)
    if user and not accounts.get(user):
        raise ValueError(f"There's no account called {user}.")
    if user == accounts.owner():
        user = ""     # the owner is what nobody picked means anyway
    with _lock:
        _write(choice_file(), {"user": user, "at": datetime.now().isoformat(timespec="seconds"),
                               "by": accounts.current() or ""})
    for listener in listeners:
        listener(user or accounts.owner())
    return user


def state() -> dict:
    on = accounts.enabled()
    return {
        "accounts": on,
        "user": chosen() if on else None,
        "owner": accounts.owner() if on else None,
        "can_pick": on and accounts.can("admin"),
        "choices": [{"username": a["username"], "name": a["name"], "owner": a["owner"]}
                    for a in accounts.everyone()] if on else [],
    }


# --- the Pi's side: when the server's choice changed ----------------------------------------

def log_file():
    return config.DATA_DIR / "scan_for.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def heard(user) -> bool:
    """The server named the account the machine scans into. Noted (with this Pi's time)
    only when it changed. Returns True when it did."""
    user = clean(user)
    if user == NOBODY:
        user = ""
    with _lock:
        data = _read(log_file())
        log = [e for e in data.get("log") or [] if isinstance(e, dict) and e.get("at")]
        last = clean(log[-1].get("user")) if log else ""
        if user == last:
            return False
        log.append({"at": _now(), "user": user})
        try:
            _write(log_file(), {"log": log[-KEEP:]})
        except OSError:
            return False
    return True


def meant_for(at: str, log: list | None = None) -> str:
    """The account the server had picked at `at` (an ISO time from this Pi's clock), or ""."""
    if log is None:
        log = _read(log_file()).get("log") or []
    user = ""
    for e in log:
        if not isinstance(e, dict) or str(e.get("at") or "") > at:
            break
        user = clean(e.get("user"))
    return user


def changes() -> list:
    """The changes the Pi has written down, oldest first (for tagging a batch of cards)."""
    return [e for e in _read(log_file()).get("log") or [] if isinstance(e, dict) and e.get("at")]


# --- the page -------------------------------------------------------------------------------

def install(app):
    """GET/POST /api/machine/account (the machine permission opens /api/machine; picking
    needs an admin, since it puts cards into someone else's collection)."""

    @app.get("/api/machine/account")
    def machine_account():
        return jsonify(state())

    @app.post("/api/machine/account")
    def machine_account_pick():
        if not accounts.enabled():
            return jsonify({"error": "Turn on accounts first (Settings, Accounts)."}), 400
        if not accounts.can("admin"):
            abort(make_response(jsonify({"error": "Only an admin can choose whose account the machine "
                                                  "scans into.", "forbidden": True}), 403))
        body = request.get_json(silent=True) or {}
        try:
            pick(body.get("user"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        from . import pi_sync
        pi_sync.poke()    # tell the Pi now, not at the next ask
        return jsonify(state())
