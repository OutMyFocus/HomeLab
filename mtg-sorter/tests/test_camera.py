"""Picking a camera (no real camera needed)."""

import pytest

from mtgscanner import camera


class FakeWebcam:
    def __init__(self, index):
        self.index = index


def test_auto_uses_the_pi_camera_when_there_is_one(monkeypatch):
    monkeypatch.setattr(camera, "pi_camera_present", lambda: True)
    monkeypatch.setattr(camera, "PiCameraSource", lambda: "pi camera")
    assert camera.open_camera("auto") == "pi camera"


def test_auto_falls_back_to_webcam_0(monkeypatch):
    monkeypatch.setattr(camera, "pi_camera_present", lambda: False)
    monkeypatch.setattr(camera, "WebcamSource", FakeWebcam)
    assert camera.open_camera("auto").index == 0


def test_webcam_number(monkeypatch):
    monkeypatch.setattr(camera, "WebcamSource", FakeWebcam)
    assert camera.open_camera("1").index == 1


def test_nonsense_camera_name():
    with pytest.raises(SystemExit):
        camera.open_camera("front")
