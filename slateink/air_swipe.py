"""Short natural sideways hand strokes; no open-palm or rotation requirement."""
from math import hypot, isfinite, sqrt
from .hand_gestures import visible_control, fingers


def swipe_hand(hand, aspect=4/3):
    if (not visible_control(hand) or not isfinite(hand.handedness_confidence)
            or hand.handedness_confidence < .6
            or not all(isfinite(v) for p in hand.landmarks for v in p)):
        return None
    p=hand.landmarks
    def length(a,b):
        return sqrt(((p[a][0]-p[b][0])*aspect)**2+(p[a][1]-p[b][1])**2+((p[a][2]-p[b][2])*aspect)**2)
    size=max(length(0,9),length(5,17))
    if size < .035:return None
    tip=(sum(p[i][0] for i in (8,12))/2*aspect,sum(p[i][1] for i in (8,12))/2)
    wrist=p[0][0]*aspect,p[0][1]
    point=(tip[0]*.75+wrist[0]*.25,tip[1]*.75+wrist[1]*.25)
    extended=fingers(hand,aspect)
    offset=(tip[0]-wrist[0])/size
    upright=(tip[1]-wrist[1])/size
    span=length(5,17)
    thumb_gap=min(length(4,8),length(4,12))/max(span,.025)
    # Upright joined fingers remain the ordinary mouse pose. A relaxed sideways
    # hand, or folded hand, reserves the swipe channel without finger-count rules.
    sideways=abs(offset)>=.55 and abs(tip[0]-wrist[0])>=abs(tip[1]-wrist[1])*.5
    ready=(sideways or not any(extended)) and (thumb_gap >= .35 or not any(extended))
    neutral=(extended==(True,True,False,False) and abs(offset)<.35 and upright<-.8)
    return point,wrist,size,ready,neutral


class WindowSwipe:
    def __init__(self):
        self.cooldown_until=0
        self.reset()

    def reset(self):
        self.armed=False;self.capturing=False
        self.baseline=self.last=None
        self.steady_since=self.motion_started=self.neutral_since=None
        self.pending=self.confirm_since=None

    def update(self,hand,t,config,aspect=4/3,blocked=False,age=0):
        if blocked or not isfinite(t) or not isfinite(age) or age>.2:
            self.reset();return False,None
        # One missed frame during the fast stroke is common in both recordings.
        # Never emit on a missing observation; bridge at most 160 ms, with no
        # owned mouse input, then require two real end observations to confirm.
        if hand is None:
            if self.capturing and self.last is not None and 0<t-self.last[1]<=.16:
                self.pending=self.confirm_since=None
                return True,None
            self.reset();return False,None
        metrics=swipe_hand(hand,aspect)
        if metrics is None:
            self.reset();return False,None
        point,wrist,size,ready,neutral=metrics
        if not self.capturing and not ready:
            self.reset();return False,None
        if self.last is not None:
            old,old_t,old_size=self.last
            if (not 0<t-old_t<=.2 or hypot(wrist[0]-old[0],wrist[1]-old[1])>.2
                    or not .45<=size/old_size<=2.2):
                self.reset();return True,None
        self.last=wrist,t,size
        if neutral and self.capturing:
            if self.neutral_since is None:self.neutral_since=t
            if t-self.neutral_since>=.15:
                self.reset();return False,None
        else:self.neutral_since=None
        if not self.capturing:
            if not ready:return False,None
            self.capturing=True;self.baseline=point,size;self.steady_since=t
            return True,None
        origin,scale=self.baseline
        dx,dy=(point[0]-origin[0])/scale,(point[1]-origin[1])/scale
        if not self.armed:
            if hypot(dx,dy)>.2:
                self.baseline=point,size;self.steady_since=t
            elif t-self.steady_since>=.1 and t>=self.cooldown_until:
                self.armed=True
            return True,None
        if abs(dx)<.12:
            if abs(dy)>.5:
                self.baseline=point,size;self.steady_since=t;self.armed=False
            return True,None
        if self.motion_started is None and abs(dx)>.35:self.motion_started=t
        if (self.motion_started is not None and t-self.motion_started>.75) or abs(dy)>.9:
            self.baseline=point,size;self.steady_since=t;self.armed=False
            self.motion_started=None;self.pending=self.confirm_since=None
            return True,None
        threshold=.7/config.touchpad_swipe_sensitivity
        if abs(dx)<threshold or abs(dx)<abs(dy)*1.6:
            self.pending=self.confirm_since=None
            return True,None
        # Meaning matches the two named source videos and survives preview
        # mirroring. Handedness labels do not determine the swipe direction.
        direction=1 if dx*(-1 if config.camera_mirrored else 1)>0 else -1
        if self.pending!=direction:
            self.pending=direction;self.confirm_since=t
            return True,None
        if t-self.confirm_since>=.06:
            self.cooldown_until=t+config.touchpad_swipe_cooldown
            self.baseline=point,size;self.steady_since=t;self.armed=False
            self.motion_started=None;self.pending=self.confirm_since=None
            return True,direction
        return True,None
