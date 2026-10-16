import math
import pytest
from slateink.mouse_control import HandMouseController,WindowsMouse
from slateink.config import Config
from slateink.calibration import Surface
from slateink.tracking import Hand
from slateink.injection import InjectionError


class Sink:
    def __init__(self):self.events=[]; self.held=set()
    def move(self,x,y):self.events.append(("move",x,y))
    def move_relative(self,x,y):self.events.append(("relative",x,y))
    def wheel(self,vertical=0,horizontal=0):self.events.append(("wheel",vertical,horizontal))
    def button(self,name,down):
        self.events.append((name,down))
        if down:self.held.add(name)
        else:self.held.discard(name)
    def release_all(self):
        for name in tuple(self.held):self.button(name,False)


def hand(left=0.8,right=0.8,x=0.5,label="Left"):
    points=[(0.5,0.5,0)]*21
    points[5]=(x-0.1,0.6,0);points[17]=(x+0.1,0.6,0)
    points[9]=(x,0.6,0)
    points[0]=(x,.83,0);points[6]=(x-.04,.52,0);points[10]=(x+.02,.52,0)
    points[4]=(x,0.5,0);points[8]=(x-left*.2,0.5,0)
    points[12]=(x+right*0.2,0.5,0)
    return Hand(tuple(points),left,label)


def controller():
    sink=Sink(); c=HandMouseController(Config(),sink)
    c.surface=Surface.from_corners([(0.1,0.1),(0.9,0.1),(0.9,0.9),(0.1,0.9)])
    c.set_enabled(True)
    return c,sink


def arm(c):
    c.process(hand(),1.0);c.process(hand(),1.1)


def hold_left(c):
    arm(c);c.process(hand(left=0.2),1.14);c.process(hand(left=0.2),1.22)
    assert c.button_held=="left"


def test_disabled_mouse_never_moves_or_clicks():
    c,s=controller();c.set_enabled(False)
    c.process(hand(left=0.1),1)
    assert s.events==[]


def test_existing_pinch_at_enable_cannot_click():
    c,s=controller()
    c.process(hand(left=0.1),1);c.process(hand(left=0.1),1.2)
    assert s.events==[]


def stick(x=.5,spread=False):
    p=list(hand(x=x).landmarks)
    p[0]=(x,.8,0);p[6]=(x-.04,.45,0);p[10]=(x+.01,.45,0)
    p[8]=(x-.04,.3,0);p[12]=(x+(.13 if spread else .01),.3,0)
    p[4]=(x-.15,.6,0)
    return Hand(tuple(p),.8,"Left")


def test_open_hand_does_not_move_cursor():
    c,s=controller();arm(c)
    c.process(hand(x=0.55),1.15)
    assert s.events==[]
    assert not s.held


def test_touchpad_moves_relative_after_joined_fingers_settle():
    c,s=controller()
    for i in range(18):c.process(stick(.5+max(0,i-5)*.004),1+i*.033)
    assert any(e[0]=="relative" and e[1]>0 for e in s.events)
    assert not any(e[0]=="move" for e in s.events)


def test_stationary_jitter_stays_in_deadzone():
    c,s=controller()
    for i in range(80):c.process(stick(.5+math.sin(i)*.0015),1+i*.033)
    assert s.events==[]


def test_separating_fingers_clutches_and_reacquisition_does_not_jump():
    c,s=controller()
    for i in range(12):c.process(stick(),1+i*.033)
    for i in range(10):c.process(stick(.5+i*.01,spread=True),1.4+i*.033)
    assert not s.events
    for i in range(6):c.process(stick(.59),1.75+i*.033)
    assert not s.events


def test_click_closure_does_not_move_then_held_palm_can_drag():
    c,s=controller();hold_left(c)
    c.process(hand(left=.2,x=.54),1.27)
    assert not any(e[0]=="relative" for e in s.events)
    for i in range(9):c.process(hand(left=.2,x=.54+i*.004),1.42+i*.033)
    assert any(e[0]=="relative" for e in s.events) and s.held=={"left"}


