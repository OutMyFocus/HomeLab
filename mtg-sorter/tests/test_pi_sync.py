"""The sorter's Pi following the server: the cards it saves are copied into the server's
collection, and its pages send the browser on to the server's site."""

import csv
import io

import pytest

from app import Scanner, create_app
from mtgscanner import accounts, config, pi_sync
from mtgscanner.collection import add_card
from mtgscanner.database import Card
from mtgscanner.remote_machine import KEY_HEADER
from test_pi_docker import TOWER, pi_machine
from test_scanner import db  # noqa: F401  (a fixture)

PI_URL = "http://10.0.0.247:5000"
SITE = "https://mtg.example.com"


def card(i: int) -> Card:
    return Card(f"id{i}", f"Card {i}", "tst", "Test Set", str(i), "rare", "R", 1.0, None)


class Folders:
    """The Pi and the server in one test, each with a data folder of its own."""

    def __init__(self, tmp_path, monkeypatch):
        self.mp = monkeypatch
        self.pi, self.server = tmp_path / "pi", tmp_path / "server"
        self.pi.mkdir()
        self.server.mkdir()
        self.use(self.server)

    def use(self, folder):
        self.mp.setattr(config, "DATA_DIR", folder)
        self.mp.setattr(config, "COLLECTION_CSV", folder / "collection.csv")

    def on_pi(self, fn):
        self.use(self.pi)
        try:
            return fn()
        finally:
            self.use(self.server)


@pytest.fixture
def folders(tmp_path, monkeypatch):
    pi_sync._seen.clear()
    pi_sync._learned.clear()
    monkeypatch.delenv("MTG_PUBLIC_URL", raising=False)
    monkeypatch.delenv("MTG_MACHINE_URL", raising=False)
    return Folders(tmp_path, monkeypatch)


class Wire:
    """Sends PiSync's asks to the Pi's Flask test client, in the Pi's data folder."""

    def __init__(self, folders, pi_client):
        self.folders, self.pi, self.asks = folders, pi_client, []

    def get(self, url, params=None, headers=None, timeout=None):
        self.asks.append((params, headers))
        path = url.split("5000", 1)[1]
        res = self.folders.on_pi(lambda: self.pi.get(path, query_string=params, headers=headers,
                                                     environ_base=TOWER))

        class R:
            status_code = res.status_code
            def json(self): return res.get_json()
        return R()


def rows(path):
    if not path.exists():
        return []
    return list(csv.DictReader(io.StringIO(path.read_text())))


def saved_on_pi(folders, *ids):
    folders.on_pi(lambda: [add_card(config.COLLECTION_CSV, card(i), False, "Bulk", (0.5, "test")) for i in ids])


@pytest.fixture
def link(db, folders, monkeypatch):  # noqa: F811
    pi_client = folders.on_pi(lambda: create_app(Scanner(db, None, source=None), pi_machine()).test_client())
    sync = pi_sync.PiSync(PI_URL, key="")
    sync.http = Wire(folders, pi_client)
    return sync, pi_client


def test_cards_the_pi_saves_are_copied_to_the_server(folders, link, monkeypatch):
    sync, _ = link
    saved_on_pi(folders, 0)                  # before the link: stays on the Pi
    assert sync.sync_once() == 0
    assert rows(config.COLLECTION_CSV) == []
    saved_on_pi(folders, 1, 2)
    assert sync.sync_once() == 2
    got = rows(config.COLLECTION_CSV)
    assert [r["Name"] for r in got] == ["Card 1", "Card 2"]
    assert got[0]["Price CAD"] == "0.50" and got[0]["Bin"] == "Bulk" and got[0]["Scanned at"]
    # Asking again copies nothing twice, even for cards saved in the same second.
    assert sync.sync_once() == 0
    saved_on_pi(folders, 1)                  # another copy of the same card
    assert sync.sync_once() == 1
    assert [r["Name"] for r in rows(config.COLLECTION_CSV)] == ["Card 1", "Card 2", "Card 1"]
    assert sync.state()["copied"] == 3 and sync.state()["ok"]


def test_a_long_backlog_comes_over_in_parts(folders, link, monkeypatch):
    """Answers hold a few cards at a time, never splitting a second, and every card comes over once."""
    sync, _ = link
    sync.sync_once()
    real = pi_sync.saved_since
    monkeypatch.setattr(pi_sync, "saved_since", lambda after, limit=3: real(after, limit))
    times = [f"2099-01-01T00:00:{s:02d}" for s in (1, 1, 1, 1, 2, 3, 3)]

    def backlog():
        path = config.COLLECTION_CSV
        for i in range(7):
            add_card(path, card(i % 2), False, "Bulk", (None, ""))
        data = rows(path)
        for r, t in zip(data, times):
            r["Scanned at"] = t
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
    folders.on_pi(backlog)
    assert sync.sync_once() == 7
    assert len(rows(config.COLLECTION_CSV)) == 7
    assert sync.sync_once() == 0


