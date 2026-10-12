import os
os.environ["QT_QPA_PLATFORM"]="offscreen"
import threading,time
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from slateink.app import MainWindow
from slateink.camera import Packet
from slateink.calibration import Surface
from slateink.config import Config
from slateink.recognition import Recognition
from slateink.state import State
from slateink.mouse_control import HandMouseController


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([])
    w=MainWindow(Config(initial_mode="paper"));w.timer.stop();w.performance_timer.stop()
    yield w
    w.worker=None;w.close()


class Sink:
    def __init__(self):self.moves=[];self.buttons=[];self.held=set()
    def move(self,x,y):self.moves.append((x,y))
    def button(self,name,down):self.buttons.append((name,down))
    def release_all(self):self.held.clear()


class Worker:
    def __init__(self):self.stop_event=threading.Event()
    def stop(self):self.stop_event.set()
    def take(self):return None
    def deleteLater(self):pass


def surface():return Surface.from_corners([(0.1,0.1),(0.9,0.1),(0.9,0.9),(0.1,0.9)])


def test_default_paper_mode_never_enables_desktop_mouse(window):
    assert window.mode=="paper" and window.config.camera_width==1280
    assert not window.hand_mouse.enabled and not window.pen_pointer_enabled
    assert window.pointer_deadline is None


def test_swipe_settings_apply_only_in_desktop_and_lock_while_active(window):
    window.mode_choice.setCurrentIndex(1)
    assert not window.swipe_panel.isHidden()
    window.swipe_sensitivity.setValue(1.4);window.swipe_cooldown.setValue(1.2)
    assert window.config.touchpad_swipe_sensitivity==1.4
    assert window.touchpad_session.config.touchpad_swipe_cooldown==1.2
    window.swipe_enabled.setChecked(False)
    assert not window.config.touchpad_swipe_enabled
    for mode in (1,2):
        window.submode_choice.setCurrentIndex(mode)
        assert window.swipe_panel.isHidden()
    window.submode_choice.setCurrentIndex(0);window.worker=Worker()
    window.refresh_controls();window.toggle_pointer()
    assert not window.swipe_sensitivity.isEnabled()
    window.pointer_tick(window.pointer_deadline+.01)
    assert window.swipe_enabled.isEnabled() and not window.swipe_cooldown.isEnabled()
    window.touchpad_session.swipe.capturing=True
    window.swipe_enabled.setChecked(True)
    assert window.hand_mouse.enabled and not window.touchpad_session.swipe.capturing
    window.swipe_enabled.setChecked(False)
    assert window.hand_mouse.enabled and not window.config.touchpad_swipe_enabled
    window.stop_pointer();window.refresh_controls()
    assert window.swipe_sensitivity.isEnabled()


def test_live_swipe_toggle_saves_choice_and_preserves_active_mouse(window,tmp_path,monkeypatch):
    import slateink.config as config_module
    from test_touchpad_submodes import Pixels
    from test_air_swipe import air_pose
    from test_window_swipe import Switcher
    monkeypatch.setattr(config_module,"ROOT",tmp_path)
    window.persist_preferences=True
    window.mode_choice.setCurrentIndex(1);window.worker=Worker()
    mouse=Pixels();window.hand_mouse.sink=mouse
    switcher=Switcher();window.touchpad_session.window_switcher=switcher
    window.refresh_controls();window.toggle_pointer();window.pointer_tick(window.pointer_deadline+.01)
    assert window.hand_mouse.enabled
    window.touchpad_session.swipe.capturing=True
    window.swipe_enabled.setChecked(False)
    assert window.hand_mouse.enabled and not window.touchpad_session.swipe.capturing
    assert not config_module.load_config().touchpad_swipe_enabled
    for i in range(20):
        window.touchpad_session.process((air_pose(min(1,i/8),mirrored=True),),1+i*.05,aspect=16/9)
    assert not switcher.events
    window.swipe_enabled.setChecked(True)
    assert config_module.load_config().touchpad_swipe_enabled and window.hand_mouse.enabled


def test_paper_results_require_preview_and_acceptance(window):
    window.recognition_kind="paper";window.set_state(State.PROCESSING)
    window.recognized(Recognition("Hello world",0.99,0.1))
    assert window.state==State.PREVIEW and window.preview.toPlainText()=="Hello world"
    assert window.pending_letter is None and window.countdown_deadline is None


def test_paper_failure_keeps_old_reference_but_blocks_send(window):
    window.preview.setPlainText("previous result");window.recognition_kind="paper"
    window.recognition_failed("Could not read new paper")
    assert window.preview.toPlainText()=="previous result"
    assert not window.result_valid and not window.accept_button.isEnabled()