def test_left_pinch_holds_drag_and_release_finishes_once():
    c,s=controller();hold_left(c)
    c.process(hand(left=0.2,x=0.53),1.25)
    c.process(hand(left=0.2,x=0.55),1.28)
    assert s.held=={"left"}
    c.process(hand(left=0.8),1.3);c.process(hand(left=0.8),1.38)
    assert not s.held
    assert s.events.count(("left",True))==s.events.count(("left",False))==1


def test_middle_pinch_right_click_without_left_press():
    c,s=controller();arm(c)
    c.process(hand(right=0.2),1.14);c.process(hand(right=0.2),1.22)
    assert not s.held # right click deliberately needs longer confirmation
    c.process(hand(right=0.2),1.26)
    assert s.held=={"right"}
    c.process(hand(),1.29);c.process(hand(),1.37)
    assert not s.held and ("left",True) not in s.events


@pytest.mark.parametrize("button",["left","right"])
def test_joined_fingers_allow_a_clearly_closer_thumb_target(button):
    c,s=controller();arm(c)
    h=hand(left=.04,right=.25) if button=="left" else hand(left=.25,right=.04)
    p=list(h.landmarks);p[14]=(.6,.52,0);p[16]=(.6,.3,0)
    h=Hand(tuple(p),h.ratio,h.label)
    c.process(h,1.14);c.process(h,1.22)
    c.process(h,1.26)
    assert s.held=={button}


def test_left_click_arms_without_requiring_middle_pinch_to_open_fully():
    c,s=controller()
    c.process(hand(right=.5),1);c.process(hand(right=.5),1.1)
    assert c.left.released and not c.right.released
    c.process(hand(left=.2,right=.5),1.14);c.process(hand(left=.2,right=.5),1.22)
    assert s.held=={"left"}
    c.process(hand(right=.5),1.26);c.process(hand(right=.5),1.34)
    assert s.events==[("left",True),("left",False)]


def test_folded_index_with_straight_middle_resolves_joined_left_pinch():
    c,s=controller();arm(c)
    p=list(hand().landmarks)
    p[0]=(.5,.8,0);p[6]=(.48,.55,0);p[8]=(.48,.58,0)
    p[10]=(.52,.6,0);p[12]=(.52,.5,0);p[4]=(.49,.55,0)
    from slateink.gestures import pinch_ratio
    h=Hand(tuple(p),pinch_ratio(p),"Left")
    c.process(h,1.14);c.process(h,1.22)
    assert s.held=={"left"} and ("right",True) not in s.events


def test_brief_middle_pinch_flicker_does_not_right_click():
    c,s=controller();arm(c)
    c.process(hand(right=.2),1.14);c.process(hand(right=.2),1.22)
    c.process(hand(),1.24);c.process(hand(),1.32)
    assert not s.events and not s.held


def test_right_click_cannot_start_with_an_unarmed_index_pinch():
    c,s=controller()
    c.process(hand(left=.5),1);c.process(hand(left=.5),1.1)
    assert c.right.released and not c.left.released
    for t in (1.14,1.2,1.26):c.process(hand(left=.5,right=.2),t)
    for t in (1.3,1.38):c.process(hand(right=.2),t)
    assert not s.events and not s.held


def test_middle_just_closer_than_index_is_not_a_clear_right_click():
    c,s=controller();arm(c)
    for i in range(8):c.process(hand(left=.4,right=.3),1.14+i*.05)
    assert not s.events and not s.held


def test_swipe_speed_palm_travel_during_pinch_cannot_become_right_click():
    c,s=controller();arm(c)
    c.process(hand(right=.2),1.14)
    c.process(hand(right=.2,x=.57),1.26)
    assert not s.events and not s.held


def test_two_left_pinches_still_deliver_two_clicks_without_right_click():
    c,s=controller();arm(c)
    for start in (1.14,1.4):
        c.process(hand(left=.2),start);c.process(hand(left=.2),start+.08)
        c.process(hand(),start+.12);c.process(hand(),start+.2)
    assert s.events==[("left",True),("left",False)]*2


