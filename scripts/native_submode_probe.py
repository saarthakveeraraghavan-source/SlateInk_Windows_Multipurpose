"""Actual WASD and equal pixel strokes confined to a disposable child window.

No webcam, game, personal document, Wispr or microphone is opened.
"""
from pathlib import Path
import ctypes,json,os,subprocess,sys,time
from ctypes import wintypes
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from slateink.config import ROOT,Config
from slateink.mouse_control import WindowsMouse
from slateink.touchpad_submodes import WindowsMovementKeys,DrawingController
from slateink.tracking import Hand
from slateink.injection import InjectionError

READY=ROOT/"artifacts/submode-corrections-fixture-ready.json"
RESULT=ROOT/"artifacts/native-submode-corrections.json"


def fixture():
    from PySide6.QtCore import Qt,QTimer
    from PySide6.QtWidgets import QApplication,QWidget
    from PySide6.QtGui import QPainter,QPen,QColor,QPixmap
    app=QApplication([])
    counts={"key_down":[],"key_up":[],"left_down":0,"left_up":0,"ink_moves":0}
    class Pad(QWidget):
        def __init__(self):
            super().__init__();self.setWindowTitle("SlateInk disposable gaming / drawing check")
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus);self.previous=None
            self.ink=QPixmap(740,400);self.ink.fill(QColor("white"))
        def paintEvent(self,event):
            p=QPainter(self);p.drawPixmap(0,0,self.ink)
            p.drawText(20,30,"Disposable fixture: WASD key releases and equal horizontal / vertical ink strokes")
        def keyPressEvent(self,event):counts["key_down"].append(event.text().upper())
        def keyReleaseEvent(self,event):counts["key_up"].append(event.text().upper())
        def mousePressEvent(self,event):
            if event.button()==Qt.MouseButton.LeftButton:counts["left_down"]+=1;self.previous=event.position()
        def mouseReleaseEvent(self,event):
            if event.button()==Qt.MouseButton.LeftButton:counts["left_up"]+=1;self.previous=None
        def mouseMoveEvent(self,event):
            if event.buttons()&Qt.MouseButton.LeftButton and self.previous is not None:
                counts["ink_moves"]+=1;p=QPainter(self.ink);p.setPen(QPen(QColor("#087f71"),3))
                p.drawLine(self.previous,event.position());p.end();self.previous=event.position();self.update()
    pad=Pad();pad.resize(740,400);pad.move(140,140);pad.show();pad.activateWindow();pad.setFocus()
    READY.write_text(json.dumps({"pid":os.getpid(),"hwnd":int(pad.winId())}),encoding="utf-8")
    def finish():
        pad.grab().save(str(ROOT/"artifacts/native-submode-corrections-ink.png"))
        RESULT.write_text(json.dumps(counts,indent=2),encoding="utf-8");app.quit()
    QTimer.singleShot(9000,finish);app.exec()


def hand(hover=True,x=.5,y=.65,pinch=False):
    p=[(x,y,0)]*21;p[0]=(x,y+.2,0);p[5]=(x-.1,y,0);p[9]=(x,y,0);p[17]=(x+.1,y,0);p[4]=(x-.18,y,0)
    for j,(tip,pip) in enumerate(((8,6),(12,10),(16,14),(20,18))):
        xx=x-.05+j*.05;p[pip]=(xx,y-.12,0)
        p[tip]=(xx,y-.32 if j==0 or (j==1 and hover) else y+.03,0)
    if pinch:p[8]=(x-.17,y-.04,0)
    return Hand(tuple(p),.15 if pinch else .8,"Right")


