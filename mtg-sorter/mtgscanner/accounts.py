"""User accounts: everyone logs in, and each person has their own cards.

Accounts are off until someone turns them on (Settings, Accounts). Until then the app
works as it always did: one collection, no login (the optional PIN lock still works).

Turning accounts on makes the first account, the owner. The owner keeps everything that
was already there: data/collection.csv, decks.json, wishlist.json and the rest stay
exactly where they are, so nothing gets moved. A backup is saved in data/backups first.
Everyone added after that gets a folder of their own, data/users/<username>/, holding
the same files for them: their collection, decks, wishlist, alerts, trade binder, games
and value history.

Shared by everyone: the card database (and what it learned), prices, the machine and its
bins, the lights, and the app's settings.

What each person may do (their permissions):
    scan     scan cards into their collection, with their phone's camera or photos
    edit     change their own collection, decks, wishlist, trades and games
    machine  run the sorting machine: the Machine, Lights and Bins pages, the machine's
             camera, and training the scanner
    admin    everything, plus Maintenance, the weekly price check and the accounts
Someone with none of these can still look at their own cards.

The Pi itself is never locked out: requests from the Pi (the auto-update check, the `mtg`
command) count as the owner, as long as they didn't come in through a tunnel.

Locked out? Delete data/users.json on the Pi or server and the login is gone (everyone's
cards stay where they are; turn accounts on again to get them back).
"""

import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from . import config

PERMS = ("scan", "edit", "machine", "admin")
ROLES = {   # ready-made sets of permissions, as the Settings page offers them
    "admin": ["scan", "edit", "machine", "admin"],
    "member": ["scan", "edit"],
    "viewer": [],
}
COOKIE = "mtg_session"
DAYS = 60
TRIES, PAUSE = 5, 30          # wrong passwords in a row before a pause of PAUSE seconds
MIN_PASSWORD = 6
USERNAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,23}")

_current: ContextVar[str | None] = ContextVar("mtg_account", default=None)
_cache: dict = {"mtime": None, "data": None}
_lock = threading.RLock()
_tries: dict[str, tuple[int, float]] = {}


# --- The accounts file ----------------------------------------------------------------------

def users_file() -> Path:
    return config.DATA_DIR / "users.json"


def _load() -> dict | None:
    """users.json, or None while accounts are off. Read again only when it changes."""
    path = users_file()
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return None
    with _lock:
        if _cache["mtime"] == mtime and _cache.get("path") == path:
            return _cache["data"]
        try:
            data = json.loads(path.read_text())
            ok = isinstance(data, dict) and data.get("secret") and isinstance(data.get("users"), dict) and data["users"]
        except (OSError, ValueError):
            ok = False
        data = data if ok else None
        _cache.update(mtime=mtime, data=data, path=path)
        return data


def _save(data: dict):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = users_file().with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(users_file())
    with _lock:
        _cache.update(mtime=None)


def enabled() -> bool:
    return _load() is not None


def owner() -> str | None:
    """The first account, whose cards are the ones that were there before accounts."""
    data = _load()
    if not data:
        return None
    return next((u for u, a in data["users"].items() if a.get("owner")), next(iter(data["users"])))


def get(username: str | None) -> dict | None:
    data = _load()
    return data["users"].get(username) if data and username else None


def usernames() -> list[str]:
    data = _load()
    return list(data["users"]) if data else []


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()


def _clean_username(raw) -> str:
    name = str(raw or "").strip().lower()
    if not USERNAME.fullmatch(name):
        raise ValueError("A username is 1 to 24 letters, numbers, - or _, starting with a letter or number")
    return name


def _clean_password(raw) -> str:
    password = str(raw or "")
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"The password has to be at least {MIN_PASSWORD} characters")
    if len(password) > 200:
        raise ValueError("That password is too long")
    return password


def _clean_perms(raw, role=None) -> list[str]:
    if role in ROLES and raw is None:
        return list(ROLES[role])
    perms = [p for p in PERMS if p in (raw or [])]
    return list(PERMS) if "admin" in perms else perms


def _account(name, password, perms) -> dict:
    salt = secrets.token_hex(16)
    return {"name": str(name or "").strip()[:40], "perms": perms, "salt": salt,
            "hash": _hash(password, salt), "session": 1, "created": time.strftime("%Y-%m-%d %H:%M")}


def setup(username, password, name="") -> str:
    """Turn accounts on: the first account is the owner, and keeps the existing cards."""
    if enabled():
        raise ValueError("Accounts are on already")
    username = _clean_username(username)
    account = _account(name or username, _clean_password(password), list(PERMS)) | {"owner": True}
    _save({"secret": secrets.token_hex(32), "users": {username: account}})
    return username


def add(username, password, name="", perms=None, role="member") -> str:
    data = _load()
    if not data:
        raise ValueError("Turn accounts on first")
    username = _clean_username(username)
    if username in data["users"]:
        raise ValueError("Someone already has that username")
    data["users"][username] = _account(name or username, _clean_password(password), _clean_perms(perms, role))
    _save(data)
    home(username).mkdir(parents=True, exist_ok=True)
    return username


