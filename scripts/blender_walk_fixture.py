"""Disposable factory-startup Blender scene; aggregate walk movement only."""
import bpy
import ctypes,json,os,time
from ctypes import wintypes
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
READY=ROOT/"artifacts/blender-walk-ready.json"
TRACE=ROOT/"artifacts/blender-walk-trace.json"
api=ctypes.WinDLL("user32")
api.GetForegroundWindow.restype=wintypes.HWND
api.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
api.SetForegroundWindow.argtypes=[wintypes.HWND]
state={"fixture":"factory-startup scene", "blender_version":bpy.app.version_string,"walk_running":False}
region_view=None
if hasattr(bpy.context.preferences.view,"show_splash"):bpy.context.preferences.view.show_splash=False


def sample():
    if region_view is None:return None
    state["view_location"]=list(region_view.view_location)
    TRACE.write_text(json.dumps(state),encoding="utf-8")
    return .04


def start():
    global region_view
    try:
        win=bpy.context.window_manager.windows[0]
        area=next(a for a in win.screen.areas if a.type=="VIEW_3D")
        region=next(r for r in area.regions if r.type=="WINDOW")
        region_view=area.spaces.active.region_3d
        handles=[]
        callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        def collect(hwnd,param):
            pid=wintypes.DWORD();api.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
            if pid.value==os.getpid() and api.IsWindowVisible(hwnd):handles.append(int(hwnd))
            return True
        api.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
        callback=callback_type(collect);api.EnumWindows(callback,0)
        if not handles:raise RuntimeError("Fixture window unavailable")
        api.SetForegroundWindow(handles[0])
        with bpy.context.temp_override(window=win,area=area,region=region):
            invoked=bpy.ops.view3d.walk("INVOKE_DEFAULT")
        state["walk_running"]="RUNNING_MODAL" in invoked
        state["view_location"]=list(region_view.view_location)
        TRACE.write_text(json.dumps(state),encoding="utf-8")
        READY.write_text(json.dumps({"pid":os.getpid(),"hwnd":handles[0],**state}),encoding="utf-8")
        bpy.app.timers.register(sample,first_interval=.04)
    except Exception as exc:
        READY.write_text(json.dumps({"error":type(exc).__name__+": "+str(exc)}),encoding="utf-8")
    return None


def finish():
    sample();bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(start,first_interval=2.0)
bpy.app.timers.register(finish,first_interval=13.0)
