"""An optional PIN lock for the web app (set it on the Settings page, /settings).

With a PIN set, every page and every button asks for the PIN first, so other people on
the Wi-Fi (or anyone who finds a shared link) can't change your collection or move the
machine. A phone or laptop that typed the right PIN stays unlocked for 30 days.

The Pi itself is never locked out: requests from the Pi (the auto-update check, the
`mtg` command) always go through, as long as they didn't come in through a tunnel.

Forgot the PIN? On the Pi, delete data/pin.json (rm ~/HomeLab/mtg-sorter/data/pin.json)
and the lock is gone.
"""

import hashlib
import hmac
import json
import secrets
import threading
import time
from pathlib import Path

from flask import jsonify, make_response, request, send_from_directory

from . import config

COOKIE = "mtg_unlocked"
DAYS = 30
TRIES = 5            # wrong PINs in a row before a pause...
PAUSE = 30           # ...of this many seconds
OPEN_PATHS = {"/lock", "/api/unlock", "/api/lock", "/api/health", "/favicon.ico"}
_tries: dict[str, tuple[int, float]] = {}
_lock = threading.Lock()


def pin_file() -> Path:
    return config.DATA_DIR / "pin.json"


def _load() -> dict | None:
    try:
        data = json.loads(pin_file().read_text())
        return data if data.get("hash") and data.get("salt") and data.get("secret") else None
    except (OSError, ValueError, AttributeError):
        return None


def enabled() -> bool:
    return _load() is not None


def _hash(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), 200_000).hex()


def check_pin_format(pin) -> str:
    pin = str(pin or "").strip()
    if not pin.isdigit() or not 4 <= len(pin) <= 8:
        raise ValueError("The PIN has to be 4 to 8 digits")
    return pin


def set_pin(pin) -> dict:
    pin = check_pin_format(pin)
    salt = secrets.token_hex(16)
    data = {"salt": salt, "hash": _hash(pin, salt), "secret": secrets.token_hex(32),
            "set": time.strftime("%Y-%m-%d %H:%M")}
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = pin_file().with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(pin_file())
    return data


def remove_pin():
    try:
        pin_file().unlink()
    except FileNotFoundError:
        pass


def right_pin(pin) -> bool:
    data = _load()
    return bool(data) and hmac.compare_digest(_hash(str(pin or "").strip(), data["salt"]), data["hash"])


def _token(data: dict, expires: int) -> str:
    sig = hmac.new(bytes.fromhex(data["secret"]), str(expires).encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{sig}"


def has_valid_cookie() -> bool:
    data = _load()
    if not data:
        return True
    try:
        expires, _ = request.cookies.get(COOKIE, "").split(".", 1)
        return int(expires) > time.time() and hmac.compare_digest(request.cookies[COOKIE], _token(data, int(expires)))
    except (ValueError, KeyError):
        return False


def is_local() -> bool:
    """A request from the Pi itself, not forwarded by a tunnel (Cloudflare, nginx)."""
    forwarded = any(h in request.headers for h in ("X-Forwarded-For", "CF-Connecting-IP", "X-Real-IP", "Forwarded"))
    return request.remote_addr in ("127.0.0.1", "::1") and not forwarded


def allowed() -> bool:
    return not enabled() or is_local() or has_valid_cookie()


def _grant(resp, data):
    expires = int(time.time()) + DAYS * 86400
    resp.set_cookie(COOKIE, _token(data, expires), max_age=DAYS * 86400, httponly=True, samesite="Lax")
    return resp


def install(app, web_dir):
    """Guard every route, and add the lock page and its API."""

    @app.before_request
    def guard():
        path = request.path
        if path in OPEN_PATHS or path.startswith("/static/") or allowed():
            return None
        if path.startswith("/api/") or path.startswith("/captures/") or path.endswith(".mjpg"):
            return jsonify({"error": "Locked: type the PIN first", "locked": True}), 401
        resp = make_response(send_from_directory(web_dir, "lock.html"))
        resp.status_code = 401
        return resp

    @app.get("/lock")
    def lock_page():
        return send_from_directory(web_dir, "lock.html")

    @app.get("/api/lock")
    def lock_state():
        return jsonify({"enabled": enabled(), "unlocked": allowed(), "local": is_local()})

    @app.post("/api/unlock")
    def unlock():
        who = request.remote_addr or "?"
        with _lock:
            count, since = _tries.get(who, (0, 0.0))
            if count >= TRIES and time.time() - since < PAUSE:
                return jsonify({"error": f"Too many wrong PINs. Wait {PAUSE} seconds and try again"}), 429
        pin = (request.get_json(force=True, silent=True) or {}).get("pin")
        data = _load()
        if not data:
            return jsonify({"ok": True})
        if not right_pin(pin):
            with _lock:
                count, _ = _tries.get(who, (0, 0.0))
                _tries[who] = (count % TRIES + 1, time.time())
            return jsonify({"error": "That's not the PIN"}), 403
        with _lock:
            _tries.pop(who, None)
        return _grant(jsonify({"ok": True}), data)

    @app.post("/api/lock/set")
    def lock_set():
        """Set or change the PIN (needs the page unlocked already, which the guard checks)."""
        try:
            data = set_pin((request.get_json(force=True, silent=True) or {}).get("pin"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return _grant(jsonify({"enabled": True}), data)   # this device stays unlocked; others must type it

    @app.post("/api/lock/remove")
    def lock_remove():
        remove_pin()
        resp = jsonify({"enabled": False})
        resp.delete_cookie(COOKIE)
        return resp

    @app.post("/api/lock/now")
    def lock_now():
        resp = jsonify({"ok": True})
        resp.delete_cookie(COOKIE)
        return resp
