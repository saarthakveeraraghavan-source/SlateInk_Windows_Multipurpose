from dataclasses import dataclass
from math import hypot, isfinite
import copy


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    t: float


class StrokeBuffer:
    def __init__(self, max_points=40000):
        self.max_points = max_points
        self.strokes: list[list[Point]] = []
        self.active = False
        self.count = 0

    def add(self, x, y, t):
        if not all(isfinite(v) for v in (x, y, t)) or not (0 <= x <= 1 and 0 <= y <= 1):
            self.pen_up()
            return False
        if self.count >= self.max_points:
            self.pen_up()
            raise BufferError("Canvas is full. Submit or clear the current line.")
        if self.active:
            previous = self.strokes[-1][-1]
            if t < previous.t:
                raise ValueError("Stroke timestamps must be monotonic.")
            if hypot(x-previous.x, y-previous.y) < 0.001 and t-previous.t < 0.1:
                return False
        else:
            self.strokes.append([])
            self.active = True
        self.strokes[-1].append(Point(x, y, t))
        self.count += 1
        return True

    def pen_up(self):
        self.active = False

    def clear(self):
        self.strokes.clear()
        self.count = 0
        self.pen_up()

    def undo(self):
        self.pen_up()
        if self.strokes:
            self.count -= len(self.strokes.pop())

    def snapshot(self):
        return copy.deepcopy(self.strokes)
