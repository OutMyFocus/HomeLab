"""User accounts: logging in, permissions, and everyone keeping their own cards."""

import csv
import hashlib
import io
import zipfile

import pytest

from app import Scanner, create_app
from mtgscanner import accounts, config, decks
from test_scanner import db  # noqa: F401  (db is a fixture)

AWAY = {"REMOTE_ADDR": "10.0.0.5"}   # a phone, not the sorter itself


@pytest.fixture
def app(db, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "USD_TO_CAD", 1.5)
    scanner = Scanner(db, None, source=None)
    return create_app(scanner)


def device(app):
    c = app.test_client()
    c.environ_base.update(AWAY)
    return c


def names(path):
    return [r["Name"] for r in csv.DictReader(path.open())] if path.exists() else []


def turn_on(app, tmp_path):
    """Nic already has cards, then turns accounts on and adds Sam."""
    nic = device(app)
    assert nic.post("/api/add", json={"id": "id1"}).status_code == 200          # before accounts
    assert names(tmp_path / "collection.csv") == ["Card 1"]
    r = nic.post("/api/accounts/setup", json={"username": "Nic", "password": "secret-1", "name": "Nic"})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["backup"].startswith("before-accounts-")
    assert nic.post("/api/accounts/add", json={"username": "sam", "password": "sammy-1", "name": "Sam"}).status_code == 200
    sam = device(app)
    assert sam.post("/api/login", json={"username": "sam", "password": "sammy-1"}).status_code == 200
    return nic, sam


def test_without_accounts_nothing_changes(app):
    c = device(app)
    assert c.get("/api/me").get_json()["accounts"] is False
    assert c.get("/api/collection").status_code == 200
    assert c.get("/machine").status_code == 200


def test_the_owner_keeps_every_card_and_has_every_permission(app, tmp_path):
    nic, sam = turn_on(app, tmp_path)
    me = nic.get("/api/me").get_json()
    assert me["me"]["username"] == "nic" and me["me"]["owner"]
    assert all(me["perms"].values())
    assert [c["name"] for c in nic.get("/api/collection").get_json()["cards"]] == ["Card 1"]
    assert (tmp_path / "backups").is_dir()
    assert not (tmp_path / "users" / "nic").exists()   # the owner's files didn't move


def test_everyone_has_their_own_cards(app, tmp_path):
    nic, sam = turn_on(app, tmp_path)
    assert sam.get("/api/collection").get_json()["cards"] == []
    sam.post("/api/collection/add", json={"id": "id2"})
    sam.post("/api/decks/save", json={"name": "Sam's deck", "text": "1 Card 2"})
    assert names(tmp_path / "users" / "sam" / "collection.csv") == ["Card 2"]
    assert names(tmp_path / "collection.csv") == ["Card 1"]
    assert [c["name"] for c in nic.get("/api/collection").get_json()["cards"]] == ["Card 1"]
    assert nic.get("/api/decks").get_json()["decks"] == []
    with accounts.acting_as("sam"):
        assert [d["name"] for d in decks.load_decks()] == ["Sam's deck"]


def test_a_phone_scans_into_its_persons_collection(app, tmp_path):
    nic, sam = turn_on(app, tmp_path)
    phone = {"X-Scanner": "sam-phone"}
    r = sam.post("/api/camera", json={"index": "browser", "token": "sam-phone", "name": "Phone camera"}, headers=phone)
    assert r.status_code == 200 and r.get_json()["saving_to"]["username"] == "sam"
    assert sam.post("/api/add", json={"id": "id3"}, headers=phone).status_code == 200
    assert names(tmp_path / "users" / "sam" / "collection.csv") == ["Card 3"]
    # Someone else can't drive Sam's scanner.
    assert nic.post("/api/add", json={"id": "id0"}, headers=phone).status_code == 200   # admins may
    alex_pw = {"username": "alex", "password": "alex-pass", "role": "member"}
    nic.post("/api/accounts/add", json=alex_pw)
    alex = device(app)
    alex.post("/api/login", json=alex_pw)
    assert alex.post("/api/add", json={"id": "id0"}, headers=phone).status_code == 403
    sam.post("/api/camera/release", json={"token": "sam-phone"}, headers=phone)
    app.config["scanners"].pop("sam-phone", None)


