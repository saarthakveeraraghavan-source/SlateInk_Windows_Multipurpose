"""Camera owner and latest-frame mailbox. No queued video or disk storage."""
from collections import deque
from dataclasses import dataclass
import threading
import time
import cv2
from PySide6.QtCore import QThread, Signal
from .tracking import HandTracker
from .config import ROOT
from .orientation import orient_frame


class CameraSource(threading.Thread):
    def __init__(self, config):
        super().__init__(name="visible-camera", daemon=True)
        self.config = config
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.latest = None
        self.error = None
        self.times = deque(maxlen=90)
        self.sequence = 0
        self.opened = False
        self.resolution = None

    def run(self):
        backend = cv2.CAP_DSHOW if __import__("sys").platform == "win32" else cv2.CAP_ANY
        camera = cv2.VideoCapture(self.config.camera_index, backend)
        original_exposure = None
        try:
            if not camera.isOpened():
                raise RuntimeError("Cannot open webcam. Close other camera apps and check Windows camera permission.")
            camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.camera_width)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.camera_height)
            camera.set(cv2.CAP_PROP_FPS, self.config.camera_fps)
            if __import__("sys").platform == "win32" and self.config.camera_exposure is not None:
                original_exposure = camera.get(cv2.CAP_PROP_EXPOSURE)
                if not camera.set(cv2.CAP_PROP_EXPOSURE, self.config.camera_exposure):
                    raise RuntimeError("Camera rejected the configured exposure. Set camera_exposure to null to use the camera default.")
            self.opened = True
            failures = 0
            while not self.stop_event.is_set():
                ok, frame = camera.read()
                if not ok:
                    failures += 1
                    if failures >= 5:
                        raise RuntimeError("Webcam stopped delivering frames. Capture has been disabled.")
                    time.sleep(0.03)
                    continue
                failures = 0
                t = time.monotonic()
                self.resolution = (frame.shape[1], frame.shape[0])
                with self.lock:
                    self.times.append(t)
                    self.sequence += 1
                    self.latest = (self.sequence, t, frame)
        except Exception as exc:
            self.error = str(exc)
        finally:
            if original_exposure is not None:
                camera.set(cv2.CAP_PROP_EXPOSURE, original_exposure)
            camera.release()
            self.opened = False
            with self.lock:
                self.latest = None

    def get(self, last_sequence):
        with self.lock:
            if self.latest is None or self.latest[0] == last_sequence:
                return None
            fps = ((len(self.times)-1)/(self.times[-1]-self.times[0])) if len(self.times) > 1 else 0
            return (*self.latest, fps)


@dataclass
class Packet:
    rgb: object
    hand: object
    hand_count: int
    t: float
    camera_fps: float
    tracking_fps: float
    tracking_ms: float
    age_ms: float
    eye: object = None
    eye_count: int = 0
    eye_ms: float = 0
    hands: tuple = ()


class CameraWorker(QThread):
    failed = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.source = CameraSource(config)
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.latest = None

    def take(self):
        with self.lock:
            packet, self.latest = self.latest, None
            return packet

    def stop(self):
        self.stop_event.set()
        self.source.stop_event.set()

    def run(self):
        tracker = None
        eyes=None
        try:
            tracker = HandTracker(ROOT / "models" / "hand_landmarker.task")
            if self.config.initial_mode=="eye_gaze":
                from .eye_tracking import EyeTracker
                eyes=EyeTracker()
            self.source.start()
            last_sequence = -1
            processed = deque(maxlen=90)
            start = time.monotonic()
            while not self.stop_event.is_set():
                if self.source.error:
                    raise RuntimeError(self.source.error)
                current = self.source.get(last_sequence)
                if current is None:
                    if time.monotonic()-start > 5 and not self.source.opened:
                        raise RuntimeError("Webcam did not start. Check camera availability.")
                    if processed and time.monotonic()-processed[-1] > 3:
                        raise RuntimeError("Webcam stalled. Stop other camera apps and restart capture.")
                    self.msleep(3)
                    continue
                last_sequence, t, bgr, camera_fps = current
                bgr=orient_frame(bgr,self.config.camera_mirrored,self.config.camera_rotation)
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                hands,latency=tracker.detect_all(rgb,t)
                count=len(hands);hand=hands[0] if count==1 else None
                eye,eye_count,eye_ms=eyes.detect(rgb,t) if eyes is not None else (None,0,0)
                now = time.monotonic()
                processed.append(now)
                fps = (len(processed)-1)/(processed[-1]-processed[0]) if len(processed)>1 else 0
                packet = Packet(rgb, hand, count, t, camera_fps, fps, latency, (now-t)*1000,eye,eye_count,eye_ms,hands)
                with self.lock:
                    self.latest = packet
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.source.stop_event.set()
            # Keep CAMERA STOPPING visible until the actual device owner exits.
            # Never claim camera-off while a blocked native read still owns it.
            while self.source.is_alive():
                self.source.join(timeout=0.1)
            if tracker:
                tracker.close()
            if eyes:eyes.close()
            with self.lock:
                self.latest = None
