import multiprocessing as mp
from queue import Queue,Full
import threading,time
import numpy as np
from slateink.config import Config
from slateink import camera_source


class LocalQueue(Queue):
    def cancel_join_thread(self):pass


def fake_frames(config,stop,opened,frames,errors):
    frames.cancel_join_thread();opened.set();sequence=0
    while not stop.is_set():
        sequence+=1
        try:frames.put_nowait((sequence,time.monotonic(),np.zeros((120,160,3),np.uint8)))
        except Full:pass
        stop.wait(.02)


def stalled_frames(config,stop,opened,frames,errors):
    opened.set();time.sleep(30) # Models a native driver read ignoring cancellation.


def test_capture_owner_releases_device_in_finally_without_saving_frames(monkeypatch):
    stop=threading.Event();opened=threading.Event();released=[]
    class Camera:
        def isOpened(self):return True
        def set(self,*args):return True
        def read(self):stop.set();return True,np.zeros((120,160,3),np.uint8)
        def release(self):released.append(True)
    monkeypatch.setattr(camera_source.cv2,"VideoCapture",lambda *args:Camera())
    monkeypatch.setattr(camera_source,"watch_parent",lambda:None)
    config={"camera_index":0,"camera_width":160,"camera_height":120,"camera_fps":30,"camera_exposure":None}
    frames=LocalQueue(maxsize=1);errors=LocalQueue()
    camera_source.capture_frames(config,stop,opened,frames,errors)
    assert released==[True] and not opened.is_set() and errors.empty() and frames.qsize()==1


def test_stop_before_start_does_not_open_camera(monkeypatch):
    stop=threading.Event();stop.set()
    monkeypatch.setattr(camera_source,"watch_parent",lambda:None)
    monkeypatch.setattr(camera_source.cv2,"VideoCapture",lambda *args:(_ for _ in ()).throw(AssertionError("Camera opened")))
    camera_source.capture_frames({},stop,threading.Event(),LocalQueue(),LocalQueue())


def test_normal_camera_source_stops_owner_and_clears_frame(monkeypatch):
    monkeypatch.setattr(camera_source,"capture_frames",fake_frames)
    source=camera_source.CameraSource(Config());source.start()
    try:
        deadline=time.monotonic()+6
        while source.get(-1) is None and time.monotonic()<deadline:time.sleep(.02)
        assert source.get(-1) is not None and source.owner.is_alive()
    finally:source.stop_event.set();source.join(4)
    assert not source.is_alive() and not source.owner.is_alive()
    assert not source.opened and source.latest is None and source.error is None


def test_stalled_driver_owner_is_bounded_and_does_not_hold_up_app_exit(monkeypatch):
    monkeypatch.setattr(camera_source,"capture_frames",stalled_frames)
    source=camera_source.CameraSource(Config());source.start()
    try:
        deadline=time.monotonic()+6
        while not source.opened and time.monotonic()<deadline:time.sleep(.02)
        assert source.opened
    finally:
        started=time.monotonic();source.stop_event.set();source.join(4)
    assert time.monotonic()-started<3.5
    assert not source.is_alive() and not source.owner.is_alive() and not source.opened
