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
import ipaddress
import json
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit

from flask import jsonify, make_response, request, send_from_directory

from . import accounts, config
from .remote_machine import server_allowed

COOKIE = "mtg_unlocked"
DAYS = 30
TRIES = accounts.TRIES   # wrong PINs in a row before a pause...
PAUSE = accounts.PAUSE   # ...of this many seconds, twice as long after each wrong one after that
FORGET = 24 * 3600   # wrong PINs are forgotten a day after the last one
ALL_CAP, ALL_SPAN = 50, 10 * 60   # wrong PINs from everywhere together, in ALL_SPAN seconds
OPEN_PATHS = {"/lock", "/api/unlock", "/api/lock", "/api/health", "/favicon.ico"}
_tries: dict[str, tuple[int, float]] = {}


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


def client_ip() -> str:
    """Who is asking, for counting wrong passwords and PINs. A tunnel (cloudflared) reaches
    the app from the same address for everyone, so behind one the address it passes on
    (CF-Connecting-IP) is used. Only from a local or private address, which is where a
    tunnel runs: from anywhere else the header could be made up."""
    addr = request.remote_addr or "?"
    try:
        here = ipaddress.ip_address(addr)
    except ValueError:
        return addr
    if here.is_loopback or here.is_private:
        try:
            return str(ipaddress.ip_address(request.headers.get("CF-Connecting-IP", "").strip()))
        except ValueError:
            pass
    return addr


def via_https() -> bool:
    """The browser reached the app over https: directly, or through a tunnel on the Pi or
    server itself (Cloudflare, Tailscale Serve) that turns it into plain http. Login cookies
    are then marked Secure, so the browser never sends them over plain http."""
    if request.is_secure:
        return True
    proto = request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip().lower()
    return request.remote_addr in ("127.0.0.1", "::1") and proto == "https"


def from_another_site() -> bool:
    """A change (POST and the like) that a page on some other website made the browser send.
    The browser says where a request came from (Sec-Fetch-Site; older ones only Origin).
    Requests with neither (the mtg command, the server driving the Pi) aren't from a page."""
    site = request.headers.get("Sec-Fetch-Site", "").strip().lower()
    if site in ("same-origin", "none"):
        return False
    if site == "cross-site":
        return True
    origin = request.headers.get("Origin")
    if origin is None:
        return bool(site)    # same-site without an Origin: can't tell, so no
    if origin == "null":
        return True
    host = urlsplit(origin).netloc.lower()
    forwarded = request.headers.get("X-Forwarded-Host", "").split(",")[0].strip().lower()
    return host not in (request.host.lower(), forwarded) or not host


def allowed() -> bool:
    return not enabled() or is_local() or has_valid_cookie()


def _grant(resp, data):
    expires = int(time.time()) + DAYS * 86400
    resp.set_cookie(COOKIE, _token(data, expires), max_age=DAYS * 86400, httponly=True, samesite="Lax",
                    secure=via_https())
    return resp


def install(app, web_dir):
    """Guard every route, and add the lock page and its API."""

    def same_site_only():
        """Another website can't press this app's buttons through your browser (with no PIN
        or accounts, the Pi would otherwise do whatever any web page asks)."""
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and from_another_site():
            return jsonify({"error": "Blocked a request from another website"}), 403
        return None

    # First of all the checks, before the login (logins.py) and the PIN.
    app.before_request_funcs.setdefault(None, []).insert(0, same_site_only)

    @app.before_request
    def guard():
        path = request.path
        if accounts.enabled():   # logins (logins.py) do the PIN's job then
            return None
        if server_allowed():     # the server driving this Pi's machine (remote_machine.py)
            return None
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
        if accounts.enabled():
            return jsonify({"enabled": False, "unlocked": True, "local": is_local(), "accounts": True})
        return jsonify({"enabled": enabled(), "unlocked": allowed(), "local": is_local()})

    @app.post("/api/unlock")
    def unlock():
        who = client_ip()
        pin = (request.get_json(force=True, silent=True) or {}).get("pin")
        data = _load()
        if not data:
            return jsonify({"ok": True})
        # Counted before the slow check, so PINs sent all at once can't slip past the limit.
        wait = accounts.take_try(who, _tries, FORGET, also=("*", ALL_CAP, ALL_SPAN))
        if wait:
            return jsonify({"error": f"Too many wrong PINs. Wait {accounts.wait_words(wait)} and try again"}), 429
        if not right_pin(pin):
            return jsonify({"error": "That's not the PIN"}), 403
        accounts.clear_tries(who, _tries, "*")
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
