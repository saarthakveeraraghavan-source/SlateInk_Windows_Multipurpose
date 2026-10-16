from dataclasses import replace
import ctypes
from ctypes import wintypes
from types import SimpleNamespace
import math
import pytest
from slateink.config import Config
from slateink.window_swipe import WindowSwipe
from slateink.window_switching import WindowCycle, WindowsWindowBackend
from slateink.injection import INPUT, InjectionError
from slateink.mouse_control import HandMouseController
from slateink.touchpad_session import TouchpadSession
from test_touchpad_product import pose, rock_pose, Shortcuts
from test_mouse_control import hand
from test_touchpad_submodes import Keys, Pixels
from test_air_swipe import air_pose


class Backend:
    def __init__(self):self.items=[10,20,30];self.current=10;self.events=[];self.busy=False
    def input_busy(self):return self.busy
    def windows(self):return self.items
    def foreground(self):return self.current
    def activate(self,w):
        self.events.append(w);self.current=w
        self.items=[w]+[x for x in self.items if x!=w] # emulate changing Z order


def test_stable_order_reaches_every_window_and_reverses():
    backend=Backend();cycle=WindowCycle(backend)
    for _ in range(6):cycle.switch(1)
    assert backend.events==[20,30,10,20,30,10]
    for _ in range(3):cycle.switch(-1)
    assert backend.events[-3:]==[30,20,10]


def test_closed_and_new_windows_update_without_reordering_survivors():
    backend=Backend();cycle=WindowCycle(backend);cycle.switch(1)
    backend.items=[40,30,20]
    cycle.switch(1);cycle.switch(1);cycle.switch(1)
    assert backend.events==[20,30,40,20]


@pytest.mark.parametrize("items,current,direction,expected", [([],10,1,[]),([10],10,1,[]),([20],10,1,[20]),([20,30],10,-1,[30])])
def test_missing_foreground_and_small_window_lists(items,current,direction,expected):
    backend=Backend();backend.items=items;backend.current=current
    WindowCycle(backend).switch(direction)
    assert backend.events==expected


def test_physical_input_blocks_window_switch():
    backend=Backend();backend.busy=True
    assert "Release" in WindowCycle(backend).switch(1)
    assert not backend.events


class Switcher:
    def __init__(self):self.events=[]
    def switch(self,direction):self.events.append(direction);return "switched"
    def release_all(self):pass


def session(config=None):
    sink=Pixels();controller=HandMouseController(config or Config(touchpad_hand="Right",camera_mirrored=False),sink)
    switcher=Switcher();keys=Keys();flow=Shortcuts()
    ses=TouchpadSession(controller,flow,keys,switcher);ses.set_enabled(True)
    for i in range(8):ses.process((pose(label="Right"),),1+i*.033)
    return ses,sink,switcher,flow


def session_sweep(ses,start=1.3,helper=None):
    for i in range(26):
        progress=max(0,min(1,(i-9)/8))
        hands=(air_pose(progress,mirrored=ses.config.camera_mirrored),)
        if helper is not None:hands+=(helper,)
        ses.process(hands,start+i*.05,aspect=16/9)


def test_swipe_freezes_pointer_and_never_clicks_or_scrolls():
    ses,sink,switcher,_=session();sink.events.clear()
    session_sweep(ses)
    assert switcher.events==[1] and not sink.events and not sink.held


@pytest.mark.parametrize("submode",["gaming","drawing"])
def test_swipes_isolated_from_other_submodes(submode):
    ses,_,switcher,_=session(Config(touchpad_submode=submode))
    session_sweep(ses)
    assert not switcher.events and not ses.swipe.armed


def test_disabled_swipes_and_three_finger_scroll_never_switch():
    ses,_,switcher,_=session(Config(touchpad_swipe_enabled=False));session_sweep(ses)
    assert not switcher.events
    ses,_,switcher,_=session()
    for i in range(18):ses.process((pose((True,True,True,False),x=.5-i*.014),),1.3+i*.033)
    assert not switcher.events


def test_two_palm_pause_and_helper_precision_take_priority():
    ses,_,switcher,_=session()
    for i in range(24):ses.process((pose((True,)*4,label="Right"),pose((True,)*4,label="Left")),1.3+i*.05)
    assert not switcher.events and not ses.swipe.armed
    ses,_,switcher,_=session()
    for i in range(20):ses.process((pose(x=.5+i*.005,label="Right"),pose((True,)*4,label="Left")),1.3+i*.033)
    assert not switcher.events


def test_wispr_blocks_swipe_and_clears_candidate():
    ses,_,switcher,flow= session(Config(wispr_enabled=True))
    for i in range(30):ses.process((pose(label="Right"),rock_pose(label="Left")),1.3+i*.033)
    assert ses.dictating
    session_sweep(ses,start=2.4,helper=rock_pose(label="Left"))
    assert not switcher.events and not ses.swipe.armed


def test_held_click_cannot_turn_into_swipe():
    ses,sink,switcher,_=session()
    for t in (1.3,1.4):ses.controller.process(hand(label="Right"),t)
    for t in (1.45,1.53):ses.controller.process(hand(left=.2,label="Right"),t)
    assert sink.held
    for i in range(20):ses.process((hand(left=.2,x=.5+i*.001,label="Right"),),1.6+i*.05)
    assert not switcher.events and sink.held=={"left"}
    ses.interrupt();assert not sink.held


