import logging
import math
import os
import sys
import threading
import time
from dataclasses import replace
import psutil
from PySide6.QtCore import QEvent, QThread, QTimer, Signal, Qt
from PySide6.QtGui import QKeySequence, QShortcut, QFont, QFontDatabase, QTextCursor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton,
                             QHBoxLayout, QVBoxLayout, QFrame, QPlainTextEdit, QSplitter,
                             QSpinBox, QLineEdit, QCheckBox, QComboBox, QScrollArea, QLayout)
from .camera import CameraWorker
from .calibration import Surface
from .config import load_config
from .controller import CaptureController
from .injection import InjectionError, create_injector, validate_text
from .recognition import RecognitionWorker
from .rendering import render_strokes
from .state import State
from .widgets import CameraView, InkView
from .modes import ModesMixin
from .camera_preview import CameraPreviewMixin

LOG = logging.getLogger("slateink")


class SendWorker(QThread):
    done = Signal()
    failed = Signal(str)

    def __init__(self, injector, text, destination, limit):
        super().__init__()
        self.injector, self.text, self.destination, self.limit = injector, text, destination, limit
        self.cancel_event = threading.Event()

    def run(self):
        try:
            self.injector.send(self.text, self.destination, self.cancel_event.is_set, self.limit)
            self.done.emit()
        except Exception as exc:
            # Adapter exceptions contain diagnostics, never the accepted text.
            self.failed.emit(str(exc) if isinstance(exc, InjectionError) else "Input failed. No automatic retry; review the destination before trying again.")
        finally:
            self.text = ""


STYLE = """
QMainWindow, QWidget { background:#eef2f7; color:#172536; font-family:'Segoe UI'; font-size:14px; }
QLabel#title { font-size:28px; font-weight:700; }
QLabel#subtitle { color:#64748b; }
QLabel#status { background:#142c3d; color:#e8ffff; padding:9px 14px; border-radius:7px; font-weight:700; }
QLabel#camera { color:#655b70; font-weight:600; }
QLabel#heading { font-size:16px; font-weight:700; }
QLabel#hint { color:#496075; }
QLabel#error { background:#fff0df; color:#8a430d; padding:10px; border-radius:6px; }
QFrame#card { background:white; border:1px solid #dce4ed; border-radius:10px; }
QFrame#card QLabel, QFrame#card QWidget { background:white; }
QPushButton { background:#fff; border:1px solid #bccbd9; padding:9px 14px; border-radius:6px; font-weight:600; }
QPushButton:hover { background:#e3edf5; }
QPushButton:disabled { color:#98a3af; background:#e9eef4; border-color:#dce4ed; }
QPushButton#primary { background:#087f71; color:white; border-color:#087f71; }
QPushButton#primary:hover { background:#066c60; }
QPushButton#primary:disabled { color:#98a3af; background:#e9eef4; border-color:#dce4ed; }
QPushButton#danger { color:#a03737; border-color:#dab9b9; }
QPlainTextEdit { background:#fff; border:1px solid #bacbdc; border-radius:6px; padding:8px; font-size:18px; }
QSpinBox { background:white; padding:5px; border:1px solid #bccbd9; border-radius:5px; }
QLineEdit, QComboBox { background:white; padding:5px; border:1px solid #bccbd9; border-radius:5px; }
"""


