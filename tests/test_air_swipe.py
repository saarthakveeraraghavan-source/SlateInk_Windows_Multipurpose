"""Generic synthetic strokes and daily-use gesture arbitration."""
from dataclasses import replace
import json
import math
from pathlib import Path
import pytest
from slateink.config import Config
from slateink.tracking import Hand
from slateink.air_swipe import WindowSwipe,swipe_hand
from slateink.mouse_control import HandMouseController
from slateink.touchpad_session import TouchpadSession
from slateink.hand_gestures import fingers
from test_touchpad_product import Shortcuts,pose
from test_touchpad_submodes import Pixels

CLIPS=json.loads((Path(__file__).parent/"fixtures/natural_swipe_reference_landmarks.json").read_text())
RAW_NEXT=next(c for c in CLIPS if c["video"].startswith("Next") and not c["mirrored"])
RAW_PREVIOUS=next(c for c in CLIPS if c["video"].startswith("Previous") and not c["mirrored"])


def observed(h):
    return Hand(tuple(tuple(p) for p in h["landmarks"]),h["ratio"],h["label"],h["confidence"])


def air_pose(progress=0,mirrored=False,x=.5,y=.65,direction=1):
    source=RAW_NEXT if direction==1 else RAW_PREVIOUS
    a=observed(source["rows"][18 if direction==1 else 10]["hands"][0])
    b=observed(source["rows"][26 if direction==1 else 16]["hands"][0])
    points=[tuple((1-progress)*p[i]+progress*q[i] for i in range(3)) for p,q in zip(a.landmarks,b.landmarks)]
    ox,oy=points[0][:2];points=[(p[0]-ox+x,p[1]-oy+y,p[2]) for p in points]
    if mirrored:points=[(1-p[0],p[1],p[2]) for p in points]
    return Hand(tuple(points),(1-progress)*a.ratio+progress*b.ratio,"Left" if mirrored else "Right",.99)


def prime(swipe,start=1,direction=1,mirrored=False,fps=20,config=None):
    cfg=config or Config(camera_mirrored=mirrored)
    for i in range(round(.25*fps)+1):
        swipe.update(air_pose(0,mirrored,direction=direction),start+i/fps,cfg,16/9)


def sweep(swipe,start=1.3,direction=1,mirrored=False,fps=20,config=None,amount=1):
    cfg=config or Config(camera_mirrored=mirrored);count=round(.35*fps);result=[]
    for i in range(count+1+math.ceil(.15*fps)):
        progress=min(1,i/count)*amount
        result.append(swipe.update(air_pose(progress,mirrored,direction=direction),start+i/fps,cfg,16/9))
    return result


class Switcher:
    def __init__(self):self.events=[]
    def release_all(self):pass
    def switch(self,d):self.events.append(d);return "switched"


@pytest.mark.parametrize("clip",CLIPS,ids=lambda c:c["video"]+str(c["mirrored"]))
@pytest.mark.parametrize("stride",[1,2])
def test_synthetic_replay_emits_named_action_without_pointer_click_scroll_or_voice(clip,stride):
    mouse=Pixels();switcher=Switcher();voice=Shortcuts()
    config=Config(camera_mirrored=clip["mirrored"],wispr_enabled=True)
    session=TouchpadSession(HandMouseController(config,mouse),voice,window_switcher=switcher)
    session.set_enabled(True)
    for row in clip["rows"][::stride]:
        session.process(tuple(observed(h) for h in row["hands"]),row["t"]+1,aspect=clip["aspect"])
    expected=[1] if clip["video"].startswith("Next") else [-1]
    if stride==1:assert switcher.events==expected
    else:assert switcher.events in ([],expected) # insufficient observations must stay safe
    assert not mouse.events and not mouse.held and not voice.calls


@pytest.mark.parametrize("direction",[1,-1])
@pytest.mark.parametrize("mirrored",[True,False])
@pytest.mark.parametrize("fps",[10,15,20,30])
def test_air_swipe_direction_and_one_event_at_low_tracking_rates(direction,mirrored,fps):
    swipe=WindowSwipe();prime(swipe,direction=direction,mirrored=mirrored,fps=fps)
    assert [d for _,d in sweep(swipe,direction=direction,mirrored=mirrored,fps=fps) if d is not None]==[direction]


