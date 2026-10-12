"""Run the complete hand-session -> native WASD -> Blender Walk path.

Uses a separate factory scene, synthetic hands and a click-through status HUD.
Never accesses the user's current Blender document or camera.
"""
from pathlib import Path
import argparse,ctypes,json,math,subprocess,sys,time
from ctypes import wintypes
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from PySide6.QtWidgets import QApplication
from slateink.config import ROOT,load_config
from slateink.tracking import Hand
from slateink.touchpad_submodes import WindowsMovementKeys
from slateink.mouse_control import WindowsMouse,HandMouseController
from slateink.touchpad_session import TouchpadSession
from slateink.widgets import GamingStatusOverlay


def pose(extended=(True,True,True,False),x=.5,y=.65,label="Right"):
    p=[(x,y,0)]*21;p[0]=(x,y+.2,0);p[5]=(x-.1,y,0);p[9]=(x,y,0);p[17]=(x+.1,y,0);p[4]=(x-.18,y,0)
    for j,(tip,pip) in enumerate(((8,6),(12,10),(16,14),(20,18))):
        xx=x-.05+j*.05;p[pip]=(xx,y-.12,0);p[tip]=(xx,y-.32 if extended[j] else y+.03,0)
    return Hand(tuple(p),.8,label)


def main(blender):
    app=QApplication([]);api=ctypes.WinDLL("user32")
    api.GetForegroundWindow.restype=wintypes.HWND;api.SetForegroundWindow.argtypes=[wintypes.HWND]
    api.GetCursorPos.argtypes=[ctypes.POINTER(wintypes.POINT)]
    original_window=api.GetForegroundWindow();original=wintypes.POINT();api.GetCursorPos(ctypes.byref(original))
    ready=ROOT/"artifacts/blender-walk-ready.json";trace=ROOT/"artifacts/blender-walk-trace.json"
    for path in (ready,trace):
        if path.exists():path.unlink()
    child=subprocess.Popen([blender,"--factory-startup","--python-exit-code","1","--python",str(ROOT/"scripts/blender_walk_fixture.py")],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    config=replace(load_config(),touchpad_submode="gaming")
    keys=WindowsMovementKeys();mouse=WindowsMouse();controller=HandMouseController(config,mouse)
    session=TouchpadSession(controller,None,keys);hud=GamingStatusOverlay()
    result={"success":False,"physical_gestures_tested":False,"source":"synthetic hands through TouchpadSession","scene":"separate factory-startup Blender window","directions":{},"configured_travel":config.gaming_radius}
    try:
        deadline=time.monotonic()+12;info=None
        while time.monotonic()<deadline:
            if ready.exists():
                try:info=json.loads(ready.read_text(encoding="utf-8"))
                except (OSError,json.JSONDecodeError):time.sleep(.03);continue
                if "error" in info:raise RuntimeError(info["error"])
                if info["walk_running"] and keys.target()==(info["hwnd"],info["pid"]):break
            if child.poll() is not None:raise RuntimeError("Blender fixture exited before becoming ready")
            time.sleep(.03)
        else:raise RuntimeError("Blender fixture did not obtain focus; no input sent")
        expected=(info["hwnd"],info["pid"]);session.set_enabled(True)
        mouse_label="Left" if config.camera_mirrored else "Right"
        helper_label="Right" if config.camera_mirrored else "Left"
        right=pose((True,True,False,False),x=.72,label=mouse_label)
        def frames(left,duration):
            end=time.monotonic()+duration;message=""
            while time.monotonic()<end:
                if keys.target()!=expected or api.GetAsyncKeyState(0x1b)&0x8000:raise RuntimeError("Fixture focus/Escape changed; owned input will release")
                message=session.process((right,left),time.monotonic())
                hud.set_status(session.gaming.wanted,message);hud.show();app.processEvents()
                if keys.target()!=expected:raise RuntimeError("Status display stole destination focus")
                time.sleep(.033)
            return message
        def position():
            for _ in range(8):
                try:return json.loads(trace.read_text(encoding="utf-8"))["view_location"]
                except (OSError,json.JSONDecodeError):time.sleep(.02)
            raise RuntimeError("Fixture position unavailable")
        center=pose(x=.5,label=helper_label)
        frames(center,.5)
        if session.gaming.center is None:raise RuntimeError("Joystick did not center")
        result["overlay_preserved_focus"]=True
        for name,x,y in (("W",.5,.83),("A",.32,.65),("S",.5,.43),("D",.68,.65)):
            before=position();message=frames(pose(x=x,y=y,label=helper_label),.65)
            held=set(keys.held);frames(center,.3);after=position()
            moved=math.dist(before,after)
            result["directions"][name]={"held_correct_key":held=={name},"viewport_distance":round(moved,5),"released_at_center":not keys.held,"message":message.split("  Right mouse:",1)[0]}
        result["blender_version"]=info["blender_version"]
        result["success"]=all(v["held_correct_key"] and v["released_at_center"] and v["viewport_distance"]>.02 for v in result["directions"].values())
        session.set_enabled(False);result["owned_input_released"]=not keys.held and not mouse.held
    finally:
        try:session.set_enabled(False)
        finally:
            hud.close();app.processEvents()
            if child.poll() is None:
                try:child.wait(timeout=9)
                except subprocess.TimeoutExpired:child.terminate();child.wait(timeout=4)
            vx,vy=api.GetSystemMetrics(76),api.GetSystemMetrics(77);vw,vh=api.GetSystemMetrics(78),api.GetSystemMetrics(79)
            mouse.move((original.x-vx)/(vw-1),(original.y-vy)/(vh-1))
            if original_window:api.SetForegroundWindow(original_window)
            (ROOT/"artifacts/native-blender-joystick.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2),flush=True)
    if not result["success"]:raise RuntimeError("Blender joystick fixture failed")


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--blender",required=True)
    main(parser.parse_args().blender)
