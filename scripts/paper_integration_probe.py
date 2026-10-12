"""Synthetic paper snapshot -> local OCR -> review -> native external textbox."""
import json,time,threading,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from slateink.privacy import enforce_offline
enforce_offline()
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from slateink.app import MainWindow
from slateink.calibration import Surface
from slateink.state import State
from native_input_probe import RESULT,READY
ROOT=Path(__file__).resolve().parent.parent
EXPECTED="Hello world Differentiate velocity"
app=QApplication([]);window=MainWindow();window.show()
stages={"synthetic_paper":True,"camera_opened":False,"offline":True};child=None
for path in (RESULT,READY):
    if path.exists():path.unlink()
class SyntheticCamera:
    stop_event=threading.Event()
    def stop(self):self.stop_event.set();QTimer.singleShot(10,window.camera_finished)
    def take(self):return None
    def deleteLater(self):pass
window.worker=SyntheticCamera()
window.controller.surface=Surface.from_corners([(0,0),(1,0),(1,1),(0,1)])
image=Image.new("RGB",(1000,250),"white");font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf",55)
draw=ImageDraw.Draw(image);draw.text((40,20),"Hello world",font=font,fill="black");draw.text((40,130),"Differentiate velocity",font=font,fill="black")
# Mirror the camera fixture so the actual OCR path must undo that orientation.
window.latest_rgb=np.array(image)[:,::-1].copy()
window.refresh_controls()
def result_ready(result):
    if result.text!=EXPECTED or window.state!=State.PREVIEW:raise RuntimeError("Paper OCR fixture mismatch")
    stages.update(local_paper_ocr=True,unmirrored_ink=True,multiple_lines=True,preview=True,
                  recognition_seconds=result.latency_seconds,score_uncalibrated=result.score)
    stages["actual_ocr_device"]=result.device
def finished():
    global child
    if not stages.get("preview"):return
    child=subprocess.Popen([sys.executable,str(ROOT/"scripts/native_input_probe.py"),"--fixture","--paper"])
    window.accept();stages["explicit_accept"]=window.state==State.TYPING
def start():
    window.latest_frame_at=time.monotonic();window.submit()
    if window.recognition_worker is None:raise RuntimeError("Paper capture did not start")
    window.recognition_worker.ready.connect(result_ready);window.recognition_worker.finished.connect(finished)
deadline=time.monotonic()+90 # First CUDA model initialization is measured separately.
def check():
    if stages.get("explicit_accept") and RESULT.exists():
        output=json.loads(RESULT.read_text(encoding="utf-8"))
        if output.get("success") and window.send_worker is None and window.state==State.CAMERA_OFF:
            stages.update(native_external_typing=True,success=True)
            (ROOT/"artifacts/paper-integration.json").write_text(json.dumps(stages,indent=2),encoding="utf-8")
            print(json.dumps(stages,indent=2),flush=True);window.close();return
    if time.monotonic()>deadline:
        print("Paper integration timeout:",window.error_label.text(),flush=True);window.close()
poll=QTimer();poll.timeout.connect(check);poll.start(50);QTimer.singleShot(250,start)
app.exec()
if child is not None and child.poll() is None:child.wait(timeout=15)
if not stages.get("success"):sys.exit(1)
