import ctypes
import sys
import pytest
from slateink.injection import validate_text, InjectionError, INPUT, WindowsInjector, Destination


@pytest.mark.parametrize("text",["Hello, world!","Differentiate velocity", "Aa 11 --:;!?", "café ₹42"])
def test_plain_unicode_text_allowed(text):
    assert validate_text(text) == text


@pytest.mark.parametrize("text",["", "   ","abc\n", "a\t", "a\b", "x\x1b", "a\u200b", "\ud800"])
def test_command_and_control_characters_rejected(text):
    with pytest.raises(InjectionError):
        validate_text(text)


def test_length_limit():
    with pytest.raises(InjectionError):
        validate_text("x"*21,20)


@pytest.mark.skipif(sys.platform != "win32",reason="Windows ABI")
def test_native_input_structure_matches_windows_64bit_abi():
    assert ctypes.sizeof(INPUT) == 40


def stub_injector(sent=None,focus_changed=False):
    obj = object.__new__(WindowsInjector)
    target = Destination(1,2,3,4)
    obj.escape_pressed = lambda: False
    obj.modifiers_pressed = lambda: False
    obj.destination = lambda **kw: Destination(5,6,7,8) if focus_changed else target
    class API:
        calls=[]
        def SendInput(self,n,events,size):
            self.calls.append([(e.ki.wVk,e.ki.wScan,e.ki.dwFlags) for e in events])
            return n if sent is None else sent
    obj.api = API()
    obj.api.calls=[]
    return obj,target


def test_unicode_keys_have_no_virtual_commands():
    obj,destination = stub_injector()
    obj.send("A!₹",destination)
    assert len(obj.api.calls) == 3
    for pair in obj.api.calls:
        assert pair[0][0] == pair[1][0] == 0
        assert pair[0][2] == 4
        assert pair[1][2] == 6


def test_surrogate_pair_sent_together():
    obj,destination=stub_injector()
    obj.send("😀",destination)
    assert len(obj.api.calls) == 1
    assert len(obj.api.calls[0]) == 4


def test_partial_send_never_retried():
    obj,destination=stub_injector(sent=1)
    with pytest.raises(InjectionError):
        obj.send("ABC",destination)
    assert len(obj.api.calls)==1


def test_changed_focus_stops_before_any_input():
    obj,destination=stub_injector(focus_changed=True)
    with pytest.raises(InjectionError):
        obj.send("ABC",destination)
    assert obj.api.calls==[]


def test_cancel_stops_before_any_input():
    obj,destination=stub_injector()
    with pytest.raises(InjectionError):
        obj.send("ABC",destination,cancelled=lambda:True)
    assert obj.api.calls==[]
