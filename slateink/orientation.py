"""One orientation transform shared by tracking, preview and calibration."""
import cv2


def orient_frame(frame, mirrored=True, rotation=0):
    if rotation not in {0,90,180,270}:
        raise ValueError("Rotation must be 0, 90, 180 or 270 degrees.")
    rotations={90:cv2.ROTATE_90_CLOCKWISE,180:cv2.ROTATE_180,270:cv2.ROTATE_90_COUNTERCLOCKWISE}
    if rotation:
        frame=cv2.rotate(frame,rotations[rotation])
    if mirrored:
        frame=cv2.flip(frame,1)
    return frame
