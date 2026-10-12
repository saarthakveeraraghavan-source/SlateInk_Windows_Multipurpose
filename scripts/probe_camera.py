"""Measure camera/tracker in memory. Prints metrics only, never images/text."""
import argparse
import json
from pathlib import Path
import sys
import time
import statistics
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from slateink.privacy import enforce_offline
enforce_offline()
import cv2
from slateink.config import ROOT,load_config
from slateink.tracking import HandTracker


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--seconds",type=float,default=8)
    parser.add_argument("--tracking",action="store_true")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    config=load_config()
    cap=cv2.VideoCapture(config.camera_index,cv2.CAP_DSHOW if sys.platform=="win32" else cv2.CAP_ANY)
    detector=None
    original_exposure=None
    try:
        if not cap.isOpened():
            raise RuntimeError("Cannot open camera")
        cap.set(cv2.CAP_PROP_FOURCC,cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,config.camera_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT,config.camera_height)
        cap.set(cv2.CAP_PROP_FPS,config.camera_fps)
        if sys.platform=="win32" and config.camera_exposure is not None:
            original_exposure=cap.get(cv2.CAP_PROP_EXPOSURE)
            if not cap.set(cv2.CAP_PROP_EXPOSURE,config.camera_exposure):
                raise RuntimeError("Configured exposure rejected")
        if args.tracking:
            detector=HandTracker(ROOT/"models"/"hand_landmarker.task")
        # Warm up exposure and model; exclude this from steady-state measurement.
        for _ in range(10):
            ok,frame=cap.read()
            if not ok: raise RuntimeError("Camera read failed")
            if detector: detector.detect(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB),time.monotonic())
        start=time.perf_counter()
        times=[]
        latencies=[]
        hand_counts=[]
        while time.perf_counter()-start < args.seconds:
            ok,frame=cap.read()
            if not ok: raise RuntimeError("Camera read failed")
            times.append(time.perf_counter())
            if detector:
                _,count,ms=detector.detect(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB),time.monotonic())
                latencies.append(ms)
                hand_counts.append(count)
        result={"frames":len(times),"elapsed_seconds":time.perf_counter()-start,
                "measured_fps":(len(times)-1)/(times[-1]-times[0]),
                "resolution":[frame.shape[1],frame.shape[0]],"reported_camera_fps":cap.get(cv2.CAP_PROP_FPS),
                "tracking":args.tracking,"hand_present_frames":sum(n==1 for n in hand_counts)}
        result["configured_exposure"]=config.camera_exposure
        if latencies:
            result.update(tracking_median_ms=statistics.median(latencies),tracking_p95_ms=sorted(latencies)[int(len(latencies)*0.95)])
        print(json.dumps(result,indent=2))
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(result,indent=2),encoding="utf-8")
    finally:
        if original_exposure is not None:
            cap.set(cv2.CAP_PROP_EXPOSURE,original_exposure)
        cap.release()
        if detector: detector.close()


if __name__=="__main__":
    main()