def test_photos_without_the_machine_go_to_your_own_cards(app, tmp_path):
    nic, sam = turn_on(app, tmp_path)
    # No phone scanner yet: Sam (no machine permission) gets a scanner of his own.
    assert sam.post("/api/add", json={"id": "id2"}).status_code == 200
    assert names(tmp_path / "users" / "sam" / "collection.csv") == ["Card 2"]
    state = sam.get("/api/state").get_json()
    assert state["saving_to"]["username"] == "sam" and state["status"] == "waiting"
    # Nic uses the machine, which saves into his cards.
    assert nic.post("/api/add", json={"id": "id1"}).get_json()["saving_to"]["username"] == "nic"
    assert names(tmp_path / "collection.csv") == ["Card 1", "Card 1"]


def test_permissions(app, tmp_path):
    nic, sam = turn_on(app, tmp_path)
    assert sam.get("/machine").status_code == 403
    assert sam.post("/api/machine/move", json={}).status_code == 403
    assert sam.get("/api/system").status_code == 403
    assert sam.post("/api/accounts/add", json={"username": "x", "password": "123456"}).status_code == 403
    assert sam.post("/api/camera", json={"index": 0}).status_code == 403
    assert sam.get("/api/collection").status_code == 200
    # A viewer can look but not change anything.
    nic.post("/api/accounts/update", json={"username": "sam", "role": "viewer"})
    assert sam.post("/api/collection/add", json={"id": "id2"}).status_code == 403
    assert sam.post("/api/add", json={"id": "id2"}).status_code == 403
    assert sam.get("/api/collection").status_code == 200
    # Give Sam the machine.
    nic.post("/api/accounts/update", json={"username": "sam", "perms": ["scan", "edit", "machine"]})
    assert sam.get("/machine").status_code == 200
    assert sam.get("/api/me").get_json()["perms"] == {"scan": True, "edit": True, "machine": True, "admin": False}
    # The owner can't lose admin, and the last admin can't be removed.
    assert nic.post("/api/accounts/update", json={"username": "nic", "role": "member"}).status_code == 400
    assert nic.post("/api/accounts/remove", json={"username": "nic"}).status_code == 400


def test_logging_in_and_out(app, tmp_path):
    nic, sam = turn_on(app, tmp_path)
    stranger = device(app)
    assert stranger.get("/api/collection").status_code == 401
    page = stranger.get("/collection")
    assert page.status_code == 302 and page.headers["Location"].startswith("/login?next=/collection")
    assert stranger.post("/api/login", json={"username": "sam", "password": "nope"}).status_code == 403
    # The sorter itself is never locked out (the update check, the mtg command).
    assert app.test_client().get("/api/collection").status_code == 200
    # A new password logs Sam out everywhere else.
    other = device(app)
    other.post("/api/login", json={"username": "sam", "password": "sammy-1"})
    assert sam.post("/api/password", json={"old": "sammy-1", "new": "sammy-2"}).status_code == 200
    assert sam.get("/api/collection").status_code == 200
    assert other.get("/api/collection").status_code == 401
    sam.post("/api/logout")
    assert sam.get("/api/collection").status_code == 401


def test_removed_people_keep_their_cards(app, tmp_path):
    nic, sam = turn_on(app, tmp_path)
    sam.post("/api/collection/add", json={"id": "id2"})
    assert nic.post("/api/accounts/remove", json={"username": "sam"}).status_code == 200
    assert sam.get("/api/collection").status_code == 401
    nic.post("/api/accounts/add", json={"username": "sam", "password": "sammy-9"})
    sam.post("/api/login", json={"username": "sam", "password": "sammy-9"})
    assert [c["name"] for c in sam.get("/api/collection").get_json()["cards"]] == ["Card 2"]


