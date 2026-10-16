"""Native app/window/packet routing using synthetic hands, with camera/input off."""
from pathlib import Path
import json,sys,time,threading,math
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from slateink.app import MainWindow
from slateink.config import Config,ROOT
from slateink.camera import Packet
from slateink.tracking import Hand


def hand(x,y,label):
    p=[(x,y,0.)]*21;p[0]=(x,y+.12,0.);p[4]=(x-.08,y+.03,0.)
    p[5]=(x-.06,y+.02,0.);p[9]=(x,y+.02,0.);p[17]=(x+.06,y+.02,0.)
    for pip,tip,dx in ((6,8,-.02),(10,12,.01),(14,16,.035),(18,20,.06)):
        p[pip]=(x+dx,y+.02,0.);p[tip]=(x+dx,y-.04,0.)
    p[8]=(x,y,0.)
    return Hand(tuple(p),.9,label,.99)


def main():
    app=QApplication([]);window=MainWindow(Config(initial_mode="hand_mouse",touchpad_submode="fun"))
    report={"success":False,"camera_opened":False,"synthetic_packets":True,"scenes":[]}
    out=ROOT/'artifacts/native-playground';out.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();stage="start";deadline=0;fun=None
    class Worker:
        def __init__(self):
            self.stop_event=threading.Event();self.last=0;self.source=type("Source",(),{"times":[]})()
        def stop(self):self.stop_event.set()
        def take(self):
            now=time.monotonic()
            if now-self.last<1/30:return None
            self.last=now;a=(now-started)*2
            right=hand(.5+math.cos(a)*.20,.48+math.sin(a)*.25,"Left")
            hands=(right,)
            if fun and fun.model.scene=="web":hands=(hand(.22,.5,"Left"),hand(.78,.5,"Right"))
            image=np.full((480,640,3),20,np.uint8)
            return Packet(image,right,len(hands),now,30,30,0,0,hands=hands)
    worker=Worker();window.worker=worker;window.camera_started_at=started;window.last_packet_time=started
    window.show();window.refresh_controls()
    def check_scene():
        assert fun.model.brush is not None,"Native window did not accept fresh hand packets"
        assert not window.hand_mouse.enabled and not window.mouse_sink.held
        assert not window.touchpad_session.dictating
        assert not fun.canvas.preview.isNull()
        item={"scene":fun.model.scene,"fullscreen":fun.isFullScreen(),"fresh_hand":True,"desktop_input_off":True,
              "portals":len(fun.model.portals),"scale":round(fun.model.dome_scale,2)}
        report["scenes"].append(item);fun.grab().save(str(out/(fun.model.scene+'.png')))
    def step():
        nonlocal stage,deadline,fun
        now=time.monotonic()
        if now-started>14:raise RuntimeError("Native playground check timed out")
        if stage=="start":
            if now-started<.6:return
            window.launch_fun();fun=window.fun_window;stage="portal";deadline=now+4;return
        if now<deadline:return
        check_scene()
        if stage=="portal":
            assert fun.model.portals,"Observed circle did not seal a portal"
            fun.choose_scene("web");stage="web";deadline=now+1.3
        elif stage=="web":
            assert fun.model.dome_scale>1.2
            fun.choose_scene("nebula");stage="nebula";deadline=now+1
        else:
            fun.close()
            report["exit_requested_camera_stop"]=worker.stop_event.is_set() and window.fun_window is None
            report["success"]=report["exit_requested_camera_stop"] and len(report["scenes"])==3
            # This synthetic worker has no QThread.finished signal. Complete
            # that test fixture lifecycle before asking QApplication to quit.
            window.worker=None
            app.quit()
    def guarded():
        try:step()
        except Exception as error:
            report["error"]=str(error);worker.stop();window.worker=None;app.quit()
    timer=QTimer();timer.timeout.connect(guarded);timer.start(25)
    try:app.exec()
    finally:
        window.stop_pointer();worker.stop();window.worker=None;window.close()
        (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
    return 0 if report["success"] else 1


if __name__=='__main__':raise SystemExit(main())
