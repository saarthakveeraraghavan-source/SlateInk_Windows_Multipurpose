"""Native Qt calibration/retry fixture. Synthetic camera/eyes only; no desktop input."""
from pathlib import Path
import sys,json,time,threading,argparse
from collections import deque
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from slateink.privacy import enforce_offline
enforce_offline()
import numpy as np
from PySide6.QtCore import QTimer,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from slateink.app import MainWindow
from slateink.config import Config,ROOT
from slateink.camera import Packet
from slateink.eye_tracking import EyeObservation
from slateink.gaze import GazeController
from slateink.mouse_control import HandMouseController
from slateink.tracking import Hand

parser=argparse.ArgumentParser();parser.add_argument("--unverified",action="store_true");args=parser.parse_args()
app=QApplication([]);window=MainWindow(Config(initial_mode="eye_gaze",gaze_allow_unverified=args.unverified))
class Sink:
    def __init__(self):self.events=[];self.held=set()
    def release_all(self):
        for name in tuple(self.held):self.button(name,False)
    def move(self,*p):self.events.append("move")
    def button(self,name,down):
        self.events.append((name,down))
        if down:self.held.add(name)
        else:self.held.discard(name)
sink=Sink();window.mouse_sink=sink;window.hand_mouse=HandMouseController(window.config,sink)
window.gaze_controller=GazeController(window.config,sink,window.gaze_calibration)
class Source:
    def __init__(self):self.times=deque(maxlen=90)
class SyntheticCamera:
    def __init__(self):self.stop_event=threading.Event();self.source=Source();self.last=0;self.active_at=None
    def stop(self):self.stop_event.set();QTimer.singleShot(10,window.camera_finished)
    def deleteLater(self):pass
    def take(self):
        now=time.monotonic()
        if now-self.last<1/30:return None
        self.last=now;self.source.times.append(now)
        d=window.gaze_dialog;x,y=d.target if d else (.5,.5)
        bad=d and d.phase=="validate" and d.validation_order[d.index]==2 and fail_once
        o=EyeObservation((.35+.2*x,.03*(y-.5),.65-.2*x,-.03*(y-.5)),(.7,.5,.2) if bad else (.5,.5,.2),((.4,.4),(.6,.4)),True)
        hand=None
        if args.unverified and window.gaze_controller.enabled:
            if self.active_at is None:self.active_at=now
            left=.2 if .7<=now-self.active_at<1.15 else .8
            p=[(.5,.5,0)]*21;p[5]=(.4,.6,0);p[17]=(.6,.6,0);p[12]=(.66,.5,0);p[8]=(.5+left*.2,.5,0)
            hand=Hand(tuple(p),left,"Left")
        return Packet(np.full((480,640,3),70,np.uint8),hand,int(hand is not None),now,30,30,0,0,o,1,0)
window.worker=SyntheticCamera();window.camera_started_at=time.monotonic();window.last_packet_time=window.camera_started_at
window.show();started=time.monotonic();fail_once=True;stage="open";retained={};mapping=None;success=False
report={"synthetic_camera":True,"real_webcam_opened":False,"private_data_used":False}
def check():
    global stage,fail_once,retained,mapping,success
    if time.monotonic()-started>50:
        d=window.gaze_dialog
        raise RuntimeError(f"Synthetic calibration timed out: stage={stage}; phase={d.phase if d else 'none'}; dot={d.index if d else -1}; camera={window.worker is not None}; status={d.status.text() if d else window.hint.text()}")
    if stage=="open" and window.calibrate_button.isEnabled():
        window.begin_gaze_calibration();stage="setup"
    d=window.gaze_dialog
    if stage=="setup" and d.start_button.isEnabled():
        QTest.mouseClick(d.start_button,Qt.MouseButton.LeftButton)
        assert d.phase=="calibrate"
        d.grab().save(str(ROOT/"artifacts/calibration-target-synthetic.png"));stage="first_result"
    elif args.unverified and stage=="first_result" and d.phase=="validate":
        QTest.mouseClick(d.use_button,Qt.MouseButton.LeftButton)
        assert window.gaze_dialog is None and not window.gaze_calibration.validated
        assert window.unverified_gaze.isChecked() and window.pointer_button.isEnabled()
        QTest.mouseClick(window.pointer_button,Qt.MouseButton.LeftButton);stage="unverified_pointer"
    elif stage=="unverified_pointer" and ("left",False) in sink.events:
        assert window.gaze_controller.enabled and window.gaze_controller.unverified and not sink.held
        assert not window.gaze_calibration.validated
        report.update(nine_point_fit_completed=True,last_five_skipped=True,unverified_control_enabled=True,
                      simulated_left_click=True,actual_desktop_input_events=0)
        window.stop_camera();stage="closing"
    elif stage=="first_result" and d.phase=="done":
        assert not d.calibration.validated and d.report["retry_indices"]==[2]
        assert len(d.calibration.groups)==9 and len(d.checks)==5 and not sink.events
        d.grab().save(str(ROOT/"artifacts/calibration-retry-synthetic.png"))
        retained={i:id(v) for i,v in d.checks.items() if i!=2};mapping=d.calibration.weights.copy()
        fail_once=False;QTest.mouseClick(d.retry_button,Qt.MouseButton.LeftButton)
        assert d.phase=="validate" and d.validation_order==[2]
        report.update(all_fourteen_completed=True,only_failed_dot_retried=True);stage="retry_result"
    elif stage=="retry_result" and d.phase=="done":
        assert d.calibration.validated and np.array_equal(d.calibration.weights,mapping)
        assert all(id(d.checks[i])==v for i,v in retained.items()) and not sink.events
        QTest.mouseClick(d.return_button,Qt.MouseButton.LeftButton)
        assert window.gaze_dialog is None and window.pointer_button.isEnabled() and not window.gaze_controller.enabled
        report.update(successful_checks_retained=True,fit_retained=True,desktop_input_events=0,returned_to_app=True)
        window.stop_camera();stage="closing"
    elif stage=="closing" and window.worker is None:
        report.update(success=True,camera_released=True);success=True
        ROOT.joinpath("artifacts/calibration-unverified-probe.json" if args.unverified else "artifacts/calibration-flow-probe.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report,indent=2),flush=True);window.close()
def guarded_check():
    try:check()
    except Exception as exc:
        print(type(exc).__name__+": "+str(exc),flush=True);window.close()
timer=QTimer();timer.timeout.connect(guarded_check);timer.start(30)
app.exec()
if not success:raise SystemExit(1)
