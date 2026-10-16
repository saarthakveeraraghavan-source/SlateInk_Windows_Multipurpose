"""Right-hand open-palm sweeps, measured against the named video references."""
from collections import deque
from math import hypot, isfinite, sqrt
from .hand_gestures import visible_control, fingers


def swipe_hand(hand, aspect=4/3):
    if (not visible_control(hand) or not isfinite(aspect) or aspect<=0
            or not isfinite(hand.handedness_confidence) or hand.handedness_confidence<.65
            or hand.ratio is None or not isfinite(hand.ratio)
            or not all(len(p)==3 and all(isfinite(v) for v in p) for p in hand.landmarks)):
        return None
    p=hand.landmarks
    def length(a,b):
        return sqrt(((p[a][0]-p[b][0])*aspect)**2+(p[a][1]-p[b][1])**2+((p[a][2]-p[b][2])*aspect)**2)
    size=max(length(0,9),length(5,17))
    if size<.035:return None
    point=(sum(p[i][0] for i in (0,5,9,13,17))/5*aspect,
           sum(p[i][1] for i in (0,5,9,13,17))/5)
    wrist=p[0][0]*aspect,p[0][1]
    radial=fingers(hand,aspect)
    def straight(mcp,pip,tip):
        # A palm turning edge-on can shorten the projected finger. Use the
        # joint's 3D shape as well, while curled mouse/scroll fingers stay out.
        a=tuple((p[mcp][i]-p[pip][i])*(aspect if i!=1 else 1) for i in range(3))
        b=tuple((p[tip][i]-p[pip][i])*(aspect if i!=1 else 1) for i in range(3))
        norm=sqrt(sum(v*v for v in a)*sum(v*v for v in b))
        return (norm>1e-8 and sum(x*y for x,y in zip(a,b))/norm<-.35
                and length(mcp,tip)>length(mcp,pip)*1.45)
    extended=tuple(r or straight(*joints) for r,joints in zip(radial,((5,6,8),(9,10,12),(13,14,16),(17,18,20))))
    ready=all(extended) and hand.ratio>.7
    partial=sum(extended)>=3 and hand.ratio>.6
    return point,wrist,size,ready,partial


class WindowSwipe:
    # Fast reference strokes can lose landmarks for several video frames.
    # Keep only observed start anchors; never emit or invent motion on missing
    # data. A new, matching palm needs two fresh end observations to switch.
    max_gap=.7
    stroke_window=1.2

    def __init__(self):
        self.cooldown_until=0
        self.reset()

    def reset(self):
        self.armed=False;self.capturing=False
        self.anchors=deque()
        self.last=None;self.last_t=None;self.partial_since=None
        self.pending=self.confirm_since=None;self.pending_end=None
        self.moving=False

    @property
    def hint(self):
        return "Right-hand swipe ready — sweep your open hand as in Next or Previous; relax it to point."

    def _missing(self,t):
        if self.capturing and self.last_t is not None and 0<t-self.last_t<=self.max_gap:
            self.pending=self.confirm_since=self.pending_end=None
            return True,None
        self.reset();return False,None

    def update(self,hand,t,config,aspect=4/3,blocked=False,age=0):
        if blocked or not isfinite(t) or not isfinite(age) or age>.2:
            self.reset();return False,None
        expected="Left" if config.camera_mirrored else "Right"
        if hand is None or hand.label!=expected:return self._missing(t)
        metrics=swipe_hand(hand,aspect)
        if metrics is None:return self._missing(t)
        point,wrist,size,ready,partial=metrics
        if self.last_t is not None:
            if t<=self.last_t:
                self.reset();return False,None
            if t-self.last_t>self.max_gap:self.reset()
        if not ready:
            # A temporarily hidden little finger is common in the open-palm
            # reference. Pointing/two fingers or a folded hand release at once.
            if self.capturing and partial:
                if self.partial_since is None:self.partial_since=t
                if t-self.partial_since<=.35:return self._missing(t)
            self.reset();return False,None
        self.partial_since=None
        if self.last is not None:
            old_point,old_wrist,old_size=self.last
            dt=t-self.last_t
            if (hypot(wrist[0]-old_wrist[0],wrist[1]-old_wrist[1])>max(.12,dt*4)
                    or not .5<=size/old_size<=2):
                self.reset();return True,None
        self.capturing=True
        self.last=point,wrist,size;self.last_t=t
        while self.anchors and t-self.anchors[0][0]>self.stroke_window:self.anchors.popleft()
        # A fast reverse may expose only ONE starting frame. A fully open,
        # trusted hand can anchor it; two real end observations are still
        # mandatory. Keep acquiring during cooldown so a reverse start is not
        # thrown away merely because the previous switch is settling.
        self.anchors.append((t,point,wrist,size))
        self.moving=self.moving or any(
            max(hypot(point[0]-origin[0],point[1]-origin[1]),hypot(wrist[0]-ow[0],wrist[1]-ow[1]))>scale*.4
            for _,origin,ow,scale in self.anchors)
        self.armed=bool(self.anchors)
        candidate=None
        threshold=max(.85,1.1/config.touchpad_swipe_sensitivity)
        for start,origin,origin_wrist,scale in self.anchors:
            if not .12<=t-start<=self.stroke_window:continue
            dx,dy=(point[0]-origin[0])/scale,(point[1]-origin[1])/scale
            wx,wy=(wrist[0]-origin_wrist[0])/scale,(wrist[1]-origin_wrist[1])/scale
            travel=min(abs(dx),abs(wx))
            if (dx*wx>0 and travel>=threshold
                    and abs(dx)>abs(dy)*1.5 and abs(wx)>abs(wy)*1.5):
                # The named unmirrored Next recording moves image-right;
                # mirrored live frames must give the SAME named action.
                candidate=1 if dx*(-1 if config.camera_mirrored else 1)>0 else -1
                break
        if candidate is None:
            self.pending=self.confirm_since=self.pending_end=None
            return True,None
        if self.pending!=candidate:
            self.pending=candidate;self.confirm_since=t;self.pending_end=point
            return True,None
        # Observe the destination again; do not confirm an implausible endpoint
        # jump or infer direction from unobserved frames during a tracking gap.
        if hypot(point[0]-self.pending_end[0],point[1]-self.pending_end[1])>size*.9:
            self.confirm_since=t;self.pending_end=point;return True,None
        if t-self.confirm_since>=.05 and t>=self.cooldown_until:
            self.cooldown_until=t+config.touchpad_swipe_cooldown
            self.reset()
            return True,candidate
        return True,None
