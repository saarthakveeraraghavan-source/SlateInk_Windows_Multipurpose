"""Right-hand reference sweeps, mirroring and cursor-conflict regressions."""
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
from test_touchpad_product import Shortcuts,pose,rock_pose
from test_touchpad_submodes import Pixels


def air_pose(progress=0,mirrored=False,x=.42,y=.55,direction=1):
    """Generic open palm translated as a whole, independently of user footage."""
    x+=progress*.23*direction
    points=[(x,y,0.) for _ in range(21)]
    points[0]=(x,y+.18,0.);points[4]=(x-.16,y+.01,0.)
    for j,(mcp,pip,dip,tip) in enumerate(((5,6,7,8),(9,10,11,12),(13,14,15,16),(17,18,19,20))):
        xx=x+(-.07,0.,.045,.085)[j]
        points[mcp]=(xx,y+(0.,0.,.01,.03)[j],0.)
        points[pip]=(xx,y-.1,0.)
        points[dip]=(xx,y-.2,0.)
        points[tip]=(xx,y-.3+(0.,-.02,.025,.065)[j],0.)
    if mirrored:points=[(1-p[0],p[1],p[2]) for p in points]
    return Hand(tuple(points),1.2,"Left" if mirrored else "Right",.99)


def observed(h):
    return Hand(tuple(tuple(p) for p in h["landmarks"]),h["ratio"],h["label"],h["confidence"])


def prime(swipe,start=1,direction=1,mirrored=False,fps=20,config=None):
    cfg=config or Config(camera_mirrored=mirrored)
    for i in range(round(.2*fps)+1):swipe.update(air_pose(0,mirrored,direction=direction),start+i/fps,cfg,16/9)


def sweep(swipe,start=1.25,direction=1,mirrored=False,fps=20,config=None,amount=1):
    cfg=config or Config(camera_mirrored=mirrored);count=round(.35*fps);result=[]
    for i in range(count+1+math.ceil(.15*fps)):
        result.append(swipe.update(air_pose(min(1,i/count)*amount,mirrored,direction=direction),start+i/fps,cfg,16/9))
    return result


class Switcher:
    def __init__(self):self.events=[]
    def release_all(self):pass
    def switch(self,d):self.events.append(d);return "switched"


@pytest.mark.parametrize("direction",[1,-1])
@pytest.mark.parametrize("mirrored",[True,False])
@pytest.mark.parametrize("fps",[10,15,20,30,60])
def test_open_palm_direction_and_one_event_at_tracking_rates(direction,mirrored,fps):
    swipe=WindowSwipe();prime(swipe,direction=direction,mirrored=mirrored,fps=fps)
    assert swipe.armed
    assert [d for _,d in sweep(swipe,direction=direction,mirrored=mirrored,fps=fps) if d is not None]==[direction]


@pytest.mark.parametrize("angle",[-100,-70,-40,0,40,70,100])
@pytest.mark.parametrize("extended",[(True,True,False,False),(True,True,True,False),(True,False,False,False),(False,)*4])
def test_pointing_scroll_or_folded_hand_at_any_angle_never_captures(extended,angle):
    swipe=WindowSwipe();cfg=Config(camera_mirrored=False)
    for i in range(45):
        h=pose(extended,x=.4+min(i,30)*.004,y=.5,label="Right")
        ox,oy=h.landmarks[0][:2];a=math.radians(angle)
        points=tuple((ox+(x-ox)*math.cos(a)-(y-oy)*math.sin(a),oy+(x-ox)*math.sin(a)+(y-oy)*math.cos(a),z) for x,y,z in h.landmarks)
        assert swipe.update(replace(h,landmarks=points),1+i*.05,cfg)==(False,None)


def test_cursor_still_moves_sideways_with_swipes_enabled():
    cfg=Config(camera_mirrored=False);mouse=Pixels();switcher=Switcher()
    session=TouchpadSession(HandMouseController(cfg,mouse),Shortcuts(),window_switcher=switcher);session.set_enabled(True)
    for i in range(40):session.process((pose(x=.4+i*.004,label="Right"),),1+i*.05)
    assert any(e[0]=="relative" for e in mouse.events) and not switcher.events


def test_one_frame_open_pose_flicker_during_cursor_motion_cannot_swipe():
    cfg=Config(camera_mirrored=False);switcher=Switcher();mouse=Pixels()
    session=TouchpadSession(HandMouseController(cfg,mouse),None,window_switcher=switcher);session.set_enabled(True)
    for i in range(90):
        x=.45+math.sin(i*.1)*.13
        h=air_pose(x=x) if i%8==0 else pose(x=x,label="Right")
        session.process((h,),1+i*.05,aspect=16/9)
    assert not switcher.events