def test_mode_change_disarms_and_preserves_text(window):
    sink=Sink();window.hand_mouse=HandMouseController(window.config,sink)
    window.hand_mouse.surface=surface();window.hand_mouse.set_enabled(True);sink.held={"left"}
    window.preview.setPlainText("keep");window.controller.surface=surface()
    window.mode_choice.setCurrentIndex(1)
    assert window.mode=="hand_mouse" and not window.hand_mouse.enabled and not sink.held
    assert window.controller.surface is None and window.preview.toPlainText()=="keep"


def test_touchpad_enable_is_delayed_without_area_calibration(window):
    window.mode_choice.setCurrentIndex(1);window.worker=Worker()
    window.refresh_controls();window.toggle_pointer()
    assert window.pointer_deadline is not None and not window.hand_mouse.enabled
    window.pointer_tick(window.pointer_deadline+0.01)
    assert window.hand_mouse.enabled and window.state==State.MOUSE
    window.emergency_stop()
    assert not window.hand_mouse.enabled and window.pointer_deadline is None


def test_gaze_enable_blocked_until_accuracy_passes_and_reset_clears_it(window):
    window.mode_choice.setCurrentIndex(4);window.worker=Worker();window.refresh_controls()
    assert not window.pointer_button.isEnabled()
    window.toggle_pointer();assert window.pointer_deadline is None
    from test_gaze import calibration
    fitted=calibration();fitted.validated=True;window.gaze_calibrated(fitted)
    window.refresh_controls();window.toggle_pointer()
    assert window.pointer_deadline is not None
    window.pointer_tick(window.pointer_deadline+.01)
    assert window.gaze_controller.enabled and window.state==State.GAZE
    window.stop_camera()
    assert not window.gaze_controller.enabled and not window.gaze_calibration.validated


def test_authorized_unverified_gaze_can_enable_after_failed_check(window):
    from test_gaze import calibration,checks
    window.mode_choice.setCurrentIndex(4);window.worker=Worker()
    fitted=calibration();fitted.validate(checks(.2),1920,1080)
    window.gaze_calibrated(fitted);window.refresh_controls()
    assert not window.pointer_button.isEnabled()
    window.unverified_gaze.setChecked(True);assert window.pointer_button.isEnabled()
    window.toggle_pointer();window.pointer_tick(window.pointer_deadline+.01)
    assert window.gaze_controller.enabled and window.gaze_controller.unverified
    assert not fitted.validated and "UNVERIFIED" in window.status_label.text()
    window.unverified_gaze.setChecked(False)
    assert not window.gaze_controller.enabled and not window.pointer_button.isEnabled()


def test_unverified_option_does_not_enable_without_a_screen_mapping(window):
    window.mode_choice.setCurrentIndex(4);window.worker=Worker()
    window.unverified_gaze.setChecked(True);window.refresh_controls()
    assert not window.pointer_button.isEnabled()


def test_pen_hover_moves_without_clicks(window):
    sink=Sink();window.mouse_sink=sink;window.hand_mouse=HandMouseController(window.config,sink)
    window.mode_choice.setCurrentIndex(2);window.controller.surface=surface()
    window.pen_pointer_enabled=True
    image=np.full((200,200,3),255,np.uint8)
    import cv2
    cv2.circle(image,(100,100),5,(0,180,30),-1)
    window.pen_marker.select(image,0.5,0.5)
    t=time.monotonic();packet=Packet(image,None,0,t,30,30,1,1)
    window.process_mode_packet(packet,t)
    assert sink.moves and sink.buttons==[] and not sink.held


def test_stale_paper_frame_cannot_start_recognition(window):
    window.worker=Worker();window.controller.surface=surface()
    window.latest_rgb=np.full((300,300,3),255,np.uint8);window.latest_frame_at=time.monotonic()-2
    window.refresh_controls();window.submit()
    assert window.recognition_worker is None and "stale" in window.error_label.text()


def test_two_hands_block_paper_capture_without_landmarks(window):
    window.worker=Worker();window.controller.surface=surface()
    window.latest_rgb=np.full((300,300,3),255,np.uint8);window.latest_frame_at=time.monotonic()
    window.latest_hand_count=2;window.camera_view.hand=None
    window.refresh_controls();window.submit()
    assert window.recognition_worker is None and "both hands" in window.error_label.text()


def test_minimize_or_stop_disables_pointer(window):
    sink=Sink();window.hand_mouse=HandMouseController(window.config,sink)
    window.hand_mouse.surface=surface();window.hand_mouse.set_enabled(True);sink.held={"right"}
    window.stop_camera()
    assert not window.hand_mouse.enabled and not sink.held and window.latest_rgb is None


