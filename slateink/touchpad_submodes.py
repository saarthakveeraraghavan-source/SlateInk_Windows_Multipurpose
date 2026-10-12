"""Left-palm WASD joystick and isotropic index drawing; local input only."""
import ctypes
import os
from ctypes import wintypes
from math import hypot,isfinite
from .injection import WindowsInjector,INPUT,KEYBDINPUT,InjectionError
from .hand_gestures import visible_control,fingers,open_palm,distance
from .smoothing import OneEuro
from .gestures import Pinch


class WindowsMovementKeys:
    """Owned press/release events restricted to four physical WASD scan codes."""
    CODES={"W":0x11,"A":0x1e,"S":0x1f,"D":0x20}

    def __init__(self):
        self.api=WindowsInjector().api;self.held=set()

    def target(self):
        window=self.api.GetForegroundWindow()
        if not window:return None
        pid=wintypes.DWORD()
        self.api.GetWindowThreadProcessId(window,ctypes.byref(pid))
        return None if not pid.value or pid.value==os.getpid() else (int(window),pid.value)

    def key(self,name,down):
        code=self.CODES[name]
        if down:
            if name in self.held:return
            self.held.add(name)
        elif name not in self.held:return
        event=INPUT();event.type=1
        event.ki=KEYBDINPUT(0,code,0x0008 | (0 if down else 0x0002),0,0)
        if self.api.SendInput(1,ctypes.byref(event),ctypes.sizeof(INPUT))!=1:
            raise InjectionError("Windows blocked gaming input. Control stopped; no automatic retry.")
        if not down:self.held.discard(name)

    def release_all(self):
        failures=[]
        for key in tuple(self.held):
            try:self.key(key,False)
            except InjectionError:failures.append(key)
        if failures:raise InjectionError("WASD release was not confirmed. Release the keys with your keyboard; control is stopped.")


class GamingController:
    def __init__(self,config,sink):
        self.config=config;self.sink=sink;self.filter=OneEuro(min_cutoff=3,beta=.4)
        self.center=None;self.last=None;self.neutral_since=None;self.ready=False
        self.center_since=None;self.target=None;self.wanted=set();self.candidate=None;self.since=0

    def interrupt(self):
        try:
            if self.sink:self.sink.release_all()
        finally:
            self.center=None;self.last=None;self.neutral_since=None;self.ready=False
            self.center_since=None;self.target=None;self.wanted=set();self.candidate=None
            self.filter.reset()

    def process(self,hand,t,age=0,aspect=4/3):
        if self.sink is None:return "Gaming keyboard unavailable."
        target=self.sink.target()
        if target is None or (self.target is not None and target!=self.target):
            self.interrupt();return "Focus changed — WASD released. Focus the game, then hold your left palm still to center."
        if hand is None or age>.2 or not visible_control(hand):
            self.interrupt();return "Left hand missing — WASD released. Show a steady palm to center."
        p=hand.landmarks
        raw=(sum(p[i][0] for i in (5,9,13,17))/4*aspect,sum(p[i][1] for i in (5,9,13,17))/4)
        if self.last and (t-self.last[1]>.2 or t<=self.last[1] or hypot(raw[0]-self.last[0][0],raw[1]-self.last[0][1])>.25):
            self.interrupt();return "Left-hand tracking jump — WASD released. Show a steady palm to center."
        self.last=(raw,t);self.target=target
        extended=fingers(hand,aspect)
        if not any(extended):
            self.sink.release_all();self.wanted=set();self.center=None;self.center_since=None;self.filter.reset();self.candidate=None
            if self.neutral_since is None:self.neutral_since=t
            if t-self.neutral_since>=.12:self.ready=True
            return "Left fist: stopped. Open palm at a comfortable center to arm the joystick."
        self.neutral_since=None
        if sum(extended)<3:
            # Real fist-to-palm transitions pass through one/two extended
            # fingers. Stop keys without destroying an established center.
            self.sink.release_all();self.wanted=set();self.candidate=None
            self.center_since=None;self.filter.reset()
            return "Left joystick stopped — extend at least three fingers to steer; fist recenters."
        point=self.filter.update(raw,t)
        if self.center is None:
            if self.center_since is None:self.center_since=t;self.center_candidate=point
            if hypot(point[0]-self.center_candidate[0],point[1]-self.center_candidate[1])>.018:
                self.center_since=t;self.center_candidate=point
            progress=min(100,round((t-self.center_since)/.3*100))
            if t-self.center_since<.3:return f"Left joystick CENTERING {progress}% — hold palm still with at least three fingers extended."
            self.center=point;self.ready=True;self.radius=max(.025,distance(hand,5,17,aspect)*self.config.gaming_radius)
        dx,dy=point[0]-self.center[0],point[1]-self.center[1]
        wanted=set()
        # User's forward/back hand motion projects onto increasing/decreasing
        # camera y respectively. Reverse only this joystick axis.
        for delta,negative,positive in ((dx,"A","D"),(dy,"S","W")):
            threshold=self.radius*(.68 if negative in self.wanted or positive in self.wanted else 1)
            if delta < -threshold:wanted.add(negative)
            elif delta > threshold:wanted.add(positive)
        # Release immediately; debounce only new presses. Never hold opposites.
        for name in self.wanted-wanted:self.sink.key(name,False)
        self.wanted.intersection_update(wanted)
        if wanted!=self.candidate:self.candidate=wanted;self.since=t
        if t-self.since>=.045:
            for name in wanted-self.wanted:self.sink.key(name,True)
            self.wanted=set(wanted)
        return "Left joystick: "+(" + ".join(sorted(self.wanted)) if self.wanted else "center / stopped")+" · fist stops and recenters."


