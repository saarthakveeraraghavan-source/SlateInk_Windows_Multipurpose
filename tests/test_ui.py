import os
os.environ["QT_QPA_PLATFORM"]="offscreen"
import pytest
from PySide6.QtWidgets import QApplication
from slateink.app import MainWindow
from slateink.calibration import Surface
from slateink.recognition import Recognition
from slateink.state import State
from slateink.config import Config


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp):
    w=MainWindow(Config(initial_mode="finger_letters"))
    yield w
    w.timer.stop(); w.performance_timer.stop(); w.close()


def recognized(window,text="A",score=0.5):
    window.set_state(State.PROCESSING)
    window.recognized(Recognition(text,score,0.1,alternatives=((text,score),("B",0.1))))


def collected(window,text="Hello, world!"):
    window.preview.setPlainText(text)
    window.set_state(State.PREVIEW)


def test_startup_is_camera_off_and_not_typing(window):
    assert window.worker is None and not window.controller.enabled
    assert not window.accept_button.isEnabled() and not window.submit_button.isEnabled()
    assert window.state==State.CAMERA_OFF
    assert window.mirror.isChecked()


def test_even_high_score_letter_requires_explicit_add(window):
    recognized(window,score=0.999)
    assert window.state==State.PREVIEW
    assert window.letter_preview.text()=="a"
    assert window.preview.toPlainText()==""
    assert window.countdown_deadline is None and window.send_worker is None
    assert not window.accept_button.isEnabled()


def test_late_result_after_discard_is_ignored(window):
    window.set_state(State.PROCESSING); window.discard()
    window.recognized(Recognition("A",0.9,0.1))
    assert window.pending_letter is None and window.preview.toPlainText()==""


def test_low_score_letter_is_visible_and_editable(window):
    recognized(window)
    assert window.letter_preview.isEnabled()
    assert "uncalibrated" in window.score_label.text()
    assert "Low model score" in window.error_label.text()


def test_processing_disables_orientation_capture_and_send(window):
    window.set_state(State.PROCESSING)
    assert not window.camera_button.isEnabled() and not window.capture_button.isEnabled()
    assert not window.accept_button.isEnabled() and not window.mirror.isEnabled()


def test_accept_rejects_enter_and_keeps_collected_text(window):
    collected(window,"Hello\nworld"); window.accept()
    assert window.countdown_deadline is None and window.state==State.PREVIEW
    assert "single line" in window.error_label.text()


def test_escape_cancels_send_without_clearing_collected_text(window):
    collected(window); window.accept()
    assert window.countdown_deadline is not None
    window.emergency_stop()
    assert window.countdown_deadline is None and window.accepted_text is None
    assert window.preview.toPlainText()=="Hello, world!"


def test_discard_clears_ink_pending_letter_and_text(window):
    window.controller.buffer.add(0.2,0.3,0)
    collected(window); recognized(window)
    window.discard()
    assert window.controller.buffer.count==0 and not window.controller.enabled
    assert not window.result_valid and window.pending_letter is None
    assert window.preview.toPlainText()==""


def test_failed_recognizer_keeps_previous_letters_and_does_not_send(window):
    collected(window,"old")
    window.controller.buffer.add(0.2,0.3,0)
    window.recognition_failed("failed")
    assert window.preview.toPlainText()=="old" and window.pending_letter is None
    assert window.countdown_deadline is None and not window.accept_button.isEnabled()


def test_self_focus_at_deadline_fails_closed(window):
    from slateink.injection import InjectionError
    class Fake:
        def destination(self):raise InjectionError("own window")
        def escape_pressed(self):return False
        def modifiers_pressed(self):return False
    window.injector=Fake(); collected(window); window.accept()
    window.typing_tick(window.countdown_deadline+0.1)
    assert window.send_worker is None and window.state==State.PREVIEW and window.result_valid


def test_two_letters_reuse_ink_area_and_preserve_collected_text(window):
    surface=Surface.from_corners([(0.1,0.1),(0.9,0.1),(0.9,0.9),(0.1,0.9)])
    window.controller.surface=surface
    for char in ("H","I"):
        window.controller.buffer.add(0.2,0.3,0)
        recognized(window,char)
        window.add_letter()
        assert window.controller.buffer.count==0
        assert window.controller.surface is surface
        assert not window.controller.pinch.released
    assert window.preview.toPlainText()=="hi"
    assert window.pending_letter is None


def test_clear_ink_does_not_clear_collected_text(window):
    collected(window,"keep")
    window.controller.buffer.add(0.2,0.3,0)
    recognized(window)
    window.clear_ink()
    assert window.preview.toPlainText()=="keep" and window.pending_letter is None
    assert window.controller.buffer.count==0


def test_case_and_corrected_letter(window):
    recognized(window,"A")
    window.uppercase.setChecked(True)
    assert window.letter_preview.text()=="A"
    window.letter_preview.setText("B"); window.add_letter()
    assert window.preview.toPlainText()=="B"


def test_space_and_backspace_edit_only_collected_text(window):
    collected(window,"hi"); window.add_space()
    assert window.preview.toPlainText()=="hi "
    window.backspace_text()
    assert window.preview.toPlainText()=="hi"
    assert window.send_worker is None


def test_orientation_invalidates_surface_and_keeps_text(window):
    collected(window,"keep")
    window.controller.surface=Surface.from_corners([(0.1,0.1),(0.9,0.1),(0.9,0.9),(0.1,0.9)])
    window.controller.buffer.add(0.2,0.3,0)
    window.mirror.setChecked(False)
    assert window.controller.surface is None and not window.controller.enabled
    assert window.controller.buffer.count==0 and window.preview.toPlainText()=="keep"
    assert not window.config.camera_mirrored


def test_orientation_after_camera_stop_restarts_with_new_config(window,monkeypatch):
    import threading
    class Worker:
        stop_event=threading.Event()
        def stop(self):self.stop_event.set()
        def deleteLater(self):pass
    old=Worker(); window.worker=old
    started=[]
    monkeypatch.setattr(window,"start_camera",lambda:started.append(window.config.camera_rotation))
    window.rotation.setCurrentIndex(1)
    assert old.stop_event.is_set() and window.restart_after_orientation
    window.camera_finished()
    assert started==[90] and not window.restart_after_orientation


def test_pending_letter_cannot_be_sent_as_text(window):
    collected(window,"old"); recognized(window)
    assert not window.accept_button.isEnabled()
    window.accept()
    assert window.countdown_deadline is None


@pytest.mark.parametrize("text",["AB","1",".","é"])
def test_non_single_english_letter_result_rejected(window,text):
    recognized(window,text)
    assert window.pending_letter is None and not window.add_letter_button.isEnabled()


def test_invalid_review_character_cannot_append(window):
    recognized(window); window.letter_preview.setText("9"); window.add_letter()
    assert window.preview.toPlainText()=="" and window.pending_letter is not None
