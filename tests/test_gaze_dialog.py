import os
from types import SimpleNamespace
from dataclasses import replace
import pytest
os.environ["QT_QPA_PLATFORM"]="offscreen"
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from slateink.gaze_widgets import GazeCalibrationDialog,TRAIN,CHECK
import slateink.gaze_widgets as widgets
from test_gaze import observation


def space(dialog):dialog.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress,Qt.Key.Key_Space,Qt.KeyboardModifier.NoModifier))


@pytest.fixture
def dialog(monkeypatch):
    clock=[100.0]
    monkeypatch.setattr(widgets,"time",SimpleNamespace(monotonic=lambda:clock[0]))
    app=QApplication.instance() or QApplication([]);d=GazeCalibrationDialog();d.timer.stop();d.auto.setChecked(False)
    yield d,clock
    d.reject()


def feed(d,clock,target,override=None,count=35):
    clock[0]=max(clock[0],d.changed_at+.45)
    for i in range(count):
        clock[0]+=.033
        o=override if override is not None else observation(*target)
        d.observe(o,clock[0])
    d.poll()


def start(d,clock):
    feed(d,clock,(.5,.5));space(d)
    assert d.phase=="calibrate"


def finish(d,clock,bad_index=None):
    start(d,clock)
    for target in TRAIN:
        assert d.target==target;feed(d,clock,target);space(d)
    for i,target in enumerate(CHECK):
        assert d.target==target
        bad=replace(observation(*target),head=(.7,.5,.2)) if i==bad_index else None
        feed(d,clock,target,bad);space(d)


def test_dialog_uses_separate_targets_and_saves_no_sample_history(dialog):
    d,clock=dialog
    completed=[];d.completed.connect(completed.append)
    finish(d,clock)
    assert d.phase=="done" and completed and completed[0].validated
    d.accept();assert not d.samples and not d.checks and not d.timer.isActive()


def test_no_eyes_or_stale_samples_cannot_advance_dialog(dialog):
    d,clock=dialog
    space(d);assert d.phase=="setup"
    feed(d,clock,(.5,.5));clock[0]+=2;space(d)
    assert d.phase=="setup" and "Camera samples stopped" in d.capture_notice


def test_early_space_keeps_collected_samples(dialog):
    d,clock=dialog;start(d,clock)
    feed(d,clock,TRAIN[0],count=5);previous=list(d.samples);space(d)
    assert list(d.samples)==previous and d.index==0
    feed(d,clock,TRAIN[0]);space(d);assert d.index==1


def test_all_fourteen_checks_finish_with_specific_failure_and_selective_retry(dialog):
    d,clock=dialog;finish(d,clock,bad_index=2)
    assert d.phase=="done" and not d.calibration.validated
    assert d.report["retry_indices"]==[2]
    assert "Head position changed" in d.status.text()
    retained={i:id(v) for i,v in d.checks.items() if i!=2};mapping=d.calibration.weights.copy()
    d.retry_failed()
    assert d.phase=="validate" and d.target==CHECK[2] and len(d.calibration.groups)==9
    feed(d,clock,CHECK[2]);space(d)
    assert d.phase=="done" and d.calibration.validated
    assert all(id(d.checks[i])==v for i,v in retained.items())
    import numpy as np
    assert np.array_equal(mapping,d.calibration.weights)


def test_insufficient_eye_movement_finishes_without_restarting_train(dialog):
    d,clock=dialog;start(d,clock)
    for _ in TRAIN:feed(d,clock,(.5,.5));space(d)
    assert d.phase=="done" and not d.calibration.validated
    assert "Not enough eye movement" in d.status.text()


def test_automatic_capture_and_duplicate_timestamp_guard(dialog):
    d,clock=dialog;start(d,clock);d.auto.setChecked(True)
    feed(d,clock,TRAIN[0]);assert d.index==1
    clock[0]=d.changed_at+.5
    for _ in range(30):d.observe(observation(*TRAIN[1]),clock[0])
    d.poll();assert d.index==1 and len(d.samples)==1


def test_blinks_pause_collection_and_explain_why(dialog):
    d,clock=dialog;start(d,clock)
    d.observe(replace(observation(),valid=False,reason="Eyes closed or occluded."),clock[0]+.5)
    clock[0]+=.5;d.poll();space(d)
    assert d.index==0 and "Eyes closed" in d.status.text()


def test_user_can_continue_after_nine_dots_without_last_five_checks(dialog):
    d,clock=dialog;requested=[];d.unverified_requested.connect(requested.append)
    start(d,clock)
    for target in TRAIN:feed(d,clock,target);space(d)
    assert d.phase=="validate" and d.calibration.weights is not None
    d.use_unverified()
    assert requested==[d.calibration] and not d.calibration.validated
    assert not d.calibration.report["passed"] and not d.timer.isActive()


def test_failed_checks_can_be_overridden_without_faking_a_pass(dialog):
    d,clock=dialog;finish(d,clock,bad_index=2)
    failed=d.report;requested=[];d.unverified_requested.connect(requested.append)
    d.use_unverified()
    assert requested and d.calibration.report is failed and not failed["passed"]
