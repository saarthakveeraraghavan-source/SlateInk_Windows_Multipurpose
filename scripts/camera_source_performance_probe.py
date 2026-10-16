"""Compare acquisition patterns in the same lighting; no images are saved."""
from pathlib import Path
import json,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
from slateink.config import ROOT,load_config
from slateink.camera_source import CameraSource


def main():
    cfg=load_config();camera=cv2.VideoCapture(cfg.camera_index,cv2.CAP_DSHOW);times=[]
    old_exposure=None
    try:
        assert camera.isOpened(),"Camera unavailable"
        for prop,value in ((cv2.CAP_PROP_FOURCC,cv2.VideoWriter_fourcc(*"MJPG")),(cv2.CAP_PROP_FRAME_WIDTH,cfg.camera_width),(cv2.CAP_PROP_FRAME_HEIGHT,cfg.camera_height),(cv2.CAP_PROP_FPS,cfg.camera_fps)):
            camera.set(prop,value)
        if cfg.camera_exposure is not None:
            old_exposure=camera.get(cv2.CAP_PROP_EXPOSURE);camera.set(cv2.CAP_PROP_EXPOSURE,cfg.camera_exposure)
        start=time.monotonic()
        while time.monotonic()-start<3:
            ok,frame=camera.read()
            if ok:times.append(time.monotonic())
    finally:
        if old_exposure is not None:camera.set(cv2.CAP_PROP_EXPOSURE,old_exposure)
        camera.release()
    baseline=(len(times)-1)/(times[-1]-times[0])
    source=CameraSource(cfg);source.start();received=[];sequence=-1;started=time.monotonic()
    try:
        while time.monotonic()-started<8:
            packet=source.get(sequence)
            if packet:
                sequence,t,frame,fps=packet;received.append(t)
                if received[-1]-received[0]>=3:break
            time.sleep(.003)
    finally:source.stop_event.set();source.join(4)
    report={"baseline_direct_fps":round(baseline,2),"isolated_delivered_fps":round((len(received)-1)/(received[-1]-received[0]),2),"capture_sequence":sequence,"received_frames":len(received),"owner_exited":not source.owner.is_alive(),"frames_saved":0}
    ROOT.joinpath("artifacts/camera-source-performance.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()