def test_stationary_hand_and_finger_only_motion_do_not_switch():
    swipe=WindowSwipe();prime(swipe)
    for i in range(40):
        h=air_pose(min(1,i/12));points=list(h.landmarks)
        for j in (0,5,9,13,17):points[j]=air_pose().landmarks[j]
        assert swipe.update(replace(h,landmarks=tuple(points)),1.25+i*.05,Config(camera_mirrored=False),16/9)[1] is None


def test_vertical_motion_and_small_horizontal_motion_do_not_switch():
    for vertical in (True,False):
        swipe=WindowSwipe();prime(swipe)
        for i in range(20):
            h=air_pose(y=.55+i*.006) if vertical else air_pose(min(1,i/8)*.2)
            assert swipe.update(h,1.25+i*.05,Config(camera_mirrored=False),16/9)[1] is None


def test_missing_data_never_switches_and_matching_endpoint_is_observed_twice():
    swipe=WindowSwipe();prime(swipe);cfg=Config(camera_mirrored=False)
    for i in range(8):assert swipe.update(None,1.25+i*.05,cfg,16/9)==(True,None)
    assert swipe.update(air_pose(1),1.8,cfg,16/9)==(True,None)
    assert swipe.update(air_pose(1),1.87,cfg,16/9)==(True,1)


def test_gap_timeout_recovers_without_pointing_pose_or_permanent_cancelled_lock():
    swipe=WindowSwipe();prime(swipe);cfg=Config(camera_mirrored=False)
    assert swipe.update(None,2,cfg,16/9)==(False,None)
    prime(swipe,start=2.1)
    assert [d for _,d in sweep(swipe,start=2.35) if d is not None]==[1]
    assert "cancelled" not in swipe.hint.lower() and "finished" not in swipe.hint.lower()


def test_cancel_with_folded_hand_then_open_again_works_without_special_unlock():
    swipe=WindowSwipe();prime(swipe);cfg=Config(camera_mirrored=False)
    assert swipe.update(pose((False,)*4,label="Right"),1.25,cfg,16/9)==(False,None)
    prime(swipe,start=1.3)
    assert [d for _,d in sweep(swipe,start=1.55) if d is not None]==[1]


def test_held_finish_pose_does_not_repeat_after_cooldown():
    swipe=WindowSwipe();prime(swipe);assert [d for _,d in sweep(swipe) if d is not None]==[1]
    for i in range(80):assert swipe.update(air_pose(1),1.85+i*.05,Config(camera_mirrored=False),16/9)[1] is None


def test_opposite_followup_sweep_rearms_automatically_after_cooldown():
    swipe=WindowSwipe();cfg=Config(camera_mirrored=False,touchpad_swipe_cooldown=.4);prime(swipe,config=cfg);sweep(swipe,config=cfg)
    for i in range(14):swipe.update(air_pose(1),1.85+i*.05,cfg,16/9)
    events=[]
    for i in range(14):
        event=swipe.update(air_pose(1-min(1,i/8)),2.55+i*.05,cfg,16/9)[1]
        if event is not None:events.append(event)
    assert events==[-1]


@pytest.mark.parametrize("reason",["stale","duplicate","jump","nan","blocked"])
def test_unsafe_observations_cancel_without_emitting(reason):
    swipe=WindowSwipe();prime(swipe);hand=air_pose(.5);t=1.25;kwargs={}
    if reason=="stale":kwargs["age"]=.3
    elif reason=="duplicate":t=1.2
    elif reason=="jump":hand=air_pose(.5,x=.8)
    elif reason=="nan":hand=air_pose(.5,x=math.nan);kwargs["age"]=.3
    elif reason=="blocked":kwargs["blocked"]=True
    assert swipe.update(hand,t,Config(camera_mirrored=False),16/9,**kwargs)[1] is None
    assert not swipe.armed


@pytest.mark.parametrize("mirrored",[False,True])
def test_physical_left_hand_cannot_switch(mirrored):
    swipe=WindowSwipe();cfg=Config(camera_mirrored=mirrored)
    for i in range(30):
        hand=replace(air_pose(min(1,max(0,(i-7)/8)),mirrored),label="Right" if mirrored else "Left")
        assert swipe.update(hand,1+i*.05,cfg,16/9)==(False,None)


