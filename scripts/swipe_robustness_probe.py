"""Controlled replay perturbations, not a live-camera accuracy benchmark."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from slateink.config import Config
from slateink.tracking import Hand
from slateink.mouse_control import HandMouseController
from slateink.touchpad_session import TouchpadSession


class Mouse:
    def __init__(self):self.events=[];self.held=set()
    def release_all(self):
        for name in tuple(self.held):self.button(name,False)
    def button(self,name,down):
        self.events.append((name,down))
        if down:self.held.add(name)
        else:self.held.discard(name)
    def move_relative(self,*args):self.events.append(("pointer",*args))
    def wheel(self,**args):self.events.append(("scroll",args))


class Switcher:
    def __init__(self):self.events=[]
    def release_all(self):pass
    def switch(self,direction):self.events.append(direction);return "recorded"


def replay(clip,stride=1,offset=0,speed=1,confidence_loss=0):
    mouse=Mouse();switcher=Switcher()
    config=Config(camera_mirrored=clip["mirrored"],touchpad_swipe_cooldown=.4)
    session=TouchpadSession(HandMouseController(config,mouse),None,window_switcher=switcher)
    session.set_enabled(True)
    for row in clip["rows"][offset::stride]:
        hands=tuple(Hand(tuple(tuple(p) for p in h["landmarks"]),h["ratio"],h["label"],max(.01,h["confidence"]-confidence_loss)) for h in row["hands"])
        session.process(hands,1+row["t"]*speed,aspect=clip["aspect"])
    expected=clip["expected_direction"]
    return {"video":clip["video"],"mirrored":clip["mirrored"],"stride":stride,"offset":offset,
            "time_scale":speed,"confidence_reduction":confidence_loss,"events":switcher.events,
            "recognized":switcher.events==[expected],"wrong_or_duplicate":switcher.events not in ([],[expected]),
            "mouse_events":mouse.events,"held":sorted(mouse.held)}


def main():
    clips=json.loads(ROOT.joinpath("tests/fixtures/right_hand_swipe_reference_landmarks.json").read_text())
    cases=[replay(c,stride,offset,speed,loss) for c in clips for stride,offset in ((1,0),(2,0),(2,1),(3,0),(3,1),(3,2)) for speed in (.85,1,1.1) for loss in (0,.1)]
    summary={"cases":len(cases),"recognized":sum(c["recognized"] for c in cases),
             "reverse_recognized":sum(c["recognized"] for c in cases if c["video"].startswith("Previous")),
             "reverse_cases":sum(c["video"].startswith("Previous") for c in cases),
             "wrong_or_duplicate":sum(c["wrong_or_duplicate"] for c in cases),
             "cases_with_mouse_events":sum(bool(c["mouse_events"]) for c in cases),
             "held_inputs":sum(bool(c["held"]) for c in cases)}
    target=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/"artifacts/swipe-robustness.json"
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps({"summary":summary,"controlled_replay_only":True,"cases":cases},indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
    return int(bool(summary["wrong_or_duplicate"] or summary["held_inputs"]))


if __name__=="__main__":raise SystemExit(main())
