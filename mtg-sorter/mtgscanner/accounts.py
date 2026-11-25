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

users.json.bak next to it is a copy from the last save. If users.json gets damaged, the app
uses that copy; with neither readable, only the Pi itself gets in until one is fixed.
"""

import copy
import hashlib
import hmac
import json
import logging
import math
import os
import re
import secrets
import tempfile
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
log = logging.getLogger(__name__)


# --- The accounts file ----------------------------------------------------------------------

def users_file() -> Path:
    return config.DATA_DIR / "users.json"


def backup_file() -> Path:
    """A copy of users.json from the last time it was saved, in case users.json gets damaged."""
    return config.DATA_DIR / "users.json.bak"


def _read(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    ok = isinstance(data, dict) and data.get("secret") and isinstance(data.get("users"), dict) and data["users"]
    return data if ok else None


def _load() -> dict | None:
    """users.json, or None while accounts are off (no file) or the file is damaged.
    Read again only when it changes.

    A file that is there but can't be read (a bad hand edit, a half-copied restore) never
    turns accounts off: the app keeps the accounts it read last, or the copy saved next to
    it (users.json.bak). With neither, damaged() is True and logins.py lets only the Pi in."""
    path = users_file()
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return None
    with _lock:
        if _cache["mtime"] == mtime and _cache.get("path") == path:
            return _cache["data"]
        data = _read(path)
        if data is None:
            data = (_cache["data"] if _cache.get("path") == path else None) or _read(backup_file())
            log.warning("%s can't be read: using %s", path,
                        "the accounts read before it broke" if data else "nothing (only the Pi can get in)")
        _cache.update(mtime=mtime, data=data, path=path)
        return data


def _write(path: Path, text: str):
    """Write a file in one go: a half-written file is never left in its place."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name.split(".")[0] + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _save(data: dict):
    """Save users.json (and the spare copy, users.json.bak). Call it holding _lock, with
    a copy of what _load gave (see _changing)."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=1)
    with _lock:
        _write(users_file(), text)
        _write(backup_file(), text)
        _cache.update(mtime=None)


@contextmanager
def _changing():
    """A copy of the accounts to change and save, one change at a time. Nothing changes
    in memory if the change stops half way with an error."""
    with _lock:
        data = _load()
        yield copy.deepcopy(data) if data else None


def damaged() -> bool:
    """users.json is there but can't be read, and there's no good copy to use instead."""
    return _load() is None and users_file().exists()


def enabled() -> bool:
    """Accounts are on. A damaged users.json still counts as on, so nobody gets in
    without logging in just because the file broke."""
    return _load() is not None or users_file().exists()


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


DAMAGED = ("data/users.json is damaged (and so is its copy, users.json.bak), so nobody can log in. "
           "On the Pi or server, put back users.json from a backup, or delete it to turn accounts off.")


def _secret(password: str) -> tuple[str, str]:
    """A new salt and hash. Slow on purpose: do it before taking _lock."""
    salt = secrets.token_hex(16)
    return salt, _hash(password, salt)


def _account(name, secret: tuple[str, str], perms, session=1) -> dict:
    salt, hashed = secret
    return {"name": str(name or "").strip()[:40], "perms": perms, "salt": salt,
            "hash": hashed, "session": session, "created": time.strftime("%Y-%m-%d %H:%M")}


def _new_session(data: dict, username: str) -> int:
    """Where a new account's logins start. A username that was removed starts after its
    old logins, so a phone still holding one doesn't get into the new account."""
    return int((data.get("retired") or {}).pop(username, 0)) + 1


def setup(username, password, name="") -> str:
    """Turn accounts on: the first account is the owner, and keeps the existing cards."""
    if users_file().exists():
        raise ValueError(DAMAGED if damaged() else "Accounts are on already")
    username = _clean_username(username)
    secret = _secret(_clean_password(password))
    with _lock:
        if users_file().exists():
            raise ValueError("Accounts are on already")
        account = _account(name or username, secret, list(PERMS)) | {"owner": True}
        _save({"secret": secrets.token_hex(32), "users": {username: account}})
    return username


def add(username, password, name="", perms=None, role="member") -> str:
    if not _load():
        raise ValueError("Turn accounts on first")
    username = _clean_username(username)
    secret = _secret(_clean_password(password))
    with _changing() as data:
        if not data:
            raise ValueError("Turn accounts on first")
        if username in data["users"]:
            raise ValueError("Someone already has that username")
        data["users"][username] = _account(name or username, secret, _clean_perms(perms, role),
                                           _new_session(data, username))
        _save(data)
    home(username).mkdir(parents=True, exist_ok=True)
    return username


