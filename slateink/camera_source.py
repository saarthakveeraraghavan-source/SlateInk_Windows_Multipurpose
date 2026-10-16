"""One bounded webcam owner process; the UI/tracker never owns the device."""
from collections import deque
from dataclasses import asdict
import multiprocessing as mp
from multiprocessing.connection import wait
import os
from queue import Empty,Full
import sys
import threading
import time
import cv2


def watch_parent():
    parent=mp.parent_process()
    if parent is not None:
        wait([parent.sentinel])
        os._exit(0) # Parent died: OS releases our camera handle even if read is stuck.


def capture_frames(config,stop,opened,frames,errors):
    """Runs only in the device-owner process. No frames are written to disk."""
    threading.Thread(target=watch_parent,daemon=True).start()
    frames.cancel_join_thread()
    camera=None;original_exposure=None
    try:
        if stop.is_set():return
        camera=cv2.VideoCapture(config["camera_index"],cv2.CAP_DSHOW if sys.platform=="win32" else cv2.CAP_ANY)
        if not camera.isOpened():raise RuntimeError("Cannot open webcam. Close other camera apps and check Windows camera permission.")
        camera.set(cv2.CAP_PROP_FOURCC,cv2.VideoWriter_fourcc(*"MJPG"))
        camera.set(cv2.CAP_PROP_FRAME_WIDTH,config["camera_width"])
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT,config["camera_height"])
        camera.set(cv2.CAP_PROP_FPS,config["camera_fps"])
        if sys.platform=="win32" and config["camera_exposure"] is not None:
            original_exposure=camera.get(cv2.CAP_PROP_EXPOSURE)
            if not camera.set(cv2.CAP_PROP_EXPOSURE,config["camera_exposure"]):
                raise RuntimeError("Camera rejected the configured exposure. Set camera_exposure to null to use the camera default.")
        opened.set();failures=0;sequence=0
        while not stop.is_set():
            ok,bgr=camera.read()
            if not ok:
                failures+=1
                if failures>=5:raise RuntimeError("Webcam stopped delivering frames. Capture has been disabled.")
                stop.wait(.03);continue
            failures=0;sequence+=1
            try:frames.put_nowait((sequence,time.monotonic(),bgr))
            except Full:pass # Bounded mailbox; never accumulate a video backlog.
    except Exception as error:
        try:errors.put_nowait(str(error))
        except Full:pass
    finally:
        if camera is not None:
            if original_exposure is not None:camera.set(cv2.CAP_PROP_EXPOSURE,original_exposure)
            camera.release()
        opened.clear()


def finish_owner(process,stop,grace=.8):
    """Normal release first; only this explicitly owned child can be terminated."""
    stop.set();process.join(grace)
    if process.is_alive():process.terminate();process.join(1)
    if process.is_alive():process.kill();process.join(1)
    if process.is_alive():raise RuntimeError("Webcam owner has not exited; camera shutdown is not confirmed.")


class CameraSource(threading.Thread):
    def __init__(self,config):
        super().__init__(name="visible-camera",daemon=True)
        self.config=config;self.stop_event=threading.Event();self.lock=threading.Lock()
        self.latest=None;self.error=None;self.times=deque(maxlen=90)
        self.sequence=0;self.opened=False;self.resolution=None;self.owner=None

    def run(self):
        context=mp.get_context("spawn")
        stop=context.Event();opened=context.Event()
        frames=context.Queue(maxsize=1);errors=context.Queue(maxsize=1)
        owner=context.Process(target=capture_frames,args=(asdict(self.config),stop,opened,frames,errors),name="SlateInk webcam",daemon=True)
        started=False
        try:
            if self.stop_event.is_set():return
            self.owner=owner;owner.start();started=True
            while not self.stop_event.is_set():
                try:raise RuntimeError(errors.get_nowait())
                except Empty:pass
                self.opened=opened.is_set()
                try:sequence,t,bgr=frames.get(timeout=.03)
                except Empty:
                    if not owner.is_alive():
                        try:message=errors.get(timeout=.1)
                        except Empty:message="Webcam owner exited before capture completed."
                        raise RuntimeError(message)
                    continue
                self.resolution=bgr.shape[1],bgr.shape[0]
                with self.lock:
                    self.times.append(t);self.sequence=sequence;self.latest=sequence,t,bgr
        except Exception as error:self.error=str(error)
        finally:
            if started:
                try:finish_owner(owner,stop)
                except RuntimeError as error:self.error=str(error)
            for channel in (frames,errors):channel.cancel_join_thread();channel.close()
            self.opened=False
            with self.lock:self.latest=None

    def get(self,last_sequence):
        with self.lock:
            if self.latest is None or self.latest[0]==last_sequence:return None
            fps=(len(self.times)-1)/(self.times[-1]-self.times[0]) if len(self.times)>1 else 0
            return (*self.latest,fps)
