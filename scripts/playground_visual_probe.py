"""Render synthetic playground motion and report frame cost; no camera or audio."""
from pathlib import Path
import os,sys,time,json,statistics
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from slateink.config import ROOT
from slateink.fun_playground import FunWindow


def main():
    app=QApplication([]);out=ROOT/'artifacts/playground-visuals';out.mkdir(parents=True,exist_ok=True)
    report={"synthetic_motion":True,"camera_opened":False,"scenes":[]}
    for scene in ("portal","web","nebula"):
        window=FunWindow(scene);window.timer.stop();window.resize(1400,950);window.show();app.processEvents()
        window.toggle_demo(True);now=time.monotonic();window.demo_start=now
        for i in range(421):
            t=now+i/60;window.demo_frame(t);window.model.advance(t)
        samples=[]
        for _ in range(24):
            start=time.perf_counter();image=window.grab();samples.append((time.perf_counter()-start)*1000)
        image.save(str(out/(scene+'.png')))
        report['scenes'].append({"scene":scene,"render_median_ms":round(statistics.median(samples),2),
                                 "particles":len(window.model.particles),"portals":len(window.model.portals),
                                 "image":str(out/(scene+'.png'))})
        window.close();app.processEvents()
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