# --- Invite links ----------------------------------------------------------------------------
# An admin makes a link (Settings, People and permissions) and sends it. Whoever opens it
# picks their own username and password and joins as a member (or viewer). Only a hash of
# each link's code is kept, so the links can't be read back out of users.json or a backup.

INVITE_ROLES = ("member", "viewer")
INVITE_DAYS = (1, 7, 30)
INVITE_USES = (1, 5, 20)


def _code_id(code: str) -> str:
    return hashlib.sha256(str(code or "").encode()).hexdigest()


def create_invite(by: str, role="member", uses=1, days=7, note="") -> str:
    """A new invite link's code (shown once)."""
    if not _load():
        raise ValueError("Turn accounts on first")
    if role not in INVITE_ROLES:
        raise ValueError("An invite makes a member or a viewer. Make admins on the People list")
    uses = int(uses) if str(uses).isdigit() and int(uses) in INVITE_USES else 1
    days = int(days) if str(days).isdigit() and int(days) in INVITE_DAYS else 7
    code = secrets.token_urlsafe(18)
    with _changing() as data:
        if not data:
            raise ValueError("Turn accounts on first")
        invites = _live_invites(data)
        invites[_code_id(code)] = {"role": role, "uses": uses, "used": [], "by": by or "",
                                   "note": str(note or "").strip()[:40], "created": int(time.time()),
                                   "expires": int(time.time()) + days * 86400}
        data["invites"] = invites
        _save(data)
    return code


def _live_invites(data) -> dict:
    now = time.time()
    return {k: v for k, v in (data.get("invites") or {}).items()
            if isinstance(v, dict) and v.get("expires", 0) > now and len(v.get("used", [])) < v.get("uses", 1)}


def invites() -> list[dict]:
    data = _load()
    if not data:
        return []
    return [{"id": k[:12], "role": v["role"], "uses": v["uses"], "used": v.get("used", []), "by": v.get("by", ""),
             "note": v.get("note", ""), "created": v["created"], "expires": v["expires"]}
            for k, v in sorted(_live_invites(data).items(), key=lambda kv: -kv[1]["created"])]


def check_invite(code) -> dict | None:
    data = _load()
    invite = data and _live_invites(data).get(_code_id(code))
    if not invite:
        return None
    by = get(invite.get("by")) or {}
    return {"role": invite["role"], "by": by.get("name") or invite.get("by") or "", "expires": invite["expires"]}


def cancel_invite(invite_id: str):
    with _changing() as data:
        if not data:
            return
        invites = _live_invites(data)
        gone = [k for k in invites if k[:12] == str(invite_id or "")]
        if not gone:
            raise ValueError("That invite is used up, ran out or was cancelled already")
        for k in gone:
            del invites[k]
        data["invites"] = invites
        _save(data)


def join(code, username, password, name="") -> str:
    """Make an account from an invite link. The username can't be one someone has, or one
    whose cards are still kept (someone removed who had cards)."""
    if not _load():
        raise ValueError("This sorter doesn't use accounts")
    username = _clean_username(username)
    secret = _secret(_clean_password(password))
    with _changing() as data:
        if not data:
            raise ValueError("This sorter doesn't use accounts")
        invites = _live_invites(data)
        key = _code_id(code)
        invite = invites.get(key)
        if not invite:
            raise ValueError("This invite link is used up, ran out or was cancelled. Ask for a new one")
        folder = config.DATA_DIR / "users" / username
        if username in data["users"] or (folder.is_dir() and any(folder.iterdir())):
            raise ValueError("Someone already has that username: pick another")
        data["users"][username] = _account(name or username, secret, list(ROLES[invite["role"]]),
                                           _new_session(data, username)) | {"invited_by": invite.get("by", "")}
        invite.setdefault("used", []).append(username)
        data["invites"] = _live_invites(data)
        _save(data)
    home(username).mkdir(parents=True, exist_ok=True)
    return username


def update(username, name=None, perms=None, password=None):
    """Change someone's name, permissions or password. A new password logs them out
    everywhere else. Everything is checked first: a refused change changes nothing."""
    data = _load()
    account = data and data["users"].get(username)
    if not account:
        raise ValueError("There's no account called that")
    if perms is not None:
        perms = _clean_perms(perms)
    secret = _secret(_clean_password(password)) if password is not None else None
    with _changing() as data:
        account = data and data["users"].get(username)
        if not account:
            raise ValueError("There's no account called that")
        if perms is not None:
            if account.get("owner") and "admin" not in perms:
                raise ValueError("The owner always stays an admin")
            if "admin" in account["perms"] and "admin" not in perms and _admins(data) == [username]:
                raise ValueError("Keep at least one admin")
            account["perms"] = perms
        if name is not None:
            account["name"] = str(name).strip()[:40] or username
        if secret is not None:
            account["salt"], account["hash"] = secret
            account["session"] = int(account.get("session", 1)) + 1
        _save(data)


