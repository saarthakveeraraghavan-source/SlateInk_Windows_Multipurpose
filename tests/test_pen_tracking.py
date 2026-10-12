import cv2
import numpy as np
import pytest
from slateink.pen_tracking import PenMarker


def frame(x=50,y=50):
    image=np.full((200,200,3),255,np.uint8)
    cv2.circle(image,(x,y),5,(0,180,30),-1)
    return image


def test_marker_selection_and_motion():
    p=PenMarker();p.select(frame(),0.25,0.25)
    point=p.detect(frame(60,55),1)
    assert point is not None and point[0]>0.25


def test_plain_black_or_blank_marker_rejected():
    p=PenMarker()
    with pytest.raises(ValueError):p.select(np.full((200,200,3),255,np.uint8),0.5,0.5)


def test_missing_marker_does_not_invent_position():
    p=PenMarker();p.select(frame(),0.25,0.25)
    assert p.detect(np.full((200,200,3),255,np.uint8),1) is None


def test_marker_jump_is_not_followed():
    p=PenMarker();p.select(frame(),0.25,0.25)
    assert p.detect(frame(180,180),1) is None
