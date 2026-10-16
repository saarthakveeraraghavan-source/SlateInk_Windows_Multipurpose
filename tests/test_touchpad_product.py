from dataclasses import replace
import math
import numpy as np
import pytest
from slateink.config import Config
from slateink.tracking import Hand
from slateink.mouse_control import HandMouseController
from slateink.touchpad_session import TouchpadSession
from slateink.hand_gestures import fingers,scroll_pose,voice_symbol,open_palm
from test_mouse_control import Sink,hand,stick,controller,arm,hold_left


def pose(extended=(True,True,False,False),x=.5,y=.65,label="Left",spread=False):
    p=[(x,y,0)]*21;p[0]=(x,y+.2,0);p[5]=(x-.1,y,0);p[9]=(x,y,0);p[17]=(x+.1,y,0)
    p[4]=(x-.18,y,0)
    for j,(tip,pip) in enumerate(((8,6),(12,10),(16,14),(20,18))):
        xx=x+(-.05+j*.05)
        p[pip]=(xx,y-.12,0);p[tip]=(xx,y-.32 if extended[j] else y+.03,0)
    if spread:p[8]=(x-.13,y-.32,0);p[12]=(x+.13,y-.32,0)
    return Hand(tuple(p),.8,label)


def rock_pose(label="Right",mirrored=False,extended_thumb=False):
    p=list(pose((True,False,False,True),label=label).landmarks)
    p[2]=(.35,.7,0)
    p[3]=(.31,.65,0) if extended_thumb else (.43,.68,0)
    p[4]=(.21,.62,0) if extended_thumb else (.5,.67,0)
    if mirrored:p=[(1-x,y,z) for x,y,z in p]
    from slateink.gestures import pinch_ratio
    return Hand(tuple(p),pinch_ratio(p),label)


def old_thumb_pose(label="Right",mirrored=False):
    p=list(pose((False,)*4,label=label).landmarks)
    p[2]=(.4,.62,0);p[3]=(.4,.49,0);p[4]=(.4,.36,0)
    if mirrored:p=[(1-x,y,z) for x,y,z in p]
    from slateink.gestures import pinch_ratio
    return Hand(tuple(p),pinch_ratio(p),label)


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


def test_rock_starts_promptly_then_hands_can_relax_until_same_hand_swag():
    ses,s,k=session();v=rock_pose(label="Right")
    assert voice_symbol(v)=="start" and not open_palm(v) and not scroll_pose(v)
    before=len(s.events)
    ses.process((pose(),v),1.4)
    assert not k.calls
    ses.process((pose(),v),1.433)
    assert k.calls==[("begin","toggle_ctrl_win")] and ses.dictating
    for i in range(55):ses.process((pose(),v),1.466+i*.033)
    assert k.calls==[("begin","toggle_ctrl_win")] and ses.dictating
    assert len(s.events)==before
    for i in range(25):ses.process((pose(),),3.3+i*.033)
    for i in range(25):ses.process((),4.3+i*.033)
    assert k.calls==[("begin","toggle_ctrl_win")] and ses.dictating
    for i in range(5):ses.process((rock_pose(extended_thumb=True),),5.3+i*.033)
    assert k.calls==[("begin","toggle_ctrl_win"),("finish",)] and not ses.dictating


def test_stale_tracking_keeps_latched_wispr_but_explicit_stop_cancels():
    ses,s,k=session();v=rock_pose(label="Right")
    for i in range(35):ses.process((pose(),v),1.4+i*.033)
    assert ses.dictating
    ses.process((pose(),v),2.7,age=.3)
    assert k.calls==[("begin","toggle_ctrl_win")] and ses.dictating and not s.held
    ses.tracking_stale()
    assert ses.dictating
    ses.interrupt()
    assert k.calls[-1]==("cancel",) and not ses.dictating


def test_changed_textbox_cancels_instead_of_pasting():
    ses,s,k=session();v=rock_pose(label="Right")
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


def test_initial_rock_starts_without_a_neutral_or_long_hold():
    c,s=controller();c.config=replace(c.config,wispr_enabled=True);k=Shortcuts();ses=TouchpadSession(c,k);ses.set_enabled(True)
    ses.process((rock_pose(),),1)
    ses.process((rock_pose(),),1.034)
    assert k.calls==[("begin","toggle_ctrl_win")] and ses.dictating


def test_other_hand_swag_and_two_palms_cannot_finish_or_pause_dictation():
    ses,s,k=session()
    for t in (1.4,1.44):ses.process((rock_pose(label="Right"),),t)
    for i in range(20):ses.process((rock_pose("Left",extended_thumb=True),),1.5+i*.05)
    for i in range(30):ses.process((pose((True,)*4),pose((True,)*4,label="Right")),2.6+i*.05)
    assert ses.dictating and not ses.paused and k.calls==[("begin","toggle_ctrl_win")]
    assert not s.events


