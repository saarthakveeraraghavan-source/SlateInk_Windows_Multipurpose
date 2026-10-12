import numpy as np
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QFont
from PySide6.QtWidgets import QWidget,QLabel,QVBoxLayout,QApplication


class GamingStatusOverlay(QWidget):
    """Non-activating, click-through key feedback over the destination app."""
    def __init__(self):
        flags=Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.WindowDoesNotAcceptFocus|Qt.WindowType.WindowTransparentForInput
        super().__init__(None,flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose,False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setObjectName("gamingOverlay");self.setStyleSheet("#gamingOverlay {background:#142c3d; border:1px solid #496075; border-radius:8px;} QLabel {color:#e8ffff;background:transparent;font-size:13px;}")
        layout=QVBoxLayout(self);self.keys=QLabel();self.detail=QLabel();self.detail.setWordWrap(True)
        layout.addWidget(self.keys);layout.addWidget(self.detail);layout.addWidget(QLabel("Ctrl+Alt+M: pause / resume · Escape: stop"))
        self.setFixedWidth(380)
        screen=QApplication.primaryScreen()
        if screen:
            bounds=screen.availableGeometry();self.move(bounds.right()-395,bounds.top()+65)

    def set_status(self,held,message,paused=False):
        labels="  ".join(f'<span style="color:{"#4ee0c4" if key in held else "#8899ac"}">{key}</span>' for key in ("W","A","S","D"))
        self.keys.setText(("SlateInk · PAUSED" if paused else "SlateInk · left joystick")+" &nbsp; "+labels)
        self.detail.setText(message.split("  Right mouse:",1)[0]);self.adjustSize()


class CameraView(QWidget):
    corner_clicked = Signal(float, float)
    pen_clicked = Signal(float,float)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(360, 140)
        self.image = None
        self.hand = None
        self.corners = []
        self.calibrating = False
        self.selecting_pen = False
        self.pen_point = None
        self.eye_centers=()
        self.image_rect = QRectF()

    def set_frame(self, rgb, hand):
        h, w, _ = rgb.shape
        self.image = QImage(rgb.data, w, h, int(rgb.strides[0]), QImage.Format.Format_RGB888).copy()
        self.hand = hand
        self.update()

    def clear(self):
        self.image = self.hand = None
        self.pen_point=None
        self.eye_centers=()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#101b27"))
        if self.image is None:
            painter.setPen(QColor("#a8b6c8"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Camera is off\nStart camera when you are ready")
            self.image_rect = QRectF()
            return
        scale = min(self.width()/self.image.width(), self.height()/self.image.height())
        w, h = self.image.width()*scale, self.image.height()*scale
        rect = QRectF((self.width()-w)/2, (self.height()-h)/2, w, h)
        self.image_rect = rect
        painter.drawImage(rect, self.image)
        def xy(point):
            from PySide6.QtCore import QPointF
            return QPointF(rect.x()+point[0]*w, rect.y()+point[1]*h)
        if self.corners:
            painter.setPen(QPen(QColor("#4ee0c4"), 2))
            for i in range(len(self.corners)-1):
                painter.drawLine(xy(self.corners[i]), xy(self.corners[i+1]))
            if len(self.corners) == 4:
                painter.drawLine(xy(self.corners[-1]), xy(self.corners[0]))
            for i, point in enumerate(self.corners):
                p = xy(point)
                painter.setBrush(QColor("#0b252c"))
                painter.drawEllipse(p, 12, 12)
                painter.drawText(QRectF(p.x()-12, p.y()-12, 24, 24), Qt.AlignmentFlag.AlignCenter, str(i+1))
        if self.hand is not None:
            points = self.hand.landmarks
            painter.setPen(QPen(QColor("#c4e5ec"), 1))
            for chain in ((0,1,2,3,4), (0,5,6,7,8), (5,9,10,11,12), (9,13,14,15,16), (13,17,18,19,20),(0,17)):
                for a, b in zip(chain, chain[1:]):
                    painter.drawLine(xy(points[a]), xy(points[b]))
            for index, color in ((4,"#f8ba69"),(8,"#4ee0c4")):
                painter.setPen(QPen(QColor("#fff"), 2))
                painter.setBrush(QColor(color))
                painter.drawEllipse(xy(points[index]), 7, 7)
        if self.calibrating:
            painter.fillRect(QRectF(rect.x(), rect.y(), w, 30), QColor(0, 0, 0, 170))
            painter.setPen(QColor("#fff"))
            label = ("top left", "top right", "bottom right", "bottom left")[min(3, len(self.corners))]
            painter.drawText(QRectF(rect.x()+10, rect.y(), w-20, 30), Qt.AlignmentFlag.AlignVCenter, f"Click corner {len(self.corners)+1}: {label}")
        if self.pen_point is not None:
            painter.setPen(QPen(QColor("#f6c453"),3)); painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(xy(self.pen_point),10,10)
        for point in self.eye_centers:
            painter.setPen(QPen(QColor("#5eb7ff"),2));painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(xy(point),5,5)
        if self.selecting_pen:
            painter.fillRect(QRectF(rect.x(),rect.y(),w,35),QColor(0,0,0,170))
            painter.setPen(QColor("#fff"))
            painter.drawText(QRectF(rect.x()+10,rect.y(),w-20,35),Qt.AlignmentFlag.AlignVCenter,"Click the colored marker near your pen tip")

    def mousePressEvent(self, event):
        p = event.position()
        if self.calibrating and self.image is not None and self.image_rect.contains(p):
            self.corner_clicked.emit((p.x()-self.image_rect.x())/self.image_rect.width(),
                                     (p.y()-self.image_rect.y())/self.image_rect.height())
        elif self.selecting_pen and self.image is not None and self.image_rect.contains(p):
            self.pen_clicked.emit((p.x()-self.image_rect.x())/self.image_rect.width(),
                                  (p.y()-self.image_rect.y())/self.image_rect.height())


class InkView(QWidget):
    def __init__(self, controller, config):
        super().__init__()
        self.controller, self.config = controller, config
        self.setMinimumSize(360, 140)
        self.image=None
        self.empty_message="Write one letter here"
        self.show_guides=True

    def set_image(self,rgb):
        if rgb is None:self.image=None
        else:
            h,w=rgb.shape[:2]
            self.image=QImage(rgb.data,w,h,int(rgb.strides[0]),QImage.Format.Format_RGB888).copy()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f9fbff"))
        if self.image is not None:
            scale=min((self.width()-20)/self.image.width(),(self.height()-20)/self.image.height())
            w,h=self.image.width()*scale,self.image.height()*scale
            painter.drawImage(QRectF((self.width()-w)/2,(self.height()-h)/2,w,h),self.image)
            return
        scale = min((self.width()-24)/self.config.canvas_width, (self.height()-24)/self.config.canvas_height)
        w, h = self.config.canvas_width*scale, self.config.canvas_height*scale
        rect = QRectF((self.width()-w)/2, (self.height()-h)/2, w, h)
        painter.setPen(QPen(QColor("#dce4ed"), 1))
        painter.drawRect(rect)
        guide = QPen(QColor("#e5eaf2"), 1, Qt.PenStyle.DashLine)
        painter.setPen(guide)
        if self.show_guides:
            for proportion in (0.30,0.65,0.80):
                painter.drawLine(int(rect.x()), int(rect.y()+h*proportion), int(rect.right()), int(rect.y()+h*proportion))
        from PySide6.QtCore import QPointF
        def xy(p):
            return QPointF(rect.x()+p.x*w, rect.y()+p.y*h)
        painter.setPen(QPen(QColor("#172536"), max(2, 5*scale), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        for stroke in self.controller.buffer.strokes:
            if len(stroke) == 1:
                painter.drawPoint(xy(stroke[0]))
            for a,b in zip(stroke,stroke[1:]):
                painter.drawLine(xy(a),xy(b))
        if not self.controller.buffer.strokes:
            painter.setPen(QColor("#788696"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.empty_message)
        if self.controller.cursor is not None:
            x,y = self.controller.cursor
            painter.setPen(QPen(QColor("#078f79"),2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(rect.x()+x*w,rect.y()+y*h),6,6)
