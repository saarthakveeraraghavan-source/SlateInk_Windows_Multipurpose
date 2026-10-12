"""Offline repeated single letters -> preview/edit/add -> native test textbox.

Uses synthetic vector ink only, not camera or private handwriting.
"""
import json
import math
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from slateink.privacy import enforce_offline
enforce_offline()
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from slateink.app import MainWindow
from slateink.calibration import Surface
from slateink.state import State
from slateink.config import Config
from native_input_probe import SAMPLE,RESULT,READY

ROOT=Path(__file__).resolve().parent.parent
app=QApplication([])
window=MainWindow(Config(initial_mode="finger_letters")); window.show()
child=None
index=0
surface=Surface.from_corners([(0.1,0.1),(0.9,0.1),(0.9,0.9),(0.1,0.9)])
window.controller.surface=surface
stages={"synthetic_ink":True,"camera_opened":False,"offline":True,"letters":[]}
for path in (RESULT,READY):
    if path.exists():path.unlink()
glyphs=[("A",[[(0.3,0.75),(0.5,0.2),(0.7,0.75)],[(0.38,0.53),(0.62,0.53)]]),
        ("O",[[(0.5+0.23*math.cos(i*2*math.pi/40),0.5+0.3*math.sin(i*2*math.pi/40)) for i in range(41)]])]


def on_result(result):
    if window.state!=State.PREVIEW or window.pending_letter is None:
        raise RuntimeError("Letter did not enter mandatory preview")
    stages["letters"].append({"expected":glyphs[index][0],"model_prediction":result.text,
                              "score_uncalibrated":result.score,"latency_ms":result.latency_seconds*1000})
    stages.update(local_recognition=True,preview=True)
    window.letter_preview.setText(glyphs[index][0].lower())
    stages["edit"]=True


def on_finished():
    global index,child
    if window.pending_letter is None:return
    window.add_letter()
    if window.controller.buffer.count!=0 or window.controller.surface is not surface:
        raise RuntimeError("Adding a letter failed to clear ink or retain calibration")
    index+=1
    if window.preview.toPlainText()!="ao"[:index]:
        raise RuntimeError("Collected text was replaced instead of appended")
    if index<len(glyphs):
        QTimer.singleShot(100,start_letter)
        return
    stages.update(reused_same_ink_area=True,kept_calibration=True,collected_text="ao")
    # Explicit fixture correction exercises arbitrary approved Unicode input.
    window.preview.setPlainText(SAMPLE)
    child=subprocess.Popen([sys.executable,str(ROOT/"scripts/native_input_probe.py"),"--fixture"])
    window.accept()
    stages["explicit_accept_and_countdown"]=window.state==State.TYPING


def start_letter():
    t=0.0
    for stroke in glyphs[index][1]:
        for x,y in stroke:
            window.controller.buffer.add(x,y,t); t+=0.03
        window.controller.buffer.pen_up()
    window.refresh_controls(); window.submit()
    if window.recognition_worker is None:raise RuntimeError("Recognition did not start")
    window.recognition_worker.ready.connect(on_result)
    window.recognition_worker.finished.connect(on_finished)


deadline=time.monotonic()+25
def check():
    if stages.get("explicit_accept_and_countdown") and RESULT.exists():
        fixture=json.loads(RESULT.read_text(encoding="utf-8"))
        if fixture.get("success") and window.send_worker is None and window.state==State.CAMERA_OFF:
            required=("local_recognition","preview","edit","reused_same_ink_area","kept_calibration","explicit_accept_and_countdown")
            if not all(stages.get(name) for name in required):raise RuntimeError("Required stage missing")
            import ctypes
            stages.update(native_external_typing=True,clear_after_send=not window.result_valid,
                          success=True,ordinary_user_permissions=not bool(ctypes.windll.shell32.IsUserAnAdmin()))
            (ROOT/"artifacts/end-to-end-letters.json").write_text(json.dumps(stages,indent=2),encoding="utf-8")
            print(json.dumps(stages,indent=2),flush=True); window.close(); return
    if time.monotonic()>deadline:
        stages.update(success=False,state=window.state.value,error=window.error_label.text())
        (ROOT/"artifacts/end-to-end-letters.json").write_text(json.dumps(stages,indent=2),encoding="utf-8")
        print(json.dumps(stages,indent=2),flush=True); window.emergency_stop(); window.close()


poll=QTimer(); poll.timeout.connect(check); poll.start(50)
QTimer.singleShot(250,start_letter)
app.exec()
if child is not None and child.poll() is None:child.wait(timeout=15)
if not stages.get("success"):sys.exit(1)
