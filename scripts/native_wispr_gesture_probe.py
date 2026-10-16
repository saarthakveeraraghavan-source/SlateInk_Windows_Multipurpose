"""Latched rock/swag routing to a disposable native shortcut receiver.

Synthetic hands, no webcam/audio. Win and Escape map to fixture-only F8/F9;
this proves native key delivery, not actual Wispr acceptance or recording.
"""
from pathlib import Path
import ctypes,json,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer,Qt
from PySide6.QtWidgets import QApplication,QPlainTextEdit
from slateink.config import Config,ROOT
from slateink.desktop_shortcuts import WindowsWisprShortcut
from slateink.gestures import pinch_ratio
from slateink.mouse_control import WindowsMouse,HandMouseController
from slateink.touchpad_session import TouchpadSession
from slateink.tracking import Hand
from slateink.window_switching import WindowsWindowBackend


def pose(kind,label,mirrored):
    p=[(.5,.6,0.)]*21;p[0]=(.5,.85,0.);p[4]=(.3,.65,0.)
    for j,(mcp,pip,tip) in enumerate(((5,6,8),(9,10,12),(13,14,16),(17,18,20))):
        x=.4+j*.065;p[mcp]=(x,.65,0.);p[pip]=(x,.53,0.)
        p[tip]=(x,.33 if kind in ("rock","swag") and j in (0,3) else .68,0.)
    if kind in ("rock","swag"):
        p[2]=(.35,.7,0.);p[3]=(.43,.68,0.);p[4]=(.5,.67,0.)
    if kind=="swag":p[2]=(.35,.7,0.);p[3]=(.31,.65,0.);p[4]=(.21,.62,0.)
    if mirrored:p=[(1-x,y,z) for x,y,z in p]
    return Hand(tuple(p),pinch_ratio(p),label,.99)


def main():
    app=QApplication([]);events=[];backend=WindowsWindowBackend(excluded_pid=0)
    original=backend.foreground()
    class Receiver(QPlainTextEdit):
        def keyPressEvent(self,event):
            if event.key()==Qt.Key.Key_F8 and event.modifiers()&Qt.KeyboardModifier.ControlModifier:
                events.append("toggle");event.accept();return
            if event.key()==Qt.Key.Key_F9:events.append("cancel");event.accept();return
            super().keyPressEvent(event)
    window=Receiver("Temporary gesture shortcut receiver");window.setWindowTitle("Wispr gesture verification")
    window.resize(600,220);window.show();window.activateWindow();window.setFocus()
    class FixtureShortcut(WindowsWisprShortcut):
        def key(self,vk,down):super().key({0x5B:0x77,0x1B:0x78}.get(vk,vk),down)
        def flow_running(self):return True
    keys=FixtureShortcut();destination=keys.injector.destination
    keys.injector.destination=lambda:destination(allow_own=True)
    mouse=WindowsMouse()
    report={"success":False,"synthetic_hands":True,"microphone_opened":False,"actual_wispr_tested":False,"cases":[]}
    program=[("neutral",.35),("rock",.1),("absent",.6),("other_swag",.25),("stale",.25),("check",0),("swag",.15),("done",0)]
    session=None;mirrored=False;phase="focus";index=0;due=0;started=time.monotonic();baseline=0
    def step():
        nonlocal session,mirrored,phase,index,due,baseline
        now=time.monotonic()
        if now-started>12:raise RuntimeError("Native gesture receiver timed out")
        if now-started<.6:return
        if phase=="focus":
            if backend.input_busy():return
            backend.activate(int(window.winId()))
            session=TouchpadSession(HandMouseController(Config(camera_mirrored=mirrored,wispr_enabled=True),mouse),keys)
            session.set_enabled(True);baseline=len(events);index=0;due=now+program[0][1];phase="run"
            report["cases"].append({"mirrored":mirrored});return
        if backend.foreground()!=int(window.winId()):raise RuntimeError(f"Disposable receiver lost focus during {program[index][0]}")
        kind,_=program[index];owner="Left" if mirrored else "Right"
        other="Right" if mirrored else "Left"
        if kind=="check":
            case=report["cases"][-1]
            case["listening_after_hand_loss_other_hand_and_staleness"]=session.dictating and events[baseline:]==["toggle"]
            index+=1;due=now+program[index][1];return
        if kind=="done":
            case=report["cases"][-1]
            case["same_hand_swag_stopped_once"]=not session.dictating and events[baseline:]==["toggle","toggle"]
            case["keys_released"]=not keys.owned;session.set_enabled(False)
            if not mirrored:mirrored=True;phase="focus";return
            report["success"]=all(all(v for k,v in case.items() if k!="mirrored") for case in report["cases"])
            app.quit();return
        if kind=="stale":session.tracking_stale()
        else:
            hands=() if kind=="absent" else (pose("swag" if kind=="other_swag" else kind,other if kind=="other_swag" else owner,mirrored),)
            session.process(hands,now)
        if now>=due:index+=1;due=now+program[index][1]
    def guarded():
        try:step()
        except Exception as error:report["error"]=str(error);app.quit()
    timer=QTimer();timer.timeout.connect(guarded);timer.start(20)
    try:app.exec()
    finally:
        if backend.foreground()!=int(window.winId()):keys.active=False
        if session:session.set_enabled(False)
        keys.cancel();mouse.release_all();backend.release_all()
        report["keys_released"]=not keys.owned
        report["ordinary_permissions"]=not bool(ctypes.windll.shell32.IsUserAnAdmin())
        if backend.foreground()==int(window.winId()) and original and backend.api.IsWindow(original) and not backend.input_busy():
            try:backend._alt(True);time.sleep(.02);backend.api.SetForegroundWindow(original)
            finally:backend.release_all()
        window.close()
        ROOT.joinpath("artifacts/native-wispr-gestures.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report,indent=2))
    return 0 if report["success"] else 1


if __name__=="__main__":raise SystemExit(main())
