"""User accounts: logging in, permissions, and everyone keeping their own cards."""

import csv
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
