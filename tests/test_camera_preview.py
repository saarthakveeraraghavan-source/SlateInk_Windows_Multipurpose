import os
os.environ["QT_QPA_PLATFORM"]="offscreen"
from dataclasses import replace
import threading,time,uuid
import numpy as np
import pytest
from PySide6.QtCore import Qt,QPoint,QPointF,QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from slateink.app import MainWindow
from slateink.config import Config
from slateink.single_instance import SingleInstance


class Worker:
    def __init__(self):self.stop_event=threading.Event()
    def stop(self):self.stop_event.set()
    def deleteLater(self):pass


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([])
    w=MainWindow(Config());w.timer.stop();w.performance_timer.stop()
    yield w
    w.worker=None;w.close();app.processEvents()


def camera_on(w):
    w.worker=Worker();w.camera_view.set_frame(np.full((120,160,3),80,np.uint8),None)
    w.latest_frame_at=time.monotonic();w.refresh_controls()


@pytest.mark.parametrize("mode,submode",[(0,0),(1,0),(1,1),(1,2),(2,0),(3,0),(4,0)])
def test_shared_floating_feed_in_every_mode_is_optional_and_nonactivating(window,mode,submode):
    window.mode_choice.setCurrentIndex(mode)
    if mode==1:window.submode_choice.setCurrentIndex(submode)
    window.camera_preview_choice.setChecked(True);assert window.camera_preview is None
    camera_on(window);preview=window.camera_preview
    assert preview.isVisible() and preview.parentWidget() is None
    assert preview.windowFlags()&Qt.WindowType.WindowStaysOnTopHint
    assert preview.windowFlags()&Qt.WindowType.WindowDoesNotAcceptFocus
    assert preview.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert preview.view.image.cacheKey()==window.camera_view.image.cacheKey()
    assert "LIVE" in preview.status.text()
    window.camera_preview_choice.setChecked(False)
    assert not preview.isVisible() and preview.view.image is None
    assert not window.worker.stop_event.is_set()


def test_drag_header_saves_position_and_overlay_hide_saves_choice(window,tmp_path,monkeypatch):
    import slateink.config as config
    monkeypatch.setattr(config,"ROOT",tmp_path);window.persist_preferences=True
    window.camera_preview_choice.setChecked(True);camera_on(window)
    overlay=window.camera_preview;overlay.move(80,80)
    origin=QPointF(95,90)
    for kind,pos,button,buttons in ((QEvent.Type.MouseButtonPress,origin,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton),
                                  (QEvent.Type.MouseMove,origin+QPointF(40,20),Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton),
                                  (QEvent.Type.MouseButtonRelease,origin+QPointF(40,20),Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)):
        event=QMouseEvent(kind,QPointF(15,10),pos,button,buttons,Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(overlay.bar,event)
    saved=config.load_config()
    assert overlay.pos()==QPoint(120,100)
    assert (saved.camera_preview_x,saved.camera_preview_y)==(120,100)
    overlay.hide_button.click()
    assert not config.load_config().camera_preview_enabled and not overlay.isVisible()


def test_preview_clears_stale_or_stopped_frames_and_recovers_offscreen_position(window):
    window.camera_preview_choice.setChecked(True);camera_on(window);overlay=window.camera_preview
    overlay.move(-99999,-99999);overlay.keep_on_screen()
    assert any(s.availableGeometry().contains(overlay.frameGeometry()) for s in QApplication.screens())
    window.latest_frame_at=time.monotonic()-.6;window.sync_camera_preview()
    assert overlay.view.image is None and "Waiting" in overlay.status.text()
    window.stop_camera();assert not overlay.isVisible() and overlay.view.image is None


def test_ui_tracking_delay_preserves_wispr_and_preview_names_the_stop_hand(window,monkeypatch):
    from test_touchpad_product import Shortcuts
    window.mode_choice.setCurrentIndex(1);window.camera_preview_choice.setChecked(True);camera_on(window)
    session=window.touchpad_session;session.shortcuts=Shortcuts();session.set_enabled(True)
    session.shortcuts.begin("toggle_ctrl_win");session.voice_started=time.monotonic();session.voice_hand="Left"
    window.config=replace(window.config,camera_mirrored=True)
    session.config=window.config
    window.sync_camera_preview()
    assert "RIGHT swag sign" in window.camera_preview.status.text()
    monkeypatch.setattr(window.injector,"escape_pressed",lambda:False)
    window.worker.take=lambda:None
    window.last_packet_time=time.monotonic()-.3
    window.tick()
    assert session.dictating and session.shortcuts.calls==[("begin","toggle_ctrl_win")]
    assert "Wispr listening" in window.hint.text()
    window.stop_camera()
    assert not session.dictating and session.shortcuts.calls[-1]==("cancel",)


def test_minimized_camera_preview_keeps_feed_but_stops_non_touchpad_input(window):
    window.camera_preview_choice.setChecked(True);camera_on(window)
    window.controller.set_enabled(True);window.show();QApplication.processEvents()
    window.showMinimized();QApplication.processEvents()
    assert window.isMinimized() and window.camera_preview.isVisible()
    assert not window.worker.stop_event.is_set() and not window.controller.enabled
    window.camera_preview.hide_button.click()
    assert window.worker.stop_event.is_set() and not window.camera_preview.isVisible()


def test_owned_caption_minimize_releases_mouse_and_preserves_background_tracking(window):
    from test_touchpad_submodes import Pixels
    window.mode_choice.setCurrentIndex(1);camera_on(window)
    mouse=Pixels();window.mouse_sink=mouse;window.hand_mouse.sink=mouse
    window.touchpad_session.set_enabled(True);window.tray=object()
    window.show();QApplication.processEvents()
    mouse.button("left",True);window.hand_mouse.button_held="left"
    assert window.handle_gesture_caption(8)
    QApplication.processEvents()
    assert window.isMinimized() and not mouse.held and window.hand_mouse.enabled
    assert not window.worker.stop_event.is_set()
    window.tray=None


def test_physical_caption_click_is_not_intercepted(window):
    assert not window.handle_gesture_caption(8)
    assert not window.handle_gesture_caption(2)


def test_second_launch_requests_show_without_owning_another_session():
    app=QApplication.instance() or QApplication([]);name="SlateInk_test_"+uuid.uuid4().hex
    first=SingleInstance(name);second=SingleInstance(name);seen=[]
    first.show_requested.connect(lambda:seen.append(True))
    try:
        assert first.acquire() and not second.acquire()
        deadline=time.monotonic()+1
        while not seen and time.monotonic()<deadline:app.processEvents()
        assert seen==[True]
    finally:second.close();first.close()


@pytest.mark.parametrize("options",[{"camera_preview_enabled":1},{"camera_preview_x":2},
                                     {"camera_preview_x":True,"camera_preview_y":0},
                                     {"camera_preview_x":999999,"camera_preview_y":0}])
def test_invalid_preview_preferences_are_rejected(options):
    with pytest.raises(ValueError):Config(**options)
