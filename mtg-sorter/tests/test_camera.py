"""Picking a camera (no real camera needed)."""

from mtgscanner import camera


def test_pi_camera_is_listed_first(monkeypatch):
    monkeypatch.setattr(camera, "pi_camera_present", lambda: True)
    assert camera.list_cameras()[0] == {"index": camera.PI_CAMERA, "name": "Pi camera"}


def test_no_pi_camera_on_a_pc(monkeypatch):
    monkeypatch.setattr(camera, "pi_camera_present", lambda: False)
    assert all(c["index"] != camera.PI_CAMERA for c in camera.list_cameras())


def test_pi_camera_opens_through_picamera2(monkeypatch):
    monkeypatch.setattr(camera, "PiCapture", lambda: "pi capture")
    assert camera.open_camera(camera.PI_CAMERA) == "pi capture"