def test_backups_hold_everyone(app, tmp_path):
    nic, sam = turn_on(app, tmp_path)
    sam.post("/api/collection/add", json={"id": "id2"})
    z = zipfile.ZipFile(io.BytesIO(nic.get("/api/system/backup").data))
    assert {"collection.csv", "users.json", "users/sam/collection.csv"} <= set(z.namelist())


def test_pages_that_were_not_listed_need_admin_to_change():
    from mtgscanner.logins import needed
    assert needed("POST", "/api/some/new/button") == "admin"
    assert needed("POST", "/api/bins/preview") == ""
    assert needed("POST", "/api/bins") == "machine"
    assert needed("POST", "/api/camera/release") == "scan"
    assert needed("POST", "/api/wishlist/add") == "edit"
    assert needed("GET", "/api/collection") == ""
    assert needed("GET", "/maintenance") == "admin"


def test_invite_links(app, tmp_path):
    nic, sam = turn_on(app, tmp_path)
    # Only admins make invites, and an invite can't make an admin.
    assert sam.post("/api/accounts/invite", json={}).status_code == 403
    assert nic.post("/api/accounts/invite", json={"role": "admin"}).status_code == 400
    made = nic.post("/api/accounts/invite", json={"role": "member", "uses": 1, "note": "Alex"}).get_json()
    code = made["code"]
    assert made["path"] == "/join#" + code
    assert code not in (tmp_path / "users.json").read_text()   # only its hash is kept
    friend = device(app)
    assert friend.get("/join").status_code == 200                  # no login needed
    check = friend.post("/api/join", json={"code": code}).get_json()
    assert check["invite"]["role"] == "member" and check["invite"]["by"] == "Nic"
    assert friend.post("/api/join", json={"code": "wrong"}).status_code == 404
    # The username of someone removed (whose cards are still kept) can't be taken.
    sam.post("/api/collection/add", json={"id": "id2"})
    nic.post("/api/accounts/remove", json={"username": "sam"})
    assert friend.post("/api/join", json={"code": code, "username": "sam", "password": "alex-pass"}).status_code == 400
    assert friend.post("/api/join", json={"code": code, "username": "nic", "password": "alex-pass"}).status_code == 400
    r = friend.post("/api/join", json={"code": code, "username": "Alex", "password": "alex-pass", "name": "Alex"})
    assert r.status_code == 200, r.get_json()
    me = friend.get("/api/me").get_json()
    assert me["me"]["username"] == "alex" and me["perms"] == {"scan": True, "edit": True, "machine": False, "admin": False}
    assert friend.get("/api/collection").get_json()["cards"] == []
    # Used up: the next person can't use it, and it's gone from the list.
    assert device(app).post("/api/join", json={"code": code, "username": "jo", "password": "jo-pass1"}).status_code == 404
    assert nic.get("/api/accounts").get_json()["invites"] == []


def test_invites_for_several_people_and_cancelling(app, tmp_path):
    nic, _ = turn_on(app, tmp_path)
    code = nic.post("/api/accounts/invite", json={"role": "viewer", "uses": 5}).get_json()["code"]
    for name in ("ann", "bob"):
        assert device(app).post("/api/join", json={"code": code, "username": name, "password": "pass-123"}).status_code == 200
    [inv] = nic.get("/api/accounts").get_json()["invites"]
    assert inv["used"] == ["ann", "bob"] and inv["uses"] == 5
    assert accounts.get("ann")["perms"] == []
    assert nic.post("/api/accounts/invite/cancel", json={"id": inv["id"]}).status_code == 200
    assert device(app).post("/api/join", json={"code": code, "username": "cy", "password": "pass-123"}).status_code == 404


