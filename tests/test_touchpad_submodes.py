from dataclasses import replace
from types import SimpleNamespace
import ctypes
import math
import pytest
from slateink.config import Config
from slateink.injection import INPUT,InjectionError
from slateink.mouse_control import WindowsMouse,HandMouseController
from slateink.touchpad_session import TouchpadSession
from slateink.touchpad_submodes import GamingController,DrawingController,WindowsMovementKeys
from test_touchpad_product import pose,Shortcuts
from test_mouse_control import Sink,hand


class Pixels(Sink):
    def pixel_scale(self):return 1080
    def move_pixels(self,x,y):self.events.append(("pixels",x,y))


class Keys:
    def __init__(self):self.held=set();self.events=[];self.focus=(123,456)
    def target(self):return self.focus
    def key(self,key,down):
        self.events.append((key,down))
        if down:self.held.add(key)
        else:self.held.discard(key)
    def release_all(self):
        for key in tuple(self.held):self.key(key,False)


def gaming():
    k=Keys();g=GamingController(Config(),k)
    for i in range(6):g.process(pose((False,)*4),1+i*.033)
    for i in range(12):g.process(pose((True,)*4),1.2+i*.033)
    assert g.center is not None and not k.held
    return g,k


def steer(g,x=.5,y=.65,start=1.6):
    for i in range(14):g.process(pose((True,)*4,x=x,y=y),start+i*.033)


def test_fist_opening_through_partial_poses_can_center_and_steer():
    k=Keys();g=GamingController(Config(),k)
    for i in range(6):g.process(pose((False,)*4),1+i*.033)
    for i in range(5):g.process(pose((True,False,False,False)),1.2+i*.033)
    for i in range(14):g.process(pose((True,)*4),1.4+i*.033)
    steer(g,y=.75,start=1.9)
    assert k.held=={"W"}


@pytest.mark.parametrize("dx,dy,expected",[(0,-.1,{"S"}),(-.1,0,{"A"}),(0,.1,{"W"}),(.1,0,{"D"}),(-.1,-.1,{"A","S"}),(.1,-.1,{"D","S"}),(.1,.1,{"D","W"}),(-.1,.1,{"A","W"})])
def test_joystick_directions_and_diagonals(dx,dy,expected):
    g,k=gaming();steer(g,.5+dx,.65+dy)
    assert k.held==expected
    assert len(k.events)==len(expected) # held keys are not repeated every frame


def test_initial_steady_palm_centers_without_fist_and_never_moves_at_center():
    k=Keys();g=GamingController(Config(),k)
    for i in range(50):g.process(pose((True,)*4,x=.6),1+i*.033)
    assert not k.events and g.center is not None


def test_fist_stops_immediately_and_recenters_at_new_location():
    g,k=gaming();steer(g,y=.75);assert k.held=={"W"}
    g.process(pose((False,)*4,y=.75),2.1);assert not k.held
    for i in range(6):g.process(pose((False,)*4,x=.58),2.14+i*.033)
    for i in range(12):g.process(pose((True,)*4,x=.58),2.36+i*.033)
    assert g.center[0]==pytest.approx(.58*4/3) and not k.held


def test_center_stops_and_direction_reversal_never_holds_opposites():
    g,k=gaming();steer(g,x=.6);steer(g,x=.5,start=2.1);assert not k.held
    steer(g,x=.4,start=2.6);assert k.held=={"A"}
    states=set()
    for key,down in k.events:
        if down:states.add(key)
        else:states.discard(key)
        assert not {"A","D"}<=states and not {"W","S"}<=states


@pytest.mark.parametrize("reason",["lost","stale","jump","gap","partial","focus","own"])
def test_gaming_interrupt_releases_and_steady_palm_can_recenter(reason):
    g,k=gaming();steer(g,y=.75);assert k.held
    h=pose((True,)*4,y=.75);t=2.1;age=0
    if reason=="lost":h=None
    elif reason=="stale":age=.3
    elif reason=="jump":h=pose((True,)*4,x=.8,y=.75)
    elif reason=="gap":t=3
    elif reason=="partial":h=pose((True,False,False,False))
    elif reason=="focus":k.focus=(789,456)
    elif reason=="own":k.focus=None
    g.process(h,t,age);assert not k.held
    k.focus=(123,456)
    for i in range(15):g.process(pose((True,)*4),t+.04+i*.033)
    assert not k.held and g.center is not None


