"""Verify native focus changes only among disposable windows in our child.

No camera, microphone, text injection or existing-document edits. A restricted
backend keeps every cycle inside the fixture; restore initial focus on exit.
"""
from pathlib import Path
import ctypes
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def fixture():
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
    app = QApplication([])
    windows = []
    for i, name in enumerate(("Swipe validation A", "Swipe validation B", "Swipe validation C")):
        window = QWidget()
        window.setWindowTitle(name)
        layout = QVBoxLayout(window)
        layout.addWidget(QLabel("Disposable swipe test window — closes automatically."))
        window.resize(430, 110);window.move(140+i*70, 140+i*100);window.show()
        windows.append(window)
    tool = QWidget(None, Qt.WindowType.Tool);tool.setWindowTitle("Swipe validation tool");tool.show()
    hidden = QWidget();hidden.setWindowTitle("Swipe validation hidden")
    disabled = QWidget();disabled.setWindowTitle("Swipe validation disabled");disabled.setEnabled(False);disabled.show()
    from ctypes import wintypes
    native=ctypes.WinDLL("user32");native.EnableWindow.argtypes=[wintypes.HWND,wintypes.BOOL]
    native.EnableWindow(int(disabled.winId()),False)
    slate = QWidget();slate.setWindowTitle("SlateInk excluded fixture");slate.show()
    def ready():
        print(json.dumps({"pid":os.getpid(),"windows":[int(w.winId()) for w in windows],
                          "excluded":[int(w.winId()) for w in (tool,hidden,disabled,slate)]}),flush=True)
    QTimer.singleShot(200,ready)
    QTimer.singleShot(20000,app.quit)
    app.exec()


