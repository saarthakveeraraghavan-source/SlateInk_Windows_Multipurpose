"""Small non-activating camera monitor, shared with the main camera view."""
from dataclasses import replace
import time
from PySide6.QtCore import Qt,Signal,QPoint
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget,QHBoxLayout,QVBoxLayout,QLabel,QToolButton,QApplication
from .widgets import CameraView


class DragBar(QWidget):
    def __init__(self,overlay):
        super().__init__(overlay);self.overlay=overlay;self.anchor=None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.anchor=event.globalPosition().toPoint()-self.overlay.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor);event.accept()

    def mouseMoveEvent(self,event):
        if self.anchor is not None and event.buttons()&Qt.MouseButton.LeftButton:
            self.overlay.move(event.globalPosition().toPoint()-self.anchor);event.accept()

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.anchor is not None:
            self.anchor=None;self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.overlay.keep_on_screen();self.overlay.moved.emit(self.overlay.x(),self.overlay.y());event.accept()


class CameraPreview(QWidget):
    dismissed=Signal()
    moved=Signal(int,int)

    def __init__(self,x=None,y=None):
        flags=Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.WindowDoesNotAcceptFocus
        super().__init__(None,flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose,False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setWindowTitle("SlateInk floating camera")
        self.setObjectName("cameraPreview")
        self.setStyleSheet("#cameraPreview {background:#142c3d;border:1px solid #496075;} QLabel {color:#e8ffff;background:transparent;font-size:12px;} QToolButton {background:transparent;color:#e8ffff;border:0;font-size:18px;}")
        layout=QVBoxLayout(self);layout.setContentsMargins(1,1,1,1);layout.setSpacing(0)
        self.bar=DragBar(self);row=QHBoxLayout(self.bar);row.setContentsMargins(8,2,5,2)
        self.status=QLabel("Camera starting · drag here")
        self.status.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row.addWidget(self.status,1)
        self.hide_button=QToolButton();self.hide_button.setText("×");self.hide_button.setToolTip("Hide floating camera preview")
        self.hide_button.setFocusPolicy(Qt.FocusPolicy.NoFocus);self.hide_button.clicked.connect(self.dismissed)
        row.addWidget(self.hide_button);layout.addWidget(self.bar)
        self.view=CameraView();self.view.setMinimumSize(1,1);layout.addWidget(self.view,1)
        self.setFixedSize(288,248);self.last_paint=0
        if x is None:
            bounds=QApplication.primaryScreen().availableGeometry();x=bounds.right()-self.width()-16;y=bounds.top()+64
        self.move(x,y);self.keep_on_screen()

    def keep_on_screen(self):
        screens=QApplication.screens()
        if not screens:return
        rect=self.frameGeometry()
        screen=max(screens,key=lambda s:s.availableGeometry().intersected(rect).width()*max(0,s.availableGeometry().intersected(rect).height()))
        bounds=screen.availableGeometry()
        self.move(max(bounds.left(),min(self.x(),bounds.right()-self.width()+1)),
                  max(bounds.top(),min(self.y(),bounds.bottom()-self.height()+1)))

    def show_frame(self,source,frame_time,now):
        if source.image is None or frame_time is None or now-frame_time>.35:
            self.view.clear();self.status.setText("Waiting for camera · drag here");return
        if self.view.image is not None and now-self.last_paint<1/15:return
        self.last_paint=now
        height=max(90,min(288,round(286*source.image.height()/source.image.width())))
        if self.height()!=height+32:self.setFixedHeight(height+32);self.keep_on_screen()
        # QImage is implicitly shared. No second capture, pixel copy or inference.
        self.view.image=QImage(source.image);self.view.hand=source.hand
        self.view.corners=list(source.corners);self.view.pen_point=source.pen_point
        self.view.eye_centers=source.eye_centers;self.view.update()
        self.status.setText("Camera LIVE · drag here")

    def closeEvent(self,event):
        self.dismissed.emit();event.ignore()


class CameraPreviewMixin:
    def set_camera_preview(self,enabled):
        self.config=replace(self.config,camera_preview_enabled=enabled)
        self.save_camera_preview_preferences();self.sync_camera_preview()
        if self.isMinimized() and not enabled and not self.can_background_touchpad():self.emergency_stop()

    def save_camera_preview_preferences(self):
        if not self.persist_preferences:return
        from .config import save_preferences
        try:save_preferences({k:getattr(self.config,k) for k in ("camera_preview_enabled","camera_preview_x","camera_preview_y")})
        except (OSError,ValueError):self.show_error("Could not save floating camera preferences. The current preview still works.")

    def camera_preview_moved(self,x,y):
        self.config=replace(self.config,camera_preview_x=x,camera_preview_y=y)
        self.save_camera_preview_preferences()

    def sync_camera_preview(self):
        preview=getattr(self,"camera_preview",None)
        playground=getattr(self,"fun_window",None)
        active=self.config.camera_preview_enabled and self.worker is not None and not self.worker.stop_event.is_set() and not self.closing and not (playground and playground.isVisible())
        if not active:
            if preview:preview.view.clear();preview.hide()
            return
        if preview is None:
            preview=self.camera_preview=CameraPreview(self.config.camera_preview_x,self.config.camera_preview_y)
            preview.dismissed.connect(lambda:self.camera_preview_choice.setChecked(False))
            preview.moved.connect(self.camera_preview_moved)
        preview.show_frame(self.camera_view,self.latest_frame_at,time.monotonic())
        session=getattr(self,"touchpad_session",None)
        if session and session.dictating:
            right="Left" if self.config.camera_mirrored else "Right"
            owner="RIGHT" if session.voice_hand==right else "LEFT"
            preview.status.setText(f"Wispr · {owner} swag sign stops")
        if not preview.isVisible():preview.show()

    def can_background_camera_preview(self):
        preview=getattr(self,"camera_preview",None)
        return bool(self.config.camera_preview_enabled and preview and preview.isVisible() and self.worker and not self.worker.stop_event.is_set())

    def handle_background_window(self):
        if self.can_background_touchpad():return
        if self.can_background_camera_preview():
            self.cancel_pending();self.stop_pointer();self.controller.set_enabled(False)
        else:self.emergency_stop()
