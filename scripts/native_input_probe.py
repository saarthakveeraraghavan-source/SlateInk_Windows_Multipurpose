"""Real Windows input into a dedicated, disposable external Qt textbox only."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from slateink.privacy import enforce_offline
enforce_offline()
from slateink.injection import WindowsInjector, InjectionError

SAMPLE = "Aa hello, world! ₹42 café 😀"
ROOT = Path(__file__).resolve().parent.parent
RESULT = ROOT / "artifacts" / "native-input.json"
READY = ROOT / "artifacts" / "native-fixture-ready.json"


def fixture():
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMainWindow, QPlainTextEdit
    app=QApplication([])
    window=QMainWindow()
    window.setWindowTitle("SlateInk input validation — disposable test textbox")
    window.resize(700,240)
    editor=QPlainTextEdit()
    editor.setPlaceholderText("Dedicated test fixture. No personal document is open.")
    window.setCentralWidget(editor)
    window.show()
    READY.write_text(json.dumps({"pid":os.getpid()}),encoding="utf-8")
    editor.setFocus()
    window.activateWindow()
    window.raise_()
    def activate_fixture():
        # Standard foreground request for this test's own window; no attach-input,
        # fake Alt press, foreground-lock changes, or security bypass.
        import ctypes
        api=ctypes.WinDLL("user32")
        from ctypes import wintypes
        api.SetForegroundWindow.argtypes=[wintypes.HWND]
        api.SetForegroundWindow.restype=wintypes.BOOL
        api.SetForegroundWindow(int(window.winId()))
        editor.setFocus()
    QTimer.singleShot(500,activate_fixture)
    def check():
        actual=editor.toPlainText()
        if len(actual)>=len(SAMPLE):
            RESULT.write_text(json.dumps({"success":actual==SAMPLE,"characters":len(SAMPLE),
                "method":"native Windows Unicode SendInput","external_process":True,
                "fixture_only_differences":[{"position":i,"expected_codepoint":ord(a),"observed_codepoint":ord(b)}
                    for i,(a,b) in enumerate(zip(SAMPLE,actual)) if a!=b]},indent=2),encoding="utf-8")
            app.quit()
    timer=QTimer()
    timer.timeout.connect(check)
    timer.start(50)
    def timeout():
        actual=editor.toPlainText()
        matched_prefix=0
        for expected,observed in zip(SAMPLE,actual):
            if expected!=observed: break
            matched_prefix+=1
        RESULT.write_text(json.dumps({"success":False,"received_characters":len(actual),
            "expected_characters":len(SAMPLE),"matching_prefix":matched_prefix,
            "is_full_sample_prefix":SAMPLE.startswith(actual),
            "reason":"Fixture timeout or mismatched text; private text not saved"},indent=2),encoding="utf-8")
        app.quit()
    QTimer.singleShot(12000,timeout)
    app.exec()


def probe():
    if RESULT.exists():
        RESULT.unlink()
    if READY.exists():
        READY.unlink()
    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),"--fixture"])
    injector=WindowsInjector()
    target=None
    observed_pids=set()
    previous=None
    stable_since=None
    deadline=time.monotonic()+8
    try:
        while time.monotonic()<deadline:
            try:
                current=injector.destination()
                observed_pids.add(current.pid)
                fixture_pid=json.loads(READY.read_text(encoding="utf-8"))["pid"] if READY.exists() else None
                if current.pid==fixture_pid:
                    if current!=previous:
                        previous,stable_since=current,time.monotonic()
                    elif time.monotonic()-stable_since>0.8:
                        target=current
                        break
            except InjectionError:
                pass
            time.sleep(0.05)
        if target is None:
            print("Fixture PID:",child.pid,"Observed foreground PIDs:",sorted(observed_pids))
            raise RuntimeError("Disposable fixture did not obtain stable focus. No input sent.")
        injector.send(SAMPLE,target)
        child.wait(timeout=15)
        result=json.loads(RESULT.read_text(encoding="utf-8"))
        print(json.dumps(result,indent=2))
        if not result["success"]:
            raise RuntimeError("Native input mismatch")
    finally:
        if child.poll() is None:
            child.wait(timeout=15)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--fixture",action="store_true")
    parser.add_argument("--paper",action="store_true")
    args=parser.parse_args()
    if args.paper:SAMPLE="Hello world Differentiate velocity"
    fixture() if args.fixture else probe()
