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


def fake_picamera2(monkeypatch, autofocus=True):
    import sys
    import types

    made = []

    class FakePicamera2:
        camera_controls = {"AfMode": (0, 2, 0)} if autofocus else {}

        def __init__(self):
            self.controls = []
            made.append(self)

        def create_video_configuration(self, **kw):
            return kw

        def configure(self, cfg):
            pass

        def start(self):
            pass

        def set_controls(self, c):
            self.controls.append(c)

    monkeypatch.setitem(sys.modules, "picamera2", types.SimpleNamespace(Picamera2=FakePicamera2))
    return made


def test_pi_camera_autofocus_reaches_close_up_cards(monkeypatch):
    # Auto must use the Full range: the default Normal range skips the closest distances,
    # so a card 12 cm under the lens stayed blurry.
    made = fake_picamera2(monkeypatch)
    monkeypatch.setattr(camera, "focus_cm", None)
    cap = camera.PiCapture()
    assert made[0].controls[-1] == {"AfMode": 2, "AfRange": 2, "AfSpeed": 1}
    assert cap.has_focus and cap.focus_cm is None


def test_pi_camera_focus_can_be_locked_at_the_scan_bed(monkeypatch):
    made = fake_picamera2(monkeypatch)
    monkeypatch.setattr(camera, "focus_cm", 12)
    cap = camera.PiCapture()                     # opens with the focus picked last time
    assert made[0].controls[-1] == {"AfMode": 0, "LensPosition": 100 / 12}
    cap.set_focus(None)
    assert made[0].controls[-1]["AfMode"] == 2 and cap.focus_cm is None


def test_a_camera_without_autofocus_is_left_alone(monkeypatch):
    made = fake_picamera2(monkeypatch, autofocus=False)
    cap = camera.PiCapture()
    assert not cap.has_focus and made[0].controls == []
    src = camera.CameraSource.__new__(camera.CameraSource)
    src.cap = cap
    assert src.set_focus(12) is False


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
