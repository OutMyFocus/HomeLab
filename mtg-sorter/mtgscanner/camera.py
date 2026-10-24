"""Opening the camera: the Raspberry Pi camera (Camera Module 3 on the ribbon cable) or a
USB webcam. Both hand back OpenCV-style BGR frames from read(), or None if a frame failed."""

import cv2

WIDTH, HEIGHT = 1280, 720


class WebcamSource:
    def __init__(self, index: int):
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise SystemExit(f"Could not open camera {index}. Try --camera 1, or --demo <folder> to test without one.")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)

    def read(self):
        ok, frame = self.cap.read()
        return frame if ok else None

    def close(self):
        self.cap.release()


class PiCameraSource:
    """The Pi camera, through picamera2 (libcamera). OpenCV can't open it on a Pi 5."""

    def __init__(self):
        from picamera2 import Picamera2

        self.cam = Picamera2()
        # picamera2's "RGB888" is laid out blue-green-red in memory, which is what OpenCV expects.
        self.cam.configure(self.cam.create_video_configuration(main={"size": (WIDTH, HEIGHT), "format": "RGB888"}))
        self.cam.start()
        try:
            self.cam.set_controls({"AfMode": 2})  # keep refocusing (Camera Module 3 has autofocus)
        except Exception:
            pass  # cameras without autofocus

    def read(self):
        try:
            return self.cam.capture_array("main")
        except Exception:
            return None

    def close(self):
        self.cam.stop()
        self.cam.close()


def pi_camera_present() -> bool:
    try:
        from picamera2 import Picamera2
    except ImportError:
        return False
    try:
        return bool(Picamera2.global_camera_info())
    except Exception:
        return False


def open_camera(camera: str = "auto"):
    """camera is "pi", a webcam number like "0", or "auto" (the Pi camera if there is one,
    otherwise webcam 0)."""
    if camera == "pi" or (camera == "auto" and pi_camera_present()):
        return PiCameraSource()
    if camera == "auto":
        camera = "0"
    if not camera.isdigit():
        raise SystemExit(f'--camera should be "pi", "auto" or a webcam number, not {camera!r}')
    return WebcamSource(int(camera))
