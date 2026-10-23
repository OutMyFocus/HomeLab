"""The browser app's API, using fake cards and Flask's test client (no camera needed)."""

import csv

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


def show(scanner, frame, times):
    """Put a picture in front of the scanner for a few frames, like the camera loop does."""
    for _ in range(times):
        scanner.process(frame)


EMPTY = np.full((720, 960, 3), 170, np.uint8)


def table_app(db, tmp_path, monkeypatch, **settings):  # noqa: F811
    import app
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