def remove(username):
    """Take the account away. Their cards stay in data/users/<username>/, so adding the
    same username again brings the cards back (but not the old logins: a phone that was
    logged in as them stays logged out)."""
    with _changing() as data:
        account = data and data["users"].get(username)
        if not account:
            raise ValueError("There's no account called that")
        if account.get("owner"):
            raise ValueError("The owner's account can't be removed")
        data.setdefault("retired", {})[username] = int(account.get("session", 1))
        del data["users"][username]
        _save(data)


def log_out_everywhere(username):
    with _changing() as data:
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


# --- Too many wrong passwords ---------------------------------------------------------------
# After TRIES wrong tries in a row from one place it waits PAUSE seconds, then twice as long
# after each wrong one after that, up to MAX_PAUSE. A right one clears it, and so does a
# quiet spell (`forget` seconds after the last try). The PIN lock (security.py) uses the same.

MAX_PAUSE = 15 * 60
FORGET = 15 * 60                 # a login's wrong tries are forgotten this long after the last one
USER_CAP, USER_SPAN = 20, 10 * 60   # wrong passwords for one username, from anywhere, in USER_SPAN


def _pause_after(count: int) -> float:
    return 0 if count < TRIES else min(PAUSE * 2 ** (count - TRIES), MAX_PAUSE)


def _wait(book: dict, who: str, forget: float, now: float) -> int:
    count, last = book.get(who, (0, 0.0))
    if now - last > forget:
        return 0
    return max(0, math.ceil(_pause_after(count) - (now - last)))


def _prune(book: dict, now: float, forget: float):
    if len(book) > 500:
        for k in [k for k, (_, last) in book.items() if now - last > forget]:
            del book[k]


def take_try(who: str, book: dict | None = None, forget: float = FORGET, also=None) -> int:
    """Count a try before it's checked, so tries sent all at once can't slip past the
    limit while the first ones are still being checked. Returns 0 to go ahead, or how many
    seconds to wait. `also` is (key, cap, span): a second limit, at most `cap` tries in
    `span` seconds under that key (span no longer than forget)."""
    book = _tries if book is None else book
    with _lock:
        now = time.time()
        _prune(book, now, forget)
        wait = _wait(book, who, forget, now)
        if wait:
            return wait
        if also:
            key, cap, span = also
            count, start = book.get(key, (0, now))
            if now - start > span:
                count, start = 0, now
            if count >= cap:
                return max(1, math.ceil(span - (now - start)))
            book[key] = (count + 1, start)
        count, last = book.get(who, (0, 0.0))
        book[who] = ((0 if now - last > forget else count) + 1, now)
        return 0


def clear_tries(who: str, book: dict | None = None, also_key: str | None = None):
    """A right password or PIN: forget the wrong ones from there (and take this one back
    off the second limit, which only counts wrong ones)."""
    book = _tries if book is None else book
    with _lock:
        book.pop(who, None)
        if also_key in book:
            count, start = book[also_key]
            book[also_key] = (max(0, count - 1), start)


def login_limit(username: str):
    """The second limit for a login: wrong passwords for this username from anywhere."""
    return ("user:" + username, USER_CAP, USER_SPAN) if get(username) else None


def too_many_tries(who: str) -> int:
    """Seconds `who` still has to wait (0: none). For invite links, whose codes are too long
    to guess, so they're counted after the check (see note_try)."""
    with _lock:
        return _wait(_tries, who, FORGET, time.time())


def note_try(who: str, ok: bool):
    with _lock:
        if ok:
            _tries.pop(who, None)
        else:
            now = time.time()
            _prune(_tries, now, FORGET)
            count, last = _tries.get(who, (0, 0.0))
            _tries[who] = ((0 if now - last > FORGET else count) + 1, now)


def wait_words(seconds: int) -> str:
    """How long to wait, in words: "30 seconds", "2 minutes"."""
    if seconds < 60:
        return f"{seconds} second" + ("" if seconds == 1 else "s")
    minutes = math.ceil(seconds / 60)
    return f"{minutes} minute" + ("" if minutes == 1 else "s")


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
        # users.json is damaged: logins.py lets only the Pi itself and the server's machine
        # key through then, so the Pi (and stopping its machine) keeps working.
        return damaged()
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