@pytest.mark.parametrize("fps",[15,24,30,60])
def test_short_index_pinch_is_not_lost_at_normal_camera_rates(fps):
    c,s=controller();dt=1/fps
    for i in range(round(.3*fps)+1):c.process(hand(),1+i*dt)
    for i in range(max(2,round(.1*fps))):c.process(hand(left=.2),1.4+i*dt)
    for i in range(round(.3*fps)+1):c.process(hand(),1.6+i*dt)
    assert s.events==[("left",True),("left",False)]


def test_left_contact_hysteresis_tolerates_threshold_jitter_but_not_a_single_frame():
    c,s=controller();arm(c)
    c.process(hand(left=.2),1.14);c.process(hand(),1.173)
    assert not s.events
    for t,ratio in ((1.21,.3),(1.243,.38),(1.276,.32),(1.31,.4)):
        c.process(hand(left=ratio),t)
    assert s.held=={"left"} and ("right",True) not in s.events


def test_natural_index_pinch_can_keep_other_fingers_curled_without_clicking_a_fist():
    from test_touchpad_product import pose
    from slateink.gestures import pinch_ratio
    c,s=controller();arm(c)
    p=list(pose((False,)*4).landmarks)
    p[4]=(.42,.58,0);p[8]=(.45,.58,0)
    h=Hand(tuple(p),pinch_ratio(p),"Left")
    for t in (1.14,1.18,1.22):c.process(h,t)
    assert s.held=={"left"}


def test_drag_cannot_switch_to_right_button_without_rearm():
    c,s=controller();hold_left(c)
    c.process(hand(left=.8,right=.1),1.25);c.process(hand(left=.8,right=.1),1.33)
    assert not s.held and ("right",True) not in s.events


@pytest.mark.parametrize("reason",["lost","stale","outside","jump","changed","ambiguous","nan"])
def test_interruption_releases_drag_and_requires_rearm(reason):
    c,s=controller();hold_left(c)
    if reason=="lost":c.process(None,1.25)
    elif reason=="stale":c.process(hand(left=0.2),1.25,age=0.3)
    elif reason=="outside":c.process(hand(left=0.2,x=0.99),1.25)
    elif reason=="jump":c.process(hand(left=0.2,x=0.85),1.25)
    elif reason=="changed":c.process(hand(left=0.2,label="Right"),1.25)
    elif reason=="ambiguous":c.process(hand(left=0.2,right=0.2),1.25)
    else:c.process(hand(left=math.nan),1.25)
    assert not s.held and c.button_held is None
    presses=s.events.count(("left",True))
    c.process(hand(left=0.2),1.28);c.process(hand(left=0.2),1.36)
    assert s.events.count(("left",True))==presses


def test_disable_releases_button():
    c,s=controller();hold_left(c);c.set_enabled(False)
    assert not c.enabled and not s.held


def test_right_click_can_be_disabled():
    c,s=controller();c.right_enabled=False;arm(c)
    c.process(hand(right=0.2),1.15);c.process(hand(right=0.2),1.23)
    assert not s.held


def test_native_mouse_absolute_mapping_and_button_flags():
    mouse=object.__new__(WindowsMouse); mouse.held=set(); events=[]
    mouse._event=lambda flags,x=0,y=0:events.append((flags,x,y))
    mouse.move(0.5,1);mouse.button("left",True);mouse.button("left",True)
    mouse.release_all();mouse.button("right",True);mouse.release_all()
    assert events[0]==(0xC001,32768,65535)
    assert [e[0] for e in events[1:]]==[2,4,8,16]


def test_failed_down_keeps_ownership_for_emergency_release():
    mouse=object.__new__(WindowsMouse);mouse.held=set()
    def fail(*args):raise InjectionError("blocked")
    mouse._event=fail
    with pytest.raises(InjectionError):mouse.button("left",True)
    assert mouse.held=={"left"}
