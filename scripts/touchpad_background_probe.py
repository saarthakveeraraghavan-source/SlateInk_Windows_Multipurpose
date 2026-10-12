"""Native minimize/resume lifecycle with synthetic hands and no desktop input."""
from pathlib import Path
import sys,time,json,threading
from collections import deque
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from slateink.privacy import enforce_offline
enforce_offline()
import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from slateink.app import MainWindow
from slateink.config import Config,ROOT
from slateink.camera import Packet
from slateink.mouse_control import HandMouseController
from slateink.tracking import Hand

app=QApplication([]);w=MainWindow(Config(initial_mode="hand_mouse",touchpad_background=True))
class Sink:
    def __init__(self):self.moves=0
    def release_all(self):pass
    def move_relative(self,*p):self.moves+=1
    def button(self,*p):raise RuntimeError("Unexpected button input")
class Tray:
    def setToolTip(self,*a):pass
    def setVisible(self,*a):pass
    def hide(self):pass
sink=Sink();w.hand_mouse=HandMouseController(w.config,sink);w.touchpad_session.controller=w.hand_mouse
w.tray=Tray()
class Source:
    times=deque(maxlen=90)
class Camera:
    def __init__(self):self.stop_event=threading.Event();self.source=Source()
    def stop(self):self.stop_event.set();QTimer.singleShot(10,w.camera_finished)
    def deleteLater(self):pass
    def take(self):
        now=time.monotonic();x=.5+.05*np.sin(now*2);p=[(x,.6,0)]*21
        p[0]=(x,.85,0);p[5]=(x-.1,.6,0);p[17]=(x+.1,.6,0);p[9]=(x,.6,0)
        p[4]=(x-.18,.6,0);p[6]=(x-.04,.47,0);p[10]=(x+.01,.47,0)
        p[8]=(x-.04,.3,0);p[12]=(x+.01,.3,0)
        h=Hand(tuple(p),.8,"Left");self.source.times.append(now)
        return Packet(np.full((480,640,3),80,np.uint8),h,1,now,30,30,0,0,hands=(h,))
w.worker=Camera();w.camera_started_at=time.monotonic();w.show();w.touchpad_session.set_enabled(True)
started=time.monotonic();stage=0;before=0;success=False
def check():
    global stage,before,success
    elapsed=time.monotonic()-started
    if elapsed>9:raise RuntimeError("Background fixture timed out")
    if stage==0 and elapsed>1:
        before=sink.moves;w.showMinimized();stage=1
    elif stage==1 and elapsed>2:
        assert w.isMinimized() and w.worker is not None and w.hand_mouse.enabled and sink.moves>before
        w.toggle_touchpad();assert w.touchpad_session.paused;before=sink.moves;stage=2
    elif stage==2 and elapsed>3:
        assert sink.moves==before;w.toggle_touchpad();assert not w.touchpad_session.paused;stage=3
    elif stage==3 and elapsed>4:
        assert sink.moves>before;w.emergency_stop();stage=4
    elif stage==4 and w.worker is None:
        success=True
        report={"synthetic_camera":True,"real_camera_opened":False,"continued_when_minimized":True,"pause_resume":True,"escape_stop_path":True,"actual_desktop_input_events":0,"camera_released":True,"success":True}
        ROOT.joinpath("artifacts/touchpad-background-probe.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report,indent=2),flush=True);w.close()
def guarded():
    try:check()
    except Exception as exc:print(type(exc).__name__+": "+str(exc),flush=True);w.close()
timer=QTimer();timer.timeout.connect(guarded);timer.start(30)
app.exec()
if not success:raise SystemExit(1)
