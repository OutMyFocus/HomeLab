"""Logging in, and who may open what, once accounts are on (see accounts.py).

Every request names its person by the login cookie. Pages and buttons need a permission:
the tables below say which. Anything not listed needs nothing for looking (GET) and
admin for changing (POST), so a new button stays safe until it's listed here.
"""

import time
from urllib.parse import quote

from flask import jsonify, make_response, redirect, request, send_from_directory

from . import accounts, config, security, system
from .remote_machine import server_allowed

OPEN_PATHS = {"/login", "/api/login", "/api/logout", "/api/me", "/api/health", "/favicon.ico",
              "/lock", "/api/lock", "/join", "/api/join"}

# Looking at these needs a permission (path, or path prefix ending in /).
GET_NEEDS = [
    ("/maintenance", "admin"), ("/api/system/", "admin"), ("/api/system", "admin"),
    ("/api/accounts", "admin"),
    ("/machine", "machine"), ("/api/machine", "machine"), ("/lights", "machine"), ("/api/lights", "machine"),
    ("/api/training", "machine"), ("/captures/", "machine"),
]
# Pressing these needs a permission. Ones that only look (export, check, preview) need none.
POST_NEEDS = {
    "": ["/api/collection/export", "/api/collection/refresh", "/api/decks/check", "/api/bins/preview",
         "/api/history/export", "/api/password", "/api/logout/everywhere"],
    "scan": ["/api/frame", "/api/camera", "/api/camera/release", "/api/add", "/api/save_all",
             "/api/correct", "/api/undo", "/api/wrong", "/api/photos", "/api/settings"],
    "edit": ["/api/collection/edit", "/api/collection/add", "/api/decks/save", "/api/decks/delete",
             "/api/wishlist/", "/api/alerts", "/api/games/", "/api/trades/", "/api/sources/",
             "/api/history/delete", "/api/vault/import"],
    "machine": ["/api/machine/", "/api/lights", "/api/bins", "/api/train", "/api/forget", "/api/label"],
    "admin": ["/api/system/", "/api/accounts", "/api/vault/run", "/api/lock/"],
}


def _matches(path: str, rule: str) -> bool:
    return path == rule or (rule.endswith("/") and path.startswith(rule)) or path.startswith(rule + "/")


def needed(method: str, path: str) -> str:
    """The permission a request needs: "" for none (just being logged in)."""
    if method in ("GET", "HEAD", "OPTIONS"):
        return next((perm for rule, perm in GET_NEEDS if _matches(path, rule)), "")
    best = None   # the longest matching rule wins
    for perm, rules in POST_NEEDS.items():
        for rule in rules:
            if _matches(path, rule) and (best is None or len(rule) > len(best[0])):
                best = (rule, perm)
    return best[1] if best else "admin"


def who() -> str | None:
    """The logged-in person, or the owner for the Pi itself."""
    if security.is_local():
        return accounts.owner()
    return accounts.user_from_token(request.cookies.get(accounts.COOKIE))