def test_stationary_relaxed_hand_does_not_switch_and_requires_no_open_palm():
    hand=air_pose();assert not all(fingers(hand,16/9))
    swipe=WindowSwipe();prime(swipe)
    for i in range(30):assert swipe.update(hand,1.3+i*.05,Config(camera_mirrored=False),16/9)[1] is None
    assert [d for _,d in sweep(swipe,start=2.8) if d is not None]==[1]


def test_upright_mouse_and_scroll_shapes_do_not_enter_swipe_capture():
    swipe=WindowSwipe()
    for extended in ((True,True,False,False),(True,True,True,False)):
        for i in range(10):
            assert swipe.update(pose(extended,x=.5+i*.01),1+i*.05,Config())[0] is False


def test_small_air_motion_cannot_switch():
    swipe=WindowSwipe();prime(swipe)
    assert not any(d for _,d in sweep(swipe,amount=.2))


def test_folded_relaxed_hand_can_swipe_without_opening_palm():
    swipe=WindowSwipe();cfg=Config(camera_mirrored=False)
    for i in range(5):swipe.update(pose((False,)*4),1+i*.05,cfg)
    events=[]
    for i in range(12):
        _,event=swipe.update(pose((False,)*4,x=.5+min(i,8)*.025),1.25+i*.05,cfg)
        if event is not None:events.append(event)
    assert events==[1]


def test_vertical_arm_motion_is_not_a_window_swipe():
    swipe=WindowSwipe();cfg=Config(camera_mirrored=False);prime(swipe,config=cfg)
    for i in range(10):
        assert swipe.update(air_pose(y=.65+i*.01),1.3+i*.05,cfg,16/9)[1] is None


def test_cooldown_survives_reset_and_stationary_finish_does_not_repeat():
    swipe=WindowSwipe();prime(swipe);sweep(swipe)
    assert swipe.cooldown_until>2
    for i in range(30):assert swipe.update(air_pose(1),1.9+i*.05,Config(camera_mirrored=False),16/9)[1] is None
    swipe.reset();swipe.cooldown_until=5
    prime(swipe,start=4)
    assert not swipe.armed


def test_one_missed_frame_is_bridged_but_never_emits_on_missing_data():
    swipe=WindowSwipe();prime(swipe)
    assert swipe.update(None,1.3,Config(camera_mirrored=False),16/9)==(True,None)
    assert [d for _,d in sweep(swipe,start=1.35) if d is not None]==[1]
    swipe=WindowSwipe();prime(swipe)
    for t in (1.3,1.4,1.5):assert swipe.update(None,t,Config(),16/9)[1] is None
    assert not swipe.capturing


@pytest.mark.parametrize("reason",["stale","gap","duplicate","jump","confidence","nan","blocked"])
def test_unsafe_tracking_discards_swipe(reason):
    swipe=WindowSwipe();prime(swipe)
    hand=air_pose(1);t=1.3;kwargs={}
    if reason=="stale":kwargs["age"]=.3
    elif reason=="gap":t=1.6
    elif reason=="duplicate":t=1.25
    elif reason=="jump":hand=air_pose(1,x=.8)
    elif reason=="confidence":hand=replace(hand,handedness_confidence=.4)
    elif reason=="nan":hand=air_pose(1,x=math.nan)
    elif reason=="blocked":kwargs["blocked"]=True
    assert swipe.update(hand,t,Config(),16/9,**kwargs)[1] is None
    assert not swipe.armed


def test_initial_one_frame_wrong_label_does_not_lock_out_previous_hand():
    config=Config();session=TouchpadSession(HandMouseController(config,Pixels()),None,window_switcher=Switcher());session.set_enabled(True)
    session.process((replace(air_pose(1),label="Left"),),1,aspect=16/9)
    session.process((air_pose(1),),1.07,aspect=16/9)
    assert session.primary.label=="Right" and session.chosen_label=="Right"


def test_confident_duplicate_hands_still_stop_inputs():
    session=TouchpadSession(HandMouseController(Config(),Pixels()),None,window_switcher=Switcher());session.set_enabled(True)
    session.process((air_pose(),air_pose(x=.7)),1,aspect=16/9)
    assert session.primary is None and not session.swipe.capturing


def test_sensitivity_controls_required_travel():
    for sensitivity,expected in ((.5,False),(2,True)):
        cfg=Config(camera_mirrored=False,touchpad_swipe_sensitivity=sensitivity)
        swipe=WindowSwipe();prime(swipe,config=cfg)
        assert bool(any(d for _,d in sweep(swipe,config=cfg,amount=.65)))==expected
