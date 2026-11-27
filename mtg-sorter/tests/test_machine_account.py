"""Choosing whose account the machine scans into (machine_account.py): the server's machine
scanner, the sort runs it starts on the Pi, and the cards the Pi's sync brings over."""

import pytest

from app import Scanner, create_app
from mtgscanner import accounts, config, machine_account, pi_sync
from mtgscanner.remote_machine import RemoteMachine
from test_accounts import AWAY, device, names
from test_pi_sync import PI_URL, Wire, card, folders, rows, saved_on_pi  # noqa: F401  (fixtures)
from test_pi_docker import pi_machine
from test_scanner import db  # noqa: F401  (a fixture)
from mtgscanner.collection import add_card


@pytest.fixture
def server(db, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "USD_TO_CAD", 1.5)
    scanner = Scanner(db, None, source=None)
    app = create_app(scanner)
    nic = device(app)
    assert nic.post("/api/accounts/setup", json={"username": "nic", "password": "secret-1", "name": "Nic"}).status_code == 200
    nic.post("/api/accounts/add", json={"username": "sam", "password": "sammy-1", "name": "Sam", "role": "member"})
    nic.post("/api/accounts/add", json={"username": "kim", "password": "kimmy-1", "name": "Kim",
                                         "perms": ["scan", "edit", "machine"]})
    return app, scanner, nic


def login(app, username, password):
    c = device(app)
    assert c.post("/api/login", json={"username": username, "password": password}).status_code == 200
    return c


