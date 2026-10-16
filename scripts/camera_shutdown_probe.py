"""Explicit local webcam close/reopen check. No recording or desktop input."""
from dataclasses import replace
from pathlib import Path
import json,subprocess,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from slateink.config import ROOT,load_config


def session():
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from slateink.app import MainWindow
    app=QApplication([])
    w=MainWindow(replace(load_config(),initial_mode="hand_mouse",camera_preview_enabled=True))
    w.show();w.start_camera()
    started=time.monotonic();last=None;frames=0;owner=None;closing_at=None
    report={"success":False,"real_camera_opened":True,"frames_saved":0,"desktop_input_enabled":False}
    def check():
        nonlocal last,frames,owner,closing_at
        if w.worker and w.worker.source.owner:owner=w.worker.source.owner
        if w.latest_frame_at is not None and w.latest_frame_at!=last:
            last=w.latest_frame_at;frames+=1
        if closing_at is None and frames>=15:
            report["preview_live"]=bool(w.camera_preview and w.camera_preview.isVisible() and w.camera_preview.view.image)
            report["camera_fps"]=(len(w.worker.source.times)-1)/(w.worker.source.times[-1]-w.worker.source.times[0])
            closing_at=time.monotonic();w.close()
        if time.monotonic()-started>18:
            report["error"]=w.error_label.text() or "Camera close/reopen session timed out"
            w.close()
            if not w.worker:app.exit(1)
    timer=QTimer();timer.timeout.connect(check);timer.start(30)
    result=app.exec();timer.stop()
    report.update(event_loop_exited=True,frames_received=frames,owner_exited=owner is not None and not owner.is_alive(),camera_worker_finished=w.worker is None)
    if closing_at:report["close_seconds"]=round(time.monotonic()-closing_at,3)
    report["success"]=bool(result==0 and frames>=15 and report["preview_live"] and report["owner_exited"] and report["camera_worker_finished"])
    print("RESULT "+json.dumps(report),flush=True)
    return 0 if report["success"] else 1


def main():
    runs=[]
    for _ in range(2):
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),"--session"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:stdout,stderr=child.communicate(timeout=25)
        except subprocess.TimeoutExpired:
            child.terminate();child.communicate(timeout=5)
            runs.append({"success":False,"error":"Camera session process timed out"});break
        lines=[line[7:] for line in stdout.splitlines() if line.startswith("RESULT ")]
        if not lines:
            runs.append({"success":False,"exit_code":child.returncode,"error":stderr[-1200:]});break
        runs.append(json.loads(lines[-1]))
        if child.returncode:break
    report={"success":len(runs)==2 and all(r["success"] for r in runs),"recorded_images":False,"sessions":runs}
    ROOT.joinpath("artifacts/camera-shutdown.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 0 if report["success"] else 1


if __name__=="__main__":raise SystemExit(session() if "--session" in sys.argv else main())