def drawing(aspect=4/3):
    s=Pixels();d=DrawingController(Config(),s)
    for i in range(7):d.process(pose(),1+i*.033,aspect=aspect)
    for i in range(5):d.process(pose((True,False,False,False)),1.25+i*.033,aspect=aspect)
    assert s.held=={"left"}
    s.events.clear();return d,s


def test_index_alone_on_enable_cannot_start_ink():
    s=Pixels();d=DrawingController(Config(),s)
    for i in range(30):d.process(pose((True,False,False,False)),1+i*.033)
    assert not s.events and not d.held


def test_ink_requires_no_pinch_and_middle_finger_lifts_immediately():
    d,s=drawing();assert d.held
    d.process(pose(),1.45)
    assert not s.held and not d.held and s.events.count(("left",False))==1
    for i in range(10):d.process(pose(x=.5+i*.003),1.5+i*.033)
    assert any(e[0]=="pixels" for e in s.events) and ("left",True) not in s.events


@pytest.mark.parametrize("aspect",[4/3,16/9,.75])
def test_equal_camera_pixel_strokes_have_equal_screen_lengths(aspect):
    lengths=[]
    for vx,vy in ((1,0),(0,1),(math.sqrt(.5),math.sqrt(.5))):
        d,s=drawing(aspect)
        for i in range(1,31):
            d.process(pose((True,False,False,False),x=.5+i*.002*vx/aspect,y=.65+i*.002*vy),1.42+i*.033,aspect=aspect)
        dx=sum(e[1] for e in s.events if e[0]=="pixels")
        dy=sum(e[2] for e in s.events if e[0]=="pixels")
        lengths.append(hypot(dx,dy))
    assert max(lengths)-min(lengths)<2


from math import hypot


def test_folded_reposition_has_no_cursor_jump_and_no_ink_bridge():
    d,s=drawing();d.process(pose((False,)*4),1.45);assert not s.held
    for i in range(12):d.process(pose((False,)*4,x=.5+i*.01),1.5+i*.033)
    before=len(s.events)
    for i in range(8):d.process(pose(x=.61),1.92+i*.033)
    assert len(s.events)==before


@pytest.mark.parametrize("reason",["lost","stale","jump","label","outside","nan","gap","focus"])
def test_drawing_interruption_lifts_and_requires_hover(reason):
    d,s=drawing();d.focus=lambda:(12,34);d.target=(12,34)
    h=pose((True,False,False,False));age=0;t=1.45
    if reason=="lost":h=None
    elif reason=="stale":age=.3
    elif reason=="jump":h=pose((True,False,False,False),x=.8)
    elif reason=="label":h=replace(h,label="Right")
    elif reason=="outside":h=pose((True,False,False,False),x=.99)
    elif reason=="nan":h=pose((True,False,False,False),x=math.nan)
    elif reason=="gap":t=2
    elif reason=="focus":d.focus=lambda:(99,34)
    d.process(h,t,age);assert not s.held and not d.armed
    for i in range(6):d.process(pose((True,False,False,False)),t+.04+i*.033)
    assert ("left",True) not in s.events


def test_gaming_fixed_right_mouse_roles_ignore_detection_order_and_disable_wispr():
    s=Pixels();k=Keys();c=HandMouseController(Config(touchpad_submode="gaming",wispr_enabled=True,touchpad_hand="Left"),s)
    flow=Shortcuts();ses=TouchpadSession(c,flow,k);ses.set_enabled(True)
    for i in range(35):ses.process((pose(spread=True,label="Left"),pose(label="Right")),1+i*.033)
    assert ses.primary.label=="Left" and ses.helper.label=="Right" and not flow.calls


def test_gaming_unmirrored_roles():
    c=HandMouseController(Config(touchpad_submode="gaming",camera_mirrored=False),Pixels())
    ses=TouchpadSession(c,None,Keys())
    right,left=ses.choose_hands((pose(label="Right"),pose(label="Left")))
    assert right.label=="Right" and left.label=="Left"


