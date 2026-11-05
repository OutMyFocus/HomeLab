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


def test_a_pi_camera_that_fails_to_start_is_let_go(monkeypatch):
    # If configure/start fails, the camera must be closed, or every later try fails with
    # "Camera in Configured state trying acquire()" until the app restarts.
    import sys
    import types

    import pytest

    made = []

    class FakePicamera2:
        def __init__(self):
            self.closed = False
            made.append(self)

        def create_video_configuration(self, **kw):
            return kw

        def configure(self, cfg):
            raise OSError(12, "Cannot allocate memory")

        def close(self):
            self.closed = True

    monkeypatch.setitem(sys.modules, "picamera2", types.SimpleNamespace(Picamera2=FakePicamera2))
    with pytest.raises(RuntimeError, match="Cannot allocate memory"):
        camera.CameraSource(camera.PI_CAMERA, "Pi camera")
    assert made and made[0].closed


def test_the_pi_container_gets_the_camera_memory():
    # Without the Pi's /dev/dma_heap (and its vidbuf_cached link) picamera2 runs out of memory.
    from pathlib import Path

    unit = (Path(__file__).parents[1] / "deploy" / "mtg-sorter-docker.service").read_text()
    assert "-v /dev/dma_heap:/dev/dma_heap" in unit


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
