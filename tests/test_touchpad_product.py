from dataclasses import replace
import math
import numpy as np
from slateink.config import Config
from slateink.tracking import Hand
from slateink.mouse_control import HandMouseController
from slateink.touchpad_session import TouchpadSession
from slateink.hand_gestures import fingers,scroll_pose,victory,open_palm
from test_mouse_control import Sink,hand,stick,controller,arm,hold_left


def pose(extended=(True,True,False,False),x=.5,y=.65,label="Left",spread=False):
    p=[(x,y,0)]*21;p[0]=(x,y+.2,0);p[5]=(x-.1,y,0);p[9]=(x,y,0);p[17]=(x+.1,y,0)
    p[4]=(x-.18,y,0)
    for j,(tip,pip) in enumerate(((8,6),(12,10),(16,14),(20,18))):
        xx=x+(-.05+j*.05)
        p[pip]=(xx,y-.12,0);p[tip]=(xx,y-.32 if extended[j] else y+.03,0)
    if spread:p[8]=(x-.13,y-.32,0);p[12]=(x+.13,y-.32,0)
    return Hand(tuple(p),.8,label)


class Shortcuts:
    def __init__(self):self.calls=[];self.active=False;self.same=True
    def begin(self,mode):self.calls.append(("begin",mode));self.active=True
    def finish(self):self.calls.append(("finish",));self.active=False
    def cancel(self):
        if self.active:self.calls.append(("cancel",))
        self.active=False
    def target_unchanged(self):return self.same


def session():
    c,s=controller();c.config=replace(c.config,wispr_enabled=True)
    keys=Shortcuts();ses=TouchpadSession(c,keys);ses.set_enabled(True)
    for i in range(10):ses.process((pose(),),1+i*.033)
    return ses,s,keys


def test_visible_fingertips_work_when_wrist_is_just_below_camera():
    c,s=controller();p=list(pose(y=.85).landmarks);p[0]=(.5,1.08,0)
    h=Hand(tuple(p),.8,"Left")
    for i in range(10):assert "left the camera" not in c.process(h,1+i*.033)
    p[8]=(.5,1.05,0)
    assert "left the camera" in c.process(Hand(tuple(p),.8,"Left"),1.4)


def test_three_fingers_scroll_down_and_never_point_or_click():
    c,s=controller()
    for i in range(22):c.process(pose((True,True,True,False),y=.5+i*.003),1+i*.033)
    wheels=[e for e in s.events if e[0]=="wheel"]
    assert wheels and all(e[1]<0 and e[2]==0 for e in wheels)
    assert not any(e[0]=="relative" or e==("left",True) for e in s.events)


def test_horizontal_scroll_and_reversed_direction():
    c,s=controller();c.config=replace(c.config,touchpad_natural_scroll=True)
    for i in range(22):c.process(pose((True,True,True,False),x=.5+i*.003),1+i*.033)
    assert any(e[0]=="wheel" and e[2]<0 and e[1]==0 for e in s.events)


def test_holding_click_without_deliberate_movement_never_drags():
    c,s=controller();hold_left(c)
    for i in range(35):c.process(hand(left=.2,x=.5+.003*math.sin(i)),1.25+i*.033)
    assert not c.dragging and not any(e[0]=="relative" for e in s.events)


def test_precision_reduces_movement_for_same_sweep():
    normal=[];precise=[]
    for precision,results in ((False,normal),(True,precise)):
        c,s=controller()
        for i in range(18):c.process(stick(.5+max(0,i-5)*.004),1+i*.033,precision=precision)
        results.extend(abs(e[1]) for e in s.events if e[0]=="relative")
    assert 0<sum(precise)<sum(normal)


def test_two_hands_keep_controlling_identity_and_helper_precision():
    ses,s,k=session();right=pose(label="Right",extended=(True,)*4)
    for i in range(12):ses.process((right,pose(x=.5+i*.003)),1.4+i*.033)
    assert ses.primary.label=="Left" and ses.helper.label=="Right"
    assert any(e[0]=="relative" for e in s.events) and not k.calls
    before=len(s.events);ses.process((right,),1.82)
    assert ses.primary is None and len(s.events)==before


def test_v_gesture_starts_once_then_release_finishes_once_and_freezes_pointer():
    ses,s,k=session();v=pose(label="Right",spread=True)
    assert victory(v) and not open_palm(v) and not scroll_pose(v)
    before=len(s.events)
    for i in range(55):ses.process((pose(),v),1.4+i*.033)
    assert k.calls==[("begin","toggle_ctrl_win")] and ses.dictating
    assert len(s.events)==before
    for i in range(25):ses.process((pose(),),3.3+i*.033)
    assert k.calls==[("begin","toggle_ctrl_win"),("finish",)] and not ses.dictating


def test_stale_frame_cancels_wispr_and_releases_clicks():
    ses,s,k=session();v=pose(label="Right",spread=True)
    for i in range(35):ses.process((pose(),v),1.4+i*.033)
    assert ses.dictating
    ses.process((pose(),v),2.7,age=.3)
    assert k.calls[-1]==("cancel",) and not ses.dictating and not s.held


def test_changed_textbox_cancels_instead_of_pasting():
    ses,s,k=session();v=pose(label="Right",spread=True)
    for i in range(35):ses.process((pose(),v),1.4+i*.033)
    k.same=False;ses.process((pose(),v),2.7)
    assert k.calls[-1]==("cancel",) and ("finish",) not in k.calls


def test_both_open_palms_pause_once_and_resume_after_release():
    ses,s,k=session();left=pose(extended=(True,)*4);right=pose(extended=(True,)*4,label="Right")
    for i in range(70):ses.process((left,right),1.4+i*.033)
    assert ses.paused
    for i in range(12):ses.process((pose(),),3.8+i*.033)
    for i in range(40):ses.process((left,right),4.3+i*.033)
    assert not ses.paused


def test_initial_v_pose_cannot_trigger_shortcut_without_neutral_rearm():
    c,s=controller();c.config=replace(c.config,wispr_enabled=True);k=Shortcuts();ses=TouchpadSession(c,k);ses.set_enabled(True)
    for i in range(60):ses.process((pose(spread=True),),1+i*.033)
    assert not k.calls


def test_relaxed_closed_fist_cannot_be_interpreted_as_a_click():
    c,s=controller();arm(c)
    closed=pose((False,False,False,False));closed=replace(closed,ratio=.1)
    for i in range(15):c.process(closed,1.3+i*.033)
    assert not any(e==("left",True) for e in s.events)
