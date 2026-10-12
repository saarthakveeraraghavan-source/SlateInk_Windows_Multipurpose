from math import hypot, isfinite


class Pinch:
    """Hysteresis, time debounce, and release-to-arm after every interruption."""
    def __init__(self, down=0.35, up=0.55, debounce_ms=60):
        self.down_threshold, self.up_threshold = down, up
        self.debounce = debounce_ms / 1000
        self.reset()

    def reset(self):
        self.down = False
        self.released = False
        self.candidate = None
        self.since = 0.0

    def update(self, ratio, t):
        if ratio is None or not isfinite(ratio):
            self.reset()
            return False
        if not self.released:
            if ratio >= self.up_threshold:
                if self.candidate != "release":
                    self.candidate, self.since = "release", t
                elif t - self.since >= self.debounce:
                    self.released, self.candidate = True, None
            else:
                self.candidate = None
            return False
        wanted = ratio < self.down_threshold if not self.down else ratio < self.up_threshold
        if wanted == self.down:
            self.candidate = None
        elif self.candidate != wanted:
            self.candidate, self.since = wanted, t
        elif t - self.since >= self.debounce:
            self.down, self.candidate = wanted, None
        return self.down


def pinch_ratio(landmarks, aspect=4 / 3):
    def distance(a, b):
        return hypot((landmarks[a][0] - landmarks[b][0]) * aspect,
                     landmarks[a][1] - landmarks[b][1])
    palm = distance(5, 17)
    return None if palm < 0.025 else distance(4, 8) / palm
