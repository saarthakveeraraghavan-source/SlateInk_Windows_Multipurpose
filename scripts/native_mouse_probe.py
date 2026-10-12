"""Native click/drag/right-click confined to a disposable test window."""
from pathlib import Path
import argparse,ctypes,json,os,subprocess,sys,time
from ctypes import wintypes
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from slateink.privacy import enforce_offline
enforce_offline()
from slateink.mouse_control import WindowsMouse
from slateink.injection import WindowsInjector
ROOT=Path(__file__).resolve().parent.parent
READY=ROOT/"artifacts/mouse-fixture-ready.json"
RESULT=ROOT/"artifacts/native-mouse.json"


def fixture():
    from PySide6.QtCore import QTimer,Qt
    from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QLabel
    app=QApplication([]); window=QMainWindow(); window.setWindowTitle("SlateInk disposable mouse validation")
    counts={"left_down":0,"left_up":0,"right_down":0,"right_up":0,"drag_moves":0,"vertical_wheel":0,"horizontal_wheel":0}
    class Pad(QWidget):
        def __init__(self):
            super().__init__();self.setMouseTracking(True)
            layout=QVBoxLayout(self);layout.addWidget(QLabel("Disposable mouse fixture only.\nLeft click, drag, right click and title-bar drag are tested here."))
        def mousePressEvent(self,event):
            key="left_down" if event.button()==Qt.MouseButton.LeftButton else "right_down"
            counts[key]+=1
        def mouseReleaseEvent(self,event):
            key="left_up" if event.button()==Qt.MouseButton.LeftButton else "right_up"
            counts[key]+=1
        def mouseMoveEvent(self,event):
            if event.buttons()&Qt.MouseButton.LeftButton:counts["drag_moves"]+=1
        def contextMenuEvent(self,event):event.accept()
        def wheelEvent(self,event):
            counts["vertical_wheel"]+=abs(event.angleDelta().y());counts["horizontal_wheel"]+=abs(event.angleDelta().x());event.accept()
    window.setCentralWidget(Pad());window.resize(700,340);window.move(180,160);window.show();window.activateWindow();window.raise_()
    READY.write_text(json.dumps({"pid":os.getpid(),"hwnd":int(window.winId())}),encoding="utf-8")
    def activate():
        api=ctypes.WinDLL("user32");api.SetForegroundWindow.argtypes=[wintypes.HWND]
        api.SetForegroundWindow(int(window.winId()))
    QTimer.singleShot(500,activate)
    def finish():
        RESULT.write_text(json.dumps(counts,indent=2),encoding="utf-8");app.quit()
    QTimer.singleShot(8000,finish);app.exec()


def probe():
    api=ctypes.WinDLL("user32");api.SetProcessDPIAware()
    api.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    api.GetCursorPos.argtypes=[ctypes.POINTER(wintypes.POINT)]
    original=wintypes.POINT();api.GetCursorPos(ctypes.byref(original))
    for path in (READY,RESULT):
        if path.exists():path.unlink()
    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),"--fixture"])
    mouse=WindowsMouse(); injector=WindowsInjector(); deadline=time.monotonic()+6
    info=None;stable=None;since=None
    try:
        while time.monotonic()<deadline:
            if READY.exists():
                info=json.loads(READY.read_text(encoding="utf-8"))
                try:
                    current=injector.destination()
                    if current.pid==info["pid"]:
                        if stable!=current:stable=current;since=time.monotonic()
                        elif time.monotonic()-since>0.7:break
                except Exception:pass
            time.sleep(0.03)
        else:raise RuntimeError("Fixture did not obtain focus. No mouse input sent.")
        rect=wintypes.RECT();api.GetWindowRect(info["hwnd"],ctypes.byref(rect))
        bounds=(rect.left,rect.top,rect.right,rect.bottom)
        vx,vy=api.GetSystemMetrics(76),api.GetSystemMetrics(77)
        vw,vh=api.GetSystemMetrics(78),api.GetSystemMetrics(79)
        def move(x,y):
            if injector.escape_pressed() or injector.destination().pid!=info["pid"]:raise RuntimeError("Focus/Escape interrupted fixture. Buttons will be released.")
            mouse.move((x-vx)/(vw-1),(y-vy)/(vh-1));time.sleep(0.05)
        x,y=(rect.left+rect.right)//2,(rect.top+rect.bottom)//2
        move(x,y);mouse.button("left",True);time.sleep(0.06);mouse.button("left",False)
        move(x-100,y);mouse.button("left",True)
        for delta in (20,40,60,80,100):move(x-100+delta,y+20)
        mouse.button("left",False)
        move(x,y+50);mouse.button("right",True);time.sleep(0.06);mouse.button("right",False)
        # Relative touchpad motion reads the current Windows position, avoiding
        # the old camera-to-screen absolute mapping and OS acceleration changes.
        move(x,y);mouse.move_relative(45/(vw-1),-20/(vh-1));time.sleep(.1)
        relative_pos=wintypes.POINT();api.GetCursorPos(ctypes.byref(relative_pos))
        relative_ok=abs(relative_pos.x-(x+45))<=2 and abs(relative_pos.y-(y-20))<=2
        move(x,y);mouse.wheel(vertical=-240);time.sleep(.12);mouse.wheel(horizontal=120);time.sleep(.12)
        # Drag only this fixture's ordinary title bar, away from window buttons.
        move(x,rect.top+15);mouse.button("left",True);time.sleep(0.08)
        move(x+70,rect.top+65);time.sleep(0.12);mouse.button("left",False);time.sleep(0.2)
        new_rect=wintypes.RECT();api.GetWindowRect(info["hwnd"],ctypes.byref(new_rect))
        moved=new_rect.left!=bounds[0] or new_rect.top!=bounds[1]
        child.wait(timeout=12)
        counts=json.loads(RESULT.read_text(encoding="utf-8"))
        success=counts["left_down"]>=2 and counts["left_up"]>=2 and counts["right_down"]==1 and counts["right_up"]==1 and counts["drag_moves"]>0 and moved and relative_ok and counts["vertical_wheel"]>0 and counts["horizontal_wheel"]>0
        counts.update(success=success,relative_touchpad_position=relative_ok,title_bar_window_drag=moved,buttons_released=not mouse.held,ordinary_permissions=not bool(ctypes.windll.shell32.IsUserAnAdmin()))
        RESULT.write_text(json.dumps(counts,indent=2),encoding="utf-8");print(json.dumps(counts,indent=2))
        if not success:raise RuntimeError("Native mouse fixture failed")
    finally:
        mouse.release_all()
        vx,vy=api.GetSystemMetrics(76),api.GetSystemMetrics(77)
        vw,vh=api.GetSystemMetrics(78),api.GetSystemMetrics(79)
        mouse.move((original.x-vx)/(vw-1),(original.y-vy)/(vh-1))
        if child.poll() is None:child.wait(timeout=15)


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--fixture",action="store_true")
    args=parser.parse_args();fixture() if args.fixture else probe()
