"""Compare a shorter camera exposure, restoring original settings after test."""
import json
from pathlib import Path
import time
import cv2

cap=cv2.VideoCapture(0,cv2.CAP_DSHOW)
original=cap.get(cv2.CAP_PROP_EXPOSURE)
times=[]
brightness=[]
try:
    cap.set(cv2.CAP_PROP_FOURCC,cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
    cap.set(cv2.CAP_PROP_FPS,30)
    changed=cap.set(cv2.CAP_PROP_EXPOSURE,-5)
    actual=cap.get(cv2.CAP_PROP_EXPOSURE)
    for k in range(160):
        ok,frame=cap.read()
        if not ok:
            raise RuntimeError("Camera read failed")
        if k>15:
            times.append(time.monotonic())
            brightness.append(float(frame.mean()))
finally:
    restored=cap.set(cv2.CAP_PROP_EXPOSURE,original)
    cap.release()
result={"original_exposure":original,"tested_exposure":-5,"actual_exposure":actual,
        "setting_applied":changed,"fps":(len(times)-1)/(times[-1]-times[0]),
        "mean_brightness":sum(brightness)/len(brightness),"restored_original_exposure":restored}
print(json.dumps(result,indent=2))
Path("artifacts/exposure-test.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
