import math


class OneEuro:
    """Adaptive low-pass filter: steady at rest, less lag during motion."""
    def __init__(self, min_cutoff=1.7, beta=0.35, derivative_cutoff=1.0):
        self.min_cutoff, self.beta, self.derivative_cutoff = min_cutoff, beta, derivative_cutoff
        self.reset()

    def reset(self):
        self.value = self.raw = self.derivative = self.t = None

    @staticmethod
    def alpha(cutoff, dt):
        return 1 / (1 + 1 / (2 * math.pi * cutoff * dt))

    def update(self, point, t):
        if self.t is None or t - self.t > 0.2:
            self.value = self.raw = tuple(point)
            self.derivative, self.t = (0.0, 0.0), t
            return self.value
        dt = max(0.001, t - self.t)
        speed = tuple((point[i] - self.raw[i]) / dt for i in range(2))
        ad = self.alpha(self.derivative_cutoff, dt)
        self.derivative = tuple(ad * speed[i] + (1-ad) * self.derivative[i] for i in range(2))
        a = self.alpha(self.min_cutoff + self.beta * math.hypot(*self.derivative), dt)
        self.value = tuple(a * point[i] + (1-a) * self.value[i] for i in range(2))
        self.raw, self.t = tuple(point), t
        return self.value
