from dataclasses import dataclass
import time
import numpy as np
import mediapipe as mp
from .gestures import pinch_ratio


@dataclass(frozen=True)
class Hand:
    landmarks: tuple
    ratio: float | None
    label: str
    handedness_confidence: float = 1.0

    @property
    def index(self):
        return self.landmarks[8][:2]


class HandTracker:
    def __init__(self, model_path):
        if not model_path.exists():
            raise FileNotFoundError("Hand model missing. Run scripts/setup_models.py once.")
        from .models import verify_assets,HAND_FILES
        verify_assets(HAND_FILES)
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=2, min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.6, min_tracking_confidence=0.6)
        self.detector = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self.previous_timestamp = -1

    def detect(self, rgb, t):
        hands,latency=self.detect_all(rgb,t)
        return (hands[0] if len(hands)==1 else None),len(hands),latency

    def detect_all(self,rgb,t):
        timestamp = max(self.previous_timestamp + 1, int(t*1000))
        self.previous_timestamp = timestamp
        start = time.perf_counter()
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        result = self.detector.detect_for_video(image, timestamp)
        latency = (time.perf_counter()-start)*1000
        hands=[]
        for landmarks,handedness in zip(result.hand_landmarks,result.handedness):
            points=tuple((p.x,p.y,p.z) for p in landmarks)
            hands.append(Hand(points,pinch_ratio(points,rgb.shape[1]/rgb.shape[0]),handedness[0].category_name,handedness[0].score))
        return tuple(hands),latency

    def close(self):
        self.detector.close()
