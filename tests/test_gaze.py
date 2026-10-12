from dataclasses import replace
import math
import numpy as np
import pytest
from slateink.gaze import GazeCalibration,GazeController
from slateink.eye_tracking import EyeObservation,eye_features
from slateink.config import Config
from test_mouse_control import Sink,hand


def observation(x=.5,y=.5,noise=0):
    return EyeObservation((.35+.2*x+noise,.03*(y-.5)+noise,.65-.2*x-noise,-.03*(y-.5)-noise),(.5,.5,.2),((.4,.4),(.6,.4)),True)


def samples(x,y):return [observation(x,y,math.sin(i)*.0001) for i in range(18)]


def calibration():
    c=GazeCalibration()
    for y in (.1,.5,.9):
        for x in (.1,.5,.9):c.add(samples(x,y),(x,y))
    c.fit();return c


def checks(offset=0):
    return [(samples(x,y),(x+offset,y)) for x,y in ((.25,.25),(.75,.3),(.35,.7),(.7,.75),(.5,.6))]


def test_synthetic_calibration_requires_independent_check():
    c=calibration();assert not c.validated
    assert np.linalg.norm(np.array(c.predict(observation(.75,.3)))-[.75,.3])<.01
    report=c.validate(checks(),1920,1080)
    assert report["passed"] and report["median_error_px"]<10


def test_bad_accuracy_and_incomplete_validation_block_control():
    c=calibration();assert not c.validate(checks(.2),1920,1080)["passed"]
    c.validate(checks(),1920,1080)
    with pytest.raises(ValueError):c.validate(checks()[:1],1920,1080)
    assert not c.validated


@pytest.mark.parametrize("o",[None,replace(observation(),valid=False),replace(observation(),head=(.7,.5,.2)),replace(observation(),head=(.5,.5,.3)),replace(observation(),head=(math.nan,.5,.2)),replace(observation(),features=(math.nan,0,0,0))])
def test_unusable_eyes_head_motion_or_nonfinite_features_block_prediction(o):
    assert calibration().predict(o) is None


def test_unvalidated_or_disabled_gaze_cannot_send_events():
    c=calibration();sink=Sink();control=GazeController(Config(),sink,c)
    control.set_enabled(True);assert not control.enabled
    for i in range(20):control.process(observation(),hand(left=.2),1+i*.033)
    assert sink.events==[]


def control():
    c=calibration();c.validate(checks(),1920,1080)
    sink=Sink();g=GazeController(Config(),sink,c);g.set_enabled(True)
    for i in range(12):g.process(observation(),hand(),1+i*.033)
    return g,sink


@pytest.mark.parametrize("button",["left","right"])
def test_gaze_click_at_stable_target_freezes_while_held(button):
    g,s=control();pinch=hand(left=.2) if button=="left" else hand(right=.2)
    g.process(observation(),pinch,1.42);g.process(observation(),pinch,1.50)
    assert s.held=={button}
    moves=len([e for e in s.events if e[0]=="move"])
    g.process(observation(.7,.5),pinch,1.55)
    assert len([e for e in s.events if e[0]=="move"])==moves
    g.process(observation(),hand(),1.6);g.process(observation(),hand(),1.68)
    assert not s.held and s.events.count((button,True))==s.events.count((button,False))==1


@pytest.mark.parametrize("kind",["stale","eyes","hand","ambiguous","disabled"])
def test_gaze_interruption_releases_and_requires_new_open_pinches(kind):
    g,s=control();g.process(observation(),hand(left=.2),1.42);g.process(observation(),hand(left=.2),1.50)
    assert s.held=={"left"}
    if kind=="stale":g.process(observation(),hand(left=.2),1.55,age=.3)
    elif kind=="eyes":g.process(None,hand(left=.2),1.55)
    elif kind=="hand":g.process(observation(),None,1.55)
    elif kind=="ambiguous":g.process(observation(),hand(left=.2,right=.2),1.55)
    else:g.set_enabled(False)
    assert not s.held
    for i in range(8):g.process(observation(),hand(left=.2),1.6+i*.033)
    assert s.events.count(("left",True))==1