class DrawingController:
    def __init__(self,config,sink,focus=None):
        self.config=config;self.sink=sink;self.focus=focus
        self.filter=OneEuro(min_cutoff=3,beta=.5);self.held=False
        self.reference=None;self.last=None;self.label=None;self.armed=False
        self.hover_since=None;self.down_since=None;self.target=None;self.remainder=(0.,0.)
        self.click=Pinch(config.pinch_down_ratio,config.pinch_up_ratio,config.pinch_debounce_ms)
        self.click_held=False;self.clicking=False
        self.palm_last=None
        self.helper_last=None

    def interrupt(self):
        try:self.sink.release_all()
        finally:
            self.held=False;self.reference=None;self.last=None;self.label=None;self.armed=False
            self.hover_since=None;self.down_since=None;self.target=None;self.filter.reset();self.remainder=(0.,0.)
            self.click.reset();self.click_held=False;self.clicking=False
            self.palm_last=None
            self.helper_last=None

    def process(self,hand,t,age=0,aspect=4/3,click_hand=None,split_click=False):
        target=self.focus() if self.focus else True
        if target is None or (self.target is not None and target!=self.target):
            self.interrupt();return "Focus changed — pen lifted. Show index + middle in the drawing app to re-arm."
        if hand is None or age>.2 or not visible_control(hand) or not isfinite(aspect) or aspect<=0:
            self.interrupt();return "Drawing tracking lost — pen lifted. Show index + middle to re-arm."
        raw=(hand.index[0]*aspect,hand.index[1])
        palm=(hand.landmarks[5][0]*aspect,hand.landmarks[5][1])
        pinch_transition=self.clicking or (not split_click and hand.ratio is not None and isfinite(hand.ratio) and hand.ratio<self.config.pinch_up_ratio)
        palm_jump=self.palm_last is not None and hypot(palm[0]-self.palm_last[0],palm[1]-self.palm_last[1])>.25
        # A tip folds a long way during pinch closure. Check the stable knuckle
        # during click transitions; keep the tip jump guard for actual ink.
        if (self.label is not None and self.label!=hand.label) or palm_jump or (self.last and (t<=self.last[1] or t-self.last[1]>.2 or (not pinch_transition and hypot(raw[0]-self.last[0][0],raw[1]-self.last[0][1])>.25))):
            self.interrupt();return "Drawing tracking jump — pen lifted. Show index + middle to re-arm."
        self.target=target;self.label=hand.label;self.last=(raw,t);self.palm_last=palm
        extended=fingers(hand,aspect)
        draw=extended==(True,False,False,False)
        hover=extended==(True,True,False,False)
        ratio=hand.ratio
        if split_click:
            # Optional helper input only selects click state. It never enters
            # the drawing position/filter/gain calculation.
            helper_ok=visible_control(click_hand) and click_hand.ratio is not None and isfinite(click_hand.ratio) and any(fingers(click_hand,aspect))
            if helper_ok:
                anchor=(click_hand.landmarks[5][0]*aspect,click_hand.landmarks[5][1])
                if self.helper_last and (t-self.helper_last[1]>.2 or hypot(anchor[0]-self.helper_last[0][0],anchor[1]-self.helper_last[0][1])>.25):helper_ok=False
                self.helper_last=(anchor,t)
            else:self.helper_last=None
            if helper_ok:ratio=click_hand.ratio
            else:
                self.click.reset();ratio=self.config.pinch_up_ratio+.1
        if ratio is None or not isfinite(ratio):
            self.interrupt();return "Pinch tracking unavailable — pen lifted. Show index + middle to re-arm."
        click_down=self.click.update(ratio,t)
        if ratio<self.config.pinch_up_ratio:self.clicking=True
        if self.clicking:
            # Ink and tool clicks share left mouse ownership, but never a stroke.
            # Freeze at the hover target through pinch closure and reopening.
            if self.held:self.sink.button("left",False);self.held=False
            self.reference=None;self.filter.reset();self.remainder=(0.,0.)
            self.down_since=None;self.hover_since=None
            if not any(extended):
                if self.click_held:self.sink.button("left",False);self.click_held=False
                self.click.reset()
                return "Pen lifted / reposition. Show index + middle and open the thumb pinch to hover."
            if click_down and self.armed and not self.click_held:
                self.sink.button("left",True);self.click_held=True
            elif not click_down and self.click_held:
                self.sink.button("left",False);self.click_held=False
            if ratio>=self.config.pinch_up_ratio and not click_down and hover:
                self.clicking=False
            else:
                return "Click held — release thumb/index, then show index + middle to hover." if self.click_held else "Open thumb/index and show index + middle to hover; pinch clicks at the current target."
        if not draw:
            if self.held:self.sink.button("left",False);self.held=False
            self.down_since=None
        if not draw and not hover:
            self.reference=None;self.filter.reset();self.remainder=(0.,0.);self.hover_since=None
            return "Pen lifted / reposition. Index + middle: hover. Index only: draw."
        if hover:
            if self.hover_since is None:self.hover_since=t
            if t-self.hover_since>=.12:self.armed=True
        else:
            self.hover_since=None
            if not self.armed:
                self.reference=None;self.filter.reset();return "Show index + middle briefly to arm, then fold middle to draw."
            if not self.held:
                if self.down_since is None:self.down_since=t
                # Establish a fresh tip reference through the posture change.
                self.reference=None;self.filter.reset();self.remainder=(0.,0.)
                if t-self.down_since<.06:return "Index only detected — settling pen."
                self.sink.button("left",True);self.held=True
        point=self.filter.update(raw,t)
        if self.reference is None:self.reference=point;return "Drawing — index only." if self.held else "Hover — no ink."
        # Landmarks are normalized separately by image width/height. Convert x
        # into camera-height units BEFORE isotropic smoothing and pixel mapping.
        gain=self.sink.pixel_scale()*self.config.drawing_sensitivity
        dx=(point[0]-self.reference[0])*gain+self.remainder[0]
        dy=(point[1]-self.reference[1])*gain+self.remainder[1]
        sx,sy=round(dx),round(dy)
        self.remainder=(dx-sx,dy-sy);self.reference=point
        if sx or sy:self.sink.move_pixels(sx,sy)
        return "Drawing — raise middle finger to lift pen." if self.held else "Hover — thumb/index pinch clicks; fold middle with thumb away to draw."