# --- Keeping logins safe --------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fresh_tries():
    """Wrong-password counts are kept in memory: start every test without any."""
    from mtgscanner import security
    accounts._tries.clear()
    security._tries.clear()
    yield
    accounts._tries.clear()
    security._tries.clear()


def test_too_many_wrong_passwords_pause(app, tmp_path):
    turn_on(app, tmp_path)
    stranger = device(app)
    for _ in range(accounts.TRIES):
        assert stranger.post("/api/login", json={"username": "sam", "password": "nope"}).status_code == 403
    r = stranger.post("/api/login", json={"username": "sam", "password": "sammy-1"})
    assert r.status_code == 429 and "Wait 30 seconds" in r.get_json()["error"]
    # Somewhere else isn't paused, and wrong invite links have a count of their own.
    other = app.test_client()
    other.environ_base.update({"REMOTE_ADDR": "10.0.0.6"})
    for _ in range(accounts.TRIES):
        assert other.post("/api/join", json={"code": "wrong"}).status_code == 404
    assert other.post("/api/login", json={"username": "sam", "password": "sammy-1"}).status_code == 200


def test_each_tunnel_visitor_has_their_own_count(app, tmp_path):
    turn_on(app, tmp_path)
    tunnel = app.test_client()
    guesser = {"REMOTE_ADDR": "127.0.0.1", "HTTP_CF_CONNECTING_IP": "1.2.3.4"}
    for _ in range(accounts.TRIES):
        tunnel.post("/api/login", json={"username": "sam", "password": "nope"}, environ_base=guesser)
    assert tunnel.post("/api/login", json={"username": "sam", "password": "nope"}, environ_base=guesser).status_code == 429
    friend = {"REMOTE_ADDR": "127.0.0.1", "HTTP_CF_CONNECTING_IP": "5.6.7.8"}
    assert tunnel.post("/api/login", json={"username": "sam", "password": "sammy-1"}, environ_base=friend).status_code == 200
    # From a public address the header could be made up, so it isn't used.
    faker = app.test_client()
    for n in range(accounts.TRIES):
        faker.post("/api/login", json={"username": "sam", "password": "nope"},
                   environ_base={"REMOTE_ADDR": "8.8.8.8", "HTTP_CF_CONNECTING_IP": f"9.9.9.{n}"})
    assert faker.post("/api/login", json={"username": "sam", "password": "nope"},
                      environ_base={"REMOTE_ADDR": "8.8.8.8", "HTTP_CF_CONNECTING_IP": "9.9.9.99"}).status_code == 429