def test_blink_and_small_eyes_are_invalid():
    p=np.full((478,3),.5)
    for a,b,top,bottom,iris,x in ((33,133,159,145,468,.35),(362,263,386,374,473,.55)):
        p[a,:2]=(x,.4);p[b,:2]=(x+.1,.4);p[iris,:2]=(x+.05,.4)
        p[top,:2]=(x+.05,.38);p[bottom,:2]=(x+.05,.42)
    assert eye_features(p).valid
    p[159,:2]=p[145,:2];assert not eye_features(p).valid
    assert eye_features(p[:30]) is None


@pytest.mark.parametrize("index,delta",[(3,.3),(4,.25),(5,.25)])
def test_head_pose_change_blocks_gaze(index,delta):
    c=GazeCalibration()
    for y in (.1,.5,.9):
        for x in (.1,.5,.9):c.add([replace(o,head=(.5,.5,.2,0,0,.4)) for o in samples(x,y)],(x,y))
    c.fit();head=[.5,.5,.2,0,0,.4];head[index]+=delta
    assert c.predict(replace(observation(),head=tuple(head))) is None


def test_validation_uses_the_actual_cursor_smoothing_on_timed_samples():
    c=calibration();groups=[]
    for target in ((.25,.25),(.75,.3),(.35,.7),(.7,.75),(.5,.6)):
        timed=[(i/30,observation(*target,noise=.002*(-1)**i)) for i in range(45)]
        raw=[c.predict(o) for _,o in timed]
        assert np.max(np.std(raw,axis=0)*[1920,1080])>30
        groups.append((timed,target))
    report=c.validate(groups,1920,1080)
    assert report["passed"] and all(item["jitter_px"]<30 for item in report["checks"])


def test_genuinely_unstable_or_missing_samples_remain_blocked():
    c=calibration();groups=checks()
    target=groups[1][1]
    groups[1]=([(i/30,observation(*target,noise=.01*math.sin(i/8))) for i in range(45)],target)
    report=c.validate(groups,1920,1080)
    assert not report["passed"] and 1 in report["retry_indices"]
    groups=checks();groups[2]=(groups[2][0][:4],groups[2][1])
    report=c.validate(groups,1920,1080)
    assert not report["passed"] and report["retry_indices"]==[2]


def test_repeated_timestamps_cannot_manufacture_valid_samples():
    c=calibration();groups=checks();target=groups[0][1]
    groups[0]=([(1,observation(*target)) for _ in range(40)],target)
    report=c.validate(groups,1920,1080)
    assert not report["passed"] and report["retry_indices"]==[0]


def test_unverified_control_enables_without_changing_accuracy_result():
    c=calibration();c.validate(checks(.2),1920,1080)
    sink=Sink();g=GazeController(Config(),sink,c);g.set_enabled(True,allow_unverified=True)
    assert g.enabled and g.unverified and not c.validated and not c.report["passed"]
    for i in range(12):g.process(observation(),hand(),1+i*.033)
    g.process(observation(),hand(left=.2),1.42);g.process(observation(),hand(left=.2),1.50)
    assert sink.held=={"left"}
    g.process(None,hand(left=.2),1.55)
    assert not sink.held


def test_unverified_control_allows_finite_imprecise_mapping_but_not_stale_or_invalid_eyes():
    c=calibration();sink=Sink();g=GazeController(Config(),sink,c);g.set_enabled(True,allow_unverified=True)
    moved=replace(observation(.8,.8),head=(.7,.5,.3))
    assert c.predict(moved) is None
    g.process(moved,None,1)
    assert any(e[0]=="move" for e in sink.events)
    before=len(sink.events);g.process(moved,None,1.1,age=.3)
    g.process(replace(moved,valid=False),None,1.2)
    assert len(sink.events)==before


def test_unverified_choice_cannot_enable_without_fitted_mapping():
    g=GazeController(Config(),Sink(),GazeCalibration());g.set_enabled(True,allow_unverified=True)
    assert not g.enabled


def test_unverified_mode_accepts_a_fresh_pinch_despite_jitter():
    c=calibration();s=Sink();g=GazeController(Config(),s,c);g.set_enabled(True,allow_unverified=True)
    for i in range(12):g.process(observation(.5+.25*math.sin(i*.45),.5),hand(),1+i*.033)
    assert np.max(np.std([p for _,p in g.history],axis=0))>.008
    g.process(observation(.5,.5),hand(left=.2),1.42);g.process(observation(.5,.5),hand(left=.2),1.50)
    assert s.held=={"left"}
    g.set_enabled(False);assert not s.held and not g.unverified
