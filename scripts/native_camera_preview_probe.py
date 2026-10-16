"""Synthetic live feed over disposable windows; native drag and pinch minimize."""
from collections import deque
from pathlib import Path
import ctypes,json,sys,threading,time
import faulthandler
from ctypes import wintypes
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QWidget,QLabel,QVBoxLayout
from slateink.app import MainWindow
from slateink.config import Config,ROOT
from slateink.camera import Packet
from slateink.window_switching import WindowsWindowBackend
from native_click_gesture_probe import hand


def main():
    faulthandler.dump_traceback_later(8)
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    backend=WindowsWindowBackend(excluded_pid=0);api=backend.api;original=backend.foreground()
    api.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    api.SendMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM];api.SendMessageW.restype=ctypes.c_ssize_t
    api.GetCursorPos.argtypes=[ctypes.POINTER(wintypes.POINT)]
    original_cursor=wintypes.POINT();api.GetCursorPos(ctypes.byref(original_cursor))
    w=MainWindow(Config(initial_mode="hand_mouse",camera_preview_enabled=True));w.timer.stop();w.performance_timer.stop();w.move(70,40)
    class Worker:
        def __init__(self):self.stop_event=threading.Event();self.source=type("Source",(),{"times":deque(maxlen=90)})();self.hand=hand(mirrored=True);self.sequence=0
        def stop(self):
            if not self.stop_event.is_set():self.stop_event.set();QTimer.singleShot(10,w.camera_finished)
        def deleteLater(self):pass
        def take(self):
            if self.stop_event.is_set():return None
            now=time.monotonic();self.sequence+=1;self.source.times.append(now)
            rgb=np.zeros((240,320,3),np.uint8);rgb[:]=(24,55,74)
            rgb[:,::40]=(55,118,134);rgb[::40,:]=(55,118,134)
            x=(self.sequence*4)%290;rgb[75:120,x:x+25]=(78,224,196)
            return Packet(rgb,self.hand,1,now,30,30,1,0,hands=(self.hand,))
    source=Worker();w.worker=source;w.camera_started_at=time.monotonic();w.last_packet_time=w.camera_started_at
    w.camera_stats_logged=True;w.touchpad_session.set_enabled(True);w.show();w.refresh_controls()
    target=QWidget();target.setWindowTitle("Floating preview focus verification")
    layout=QVBoxLayout(target);layout.addWidget(QLabel("Disposable target. Floating camera must remain above this window without taking focus."))
    target.resize(760,400);target.move(220,180);target.show()
    preview=w.camera_preview;preview.move(340,220)
    mouse=w.mouse_sink
    report={"success":False,"real_camera_opened":False,"synthetic_frames":True}
    stage=0;due=time.monotonic()+.5;started=time.monotonic();before=None;image_key=None
    def focus(handle):
        try:backend._alt(True);time.sleep(.02);api.SetForegroundWindow(handle)
        finally:backend.release_all()
    def move(x,y):
        vx,vy=api.GetSystemMetrics(76),api.GetSystemMetrics(77)
        mouse.move((x-vx)/(api.GetSystemMetrics(78)-1),(y-vy)/(api.GetSystemMetrics(79)-1))
    def step():
        nonlocal stage,due,before,image_key
        now=time.monotonic()
        if now-started>10:raise RuntimeError("Native preview fixture timed out")
        w.tick()
        if now<due:return
        if stage==0:
            if backend.input_busy():return
            focus(int(target.winId()));stage=1;due=now+.2
        elif stage==1:
            report["preview_nonactivating"]=backend.foreground()==int(target.winId())
            style=api.GetWindowLongPtrW(int(preview.winId()),-20)
            report["native_topmost"]=bool(style&0x8)
            before=preview.pos();rect=wintypes.RECT();api.GetWindowRect(int(preview.winId()),ctypes.byref(rect))
            move(rect.left+(rect.right-rect.left)//2,rect.top+round(14*preview.devicePixelRatioF()))
            mouse.button("left",True);stage=2;due=now+.12
        elif stage==2:
            report["header_received_press"]=preview.bar.anchor is not None
            p=wintypes.POINT();api.GetCursorPos(ctypes.byref(p));move(p.x+80,p.y+45);stage=3;due=now+.15
        elif stage==3:
            mouse.button("left",False);stage=4;due=now+.15
        elif stage==4:
            report["drag_before"]=[before.x(),before.y()];report["drag_after"]=[preview.x(),preview.y()]
            report["native_header_drag"]=preview.pos()!=before and (w.config.camera_preview_x,w.config.camera_preview_y)==(preview.x(),preview.y())
            report["drag_kept_target_focus"]=backend.foreground()==int(target.winId())
            focus(int(w.winId()));rect=wintypes.RECT();api.GetWindowRect(int(w.winId()),ctypes.byref(rect));point=None
            for y in range(rect.top+8,rect.top+33,4):
                for x in range(rect.right-150,rect.right-40,4):
                    packed=(x&0xffff)|((y&0xffff)<<16)
                    if api.SendMessageW(int(w.winId()),0x0084,0,packed)==8:point=x,y;break
                if point:break
            if point is None:raise RuntimeError("Actual native Minimize button not found")
            move(*point);source.hand=hand("left",mirrored=True);stage=5;due=now+.2
        elif stage==5:
            source.hand=hand(mirrored=True);stage=6;due=now+.2
        elif stage==6:
            report["pinch_minimized"]=w.isMinimized()
            report["tracking_kept_running"]=w.hand_mouse.enabled and not source.stop_event.is_set()
            report["preview_visible_when_minimized"]=preview.isVisible()
            image_key=preview.view.image.cacheKey();stage=7;due=now+.2
        elif stage==7:
            report["live_updates_when_minimized"]=preview.view.image.cacheKey()!=image_key
            preview.grab().save(str(ROOT/"artifacts/floating-camera-native.png"))
            report["success"]=all(report[k] for k in ("preview_nonactivating","native_topmost","native_header_drag","drag_kept_target_focus","pinch_minimized","tracking_kept_running","preview_visible_when_minimized","live_updates_when_minimized"))
            stage=8;timer.stop();app.exit(0)
    def guarded():
        try:step()
        except Exception as error:report["error"]=str(error);timer.stop();app.exit(1)
    timer=QTimer();timer.timeout.connect(guarded);timer.start(20)
    try:app.exec()
    finally:
        faulthandler.cancel_dump_traceback_later()
        timer.stop()
        w.stop_pointer();mouse.release_all();w.worker=None;w.close();target.close()
        if original and api.IsWindow(original) and not backend.input_busy():focus(original)
        move(original_cursor.x,original_cursor.y)
        report["owned_input_released"]=not mouse.held
        ROOT.joinpath("artifacts/native-camera-preview.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report,indent=2))
    return 0 if report["success"] else 1


if __name__=="__main__":raise SystemExit(main())
