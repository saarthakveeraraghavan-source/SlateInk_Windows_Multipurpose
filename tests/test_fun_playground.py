import os
os.environ["QT_QPA_PLATFORM"]="offscreen"
from dataclasses import replace
import math
import time
import numpy as np
import pytest
from PySide6.QtCore import Qt,QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
from slateink.config import Config
from slateink.fun_physics import PlaygroundModel,fit_portal
from slateink.fun_playground import FunWindow
from slateink.tracking import Hand
from test_modes import window,Worker
from test_touchpad_product import pose,Shortcuts,rock_pose


def hand(x=.5,y=.5,label="Left",pinch=.9):
    p=[(x,y,0.)]*21
    p[0]=(x,y+.12,0.);p[4]=(x-.08,y+.03,0.)
    p[5]=(x-.06,y+.02,0.);p[9]=(x,y+.02,0.);p[17]=(x+.06,y+.02,0.)
    for pip,tip,dx in ((6,8,-.02),(10,12,.01),(14,16,.035),(18,20,.06)):
        p[pip]=(x+dx,y+.02,0.);p[tip]=(x+dx,y-.04,0.)
    p[8]=(x,y,0.)
    return Hand(tuple(p),pinch,label,.99)


def circle_samples(count=48,radius=.25):
    return [(math.cos(i*math.tau/(count-1))*radius,math.sin(i*math.tau/(count-1))*radius,1+i*1.8/(count-1)) for i in range(count)]


def test_only_a_closed_observed_circle_forms_a_portal():
    fit=fit_portal(circle_samples())
    assert fit is not None and abs(fit[2]-.25)<.001
    assert fit_portal(circle_samples()[:25]) is None
    assert fit_portal([(x,0,t) for x,y,t in circle_samples()]) is None
    assert fit_portal(circle_samples(radius=.02)) is None


@pytest.mark.parametrize("mirrored",[False,True])
def test_right_hand_movement_paints_and_seals_a_portal_in_both_mirror_modes(mirrored):
    model=PlaygroundModel(seed=3);label="Left" if mirrored else "Right"
    for x,y,t in circle_samples(60):
        model.observe((hand(.5+x/(4/3),.5+y,label),),t,mirrored)
        model.advance(t)
    assert len(model.portals)==1 and len(model.trail)>15 and model.particles
    assert not hasattr(model,"sink")


def test_left_hand_alone_cannot_paint_and_reacquisition_never_bridges_a_gap():
    model=PlaygroundModel(seed=2)
    for i in range(8):model.observe((hand(.4+i*.003,label="Right"),),1+i*.05)
    assert not model.trail and model.brush is None
    for i in range(8):model.observe((hand(.4+i*.003),),2+i*.05)
    old=model.stroke_id
    model.observe((),2.4);model.observe((hand(.6),),2.45)
    assert model.stroke_id>old and model.trail[-1][3]==old


def test_stale_ambiguous_low_confidence_and_outside_hands_stop_emission():
    model=PlaygroundModel()
    for i in range(3):model.observe((hand(.4+i*.01),),1+i*.05)
    model.advance(1.5);assert model.brush is None
    for hands,age in (((hand(),),.3),((hand(),hand()),0),((replace(hand(),handedness_confidence=.4),),0),((hand(1.1),),0)):
        model.observe(hands,2,age=age);assert model.brush is None


def test_two_hand_spread_expands_web_and_one_hand_turns_it():
    model=PlaygroundModel("web")
    model.observe((hand(.45),hand(.55,label="Right")),1)
    small=model.dome_target
    model.observe((hand(.2),hand(.8,label="Right")),1.1)
    assert model.dome_target>small
    model.observe((hand(.35),),1.2);yaw=model.yaw_target
    model.observe((hand(.6),),1.3)
    assert model.yaw_target>yaw and .5<=model.dome_target<=1.8


