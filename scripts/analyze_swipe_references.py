"""Offline reference-video hand observations; never sends desktop input."""
from pathlib import Path
import json
import hashlib
import sys
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from slateink.privacy import enforce_offline
enforce_offline()
from slateink.tracking import HandTracker
from slateink.hand_gestures import fingers,open_palm,distance
from slateink.mouse_control import middle_pinch_ratio


def analyze(filenames=None,out=None):
    filenames=filenames or ("Next_Swipe-Gesture (2).mp4","Previous_Swipe-Gesture (2).mp4")
    out=Path(out) if out else ROOT/"artifacts/right-hand-swipe-20261015"
    out.mkdir(parents=True,exist_ok=True)
    for filename in filenames:
        if not (ROOT/filename).is_file():raise FileNotFoundError(filename)
        for mirrored in (False,True):
            capture=cv2.VideoCapture(str(ROOT/filename));fps=capture.get(cv2.CAP_PROP_FPS)
            if not capture.isOpened() or fps<=0:raise ValueError("Cannot decode reference video: "+filename)
            tracker=HandTracker(ROOT/"models/hand_landmarker.task");rows=[];i=0
            try:
                while True:
                    ok,bgr=capture.read()
                    if not ok:break
                    bgr=cv2.resize(bgr,(640,360))
                    if mirrored:bgr=cv2.flip(bgr,1)
                    rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
                    hands,_=tracker.detect_all(rgb,1+i/fps)
                    row={"frame":i,"t":i/fps,"hands":[]}
                    for hand in hands:
                        aspect=rgb.shape[1]/rgb.shape[0];p=np.array(hand.landmarks)
                        palm=distance(hand,5,17,aspect);length=distance(hand,0,9,aspect)
                        normal=np.cross(p[5]-p[0],p[17]-p[0]);normal=normal/(np.linalg.norm(normal) or 1)
                        row["hands"].append({"label":hand.label,"confidence":hand.handedness_confidence,
                            "ratio":hand.ratio,"middle_ratio":middle_pinch_ratio(hand,aspect),
                            "fingers":fingers(hand,aspect),"open":open_palm(hand,aspect),
                            "palm":palm,"length":length,"width_length":palm/(length or 1),
                            "center":p[[0,5,9,17],:2].mean(axis=0).tolist(),
                            "tips":p[[8,12,16,20],:2].mean(axis=0).tolist(),
                            "normal":normal.tolist(),"landmarks":hand.landmarks})
                    rows.append(row);i+=1
            finally:capture.release();tracker.close()
            target=out/(Path(filename).stem+("-mirrored" if mirrored else "-raw")+".json")
            target.write_text(json.dumps({"video":filename,"sha256":hashlib.sha256((ROOT/filename).read_bytes()).hexdigest(),"mirrored":mirrored,"fps":fps,"aspect":640/360,"rows":rows},indent=2),encoding="utf-8")
            print(filename,"mirrored",mirrored,"detected",sum(bool(row["hands"]) for row in rows),"of",len(rows))
            for row in rows if "--verbose" in sys.argv else ():
                if row["hands"]:
                    h=row["hands"][0]
                    print(row["frame"],round(row["t"],2),h["label"],round(h["confidence"],2),h["fingers"],round(h["ratio"],2),round(h["width_length"],2),[round(v,3) for v in h["center"]],[round(v,3) for v in h["tips"]])


if __name__=="__main__":analyze()
