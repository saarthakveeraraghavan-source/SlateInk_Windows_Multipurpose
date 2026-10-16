"""Immersive native playground; shares the existing camera and tracker."""
import math
import random
import time
from PySide6.QtCore import Qt,QTimer,QPointF,QRectF,Signal
from PySide6.QtGui import QColor,QPainter,QPen,QFont,QFontDatabase,QPainterPath,QRadialGradient,QImage
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QButtonGroup
from .fun_physics import PlaygroundModel,SCENES,clamp
from .fun_audio import PlaygroundAudio

TITLES={"portal":("PORTAL FIRE","Draw a circle. Open something extraordinary.","#ffae61"),
        "web":("WEB DOME","A structure you can hold between your hands.","#67e8e0"),
        "nebula":("NEBULA","A small universe, pulled into your orbit.","#bba1ff")}


def color(hex_value,alpha=255):
    c=QColor(hex_value);c.setAlpha(round(clamp(alpha,0,255)));return c


def ensure_fonts():
    # Native Windows already supplies these. Offscreen Qt does not enumerate
    # installed fonts; load the same system fonts for reliable previews/tests.
    if QFontDatabase.families():return
    import os
    from pathlib import Path
    folder=Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts"
    for name in ("segoeui.ttf","seguisb.ttf","segoeuil.ttf"):
        if (folder/name).is_file():QFontDatabase.addApplicationFont(str(folder/name))


