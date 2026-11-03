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


def test_browser_source_hands_out_the_newest_picture():
    import numpy as np

    src = camera.BrowserSource("tok", "Phone camera")
    assert src.read(timeout=0.01) is None and src.info()["size"] is None
    src.push(np.zeros((480, 640, 3), np.uint8))
    src.push(np.ones((480, 640, 3), np.uint8))
    frame = src.read(timeout=0.01)
    assert frame is not None and frame[0, 0, 0] == 1       # the older one was skipped
    assert src.read(timeout=0.01) is None                  # nothing new since
    assert src.info() == {"index": "browser", "name": "Phone camera", "format": "JPEG", "size": [640, 480], "browser": True}
    assert not src.gone()
    src.release()
    assert src.read(timeout=0.01) is None
