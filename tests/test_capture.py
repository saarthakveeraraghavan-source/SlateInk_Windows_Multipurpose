import math
import numpy as np
import pytest
from slateink.calibration import Surface
from slateink.config import Config
from slateink.controller import CaptureController
from slateink.gestures import Pinch, pinch_ratio
from slateink.rendering import prepare_line, render_strokes
from slateink.smoothing import OneEuro
from slateink.strokes import Point, StrokeBuffer
from slateink.tracking import Hand


def hand(x=0.4,y=0.4,ratio=0.8,label="Left"):
    points = [(0,0,0)]*21
    points[8] = (x,y,0)
    return Hand(tuple(points),ratio,label)


def controller():
    c = CaptureController(Config())
    c.surface = Surface.from_corners([(0.1,0.1),(0.9,0.1),(0.9,0.9),(0.1,0.9)])
    c.set_enabled(True)
    return c


def arm(c):
    c.process(hand(),1.0)
    c.process(hand(),1.1)
    c.process(hand(ratio=0.2),1.13)
    c.process(hand(x=0.42,ratio=0.2),1.21)
    assert c.buffer.active


def test_perspective_maps_skewed_corners_and_center():
    s = Surface.from_corners([(0.1,0.2),(0.85,0.1),(0.95,0.9),(0.2,0.8)])
    for point,wanted in zip(s.corners,[(0,0),(1,0),(1,1),(0,1)]):
        mapped = s.map_point(point)
        # Numerical error near the border may be below machine precision.
        if mapped is not None:
            assert np.allclose(mapped,wanted,atol=1e-6)
    assert s.map_point((0.5,0.5)) is not None
    assert s.map_point((0.01,0.01)) is None


@pytest.mark.parametrize("corners",[
    [(0,0),(0,0),(0,0),(0,0)],
    [(0,0),(1,1),(1,0),(0,1)],
    [(0,0),(0,1),(1,1),(1,0)],
    [(0,0),(0.01,0),(0.01,0.01),(0,0.01)],
    [(0,0),(1,0),(math.nan,1),(0,1)],
    [(0,0),(1,0),(1,1)],
])
def test_reject_bad_calibration(corners):
    with pytest.raises(ValueError):
        Surface.from_corners(corners)


def test_pinch_requires_release_and_debounces_hysteresis():
    p = Pinch()
    assert not p.update(0.1,0)
    assert not p.update(0.1,0.1)
    assert not p.update(0.9,0.2)
    assert not p.update(0.9,0.3)
    assert p.released
    assert not p.update(0.2,0.4)
    assert p.update(0.2,0.5)
    assert p.update(0.45,0.6)
    assert p.update(0.8,0.7)
    assert not p.update(0.8,0.8)
    p.update(None,0.9)
    assert not p.released
    assert not p.update(0.2,1.0)


def test_brief_pinch_is_not_a_stroke():
    p = Pinch()
    p.update(1,0)
    p.update(1,0.1)
    p.update(0.1,0.15)
    assert not p.update(1,0.17)
    assert not p.down


def test_capture_paused_does_not_record():
    c = controller()
    c.set_enabled(False)
    for t in [0,0.1,0.2]:
        c.process(hand(ratio=0.1),t)
    assert c.buffer.count == 0


@pytest.mark.parametrize("interruption",["lost","outside","stale","jump","changed","gap"])
def test_interruptions_end_stroke_and_require_release(interruption):
    c = controller()
    arm(c)
    if interruption == "lost":
        c.process(None,1.24)
    elif interruption == "outside":
        c.process(hand(x=0.99,ratio=0.2),1.24)
    elif interruption == "stale":
        c.process(hand(ratio=0.2),1.24,0.3)
    elif interruption == "jump":
        c.process(hand(x=0.8,ratio=0.2),1.24)
    elif interruption == "changed":
        c.process(hand(ratio=0.2,label="Right"),1.24)
    else:
        c.process(hand(ratio=0.2),1.5)
    assert not c.buffer.active
    previous = c.buffer.count
    c.process(hand(ratio=0.2),1.55)
    c.process(hand(ratio=0.2),1.65)
    assert c.buffer.count == previous


def test_pen_up_boundaries_and_normalized_timestamps():
    c = controller()
    arm(c)
    c.process(hand(x=0.44,ratio=0.2),1.24)
    c.process(hand(x=0.45,ratio=0.9),1.27)
    c.process(hand(x=0.46,ratio=0.9),1.36)
    c.process(hand(x=0.46,ratio=0.2),1.39)
    c.process(hand(x=0.47,ratio=0.2),1.48)
    assert len(c.buffer.strokes) == 2
    assert c.buffer.strokes[0][0].t < c.buffer.strokes[1][0].t
    assert all(0<=p.x<=1 and 0<=p.y<=1 for stroke in c.buffer.strokes for p in stroke)


def test_buffer_limit_and_snapshot_not_mutated():
    b = StrokeBuffer(2)
    b.add(0.1,0.1,1)
    b.add(0.2,0.2,2)
    copy = b.snapshot()
    with pytest.raises(BufferError):
        b.add(0.3,0.3,3)
    assert not b.active
    b.clear()
    assert len(copy[0]) == 2
    assert b.count == 0


def test_buffer_undo_and_nonfinite_points():
    b = StrokeBuffer()
    b.add(0.1,0.2,0)
    b.pen_up()
    b.add(0.3,0.4,1)
    b.undo()
    assert b.count == 1
    assert not b.add(math.nan,0.2,2)
    assert not b.active


def test_smoothing_reduces_jitter_without_bridging_interruptions():
    f = OneEuro()
    raw = [(0.5+0.01*(-1)**i,0.5) for i in range(30)]
    filtered = [f.update(p,i/30)[0] for i,p in enumerate(raw)]
    assert np.std(filtered[5:]) < np.std([p[0] for p in raw[5:]])
    f.reset()
    assert f.update((0.9,0.9),2) == (0.9,0.9)


def test_monochrome_render_preserves_separate_strokes():
    strokes = [[Point(0.1,0.2,0),Point(0.2,0.7,1)],
               [Point(0.8,0.2,2),Point(0.9,0.7,3)]]
    image = render_strokes(strokes,1000,400)
    a = np.array(image)
    assert image.mode == "L"
    assert a[:,400:600].min() == 255
    prepared = prepare_line(image)
    assert prepared.mode == "RGB"
    assert np.array(prepared)[0].min() == 255


def test_blank_image_rejected():
    with pytest.raises(ValueError):
        prepare_line(render_strokes([]))


def test_pinch_ratio_handles_hand_size_and_aspect():
    points=[(0,0,0)]*21
    points[5],points[17]=(0.2,0.4,0),(0.6,0.4,0)
    points[4],points[8]=(0.3,0.2,0),(0.4,0.2,0)
    assert pinch_ratio(points) == pytest.approx(0.25)
    assert pinch_ratio([(0,0,0)]*21) is None


def test_configuration_bounds():
    with pytest.raises(ValueError):
        Config(pinch_down_ratio=0.8,pinch_up_ratio=0.5)
    with pytest.raises(ValueError):
        Config(typing_delay_seconds=0)
