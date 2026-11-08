"""The browser app's API, using fake cards and Flask's test client (no camera needed)."""

import csv
import json

import cv2
import numpy as np
import pytest

from app import Scanner, create_app
from mtgscanner import config
from test_scanner import db, fake_card, photograph  # noqa: F401  (db is a fixture)


@pytest.fixture
def client(db, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")
    scanner = Scanner(db, None, source=None)
    return create_app(scanner).test_client()


def jpeg(img):
    return cv2.imencode(".jpg", img)[1].tobytes()


def test_photos_are_recognized(client):
    import io
    files = [(io.BytesIO(jpeg(photograph(fake_card(2)))), "card.jpg"),
             (io.BytesIO(jpeg(np.full((480, 640, 3), 170, np.uint8))), "empty.jpg")]
    res = client.post("/api/photos", data={"photos": files}, content_type="multipart/form-data").get_json()
    assert res[0]["card"]["id"] == "id2"
    assert res[0]["card"]["bin"] == 3
    assert res[1]["error"] == "No card found in the photo"


def test_add_and_undo(client):
    state = client.post("/api/add", json={"id": "id1", "foil": False}).get_json()
    assert state["totals"]["count"] == 1
    assert state["session"][0]["name"] == "Card 1"
    rows = list(csv.DictReader(config.COLLECTION_CSV.open()))
    assert [r["Name"] for r in rows] == ["Card 1"]

    state = client.post("/api/undo", json={}).get_json()
    assert state["totals"]["count"] == 0
    assert list(csv.DictReader(config.COLLECTION_CSV.open())) == []


def test_settings_toggle(client):
    state = client.post("/api/settings", json={"foil": True, "auto": True}).get_json()
    assert state["foil"] and state["auto"]



def test_outline_color(db, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")
    scanner = Scanner(db, None, source=None)
    client = create_app(scanner).test_client()
    client.post("/api/settings", json={"outline": "#3b8eea"})
    assert scanner.outline == (0xea, 0x8e, 0x3b)   # stored as BGR for OpenCV
    client.post("/api/settings", json={"outline": "#zzzzzz"})
    assert scanner.outline == (0xea, 0x8e, 0x3b)


class FakeCamera:
    def __init__(self, index, name=None):
        if index == 9:
            raise RuntimeError("Could not open Camera 9.")
        self.index, self.name, self.released = index, name or f"Camera {index}", False

    def release(self):
        self.released = True


def test_switch_camera(db, tmp_path, monkeypatch):  # noqa: F811
    import app
    monkeypatch.setattr(app, "CameraSource", FakeCamera)
    monkeypatch.setattr(app, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")
    monkeypatch.setattr(app, "list_cameras", lambda: [{"index": 0, "name": "Integrated Webcam"}, {"index": 1, "name": "Brio 101"}])
    scanner = Scanner(db, None, source=FakeCamera(0, "Integrated Webcam"))
    client = create_app(scanner).test_client()

    assert [c["name"] for c in client.get("/api/cameras").get_json()] == ["Integrated Webcam", "Brio 101"]
    state = client.post("/api/camera", json={"index": 1, "name": "Brio 101"}).get_json()
    assert state["camera"] == {"index": 1, "name": "Brio 101"}
    assert "Brio 101" in (tmp_path / "settings.json").read_text()

    # Picking another before the scanner thread swapped closes the one never used.
    brio = scanner._next_source
    client.post("/api/camera", json={"index": 0, "name": "Integrated Webcam"})
    assert brio.released

    res = client.post("/api/camera", json={"index": 9})
    assert res.status_code == 409 and "Could not open" in res.get_json()["error"]


class FocusCamera(FakeCamera):
    focus = None

    def set_focus(self, cm):
        self.focus = cm
        return True

    def info(self):
        return {"index": self.index, "name": self.name, "focus": {"cm": self.focus, "choices": [12]}}


def test_set_pi_camera_focus(db, tmp_path, monkeypatch):  # noqa: F811
    import app
    from mtgscanner import camera as cameras_mod
    monkeypatch.setattr(app, "CameraSource", FakeCamera)
    monkeypatch.setattr(app, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(cameras_mod, "focus_cm", None)
    cam = FocusCamera(-1, "Pi camera")
    client = create_app(Scanner(db, None, source=cam)).test_client()

    state = client.post("/api/camera/focus", json={"cm": 12}).get_json()
    assert cam.focus == 12 and state["camera"]["focus"]["cm"] == 12
    assert app.saved_focus() == 12 and cameras_mod.focus_cm == 12   # kept for next time
    client.post("/api/camera/focus", json={"cm": None})
    assert cam.focus is None and app.saved_focus() is None
    assert client.post("/api/camera/focus", json={"cm": "close"}).status_code == 400
    assert client.post("/api/camera/focus", json={"cm": 1}).status_code == 400

    # A webcam can't: say so instead of pretending.
    client = create_app(Scanner(db, None, source=FakeCamera(0))).test_client()
    assert client.post("/api/camera/focus", json={"cm": 12}).status_code == 409


def test_rotate_and_crop_the_picture(db, tmp_path, monkeypatch):  # noqa: F811
    import app
    monkeypatch.setattr(app, "SETTINGS_FILE", tmp_path / "settings.json")
    scanner = Scanner(db, None, source=FakeCamera(0))
    client = create_app(scanner).test_client()
    client.post("/api/settings", json={"slots": [[0.5, 0.5, 1, 1]]})

    state = client.post("/api/settings", json={"crop": [0.5, 0.5, 1, 1]}).get_json()
    assert state["view"] == {"rotate": 0, "crop": [0.5, 0.5, 1, 1], "straight": False, "auto_straight": True, "min_card": None, "bed_box": None, "straight_samples": 0, "straight_refused": None}
    assert state["slots"] == [[0, 0, 1, 1]]                      # same spot, now the whole picture
    state = client.post("/api/settings", json={"crop": [0, 0, 0.5, 0.5]}).get_json()
    assert state["view"]["crop"] == [0.5, 0.5, 0.75, 0.75]       # a crop of the crop
    state = client.post("/api/settings", json={"rotate": 90}).get_json()
    assert state["view"] == {"rotate": 90, "crop": [0.25, 0.5, 0.5, 0.75], "straight": False, "auto_straight": True, "min_card": None, "bed_box": None, "straight_samples": 0, "straight_refused": None}
    saved = json.loads((tmp_path / "settings.json").read_text())
    assert saved["rotate"] == 90 and saved["crop"] == [0.25, 0.5, 0.5, 0.75]

    fresh = Scanner(db, None, source=FakeCamera(0))              # kept for next time
    fresh.restore(saved)
    assert fresh.rotate == 90 and fresh.crop == [0.25, 0.5, 0.5, 0.75]

    state = client.post("/api/settings", json={"crop": None}).get_json()
    assert state["view"]["crop"] is None
    assert client.post("/api/settings", json={"rotate": 45}).status_code == 400
    assert client.post("/api/settings", json={"crop": [0, 0, 0.01, 0.01]}).status_code == 400

    # The scanner sees the turned, cropped picture.
    client.post("/api/settings", json={"rotate": 0, "crop": [0, 0, 0.5, 1]})
    scanner.source = type("Cam", (), {"read": lambda self: np.zeros((100, 200, 3), np.uint8)})()
    seen = []
    monkeypatch.setattr(scanner, "process", lambda f: seen.append(f.shape))
    scanner.turn()
    assert seen == [(100, 100, 3)]


def show(scanner, frame, times):
    """Put a picture in front of the scanner for a few frames, like the camera loop does."""
    for _ in range(times):
        scanner.process(frame)


EMPTY = np.full((720, 960, 3), 170, np.uint8)


def table_app(db, tmp_path, monkeypatch, **settings):  # noqa: F811
    import app
    monkeypatch.setattr(config, "GONE_SECONDS", 0)      # tests show frames instantly
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")
    monkeypatch.setattr(app, "SETTINGS_FILE", tmp_path / "settings.json")
    scanner = Scanner(db, None, source=None)
    client = create_app(scanner).test_client()
    client.post("/api/settings", json=settings)
    return scanner, client


def test_scans_every_card_on_the_table(db, tmp_path, monkeypatch):  # noqa: F811
    scanner, client = table_app(db, tmp_path, monkeypatch)
    table = np.hstack([photograph(fake_card(0)), photograph(fake_card(2)), photograph(fake_card(99))])
    show(scanner, table, config.STABLE_FRAMES + 2)

    cards = client.get("/api/state").get_json()["cards"]
    assert [c["number"] for c in cards] == [1, 2, 3]
    assert sorted((c["card"] or {}).get("id", c["status"]) for c in cards) == ["id0", "id2", "unknown"]

    state = client.post("/api/save_all", json={}).get_json()
    assert sorted(e["id"] for e in state["session"]) == ["id0", "id2"]
    assert client.post("/api/save_all", json={}).get_json()["totals"]["count"] == 2   # already saved

    show(scanner, EMPTY, 10)                        # cards taken away
    assert client.get("/api/state").get_json()["cards"] == []


def test_collects_one_scan_per_card(db, tmp_path, monkeypatch):  # noqa: F811
    scanner, client = table_app(db, tmp_path, monkeypatch, collect=True)

    show(scanner, photograph(fake_card(1)), config.STABLE_FRAMES + 3)
    track = client.get("/api/state").get_json()["cards"][0]["track"]
    client.post("/api/add", json={"id": "id1", "foil": False, "track": track})
    show(scanner, EMPTY, 10)                        # card taken away: its row is written

    show(scanner, photograph(fake_card(2)), config.STABLE_FRAMES)
    track = client.get("/api/state").get_json()["cards"][0]["track"]
    assert client.post("/api/wrong", json={"track": track}).get_json()["cards"][0]["verdict"] == "wrong"
    show(scanner, EMPTY, 10)

    show(scanner, photograph(fake_card(99)), config.STABLE_FRAMES)  # not in the database
    show(scanner, EMPTY, 10)

    rows = list(csv.DictReader((tmp_path / "captures" / "log.csv").open()))
    assert [(r["card_id"], r["result"], r["verdict"]) for r in rows] == [
        ("id1", "recognized", "saved"), ("id2", "recognized", "wrong"), ("", "unknown", "")]
    assert all((tmp_path / "captures" / r["crop"]).exists() and (tmp_path / "captures" / r["frame"]).exists() for r in rows)
    assert scanner.captures.counts == {"total": 3, "unknown": 1, "saved": 1, "wrong": 1, "corrected": 0, "labeled": 1}


def test_training_teaches_an_unknown_card(db, tmp_path, monkeypatch):  # noqa: F811
    scanner, client = table_app(db, tmp_path, monkeypatch, collect=True, learn=False)
    mystery = photograph(fake_card(99))

    show(scanner, mystery, config.STABLE_FRAMES)
    (card,) = client.get("/api/state").get_json()["cards"]
    assert card["status"] == "unknown"
    assert [c["id"] for c in client.get("/api/search?q=Card 3").get_json()] == ["id3"]
    state = client.post("/api/correct", json={"id": "id3", "track": card["track"]}).get_json()
    assert state["cards"][0]["card"]["id"] == "id3" and state["session"][0]["id"] == "id3"
    show(scanner, mystery, 3)                       # stays on the card you picked
    assert scanner.tracks[0].card.id == "id3" and len(scanner.session) == 1
    show(scanner, EMPTY, 10)

    info = client.get("/api/training?show=all").get_json()
    assert info["ready"] == 1 and info["scans"][0]["true_name"] == "Card 3"
    assert client.post("/api/train", json={}).get_json() == {"added": 1, "removed": 0, "learned": 1}

    show(scanner, mystery, config.STABLE_FRAMES)    # now it knows this one
    assert scanner.tracks[0].status == "locked" and scanner.tracks[0].card.id == "id3"

    # Skipping the scan as a bad picture takes it back out on the next training.
    client.post("/api/label", json={"crop": info["scans"][0]["crop"], "verdict": "ignore"})
    assert client.post("/api/train", json={}).get_json()["removed"] == 1
    assert client.post("/api/forget", json={}).get_json() == {"removed": 0}


def test_keeps_learning_without_pressing_train(db, tmp_path, monkeypatch):  # noqa: F811
    scanner, client = table_app(db, tmp_path, monkeypatch, collect=True, learn=True)
    mystery = photograph(fake_card(99))

    show(scanner, mystery, config.STABLE_FRAMES)
    track = client.get("/api/state").get_json()["cards"][0]["track"]
    client.post("/api/correct", json={"id": "id3", "track": track})
    show(scanner, EMPTY, 10)                        # taken away: learned right then
    assert scanner.matcher.learned_count == 1

    show(scanner, mystery, config.STABLE_FRAMES)
    assert scanner.tracks[0].card.id == "id3"


def test_correcting_a_saved_card_replaces_it(db, tmp_path, monkeypatch):  # noqa: F811
    scanner, client = table_app(db, tmp_path, monkeypatch, auto=True)
    show(scanner, photograph(fake_card(2)), config.STABLE_FRAMES)    # auto-saved as Card 2
    track = client.get("/api/state").get_json()["cards"][0]["track"]
    state = client.post("/api/correct", json={"id": "id3", "track": track}).get_json()
    assert [e["id"] for e in state["session"]] == ["id3"]
    assert [r["Scryfall ID"] for r in csv.DictReader(config.COLLECTION_CSV.open())] == ["id3"]


def test_state_has_card_corners_for_the_page(db, tmp_path, monkeypatch):  # noqa: F811
    """The page draws each card's outline from its corners, given as fractions of the frame."""
    scanner, client = table_app(db, tmp_path, monkeypatch)
    show(scanner, photograph(fake_card(2)), config.STABLE_FRAMES + 2)
    state = client.get("/api/state").get_json()
    assert state["frame"] == {"w": 960, "h": 720}
    (card,) = state["cards"]
    assert len(card["corners"]) == 4
    assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in card["corners"])
    # photograph() puts the card at about x 190-560, y 90-590 of a 960x720 picture.
    xs, ys = zip(*card["corners"])
    assert 0.15 < min(xs) < 0.3 and 0.5 < max(xs) < 0.65
    assert 0.08 < min(ys) < 0.2 and 0.75 < max(ys) < 0.9


# --- Slots mode: boxes you draw on the picture, one per card position ---

def card_at(table, seed, x, y, w=200, h=280):
    """Lay a fake card flat on the table, top-left corner at (x, y)."""
    table[y:y + h, x:x + w] = cv2.resize(fake_card(seed), (w, h))


def test_slots_mode_looks_only_in_the_slots(db, tmp_path, monkeypatch):  # noqa: F811
    import json
    scanner, client = table_app(db, tmp_path, monkeypatch)
    table = EMPTY.copy()
    card_at(table, 2, 100, 100)        # in slot 1
    card_at(table, 0, 650, 100)        # outside every slot: ignored
    slots = [[0.08, 0.1, 0.34, 0.56], [0.4, 0.1, 0.62, 0.56]]     # slot 2 is empty
    state = client.post("/api/settings", json={"mode": "slots", "slots": slots}).get_json()
    assert state["mode"] == "slots" and state["slots"] == slots
    show(scanner, table, config.STABLE_FRAMES + 2)
    (c,) = client.get("/api/state").get_json()["cards"]
    assert c["number"] == 1 and c["card"]["id"] == "id2"     # numbered by slot, not by order found
    assert 0.08 < c["corners"][0][0] < 0.15                   # the card's own edges, inside the slot
    assert json.loads((tmp_path / "settings.json").read_text())["slots"] == slots   # kept for next time

    show(scanner, EMPTY, 10)
    assert client.get("/api/state").get_json()["cards"] == []
    assert client.post("/api/settings", json={"mode": "auto"}).get_json()["mode"] == "auto"
    show(scanner, table, config.STABLE_FRAMES + 2)
    assert len(client.get("/api/state").get_json()["cards"]) == 2     # Auto mode sees both again


def test_the_slot_is_the_outline_when_the_card_has_no_findable_edges(db, tmp_path, monkeypatch):  # noqa: F811
    from mtgscanner import recognize
    slot = [100 / 960, 100 / 720, 300 / 960, 380 / 720]
    scanner, client = table_app(db, tmp_path, monkeypatch, mode="slots", slots=[slot])
    table = EMPTY.copy()
    card_at(table, 2, 100, 100)
    monkeypatch.setattr(recognize, "find_cards", lambda frame, *a: [])   # as with a card in a box or a shiny sleeve
    show(scanner, table, config.STABLE_FRAMES + 2)
    (c,) = client.get("/api/state").get_json()["cards"]
    assert c["card"]["id"] == "id2"
    assert c["corners"][0] == pytest.approx(slot[:2], abs=0.03) and c["corners"][2] == pytest.approx(slot[2:], abs=0.03)

    show(scanner, EMPTY, 10)             # card taken away: an empty slot isn't a card
    assert client.get("/api/state").get_json()["cards"] == []


def test_slots_are_remembered_and_checked(db, tmp_path, monkeypatch):  # noqa: F811
    import json
    scanner, client = table_app(db, tmp_path, monkeypatch, mode="slots", slots=[[0.5, 0.9, 0.1, 0.1], [0.2, 0.2, 0.21, 0.21]])
    assert scanner.slots == [[0.1, 0.1, 0.5, 0.9]]      # corners put in order, the tiny one dropped
    again = Scanner(db, None, source=None)
    again.restore(json.loads((tmp_path / "settings.json").read_text()))
    assert again.mode == "slots" and again.slots == [[0.1, 0.1, 0.5, 0.9]]
    assert client.post("/api/settings", json={"slots": "nonsense"}).status_code == 400
    assert client.post("/api/settings", json={"slots": [[0, 0, "x", 1]]}).status_code == 400


def test_slot_occupied_tells_a_card_from_plain_table():
    from mtgscanner.recognize import slot_occupied
    assert slot_occupied(cv2.resize(fake_card(1), (200, 280)))
    assert not slot_occupied(EMPTY[100:380, 100:300])
    assert not slot_occupied(EMPTY[0:0, 0:0])


def test_starts_without_a_camera_and_picks_one_up(db, monkeypatch):  # noqa: F811
    import types

    import app

    waiting = app.WaitingForCamera(None, seconds=0)
    scanner = Scanner(db, None, source=waiting)
    waiting.on_found = scanner.use_source
    state = create_app(scanner).test_client().get("/api/state").get_json()
    assert state["status"] == "waiting"

    monkeypatch.setattr(app, "startup_camera", lambda index: (_ for _ in ()).throw(RuntimeError("none")))
    assert waiting.read() is None and scanner._next_source is None

    found = types.SimpleNamespace(name="Pi camera")
    monkeypatch.setattr(app, "startup_camera", lambda index: found)
    assert waiting.read() is None
    assert scanner._next_source is found


def test_each_phone_scans_on_its_own(db, tmp_path, monkeypatch):  # noqa: F811
    """A phone picks "This device's camera" and gets a scanner of its own: its pictures,
    its table and its session, while the machine's camera carries on untouched. Two
    phones at once don't see each other's cards, and each card remembers who scanned it."""
    from mtgscanner.camera import BrowserSource

    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")
    monkeypatch.setattr(Scanner, "run", lambda self: None)   # no scanner threads: pictures are fed by hand below
    machine = Scanner(db, None, source=FakeCamera(0, "Integrated Webcam"))
    app = create_app(machine)
    client = app.test_client()
    scanners = app.config["scanners"]

    assert client.post("/api/camera", json={"index": "browser"}).status_code == 400

    nic = {"X-Scanner": "phone-1"}
    state = client.post("/api/camera", json={"index": "browser", "name": "Phone camera", "token": "phone-1", "who": "Nic"},
                        headers=nic).get_json()
    assert state["camera"]["name"] == "Phone camera" and state["camera"]["browser"] and state["owner"] == "Nic"
    phone = scanners["phone-1"]
    assert isinstance(phone.source, BrowserSource) and phone is not machine
    assert isinstance(machine.source, FakeCamera) and machine._next_source is None   # untouched

    # A picture from a page that isn't scanning is turned away; a bad picture too.
    photo = jpeg(photograph(fake_card(2)))
    assert client.post("/api/frame", data=photo, headers={"X-Scanner": "someone-else"}).status_code == 409
    assert client.post("/api/frame", data=b"not a picture", headers=nic).status_code == 400

    for _ in range(4):
        assert client.post("/api/frame", data=photo, headers=nic).status_code == 204
        phone.process(phone.source.read(timeout=0.1))
    state = client.get("/api/state", headers=nic).get_json()
    assert state["camera"]["index"] == "browser" and state["camera"]["size"] == [960, 720]
    assert state["cards"] and state["cards"][0]["card"]["id"] == "id2"
    assert client.get("/api/state").get_json()["cards"] == []   # the machine's table is empty

    # Saving from the phone: its session, and the card's Source is the name typed on it.
    state = client.post("/api/save_all", json={"foil": False}, headers=nic).get_json()
    assert state["totals"]["count"] == 1 and state["session"][0]["name"] == "Card 2"
    assert client.get("/api/state").get_json()["totals"]["count"] == 0
    rows = list(csv.DictReader(config.COLLECTION_CSV.open()))
    assert [(r["Name"], r["Source"]) for r in rows] == [("Card 2", "Nic")]
    assert client.get("/api/state").get_json()["scanners"] == [{"name": "Phone camera", "owner": "Nic", "cards": 1}]

    # A second phone gets its own scanner; picking the camera again on the first changes nothing.
    sam = {"X-Scanner": "phone-2"}
    client.post("/api/camera", json={"index": "browser", "name": "Phone camera", "token": "phone-2", "who": "Sam"}, headers=sam)
    assert set(scanners) == {"phone-1", "phone-2"} and scanners["phone-2"].owner == "Sam"
    client.post("/api/camera", json={"index": "browser", "token": "phone-1"}, headers=nic)
    assert scanners["phone-1"] is phone and phone.owner == "Nic"
    assert client.get("/api/state", headers=sam).get_json()["totals"]["count"] == 0
    assert client.post("/api/undo", json={}, headers=nic).get_json()["totals"]["count"] == 0
    assert list(csv.DictReader(config.COLLECTION_CSV.open())) == []

    # Closing the page drops its scanner; the machine never noticed any of it.
    client.post("/api/camera/release", json={"token": "nobody"})
    assert set(scanners) == {"phone-1", "phone-2"}
    client.post("/api/camera/release", json={"token": "phone-1"})
    assert set(scanners) == {"phone-2"} and phone.stopped
    back = client.get("/api/state", headers=nic).get_json()   # the page sees the machine's scanner again
    assert back["owner"] == "" and back["status"] == "starting" and back["scanners"] == [{"name": "Phone camera", "owner": "Sam", "cards": 0}]
    assert isinstance(machine.source, FakeCamera)


def test_quiet_phone_pauses_then_goes_away(db):  # noqa: F811
    """The phone's page went to the background: its table clears and the page says paused;
    after long enough with no pictures its scanner stops and is dropped."""
    import time

    from mtgscanner.camera import BrowserSource

    source = BrowserSource("phone-3")
    source.gone_after = 0.0
    sc = Scanner(db, None, source=source)
    sc.started = True
    dropped = []
    sc.on_stop = dropped.append
    time.sleep(0.01)
    assert sc.state()["status"] == "paused"
    sc.turn()                      # one go of the scanner thread's loop
    assert not sc.started and not sc.stopped
    sc.expire = 0.0
    sc.turn()
    assert sc.stopped
    sc.run()                       # the thread's loop ends at once, and the app is told
    assert dropped == [sc]


def test_scan_page_offers_start_sorting_only_where_there_is_a_sorter(client, monkeypatch):
    """The Scan page's Start sorting button shows when the app runs the machine (the Pi,
    or a server pointed at the Pi); /api/state says so."""
    assert client.get("/api/state").get_json()["sorter"] is False       # tests: no Pi, no MTG_MACHINE_URL
    page = client.get("/scan").get_data(as_text=True)
    assert 'id="sortBtn"' in page and "Start sorting" in page


def test_the_pages_scripts_parse():
    """A syntax error in a page script kills the whole page (the Scan page lost its live
    view and buttons on 2026-11-06 to a helper declared twice), so every script is parsed."""
    import shutil
    import subprocess
    from pathlib import Path
    node = shutil.which("node")
    if not node:
        pytest.skip("node isn't installed here")
    for script in sorted((Path(__file__).resolve().parent.parent / "webui").glob("*.js")):
        check = subprocess.run([node, "--check", str(script)], capture_output=True, text=True)
        assert check.returncode == 0, f"{script.name}: {check.stderr.strip()}"


def test_whole_cards_only_measures_the_card_on_the_bed(db, tmp_path, monkeypatch):  # noqa: F811
    """Nic: the scanner shouldn't look at small sections of the card. "Whole cards
    only" sets the smallest card from the card on the bed, so its art box or text box
    is no longer read as a card of its own."""
    import app
    from mtgscanner.tracking import Track
    monkeypatch.setattr(app, "SETTINGS_FILE", tmp_path / "settings.json")
    scanner = Scanner(db, None, source=FakeCamera(0))
    client = create_app(scanner).test_client()
    # no picture or card yet: say so
    assert client.post("/api/settings", json={"min_card": "bed"}).status_code == 400

    scanner.frame_size = (100, 200)
    card = np.array([[10, 10], [70, 10], [70, 110], [10, 110]], np.float32)    # 60 x 100 = 0.3 of the picture
    art = np.array([[15, 20], [65, 20], [65, 60], [15, 60]], np.float32)       # 50 x 40 = 0.1
    scanner.tracks = [Track(1, 1, card, status="locked"), Track(2, 2, art, status="unknown")]
    state = client.post("/api/settings", json={"min_card": "bed"}).get_json()
    assert state["view"]["min_card"] == round(0.3 * config.MIN_CARD_FROM_BED, 4)
    assert scanner.tracks == []                                # looked at afresh
    assert json.loads((tmp_path / "settings.json").read_text())["min_card"] == state["view"]["min_card"]

    assert state["view"]["bed_box"] == [0.1, 0.05, 0.7, 0.55]   # where the card lay

    # the art box alone isn't a card; the whole card is
    frame = np.zeros((200, 100, 3), np.uint8)
    monkeypatch.setattr(app, "find_cards", lambda f, min_area=None: [[art]])
    (outline,), _ = scanner._find(frame)
    assert np.allclose(outline[0], card)                       # the bed box stands in for the lost edge
    monkeypatch.setattr(app, "find_cards", lambda f, min_area=None: [[card, art]])
    (outline,), _ = scanner._find(frame)
    assert outline[0] is card
    # a piece outside the bed (the next card in the slot) isn't read
    up_top = np.array([[10, 150], [40, 150], [40, 190], [10, 190]], np.float32)
    monkeypatch.setattr(app, "find_cards", lambda f, min_area=None: [[up_top]])
    assert scanner._find(frame) == ([], [])

    fresh = Scanner(db, None, source=FakeCamera(0))            # kept for next time
    fresh.restore(json.loads((tmp_path / "settings.json").read_text()))
    assert fresh.min_card == state["view"]["min_card"] and fresh.bed_box == [0.1, 0.05, 0.7, 0.55]

    assert client.post("/api/settings", json={"min_card": 0.3}).get_json()["view"]["min_card"] == 0.3
    assert client.post("/api/settings", json={"min_card": 2}).status_code == 400
    assert client.post("/api/settings", json={"bed_box": [0.2, 0.3, 0.8, 0.9]}).get_json()["view"]["bed_box"] == [0.2, 0.3, 0.8, 0.9]
    assert client.post("/api/settings", json={"bed_box": "x"}).status_code == 400
    off = client.post("/api/settings", json={"min_card": None}).get_json()["view"]
    assert off["min_card"] is None and off["bed_box"] is None
