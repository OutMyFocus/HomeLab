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