class PlaygroundCanvas(QWidget):
    def __init__(self,model):
        super().__init__();self.model=model;self.preview=QImage();self.preview_at=None;self.show_camera=True
        self.paused=False;self.demo=False
        self.setMinimumSize(640,420)
        rng=random.Random(13)
        self.background_stars=[(rng.random(),rng.random(),rng.uniform(.35,1.1)) for _ in range(105)]

    def world(self,x,y):
        scale=min(self.width()/self.model.aspect,self.height())*.88
        return QPointF(self.width()*.5+x*scale,self.height()*.53+y*scale)

    def glow_line(self,painter,path,hex_value,width=2,alpha=255):
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for size,opacity in ((width*6,.05),(width*2.4,.22),(width,1)):
            pen=QPen(color(hex_value,alpha*opacity),size)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap);pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen);painter.drawPath(path)

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor("#05070d"))
        m=self.model;w,h=self.width(),self.height();accent=TITLES[m.scene][2]
        glow=QRadialGradient(QPointF(w*.5,h*.56),w*.6)
        glow.setColorAt(0,color("#253041" if m.scene=="portal" else "#15353c",55))
        glow.setColorAt(1,color("#05070d",0));p.fillRect(self.rect(),glow)
        for x,y,size in self.background_stars:
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(color("#b0c3e9",35+25*math.sin(m.time*.35+x*20)))
            p.drawEllipse(QPointF(x*w,y*h),size,size)
        # Minimal framing leaves the gesture field dark and uncluttered.
        p.setPen(QPen(color(accent,25),1));p.drawLine(24,103,w-24,103)
        p.setFont(QFont("Segoe UI",24,QFont.Weight.Light));p.setPen(color("#f0f3fa"))
        p.drawText(QPointF(24,48),TITLES[m.scene][0])
        p.setFont(QFont("Segoe UI",10));p.setPen(color("#99a3b5"))
        p.drawText(QPointF(26,76),TITLES[m.scene][1])
        p.save();p.setClipRect(QRectF(0,106,w,h-182));p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        if m.scene=="portal":self.paint_fire(p)
        elif m.scene=="web":self.paint_web(p)
        else:self.paint_nebula(p)
        self.paint_particles(p);self.paint_brush(p)
        p.restore()
        p.setFont(QFont("Segoe UI",10));p.setPen(color(accent))
        state="PAUSED · press P to resume" if self.paused else ("DEMO · synthetic motion" if self.demo else m.input_state)
        p.drawText(QRectF(26,h-58,max(200,w-265),24),Qt.AlignmentFlag.AlignVCenter,state)
        legend={"portal":"RIGHT HAND  /  move freely · draw a full circle to seal a portal",
                "web":"TWO HANDS  /  spread to expand · bring together to shrink · right hand turns the dome",
                "nebula":"RIGHT HAND  /  attract stars · pinch for a burst · left hand repels"}[m.scene]
        p.setPen(color("#7e899d"));p.setFont(QFont("Segoe UI",9))
        p.drawText(QRectF(26,h-33,max(200,w-240),22),Qt.AlignmentFlag.AlignVCenter,legend)
        if self.show_camera:self.paint_camera(p)

    def paint_fire(self,p):
        m=self.model
        for portal in m.portals:
            scale=min(self.width()/m.aspect,self.height())*.88
            center=self.world(portal.x,portal.y);radius=portal.radius*scale
            fade=min(1,(m.time-portal.born)*3,max(0,9-(m.time-portal.born)))
            rect=QRectF(center.x()-radius,center.y()-radius,radius*2,radius*2)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            inside=QRadialGradient(center,radius)
            inside.setColorAt(0,color("#112040",215*fade));inside.setColorAt(.8,color("#07101e",245*fade))
            inside.setColorAt(1,color("#fb6719",85*fade));p.setBrush(inside);p.setPen(Qt.PenStyle.NoPen);p.drawEllipse(rect)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            for width,alpha in ((26,15),(12,35),(4.5,190),(1.4,255)):
                p.setPen(QPen(color("#ff9b39",alpha*fade),width));p.setBrush(Qt.BrushStyle.NoBrush);p.drawEllipse(rect)
            phase=m.time*.5
            for i in range(68):
                a=i*math.tau/68+phase
                length=(.02+.015*math.sin(i*13.6+m.time*9))*radius
                inner=radius*(.88 if i%4 else .81)
                outer=radius+length
                start=QPointF(center.x()+math.cos(a)*inner,center.y()+math.sin(a)*inner)
                end=QPointF(center.x()+math.cos(a)*outer,center.y()+math.sin(a)*outer)
                p.setPen(QPen(color("#ffd58c",160*fade),1.2));p.drawLine(start,end)
                if i%4==0:
                    tip=QPointF(center.x()+math.cos(a+.025)*radius*.86,center.y()+math.sin(a+.025)*radius*.86)
                    p.drawLine(start,tip);p.drawLine(tip,end)
            p.setPen(QPen(color("#ffb34d",90*fade),1));p.drawEllipse(center,radius*.78,radius*.78)
        # Age buckets keep the rope smooth without a gradient allocation for
        # each segment. A lost/reacquired hand always begins a separate path.
        for bucket in range(8):
            path=QPainterPath();previous=None
            for x,y,t,stroke in m.trail:
                age=m.time-t
                point=self.world(x,y)
                if previous is not None and stroke==previous[3] and bucket==min(7,int(max(0,age)/1.6*8)):
                    path.moveTo(self.world(previous[0],previous[1]));path.lineTo(point)
                previous=(x,y,t,stroke)
            alpha=230*(1-bucket/8)**1.3
            self.glow_line(p,path,"#ff6b20",3.7,alpha)
            p.setPen(QPen(color("#fff0ba",alpha*.8),1.1));p.drawPath(path)

    def paint_web(self,p):
        m=self.model;w,h=self.width(),self.height()
        base=QPointF(w*.5+m.dome_center[0]*h,h*.68+m.dome_center[1]*h)
        r=min(w*.30,h*.34)*m.dome_scale
        cy,sy=math.cos(m.yaw),math.sin(m.yaw);cp,sp=math.cos(m.pitch),math.sin(m.pitch)
        rings,slices=11,36
        vertices={}
        for j in range(rings):
            phi=.06+(math.pi/2-.06)*j/(rings-1)
            for i in range(slices):
                a=i*math.tau/slices
                ripple=1+.02*math.sin(a*5+j*.6+m.time*2)+m.pulse*.045*math.sin(j-i*.15)
                x=math.sin(phi)*math.cos(a)*ripple;y=-math.cos(phi)*ripple;z=math.sin(phi)*math.sin(a)*ripple
                x,z=x*cy+z*sy,-x*sy+z*cy;y,z=y*cp-z*sp,y*sp+z*cp
                perspective=3/(3.6-z*.55)
                vertices[j,i]=(QPointF(base.x()+x*r*perspective,base.y()+y*r*perspective),z)
        # The base's projected rings give a stable floor and depth reference.
        p.setBrush(Qt.BrushStyle.NoBrush)
        for factor in (1.,1.15,1.3):
            p.setPen(QPen(color("#39a9af",35/factor),1))
            p.drawEllipse(base,r*factor*.86,r*factor*.20)
        edges=[]
        for j in range(rings):
            for i in range(slices):
                edges.append(((j,i),(j,(i+1)%slices)))
                if j+1<rings:
                    edges.append(((j,i),(j+1,i)))
                    edges.append(((j,i),(j+1,(i+1)%slices)))
        edges.sort(key=lambda edge:(vertices[edge[0]][1]+vertices[edge[1]][1]))
        for a,b in edges:
            pa,za=vertices[a];pb,zb=vertices[b];near=clamp(((za+zb)/2+1)/2,0,1)
            p.setPen(QPen(color("#62f2e1",28+near*140),.65+near*.65));p.drawLine(pa,pb)
        p.setPen(Qt.PenStyle.NoPen)
        for (point,z) in vertices.values():
            p.setBrush(color("#c2fffc",60+(z+1)*65));p.drawEllipse(point,1.5,1.5)
        if m.brush and m.other:
            a=self.world(*m.brush);b=self.world(*m.other)
            path=QPainterPath(a);path.cubicTo(QPointF(a.x(),base.y()),QPointF(b.x(),base.y()),b)
            self.glow_line(p,path,"#77e9e1",.8,65)

    def paint_nebula(self,p):
        m=self.model
        well=self.world(*(m.brush or (0.,0.)));radius=self.height()*.36
        haze=QRadialGradient(well,radius)
        haze.setColorAt(0,color("#543b9d",38));haze.setColorAt(.45,color("#1e3e7b",15));haze.setColorAt(1,color("#000000",0))
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(haze);p.drawEllipse(well,radius,radius)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(3):
            r=self.height()*(.08+i*.045)
            p.setPen(QPen(color("#9683de",18-i*3),.8))
            p.drawArc(QRectF(well.x()-r,well.y()-r*.43,r*2,r*.86),int((m.time*13+i*100)%360*16),210*16)
        for star in m.stars:
            point=self.world(star.x,star.y)
            tail=self.world(star.x-star.vx*.045,star.y-star.vy*.045)
            speed=math.hypot(star.vx,star.vy)
            hue="#b997ff" if star.size>1.1 else "#64d9ff"
            p.setPen(QPen(color(hue,35),star.size*4));p.drawLine(tail,point)
            p.setPen(QPen(color(hue,150),star.size));p.drawLine(tail,point)
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(color("#e2e5ff",150+min(100,speed*120)))
            p.drawEllipse(point,star.size*.6,star.size*.6)
        if m.pulse:
            point=self.world(*(m.brush or (0.,0.)));r=(1-m.pulse)*self.height()*.7
            p.setPen(QPen(color("#b3a2ff",m.pulse*130),1.5));p.setBrush(Qt.BrushStyle.NoBrush);p.drawEllipse(point,r,r)

    def paint_particles(self,p):
        m=self.model
        for particle in m.particles:
            point=self.world(particle.x,particle.y);alpha=clamp(particle.life/particle.ttl,0,1)
            hue="#ff8834" if particle.kind==0 else "#ae99ff"
            tail=self.world(particle.x-particle.vx*.045,particle.y-particle.vy*.045)
            p.setPen(QPen(color(hue,alpha*28),particle.size*4));p.drawLine(tail,point)
            p.setPen(QPen(color("#ffe7b5" if particle.kind==0 else "#c8caff",alpha*230),particle.size*.65));p.drawLine(tail,point)

    def paint_brush(self,p):
        m=self.model
        if not m.brush:return
        point=self.world(*m.brush);accent=TITLES[m.scene][2]
        p.setPen(Qt.PenStyle.NoPen)
        for radius,alpha in ((23,9),(13,25),(6,85),(2.5,240)):
            p.setBrush(color(accent,alpha));p.drawEllipse(point,radius,radius)
        if m.other and m.scene!="portal":
            p.setPen(QPen(color(accent,140),1));p.setBrush(Qt.BrushStyle.NoBrush);p.drawEllipse(self.world(*m.other),9,9)

    def paint_camera(self,p):
        w,h=self.width(),self.height();rect=QRectF(w-222,h-163,196,110)
        p.setPen(QPen(color("#8393ac",65),1));p.setBrush(color("#10151f",225));p.drawRoundedRect(rect.adjusted(-5,-23,5,5),8,8)
        p.setFont(QFont("Segoe UI",8));p.setPen(color("#b1bed0"))
        p.drawText(QPointF(rect.x()+1,rect.y()-8),"CAMERA / HAND CHECK")
        if self.preview.isNull() or self.preview_at is None or time.monotonic()-self.preview_at>.35:
            p.setPen(color("#707f95"));p.drawText(rect,Qt.AlignmentFlag.AlignCenter,"No camera frames" if self.demo else "Waiting for camera…")
        else:
            ratio=min(rect.width()/self.preview.width(),rect.height()/self.preview.height())
            size=(self.preview.width()*ratio,self.preview.height()*ratio)
            target=QRectF(rect.center().x()-size[0]/2,rect.center().y()-size[1]/2,*size)
            p.drawImage(target,self.preview)


