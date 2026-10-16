"""Full Desktop gesture routing -> real clicks in our disposable text window.

Synthetic hands only. No webcam, microphone or existing document is used.
"""
from pathlib import Path
import ctypes,json,sys,time
from ctypes import wintypes
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer,Qt
from PySide6.QtGui import QTextCursor,QFont
from PySide6.QtWidgets import QApplication,QMainWindow,QPlainTextEdit
from slateink.config import Config,ROOT
from slateink.gestures import pinch_ratio
from slateink.tracking import Hand
from slateink.mouse_control import WindowsMouse,HandMouseController
from slateink.touchpad_session import TouchpadSession
from slateink.window_switching import WindowsWindowBackend


def hand(kind="open",mirrored=False):
    p=[(.5,.5,0.)]*21
    p[0]=(.5,.83,0.);p[5]=(.4,.6,0.);p[9]=(.5,.6,0.);p[17]=(.6,.6,0.)
    p[6]=(.46,.52,0.);p[10]=(.52,.52,0.);p[4]=(.5,.5,0.)
    left=.2 if kind=="left" else .8;right=.2 if kind=="right" else .8
    p[8]=(.5-left*.2,.5,0.);p[12]=(.5+right*.2,.5,0.)
    if kind=="palm":
        p[4]=(.32,.6,0.)
        for j,(mcp,pip,tip) in enumerate(((5,6,8),(9,10,12),(13,14,16),(17,18,20))):
            x=.4+j*.065
            p[mcp]=(x,.6,0.);p[pip]=(x,.48,0.);p[tip]=(x,.31,0.)
    if kind=="joined_left":
        p[0]=(.5,.8,0.);p[6]=(.48,.55,0.);p[8]=(.48,.58,0.)
        p[10]=(.52,.6,0.);p[12]=(.52,.5,0.);p[4]=(.49,.55,0.)
    if mirrored:p=[(1-x,y,z) for x,y,z in p]
    return Hand(tuple(p),pinch_ratio(p),"Left" if mirrored else "Right",.99)


def main():
    app=QApplication([]);backend=WindowsWindowBackend(excluded_pid=0);original=backend.foreground()
    window=QMainWindow();window.setWindowTitle("Gesture click verification")
    counts={"left_down":0,"left_up":0,"right_down":0,"right_up":0}
    class Text(QPlainTextEdit):
        def mousePressEvent(self,event):
            counts["left_down" if event.button()==Qt.MouseButton.LeftButton else "right_down"]+=1
            super().mousePressEvent(event)
        def mouseDoubleClickEvent(self,event):
            counts["left_down" if event.button()==Qt.MouseButton.LeftButton else "right_down"]+=1
            super().mouseDoubleClickEvent(event)
        def mouseReleaseEvent(self,event):
            counts["left_up" if event.button()==Qt.MouseButton.LeftButton else "right_up"]+=1
            super().mouseReleaseEvent(event)
        def contextMenuEvent(self,event):event.accept()
    text=Text("alpha beta gamma");text.setFont(QFont("Consolas",24))
    window.setCentralWidget(text);window.resize(800,300);window.move(200,180);window.show()
    text.setFocus();window.activateWindow()
    mouse=WindowsMouse();api=backend.api
    api.GetCursorPos.argtypes=[ctypes.POINTER(wintypes.POINT)]
    api.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
    cursor=wintypes.POINT();api.GetCursorPos(ctypes.byref(cursor))
    report={"success":False,"live_camera_opened":False,"synthetic_gestures":True,"cases":[]}
    class NoSwitch:
        def release_all(self):pass
        def switch(self,direction):raise RuntimeError("Click gesture unexpectedly requested a window swipe")
    session=None;mirrored=False;index=0;deadline=0;started=time.monotonic();phase="setup"
    program=[("palm",.35),("left",.08),("open",.12),("left",.08),("open",.12),
             ("check_word",0),("right",.16),("open",.12),("right",.07),("open",.12),
             ("joined_left",.14),("open",.12),("case_done",0)]
    before={}
    def move_target():
        c=QTextCursor(text.document());c.setPosition(8);rect=text.cursorRect(c)
        scale=window.devicePixelRatioF();p=wintypes.POINT(round(rect.center().x()*scale),round(rect.center().y()*scale))
        api.ClientToScreen(int(text.viewport().winId()),ctypes.byref(p))
        vx,vy=api.GetSystemMetrics(76),api.GetSystemMetrics(77)
        mouse.move((p.x-vx)/(api.GetSystemMetrics(78)-1),(p.y-vy)/(api.GetSystemMetrics(79)-1))
    def step():
        nonlocal phase,session,mirrored,index,deadline,before
        now=time.monotonic()
        if now-started>12:raise RuntimeError("Disposable gesture fixture timed out")
        if now-started<.6:return
        if phase=="setup":
            if backend.input_busy():return
            backend.activate(int(window.winId()));move_target()
            session=TouchpadSession(HandMouseController(Config(camera_mirrored=mirrored),mouse),None,window_switcher=NoSwitch())
            session.set_enabled(True);index=0;deadline=now+program[0][1];before=dict(counts)
            report["cases"].append({"mirrored":mirrored});phase="run";return
        if backend.foreground()!=int(window.winId()):raise RuntimeError("Fixture lost focus; no further test input")
        kind,duration=program[index]
        if kind=="check_word":
            report["cases"][-1]["word_selected"]=text.textCursor().selectedText()=="beta"
            index+=1;deadline=now+program[index][1];return
        if kind=="case_done":
            case=report["cases"][-1]
            case.update({k:counts[k]-before[k] for k in counts})
            case["success"]=case["word_selected"] and case["left_down"]==3 and case["left_up"]==3 and case["right_down"]==1 and case["right_up"]==1 and not mouse.held
            session.set_enabled(False)
            if not mirrored:
                mirrored=True;text.setPlainText("alpha beta gamma");phase="setup";return
            report["success"]=all(c["success"] for c in report["cases"]);app.quit();return
        session.process((hand(kind,mirrored),),now,aspect=4/3)
        if now>=deadline:
            index+=1;deadline=now+program[index][1]
    def guarded():
        try:step()
        except Exception as error:report["error"]=str(error);app.quit()
    timer=QTimer();timer.timeout.connect(guarded);timer.start(20)
    try:app.exec()
    finally:
        if session:session.set_enabled(False)
        mouse.release_all();backend.release_all()
        report["buttons_released"]=not mouse.held
        report["ordinary_permissions"]=not bool(ctypes.windll.shell32.IsUserAnAdmin())
        if backend.foreground()==int(window.winId()) and original and api.IsWindow(original) and not backend.input_busy():
            try:backend._alt(True);time.sleep(.02);api.SetForegroundWindow(original)
            finally:backend.release_all()
        vx,vy=api.GetSystemMetrics(76),api.GetSystemMetrics(77)
        mouse.move((cursor.x-vx)/(api.GetSystemMetrics(78)-1),(cursor.y-vy)/(api.GetSystemMetrics(79)-1))
        window.close()
        ROOT.joinpath("artifacts/native-gesture-clicks.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report,indent=2))
    return 0 if report["success"] else 1


if __name__=="__main__":raise SystemExit(main())
