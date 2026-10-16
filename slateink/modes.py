"""UI coordination for paper OCR, hand mouse, and experimental pen pointer."""
from dataclasses import replace
import time
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QHBoxLayout,QVBoxLayout,QLabel,QComboBox,QCheckBox,QDoubleSpinBox,QApplication,QSystemTrayIcon,QMenu
from PySide6.QtGui import QPixmap,QPainter,QColor,QIcon,QPen
from .mouse_control import WindowsMouse,HandMouseController
from .pen_tracking import PenMarker
from .smoothing import OneEuro
from .paper_ocr import PaperWorker,warp_paper
from .injection import InjectionError
from .state import State
from .gaze import GazeCalibration,GazeController
from .gaze_widgets import GazeCalibrationDialog
from .touchpad_session import TouchpadSession
from .desktop_shortcuts import WindowsWisprShortcut
from .touchpad_submodes import WindowsMovementKeys
from .window_switching import WindowsWindowSwitcher

MODES=("paper","hand_mouse","pen_pointer","finger_letters","eye_gaze")


class ModesMixin:
    def initialize_modes(self):
        self.mode=self.config.initial_mode
        self.latest_rgb=None; self.latest_hand_count=0; self.latest_frame_at=None
        self.recognition_kind="letter"; self.paper_recognizer=None
        self.pointer_deadline=None; self.pen_pointer_enabled=False
        self.pen_marker=PenMarker(); self.pen_filter=OneEuro(min_cutoff=2.5,beta=1.3)
        self.mouse_sink=None; self.hand_mouse=None
        try:
            self.mouse_sink=WindowsMouse(); self.hand_mouse=HandMouseController(self.config,self.mouse_sink)
        except InjectionError:pass
        self.shortcut_sink=None;self.touchpad_session=None;self.desktop_hotkey=None;self.tray=None;self.arm_touchpad_when_ready=False
        self.game_hud=None
        if self.hand_mouse:
            self.shortcut_sink=WindowsWisprShortcut();self.touchpad_session=TouchpadSession(self.hand_mouse,self.shortcut_sink,WindowsMovementKeys(),WindowsWindowSwitcher())
        self.gaze_calibration=GazeCalibration();self.gaze_dialog=None
        self.gaze_controller=GazeController(self.config,self.mouse_sink,self.gaze_calibration) if self.mouse_sink else None
        if self.mode=="paper":self.config=replace(self.config,camera_width=1280,camera_height=720)

    def build_modes(self,layout):
        self.mode_panel=QWidget(); panel=QVBoxLayout(self.mode_panel);panel.setContentsMargins(0,0,0,0)
        row=QHBoxLayout();panel.addLayout(row)
        row.addWidget(QLabel("Mode:"))
        self.mode_choice=QComboBox()
        self.mode_choice.addItems(["Paper / slate OCR","Hand touchpad","Pen hover pointer (experimental)","Finger letters (experimental)","Eye gaze + pinch (experimental)"])
        self.mode_choice.setCurrentIndex(MODES.index(self.mode)); row.addWidget(self.mode_choice)
        row.addStretch();row=QHBoxLayout();panel.addLayout(row)
        self.dark_slate=QCheckBox("Light ink on dark slate"); row.addWidget(self.dark_slate)
        self.ocr_variant=QComboBox(); self.ocr_variant.addItems(["Balanced OCR","English light OCR"]); row.addWidget(self.ocr_variant)
        self.ocr_device=QComboBox();self.ocr_device.addItems(["GPU when available","CPU","GPU required"])
        self.ocr_device.setCurrentIndex({"auto":0,"cpu":1,"cuda":2}[self.config.ocr_device]);row.addWidget(self.ocr_device)
        self.sensitivity=QDoubleSpinBox();self.sensitivity.setRange(.25,3);self.sensitivity.setSingleStep(.25)
        self.sensitivity.setValue(self.config.touchpad_sensitivity);self.sensitivity.setPrefix("Speed × ");row.addWidget(self.sensitivity)
        self.sensitivity.valueChanged.connect(self.set_touchpad_speed)
        self.right_click=QCheckBox("Middle + thumb: right click"); self.right_click.setChecked(True); row.addWidget(self.right_click)
        self.right_click.setToolTip("Pinch thumb + middle clearly, with the index pinch open; hold briefly (about 0.1 seconds), then release. A brief passing touch or fast hand sweep does not right-click.")
        self.unverified_gaze=QCheckBox("Allow unverified gaze");self.unverified_gaze.setChecked(self.config.gaze_allow_unverified)
        self.unverified_gaze.setToolTip("Enable after the nine-dot mapping even if accuracy checks fail. Pointing may be inaccurate.")
        self.unverified_gaze.toggled.connect(self.set_unverified_gaze);row.addWidget(self.unverified_gaze)
        self.pointer_button=self.button("Enable desktop mouse",self.toggle_pointer,"primary"); row.addWidget(self.pointer_button)
        self.pen_select_button=self.button("Select pen marker",self.select_pen); row.addWidget(self.pen_select_button)
        row.addStretch(); layout.addWidget(self.mode_panel)
        self.touchpad_panel=QWidget();options=QHBoxLayout(self.touchpad_panel);options.setContentsMargins(0,0,0,0)
        self.hand_choice=QComboBox();self.hand_choice.addItems(["Control hand: first shown","Control hand: left","Control hand: right"])
        self.hand_choice.setCurrentIndex(("auto","Left","Right").index(self.config.touchpad_hand));options.addWidget(self.hand_choice)
        self.scroll_speed=QDoubleSpinBox();self.scroll_speed.setRange(4,60);self.scroll_speed.setValue(self.config.touchpad_scroll_speed);self.scroll_speed.setPrefix("Scroll × ");options.addWidget(self.scroll_speed)
        self.natural_scroll=QCheckBox("Reverse scrolling");self.natural_scroll.setChecked(self.config.touchpad_natural_scroll);options.addWidget(self.natural_scroll)
        self.background_touchpad=QCheckBox("Keep running when minimized");self.background_touchpad.setChecked(self.config.touchpad_background);options.addWidget(self.background_touchpad)
        self.pause_button=self.button("Pause / resume · Ctrl+Alt+M",self.toggle_touchpad);options.addWidget(self.pause_button);options.addStretch();layout.addWidget(self.touchpad_panel)
        self.submode_panel=QWidget();sub=QHBoxLayout(self.submode_panel);sub.setContentsMargins(0,0,0,0)
        self.submode_choice=QComboBox();self.submode_choice.addItems(["Touchpad: desktop","Touchpad: gaming","Touchpad: drawing tablet"])
        self.submode_choice.setCurrentIndex(("desktop","gaming","drawing").index(self.config.touchpad_submode));sub.addWidget(self.submode_choice)
        self.drawing_speed=QDoubleSpinBox();self.drawing_speed.setRange(.2,3);self.drawing_speed.setSingleStep(.1);self.drawing_speed.setValue(self.config.drawing_sensitivity);self.drawing_speed.setPrefix("Drawing speed × ");sub.addWidget(self.drawing_speed)
        self.gaming_radius=QDoubleSpinBox();self.gaming_radius.setRange(.12,.6);self.gaming_radius.setSingleStep(.02);self.gaming_radius.setValue(self.config.gaming_radius);self.gaming_radius.setPrefix("Joystick travel × palm ");sub.addWidget(self.gaming_radius)
        self.gaming_display=QCheckBox("Show WASD status over other apps");self.gaming_display.setChecked(self.config.gaming_hud);sub.addWidget(self.gaming_display)
        self.drawing_helper=QCheckBox("Left hand clicks / right hand draws");self.drawing_helper.setChecked(self.config.drawing_two_hand);sub.addWidget(self.drawing_helper)
        sub.addStretch();layout.addWidget(self.submode_panel)
        self.swipe_panel=QWidget();swipes=QHBoxLayout(self.swipe_panel);swipes.setContentsMargins(0,0,0,0)
        self.swipe_enabled=QCheckBox("Enable window swipes");self.swipe_enabled.setChecked(self.config.touchpad_swipe_enabled);swipes.addWidget(self.swipe_enabled)
        self.swipe_enabled.setToolTip("Use your right hand: open the fingers and sweep as shown in your Next/Previous videos. Mirroring is corrected automatically. No fist hold or pointing-pose unlock. Uncheck anytime to disable; your choice is saved.")
        self.swipe_sensitivity=QDoubleSpinBox();self.swipe_sensitivity.setRange(.5,2);self.swipe_sensitivity.setSingleStep(.1);self.swipe_sensitivity.setValue(self.config.touchpad_swipe_sensitivity);self.swipe_sensitivity.setPrefix("Swipe sensitivity × ");swipes.addWidget(self.swipe_sensitivity)
        self.swipe_sensitivity.setToolTip("Higher sensitivity needs less whole-hand travel, with a minimum floor. Use the open right-hand sweeps in your Next/Previous videos. Pointing fingers, three-finger scrolling and finger-only movement do not start swipes.")
        self.swipe_cooldown=QDoubleSpinBox();self.swipe_cooldown.setRange(.4,3);self.swipe_cooldown.setSingleStep(.1);self.swipe_cooldown.setValue(self.config.touchpad_swipe_cooldown);self.swipe_cooldown.setPrefix("Swipe cooldown ");self.swipe_cooldown.setSuffix(" s");swipes.addWidget(self.swipe_cooldown)
        swipes.addStretch();layout.addWidget(self.swipe_panel)
        self.wispr_panel=QWidget();flow=QHBoxLayout(self.wispr_panel);flow.setContentsMargins(0,0,0,0)
        self.wispr_enabled=QCheckBox("Rock starts / swag stops Wispr");self.wispr_enabled.setChecked(self.config.wispr_enabled);flow.addWidget(self.wispr_enabled)
        self.wispr_enabled.setToolTip("Start: index + pinky raised, middle/ring folded, thumb tucked. Relax or remove your hand while talking. Stop: index + pinky + thumb extended with that SAME hand. Desktop only. Escape cancels.")
        self.wispr_mode=QComboBox();self.wispr_mode.addItems(["Ctrl+Win: press to start/stop","Ctrl+Win: hold to talk","Ctrl+Win+Space: start/stop"])
        self.wispr_mode.setCurrentIndex(("toggle_ctrl_win","hold_ctrl_win","toggle_ctrl_win_space").index(self.config.wispr_shortcut_mode));flow.addWidget(self.wispr_mode)
        self.guide_button=self.button("Open gesture guide",self.open_touchpad_guide);flow.addWidget(self.guide_button);flow.addStretch();layout.addWidget(self.wispr_panel)
        for signal in (self.hand_choice.currentIndexChanged,self.scroll_speed.valueChanged,self.natural_scroll.toggled,self.background_touchpad.toggled,self.wispr_enabled.toggled,self.wispr_mode.currentIndexChanged):signal.connect(self.update_touchpad_options)
        for signal in (self.submode_choice.currentIndexChanged,self.drawing_speed.valueChanged,self.gaming_radius.valueChanged,self.gaming_display.toggled,self.drawing_helper.toggled):signal.connect(self.update_touchpad_options)
        self.swipe_enabled.toggled.connect(self.set_window_swipes)
        for signal in (self.swipe_sensitivity.valueChanged,self.swipe_cooldown.valueChanged):signal.connect(self.update_touchpad_options)
        self.mode_choice.currentIndexChanged.connect(self.change_mode)
        self.mode_note=QLabel(); self.mode_note.setWordWrap(True); self.mode_note.setObjectName("hint")
        layout.addWidget(self.mode_note)

    def set_touchpad_speed(self,value):
        self.config=replace(self.config,touchpad_sensitivity=value)
        if self.hand_mouse:self.hand_mouse.config=self.config
        if self.touchpad_session:self.touchpad_session.config=self.config
        self.save_touchpad_preferences()

    def set_window_swipes(self,enabled):
        self.config=replace(self.config,touchpad_swipe_enabled=enabled)
        if self.hand_mouse:self.hand_mouse.config=self.config
        if self.touchpad_session:
            self.touchpad_session.config=self.config
            self.touchpad_session.swipe.reset()
        self.save_touchpad_preferences()
        self.refresh_controls()

    def update_touchpad_options(self,*args):
        self.stop_pointer()
        self.config=replace(self.config,touchpad_hand=("auto","Left","Right")[self.hand_choice.currentIndex()],touchpad_scroll_speed=self.scroll_speed.value(),touchpad_natural_scroll=self.natural_scroll.isChecked(),touchpad_background=self.background_touchpad.isChecked(),wispr_enabled=self.wispr_enabled.isChecked(),wispr_shortcut_mode=("toggle_ctrl_win","hold_ctrl_win","toggle_ctrl_win_space")[self.wispr_mode.currentIndex()])
        self.config=replace(self.config,touchpad_submode=("desktop","gaming","drawing")[self.submode_choice.currentIndex()],drawing_sensitivity=self.drawing_speed.value(),gaming_radius=self.gaming_radius.value(),gaming_hud=self.gaming_display.isChecked(),drawing_two_hand=self.drawing_helper.isChecked())
        self.config=replace(self.config,touchpad_swipe_enabled=self.swipe_enabled.isChecked(),touchpad_swipe_sensitivity=self.swipe_sensitivity.value(),touchpad_swipe_cooldown=self.swipe_cooldown.value())
        if self.hand_mouse:self.hand_mouse.config=self.config
        if self.touchpad_session:self.touchpad_session.config=self.config
        self.set_state(State.READY if self.worker else State.CAMERA_OFF)
        if self.mode=="hand_mouse":
            self.hint.setText({"desktop":"Start camera, then enable the mouse and open both pinches.","gaming":"Start camera, enable gaming controls and focus your game. Hold your left palm still to center; right hand controls the mouse. WASD feedback stays visible over the game.","drawing":"Start camera, enable drawing controls and focus your drawing app. Index + middle: hover. Thumb/index pinch: click. Index only with thumb away: draw."}[self.config.touchpad_submode])
        self.save_touchpad_preferences()

    def save_touchpad_preferences(self):
        if not getattr(self,"persist_preferences",False):return
        from .config import save_preferences
        keys=("touchpad_sensitivity","touchpad_hand","touchpad_submode","touchpad_swipe_enabled","touchpad_swipe_sensitivity","touchpad_swipe_cooldown","drawing_sensitivity","drawing_two_hand","gaming_radius","gaming_hud","touchpad_scroll_speed","touchpad_natural_scroll","touchpad_background","wispr_enabled","wispr_shortcut_mode")
        try:save_preferences({key:getattr(self.config,key) for key in keys})
        except (OSError,ValueError):self.show_error("Could not save touchpad preferences. Current-session controls still use your choices.")

    def open_touchpad_guide(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        from .config import ROOT
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(ROOT/"docs/GESTURE_GUIDE.html")))

    def install_desktop_controls(self):
        from .desktop_hotkey import DesktopHotkey
        try:
            self.desktop_hotkey=DesktopHotkey(self);self.desktop_hotkey.activated.connect(self.toggle_touchpad)
        except InjectionError as exc:self.show_error(str(exc))
        if QSystemTrayIcon.isSystemTrayAvailable():
            pix=QPixmap(32,32);pix.fill(QColor("transparent"));p=QPainter(pix);p.setPen(QPen(QColor("#087f71"),3));p.drawLine(9,5,9,26);p.drawLine(9,5,25,21);p.drawLine(9,26,16,20);p.end()
            self.tray=QSystemTrayIcon(QIcon(pix),self);menu=QMenu(self)
            menu.addAction("Pause / resume · Ctrl+Alt+M",self.toggle_touchpad)
            menu.addAction("Show SlateInk",lambda:self.showNormal())
            menu.addAction("Stop camera and controls",self.emergency_stop);menu.addAction("Quit",self.close)
            self.tray.setContextMenu(menu);self.tray.activated.connect(lambda reason:self.showNormal() if reason==QSystemTrayIcon.ActivationReason.DoubleClick else None)

    def can_background_touchpad(self):
        indicator=self.tray is not None or self.can_background_camera_preview()
        return self.mode=="hand_mouse" and self.config.touchpad_background and indicator and self.hand_mouse is not None and self.hand_mouse.enabled

    def toggle_touchpad(self):
        if self.state in {State.PROCESSING,State.TYPING}:return
        if self.mode=="hand_mouse" and self.hand_mouse and self.hand_mouse.enabled:
            try:self.hint.setText(self.touchpad_session.toggle_pause())
            except InjectionError as exc:self.stop_pointer();self.show_error(str(exc))
            self.refresh_controls();return
        if self.mode!="hand_mouse":self.mode_choice.setCurrentIndex(1)
        self.arm_touchpad_when_ready=True
        if self.worker is None:self.start_camera()

    def set_unverified_gaze(self,value):
        self.stop_pointer();self.config=replace(self.config,gaze_allow_unverified=value)
        if hasattr(self,"status_label"):
            if self.state==State.GAZE:self.set_state(State.READY)
            self.refresh_controls()

    def refresh_modes(self,busy,stopping):
        if not hasattr(self,"mode_choice"):return
        mouse_active=bool(self.hand_mouse is not None and self.hand_mouse.enabled)
        gaze=self.mode=="eye_gaze";gaze_active=bool(self.gaze_controller and self.gaze_controller.enabled)
        self.mode_choice.setEnabled(not busy and not stopping and self.recognition_worker is None and self.gaze_dialog is None)
        paper=self.mode=="paper"; hand=self.mode=="hand_mouse"; pen=self.mode=="pen_pointer"; finger=self.mode=="finger_letters"
        drawing=hand and self.config.touchpad_submode=="drawing";gaming=hand and self.config.touchpad_submode=="gaming";desktop=hand and not drawing and not gaming
        self.touchpad_panel.setVisible(hand);self.wispr_panel.setVisible(hand);self.submode_panel.setVisible(hand)
        self.swipe_panel.setVisible(desktop)
        self.wispr_enabled.setVisible(desktop);self.wispr_mode.setVisible(desktop)
        self.drawing_speed.setVisible(drawing);self.gaming_radius.setVisible(gaming)
        self.drawing_helper.setVisible(drawing);self.gaming_display.setVisible(gaming)
        self.hand_choice.setVisible(not gaming and not (drawing and self.config.drawing_two_hand));self.scroll_speed.setVisible(not drawing);self.natural_scroll.setVisible(not drawing)
        self.camera_heading.setText("Camera / hand tracking" if hand else ("Camera / eye tracking" if gaze else "Camera / writing area"))
        self.pause_button.setEnabled(not busy and not stopping)
        self.swipe_enabled.setEnabled(desktop and not busy and not stopping)
        for option in (self.hand_choice,self.submode_choice,self.drawing_speed,self.drawing_helper,self.gaming_radius,self.gaming_display,self.scroll_speed,self.natural_scroll,self.background_touchpad,self.wispr_enabled,self.wispr_mode,self.swipe_sensitivity,self.swipe_cooldown):option.setEnabled(not mouse_active and self.pointer_deadline is None and not busy)
        self.dark_slate.setVisible(paper); self.ocr_variant.setVisible(paper)
        self.ocr_device.setVisible(paper);self.ocr_device.setEnabled(not busy and self.recognition_worker is None)
        self.sensitivity.setVisible(hand and not drawing);self.sensitivity.setEnabled(not mouse_active and self.pointer_deadline is None)
        self.dark_slate.setEnabled(not busy); self.ocr_variant.setEnabled(not busy)
        self.right_click.setVisible((hand and not drawing) or gaze); self.right_click.setEnabled(not mouse_active and not gaze_active and self.pointer_deadline is None)
        self.unverified_gaze.setVisible(gaze);self.unverified_gaze.setEnabled(not busy and not stopping and self.gaze_dialog is None)
        self.pointer_button.setVisible(hand or pen or gaze)
        active=mouse_active or gaze_active or self.pen_pointer_enabled or self.pointer_deadline is not None
        if hand and mouse_active and self.touchpad_session:self.status_label.setText("HAND TOUCHPAD PAUSED" if self.touchpad_session.paused else ("WISPR LISTENING" if self.touchpad_session.dictating else "HAND TOUCHPAD ACTIVE"))
        if hand and mouse_active and not self.touchpad_session.paused and not desktop:self.status_label.setText("GAMING ACTIVE" if gaming else "DRAWING ACTIVE")
        if gaming and mouse_active and self.config.gaming_hud:
            if self.game_hud is None:
                from .widgets import GamingStatusOverlay
                self.game_hud=GamingStatusOverlay()
            self.game_hud.set_status(self.touchpad_session.gaming.wanted,self.hint.text(),self.touchpad_session.paused)
            if not self.game_hud.isVisible():self.game_hud.show()
        elif self.game_hud:self.game_hud.hide()
        if self.tray:
            camera_on=self.worker is not None
            self.tray.setToolTip("SlateInk · camera ON · "+self.status_label.text() if camera_on else "SlateInk · camera OFF")
            self.tray.setVisible(camera_on)
        self.pointer_button.setText("Disable controls / release input" if active else ("Enable pen hover pointer" if pen else ("Enable gaming controls" if gaming else ("Enable drawing controls" if drawing else "Enable desktop mouse"))))
        gaze_ready=self.gaze_calibration.weights is not None and (self.gaze_calibration.validated or self.unverified_gaze.isChecked())
        ready=hand or (pen and self.controller.surface is not None and self.pen_marker.hue is not None) or (gaze and gaze_ready and self.gaze_dialog is None)
        self.pointer_button.setEnabled(not busy and not stopping and self.mouse_sink is not None and self.worker is not None and (active or ready))
        self.pen_select_button.setVisible(pen)
        self.pen_select_button.setEnabled(not busy and self.latest_rgb is not None and not active)
        for widget in (self.letter_panel,self.undo_button,self.clear_button,self.capture_button):widget.setVisible(finger)
        self.submit_button.setVisible(paper or finger); self.retry_button.setVisible(finger)
        self.recognition_heading.setVisible(paper or finger)
        for widget in (self.preview,self.space_button,self.backspace_button,self.text_note,self.accept_button,self.delay,self.delay_label,self.discard_button):widget.setVisible(paper or finger)
        self.score_label.setVisible(paper or finger or gaze)
        if gaze:
            self.score_label.setText(self.gaze_report_text(gaze_active))
            if gaze_active:self.status_label.setText("GAZE ACTIVE — ACCURACY UNVERIFIED" if self.gaze_controller.unverified else State.GAZE.value)
        if paper:
            self.submit_button.setText("Capture writing & recognize")
            self.submit_button.setEnabled(not busy and self.recognition_worker is None and self.worker is not None and self.latest_rgb is not None and self.controller.surface is not None and not stopping)
        elif finger:self.submit_button.setText("Recognize letter  ·  Ctrl+Enter")
        self.calibrate_button.setVisible(not hand)
        self.calibrate_button.setText("Calibrate eyes & check accuracy" if gaze else ("Select writing area" if paper else ("Calibrate pointer area" if pen else "Calibrate slate")))
        messages={
            "paper":"Write with real ink on paper or a visible slate. Select the writing area; remove your hand/pen, capture it, review the text, then explicitly send it. Camera images stay local.",
            "hand_mouse":"Joined index + middle: point. Three fingers: scroll. Index pinch: click/select/drag; two pinches: double-click. Middle pinch: right-click. Windows: open your RIGHT hand and sweep as in Next/Previous videos; mirror correction is automatic. Relax fingers to point again. Helper open palm: precision; both open palms: pause/resume. Wispr: index + pinky (rock sign, thumb tucked) starts; relax while talking, then index + pinky + thumb (swag sign) with the SAME hand finishes. Escape stops everything.",
            "eye_gaze":"Local eye control: calibrate the nine-dot screen mapping. Allow unverified gaze lets you enable desktop control even if accuracy checks fail; pointing may be inaccurate. Look to point, index pinch left-clicks, middle pinch right-clicks. Escape stops and releases buttons.",
            "pen_pointer":"Experimental hover tracking requires a bright colored marker near the pen tip. Webcam-only touch/hover is not verified: this mode moves the cursor and NEVER clicks.",
            "finger_letters":"Experimental: reported inaccurate on your handwriting. Letter capture is retained for testing; use paper/slate OCR for actual ink."}
        self.mode_note.setText(messages[self.mode])
        if gaming:self.mode_note.setText("Right hand: existing mouse gestures. Hold the left palm still briefly with at least three fingers extended to center; move forward W, left A, back S, right D. Center stops; fist stops/recenters. Ctrl+Alt+M pauses/resumes. The WASD status display stays visible over your game. Escape releases all input.")
        if drawing:self.mode_note.setText("Index + middle: hover and arm. Thumb + index pinch/release: click tools at the current cursor; keep middle extended. Index only with thumb away: draw without pinching. Raise middle to lift; fold fingers to reposition. Equal drawing scale in every direction. Escape stops capture.")
        if drawing and self.config.drawing_two_hand:self.mode_note.setText("Right hand: index + middle hovers; index only draws. Left hand: thumb/index pinch clicks; keep another finger extended. Clicks lift ink and freeze the cursor, then right index + middle returns to hover. Drawing speed and smoothing use only the right fingertip. Escape stops capture.")
        self.ink_heading.setText({"paper":"Captured paper / slate writing","hand_mouse":"Touchpad status","pen_pointer":"Pen marker preview — no contact clicks","finger_letters":"Virtual ink / one letter at a time","eye_gaze":"Gaze preview — calibration required"}[self.mode])
        self.text_note.setText("Ink clears after Add letter; collected text stays." if finger else "Review captured text before sending; repeated captures replace the preview.")
        self.preview.setPlaceholderText("Collected letters — review/edit before sending." if finger else "Recognized paper/slate text appears here. Review and correct before sending.")
        self.ink_view.show_guides=finger
        self.ink_view.empty_message={"paper":"Captured writing appears here","hand_mouse":"Relative touchpad — no area calibration needed","pen_pointer":"Pen marker preview — automatic clicks disabled","finger_letters":"Write one letter here","eye_gaze":"Calibrate the nine-dot mapping, then enable desktop control"}[self.mode]
        if gaming:self.ink_view.empty_message="Left palm: forward W · left A · back S · right D\nRight hand: mouse · fist: stop/recenter"
        if drawing:self.ink_view.empty_message="Index only: ink · index + middle: hover\nThumb + index pinch: click a tool"
        self.footer.setText("Local processing · calibration stays in memory · desktop controls start OFF · Escape stops capture and releases buttons" if hand or pen or gaze else "Local writing · preview before typing · no cloud or clipboard · Escape stops capture and pending typing")

    def stop_pointer(self):
        if self.game_hud:self.game_hud.hide()
        self.pointer_deadline=None; self.pen_pointer_enabled=False
        self.pen_filter.reset()
        if self.touchpad_session:
            try:self.touchpad_session.set_enabled(False)
            except InjectionError as exc:
                if hasattr(self,"error_label"):self.show_error(str(exc))
        if self.hand_mouse is not None:
            try:self.hand_mouse.set_enabled(False)
            except InjectionError as exc:
                if hasattr(self,"error_label"):self.show_error(str(exc))
        if self.gaze_controller:
            try:self.gaze_controller.set_enabled(False)
            except InjectionError as exc:
                if hasattr(self,"error_label"):self.show_error(str(exc))

    def reset_gaze(self):
        self.stop_pointer()
        if self.gaze_dialog:self.gaze_dialog.reject()
        self.gaze_calibration.clear()
        if self.gaze_controller:self.gaze_controller.calibration=self.gaze_calibration
        self.camera_view.eye_centers=()

    def begin_gaze_calibration(self):
        if self.worker is None or self.gaze_dialog is not None:return
        self.stop_pointer();self.gaze_calibration.clear()
        self.gaze_dialog=GazeCalibrationDialog(self)
        self.gaze_dialog.completed.connect(self.gaze_calibrated)
        self.gaze_dialog.unverified_requested.connect(self.gaze_unverified_requested)
        self.gaze_dialog.finished.connect(self.gaze_calibration_closed)
        self.gaze_dialog.show();self.gaze_dialog.activateWindow();self.gaze_dialog.setFocus()
        self.refresh_controls()

    def gaze_calibrated(self,calibration):
        self.gaze_calibration=calibration
        if self.gaze_controller:
            self.gaze_controller.calibration=calibration
            screen=QApplication.primaryScreen().geometry();desktop=screen
            for item in QApplication.screens():desktop=desktop.united(item.geometry())
            self.gaze_controller.screen_rect=((screen.x()-desktop.x())/desktop.width(),(screen.y()-desktop.y())/desktop.height(),screen.width()/desktop.width(),screen.height()/desktop.height())
        self.score_label.setText(self.gaze_report_text())

    def gaze_report_text(self,active=False):
        report=self.gaze_calibration.report
        if not report:return "Calibrate the nine-dot screen mapping. Desktop control is OFF."
        metrics=f" · median {report['median_error_px']:.0f}px · p90 {report['p90_error_px']:.0f}px" if report.get("median_error_px") is not None else ""
        choice=" · ACCURACY UNVERIFIED — control allowed" if not report["passed"] and self.unverified_gaze.isChecked() and self.gaze_calibration.weights is not None else ""
        return f"Eye accuracy check: {'passed' if report['passed'] else 'not passed'}{metrics}{choice} · desktop control {'ON' if active else 'OFF'}"

    def gaze_unverified_requested(self,calibration):
        self.gaze_calibrated(calibration);self.unverified_gaze.setChecked(True)

    def gaze_calibration_closed(self,result):
        old=self.gaze_dialog;self.gaze_dialog=None
        if old:old.deleteLater()
        self.refresh_controls()

    def change_mode(self):
        if self.state in {State.PROCESSING,State.TYPING} or self.recognition_worker is not None or self.send_worker is not None:return
        self.stop_pointer(); self.mode=MODES[self.mode_choice.currentIndex()]
        self.config=replace(self.config,initial_mode=self.mode,
                            camera_width=1280 if self.mode=="paper" else 640,
                            camera_height=720 if self.mode=="paper" else 480)
        self.controller.set_enabled(False); self.controller.clear(); self.invalidate_result()
        self.pen_marker.reset(); self.camera_view.selecting_pen=False
        self.ink_view.set_image(None); self.latest_rgb=None
        self.restart_after_orientation=self.worker is not None
        self.stop_camera(preserve_state=True)
        self.set_state(State.READY if self.restart_after_orientation else State.CAMERA_OFF)
        self.hint.setText("Controls are off. Join index + middle, then enable the touchpad; no area calibration is needed." if self.mode=="hand_mouse" else ("Face the webcam and calibrate the nine-dot mapping. Allow unverified gaze permits desktop control without passing the accuracy check." if self.mode=="eye_gaze" else "Mode changed. Controls are off; select/calibrate the area again. Collected text is kept."))

    def toggle_pointer(self):
        if self.pointer_deadline is not None or self.pen_pointer_enabled or (self.hand_mouse is not None and self.hand_mouse.enabled) or (self.gaze_controller and self.gaze_controller.enabled):
            self.stop_pointer(); self.set_state(State.READY); return
        if not self.pointer_button.isEnabled():return
        self.controller.set_enabled(False)
        self.hand_mouse.surface=self.controller.surface
        self.hand_mouse.right_enabled=self.right_click.isChecked()
        if self.gaze_controller:self.gaze_controller.right_enabled=self.right_click.isChecked()
        self.pointer_deadline=time.monotonic()+3
        self.hint.setText("Pointer starts in 3 seconds. Position your hand/pen; open both pinches. Escape cancels.")
        self.refresh_controls()

    def pointer_tick(self,now):
        if self.pointer_deadline is not None:
            remaining=self.pointer_deadline-now
            self.hint.setText(f"Pointer starts in {max(0,int(remaining)+1)} s. Escape cancels.")
            if remaining<=0:
                self.pointer_deadline=None
                background_arm=self.mode=="hand_mouse" and self.config.touchpad_background and self.tray is not None
                if self.worker is None or (self.isMinimized() and not background_arm) or (self.mode=="pen_pointer" and self.controller.surface is None):
                    self.stop_pointer(); return
                try:
                    if self.mode=="hand_mouse":
                        self.touchpad_session.controller=self.hand_mouse;self.touchpad_session.config=self.config
                        self.touchpad_session.set_enabled(True);self.set_state(State.MOUSE)
                    elif self.mode=="pen_pointer":self.pen_pointer_enabled=True; self.set_state(State.PEN)
                    elif self.mode=="eye_gaze":
                        self.gaze_controller.set_enabled(True,allow_unverified=self.unverified_gaze.isChecked())
                        if self.gaze_controller.enabled:self.set_state(State.GAZE)
                except InjectionError as exc:self.stop_pointer(); self.show_error(str(exc))

    def select_pen(self):
        if not self.pen_select_button.isEnabled():return
        self.stop_pointer(); self.camera_view.selecting_pen=True; self.camera_view.calibrating=False
        self.hint.setText("Click a bright colored marker near your pen tip. Plain black tips are not supported reliably.")

    def set_pen_marker(self,x,y):
        if not self.camera_view.selecting_pen or self.latest_rgb is None:return
        try:
            self.pen_marker.select(self.latest_rgb,x,y); self.camera_view.selecting_pen=False
            self.hint.setText("Marker selected. Calibrate the pointer area, then enable hover control. Pen contact will not click.")
        except ValueError as exc:self.show_error(str(exc))
        self.refresh_controls()

    def process_mode_packet(self,packet,now):
        self.latest_rgb=packet.rgb; self.latest_frame_at=packet.t; self.latest_hand_count=packet.hand_count
        if self.arm_touchpad_when_ready and self.mode=="hand_mouse" and now-packet.t<=.2:
            self.arm_touchpad_when_ready=False;self.refresh_controls();self.toggle_pointer()
        if self.mode=="hand_mouse" and self.hand_mouse.enabled:
            try:
                self.touchpad_session.controller=self.hand_mouse;self.touchpad_session.config=self.config
                hands=packet.hands or ((packet.hand,) if packet.hand is not None else ())
                message=self.touchpad_session.process(hands,packet.t,now-packet.t,packet.rgb.shape[1]/packet.rgb.shape[0])
                self.hint.setText(message)
                self.camera_view.hand=self.touchpad_session.primary
            except InjectionError as exc:self.stop_pointer(); self.show_error(str(exc)); self.set_state(State.READY)
        elif self.mode=="eye_gaze":
            self.camera_view.eye_centers=packet.eye.iris_centers if packet.eye and packet.eye.valid else ()
            if self.gaze_dialog:self.gaze_dialog.observe(packet.eye,packet.t,packet.rgb,packet.eye_count)
            elif self.gaze_controller:
                try:
                    self.hint.setText(self.gaze_controller.process(packet.eye,packet.hand,packet.t,now-packet.t,packet.rgb.shape[1]/packet.rgb.shape[0]))
                    self.controller.cursor=self.gaze_controller.gaze
                except InjectionError as exc:self.stop_pointer();self.show_error(str(exc));self.set_state(State.READY)
        elif self.mode=="pen_pointer":
            point=self.pen_marker.detect(packet.rgb,packet.t) if now-packet.t<=0.2 else None
            self.camera_view.pen_point=point
            if point is not None and self.controller.surface is not None:
                mapped=self.controller.surface.map_point(point); self.controller.cursor=mapped
                if self.pen_pointer_enabled and mapped is not None:
                    try:self.mouse_sink.move(*self.pen_filter.update(mapped,packet.t))
                    except InjectionError as exc:self.stop_pointer(); self.show_error(str(exc))
            else:
                self.pen_filter.reset(); self.controller.cursor=None
                if self.pen_pointer_enabled:self.hint.setText("Pen marker missing/ambiguous. Cursor paused; no click or drag is held.")

    def submit_paper(self):
        if self.mode!="paper" or not self.submit_button.isEnabled():return
        if self.latest_frame_at is None or time.monotonic()-self.latest_frame_at>0.25:
            self.show_error("Camera frame is stale. Wait for live video before capture.");return
        # A visible tracked hand inside the selected writing area can cover ink.
        hand=self.camera_view.hand
        if self.latest_hand_count>1:
            self.show_error("Move both hands out of the writing area before capture.");return
        if hand is not None and any(self.controller.surface.map_point(p[:2]) is not None for p in hand.landmarks):
            self.show_error("Move your hand and pen out of the writing area, then capture the writing.");return
        self.stop_pointer(); self.controller.set_enabled(False)
        try:image=warp_paper(self.latest_rgb,self.controller.surface,self.config.camera_mirrored)
        except ValueError as exc:self.show_error(str(exc));return
        self.ink_view.set_image(image); self.error_label.hide(); self.pending_letter=None
        variant="medium" if self.ocr_variant.currentIndex()==0 else "english"
        device=("auto","cpu","cuda")[self.ocr_device.currentIndex()]
        existing=self.paper_recognizer if self.paper_recognizer is not None and self.paper_recognizer.variant==variant and self.paper_recognizer.requested_device==device else None
        self.recognition_kind="paper"
        self.recognition_worker=PaperWorker(image,self.dark_slate.isChecked(),variant,existing,device)
        self.recognition_worker.ready.connect(self.recognized)
        self.recognition_worker.failed.connect(self.recognition_failed)
        self.recognition_worker.finished.connect(self.recognition_finished)
        self.set_state(State.PROCESSING)
        self.hint.setText("Loading local OCR — the first balanced GPU capture can take about 35 seconds; later captures reuse the model. Nothing is sent automatically." if existing is None else "Reading actual writing locally. Preview will replace the previous paper result; no text is sent automatically.")
        self.recognition_worker.start()

    def recognized_paper(self,result):
        self.last_recognition=result; self.pending_letter=None
        self.preview.setPlainText(result.text)
        score=f"{result.score:.0%}" if result.score is not None else "unavailable"
        self.score_label.setText(f"Paper OCR score: {score} (uncalibrated) · {result.latency_seconds:.2f} s · {result.device} · Review required")
        if result.score is None or result.score<self.config.low_score_threshold:
            self.show_error("Low OCR score. Check/edit the recognized writing before sending.")
        self.set_state(State.PREVIEW)
        self.hint.setText("Review and correct this snapshot's text, then Type collected text. Nothing is sent without acceptance.")