def probe():
    from slateink.window_switching import WindowsWindowBackend, WindowCycle
    from slateink.touchpad_session import TouchpadSession
    from slateink.mouse_control import HandMouseController
    from slateink.config import Config
    from types import SimpleNamespace
    backend = WindowsWindowBackend()
    original = backend.foreground()
    env = dict(os.environ);env.pop("QT_QPA_PLATFORM",None)
    child = subprocess.Popen([sys.executable,str(Path(__file__).resolve()),"--fixture"],
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    report = {"success":False,"physical_hand_tested":False,"camera_opened":False}
    handles = set()
    info = {}
    try:
        info = json.loads(child.stdout.readline())
        handles = set(info["windows"])
        report["ordinary_permissions"] = not bool(ctypes.windll.shell32.IsUserAnAdmin())
        report["eligible_fixture_windows"] = len(handles.intersection(backend.windows()))
        report["unsuitable_windows_excluded"] = all(not backend.eligible(w) for w in info["excluded"])
        own_filter = WindowsWindowBackend(excluded_pid=info["pid"])
        report["own_process_excluded"] = not handles.intersection(own_filter.windows())
        # The approval click itself can still be down when the helper starts.
        # Wait for an idle physical keyboard/mouse before touching the fixture.
        idle_deadline=time.monotonic()+3
        while backend.input_busy() and time.monotonic()<idle_deadline:time.sleep(.05)
        class Restricted:
            def input_busy(self):return backend.input_busy()
            def windows(self):return [w for w in backend.windows() if w in handles]
            def foreground(self):return backend.foreground()
            def activate(self,w):
                if w not in handles:raise RuntimeError("Target outside disposable fixture")
                backend.activate(w)
        cycle = WindowCycle(Restricted())
        initial = cycle.backend.windows()
        assert len(initial)==3, "Fixture enumeration failed"
        backend.activate(initial[0]);time.sleep(.1)
        observations=[]
        for direction in (1,1,1,1,1,1,-1,-1,-1):
            assert backend.foreground() in handles, "Focus left fixture; no further test input"
            cycle.switch(direction);time.sleep(.1)
            observations.append(backend.foreground())
        order=cycle.order
        expected=[order[1],order[2],order[0],order[1],order[2],order[0],order[2],order[1],order[0]]
        report["stable_forward_and_reverse_cycle"] = observations==expected
        backend.api.ShowWindowAsync(order[1],6);time.sleep(.15)
        assert backend.api.IsIconic(order[1]), "Fixture did not minimize"
        cycle.switch(1);time.sleep(.15)
        report["minimized_window_restored"] = backend.foreground()==order[1] and not backend.api.IsIconic(order[1])
        # With --references, replay actual locally supplied hand observations.
        # Otherwise use portable generic open-palm samples, without personal data.
        fixture_name="right_hand_swipe_reference_landmarks.json" if "--references" in sys.argv else "open_palm_swipe_synthetic.json"
        clips=json.loads(ROOT.joinpath("tests/fixtures",fixture_name).read_text())
        report["reference_swipe_results"]=[]
        class Mouse:
            def __init__(self):self.events=[];self.held=set()
            def release_all(self):self.held.clear()
            def button(self,*args):self.events.append(args)
            def move_relative(self,*args):self.events.append(("pointer",*args))
            def wheel(self,**args):self.events.append(("scroll",args))
        class Switcher:
            def __init__(self):self.events=[]
            def release_all(self):backend.release_all()
            def switch(self,direction):self.events.append(direction);return cycle.switch(direction)
        for clip in clips:
            cfg=Config(camera_mirrored=clip["mirrored"],wispr_enabled=True)
            mouse=Mouse();switcher=Switcher()
            session=TouchpadSession(HandMouseController(cfg,mouse),None,window_switcher=switcher)
            session.set_enabled(True);before=backend.foreground()
            for row in clip["rows"]:
                assert backend.foreground() in handles, "Focus left fixture"
                hands=tuple(SimpleNamespace(landmarks=tuple(h["landmarks"]),ratio=h["ratio"],label=h["label"],handedness_confidence=h["confidence"]) for h in row["hands"])
                session.process(hands,row["t"]+1,aspect=clip["aspect"])
            expected=[clip["expected_direction"]]
            report["reference_swipe_results"].append({"name":clip.get("name",clip.get("video")),"mirrored":clip["mirrored"],"fixture_kind":clip["fixture_kind"],"events":switcher.events,"unwanted_mouse_events":mouse.events,"success":switcher.events==expected and not mouse.events and backend.foreground()!=before})
        report["reference_swipes_changed_native_focus_once_each"]=all(r["success"] for r in report["reference_swipe_results"])
        report["alt_released"] = not backend.alt_owned and not backend.api.GetAsyncKeyState(0x12)&0x8000
        report["success"] = all(report[k] for k in ("ordinary_permissions","unsuitable_windows_excluded","own_process_excluded","stable_forward_and_reverse_cycle","minimized_window_restored","reference_swipes_changed_native_focus_once_each","alt_released")) and report["eligible_fixture_windows"]==3
    except Exception as exc:
        report["error"] = type(exc).__name__+": "+str(exc)
    finally:
        backend.release_all()
        if handles and backend.foreground() in handles and original and backend.api.IsWindow(original) and not backend.input_busy():
            try:
                backend._alt(True);time.sleep(.02);backend.api.SetForegroundWindow(original)
            finally:backend.release_all()
        # The Windows venv launcher can have a distinct PID from the actual
        # runtime. Close the verified child's windows rather than leaving an
        # orphan runtime behind by terminating only its launcher.
        from ctypes import wintypes
        backend.api.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
        backend.api.PostMessageW.restype=wintypes.BOOL
        fixture_handles=list(handles)+info.get("excluded",[])
        for window in fixture_handles:
            pid=wintypes.DWORD()
            backend.api.GetWindowThreadProcessId(window,ctypes.byref(pid))
            if pid.value==info.get("pid"):
                backend.api.PostMessageW(window,0x10,0,0) # WM_CLOSE, only our fixture
        try:child.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            child.terminate();child.communicate(timeout=3)
        report["fixture_windows_closed"] = all(not backend.api.IsWindow(w) for w in fixture_handles)
        report["success"] = report["success"] and report["fixture_windows_closed"]
        ROOT.joinpath("artifacts/native-window-swipe.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report,indent=2))
    return 0 if report["success"] else 1


if __name__=="__main__":
    if "--fixture" in sys.argv:fixture()
    else:raise SystemExit(probe())