@pytest.mark.parametrize("reason",["stop","stale","ambiguous","right_lost","focus"])
def test_session_releases_mouse_and_keyboard_together(reason):
    s=Pixels();k=Keys();c=HandMouseController(Config(touchpad_submode="gaming"),s)
    ses=TouchpadSession(c,None,k);ses.set_enabled(True)
    ses.gaming.target=k.focus;s.button("left",True);c.button_held="left";k.key("W",True)
    hands=(pose((True,)*4,label="Right"),pose(label="Left"))
    if reason=="stop":ses.set_enabled(False)
    elif reason=="stale":ses.process(hands,1,age=.3)
    elif reason=="ambiguous":ses.process((pose(),pose()),1)
    elif reason=="right_lost":ses.process((pose(label="Right"),),1)
    else:k.focus=(999,456);ses.process(hands,1)
    assert not s.held and not k.held


def test_native_scan_codes_hold_release_and_failed_press_ownership():
    b=object.__new__(WindowsMovementKeys);b.held=set();events=[]
    def send(count,pointer,size):
        event=ctypes.cast(pointer,ctypes.POINTER(INPUT)).contents
        events.append((event.ki.wVk,event.ki.wScan,event.ki.dwFlags));return 1
    b.api=SimpleNamespace(SendInput=send)
    b.key("W",True);b.key("W",True);b.release_all()
    assert events==[(0,0x11,8),(0,0x11,10)] and not b.held
    b.api.SendInput=lambda *args:0
    with pytest.raises(InjectionError):b.key("A",True)
    assert b.held=={"A"}
    b.api.SendInput=send;b.release_all();assert not b.held


def test_native_pixel_mapping_compensates_desktop_aspect():
    b=object.__new__(WindowsMouse);events=[]
    b.api=SimpleNamespace(GetSystemMetrics=lambda i:{78:3440,79:1440,1:1440}[i])
    b.move_relative=lambda x,y:events.append((x,y))
    b.move_pixels(50,50)
    assert events==[(50/3439,50/1439)] and b.pixel_scale()==1440


@pytest.mark.parametrize("options",[{"touchpad_submode":"invalid"},{"drawing_sensitivity":.1},{"gaming_radius":.01}])
def test_submode_config_rejects_invalid_settings(options):
    with pytest.raises(ValueError):Config(**options)


@pytest.mark.parametrize("mirrored",[False,True])
@pytest.mark.parametrize("physical_hand",["Left","Right"])
def test_installed_tracker_orientation_routes_actual_public_fixture(mirrored,physical_hand):
    """Real model + camera transform; no presumed synthetic handedness labels."""
    import cv2
    import time
    from slateink.tracking import HandTracker
    from slateink.orientation import orient_frame
    from slateink.config import ROOT
    image=cv2.imread(str(ROOT/"artifacts/public-hand.jpg"))
    if image is None:pytest.skip("Public MediaPipe pointing-up fixture is unavailable")
    # The public photo shows the subject's left arm; reflection gives the
    # corresponding right-arm fixture before the camera's mirror transform.
    if physical_hand=="Right":image=cv2.flip(image,1)
    image=cv2.cvtColor(orient_frame(image,mirrored),cv2.COLOR_BGR2RGB)
    tracker=HandTracker(ROOT/"models/hand_landmarker.task")
    try:hands,_=tracker.detect_all(image,time.monotonic())
    finally:tracker.close()
    assert len(hands)==1
    c=HandMouseController(Config(touchpad_submode="gaming",camera_mirrored=mirrored),Pixels())
    mouse,joystick=TouchpadSession(c,None,Keys()).choose_hands(hands)
    assert (mouse is hands[0] and joystick is None) if physical_hand=="Right" else (joystick is hands[0] and mouse is None)