class MainWindow(CameraPreviewMixin,ModesMixin,QMainWindow):
    def __init__(self, config=None,persist_preferences=False):
        super().__init__()
        self.config = config or load_config()
        self.persist_preferences=persist_preferences
        # Windows' offscreen Qt platform has no font enumeration. Explicitly
        # load the system font so layout checks use readable text as well.
        if sys.platform == "win32" and not QFontDatabase.families():
            QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
            QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeuib.ttf")
        self.controller = CaptureController(self.config)
        self.worker = None
        self.recognition_worker = None
        self.send_worker = None
        self.recognizer = None
        self.state = State.CAMERA_OFF
        self.last_packet_time = None
        self.camera_started_at = None
        self.camera_stats_logged = False
        self.resolution = None
        self.closing = False
        self.countdown_deadline = None
        self.destination_candidate = None
        self.destination_since = None
        self.accepted_text = None
        self.result_valid = False
        self.last_recognition = None
        self.pending_letter = None
        self.resume_after_letter = False
        self.restart_after_orientation = False
        self.camera_preview=None;self.gesture_caption_pending=False
        self.initialize_modes()
        self.injector = None
        try:
            self.injector = create_injector()
        except InjectionError:
            pass
        self.process = psutil.Process()
        self.process.cpu_percent()
        self.setWindowTitle("SlateInk • Local finger handwriting")
        self.resize(1240, 890)
        self.setMinimumSize(1000, 750)
        available = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1240,available.width()-40),min(890,available.height()-40))
        self.setStyleSheet(STYLE)
        self.build_ui()
        LOG.info("Application started; pid=%d; camera off; writing paused",os.getpid())
        self.refresh_controls()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)
        self.performance_timer = QTimer(self)
        self.performance_timer.timeout.connect(self.update_resources)
        self.performance_timer.start(1000)
        self.escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        self.escape_shortcut.activated.connect(self.emergency_stop)
        self.submit_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.submit_shortcut.activated.connect(self.submit)

    def button(self, text, callback, kind=None):
        b = QPushButton(text)
        if kind:
            b.setObjectName(kind)
        b.clicked.connect(callback)
        return b

    def build_ui(self):
        root = QWidget()
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(root)
        self.setCentralWidget(scroll)
        layout = QVBoxLayout(root)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(8)
        header = QHBoxLayout()
        title_area = QVBoxLayout()
        title = QLabel("SlateInk")
        title.setObjectName("title")
        subtitle = QLabel("Paper writing · hand touchpad · experimental eye control · local processing")
        subtitle.setObjectName("subtitle")
        title_area.addWidget(title)
        title_area.addWidget(subtitle)
        header.addLayout(title_area)
        header.addStretch()
        self.status_label = QLabel(self.state.value)
        self.status_label.setObjectName("status")
        header.addWidget(self.status_label)
        layout.addLayout(header)
        self.camera_indicator = QLabel("● CAMERA OFF — no capture")
        self.camera_indicator.setObjectName("camera")
        camera_options=QHBoxLayout()
        camera_options.addWidget(self.camera_indicator,1)
        self.mirror=QCheckBox("Mirror camera")
        self.mirror.setChecked(self.config.camera_mirrored)
        self.rotation=QComboBox()
        self.rotation.addItems(["0°","90° clockwise","180°","270° clockwise"])
        self.rotation.setCurrentIndex(self.config.camera_rotation//90)
        camera_options.addWidget(self.mirror)
        camera_options.addWidget(QLabel("Rotate:"))
        camera_options.addWidget(self.rotation)
        layout.addLayout(camera_options)
        self.build_modes(layout)
        toolbar = QHBoxLayout()
        self.camera_button = self.button("Start camera", self.toggle_camera)
        self.calibrate_button = self.button("1  Calibrate slate", self.begin_calibration)
        self.capture_button = self.button("2  Enable writing", self.toggle_capture, "primary")
        self.clear_button = self.button("Clear ink", self.clear_ink)
        self.undo_button = self.button("Undo stroke", self.undo)
        self.stop_button = self.button("Stop everything  ·  Esc", self.emergency_stop, "danger")
        for b in (self.camera_button,self.calibrate_button,self.capture_button,self.undo_button,self.clear_button):
            toolbar.addWidget(b)
        toolbar.addStretch()
        self.camera_preview_choice=QCheckBox("Floating camera preview")
        self.camera_preview_choice.setChecked(self.config.camera_preview_enabled)
        self.camera_preview_choice.setToolTip("Show the same camera feed above other windows in every mode. Drag its header to place it; × hides it. Position and choice are saved.")
        self.camera_preview_choice.toggled.connect(self.set_camera_preview)
        toolbar.addWidget(self.camera_preview_choice)
        toolbar.addWidget(self.stop_button)
        layout.addLayout(toolbar)
        self.hint = QLabel("Start camera, then Enable desktop mouse — no area calibration is needed." if self.mode=="hand_mouse" else "Start the camera, check orientation, then select the area for this mode.")
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setMinimumHeight(210)
        camera_card = QFrame()
        camera_card.setObjectName("card")
        camera_layout = QVBoxLayout(camera_card)
        camera_heading = QLabel("Camera / slate calibration")
        self.camera_heading=camera_heading
        camera_heading.setObjectName("heading")
        camera_layout.addWidget(camera_heading)
        self.camera_view = CameraView()
        self.camera_view.corner_clicked.connect(self.add_corner)
        self.camera_view.pen_clicked.connect(self.set_pen_marker)
        camera_layout.addWidget(self.camera_view,1)
        self.hand_label = QLabel("Hand: —  ·  Pinch: —")
        camera_layout.addWidget(self.hand_label)
        ink_card = QFrame()
        ink_card.setObjectName("card")
        ink_layout = QVBoxLayout(ink_card)
        self.ink_heading = QLabel("Virtual ink / one letter at a time")
        self.ink_heading.setObjectName("heading")
        ink_layout.addWidget(self.ink_heading)
        self.ink_view = InkView(self.controller, self.config)
        ink_layout.addWidget(self.ink_view,1)
        self.ink_label = QLabel("0 strokes  ·  0 points")
        ink_layout.addWidget(self.ink_label)
        splitter.addWidget(camera_card)
        splitter.addWidget(ink_card)
        splitter.setSizes([560,560])
        layout.addWidget(splitter,1)
        self.metrics = QLabel("Camera FPS: —  ·  Tracking FPS: —  ·  Tracking latency: —")
        self.metrics.setObjectName("subtitle")
        layout.addWidget(self.metrics)
        self.resources = QLabel("CPU: —  ·  Memory: —  ·  Recognition: CPU")
        self.resources.setObjectName("subtitle")
        layout.addWidget(self.resources)
        self.error_label = QLabel()
        self.error_label.setObjectName("error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        self.recognition_heading=QWidget()
        preview_heading = QHBoxLayout(self.recognition_heading)
        preview_heading.setContentsMargins(0,0,0,0)
        ptitle = QLabel("3  Recognize, review & correct")
        ptitle.setObjectName("heading")
        preview_heading.addWidget(ptitle)
        preview_heading.addStretch()
        self.submit_button = self.button("Recognize letter  ·  Ctrl+Enter", self.submit, "primary")
        preview_heading.addWidget(self.submit_button)
        layout.addWidget(self.recognition_heading)
        self.letter_panel=QWidget()
        letter_actions=QHBoxLayout(self.letter_panel)
        letter_actions.setContentsMargins(0,0,0,0)
        letter_actions.addWidget(QLabel("Letter:"))
        self.letter_preview=QLineEdit()
        self.letter_preview.setMaxLength(1)
        self.letter_preview.setMaximumWidth(60)
        self.letter_preview.setPlaceholderText("?")
        letter_actions.addWidget(self.letter_preview)
        self.uppercase=QCheckBox("Uppercase")
        letter_actions.addWidget(self.uppercase)
        self.add_letter_button=self.button("Add letter & next",self.add_letter,"primary")
        letter_actions.addWidget(self.add_letter_button)
        self.choices=QLabel("Review each letter before adding it.")
        self.choices.setObjectName("subtitle")
        letter_actions.addWidget(self.choices,1)
        layout.addWidget(self.letter_panel)
        self.score_label = QLabel("Model score: — (uncalibrated; not measured accuracy)")
        self.score_label.setObjectName("subtitle")
        self.score_label.setWordWrap(True)
        layout.addWidget(self.score_label)
        self.preview = QPlainTextEdit()
        self.preview.setPlaceholderText("Collected text. Each accepted letter is added here; you can edit this text.")
        self.preview.setMaximumHeight(65)
        layout.addWidget(self.preview)
        text_actions=QHBoxLayout()
        self.space_button=self.button("Add space",self.add_space)
        self.backspace_button=self.button("Backspace text",self.backspace_text)
        text_actions.addWidget(self.space_button)
        text_actions.addWidget(self.backspace_button)
        self.text_note=QLabel("Ink clears after Add letter; collected text stays.")
        text_actions.addWidget(self.text_note,1)
        layout.addLayout(text_actions)
        actions = QHBoxLayout()
        self.accept_button = self.button("4  Type collected text", self.accept, "primary")
        self.retry_button = self.button("Retry recognition", self.submit)
        self.discard_button = self.button("Discard all / cancel", self.discard)
        actions.addWidget(self.accept_button)
        self.delay_label=QLabel("Delay:");actions.addWidget(self.delay_label)
        self.delay = QSpinBox()
        self.delay.setRange(2,30)
        self.delay.setValue(int(self.config.typing_delay_seconds))
        self.delay.setSuffix(" s")
        actions.addWidget(self.delay)
        actions.addWidget(self.retry_button)
        actions.addWidget(self.discard_button)
        actions.addStretch()
        actions.addWidget(self.button("Stop & quit", self.close, "danger"))
        layout.addLayout(actions)
        self.footer = QLabel("Slate mode · capture starts paused · no cloud or clipboard · Esc stops capture and pending typing")
        self.footer.setObjectName("subtitle")
        self.footer.setWordWrap(True)
        layout.addWidget(self.footer)
        self.mirror.toggled.connect(self.change_orientation)
        self.rotation.currentIndexChanged.connect(self.change_orientation)
        self.uppercase.toggled.connect(self.change_case)
        self.preview.textChanged.connect(self.sync_text)

    def set_state(self, state):
        if state != self.state:
            LOG.info("State: %s", state.value)
        self.state = state
        self.status_label.setText(state.value)
        self.refresh_controls()

    def refresh_controls(self):
        camera_active = self.worker is not None
        busy = self.state in {State.PROCESSING, State.TYPING} or self.send_worker is not None
        stopping = camera_active and self.worker.stop_event.is_set()
        self.camera_button.setText("Stopping camera…" if stopping else ("Stop camera" if camera_active else "Start camera"))
        self.camera_button.setEnabled(not busy and not stopping)
        self.calibrate_button.setEnabled(camera_active and self.camera_view.image is not None and not busy and not stopping)
        self.capture_button.setEnabled(camera_active and self.controller.surface is not None and not busy and not stopping and self.pending_letter is None)
        self.capture_button.setText("Pause writing" if self.controller.enabled else "2  Enable writing")
        self.undo_button.setEnabled(not busy and bool(self.controller.buffer.strokes))
        self.clear_button.setEnabled(not busy and bool(self.controller.buffer.strokes))
        recognizer_busy = self.recognition_worker is not None
        self.submit_button.setEnabled(not busy and not recognizer_busy and bool(self.controller.buffer.strokes))
        self.retry_button.setEnabled(self.pending_letter is not None and not busy and not recognizer_busy and bool(self.controller.buffer.strokes))
        self.accept_button.setEnabled(self.result_valid and not busy and self.injector is not None and self.pending_letter is None and not self.controller.buffer.strokes and not recognizer_busy)
        self.preview.setEnabled(not busy)
        self.letter_preview.setEnabled(self.pending_letter is not None and not busy)
        self.add_letter_button.setEnabled(self.pending_letter is not None and not busy and not recognizer_busy)
        self.uppercase.setEnabled(not busy)
        self.space_button.setEnabled(not busy)
        self.backspace_button.setEnabled(not busy and bool(self.preview.toPlainText()))
        self.mirror.setEnabled(not busy and not recognizer_busy and not stopping)
        self.rotation.setEnabled(not busy and not recognizer_busy and not stopping)
        self.delay.setEnabled(not busy)
        self.discard_button.setEnabled(bool(self.controller.buffer.strokes) or self.result_valid or self.pending_letter is not None or busy)
        self.refresh_modes(busy,stopping)
        self.sync_camera_preview()

    def sync_text(self):
        self.result_valid=bool(self.preview.toPlainText().strip())
        self.refresh_controls()

    def change_case(self):
        if self.pending_letter is not None:
            current=self.letter_preview.text()
            self.letter_preview.setText(current.upper() if self.uppercase.isChecked() else current.lower())

    def add_space(self):
        if self.space_button.isEnabled():
            self.preview.moveCursor(QTextCursor.MoveOperation.End)
            self.preview.insertPlainText(" ")

    def backspace_text(self):
        if self.backspace_button.isEnabled():
            cursor=self.preview.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.deletePreviousChar()
            self.preview.setTextCursor(cursor)

    def change_orientation(self):
        if self.state in {State.PROCESSING,State.TYPING} or self.recognition_worker is not None or self.send_worker is not None:
            return
        self.stop_pointer()
        self.pen_marker.reset()
        self.config=replace(self.config,camera_mirrored=self.mirror.isChecked(),camera_rotation=self.rotation.currentIndex()*90)
        self.restart_after_orientation=self.worker is not None
        self.controller.set_enabled(False)
        self.controller.clear()
        self.invalidate_result()
        self.stop_camera(preserve_state=True)
        self.camera_view.clear()
        self.ink_view.update()
        self.set_state(State.READY if self.restart_after_orientation else State.CAMERA_OFF)
        self.hint.setText("Orientation changed. Current letter cleared; collected text kept. Recalibrate before writing.")

    def show_error(self, message):
        self.error_label.setText(message)
        self.error_label.show()
        LOG.warning("User-visible failure; private content omitted")

    def toggle_camera(self):
        if self.worker is not None:
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self):
        if self.worker is not None or self.closing or self.state in {State.PROCESSING,State.TYPING}:
            return
        self.error_label.hide()
        self.reset_gaze()
        self.controller.surface = None
        self.controller.set_enabled(False)
        self.camera_view.corners = []
        self.camera_view.calibrating = False
        self.resolution = None
        self.last_packet_time = time.monotonic()
        self.camera_started_at = self.last_packet_time
        self.camera_stats_logged = False
        self.worker = CameraWorker(self.config)
        self.worker.failed.connect(self.camera_failed)
        self.worker.finished.connect(self.camera_finished)
        self.camera_indicator.setText("● CAMERA STARTING — visible capture requested")
        self.hint.setText("Starting camera and local hand tracker…")
        self.set_state(State.READY if self.pending_letter is None else State.PREVIEW)
        self.worker.start()

    def stop_camera(self, preserve_state=False):
        if not preserve_state:self.arm_touchpad_when_ready=False
        self.reset_gaze()
        self.latest_rgb=None; self.latest_frame_at=None
        self.camera_view.selecting_pen=False
        self.ink_view.set_image(None)
        self.controller.set_enabled(False)
        self.controller.surface = None
        self.camera_view.calibrating = False
        self.camera_view.corners = []
        if self.worker is not None:
            self.worker.stop()
            self.camera_indicator.setText("● CAMERA STOPPING — waiting for device release")
        else:
            self.camera_indicator.setText("● CAMERA OFF — no capture")
        if not preserve_state:
            self.cancel_pending()
            self.set_state(State.PREVIEW if self.result_valid or self.pending_letter is not None else State.CAMERA_OFF)
        self.refresh_controls()

    def camera_failed(self, message):
        self.cancel_pending()
        self.controller.set_enabled(False)
        self.show_error(message)
        self.stop_camera()

    def camera_finished(self):
        old = self.worker
        self.worker = None
        if old:
            old.deleteLater()
        self.camera_view.clear()
        self.camera_indicator.setText("● CAMERA OFF — no capture")
        self.hand_label.setText("Hand: —  ·  Pinch: —")
        if self.state not in {State.PROCESSING,State.TYPING,State.PREVIEW}:
            self.set_state(State.CAMERA_OFF)
        self.refresh_controls()
        if self.closing:
            self.close()
        elif self.restart_after_orientation:
            self.restart_after_orientation=False
            self.start_camera()

    def begin_calibration(self):
        if not self.calibrate_button.isEnabled():
            return
        if self.mode=="eye_gaze":self.begin_gaze_calibration();return
        self.stop_pointer()
        self.camera_view.selecting_pen=False
        self.controller.set_enabled(False)
        self.controller.surface = None
        self.controller.clear()
        self.invalidate_result()
        self.camera_view.corners = []
        self.camera_view.calibrating = True
        self.set_state(State.READY)
        self.error_label.hide()
        self.hint.setText("Select the writing/pointer area in the displayed view: TOP LEFT → TOP RIGHT → BOTTOM RIGHT → BOTTOM LEFT.")
        self.camera_view.update()

    def add_corner(self, x, y):
        if not self.camera_view.calibrating:
            return
        self.camera_view.corners.append((x,y))
        if len(self.camera_view.corners) == 4:
            try:
                self.controller.surface = Surface.from_corners(self.camera_view.corners)
                self.camera_view.calibrating = False
                self.hint.setText("Slate calibrated. Enable writing, show one hand, open the pinch briefly, then pinch to draw. Release between strokes.")
            except ValueError as exc:
                self.camera_view.corners = []
                self.show_error(str(exc))
        self.camera_view.update()
        self.refresh_controls()

    def toggle_capture(self):
        if not self.capture_button.isEnabled():
            return
        self.controller.set_enabled(not self.controller.enabled)
        self.set_state(State.READY)
        self.refresh_controls()

    def invalidate_result(self,clear_text=False):
        self.pending_letter = None
        self.last_recognition = None
        self.letter_preview.clear()
        self.choices.setText("Review each letter before adding it.")
        if clear_text:
            self.preview.clear()
        self.result_valid=bool(self.preview.toPlainText().strip())
        self.score_label.setText("Model score: — (uncalibrated; not measured accuracy)")

    def clear_ink(self):
        if self.state in {State.PROCESSING,State.TYPING}:
            return
        self.controller.clear()
        self.resume_after_letter=False
        self.invalidate_result()
        self.ink_view.update()
        self.set_state(State.READY if self.worker else State.CAMERA_OFF)

    def undo(self):
        if not self.undo_button.isEnabled():
            return
        self.controller.interrupt()
        self.controller.buffer.undo()
        self.invalidate_result()
        self.ink_view.update()
        self.set_state(State.READY if self.worker else State.CAMERA_OFF)

    def submit(self):
        if self.mode=="paper":
            self.submit_paper(); return
        if self.mode!="finger_letters":return
        if not self.submit_button.isEnabled():
            return
        # Retain resume intent when retrying a pending letter.
        self.resume_after_letter=self.resume_after_letter or self.controller.enabled
        self.controller.set_enabled(False)
        image = render_strokes(self.controller.buffer.snapshot(),self.config.canvas_width,self.config.canvas_height)
        self.error_label.hide()
        self.invalidate_result()
        self.set_state(State.PROCESSING)
        self.hint.setText("Recognizing this letter locally. Writing is paused; no text will be sent.")
        self.recognition_worker = RecognitionWorker(image,self.config.recognition_device,self.recognizer)
        self.recognition_kind="letter"
        self.recognition_worker.ready.connect(self.recognized)
        self.recognition_worker.failed.connect(self.recognition_failed)
        self.recognition_worker.finished.connect(self.recognition_finished)
        self.recognition_worker.start()

    def recognized(self, result):
        if self.state != State.PROCESSING or self.closing:
            return
        if self.recognition_kind=="paper":
            self.recognized_paper(result); return
        self.last_recognition = result
        if len(result.text)!=1 or result.text.upper() not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            self.recognition_failed("The model did not return one English letter. Retry or clear this letter.")
            return
        self.pending_letter=result
        self.letter_preview.setText(result.text.upper() if self.uppercase.isChecked() else result.text.lower())
        self.choices.setText("Candidates: "+"  ·  ".join(f"{char}: {value:.0%}" for char,value in result.alternatives))
        score = f"{result.score:.0%}" if result.score is not None else "unavailable"
        self.score_label.setText(f"Model score: {score} (uncalibrated)  ·  Letter recognition: {result.latency_seconds:.3f} s  ·  Review required")
        if result.truncated:
            self.show_error("The model reached its output limit. Review for missing text or write a shorter line.")
        elif result.score is None or result.score < self.config.low_score_threshold:
            self.show_error("Low model score. Carefully edit the preview, retry, or discard. Nothing has been sent.")
        self.hint.setText("Review or edit the single letter, then Add letter & next. This clears ink and keeps your collected text.")
        self.set_state(State.PREVIEW)

    def add_letter(self):
        if not self.add_letter_button.isEnabled():
            return
        letter=self.letter_preview.text()
        if len(letter)!=1 or letter.upper() not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            self.show_error("Enter exactly one English letter before adding it.")
            return
        if len(self.preview.toPlainText())>=self.config.max_text_characters:
            self.show_error("Collected text is full. Send or shorten it before adding another letter.")
            return
        self.preview.moveCursor(QTextCursor.MoveOperation.End)
        self.preview.insertPlainText(letter)
        self.controller.clear()
        self.invalidate_result()
        self.error_label.hide()
        self.controller.set_enabled(self.resume_after_letter and self.worker is not None)
        self.resume_after_letter=False
        self.ink_view.update()
        self.set_state(State.READY if self.worker else State.CAMERA_OFF)
        self.hint.setText("Letter added. Open the pinch, then write the next letter over the same area. Add space between words.")

    def recognition_failed(self, message):
        self.invalidate_result()
        if self.recognition_kind=="paper":
            self.result_valid=False
            self.score_label.setText("Paper OCR failed — any previous preview is retained for reference; edit or recapture before sending.")
        self.show_error(message)
        self.set_state(State.READY if self.worker else State.CAMERA_OFF)

    def recognition_finished(self):
        old = self.recognition_worker
        if old:
            if self.recognition_kind=="paper":self.paper_recognizer=old.recognizer
            else:self.recognizer = old.recognizer
        self.recognition_worker = None
        if old:
            old.deleteLater()
        self.refresh_controls()
        if self.closing:
            self.close()

    def accept(self):
        if not self.accept_button.isEnabled():
            return
        try:
            text = validate_text(self.preview.toPlainText(), self.config.max_text_characters)
        except InjectionError as exc:
            self.show_error(str(exc))
            return
        self.error_label.hide()
        self.accepted_text = text
        self.destination_candidate = self.destination_since = None
        self.stop_camera(preserve_state=True)
        self.countdown_deadline = time.monotonic()+self.delay.value()
        self.set_state(State.TYPING)
        self.hint.setText("Accepted. Click the destination textbox now. Keep focus there; Escape cancels.")

    def cancel_pending(self):
        self.countdown_deadline = None
        self.accepted_text = None
        self.destination_candidate = self.destination_since = None
        if self.send_worker is not None:
            self.send_worker.cancel_event.set()

    def typing_tick(self, now):
        if self.countdown_deadline is None:
            return
        remaining = self.countdown_deadline-now
        if self.injector.escape_pressed():
            self.emergency_stop()
            return
        try:
            current = self.injector.destination()
            if current != self.destination_candidate:
                self.destination_candidate, self.destination_since = current, now
        except InjectionError:
            self.destination_candidate = self.destination_since = None
        self.hint.setText(f"Typing in {max(0,math.ceil(remaining))} s — click the destination textbox and leave focus there. Escape cancels.")
        if remaining > 0:
            return
        text, self.accepted_text = self.accepted_text, None
        self.countdown_deadline = None
        if (self.destination_candidate is None or self.destination_since is None
                or now-self.destination_since < 0.75 or self.injector.modifiers_pressed()):
            self.show_error("Typing cancelled: focus was not stable in an external textbox. Review the preview and accept again.")
            self.set_state(State.PREVIEW)
            return
        if self.worker is not None:
            self.show_error("Typing cancelled: camera is still stopping. Accept again after the camera is off.")
            self.set_state(State.PREVIEW)
            return
        self.send_worker = SendWorker(self.injector,text,self.destination_candidate,self.config.max_text_characters)
        self.send_worker.done.connect(self.sent)
        self.send_worker.failed.connect(self.send_failed)
        self.send_worker.finished.connect(self.send_finished)
        self.send_worker.start()
        self.hint.setText("Sending accepted text. Escape stops the remaining characters.")

    def sent(self):
        self.controller.clear()
        self.invalidate_result(clear_text=True)
        self.ink_view.update()
        self.hint.setText("Collected text sent. Start the camera and calibrate again to write more letters.")
        self.set_state(State.CAMERA_OFF)

    def send_failed(self, message):
        self.show_error(message)
        self.set_state(State.PREVIEW)

    def send_finished(self):
        old, self.send_worker = self.send_worker, None
        if old:
            old.deleteLater()
        self.refresh_controls()
        if self.closing:
            self.close()

    def discard(self):
        self.cancel_pending()
        if self.recognition_worker is not None:
            self.recognition_worker.requestInterruption()
        self.controller.set_enabled(False)
        self.controller.clear()
        self.invalidate_result(clear_text=True)
        self.ink_view.update()
        self.ink_view.set_image(None)
        self.hint.setText("Handwriting discarded. Capture is paused.")
        self.set_state(State.READY if self.worker else State.CAMERA_OFF)

    def emergency_stop(self):
        self.arm_touchpad_when_ready=False
        self.restart_after_orientation=False
        self.resume_after_letter=False
        self.cancel_pending()
        if self.recognition_worker is not None:
            self.recognition_worker.requestInterruption()
        self.stop_camera()
        self.hint.setText("Stopped. No pending typing. Any preview is retained for review.")

    def update_resources(self):
        cpu = self.process.cpu_percent()
        memory = self.process.memory_info().rss/(1024*1024)
        device=self.paper_recognizer.device if self.paper_recognizer else "not loaded"
        self.resources.setText(f"Process CPU: {cpu:.0f}% (100% = one core)  ·  RAM: {memory:.0f} MB  ·  Tracking: CPU · Paper OCR: {device}")

    def tick(self):
        now = time.monotonic()
        if self.injector is not None and self.injector.escape_pressed():
            if self.countdown_deadline is not None or self.controller.enabled or self.worker is not None:
                self.emergency_stop()
        self.typing_tick(now)
        self.pointer_tick(now)
        if self.worker is not None and not self.worker.stop_event.is_set():
            packet = self.worker.take()
            if packet is not None:
                self.last_packet_time = now
                resolution = (packet.rgb.shape[1],packet.rgb.shape[0])
                if self.resolution is not None and resolution != self.resolution:
                    self.reset_gaze()
                    self.controller.set_enabled(False)
                    self.controller.surface = None
                    self.camera_view.corners = []
                    self.camera_view.calibrating = False
                    self.show_error("Camera resolution changed. Calibrate the slate again before writing.")
                self.resolution = resolution
                self.camera_view.set_frame(packet.rgb, packet.hand)
                self.process_mode_packet(packet,now)
                self.camera_indicator.setText("● CAMERA ACTIVE — frames stay in memory on this computer")
                if not self.camera_stats_logged and now-self.camera_started_at > 3 and len(self.worker.source.times)>=60 and packet.tracking_fps>0:
                    LOG.info("Camera live: %dx%d; camera_fps=%.1f; tracking_fps=%.1f; tracking_ms=%.1f; writing_paused=%s",
                             resolution[0],resolution[1],packet.camera_fps,packet.tracking_fps,packet.tracking_ms,
                             not self.controller.enabled)
                    self.camera_stats_logged = True
                if self.controller.surface is None and self.mode not in {"hand_mouse","eye_gaze"}:
                    self.hint.setText(self.hint.text() if self.camera_view.calibrating or self.state in {State.PROCESSING,State.PREVIEW} or self.camera_view.selecting_pen else "Camera ready. Check orientation, then select the writing/pointer area for this mode.")
                elif self.mode=="finger_letters":
                    try:
                        message = self.controller.process(packet.hand,packet.t,now-packet.t)
                    except BufferError as exc:
                        self.controller.set_enabled(False)
                        self.show_error(str(exc))
                        message = "Canvas full. Submit or clear the current line."
                    if self.state not in {State.PROCESSING,State.PREVIEW,State.TYPING}:
                        self.hint.setText(message)
                        self.set_state(State.WRITING if self.controller.buffer.active else State.READY)
                if self.mode=="hand_mouse":
                    primary=self.touchpad_session.primary
                    helper=self.touchpad_session.helper
                    keys=" + ".join(sorted(self.touchpad_session.gaming.wanted)) or "none"
                    if self.config.touchpad_submode=="fun":
                        self.hand_label.setText("Fun playground · "+(self.fun_window.model.input_state if self.fun_window else "Choose a scene, then Enter playground"))
                    elif self.config.touchpad_submode=="gaming":
                        self.hand_label.setText(f"Mouse: right hand {'visible' if primary else 'missing'} · Joystick: left hand {'visible' if helper else 'missing'} · Button: {self.touchpad_session.button_held or 'none'} · WASD: {keys}")
                    else:self.hand_label.setText(f"Control: {primary.label if primary else 'missing'} · Helper: {helper.label if helper else 'none'} · Button: {self.touchpad_session.button_held or 'none'}")
                elif self.mode=="eye_gaze":
                    eyes="visible" if packet.eye and packet.eye.valid else ("multiple faces — blocked" if packet.eye_count>1 else "unclear / not visible")
                    hand=packet.hand.label if packet.hand else ("multiple — clicks blocked" if packet.hand_count>1 else "none")
                    self.hand_label.setText(f"Eyes: {eyes} · Hand: {hand} · Held: {self.gaze_controller.held if self.gaze_controller and self.gaze_controller.held else 'none'}")
                elif packet.hand is not None:
                    ratio = f"{packet.hand.ratio:.2f}" if packet.hand.ratio is not None else "unavailable"
                    if self.mode=="hand_mouse":
                        held=self.hand_mouse.button_held or "none"
                        self.hand_label.setText(f"Hand: {packet.hand.label} · Index pinch: {ratio} · Mouse button held: {held}")
                    else:self.hand_label.setText(f"Hand: {packet.hand.label}  ·  Pinch ratio: {ratio}  ·  Pen: {'DOWN' if self.controller.buffer.active else 'UP'}")
                else:
                    self.hand_label.setText("Hand: none" if packet.hand_count == 0 else "Two hands visible — writing blocked")
                self.metrics.setText(f"Camera: {packet.camera_fps:.1f} FPS  ·  Tracking: {packet.tracking_fps:.1f} FPS  ·  Inference: {packet.tracking_ms:.1f} ms"+(f" + eyes {packet.eye_ms:.1f} ms" if self.mode=="eye_gaze" else "")+f"  ·  Frame age: {(now-packet.t)*1000:.1f} ms  ·  {resolution[0]}×{resolution[1]}")
                self.ink_view.update()
                self.refresh_controls()
            elif self.last_packet_time is not None and now-self.last_packet_time > 0.2:
                self.sync_camera_preview()
                self.controller.interrupt()
                if self.hand_mouse is not None:
                    try:
                        if self.mode=="hand_mouse" and self.touchpad_session:self.touchpad_session.tracking_stale()
                        else:self.hand_mouse.interrupt()
                    except InjectionError as exc:self.stop_pointer(); self.show_error(str(exc))
                self.pen_filter.reset()
                if self.gaze_controller:
                    try:self.gaze_controller.interrupt()
                    except InjectionError as exc:self.stop_pointer();self.show_error(str(exc))
                if self.mode=="eye_gaze":self.hint.setText("Eye tracking stale — buttons released and cursor paused.")
                if self.mode=="hand_mouse" and self.hand_mouse is not None and self.hand_mouse.enabled:
                    self.hint.setText("Wispr listening — same-hand index + pinky + thumb finishes when tracking returns." if self.touchpad_session.dictating else "Tracking stale — all held input released. Re-arm the selected sub-mode to resume.")
                    self.hand_label.setText("Tracking stale · Held input released")
                if self.state == State.WRITING:
                    self.set_state(State.READY)
                    self.hint.setText("Tracking stale — stroke ended. Release pinch to resume.")
        if self.mode=="finger_letters":self.ink_label.setText(f"{len(self.controller.buffer.strokes)} strokes  ·  {self.controller.buffer.count} points")
        elif self.mode=="paper":self.ink_label.setText("Snapshot preview · images remain in memory only")
        else:self.ink_label.setText("Pointer controls are explicitly enabled; Escape stops them")

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            self.handle_background_window()

    def hideEvent(self, event):
        if not self.closing:
            self.handle_background_window()
        super().hideEvent(event)

    def closeEvent(self, event):
        self.closing = True
        self.cancel_pending()
        self.stop_camera(preserve_state=True)
        if self.recognition_worker:
            self.recognition_worker.requestInterruption()
        if self.worker is not None or self.recognition_worker is not None or self.send_worker is not None:
            self.hint.setText("Stopping workers and releasing camera before closing…")
            event.ignore()
            return
        self.controller.clear()
        self.preview.clear()
        self.recognizer = None
        self.paper_recognizer=None; self.latest_rgb=None
        if self.desktop_hotkey:self.desktop_hotkey.close()
        if self.tray:self.tray.hide()
        if self.camera_preview:self.camera_preview.view.clear();self.camera_preview.hide()
        event.accept()

    def handle_gesture_caption(self,hit):
        if hit not in (8,9,20) or self.gesture_caption_pending or self.closing:return False
        if not self.mouse_sink or "left" not in self.mouse_sink.held:return False
        self.gesture_caption_pending=True
        def act():
            self.gesture_caption_pending=False
            if self.closing:return
            try:
                if self.touchpad_session:self.touchpad_session.interrupt()
                if self.gaze_controller:self.gaze_controller.interrupt()
                self.mouse_sink.release_all()
            except InjectionError as error:self.stop_pointer();self.show_error(str(error));return
            if hit==8:self.showMinimized()
            elif hit==9:self.showNormal() if self.isMaximized() else self.showMaximized()
            else:self.close()
        QTimer.singleShot(0,act)
        return True

    def nativeEvent(self,event_type,message):
        if sys.platform=="win32":
            import ctypes
            from ctypes import wintypes
            msg=ctypes.cast(int(message),ctypes.POINTER(wintypes.MSG)).contents
            if msg.message==0x00A1 and self.handle_gesture_caption(int(msg.wParam)):
                # Consume only our owned gesture click, avoiding the native
                # caption-button tracking loop that blocks gesture release.
                return True,0
        return super().nativeEvent(event_type,message)


def run(start_camera=False,mode=None):
    app = QApplication(sys.argv)
    app.setApplicationName("SlateInk")
    from .single_instance import SingleInstance
    from PySide6.QtWidgets import QMessageBox
    guard=SingleInstance()
    try:
        if not guard.acquire():return 0
    except RuntimeError as error:
        QMessageBox.information(None,"SlateInk",str(error));return 1
    config=load_config()
    if mode:config=replace(config,initial_mode=mode,camera_width=1280 if mode=="paper" else 640,camera_height=720 if mode=="paper" else 480)
    window = MainWindow(config,persist_preferences=True)
    def show_existing():window.showNormal();window.raise_();window.activateWindow()
    guard.show_requested.connect(show_existing)
    window.show()
    window.install_desktop_controls()
    if start_camera:
        QTimer.singleShot(250,window.start_camera)
    try:return app.exec()
    finally:guard.close()