def probe():
    api=ctypes.WinDLL("user32");api.SetProcessDPIAware()
    api.GetForegroundWindow.restype=wintypes.HWND
    api.SetForegroundWindow.argtypes=[wintypes.HWND]
    api.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    api.GetCursorPos.argtypes=[ctypes.POINTER(wintypes.POINT)]
    original=wintypes.POINT();api.GetCursorPos(ctypes.byref(original));original_window=api.GetForegroundWindow()
    for path in (READY,RESULT):
        if path.exists():path.unlink()
    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),"--fixture"])
    mouse=WindowsMouse();keys=WindowsMovementKeys();draw=DrawingController(Config(),mouse,keys.target)
    try:
        deadline=time.monotonic()+5;info=None
        while time.monotonic()<deadline:
            if READY.exists():
                info=json.loads(READY.read_text(encoding="utf-8"))
                target=keys.target()
                if target and target[1]==info["pid"]:break
            time.sleep(.03)
        else:raise RuntimeError("Disposable fixture did not obtain focus; no input sent.")
        time.sleep(.3)
        def check():
            if keys.target()!=(info["hwnd"],info["pid"]) or api.GetAsyncKeyState(0x1b)&0x8000:
                raise RuntimeError("Fixture focus / Escape interrupted validation; held input will release.")
        rect=wintypes.RECT();api.GetWindowRect(info["hwnd"],ctypes.byref(rect))
        vx,vy=api.GetSystemMetrics(76),api.GetSystemMetrics(77);vw,vh=api.GetSystemMetrics(78),api.GetSystemMetrics(79)
        def move(x,y):check();mouse.move((x-vx)/(vw-1),(y-vy)/(vh-1));time.sleep(.04)
        check()
        for name in ("W","A","S","D"):
            check();keys.key(name,True);time.sleep(.035);keys.key(name,False);time.sleep(.035)
        check();keys.key("W",True);keys.key("D",True);time.sleep(.1);keys.release_all()
        strokes=[]
        for horizontal in (True,False):
            draw.interrupt();move(rect.left+220,rect.top+(140 if horizontal else 220))
            t=time.monotonic()
            for i in range(6):check();draw.process(hand(),t+i*.033);time.sleep(.033)
            for i in range(5):check();draw.process(hand(False),t+.22+i*.033);time.sleep(.033)
            start=wintypes.POINT();api.GetCursorPos(ctypes.byref(start))
            for i in range(1,21):
                check();draw.process(hand(False,x=.5+(i*.002/(4/3) if horizontal else 0),y=.65+(0 if horizontal else i*.002)),t+.39+i*.033);time.sleep(.033)
            end=wintypes.POINT();api.GetCursorPos(ctypes.byref(end));strokes.append([end.x-start.x,end.y-start.y])
            check();draw.process(hand(),t+1.1);time.sleep(.05);draw.interrupt()
        # Tool navigation click through DrawingController, at a fixed target.
        draw.interrupt();move(rect.left+460,rect.top+160);t=time.monotonic()
        for i in range(6):check();draw.process(hand(),t+i*.033);time.sleep(.033)
        click_start=wintypes.POINT();api.GetCursorPos(ctypes.byref(click_start))
        for i in range(6):check();draw.process(hand(pinch=True),t+.22+i*.033);time.sleep(.033)
        for i in range(6):check();draw.process(hand(),t+.44+i*.033);time.sleep(.033)
        click_end=wintypes.POINT();api.GetCursorPos(ctypes.byref(click_end))
        click_stayed_at_target=abs(click_start.x-click_end.x)<=1 and abs(click_start.y-click_end.y)<=1
        keys.release_all();draw.interrupt();mouse.release_all()
        child.wait(timeout=12)
        counts=json.loads(RESULT.read_text(encoding="utf-8"))
        success=(counts["key_down"]==["W","A","S","D","W","D"] and sorted(counts["key_up"])==["A","D","D","S","W","W"]
                 and counts["left_down"]==3 and counts["left_up"]==3 and counts["ink_moves"]>0 and click_stayed_at_target
                 and abs(strokes[0][0]-strokes[1][1])<=2 and strokes[0][0]>20 and strokes[0][1]==0 and strokes[1][0]==0)
        counts.update(success=success,pixel_strokes=strokes,drawing_pinch_click_stayed_at_target=click_stayed_at_target,held_input_released=not keys.held and not mouse.held,
                      physical_gestures_tested=False,target="disposable native Qt window",ordinary_permissions=not bool(ctypes.windll.shell32.IsUserAnAdmin()))
        RESULT.write_text(json.dumps(counts,indent=2),encoding="utf-8");print(json.dumps(counts,indent=2))
        if not success:raise RuntimeError("Native sub-mode fixture failed.")
    finally:
        try:keys.release_all()
        finally:
            try:draw.interrupt();mouse.release_all()
            finally:
                if child.poll() is None:child.terminate();child.wait(timeout=5)
                vw,vh=api.GetSystemMetrics(78),api.GetSystemMetrics(79);vx,vy=api.GetSystemMetrics(76),api.GetSystemMetrics(77)
                mouse.move((original.x-vx)/(vw-1),(original.y-vy)/(vh-1))
                if original_window:api.SetForegroundWindow(original_window)


if __name__=="__main__":
    fixture() if "--fixture" in sys.argv else probe()
