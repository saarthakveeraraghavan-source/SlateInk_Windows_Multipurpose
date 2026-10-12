"""Verify local eye model on a public image; never saves webcam frames/features."""
from pathlib import Path
import sys,json,time,statistics
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from slateink.privacy import enforce_offline
enforce_offline()
import numpy as np
from PIL import Image
from slateink.eye_tracking import EyeTracker

ROOT=Path(__file__).resolve().parent.parent
tracker=EyeTracker();image=np.array(Image.open(ROOT/"artifacts/public-face-fixture.jpg").convert("RGB"))
times=[];valid=0;counts=[]
try:
    for i in range(15):
        eye,count,ms=tracker.detect(image,time.monotonic()+i*.033)
        times.append(ms);counts.append(count);valid+=bool(eye and eye.valid)
finally:tracker.close()
report={"fixture":"Google public portrait","frames":15,"exactly_one_face_all":all(c==1 for c in counts),
        "valid_eye_frames":valid,"median_ms":statistics.median(times),"no_webcam_capture":True}
print(json.dumps(report))
ROOT.joinpath("artifacts/eyes-probe.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
if not report["exactly_one_face_all"] or not valid:raise RuntimeError("Public eye model fixture failed")