def install(app, web_dir):
    @app.before_request
    def account_guard():
        accounts.set_current(None)
        if not accounts.enabled():
            return None
        if server_allowed():     # the server driving this Pi's machine (remote_machine.py)
            return None
        path = request.path
        username = who()
        accounts.set_current(username)
        if path in OPEN_PATHS or path.startswith("/static/"):
            return None
        api = path.startswith("/api/") or path.startswith("/captures/") or path.endswith(".mjpg")
        if username is None:
            if api:
                return jsonify({"error": "Log in first", "login": True, "locked": True}), 401
            return redirect("/login?next=" + quote(request.full_path.rstrip("?"), safe="/"))
        perm = needed(request.method, path)
        if perm and not accounts.can(perm):
            msg = f"Your account can't do that (it needs the {perm} permission; ask {_admin_name()})"
            if api:
                return jsonify({"error": msg, "forbidden": True}), 403
            resp = make_response(send_from_directory(web_dir, "login.html"))
            resp.status_code = 403
            return resp
        return None

    @app.teardown_request
    def forget_account(_exc=None):
        accounts.set_current(None)

    def _admin_name():
        o = accounts.get(accounts.owner()) or {}
        return o.get("name") or "the owner"

    def body() -> dict:
        js = request.get_json(force=True, silent=True)
        return js if isinstance(js, dict) else {}

    def signed_in(username):
        resp = jsonify({"ok": True, "me": me_info(username)})
        resp.set_cookie(accounts.COOKIE, accounts.session_token(username), max_age=accounts.DAYS * 86400,
                        httponly=True, samesite="Lax", secure=request.is_secure)
        return resp

    def me_info(username):
        if not accounts.enabled():
            return None
        return accounts.public(username) if username else None

    @app.get("/login")
    def login_page():
        return send_from_directory(web_dir, "login.html")

    @app.get("/api/me")
    def me():
        username = accounts.current()
        return jsonify({"accounts": accounts.enabled(), "me": me_info(username),
                        "perms": {p: accounts.can(p) for p in accounts.PERMS} if (username or not accounts.enabled()) else {},
                        "local": security.is_local()})

    @app.post("/api/login")
    def login():
        if not accounts.enabled():
            return jsonify({"ok": True, "me": None})
        where = request.remote_addr or "?"
        if accounts.too_many_tries(where):
            return jsonify({"error": f"Too many wrong passwords. Wait {accounts.PAUSE} seconds and try again"}), 429
        js = body()
        username = str(js.get("username") or "").strip().lower()
        ok = accounts.check_password(username, js.get("password"))
        accounts.note_try(where, ok)
        if not ok:
            return jsonify({"error": "That username and password don't match"}), 403
        return signed_in(username)

    @app.post("/api/logout")
    def logout():
        resp = jsonify({"ok": True})
        resp.delete_cookie(accounts.COOKIE)
        return resp

    @app.post("/api/logout/everywhere")
    def logout_everywhere():
        username = accounts.current()
        if not username:
            return jsonify({"error": "Log in first"}), 401
        accounts.log_out_everywhere(username)
        return signed_in(username)   # ...but stay logged in here

    @app.post("/api/password")
    def change_password():
        username = accounts.current()
        if not username:
            return jsonify({"error": "Log in first"}), 401
        js = body()
        if not accounts.check_password(username, js.get("old")):
            return jsonify({"error": "Your current password isn't right"}), 403
        try:
            accounts.update(username, password=js.get("new"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return signed_in(username)

    # --- Turning accounts on, and managing them (admins) ---

    @app.get("/api/accounts")
    def accounts_list():
        return jsonify({"accounts": accounts.enabled(), "users": accounts.everyone(), "me": accounts.current(),
                        "perms": list(accounts.PERMS), "roles": accounts.ROLES, "invites": accounts.invites()})

    # --- Invite links: an admin makes one, the person signs themselves up ---

    @app.post("/api/accounts/invite")
    def invite_make():
        js = body()
        try:
            code = accounts.create_invite(accounts.current() or accounts.owner(), js.get("role") or "member",
                                          js.get("uses", 1), js.get("days", 7), js.get("note") or "")
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"code": code, "path": "/join#" + code, "invites": accounts.invites()})

    @app.post("/api/accounts/invite/cancel")
    def invite_cancel():
        try:
            accounts.cancel_invite(body().get("id"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"invites": accounts.invites()})

    @app.get("/join")
    def join_page():
        return send_from_directory(web_dir, "join.html")

    @app.post("/api/join")
    def join():
        """{code} checks a link; {code, username, password, name} makes the account and
        logs it in."""
        where = request.remote_addr or "?"
        if accounts.too_many_tries(where):
            return jsonify({"error": f"Too many tries. Wait {accounts.PAUSE} seconds and try again"}), 429
        js = body()
        invite = accounts.check_invite(js.get("code"))
        if invite is None:
            accounts.note_try(where, False)
            return jsonify({"error": "This invite link is used up, ran out or was cancelled. Ask for a new one"}), 404
        if "username" not in js:
            return jsonify({"invite": invite})
        try:
            username = accounts.join(js.get("code"), js.get("username"), js.get("password"), js.get("name") or "")
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return signed_in(username)

    @app.post("/api/accounts/setup")
    def accounts_setup():
        """Turn accounts on. Whoever does it becomes the owner and keeps every card already
        here. A backup of everything is saved first."""
        if accounts.enabled():
            return jsonify({"error": "Accounts are on already"}), 400
        js = body()
        try:
            accounts._clean_username(js.get("username"))
            accounts._clean_password(js.get("password"))
            saved = save_backup("before-accounts")
            username = accounts.setup(js.get("username"), js.get("password"), js.get("name") or "")
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        security.remove_pin()   # the login does the PIN's job now
        accounts.set_current(username)
        resp = signed_in(username)
        resp.set_data(jsonify({"ok": True, "me": me_info(username), "backup": saved}).get_data())
        return resp

    @app.post("/api/accounts/add")
    def accounts_add():
        js = body()
        try:
            username = accounts.add(js.get("username"), js.get("password"), js.get("name") or "",
                                    js.get("perms"), js.get("role") or "member")
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"added": username, "users": accounts.everyone()})

    @app.post("/api/accounts/update")
    def accounts_update():
        js = body()
        username = str(js.get("username") or "")
        perms = js.get("perms")
        if js.get("role") in accounts.ROLES and perms is None:
            perms = accounts.ROLES[js["role"]]
        try:
            accounts.update(username, name=js.get("name"), perms=perms, password=js.get("password") or None)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"users": accounts.everyone()})

    @app.post("/api/accounts/remove")
    def accounts_remove():
        username = str(body().get("username") or "")
        if username == accounts.current():
            return jsonify({"error": "You can't remove your own account"}), 400
        try:
            accounts.remove(username)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"users": accounts.everyone()})


def save_backup(label: str) -> str:
    """A zip of everything in data/backups, before a big change. Returns its name."""
    folder = config.DATA_DIR / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / time.strftime(f"{label}-%Y%m%d-%H%M%S.zip")
    dest.write_bytes(system.make_backup(with_scans=False).getvalue())
    return dest.name