def test_low_confidence_reacquisition_requires_two_fresh_trusted_endpoints():
    swipe=WindowSwipe();prime(swipe);cfg=Config(camera_mirrored=False)
    swipe.update(air_pose(1),1.4,cfg,16/9)
    assert swipe.update(replace(air_pose(1),handedness_confidence=.4),1.46,cfg,16/9)[1] is None
    assert swipe.update(air_pose(1),1.52,cfg,16/9)[1] is None
    assert swipe.update(air_pose(1),1.59,cfg,16/9)[1]==1


def test_sensitivity_changes_travel_but_keeps_minimum_floor():
    for sensitivity,expected in ((.5,False),(2,True)):
        cfg=Config(camera_mirrored=False,touchpad_swipe_sensitivity=sensitivity)
        swipe=WindowSwipe();prime(swipe,config=cfg)
        assert bool(any(d for _,d in sweep(swipe,config=cfg,amount=.65)))==expected


def test_initial_one_frame_wrong_label_can_recover():
    cfg=Config();session=TouchpadSession(HandMouseController(cfg,Pixels()),None,window_switcher=Switcher());session.set_enabled(True)
    session.process((replace(air_pose(),label="Left"),),1,aspect=16/9)
    session.process((air_pose(),),1.07,aspect=16/9)
    assert session.primary.label=="Right" and session.chosen_label=="Right"


def test_confident_duplicate_hands_still_stop_inputs():
    session=TouchpadSession(HandMouseController(Config(),Pixels()),None,window_switcher=Switcher());session.set_enabled(True)
    session.process((air_pose(),air_pose(x=.6)),1,aspect=16/9)
    assert session.primary is None and not session.swipe.capturing


def test_helper_rock_cancels_candidate_before_dictation():
    cfg=Config(camera_mirrored=False,wispr_enabled=True);switcher=Switcher()
    session=TouchpadSession(HandMouseController(cfg,Pixels()),Shortcuts(),window_switcher=switcher);session.set_enabled(True)
    for i in range(6):session.process((air_pose(),),1+i*.05,aspect=16/9)
    assert session.swipe.armed
    session.process((air_pose(.5),rock_pose(label="Left")),1.3,aspect=16/9)
    assert not session.swipe.armed and not switcher.events


def test_right_hand_can_swipe_when_the_other_hand_is_selected_for_cursor():
    cfg=Config(camera_mirrored=False,touchpad_hand="Left",wispr_enabled=True)
    mouse=Pixels();switcher=Switcher();voice=Shortcuts()
    session=TouchpadSession(HandMouseController(cfg,mouse),voice,window_switcher=switcher);session.set_enabled(True)
    for i in range(30):
        right=air_pose(min(1,max(0,(i-7)/9)))
        session.process((pose(label="Left"),right),1+i*.05,aspect=16/9)
    assert switcher.events==[1] and not mouse.events and not voice.calls


def run_clip(clip,cooldown=.4,stride=1):
    cfg=Config(camera_mirrored=clip["mirrored"],wispr_enabled=True,touchpad_swipe_cooldown=cooldown)
    mouse=Pixels();switcher=Switcher();voice=Shortcuts()
    session=TouchpadSession(HandMouseController(cfg,mouse),voice,window_switcher=switcher);session.set_enabled(True)
    for row in clip["rows"][::stride]:session.process(tuple(observed(h) for h in row["hands"]),row["t"]+1,aspect=clip["aspect"])
    return switcher.events,mouse.events,mouse.held,voice.calls


REFERENCES=Path(__file__).parent/"fixtures/right_hand_swipe_reference_landmarks.json"
CLIPS=json.loads(REFERENCES.read_text()) if REFERENCES.exists() else []


@pytest.mark.parametrize("clip",CLIPS,ids=lambda c:c["video"]+str(c["mirrored"]))
@pytest.mark.parametrize("cooldown",[.4,.8])
def test_actual_new_right_hand_references_emit_named_action_once_without_other_inputs(clip,cooldown):
    events,mouse,held,voice=run_clip(clip,cooldown)
    assert events==[clip["expected_direction"]] and not mouse and not held and not voice


@pytest.mark.parametrize("clip",CLIPS,ids=lambda c:c["video"]+str(c["mirrored"]))
def test_sparse_reference_tracking_never_emits_opposite_or_duplicate_action(clip):
    events,mouse,held,voice=run_clip(clip,stride=2)
    assert events in ([],[clip["expected_direction"]]) and not held and not voice


