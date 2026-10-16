"""Camera-relative hand poses; no screen/slate calibration requirement."""
from math import hypot,isfinite


def distance(hand,a,b,aspect=4/3):
    p=hand.landmarks
    return hypot((p[a][0]-p[b][0])*aspect,p[a][1]-p[b][1])


def visible_control(hand):
    if hand is None or len(hand.landmarks)!=21:return False
    # Wrist/palm-edge joints may legitimately be inferred just beyond the image
    # while the control anchor and pinch tips remain visible. Do not reject them
    # against a calibrated writing area, which the touchpad never uses.
    for i in (0,4,5,6,8,9,10,12,13,14,16,17,18,20):
        if not all(isfinite(v) for v in hand.landmarks[i][:2]):return False
    return all(-.015<=v<=1.015 for i in (4,5,8,9,12) for v in hand.landmarks[i][:2]) and all(-.2<=v<=1.2 for i in (0,17) for v in hand.landmarks[i][:2])


def fingers(hand,aspect=4/3):
    if not visible_control(hand):return (False,)*4
    return tuple(distance(hand,tip,0,aspect)>distance(hand,pip,0,aspect)*1.12 for tip,pip in ((8,6),(12,10),(16,14),(20,18)))


def open_palm(hand,aspect=4/3):
    return hand is not None and all(fingers(hand,aspect)) and hand.ratio is not None and hand.ratio>.6


def voice_symbol(hand,aspect=4/3):
    """Rock starts; index/pinky/thumb spread stops. Ambiguous thumbs do neither.

    Thumb spread is measured along the palm's own axis, so mirroring or turning
    the hand does not reverse the meanings. Only the index and pinky extend;
    the middle/ring fingers remain folded in both symbols.
    """
    if not visible_control(hand) or fingers(hand,aspect)!=(True,False,False,True):return None
    p=hand.landmarks;palm=distance(hand,5,17,aspect)
    if palm<.025 or any(not all(isfinite(v) for v in p[i][:2]) for i in (2,3)):return None
    axis=((p[5][0]-p[17][0])*aspect,p[5][1]-p[17][1])
    tip=((p[4][0]-p[5][0])*aspect,p[4][1]-p[5][1])
    outward=sum(a*b for a,b in zip(axis,tip))/(palm*palm)
    extended=(outward>=.18 and distance(hand,4,2,aspect)>=palm*.45
              and distance(hand,4,2,aspect)>distance(hand,3,2,aspect)*1.5)
    folded=outward<=.02 and distance(hand,4,9,aspect)<=palm*.7
    if extended:return "stop"
    if folded:return "start"
    return None


class ConfirmedPose:
    """Fast two-observation confirmation; no startup neutral pose or long hold."""
    def __init__(self,hold=.025):self.hold=hold;self.reset()
    def reset(self):self.since=None;self.last=None;self.fired=False
    def update(self,active,t):
        if not active:self.reset();return False
        if self.last is None or not 0<t-self.last<=.2:
            self.reset();self.since=t
        self.last=t
        if not self.fired and t-self.since>=self.hold:
            self.fired=True;return True
        return False


def scroll_pose(hand,aspect=4/3):
    return hand is not None and fingers(hand,aspect)==(True,True,True,False)


class DwellPose:
    """One event per deliberate pose, with neutral-to-arm on startup/loss."""
    def __init__(self,hold=.8,release=.2):self.hold=hold;self.release=release;self.reset()
    def reset(self):self.armed=False;self.active_since=None;self.neutral_since=None;self.fired=False
    def update(self,active,t):
        if not active:
            self.active_since=None
            if self.neutral_since is None:self.neutral_since=t
            if t-self.neutral_since>=self.release:self.armed=True;self.fired=False
            return False
        self.neutral_since=None
        if not self.armed or self.fired:return False
        if self.active_since is None:self.active_since=t
        if t-self.active_since>=self.hold:self.fired=True;self.armed=False;return True
        return False
