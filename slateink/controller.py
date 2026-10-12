"""Pure capture policy, independently testable from the camera and UI."""
from math import hypot
from .gestures import Pinch
from .smoothing import OneEuro
from .strokes import StrokeBuffer


class CaptureController:
    def __init__(self, config):
        self.buffer = StrokeBuffer(config.max_points)
        self.pinch = Pinch(config.pinch_down_ratio, config.pinch_up_ratio, config.pinch_debounce_ms)
        self.filter = OneEuro()
        self.surface = None
        self.enabled = False
        self.previous = None
        self.hand_label = None
        self.cursor = None

    def interrupt(self):
        self.buffer.pen_up()
        self.pinch.reset()
        self.filter.reset()
        self.previous = None
        self.hand_label = None
        self.cursor = None

    def set_enabled(self, enabled):
        self.enabled = bool(enabled and self.surface is not None)
        self.interrupt()

    def clear(self):
        self.buffer.clear()
        self.interrupt()

    def process(self, hand, t, age_seconds=0):
        if hand is None or age_seconds > 0.20 or self.surface is None:
            self.interrupt()
            return "Show one hand; release pinch to re-arm."
        point = self.surface.map_point(hand.index)
        if point is None:
            self.interrupt()
            return "Pointer outside calibrated slate; release pinch before returning."
        self.cursor = point
        if not self.enabled:
            self.buffer.pen_up()
            return "Capture paused."
        if self.hand_label is not None and hand.label != self.hand_label:
            self.interrupt()
            return "Hand changed; release pinch to re-arm."
        self.hand_label = hand.label
        if self.previous is not None:
            previous, previous_t = self.previous
            if t-previous_t > 0.20 or hypot(point[0]-previous[0], point[1]-previous[1]) > 0.22:
                self.interrupt()
                return "Tracking interrupted; release pinch to re-arm."
        self.previous = point, t
        down = self.pinch.update(hand.ratio, t)
        if down:
            if not self.buffer.active:
                self.filter.reset()
            smoothed = self.filter.update(point, t)
            self.buffer.add(*smoothed, t)
            return "Writing — release thumb/index pinch to lift the pen."
        self.buffer.pen_up()
        self.filter.reset()
        return "Pinch thumb and index to write." if self.pinch.released else "Open thumb/index pinch briefly to arm the pen."