def test_another_pi_account_goes_to_the_same_account_or_the_owner(folders, link):
    sync, _ = link
    sync.sync_once()

    def pi_accounts():
        accounts.setup("nic", "secret123")
        accounts.add("sam", "secret123")
        accounts.add("kim", "secret123")
        for who, i in (("nic", 0), ("sam", 1), ("kim", 2)):
            add_card(accounts.collection_csv(who), card(i), False, "Bulk", (None, ""))
    folders.on_pi(pi_accounts)
    (folders.pi / "machine_key").write_text("k" * 40)
    sync.key = "k" * 40
    accounts.setup("nic", "secret123")       # the server: nic and sam, no kim
    accounts.add("sam", "secret123")
    assert sync.sync_once() == 3
    assert [r["Name"] for r in rows(config.COLLECTION_CSV)] == ["Card 0", "Card 2"]
    assert [r["Name"] for r in rows(accounts.collection_csv("sam"))] == ["Card 1"]


def test_a_locked_pi_needs_the_machine_key(folders, link):
    sync, _ = link
    folders.on_pi(lambda: accounts.setup("nic", "secret123"))
    with pytest.raises(RuntimeError, match="MTG_MACHINE_KEY"):
        sync.sync_once()
    (folders.pi / "machine_key").write_text("k" * 40)
    sync.key = "k" * 40
    sync.sync_once()
    assert sync.http.asks[-1][1][KEY_HEADER] == "k" * 40


def test_the_pis_pages_send_you_to_the_server(folders, link, monkeypatch):
    sync, pi_client = link
    monkeypatch.setenv("MTG_PUBLIC_URL", SITE + "/")

    def page(path, **kw):
        return folders.on_pi(lambda: pi_client.get(path, environ_base=TOWER, **kw))
    assert page("/collection").status_code == 200          # nobody has asked yet
    sync.sync_once()                                         # the server asks, saying where it lives
    assert sync.http.asks[-1][1][pi_sync.SITE_HEADER] == SITE
    r = page("/collection?view=grid")
    assert r.status_code == 302 and r.headers["Location"] == SITE + "/collection?view=grid"
    assert page("/").headers["Location"] == SITE + "/"
    # The server's calls, the stream and files stay on the Pi.
    assert page("/api/machine").status_code == 200
    assert page("/static/style.css").status_code == 200
    # ?stay=1 keeps this browser on the Pi.
    assert page("/collection?stay=1").status_code == 200
    assert page("/collection").status_code == 200
    # The Pi's own screen keeps its pages.
    assert folders.on_pi(lambda: pi_client.get("/collection")).status_code == 200


def test_the_pi_stops_sending_you_once_the_server_goes_quiet(folders, link, monkeypatch):
    sync, pi_client = link
    monkeypatch.setenv("MTG_PUBLIC_URL", SITE)
    sync.sync_once()
    page = lambda: folders.on_pi(lambda: pi_client.get("/scan", environ_base=TOWER))  # noqa: E731
    assert page().status_code == 302
    pi_sync._seen["seen"] -= pi_sync.FOLLOW_SECONDS + 1
    assert page().status_code == 200


def test_a_made_up_site_isnt_followed(folders, link):
    _, pi_client = link
    folders.on_pi(lambda: pi_client.get("/api/machine/saved?start=1", environ_base=TOWER,
                                        headers={pi_sync.SITE_HEADER: "javascript:alert(1)"}))
    assert folders.on_pi(lambda: pi_client.get("/scan", environ_base=TOWER)).status_code == 200


def test_the_server_learns_its_address_from_the_tunnel(db, folders, monkeypatch):  # noqa: F811
    monkeypatch.setenv("MTG_MACHINE_URL", PI_URL)
    server = create_app(Scanner(db, None, source=None), pi_machine()).test_client()
    assert pi_sync.public_url() is None
    server.get("/settings", base_url="http://mtg.example.com", headers={"CF-Connecting-IP": "1.2.3.4"},
               environ_base={"REMOTE_ADDR": "172.17.0.5"})
    assert pi_sync.public_url() == SITE
    # the server never sends its own pages anywhere, and has no Pi cards to give
    assert server.get("/scan").status_code == 200
    assert server.get("/api/machine/saved").status_code == 404


def test_the_maintenance_page_shows_the_link(folders, link, monkeypatch):
    sync, _ = link
    monkeypatch.setattr(pi_sync, "_sync", sync)
    sync.sync_once()
    c = pi_sync.sync_check()
    assert c["state"] == "ok" and "0 so far" in c["summary"]
    sync.error = "Can't reach the sorter's Pi at x."
    assert pi_sync.sync_check()["state"] == "off"
