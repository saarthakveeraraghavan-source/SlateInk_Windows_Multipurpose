"""Actual word selection and keyboard paths in a fixed disposable Qt window.

Wispr keys are remapped to fixture-only F8/F9 so no microphone is opened.
"""
from pathlib import Path
import sys,time,json,ctypes,os
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from slateink.privacy import enforce_offline
enforce_offline()
from ctypes import wintypes
from PySide6.QtCore import QTimer,Qt
from PySide6.QtGui import QTextCursor,QFont
from PySide6.QtWidgets import QApplication,QMainWindow,QPlainTextEdit
from slateink.config import ROOT
from slateink.mouse_control import WindowsMouse
from slateink.desktop_shortcuts import WindowsWisprShortcut
from slateink.desktop_hotkey import DesktopHotkey
from slateink.injection import WindowsInjector

app=QApplication([]);window=QMainWindow();window.setWindowTitle("SlateInk disposable selection and shortcut validation")
counts={"fixture_shortcuts":0,"global_hotkey":0};success=False
class Text(QPlainTextEdit):
    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_F8 and event.modifiers()&Qt.KeyboardModifier.ControlModifier:
            counts["fixture_shortcuts"]+=1;event.accept();return
        super().keyPressEvent(event)
text=Text("alpha beta gamma");text.setFont(QFont("Consolas",20));window.setCentralWidget(text)
window.resize(720,300);window.move(250,220);window.show();text.setFocus();window.activateWindow()
injector=WindowsInjector();mouse=WindowsMouse();api=injector.api
api.GetCursorPos.argtypes=[ctypes.POINTER(wintypes.POINT)];api.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
original=wintypes.POINT();api.GetCursorPos(ctypes.byref(original))
hotkey=DesktopHotkey();hotkey.activated.connect(lambda:counts.update(global_hotkey=counts["global_hotkey"]+1))
class FixtureShortcuts(WindowsWisprShortcut):
    def key(self,vk,down):super().key({0x5B:0x77,0x1B:0x78}.get(vk,vk),down)
    def flow_running(self):return True
keys=FixtureShortcuts();keys.injector.destination=lambda:injector.destination(allow_own=True)
stage="focus";started=time.monotonic();due=0;stable_since=None
def focused():return injector.destination(allow_own=True).pid==os.getpid()
def move_word():
    cursor=QTextCursor(text.document());cursor.setPosition(8)
    r=text.cursorRect(cursor);ratio=window.devicePixelRatioF()
    p=wintypes.POINT(round(r.center().x()*ratio),round(r.center().y()*ratio))
    api.ClientToScreen(int(text.viewport().winId()),ctypes.byref(p))
    vx,vy=api.GetSystemMetrics(76),api.GetSystemMetrics(77);vw,vh=api.GetSystemMetrics(78),api.GetSystemMetrics(79)
    mouse.move((p.x-vx)/(vw-1),(p.y-vy)/(vh-1))
def step():
    global stage,due,stable_since,success
    now=time.monotonic()
    if now-started>10:raise RuntimeError("Fixture timed out")
    if stage=="focus":
        if focused():
            if stable_since is None:stable_since=now
            if now-stable_since>.6:move_word();stage="click1";due=now+.1
        else:stable_since=None
        return
    if not focused():raise RuntimeError("Fixture lost focus; no further input")
    if now<due:return
    if stage=="click1":mouse.button("left",True);mouse.button("left",False);stage="click2";due=now+.14
    elif stage=="click2":mouse.button("left",True);mouse.button("left",False);stage="check_selection";due=now+.15
    elif stage=="check_selection":
        counts["word_selected"]=text.textCursor().selectedText()=="beta"
        keys.begin("toggle_ctrl_win");stage="finish_shortcut";due=now+.25
    elif stage=="finish_shortcut":keys.finish();stage="hotkey";due=now+.15
    elif stage=="hotkey":
        for vk in (0xA2,0xA4,0x4D):keys.key(vk,True)
        keys.release_owned();stage="result";due=now+.25
    elif stage=="result":
        counts.update(no_microphone_opened=True,actual_wispr_shortcut_tested=False,keys_released=not keys.owned,ordinary_permissions=not bool(ctypes.windll.shell32.IsUserAnAdmin()))
        success=counts["word_selected"] and counts["fixture_shortcuts"]==2 and counts["global_hotkey"]==1 and not keys.owned
        counts["success"]=success
        ROOT.joinpath("artifacts/native-touchpad-selection.json").write_text(json.dumps(counts,indent=2),encoding="utf-8")
        print(json.dumps(counts,indent=2),flush=True);window.close()
def guarded():
    try:step()
    except Exception as exc:print(type(exc).__name__+": "+str(exc),flush=True);window.close()
timer=QTimer();timer.timeout.connect(guarded);timer.start(20)
try:app.exec()
finally:
    keys.cancel();mouse.release_all();hotkey.close()
    vx,vy=api.GetSystemMetrics(76),api.GetSystemMetrics(77);vw,vh=api.GetSystemMetrics(78),api.GetSystemMetrics(79)
    mouse.move((original.x-vx)/(vw-1),(original.y-vy)/(vh-1))
if not success:raise SystemExit(1)