class FunWindow(QWidget):
    finished=Signal()
    scene_changed=Signal(str)
    sound_changed=Signal(str,bool)

    def __init__(self,scene="portal",sound_options=None):
        super().__init__();ensure_fonts();self.setWindowTitle("SlateInk · Fun playground")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose,False)
        self.setStyleSheet("QWidget {background:#080b12;color:#b9c5d5;font-family:'Segoe UI';} QPushButton {background:#101722;border:1px solid #26303e;border-radius:7px;padding:8px 12px;} QPushButton:hover {background:#1c2937;color:white;} QPushButton:checked {border-color:#d3b78b;color:#fff2d7;background:#2b231e;}")
        self.model=PlaygroundModel(scene);self.canvas=PlaygroundCanvas(self.model)
        self.sound_options={key:bool((sound_options or {}).get(key,False)) for key in SCENES}
        self.audio=PlaygroundAudio();self.audio.configure(scene,self.sound_options[scene])
        self.paused=False;self.demo=False;self.demo_start=0
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        row=QHBoxLayout();row.setContentsMargins(24,14,24,14)
        brand=QLabel("SLATEINK  /  PLAY");font=QFont("Segoe UI",10,QFont.Weight.DemiBold);font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,2);brand.setFont(font);row.addWidget(brand)
        row.addStretch();self.group=QButtonGroup(self);self.tabs={}
        for key,label in zip(SCENES,("01  Portal fire","02  Web dome","03  Nebula")):
            button=QPushButton(label);button.setCheckable(True);button.setChecked(key==scene)
            button.clicked.connect(lambda checked=False,s=key:self.choose_scene(s));self.group.addButton(button);self.tabs[key]=button;row.addWidget(button)
        row.addStretch();back=QPushButton("Back · Esc");back.clicked.connect(self.close);row.addWidget(back);layout.addLayout(row)
        layout.addWidget(self.canvas,1)
        foot=QHBoxLayout();foot.setContentsMargins(24,10,24,14)
        for text,callback in (("Clear · Space",self.clear_scene),("Pause · P",self.toggle_pause),("Full screen · F11",self.toggle_fullscreen)):
            button=QPushButton(text);button.clicked.connect(callback);foot.addWidget(button)
        self.camera_button=QPushButton("Hand check");self.camera_button.setCheckable(True);self.camera_button.setChecked(True)
        self.camera_button.toggled.connect(self.show_camera);foot.addWidget(self.camera_button)
        self.sound_button=QPushButton("Sound off");self.sound_button.setCheckable(True)
        self.sound_button.setChecked(self.sound_options[scene]);self.sound_button.setText("Sound on" if self.sound_options[scene] else "Sound off")
        self.sound_button.toggled.connect(lambda enabled:self.set_scene_sound(self.model.scene,enabled,notify=True));foot.addWidget(self.sound_button)
        foot.addStretch();self.demo_button=QPushButton("Try demo");self.demo_button.setCheckable(True);self.demo_button.toggled.connect(self.toggle_demo);foot.addWidget(self.demo_button)
        layout.addLayout(foot);self.resize(1280,850)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        for button in self.findChildren(QPushButton):button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.timer=QTimer(self);self.timer.timeout.connect(self.step);self.timer.start(16)

    def choose_scene(self,scene):
        self.model.set_scene(scene);self.tabs[scene].setChecked(True)
        self.audio.configure(scene,self.sound_options[scene]);self.sync_sound_button()
        self.demo_start=time.monotonic();self.scene_changed.emit(scene);self.canvas.update()

    def set_scene_sound(self,scene,enabled,notify=False):
        self.sound_options[scene]=bool(enabled)
        if scene==self.model.scene:
            self.audio.configure(scene,enabled);self.sync_sound_button()
        if notify:self.sound_changed.emit(scene,bool(enabled))

    def sync_sound_button(self):
        self.sound_button.blockSignals(True);self.sound_button.setChecked(self.sound_options[self.model.scene]);self.sound_button.blockSignals(False)
        self.sound_button.setText("Sound on" if self.sound_options[self.model.scene] else "Sound off")
        self.sound_button.setToolTip(self.audio.status)

    def clear_scene(self):self.audio.stop();self.model.clear();self.demo_start=time.monotonic();self.canvas.update()

    def show_camera(self,enabled):self.canvas.show_camera=enabled;self.canvas.update()

    def toggle_pause(self):
        self.paused=not self.paused;self.canvas.paused=self.paused
        self.audio.stop()
        self.model.interrupt("Paused");self.model.last_step=None;self.canvas.update()

    def toggle_demo(self,enabled):
        self.demo=self.canvas.demo=enabled;self.clear_scene()
        if enabled:self.model.input_state="Demo · synthetic motion"

    def toggle_fullscreen(self):self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def observe(self,hands,t,mirrored,age,aspect,image=None):
        if image is not None:
            self.canvas.preview=QImage(image);self.canvas.preview_at=t;self.canvas.update()
        if not self.demo and not self.paused and self.isVisible() and not self.isMinimized() and self.isActiveWindow():
            self.model.observe(hands,t,mirrored,age,aspect)

    def step(self):
        if not self.isVisible() or self.isMinimized():
            self.audio.stop();self.model.interrupt();self.model.last_step=None;return
        now=time.monotonic()
        if self.paused:self.audio.stop();self.model.last_step=None;return
        if self.demo:self.demo_frame(now)
        self.model.advance(now)
        self.audio.update(self.model,active=self.isActiveWindow())
        self.sound_button.setToolTip(self.audio.status)
        if self.sound_options[self.model.scene] and ("unavailable" in self.audio.status or "No audio" in self.audio.status or "Unsupported" in self.audio.status):
            self.sound_button.setText("Sound unavailable")
        elif self.sound_options[self.model.scene]:self.sound_button.setText("Sound on")
        self.canvas.update()

    def demo_frame(self,now):
        # Deliberately labelled synthetic mode; never opens a camera or emits
        # an input event. The same observe/physics path drives the preview.
        from .tracking import Hand
        phase=now-self.demo_start
        def hand(x,y,label,pinch=False):
            p=[(x,y,0.)]*21
            p[0]=(x,y+.12,0.);p[5]=(x-.06,y,0.);p[9]=(x,y,0.);p[17]=(x+.06,y,0.)
            for pip,tip,dx in ((6,8,-.02),(10,12,.01),(14,16,.035),(18,20,.06)):
                p[pip]=(x+dx,y-.04,0.);p[tip]=(x+dx,y-.1,0.)
            p[8]=(x,y,0.);p[4]=(x-.08,y+.04,0.)
            return Hand(tuple(p),.2 if pinch else .9,label,.99)
        if self.model.scene=="portal":
            a=phase*2.0;r=.27
            hands=(hand(.5+math.cos(a)*r/self.model.aspect,.49+math.sin(a)*r,"Left"),)
        elif self.model.scene=="web":
            span=.17+.11*(1+math.sin(phase*.9))
            hands=(hand(.5-span,.52,"Left"),hand(.5+span,.52,"Right"))
        else:
            hands=(hand(.5+math.cos(phase*.7)*.23,.5+math.sin(phase*.9)*.22,"Left",int(phase)%5==4),)
        self.model.observe(hands,now,True,0,self.model.aspect)

    def keyPressEvent(self,event):
        actions={Qt.Key.Key_Escape:self.close,Qt.Key.Key_Space:self.clear_scene,
                 Qt.Key.Key_P:self.toggle_pause,Qt.Key.Key_F11:self.toggle_fullscreen}
        if event.key() in actions:actions[event.key()]();event.accept();return
        if event.key() in (Qt.Key.Key_1,Qt.Key.Key_2,Qt.Key.Key_3):
            self.choose_scene(SCENES[event.key()-Qt.Key.Key_1]);event.accept();return
        super().keyPressEvent(event)

    def changeEvent(self,event):
        from PySide6.QtCore import QEvent
        if event.type()==QEvent.Type.ActivationChange and not self.isActiveWindow():
            self.audio.stop()
            self.model.interrupt("Playground unfocused — return here to continue")
        super().changeEvent(event)

    def closeEvent(self,event):
        self.timer.stop();self.audio.stop();self.model.interrupt();self.canvas.preview=QImage()
        self.finished.emit();event.accept()