def test_pauses_grow_and_are_forgotten(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(accounts.time, "time", lambda: now[0])
    for _ in range(accounts.TRIES):
        assert accounts.take_try("x") == 0
    assert accounts.take_try("x") == 30
    now[0] += 31
    assert accounts.take_try("x") == 0          # the 6th wrong one...
    assert accounts.take_try("x") == 60         # ...makes the next pause twice as long
    now[0] += 61
    accounts.take_try("x")
    now[0] += 121
    accounts.take_try("x")
    assert accounts.take_try("x") == 240
    waits = []
    for _ in range(6):                          # never longer than MAX_PAUSE
        now[0] += accounts.take_try("x")
        assert accounts.take_try("x") == 0
        waits.append(accounts.take_try("x"))
    assert waits[0] == 480 and waits[-1] == accounts.MAX_PAUSE
    now[0] += accounts.FORGET + 1               # a quiet spell forgets them
    for _ in range(accounts.TRIES):
        assert accounts.take_try("x") == 0
    accounts.clear_tries("x")
    assert "x" not in accounts._tries
    assert accounts.wait_words(30) == "30 seconds" and accounts.wait_words(120) == "2 minutes"


def test_tries_sent_all_at_once_are_still_limited():
    import threading
    allowed, start = [], threading.Barrier(20)

    def guess():
        start.wait()
        if accounts.take_try("burst") == 0:
            allowed.append(1)
    threads = [threading.Thread(target=guess) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(allowed) == accounts.TRIES


def test_one_username_has_a_limit_from_everywhere(app, tmp_path, monkeypatch):
    turn_on(app, tmp_path)
    right = {("sam", "sammy-1"), ("nic", "secret-1")}
    monkeypatch.setattr(accounts, "check_password", lambda u, p: (u, p) in right)   # quick
    c = app.test_client()
    for n in range(accounts.USER_CAP):
        here = {"REMOTE_ADDR": "127.0.0.1", "HTTP_CF_CONNECTING_IP": f"1.2.3.{n}"}
        assert c.post("/api/login", json={"username": "sam", "password": "nope"}, environ_base=here).status_code == 403
    here = {"REMOTE_ADDR": "127.0.0.1", "HTTP_CF_CONNECTING_IP": "1.2.4.1"}
    assert c.post("/api/login", json={"username": "sam", "password": "sammy-1"}, environ_base=here).status_code == 429
    # Only Sam's username: Nic can still log in from there.
    assert c.post("/api/login", json={"username": "nic", "password": "secret-1"}, environ_base=here).status_code == 200


def test_pin_guesses_are_limited_from_everywhere_together(app, monkeypatch):
    from mtgscanner import security
    monkeypatch.setattr(security, "_hash", lambda pin, salt: hashlib.sha256((pin + salt).encode()).hexdigest())
    security.set_pin("246813")
    c = app.test_client()
    # A device on the Wi-Fi making up a new tunnel address for every guess still runs out.
    refused = 0
    for n in range(security.ALL_CAP + 5):
        here = {"REMOTE_ADDR": "10.0.0.50", "HTTP_CF_CONNECTING_IP": f"1.2.{n // 250}.{n % 250}"}
        refused += c.post("/api/unlock", json={"pin": f"{n:06d}"}, environ_base=here).status_code == 429
    assert refused == 5


def test_tokens_cant_be_changed_or_used_after_they_run_out(app, tmp_path, monkeypatch):
    turn_on(app, tmp_path)
    token = accounts.session_token("sam")
    assert accounts.user_from_token(token) == "sam"
    user, version, expires, sig = token.split(".")
    assert accounts.user_from_token(f"nic.{version}.{expires}.{sig}") is None
    assert accounts.user_from_token(f"{user}.{version}.{int(expires) + 1}.{sig}") is None
    assert accounts.user_from_token(f"{user}.{int(version) + 1}.{expires}.{sig}") is None
    accounts.log_out_everywhere("sam")
    assert accounts.user_from_token(token) is None                 # an old version
    token = accounts.session_token("sam")
    monkeypatch.setattr(accounts.time, "time", lambda: int(expires) + accounts.DAYS * 86400)
    assert accounts.user_from_token(token) is None                 # ran out


def test_a_refused_password_change_changes_nothing(app, tmp_path):
    nic, sam = turn_on(app, tmp_path)
    before = (tmp_path / "users.json").read_text()
    assert sam.post("/api/password", json={"old": "sammy-1", "new": "abc"}).status_code == 400
    assert nic.post("/api/accounts/update", json={"username": "sam", "password": "abc"}).status_code == 400
    assert nic.post("/api/accounts/update", json={"username": "nic", "name": "X", "role": "member"}).status_code == 400
    assert (tmp_path / "users.json").read_text() == before
    assert accounts.get("nic")["name"] == "Nic"
    accounts.log_out_everywhere("nic")              # another save, then read it all again
    accounts._cache.update(mtime=None, data=None)
    assert accounts.check_password("sam", "sammy-1")
    assert device(app).post("/api/login", json={"username": "sam", "password": "sammy-1"}).status_code == 200


def test_saves_at_the_same_time_all_land(app, tmp_path):
    import json
    import threading
    turn_on(app, tmp_path)
    errors = []

    def bump():
        try:
            for _ in range(5):
                accounts.log_out_everywhere("sam")
        except Exception as e:   # noqa: BLE001
            errors.append(e)
    threads = [threading.Thread(target=bump) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert json.loads((tmp_path / "users.json").read_text())["users"]["sam"]["session"] == 1 + 20
    assert not list(tmp_path.glob("users.*.tmp"))


def test_a_damaged_users_file_keeps_everyone_out_but_the_pi(app, tmp_path):
    _, sam = turn_on(app, tmp_path)
    users = tmp_path / "users.json"
    good = users.read_text()
    # Still running: the accounts read before it broke are kept.
    users.write_text(good[:-3])
    assert sam.get("/api/collection").status_code == 200
    assert device(app).get("/api/collection").status_code == 401
    # Started again with it broken: the spare copy is used.
    accounts._cache.update(mtime=None, data=None)
    assert sam.get("/api/collection").status_code == 200
    # No spare copy either: nobody gets in, and nobody can take it over.
    (tmp_path / "users.json.bak").unlink()
    accounts._cache.update(mtime=None, data=None)
    assert accounts.enabled() and accounts.damaged()
    stranger = device(app)
    r = stranger.get("/api/collection")
    assert r.status_code == 503 and "users.json" in r.get_json()["error"]
    assert stranger.get("/collection").status_code == 503
    assert stranger.post("/api/accounts/setup", json={"username": "evil", "password": "evil-pass"}).status_code == 503
    assert sam.get("/api/collection").status_code == 503
    with pytest.raises(ValueError):
        accounts.setup("evil", "evil-pass")
    # The Pi itself still works...
    pi = app.test_client()
    assert pi.get("/api/collection").status_code == 200
    assert pi.post("/api/accounts/setup", json={"username": "evil", "password": "evil-pass"}).status_code == 400
    assert users.read_text() == good[:-3]
    # ...and deleting the file turns accounts off, as the README says.
    users.unlink()
    assert not accounts.enabled()
    assert stranger.get("/api/collection").status_code == 200


def test_old_logins_dont_come_back_with_the_same_username(app, tmp_path):
    nic, _ = turn_on(app, tmp_path)
    old = accounts.session_token("sam")
    nic.post("/api/accounts/remove", json={"username": "sam"})
    assert nic.post("/api/accounts/add", json={"username": "sam", "password": "sammy-9"}).status_code == 200
    assert accounts.user_from_token(old) is None
    fresh = device(app)
    assert fresh.post("/api/login", json={"username": "sam", "password": "sammy-9"}).status_code == 200
    assert fresh.get("/api/collection").status_code == 200
    # The same through an invite link (allowed when the old folder is empty).
    nic.post("/api/accounts/add", json={"username": "kim", "password": "kimmy-1"})
    old = accounts.session_token("kim")
    nic.post("/api/accounts/remove", json={"username": "kim"})
    code = nic.post("/api/accounts/invite", json={"role": "member"}).get_json()["code"]
    assert device(app).post("/api/join", json={"code": code, "username": "kim", "password": "kimmy-2"}).status_code == 200
    assert accounts.user_from_token(old) is None


def test_only_the_owner_changes_the_owners_password(app, tmp_path):
    nic, sam = turn_on(app, tmp_path)
    nic.post("/api/accounts/update", json={"username": "sam", "role": "admin"})
    r = sam.post("/api/accounts/update", json={"username": "nic", "password": "taken-over"})
    assert r.status_code == 403
    assert nic.get("/api/me").get_json()["me"]["username"] == "nic"     # still logged in
    assert sam.post("/api/accounts/update", json={"username": "nic", "name": "Nicky"}).status_code == 200
    assert nic.post("/api/accounts/update", json={"username": "nic", "password": "secret-2"}).status_code == 200
    assert accounts.check_password("nic", "secret-2")


def test_the_servers_machine_key_works_with_accounts_on(app, tmp_path):
    from mtgscanner.remote_machine import KEY_HEADER, key_file
    turn_on(app, tmp_path)
    key_file().write_text("secret-key\n")
    tower = app.test_client()
    tower.environ_base.update({"REMOTE_ADDR": "10.0.0.49"})
    key = {KEY_HEADER: "secret-key"}
    assert tower.post("/api/camera/focus", json={"cm": 12}).status_code == 401
    assert tower.post("/api/camera/focus", json={"cm": 12}, headers=key).status_code not in (401, 403)
    assert tower.get("/api/collection", headers=key).status_code == 401
    with app.test_request_context("/api/camera/focus", headers=key, environ_base={"REMOTE_ADDR": "10.0.0.49"}):
        app.preprocess_request()
        assert accounts.current() == "nic"


@pytest.mark.parametrize("header", ["HTTP_X_FORWARDED_FOR", "HTTP_CF_CONNECTING_IP", "HTTP_FORWARDED", "HTTP_X_REAL_IP"])
def test_a_tunnel_visitor_is_not_the_owner(app, tmp_path, header):
    turn_on(app, tmp_path)
    c = app.test_client()
    tunnel = {"REMOTE_ADDR": "127.0.0.1", header: "1.2.3.4"}
    assert c.get("/api/collection", environ_base=tunnel).status_code == 401
    page = c.get("/collection", environ_base=tunnel)
    assert page.status_code == 302 and page.headers["Location"].startswith("/login")
    assert c.get("/api/me", environ_base=tunnel).get_json()["me"] is None


def test_login_cookies_are_secure_behind_an_https_tunnel(app, tmp_path):
    turn_on(app, tmp_path)
    login = {"username": "sam", "password": "sammy-1"}
    tunnel = {"REMOTE_ADDR": "127.0.0.1", "HTTP_X_FORWARDED_PROTO": "https", "HTTP_CF_CONNECTING_IP": "1.2.3.4"}
    r = app.test_client().post("/api/login", json=login, environ_base=tunnel)
    assert r.status_code == 200 and "Secure" in r.headers["Set-Cookie"]
    r = app.test_client().post("/api/login", json=login, environ_base={"REMOTE_ADDR": "10.0.0.5"})
    assert "Secure" not in r.headers["Set-Cookie"]
    spoof = {"REMOTE_ADDR": "10.0.0.5", "HTTP_X_FORWARDED_PROTO": "https"}
    assert "Secure" not in app.test_client().post("/api/login", json=login, environ_base=spoof).headers["Set-Cookie"]


def test_other_websites_cant_press_the_buttons(app):
    c = app.test_client()
    setup = {"username": "evil", "password": "evil-pass"}
    # A form on another website, sent as text so it reads as JSON.
    r = c.post("/api/accounts/setup", data='{"username": "evil", "password": "evil-pass"}',
               content_type="text/plain", headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403 and not accounts.enabled()
    # Older browsers send only the Origin.
    assert c.post("/api/lock/set", json={"pin": "1234"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert c.post("/api/machine/home", headers={"Origin": "null"}).status_code == 403
    # The app's own pages, a proxy in front of it, and the mtg command (no headers) still work.
    assert c.post("/api/lock/set", json={"pin": "1234"}, headers={"Sec-Fetch-Site": "same-origin"}).status_code == 200
    assert c.post("/api/lock/remove", headers={"Origin": "http://localhost"}).status_code == 200
    assert c.post("/api/lock/set", json={"pin": "1234"}, headers={"Origin": "https://mtg.example.com",
                                                                  "X-Forwarded-Host": "mtg.example.com"}).status_code == 200
    c.post("/api/lock/remove")
    assert c.get("/api/me", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 200   # looking is fine
    assert c.post("/api/accounts/setup", json=setup).status_code == 200
