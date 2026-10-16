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


from .camera_source import CameraSource


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
