from types import SimpleNamespace
import ctypes
import pytest
from slateink.desktop_shortcuts import WindowsWisprShortcut
from slateink.injection import INPUT,InjectionError,Destination


def backend(mode="toggle_ctrl_win"):
    b=object.__new__(WindowsWisprShortcut);b.owned=[];b.active=False;b.target=None;b.mode=None
    events=[];target=Destination(10,11,12,13)
    def send(count,pointer,size):
        event=ctypes.cast(pointer,ctypes.POINTER(INPUT)).contents
        events.append((event.ki.wVk,event.ki.dwFlags));return 1
    b.api=SimpleNamespace(SendInput=send)
    b.injector=SimpleNamespace(modifiers_pressed=lambda:False,destination=lambda:target)
    b.flow_running=lambda:True
    return b,events,target


def test_user_toggle_sends_one_chord_on_start_and_one_on_finish():
    b,e,t=backend();b.begin("toggle_ctrl_win");b.begin("toggle_ctrl_win");b.finish()
    chord=[(0xA2,0),(0x5B,0),(0x5B,2),(0xA2,2)]
    assert e==chord*2 and not b.active and not b.owned


def test_standard_hold_keeps_keys_owned_until_release():
    b,e,t=backend();b.begin("hold_ctrl_win")
    assert b.owned==[0xA2,0x5B]
    b.finish();assert not b.owned and len(e)==4


def test_focus_change_cancels_without_sending_a_second_toggle():
    b,e,t=backend();b.begin("toggle_ctrl_win")
    b.injector.destination=lambda:Destination(99,98,97,96);b.finish()
    assert e[-2:]==[(0x1B,0),(0x1B,2)] and len(e)==6 and not b.active


def test_missing_flow_or_held_physical_modifiers_block_start():
    b,e,t=backend();b.flow_running=lambda:False
    with pytest.raises(InjectionError):b.begin("toggle_ctrl_win")
    b.flow_running=lambda:True;b.injector.modifiers_pressed=lambda:True
    with pytest.raises(InjectionError):b.begin("toggle_ctrl_win")
    assert not e


def test_partial_key_failure_releases_owned_keys_and_never_retries_start():
    b,e,t=backend();native=b.api.SendInput
    def fail(count,pointer,size):
        event=ctypes.cast(pointer,ctypes.POINTER(INPUT)).contents
        if event.ki.wVk==0x5B and event.ki.dwFlags==0:return 0
        return native(count,pointer,size)
    b.api.SendInput=fail
    with pytest.raises(InjectionError):b.begin("hold_ctrl_win")
    assert not b.owned and not b.active and e==[(0xA2,0),(0x5B,2),(0xA2,2)]
