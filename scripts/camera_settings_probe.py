"""Inspect only camera settings. No frame or video persistence."""
import json
import cv2
cap=cv2.VideoCapture(0,cv2.CAP_DSHOW)
try:
    names=["FRAME_WIDTH","FRAME_HEIGHT","FPS","EXPOSURE","AUTO_EXPOSURE","BRIGHTNESS","GAIN","FOURCC"]
    values={name:cap.get(getattr(cv2,"CAP_PROP_"+name)) for name in names}
    print(json.dumps(values,indent=2))
finally:
    cap.release()