def test_without_accounts_there_is_nothing_to_pick(db, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    c = create_app(Scanner(db, None, source=None)).test_client()
    s = c.get("/api/machine/account").get_json()
    assert s["accounts"] is False and s["choices"] == []
    assert c.post("/api/machine/account", json={"user": "sam"}).status_code == 400


def test_the_owner_is_picked_until_someone_else_is(server, tmp_path):
    app, scanner, nic = server
    s = nic.get("/api/machine/account").get_json()
    assert s["user"] == "nic" and s["can_pick"]
    assert [c["username"] for c in s["choices"]] == ["nic", "sam", "kim"]
    s = nic.post("/api/machine/account", json={"user": "sam"}).get_json()
    assert s["user"] == "sam"
    assert scanner.account == "sam"                      # Auto-save follows straight away
    assert nic.post("/api/machine/account", json={"user": "nobody"}).status_code == 400
    # Back to the owner: stored as nobody picked.
    assert nic.post("/api/machine/account", json={"user": "nic"}).get_json()["user"] == "nic"
    assert machine_account.picked() == ""


def test_only_an_admin_can_pick(server):
    app, _, nic = server
    kim = login(app, "kim", "kimmy-1")       # has the machine permission, isn't an admin
    s = kim.get("/api/machine/account").get_json()
    assert s["user"] == "nic" and not s["can_pick"]
    assert kim.post("/api/machine/account", json={"user": "kim"}).status_code == 403
    sam = login(app, "sam", "sammy-1")       # no machine permission at all
    assert sam.get("/api/machine/account").status_code == 403


def test_the_machines_scanner_saves_into_the_picked_account(server, tmp_path):
    app, _, nic = server
    assert nic.post("/api/add", json={"id": "id1"}).status_code == 200
    assert names(tmp_path / "collection.csv") == ["Card 1"]          # the owner, as before
    nic.post("/api/machine/account", json={"user": "sam"})
    assert nic.post("/api/add", json={"id": "id2"}).status_code == 200
    kim = login(app, "kim", "kimmy-1")
    assert kim.post("/api/add", json={"id": "id3"}).status_code == 200   # whoever presses
    assert names(tmp_path / "users" / "sam" / "collection.csv") == ["Card 2", "Card 3"]
    assert names(tmp_path / "collection.csv") == ["Card 1"]
    assert nic.get("/api/state").get_json()["saving_to"]["username"] == "sam"
    # A phone still scans into its own person's cards.
    phone = {"X-Scanner": "kim-phone"}
    kim.post("/api/camera", json={"index": "browser", "token": "kim-phone", "name": "Phone"}, headers=phone)
    assert kim.post("/api/add", json={"id": "id0"}, headers=phone).status_code == 200
    assert names(tmp_path / "users" / "kim" / "collection.csv") == ["Card 0"]
    kim.post("/api/camera/release", json={"token": "kim-phone"}, headers=phone)
    app.config["scanners"].pop("kim-phone", None)
    # The picked account is removed: back to whoever presses (the owner here).
    nic.post("/api/accounts/remove", json={"username": "sam"})
    assert machine_account.picked() == "" and machine_account.chosen() == "nic"


def test_a_sort_run_started_on_the_server_names_the_account(server, monkeypatch, tmp_path):
    remote = RemoteMachine(PI_URL, key="")
    sent = []
    monkeypatch.setattr(remote, "sort_start", lambda body: sent.append(body) or {"running": True})
    scanner = Scanner(server[1].matcher, None, source=None)
    c = create_app(scanner, remote).test_client()
    c.environ_base.update(AWAY)
    c.post("/api/login", json={"username": "nic", "password": "secret-1"})
    assert c.post("/api/machine/sort", json={"max_cards": 3}).status_code == 200
    assert sent[-1]["account"] == machine_account.NOBODY
    with accounts.acting_as("nic"):
        machine_account.pick("sam")
    assert c.post("/api/machine/sort", json={}).status_code == 200
    assert sent[-1]["account"] == "sam"


def test_the_pi_notes_each_change_by_its_own_clock(folders, monkeypatch):  # noqa: F811
    times = iter(["2099-01-01T10:00:00", "2099-01-01T10:05:00", "2099-01-01T10:09:00"])
    monkeypatch.setattr(machine_account, "_now", lambda: next(times))
    assert machine_account.heard("*") is False           # nothing picked is where it starts
    assert machine_account.heard("sam") is True
    assert machine_account.heard("sam") is False         # unchanged: not noted again
    assert machine_account.heard("*") is True
    assert machine_account.heard("kim") is True
    log = machine_account.changes()
    assert machine_account.meant_for("2099-01-01T09:59:59", log) == ""
    assert machine_account.meant_for("2099-01-01T10:00:00", log) == "sam"
    assert machine_account.meant_for("2099-01-01T10:07:00", log) == ""
    assert machine_account.meant_for("2099-01-01T11:00:00", log) == "kim"


@pytest.fixture
def link(db, folders):  # noqa: F811
    pi_client = folders.on_pi(lambda: create_app(Scanner(db, None, source=None), pi_machine()).test_client())
    sync = pi_sync.PiSync(PI_URL, key="")
    sync.http = Wire(folders, pi_client)
    accounts.setup("nic", "secret123")       # the server: nic and sam
    accounts.add("sam", "secret123")
    return sync, pi_client


def test_the_pis_cards_go_into_the_picked_account(folders, link):  # noqa: F811
    sync, _ = link
    sync.sync_once()                                     # the first ask
    saved_on_pi(folders, 1)
    assert sync.sync_once() == 1                         # nobody picked: the owner
    with accounts.acting_as("nic"):
        machine_account.pick("sam")
    sync.sync_once()                                     # the ask tells the Pi
    assert sync.http.asks[-1][1][machine_account.HEADER] == "sam"
    saved_on_pi(folders, 2, 3)
    assert sync.sync_once() == 2
    assert [r["Name"] for r in rows(accounts.collection_csv("sam"))] == ["Card 2", "Card 3"]
    with accounts.acting_as("nic"):
        machine_account.pick("")
    sync.sync_once()
    saved_on_pi(folders, 4)
    assert sync.sync_once() == 1
    assert [r["Name"] for r in rows(config.COLLECTION_CSV)] == ["Card 1", "Card 4"]
    assert len(rows(accounts.collection_csv("sam"))) == 2


def test_a_pi_card_for_a_removed_account_goes_to_the_owner(folders, link):  # noqa: F811
    sync, _ = link
    sync.sync_once()
    folders.on_pi(lambda: machine_account.heard("gone"))
    folders.on_pi(lambda: add_card(config.COLLECTION_CSV, card(7), False, "Bulk", (None, "")))
    sync.key = ""
    # the server still says nobody: the Pi notes that, but the card was saved while it was "gone"
    assert sync.sync_once() == 1
    assert [r["Name"] for r in rows(config.COLLECTION_CSV)] == ["Card 7"]
