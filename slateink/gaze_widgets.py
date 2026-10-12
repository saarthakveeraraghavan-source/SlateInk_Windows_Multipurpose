"""Visible, memory-only calibration with explicit results and selective retries."""
from collections import deque
import time
import numpy as np
from PySide6.QtCore import Qt,Signal,QTimer,QPointF,QRectF
from PySide6.QtGui import QPainter,QColor,QPen,QImage,QPixmap
from PySide6.QtWidgets import QDialog,QApplication,QLabel,QPushButton,QCheckBox
from .gaze import GazeCalibration

TRAIN=[(x,y) for y in (.1,.5,.9) for x in (.1,.5,.9)]
CHECK=[(.25,.25),(.75,.3),(.35,.7),(.7,.75),(.5,.6)]


class GazeCalibrationDialog(QDialog):
    completed=Signal(object)
    unverified_requested=Signal(object)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle("SlateInk eye calibration — desktop controls off")
        self.setWindowFlags(Qt.WindowType.Window|Qt.WindowType.FramelessWindowHint)
        self.calibration=GazeCalibration();self.samples=deque(maxlen=90)
        self.index=0;self.checks={};self.validation_order=list(range(5))
        self.phase="setup";self.changed_at=time.monotonic();self.last_seen=None
        self.eye_reason="Waiting for the camera. Both eyes must be clearly visible."
        self.report=None;self.progress=0;self.capture_notice=""
        self.heading=QLabel(self);self.instructions=QLabel(self);self.status=QLabel(self)
        for label in (self.heading,self.instructions,self.status):
            label.setWordWrap(True);label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("background:transparent;color:#e7f4ff;font-size:18px;")
        self.heading.setStyleSheet("background:transparent;color:#e7f4ff;font-size:24px;font-weight:600;")
        self.preview=QLabel("Camera preview stays on this computer",self)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background:#1e3144;color:#b4c7d6;")
        self.auto=QCheckBox("Advance dots automatically",self);self.auto.setChecked(True)
        self.auto.setStyleSheet("background:transparent;color:#e7f4ff;font-size:16px;")
        self.start_button=QPushButton("Start calibration",self);self.start_button.clicked.connect(self.start_calibration)
        self.start_button.setEnabled(False)
        self.retry_button=QPushButton("Retry failed dots only",self);self.retry_button.clicked.connect(self.retry_failed)
        self.restart_button=QPushButton("Start over",self);self.restart_button.clicked.connect(self.restart)
        self.return_button=QPushButton("Return to app",self);self.return_button.clicked.connect(self.return_to_app)
        self.use_button=QPushButton("Continue without accuracy check",self);self.use_button.clicked.connect(self.use_unverified)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        for control in (self.start_button,self.retry_button,self.restart_button,self.return_button,self.use_button,self.auto):control.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(33)
        self.setGeometry(QApplication.primaryScreen().geometry());self._update_ui()

    @property
    def target(self):
        if self.phase=="calibrate":return TRAIN[self.index]
        if self.phase=="validate":return CHECK[self.validation_order[self.index]]
        return (.5,.5)

    def observe(self,observation,t,rgb=None,face_count=None):
        if self.phase=="done" or (self.last_seen is not None and t<=self.last_seen):return
        self.last_seen=t
        if face_count is not None and face_count>1:self.eye_reason="More than one face is visible. Keep only your face in view."
        elif observation is None:self.eye_reason="Face/eyes not detected. Face the camera, move closer and improve front lighting."
        elif not observation.valid:self.eye_reason=observation.reason or "Both eyes must be open and clearly visible."
        else:self.eye_reason="Both eyes detected. Keep your head still."
        if t-self.changed_at>=.4:self.samples.append((t,observation))
        if self.phase=="setup" and rgb is not None:
            h,w=rgb.shape[:2]
            image=QImage(rgb.data,w,h,rgb.strides[0],QImage.Format.Format_RGB888).copy()
            self.preview.setPixmap(QPixmap.fromImage(image).scaled(self.preview.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))

    def _ready_samples(self):
        now=time.monotonic()
        if self.last_seen is None or now-self.last_seen>.2:
            return [],0,"Camera samples stopped. Return to the app and restart the camera."
        recent=[(t,o) for t,o in self.samples if 0<=now-t<=1.6]
        valid=[(t,o) for t,o in recent if o is not None and o.valid]
        if not recent or recent[-1][1] is None or not recent[-1][1].valid:return [],0,self.eye_reason
        span=valid[-1][0]-valid[0][0] if len(valid)>1 else 0
        progress=min(1,len(valid)/12,span/.9)
        if len(valid)<12 or span<.9:return [],progress,"Collecting eye samples — keep looking at the dot."
        if len(valid)/len(recent)<.75:return [],progress,self.eye_reason+" Tracking is dropping out; improve lighting or move closer."
        features=np.asarray([o.features for _,o in valid],float)
        if features.shape!=(len(valid),4) or not np.isfinite(features).all():return [],0,"Eye measurements are unclear. Keep both eyes visible."
        if np.max(np.std(features,axis=0))>.05:return [],progress,"Eyes are being measured unstably. Keep your head still and look at the dot."
        return recent,1,"Ready."

    def start_calibration(self):
        if self.phase!="setup":return
        ready,_,reason=self._ready_samples()
        if not ready:self.capture_notice=reason;return
        self.phase="calibrate";self.index=0;self.samples.clear();self.progress=0;self.changed_at=time.monotonic()
        self.preview.clear();self.capture_notice="";self._update_ui()

    def capture(self):
        if self.phase not in {"calibrate","validate"}:return
        recent,_,reason=self._ready_samples()
        if not recent:
            self.capture_notice=reason;return
        try:
            if self.phase=="calibrate":
                self.calibration.add([o for _,o in recent],self.target);self.index+=1
                if self.index==len(TRAIN):
                    self.calibration.fit();self.phase="validate";self.index=0
            else:
                original=self.validation_order[self.index]
                self.checks[original]=(recent,self.target);self.index+=1
                if self.index==len(self.validation_order):
                    ratio=QApplication.primaryScreen().devicePixelRatio()
                    self.report=self.calibration.validate([self.checks[i] for i in range(5)],self.width()*ratio,self.height()*ratio)
                    self.finish_result()
            self.samples.clear();self.progress=0;self.changed_at=time.monotonic();self.capture_notice=""
        except ValueError as exc:
            self.calibration.validated=False
            self.report={"passed":False,"reason":str(exc),"retry_indices":[],"checks":[]}
            self.calibration.report=self.report;self.finish_result()
        self._update_ui()

    def finish_result(self):
        self.phase="done";self.samples.clear();self.progress=0
        self.completed.emit(self.calibration)

    def retry_failed(self):
        if self.phase!="done" or self.calibration.weights is None or not self.report or not self.report.get("retry_indices"):return
        self.validation_order=list(self.report["retry_indices"]);self.index=0;self.phase="validate"
        self.calibration.validated=False;self.calibration.report=None;self.report=None
        self.samples.clear();self.progress=0;self.changed_at=time.monotonic();self.capture_notice="";self._update_ui()

    def restart(self):
        self.calibration=GazeCalibration();self.report=None;self.samples.clear();self.checks.clear()
        self.validation_order=list(range(5));self.index=0;self.phase="setup"
        self.changed_at=time.monotonic();self.progress=0;self.capture_notice="";self._update_ui()

    def return_to_app(self):
        self.accept() if self.phase=="done" else self.reject()

    def use_unverified(self):
        if self.calibration.weights is None or self.phase not in {"validate","done"}:return
        if self.report is None:
            self.report={"passed":False,"reason":"Accuracy check skipped at your request.","checks":[],"retry_indices":[]}
            self.calibration.report=self.report
        self.unverified_requested.emit(self.calibration)
        self.accept()

    def keyPressEvent(self,event):
        if event.isAutoRepeat():return
        if event.key()==Qt.Key.Key_Escape:self.reject();return
        if event.key() in {Qt.Key.Key_Return,Qt.Key.Key_Enter} and self.phase=="done":self.accept();return
        if event.key()==Qt.Key.Key_R and self.phase=="done":self.retry_failed();return
        if event.key()==Qt.Key.Key_U:self.use_unverified();return
        if event.key()==Qt.Key.Key_Space:
            self.start_calibration() if self.phase=="setup" else self.capture()

    def poll(self):
        if self.phase!="done":
            recent,self.progress,reason=self._ready_samples()
            self.start_button.setEnabled(self.phase=="setup" and bool(recent))
            self.status.setText(reason+"\nDesktop controls are off. Nothing is saved.")
            if self.auto.isChecked() and recent and self.phase in {"calibrate","validate"}:self.capture()
        self.update()

    def _update_ui(self):
        setup=self.phase=="setup";done=self.phase=="done"
        self.preview.setVisible(setup);self.start_button.setVisible(setup)
        self.auto.setVisible(not done and not setup)
        self.retry_button.setVisible(done and bool(self.report and self.report.get("retry_indices")))
        self.restart_button.setVisible(done and not self.report.get("passed",False))
        self.use_button.setVisible(self.calibration.weights is not None and (self.phase=="validate" or (done and not self.report["passed"])))
        if setup:
            self.heading.setText("Position your face")
            self.instructions.setText("Keep both eyes clearly visible in the preview. Face the camera in good light, then click Start calibration.")
            self.status.setText("Waiting for fresh eye samples. Desktop controls are off. Nothing is saved.")
        elif not done:
            number=self.index+1 if self.phase=="calibrate" else self.validation_order[self.index]+1
            self.heading.setText(f"{'Calibration' if self.phase=='calibrate' else 'Accuracy check'} · dot {number} of {9 if self.phase=='calibrate' else 5}")
            self.instructions.setText("Look at the center of the dot and keep your head still. The ring fills when samples are ready. Space also captures when ready.")
            self.status.setText("Keep looking at the dot while the ring fills.\nDesktop controls are off. Nothing is saved.")
        else:
            passed=self.report["passed"]
            self.heading.setText("Accuracy check passed" if passed else "Calibration finished — accuracy unverified")
            self.instructions.setText("Return to the app to explicitly enable control." if passed else "Retry failed dots (R), or Continue without accuracy check (U) to allow desktop control. Pointing may be inaccurate.")
            lines=[self.report.get("reason","")]
            if self.report.get("median_error_px") is not None:
                lines.append(f"Median error {self.report['median_error_px']:.0f}px · 90th percentile {self.report['p90_error_px']:.0f}px")
            for check in self.report.get("checks",[]):
                if not check["passed"]:lines.append(f"Dot {check['index']+1}: {check['reason']} ({check['usable_samples']}/{check['total_samples']} usable samples)")
            if not passed and self.report.get("retry_indices") and all(c["passed"] for c in self.report.get("checks",[])):
                lines.append("Overall pointing error was too large. Retry the least accurate dots.")
            self.status.setText("\n".join(lines)+"\nDesktop controls are off. No images or eye measurements were saved.")
        self._layout_controls()

    def _layout_controls(self):
        w,h=self.width(),self.height()
        self.heading.setGeometry(60,15,w-120,55);self.instructions.setGeometry(60,70,w-120,85)
        self.preview.setGeometry((w-420)//2,170,420,min(280,max(150,h-400)))
        self.status.setGeometry(60,170 if self.phase=="done" else h-180,w-120,h-270 if self.phase=="done" else 110)
        self.start_button.setGeometry(30,h-58,190,38);self.retry_button.setGeometry(30,h-58,225,38)
        self.restart_button.setGeometry(270,h-58,155,38);self.return_button.setGeometry(w-220,h-58,190,38)
        self.auto.setGeometry(30,h-58,330,38)
        self.use_button.setGeometry(450 if self.phase=="done" else 380,h-58,320,38)
        # Keep instructions out of the target rows instead of painting text over
        # the top/bottom dots. The validation targets use different empty bands.
        if self.phase=="calibrate":
            self.heading.setGeometry(60,round(h*.23),w-120,40)
            self.instructions.setGeometry(60,round(h*.29),w-120,60)
            self.status.setGeometry(60,round(h*.65),w-120,70)
        elif self.phase=="validate":self.status.setGeometry(60,round(h*.43),w-120,70)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,"return_button"):self._layout_controls()

    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(),QColor("#12202f"))
        if self.phase in {"calibrate","validate"}:
            x,y=self.target;center=QPointF(x*self.width(),y*self.height())
            painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor("#39d6bb"));painter.drawEllipse(center,9,9)
            painter.setBrush(Qt.BrushStyle.NoBrush);painter.setPen(QPen(QColor("#526577"),3));painter.drawEllipse(center,25,25)
            painter.setPen(QPen(QColor("#39d6bb"),4));painter.drawArc(QRectF(center.x()-25,center.y()-25,50,50),90*16,-round(self.progress*360*16))

    def done(self,result):
        self.timer.stop();self.samples.clear();self.checks.clear();self.preview.clear()
        super().done(result)