@pytest.mark.parametrize("mirrored",[False,True])
def test_left_joystick_and_right_mouse_work_independently_and_click(mirrored):
    s=Pixels();k=Keys();c=HandMouseController(Config(touchpad_submode="gaming",camera_mirrored=mirrored),s)
    ses=TouchpadSession(c,None,k);ses.set_enabled(True)
    mouse_label="Left" if mirrored else "Right";joystick_label="Right" if mirrored else "Left"
    right=pose(x=.72,label=mouse_label)
    for i in range(6):ses.process((pose((False,)*4,x=.32,label=joystick_label),right),1+i*.033)
    for i in range(12):ses.process((right,pose((True,)*4,x=.32,label=joystick_label)),1.2+i*.033)
    s.events.clear()
    for i in range(14):ses.process((pose((True,)*4,x=.32,y=.75,label=joystick_label),right),1.6+i*.033)
    assert k.held=={"W"} and not any(e[0]=="relative" for e in s.events)
    for i in range(14):ses.process((pose(x=.72+i*.003,label=mouse_label),pose((True,)*4,x=.32,y=.75,label=joystick_label)),2.1+i*.033)
    assert k.held=={"W"} and any(e[0]=="relative" and e[1]>0 for e in s.events)
    for i in range(5):ses.process((hand(left=.2,x=.75,label=mouse_label),pose((True,)*4,x=.32,y=.75,label=joystick_label)),2.6+i*.033)
    assert s.held=={"left"} and k.held=={"W"}
    ses.interrupt();assert not s.held and not k.held


def click_pose(ratio=.15,x=.5):
    h=pose(x=x) # middle stays extended; index bends toward thumb
    points=list(h.landmarks);points[8]=(x-.17,.61,0)
    return replace(h,landmarks=tuple(points),ratio=ratio)


def hover_drawing():
    s=Pixels();d=DrawingController(Config(),s)
    for i in range(8):d.process(pose(),1+i*.033)
    assert d.armed and d.click.released
    return d,s


def test_drawing_thumb_index_click_freezes_cursor_and_never_draws():
    d,s=hover_drawing()
    for i in range(12):d.process(click_pose(x=.5+i*.003),1.3+i*.033)
    assert s.held=={"left"} and d.click_held and not d.held
    assert s.events==[("left",True)]
    for i in range(8):d.process(pose(),1.72+i*.033)
    assert s.events==[("left",True),("left",False)] and not d.clicking and not d.held


def test_drawing_release_to_index_only_never_starts_accidental_ink():
    d,s=hover_drawing()
    for i in range(5):d.process(click_pose(),1.3+i*.033)
    for i in range(10):d.process(pose((True,False,False,False),x=.5+i*.002),1.5+i*.033)
    assert not s.held and not d.held and d.clicking
    assert s.events==[("left",True),("left",False)]
    for i in range(7):d.process(pose(),1.85+i*.033)
    for i in range(5):d.process(pose((True,False,False,False)),2.1+i*.033)
    assert d.held and s.held=={"left"}


def test_drawing_initial_pinch_and_closed_fist_cannot_click():
    s=Pixels();d=DrawingController(Config(),s)
    for i in range(20):d.process(click_pose(),1+i*.033)
    assert not s.events
    d,s=hover_drawing()
    for i in range(20):d.process(replace(pose((False,)*4),ratio=.1),1.3+i*.033)
    assert not s.events


def test_drawing_pinch_ends_ink_and_resets_motion_reference():
    d,s=drawing()
    for i in range(5):d.process(click_pose(),1.45+i*.033)
    assert s.events==[("left",False),("left",True)] and d.click_held and not d.held
    assert d.reference is None


@pytest.mark.parametrize("reason",["lost","stale","focus","stop"])
def test_drawing_click_releases_on_every_interruption(reason):
    d,s=hover_drawing()
    for i in range(5):d.process(click_pose(),1.3+i*.033)
    assert d.click_held
    if reason=="lost":d.process(None,1.5)
    elif reason=="stale":d.process(click_pose(),1.5,age=.3)
    elif reason=="focus":d.focus=lambda:None;d.process(click_pose(),1.5)
    else:d.interrupt()
    assert not d.click_held and not d.held and not s.held and not d.armed