def test_rock_from_different_hands_cannot_combine_into_one_confirmation():
    ses,s,k=session()
    ses.process((rock_pose(label="Right"),),1.4)
    ses.process((rock_pose(label="Left"),),1.44)
    assert not k.calls
    ses.process((rock_pose(label="Left"),),1.48)
    assert ses.dictating and ses.voice_hand=="Left"


def test_two_palms_between_rock_observations_reset_start_confirmation():
    ses,s,k=session()
    ses.process((rock_pose(label="Right"),),1.4)
    ses.process((pose((True,)*4),pose((True,)*4,label="Right")),1.44)
    ses.process((rock_pose(label="Right"),),1.48)
    assert not k.calls
    ses.process((rock_pose(label="Right"),),1.52)
    assert ses.dictating


def test_thumb_confirmation_requires_fresh_unambiguous_same_hand_observations():
    ses,s,k=session()
    for t in (1.4,1.44):ses.process((rock_pose(label="Right"),),t)
    for i in range(5):ses.process((rock_pose(extended_thumb=True),rock_pose(extended_thumb=True)),1.5+i*.04)
    for i in range(5):ses.process((replace(rock_pose(extended_thumb=True),handedness_confidence=.5),),1.8+i*.04)
    ses.process((rock_pose(extended_thumb=True),),2.1)
    ses.process((),2.14)
    ses.process((rock_pose(extended_thumb=True),),2.18)
    assert ses.dictating and len(k.calls)==1
    for t in (2.22,2.26):ses.process((rock_pose(extended_thumb=True),),t)
    assert not ses.dictating and k.calls[-1]==("finish",)


def test_voice_symbols_are_mirror_invariant_and_thumb_states_do_not_overlap():
    for mirror in (False,True):
        assert voice_symbol(rock_pose(mirrored=mirror))=="start"
        assert voice_symbol(rock_pose(mirrored=mirror,extended_thumb=True))=="stop"
    for h in (pose((False,)*4),pose(spread=True),pose((True,)*4),old_thumb_pose(),hand(left=.2)):
        assert voice_symbol(h) is None
    p=list(rock_pose().landmarks);p[4]=(.38,.65,0)
    assert voice_symbol(Hand(tuple(p),.8,"Right")) is None


@pytest.mark.parametrize("kind",["v","thumbs_up","swag","point","scroll","palm","fist"])
def test_old_or_non_start_gestures_never_activate_wispr(kind):
    ses,s,k=session()
    h={"v":pose(spread=True),"thumbs_up":old_thumb_pose(),"swag":rock_pose(extended_thumb=True),
       "point":pose(),"scroll":pose((True,True,True,False)),"palm":pose((True,)*4),"fist":pose((False,)*4)}[kind]
    for i in range(30):ses.process((h,),1.4+i*.05)
    assert not ses.dictating and not k.calls


def test_old_v_and_thumbs_up_cannot_stop_a_latched_rock_session():
    ses,s,k=session()
    for t in (1.4,1.44):ses.process((rock_pose(),),t)
    for i in range(20):ses.process((pose(label="Right",spread=True),),1.5+i*.05)
    for i in range(20):ses.process((old_thumb_pose(),),2.5+i*.05)
    assert ses.dictating and k.calls==[("begin","toggle_ctrl_win")]


@pytest.mark.parametrize("angle",[-60,0,60,90])
@pytest.mark.parametrize("extended_thumb",[False,True])
def test_voice_thumb_state_follows_hand_rotation(angle,extended_thumb):
    h=rock_pose(extended_thumb=extended_thumb);a=math.radians(angle);aspect=4/3
    def rotate(p):
        x,y=(p[0]-.5)*aspect,p[1]-.6
        return (.5+(x*math.cos(a)-y*math.sin(a))/aspect,.6+x*math.sin(a)+y*math.cos(a),p[2])
    h=replace(h,landmarks=tuple(rotate(p) for p in h.landmarks))
    assert voice_symbol(h)==("stop" if extended_thumb else "start")


def test_rock_can_start_a_new_dictation_after_finishing_without_extra_unlock():
    ses,s,k=session()
    for start in (1.4,2.4):
        for t in (start,start+.04):ses.process((rock_pose(label="Right"),),t)
        for t in (start+.1,start+.18):ses.process((rock_pose(extended_thumb=True),),t)
    assert k.calls==[("begin","toggle_ctrl_win"),("finish",)]*2


def test_relaxed_closed_fist_cannot_be_interpreted_as_a_click():
    c,s=controller();arm(c)
    closed=pose((False,False,False,False));closed=replace(closed,ratio=.1)
    for i in range(15):c.process(closed,1.3+i*.033)
    assert not any(e==("left",True) for e in s.events)