def update(username, name=None, perms=None, password=None):
    """Change someone's name, permissions or password. A new password logs them out
    everywhere else."""
    data = _load()
    account = data and data["users"].get(username)
    if not account:
        raise ValueError("There's no account called that")
    if name is not None:
        account["name"] = str(name).strip()[:40] or username
    if perms is not None:
        perms = _clean_perms(perms)
        if account.get("owner") and "admin" not in perms:
            raise ValueError("The owner always stays an admin")
        if "admin" in account["perms"] and "admin" not in perms and _admins(data) == [username]:
            raise ValueError("Keep at least one admin")
        account["perms"] = perms
    if password is not None:
        account["salt"] = secrets.token_hex(16)
        account["hash"] = _hash(_clean_password(password), account["salt"])
        account["session"] = int(account.get("session", 1)) + 1
    _save(data)


def remove(username):
    """Take the account away. Their cards stay in data/users/<username>/, so adding the
    same username again brings them back."""
    data = _load()
    account = data and data["users"].get(username)
    if not account:
        raise ValueError("There's no account called that")
    if account.get("owner"):
        raise ValueError("The owner's account can't be removed")
    del data["users"][username]
    _save(data)


def log_out_everywhere(username):
    data = _load()
    if data and username in data["users"]:
        data["users"][username]["session"] = int(data["users"][username].get("session", 1)) + 1
        _save(data)


def _admins(data) -> list[str]:
    return [u for u, a in data["users"].items() if "admin" in a.get("perms", [])]


def check_password(username, password) -> bool:
    account = get(str(username or "").strip().lower())
    if not account:
        _hash(str(password or ""), "00" * 16)   # take as long as a real check
        return False
    return hmac.compare_digest(_hash(str(password or ""), account["salt"]), account["hash"])


def too_many_tries(who: str) -> bool:
    with _lock:
        count, since = _tries.get(who, (0, 0.0))
        return count >= TRIES and time.time() - since < PAUSE


def note_try(who: str, ok: bool):
    with _lock:
        if ok:
            _tries.pop(who, None)
        else:
            count, _ = _tries.get(who, (0, 0.0))
            _tries[who] = (count % TRIES + 1, time.time())


# --- Logged in ------------------------------------------------------------------------------

def session_token(username: str) -> str:
    data = _load()
    expires = int(time.time()) + DAYS * 86400
    version = int(data["users"][username].get("session", 1))
    payload = f"{username}.{version}.{expires}"
    sig = hmac.new(bytes.fromhex(data["secret"]), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def user_from_token(token: str | None) -> str | None:
    data = _load()
    if not data or not token:
        return None
    try:
        username, version, expires, sig = token.split(".")
        good = hmac.new(bytes.fromhex(data["secret"]), f"{username}.{version}.{expires}".encode(),
                        hashlib.sha256).hexdigest()
        account = data["users"].get(username)
        if (account and hmac.compare_digest(sig, good) and int(expires) > time.time()
                and int(version) == int(account.get("session", 1))):
            return username
    except (ValueError, TypeError):
        pass
    return None


def current() -> str | None:
    """Who this request (or scanner) is for. None while accounts are off."""
    return _current.get() if enabled() else None


def set_current(username: str | None):
    _current.set(username)


@contextmanager
def acting_as(username: str | None):
    """Work on someone's cards for a while (a scanner saving for its person, a job)."""
    token = _current.set(username)
    try:
        yield
    finally:
        _current.reset(token)


def can(perm: str, username: str | None = None) -> bool:
    """While accounts are off, everyone can do everything (the PIN lock aside)."""
    if not enabled():
        return True
    account = get(username if username is not None else _current.get())
    if not account:
        return False
    perms = account.get("perms", [])
    return "admin" in perms or perm in perms


def public(username: str) -> dict:
    a = get(username) or {}
    return {"username": username, "name": a.get("name") or username, "perms": a.get("perms", []),
            "owner": bool(a.get("owner")), "created": a.get("created", "")}


def everyone() -> list[dict]:
    return [public(u) for u in usernames()]


# --- Where each person's files are ---------------------------------------------------------

def home(username: str | None = None) -> Path:
    """The folder with someone's cards: data/ itself for the owner (and while accounts
    are off), data/users/<username>/ for everyone else."""
    username = username if username is not None else current()
    if not username or not enabled() or username == owner():
        return config.DATA_DIR
    return config.DATA_DIR / "users" / username


def user_file(name: str, username: str | None = None) -> Path:
    return home(username) / name


def collection_csv(username: str | None = None) -> Path:
    folder = home(username)
    return config.COLLECTION_CSV if folder == config.DATA_DIR else folder / "collection.csv"


def each_user():
    """Every account in turn (or just the one collection while accounts are off), for
    jobs that cover everyone's cards, like the weekly price check."""
    for username in (usernames() or [None]):
        with acting_as(username):
            yield username