def test_video_reference_hashes_match_current_files():
    import hashlib
    root=Path(__file__).resolve().parents[1]
    for clip in CLIPS:
        original=root/clip["video"]
        if original.exists():assert hashlib.sha256(original.read_bytes()).hexdigest()==clip["sha256"]


def test_former_fist_gesture_is_no_longer_a_window_command():
    clips=json.loads((Path(__file__).parent/"fixtures/fist_swipe_synthetic.json").read_text())
    assert all(not run_clip(c)[0] for c in clips)


@pytest.mark.parametrize("clip",json.loads((Path(__file__).parent/"fixtures/open_palm_swipe_synthetic.json").read_text()),ids=lambda c:c["name"]+str(c["mirrored"]))
def test_portable_open_palm_samples_switch_once_without_other_inputs(clip):
    events,mouse,held,voice=run_clip(clip)
    assert events==[clip["expected_direction"]] and not mouse and not held and not voice


@pytest.mark.parametrize("mirrored",[True,False])
@pytest.mark.parametrize("direction",[1,-1])
def test_fast_reverse_with_one_starting_observation_and_two_end_observations(mirrored,direction):
    cfg=Config(camera_mirrored=mirrored);swipe=WindowSwipe()
    h=replace(air_pose(mirrored=mirrored,direction=direction),handedness_confidence=.68)
    assert swipe.update(h,1,cfg,16/9)[1] is None
    assert swipe.update(None,1.15,cfg,16/9)[1] is None
    end=replace(air_pose(1,mirrored,direction=direction),handedness_confidence=.68)
    assert swipe.update(end,1.4,cfg,16/9)[1] is None
    assert swipe.update(end,1.47,cfg,16/9)[1]==direction


def test_reversal_can_begin_during_cooldown_without_losing_its_start():
    cfg=Config(camera_mirrored=False,touchpad_swipe_cooldown=.4);swipe=WindowSwipe()
    prime(swipe,config=cfg);sweep(swipe,config=cfg)
    until=swipe.cooldown_until;events=[]
    swipe.update(air_pose(1),until-.25,cfg,16/9)
    for i in range(15):
        event=swipe.update(air_pose(1-min(1,i/8)),until-.2+i*.05,cfg,16/9)[1]
        if event is not None:events.append(event)
    assert events==[-1]


def test_no_observed_start_cannot_invent_a_reverse_swipe():
    swipe=WindowSwipe();cfg=Config(camera_mirrored=False)
    for i in range(25):assert swipe.update(air_pose(1),1+i*.05,cfg,16/9)[1] is None


def test_pinch_immediately_after_swipe_is_not_a_right_click_and_left_recovers():
    from test_mouse_control import hand
    cfg=Config(camera_mirrored=False);mouse=Pixels();switcher=Switcher()
    session=TouchpadSession(HandMouseController(cfg,mouse),None,window_switcher=switcher);session.set_enabled(True)
    session.process((air_pose(),),1,aspect=16/9)
    session.process((air_pose(.6),),1.1,aspect=16/9)
    # Closing after actual palm travel can resemble a middle pinch.
    for t in (1.15,1.21,1.27):session.process((hand(right=.2,label="Right"),),t,aspect=16/9)
    assert not mouse.events
    for t in (1.4,1.48):session.process((hand(label="Right"),),t,aspect=16/9)
    for t in (1.52,1.6):session.process((hand(left=.2,label="Right"),),t,aspect=16/9)
    assert mouse.held=={"left"} and ("right",True) not in mouse.events


@pytest.mark.parametrize("mirrored",[False,True])
def test_stationary_open_hand_arms_clicks_with_swipes_enabled(mirrored):
    from test_mouse_control import hand
    from slateink.gestures import pinch_ratio
    mouse=Pixels();switcher=Switcher();cfg=Config(camera_mirrored=mirrored)
    session=TouchpadSession(HandMouseController(cfg,mouse),None,window_switcher=switcher);session.set_enabled(True)
    for i in range(8):session.process((air_pose(mirrored=mirrored),),1+i*.033,aspect=16/9)
    assert session.controller.left.released
    h=hand(left=.2,label="Left" if mirrored else "Right")
    if mirrored:
        p=tuple((1-x,y,z) for x,y,z in h.landmarks)
        h=replace(h,landmarks=p,ratio=pinch_ratio(p,16/9))
    for t in (1.28,1.314):session.process((h,),t,aspect=16/9)
    assert mouse.held=={"left"} and not switcher.events