@pytest.mark.parametrize("reason",["stale","lost","ambiguous","pause","disable","mode"])
def test_session_interruptions_discard_swipe(reason):
    ses,_,switcher,_=session()
    for i in range(7):ses.process((air_pose(),),1.3+i*.05,aspect=16/9)
    ses.process((air_pose(1),),1.65,aspect=16/9)
    if reason=="stale":ses.process((air_pose(1),),1.7,age=.4)
    elif reason=="lost":
        for t in (1.7,1.8,1.9):ses.process((),t)
    elif reason=="ambiguous":ses.process((pose(),pose()),1.7)
    elif reason=="pause":ses.toggle_pause();ses.toggle_pause()
    elif reason=="disable":ses.set_enabled(False);ses.set_enabled(True)
    elif reason=="mode":
        ses.config=replace(ses.config,touchpad_submode="drawing");ses.process((pose(),),1.7)
        ses.config=replace(ses.config,touchpad_submode="desktop")
    for i in range(12):ses.process((air_pose(1),),2+i*.05,aspect=16/9)
    assert not switcher.events


def test_release_failure_still_releases_mouse_and_keys():
    ses,sink,switcher,_=session();sink.held.add("left");ses.gaming.sink.held.add("W")
    def fail():raise InjectionError("release failure")
    switcher.release_all=fail
    with pytest.raises(InjectionError):ses.interrupt()
    assert not sink.held and not ses.gaming.sink.held and not ses.swipe.armed


@pytest.mark.parametrize("options",[{"touchpad_swipe_enabled":1},{"touchpad_swipe_sensitivity":0},{"touchpad_swipe_sensitivity":math.nan},{"touchpad_swipe_cooldown":.1}])
def test_invalid_swipe_preferences(options):
    with pytest.raises(ValueError):Config(**options)


@pytest.mark.parametrize("overrides,expected", [({},True),({"visible":False},False),({"valid":False},False),({"enabled":False},False),({"pid":123},False),({"title":"SlateInk"},False),({"title":" "},False),({"cls":"WorkerW"},False),({"style":0x80},False),({"style":0x08000000},False),({"owner":8},False),({"owner":8,"style":0x40000},True),({"cloaked":1},False),({"dwm_error":1},False)])
def test_native_window_filter(overrides,expected):
    settings=dict(valid=True,visible=True,enabled=True,pid=456,title="Document",cls="Ordinary",style=0,owner=0,cloaked=0,dwm_error=0)
    settings.update(overrides)
    def pid(window,out):ctypes.cast(out,ctypes.POINTER(wintypes.DWORD)).contents.value=settings["pid"];return 7
    def title(window,out,length):out.value=settings["title"];return len(out.value)
    def cls(window,out,length):out.value=settings["cls"];return len(out.value)
    def dwm(window,attribute,out,length):
        ctypes.cast(out,ctypes.POINTER(wintypes.DWORD)).contents.value=settings["cloaked"]
        return settings["dwm_error"]
    backend=WindowsWindowBackend.__new__(WindowsWindowBackend);backend.excluded_pid=123
    backend.api=SimpleNamespace(IsWindow=lambda _:settings["valid"],IsWindowVisible=lambda _:settings["visible"],IsWindowEnabled=lambda _:settings["enabled"],GetWindowThreadProcessId=pid,GetWindowTextW=title,GetClassNameW=cls,GetWindow=lambda *_:settings["owner"])
    backend.style=lambda *_:settings["style"]
    backend.dwm=SimpleNamespace(DwmGetWindowAttribute=dwm)
    assert backend.eligible(10)==expected


@pytest.mark.parametrize("failure",[None,"press","activation","release"])
def test_native_activation_confirms_async_focus_and_cleans_alt(monkeypatch,failure):
    backend=WindowsWindowBackend.__new__(WindowsWindowBackend);backend.alt_owned=False
    events=[];requests=[];polls=[]
    def send(count,pointer,size):
        event=ctypes.cast(pointer,ctypes.POINTER(INPUT)).contents
        events.append((event.ki.wVk,event.ki.dwFlags))
        if failure=="press" and event.ki.dwFlags==0:return 0
        if failure=="release" and event.ki.dwFlags==2:return 0
        return 1
    def activate(window):requests.append(window);return failure!="activation"
    def foreground():
        polls.append(True)
        return 20 if len(polls)>=3 else 10
    backend.api=SimpleNamespace(GetAsyncKeyState=lambda _:0,IsIconic=lambda _:True,ShowWindowAsync=lambda *args:None,SendInput=send,SetForegroundWindow=activate,GetForegroundWindow=foreground)
    backend.eligible=lambda _:True
    monkeypatch.setattr("slateink.window_switching.time.sleep",lambda _:None)
    if failure:
        with pytest.raises(InjectionError):backend.activate(20)
    else:
        backend.activate(20)
        assert len(polls)>=3
    assert events==[(0x12,0),(0x12,2)]
    assert len(requests)==(0 if failure=="press" else 1)
    assert backend.alt_owned==(failure=="release")


def test_swipe_settings_save_and_reload_locally(tmp_path,monkeypatch):
    import slateink.config as config_module
    monkeypatch.setattr(config_module,"ROOT",tmp_path)
    config_module.save_preferences({"touchpad_swipe_enabled":False,"touchpad_swipe_sensitivity":1.5,"touchpad_swipe_cooldown":1.1})
    config=config_module.load_config()
    assert not config.touchpad_swipe_enabled and config.touchpad_swipe_sensitivity==1.5 and config.touchpad_swipe_cooldown==1.1
