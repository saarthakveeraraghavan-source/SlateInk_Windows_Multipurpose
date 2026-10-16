"""Current named right-hand recordings -> tracker -> full Desktop routing.

No live camera or desktop input: mouse and window sinks only record requests.
"""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from analyze_swipe_references import analyze
from slateink.config import Config
from slateink.tracking import Hand
from slateink.mouse_control import HandMouseController
from slateink.touchpad_session import TouchpadSession


class Mouse:
    def __init__(self):self.events=[];self.held=set()
    def button(self,name,down):
        self.events.append((name,down))
        if down:self.held.add(name)
        else:self.held.discard(name)
    def release_all(self):
        for name in tuple(self.held):self.button(name,False)
    def move_relative(self,*args):self.events.append(("pointer",*args))
    def wheel(self,**args):self.events.append(("scroll",args))


class Windows:
    def __init__(self):self.events=[]
    def switch(self,direction):self.events.append(direction);return "Reference window request recorded."
    def release_all(self):pass


def replay(data):
    mouse=Mouse();windows=Windows()
    config=Config(camera_mirrored=data["mirrored"],wispr_enabled=True)
    session=TouchpadSession(HandMouseController(config,mouse),None,window_switcher=windows)
    session.set_enabled(True)
    observed=[]
    for row in data["rows"]:
        hands=tuple(Hand(tuple(tuple(p) for p in h["landmarks"]),h["ratio"],h["label"],h["confidence"]) for h in row["hands"])
        before=len(windows.events)
        session.process(hands,row["t"]+1,aspect=data["aspect"])
        if len(windows.events)>before:observed.append({"time_seconds":round(row["t"],3),"direction":windows.events[-1]})
    return {"video":data["video"],"mirrored":data["mirrored"],"events":observed,
            "unwanted_mouse_events":mouse.events,"buttons_released":not mouse.held,
            "sha256":data["sha256"],
            "success":windows.events==[1 if data["video"].startswith("Next") else -1] and not mouse.events and not mouse.held}


def main():
    directory=ROOT/"artifacts/right-hand-swipe-20261015"
    analyze(out=directory)
    results=[replay(json.loads(path.read_text())) for path in sorted(directory.glob("*-raw.json"))+sorted(directory.glob("*-mirrored.json"))]
    report={"success":all(r["success"] for r in results),"live_camera_opened":False,
            "desktop_input_sent":False,"real_local_hand_tracker_used":True,"clips":results}
    (directory/"replay-results.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 0 if report["success"] else 1


if __name__=="__main__":raise SystemExit(main())