def test_joystick_accepts_relaxed_little_finger_and_thumb():
    k=Keys();g=GamingController(Config(),k)
    for i in range(13):g.process(replace(pose((True,True,True,False)),ratio=.5),1+i*.033)
    assert g.center is not None
    for i in range(14):g.process(replace(pose((True,True,True,False),y=.75),ratio=.5),1.5+i*.033)
    assert k.held=={"W"}


def test_game_right_joined_fingers_with_other_fingers_extended_does_not_pause():
    s=Pixels();k=Keys();c=HandMouseController(Config(touchpad_submode="gaming"),s)
    ses=TouchpadSession(c,None,k);ses.set_enabled(True)
    for i in range(15):ses.process((pose((True,)*4,label="Left",x=.72),pose((True,)*4,label="Right",x=.32)),1+i*.033)
    for i in range(45):ses.process((pose((True,)*4,label="Left",x=.72),pose((True,)*4,label="Right",x=.32,y=.75)),1.55+i*.033)
    assert k.held=={"W"} and not ses.paused


def test_optional_drawing_helper_motion_cannot_change_ink_pixels():
    sequences=[]
    for split in (False,True):
        s=Pixels();d=DrawingController(Config(),s)
        for i in range(8):d.process(pose(),1+i*.033,click_hand=pose(label="Right"),split_click=split)
        for i in range(34):
            right=pose((True,False,False,False),x=.5+max(0,i-5)*.002,y=.65+max(0,i-5)*.001)
            helper=pose(x=.32+i*.004,label="Right")
            d.process(right,1.3+i*.033,click_hand=helper,split_click=split)
        sequences.append(s.events)
    assert sequences[0]==sequences[1]


def two_hand_drawing():
    s=Pixels();k=Keys();c=HandMouseController(Config(touchpad_submode="drawing",drawing_two_hand=True),s)
    ses=TouchpadSession(c,None,k);ses.set_enabled(True)
    for i in range(8):ses.process((pose(x=.72,label="Left"),pose(x=.32,label="Right")),1+i*.033)
    assert ses.primary.label=="Left" and ses.helper.label=="Right"
    return ses,s


def test_two_hand_drawing_left_pinch_clicks_without_right_cursor_motion():
    ses,s=two_hand_drawing()
    for i in range(10):ses.process((pose(x=.72+i*.002,label="Left"),replace(click_pose(x=.32),label="Right")),1.3+i*.033)
    assert s.events==[("left",True)] and ses.button_held=="left"
    for i in range(8):ses.process((pose(x=.72,label="Left"),pose(x=.32,label="Right")),1.66+i*.033)
    assert s.events==[("left",True),("left",False)] and not s.held


def test_two_hand_click_lifts_existing_right_ink_and_loss_releases_click():
    ses,s=two_hand_drawing()
    for i in range(6):ses.process((pose((True,False,False,False),x=.72,label="Left"),pose(x=.32,label="Right")),1.3+i*.033)
    assert s.held=={"left"} and ses.drawing.held
    for i in range(7):ses.process((pose((True,False,False,False),x=.72,label="Left"),replace(click_pose(x=.32),label="Right")),1.53+i*.033)
    assert s.events==[("left",True),("left",False),("left",True)] and not ses.drawing.held
    ses.process((pose(x=.72,label="Left"),),1.8)
    assert not s.held and not ses.drawing.click_held


def test_two_hand_helper_initial_pinch_cannot_click_until_opened():
    s=Pixels();d=DrawingController(Config(),s)
    for i in range(9):d.process(pose(),1+i*.033,split_click=True)
    for i in range(9):d.process(pose(),1.35+i*.033,click_hand=click_pose(),split_click=True)
    assert not s.events


def test_default_drawing_still_uses_first_shown_hand_and_helper_never_clicks():
    s=Pixels();c=HandMouseController(Config(touchpad_submode="drawing"),s)
    ses=TouchpadSession(c,None,Keys());ses.set_enabled(True)
    for i in range(8):ses.process((pose(label="Right"),),1+i*.033)
    for i in range(9):ses.process((pose(label="Right"),click_pose()),1.3+i*.033)
    assert ses.primary.label=="Right" and not s.events and not ses.config.drawing_two_hand