def test_nebula_gravity_and_pinch_burst_are_bounded_without_desktop_clicks():
    model=PlaygroundModel("nebula",seed=1)
    for t in (1,1.1):model.observe((hand(),),t);model.advance(t)
    model.observe((hand(pinch=.2),),1.14);model.observe((hand(pinch=.2),),1.18)
    assert model.pulse==1 and model.particles
    initial=[(p.x,p.y) for p in model.stars]
    for i in range(120):model.advance(1.18+i/60)
    assert initial!=[(p.x,p.y) for p in model.stars]
    assert all(math.isfinite(v) for p in model.stars for v in (p.x,p.y,p.vx,p.vy))
    for i in range(40):model.emit(0,0,1000)
    assert len(model.particles)<=model.max_particles


def test_fun_config_is_validated_and_existing_submodes_remain_available():
    assert Config(touchpad_submode="fun",fun_scene="web").fun_scene=="web"
    for submode in ("desktop","gaming","drawing"):assert Config(touchpad_submode=submode)
    with pytest.raises(ValueError):Config(fun_scene="missing")


def test_fun_launch_packet_exit_and_camera_shutdown_leave_desktop_input_off(window):
    from slateink.camera import Packet
    window.mode_choice.setCurrentIndex(1);window.submode_choice.setCurrentIndex(3)
    window.worker=Worker();window.refresh_controls()
    assert not window.fun_panel.isHidden() and window.pointer_button.isHidden()
    window.launch_fun();QApplication.processEvents()
    fun=window.fun_window;fun.timer.stop()
    assert fun is not None and not window.hand_mouse.enabled
    t=time.monotonic();image=np.zeros((480,640,3),np.uint8)
    packet=Packet(image,hand(),1,t,30,30,10,0,hands=(hand(),))
    window.camera_view.set_frame(image,hand());window.process_mode_packet(packet,t)
    assert not fun.canvas.preview.isNull() and not window.hand_mouse.enabled
    fun.choose_scene("web");assert window.config.fun_scene=="web"
    worker=window.worker
    QApplication.sendEvent(fun,QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Escape,Qt.KeyboardModifier.NoModifier));QApplication.processEvents()
    assert window.fun_window is None and worker.stop_event.is_set() and not window.hand_mouse.enabled


def test_fun_session_cannot_dispatch_clicks_swipes_or_wispr_even_if_enabled():
    from test_mouse_control import controller
    from slateink.touchpad_session import TouchpadSession
    c,s=controller();c.config=replace(c.config,touchpad_submode="fun",wispr_enabled=True)
    keys=Shortcuts();session=TouchpadSession(c,keys);session.set_enabled(True)
    for i in range(20):session.process((rock_pose(),),1+i*.05)
    assert not keys.calls and not s.events and not session.dictating


def test_in_scene_camera_replaces_floating_overlay_without_changing_preference(window):
    window.mode_choice.setCurrentIndex(1);window.submode_choice.setCurrentIndex(3)
    window.worker=Worker();window.latest_frame_at=time.monotonic()
    window.camera_view.set_frame(np.zeros((120,160,3),np.uint8),None)
    window.camera_preview_choice.setChecked(True);window.refresh_controls()
    assert window.camera_preview.isVisible()
    window.launch_fun();QApplication.processEvents();window.sync_camera_preview()
    assert window.config.camera_preview_enabled and not window.camera_preview.isVisible()
    window.stop_pointer()


@pytest.mark.parametrize("scene",["portal","web","nebula"])
def test_scene_renders_and_clear_pause_shortcuts_do_not_need_a_camera(scene,tmp_path):
    app=QApplication.instance() or QApplication([])
    window=FunWindow(scene);window.timer.stop();window.resize(1100,760);window.show();app.processEvents()
    window.toggle_demo(True)
    now=time.monotonic();window.demo_start=now-3
    for i in range(90):window.demo_frame(now+i/60);window.model.advance(now+i/60)
    pixmap=window.grab()
    assert not pixmap.isNull()
    # The composed scene must contain more than a flat empty background.
    image=pixmap.toImage();assert image.pixelColor(500,400)!=image.pixelColor(1,100)
    QApplication.sendEvent(window,QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_P,Qt.KeyboardModifier.NoModifier));assert window.paused
    QApplication.sendEvent(window,QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Space,Qt.KeyboardModifier.NoModifier))
    assert not window.model.trail and not window.model.portals
    window.close();app.processEvents()
