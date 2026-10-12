from dataclasses import dataclass
import cv2
import numpy as np


@dataclass
class Surface:
    corners: np.ndarray
    matrix: np.ndarray

    @classmethod
    def from_corners(cls, corners):
        points = np.asarray(corners, dtype=np.float32)
        if points.shape != (4, 2) or not np.isfinite(points).all():
            raise ValueError("Choose four finite corner points.")
        if np.any(points < 0) or np.any(points > 1):
            raise ValueError("Corners must lie inside the camera view.")
        contour = points.reshape(-1, 1, 2)
        if not cv2.isContourConvex(contour) or abs(cv2.contourArea(contour)) < 0.025:
            raise ValueError("Select a larger, convex rectangle in TL, TR, BR, BL order.")
        # Positive signed area corresponds to clockwise screen coordinates.
        if cv2.contourArea(contour, oriented=True) <= 0:
            raise ValueError("Click clockwise: top left, top right, bottom right, bottom left.")
        if (points[1, 0] <= points[0, 0] or points[2, 0] <= points[3, 0]
                or points[3, 1] <= points[0, 1] or points[2, 1] <= points[1, 1]):
            raise ValueError("Corner labels do not match TL, TR, BR, BL. Keep the slate approximately upright.")
        destination = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32)
        matrix = cv2.getPerspectiveTransform(points, destination)
        if not np.isfinite(matrix).all() or np.linalg.cond(matrix) > 10000:
            raise ValueError("Surface is too oblique. Move the camera toward an overhead view.")
        return cls(points, matrix)

    def map_point(self, point):
        mapped = cv2.perspectiveTransform(np.asarray([[point]], np.float32), self.matrix)[0, 0]
        if not np.isfinite(mapped).all() or np.any(mapped < -1e-6) or np.any(mapped > 1+1e-6):
            return None
        mapped = np.clip(mapped, 0, 1)
        return float(mapped[0]), float(mapped[1])
