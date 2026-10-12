"""Track a public hand example offline; never capture the user's camera."""
import json
from pathlib import Path
import statistics
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from slateink.privacy import enforce_offline
enforce_offline()
import cv2
from slateink.config import ROOT
from slateink.tracking import HandTracker

image=cv2.imread(str(ROOT/"artifacts"/"public-hand.jpg"))
if image is None: raise RuntimeError("Public test image missing")
image=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
tracker=HandTracker(ROOT/"models"/"hand_landmarker.task")
latencies=[]
try:
    for i in range(60):
        hand,count,ms=tracker.detect(image,time.monotonic()+i*0.034)
        latencies.append(ms)
        if hand is None or count!=1:
            raise RuntimeError("Expected one hand in the public fixture")
    result={"fixture":"Google MediaPipe pointing_up.jpg", "single_hand_detected":True,
            "landmarks":len(hand.landmarks),"index_tip_available":True,"thumb_tip_available":True,
            "pinch_ratio_available":hand.ratio is not None,
            "median_tracking_ms":statistics.median(latencies[5:]),"offline":True}
    (ROOT/"artifacts"/"tracking-fixture.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
finally:
    tracker.close()
