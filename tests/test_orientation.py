import numpy as np
import pytest
from slateink.orientation import orient_frame
from slateink.calibration import Surface


def test_horizontal_mirror_moves_pixels_and_pointer_in_the_same_direction():
    frame=np.zeros((100,100,3),np.uint8)
    frame[50,75]=[255,10,20]
    mirrored=orient_frame(frame,True,0)
    assert np.array_equal(mirrored[50,24],[255,10,20])
    surface=Surface.from_corners([(0,0),(1,0),(1,1),(0,1)])
    assert surface.map_point((24/99,50/99))[0]<0.5


def test_orientation_identity_and_clockwise_rotation():
    frame=np.arange(18).reshape(2,3,3).astype(np.uint8)
    assert np.array_equal(orient_frame(frame,False,0),frame)
    rotated=orient_frame(frame,False,90)
    assert rotated.shape==(3,2,3)
    assert np.array_equal(rotated[0,-1],frame[0,0])


@pytest.mark.parametrize("rotation",[0,90,180,270])
def test_mirrored_rotation_is_reversible(rotation):
    frame=np.arange(60).reshape(4,5,3).astype(np.uint8)
    actual=orient_frame(frame,True,rotation)
    import cv2
    restored=orient_frame(cv2.flip(actual,1),False,(360-rotation)%360)
    assert np.array_equal(restored,frame)


def test_bad_rotation_rejected():
    with pytest.raises(ValueError):orient_frame(np.zeros((10,10,3),np.uint8),True,45)
