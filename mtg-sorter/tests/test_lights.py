"""The light bars, with a fake SPI output (no Pi or LEDs needed)."""

import numpy as np
import pytest

from app import Scanner, create_app
from mtgscanner import config, lights as L
from mtgscanner.lights import Lights, encode
from test_scanner import db, fake_card  # noqa: F401  (db is a fixture)


class FakeSpi:
    def __init__(self):
        self.writes = []

    def write(self, data): self.writes.append(data)
    def close(self): pass


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")


@pytest.fixture
def spi():
    return FakeSpi()


@pytest.fixture
def lights(spi):
    return Lights(opener=lambda: spi)


@pytest.fixture
def client(db, lights):  # noqa: F811
    return create_app(Scanner(db, None, source=None), lights=lights).test_client()


def test_bits_become_short_and_long_pulses():
    data = encode(np.array([[0xFF, 0x00, 0x80]], np.uint8))   # red, green, blue
    colors = data[len(L.LEAD):len(L.LEAD) + 24]
    # WS2812 takes green first, then red, then blue.
    assert colors[:8] == bytes([0b11000000] * 8)                       # green 0x00
    assert colors[8:16] == bytes([0b11111000] * 8)                     # red 0xFF
    assert colors[16:] == bytes([0b11111000] + [0b11000000] * 7)       # blue 0x80
    assert data.endswith(L.RESET)


def test_full_frame_fits_one_spi_write():
    assert len(encode(np.zeros((L.MAX_LEDS, 3), np.uint8))) <= 4096


def test_brightness_and_power_limit(lights):
    lights.update({"color": "#ffffff", "brightness": 100, "count": 60})
    frame, _ = lights.render(0)
    assert L.amps(frame) <= config.LIGHTS_MAX_AMPS + 0.01      # 60 LEDs of white would be 3.6 A
    lights.update({"brightness": 10, "count": 10})
    frame, _ = lights.render(0)
    assert frame.shape == (10, 3) and frame.max() == round(255 * 0.1)


def test_off_is_dark_and_effects_move(lights):
    lights.update({"on": False})
    assert lights.render(0)[0].max() == 0
    lights.update({"on": True, "effect": "rainbow"})
    a, moving = lights.render(1.0)
    b, _ = lights.render(1.5)
    assert moving and not np.array_equal(a, b)


def test_settings_are_kept_and_checked(client):
    s = client.post("/api/lights", json={"color": "#00ff00", "brightness": 250, "effect": "breathe"}).get_json()
    assert s["settings"]["color"] == "#00ff00" and s["settings"]["brightness"] == 100
    assert Lights().settings["effect"] == "breathe"                  # saved in data/lights.json
    assert client.post("/api/lights", json={"color": "green"}).status_code == 400
    assert client.post("/api/lights", json={"effect": "disco"}).status_code == 400
    client.post("/api/lights/reset", json={})
    assert Lights().settings["color"] == L.DEFAULTS["color"]


def test_preview_and_page(client):
    client.post("/api/lights", json={"color": "#ff0000", "brightness": 50, "count": 5, "effect": "solid"})
    colors = client.get("/api/lights/preview").get_json()["colors"]
    assert colors == ["#7f0000"] * 5 or colors == ["#800000"] * 5
    assert client.get("/lights").status_code == 200


def test_flash_shows_then_fades(lights):
    lights.update({"color": "#000000", "brightness": 100, "count": 4})
    lights.flash("saved")
    green = L.to_rgb(lights.settings["events"]["saved"]["color"])
    frame, moving = lights.render(lights._flash[1] + 0.1)
    assert moving and np.allclose(frame[0], green, atol=2)
    frame, _ = lights.render(lights._flash[1] + L.FLASH_SECONDS + 0.1)
    assert frame.max() == 0
    lights.update({"flashes": False})
    lights.flash("saved")
    assert lights._flash is None
    with pytest.raises(ValueError):
        lights.flash("party")


def test_saving_a_card_flashes(client, lights):
    client.post("/api/add", json={"id": "id1", "foil": False})
    assert lights._flash is not None


def test_sends_to_spi(lights, spi):
    lights.update({"color": "#ffffff", "brightness": 20, "count": 3})
    frame, _ = lights.render(0)
    lights._send(frame)
    assert spi.writes and len(spi.writes[-1]) == len(encode(np.zeros((L.MAX_LEDS, 3), np.uint8)))


def test_without_spi_it_says_why(db):  # noqa: F811
    def no_spi():
        raise FileNotFoundError("/dev/spidev0.0")
    lights = Lights(opener=no_spi)
    s = lights.state()
    assert not s["ok"] and s["error"]
    client = create_app(Scanner(db, None, source=None), lights=lights).test_client()
    assert client.post("/api/lights", json={"color": "#123456"}).status_code == 200
