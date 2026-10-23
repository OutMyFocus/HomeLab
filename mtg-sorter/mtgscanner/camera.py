"""The webcam, opened the fast way and read in the background.

Used by app.py and scan.py. Two things here make a big difference to speed:

1. The format. Over USB a webcam can only send about 5 uncompressed 1080p pictures a
   second, but 30 compressed (MJPG) ones. OpenCV's Windows driver drops back to the
   uncompressed format whenever the size or frame rate is set, so MJPG is asked for LAST.
2. The newest picture. A webcam produces pictures whether or not anyone is looking. If
   the scanner asked for "the next one" each time, it would be handed pictures taken
   while it was busy and fall further and further behind. A small thread keeps reading
   the camera, and the scanner is handed the newest picture whenever it asks.
"""

import sys
import threading
import time

import cv2

from . import config

# Each system's own camera driver. On Windows, DirectShow opens a webcam in about a
# second where OpenCV's default can take 20.
BACKEND = {"win32": cv2.CAP_DSHOW, "linux": cv2.CAP_V4L2, "darwin": cv2.CAP_AVFOUNDATION}.get(sys.platform, cv2.CAP_ANY)


def list_cameras() -> list[dict]:
    """The webcams plugged in, with their names (e.g. "Brio 101")."""
    try:
        from cv2_enumerate_cameras import enumerate_cameras
        cams = [{"index": c.index, "name": c.name} for c in enumerate_cameras(BACKEND)]
    except Exception:   # library missing or unsupported here: just number them
        return [{"index": i, "name": f"Camera {i}"} for i in range(3)]
    seen, unique = set(), []
    for c in cams:      # Linux lists some cameras twice (one per video node)
        if c["name"] not in seen:
            seen.add(c["name"])
            unique.append(c)
    return unique


def open_camera(index: int) -> cv2.VideoCapture:
    """Open a webcam at the size in config.py, compressed, at 30 pictures a second."""
    cap = cv2.VideoCapture(index, BACKEND)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Could not open camera {index}.")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_SIZE[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_SIZE[1])
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))   # last, see above
    return cap


def describe(cap: cv2.VideoCapture) -> tuple[str, tuple[int, int]]:
    """(format such as "MJPG", (width, height)) the camera actually agreed to."""
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, "little").decode("ascii", "replace")
    return fourcc, (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))


class CameraSource:
    """A webcam that always hands out its NEWEST picture (see the module docstring)."""

    def __init__(self, index: int, name: str | None = None):
        self.index, self.name = index, name or f"Camera {index}"
        try:
            self.cap = open_camera(index)
        except RuntimeError:
            raise RuntimeError(f"Could not open {self.name}.") from None
        self.format, self.size = describe(self.cap)
        self._cond = threading.Condition()
        self._frame, self._seq, self._given, self._stop = None, 0, 0, False
        self.taken_at = 0.0          # when the newest picture was taken (time.monotonic)
        self.camera_fps = None       # how many pictures a second the camera really delivers
        self._thread = threading.Thread(target=self._pump, name="camera", daemon=True)
        self._thread.start()

    def _pump(self):
        # All camera calls happen on this one thread (OpenCV's camera isn't thread-safe).
        # cap.read() waits for the camera's next picture, so this loop runs at its pace.
        count, since, failures = 0, time.monotonic(), 0
        while not self._stop:
            ok, frame = self.cap.read()
            if not ok:
                failures += 1
                time.sleep(0.05 if failures < 20 else 0.5)
                continue
            failures = 0
            now = time.monotonic()
            count += 1
            if now - since >= 2.0:       # a webcam slows down in dim light; the page shows that
                self.camera_fps, count, since = count / (now - since), 0, now
            with self._cond:
                self._frame, self.taken_at, self._seq = frame, now, self._seq + 1
                self._cond.notify_all()

    def read(self, timeout: float = 2.0):
        """The newest picture not handed out yet (None if the camera stops sending)."""
        with self._cond:
            seq = self._given
            if not self._cond.wait_for(lambda: self._seq > seq or self._stop, timeout):
                return None
            self._given = self._seq
            return self._frame

    def info(self) -> dict:
        out = {"index": self.index, "name": self.name, "format": self.format, "size": list(self.size)}
        if self.camera_fps is not None:
            out["fps"] = round(self.camera_fps, 1)
        return out

    def release(self):
        self._stop = True
        with self._cond:
            self._cond.notify_all()
        self._thread.join(timeout=2.0)
        self.cap.release()
