import numpy as np
import cv2
from PIL import Image


def render_strokes(strokes, width=1200, height=500, line_width=5):
    canvas = np.full((height, width), 255, np.uint8)
    for stroke in strokes:
        coords = np.array([[round(p.x*(width-1)), round(p.y*(height-1))] for p in stroke], np.int32)
        if len(coords) == 1:
            cv2.circle(canvas, tuple(coords[0]), max(1, line_width//2), 0, -1, cv2.LINE_AA)
        elif len(coords) > 1:
            cv2.polylines(canvas, [coords], False, 0, line_width, cv2.LINE_AA)
    return Image.fromarray(canvas)


def prepare_line(image):
    """Crop clean ink, retaining margins and the natural line aspect ratio."""
    array = np.array(image.convert("L"))
    ys, xs = np.where(array < 180)
    if len(xs) < 20 or xs.max()-xs.min() < 5 or ys.max()-ys.min() < 5:
        raise ValueError("Not enough handwriting to recognize. Write a word first.")
    x0, x1, y0, y1 = xs.min(), xs.max()+1, ys.min(), ys.max()+1
    cropped = Image.fromarray(array[y0:y1, x0:x1])
    margin = max(12, round(cropped.height * 0.12))
    result = Image.new("RGB", (cropped.width + 2*margin, cropped.height + 2*margin), "white")
    result.paste(cropped, (margin, margin))
    return result