def test_two_hand_packets_route_to_touchpad_without_slate_region(window):
    from test_touchpad_product import pose
    window.mode_choice.setCurrentIndex(1)
    sink=Sink();sink.move_relative=lambda x,y:sink.moves.append((x,y));window.hand_mouse=HandMouseController(window.config,sink)
    window.touchpad_session.controller=window.hand_mouse;window.touchpad_session.set_enabled(True)
    image=np.zeros((480,640,3),np.uint8);start=time.monotonic()
    for i in range(20):
        hands=(pose(x=.5+max(0,i-5)*.003),pose(extended=(True,)*4,label="Right"))
        p=Packet(image,None,2,start+i*.033,30,30,1,1,hands=hands)
        window.process_mode_packet(p,p.t)
    assert sink.moves and window.controller.surface is None
    assert window.touchpad_session.primary.label=="Left" and window.touchpad_session.helper.label=="Right"


def test_background_hand_permission_requires_visible_tray_and_enabled_mode(window):
    window.mode_choice.setCurrentIndex(1);window.hand_mouse.set_enabled(True)
    assert not window.can_background_touchpad()
    window.tray=object();assert window.can_background_touchpad()
    window.tray=None;window.stop_pointer();assert not window.can_background_touchpad()


@pytest.mark.parametrize("submode",["gaming","drawing"])
def test_submode_controls_enable_after_countdown_and_stop_releases_all(window,submode):
    from test_touchpad_submodes import Keys,Pixels
    window.mode_choice.setCurrentIndex(1)
    window.submode_choice.setCurrentIndex(("desktop","gaming","drawing").index(submode))
    assert window.config.touchpad_submode==submode and not window.hand_mouse.enabled
    assert window.hand_choice.isHidden()==(submode=="gaming")
    assert window.drawing_speed.isHidden()==(submode!="drawing")
    assert window.gaming_radius.isHidden()==(submode!="gaming")
    assert window.wispr_enabled.isHidden()
    sink=Pixels();keys=Keys();window.touchpad_session.gaming.sink=keys
    window.touchpad_session.drawing.focus=keys.target
    window.hand_mouse.sink=sink;window.touchpad_session.drawing.sink=sink
    window.worker=Worker();window.refresh_controls();window.toggle_pointer()
    assert window.pointer_deadline and not window.hand_mouse.enabled
    window.pointer_tick(window.pointer_deadline+.01)
    assert window.hand_mouse.enabled and not window.submode_choice.isEnabled()
    sink.button("left",True);keys.key("W",True)
    window.emergency_stop()
    assert not sink.held and not keys.held and not window.hand_mouse.enabled


def test_changing_submode_releases_input_and_preserves_mouse_speed(window):
    from test_touchpad_submodes import Keys
    window.mode_choice.setCurrentIndex(1);keys=Keys();window.touchpad_session.gaming.sink=keys
    window.hand_mouse.set_enabled(True);keys.key("W",True)
    before=window.config.touchpad_sensitivity
    window.submode_choice.setCurrentIndex(2);window.drawing_speed.setValue(.8)
    assert not keys.held and not window.hand_mouse.enabled
    assert window.config.drawing_sensitivity==.8 and window.config.touchpad_sensitivity==before


def test_drawing_packets_route_fingertip_to_external_ink(window):
    from test_touchpad_product import pose
    from test_touchpad_submodes import Pixels,Keys
    window.mode_choice.setCurrentIndex(1);window.submode_choice.setCurrentIndex(2)
    sink=Pixels();keys=Keys();window.hand_mouse.sink=sink
    window.touchpad_session.drawing.focus=keys.target;window.touchpad_session.set_enabled(True)
    image=np.zeros((480,640,3),np.uint8);start=time.monotonic()
    for i in range(26):
        h=pose() if i<8 else pose((True,False,False,False),x=.5+max(0,i-13)*.003)
        p=Packet(image,h,1,start+i*.033,30,30,1,1,hands=(h,))
        window.process_mode_packet(p,p.t)
    assert sink.held=={"left"} and any(e[0]=="pixels" for e in sink.events)
    assert window.touchpad_session.button_held=="left" and window.controller.surface is None


def test_gaming_feedback_overlay_does_not_accept_focus_and_hides_on_stop(window):
    from PySide6.QtCore import Qt
    window.mode_choice.setCurrentIndex(1);window.submode_choice.setCurrentIndex(1)
    window.hand_mouse.set_enabled(True);window.refresh_controls()
    overlay=window.game_hud
    assert overlay.isVisible() and overlay.windowFlags()&Qt.WindowType.WindowDoesNotAcceptFocus
    assert overlay.windowFlags()&Qt.WindowType.WindowTransparentForInput
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    window.stop_pointer();assert not overlay.isVisible()


def test_two_hand_drawing_option_is_off_and_changes_release_input(window):
    window.mode_choice.setCurrentIndex(1);window.submode_choice.setCurrentIndex(2)
    assert not window.config.drawing_two_hand and not window.drawing_helper.isChecked()
    window.hand_mouse.set_enabled(True);window.drawing_helper.setChecked(True)
    assert window.config.drawing_two_hand and not window.hand_mouse.enabled and window.hand_choice.isHidden()
    window.drawing_helper.setChecked(False)
    assert not window.config.drawing_two_hand and not window.hand_choice.isHidden()
