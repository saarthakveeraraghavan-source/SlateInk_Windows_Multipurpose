"""Visible camera performance check. Saves aggregate timings only; no eye data."""
import sys,time,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from slateink.privacy import enforce_offline
enforce_offline()
from dataclasses import replace
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from slateink.app import MainWindow
from slateink.config import load_config,ROOT

app=QApplication([]);window=MainWindow(replace(load_config(),initial_mode="eye_gaze"))
window.show();window.start_camera();start=time.monotonic();rows=[];stopped=False
def check():
    global stopped
    if window.worker and time.monotonic()-start>3:
        source=window.worker.source
        with window.worker.lock:packet=window.worker.latest
        if packet:rows.append((packet.camera_fps,packet.tracking_fps,packet.tracking_ms,packet.eye_ms,packet.age_ms))
    if not stopped and time.monotonic()-start>10:
        stopped=True;window.stop_camera()
    if stopped and window.worker is None:
        import numpy as np
        values=np.median(rows,axis=0) if rows else [0]*5
        report=dict(zip(("camera_fps","processed_fps","hand_ms","eyes_ms","frame_age_ms"),map(float,values)))
        report.update(camera_released=True,desktop_control_enabled=False,saved_frames=False,saved_eye_features=False)
        ROOT.joinpath("artifacts/live-gaze-metrics.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report,indent=2),flush=True);window.close()
timer=QTimer();timer.timeout.connect(check);timer.start(15)
app.exec()
