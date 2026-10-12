"""Unicode-only Windows input. No clipboard, Enter, Tab, shell, or retries."""
from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import os
import sys
import time
import unicodedata


class InjectionError(RuntimeError):
    pass


def validate_text(text, max_characters=2000):
    if not text or not text.strip():
        raise InjectionError("There is no text to send.")
    if len(text) > max_characters:
        raise InjectionError("Accepted text exceeds the configured length limit.")
    if any(unicodedata.category(c) in {"Cc", "Cs", "Cf"} for c in text):
        raise InjectionError("Use a single line of text. Enter, Tab, control characters, and hidden formatting are not sent.")
    return text


ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", INPUTUNION)]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
                ("rcCaret", wintypes.RECT)]


@dataclass(frozen=True)
class Destination:
    window: int
    control: int
    thread: int
    pid: int


class UnsupportedInjector:
    def __init__(self, *args):
        raise InjectionError("Text injection is implemented for Windows only. Linux capture/recognition can run, but sending text is disabled.")


class WindowsInjector:
    def __init__(self):
        if sys.platform != "win32":
            raise InjectionError("Windows SendInput is unavailable on this OS.")
        self.api = ctypes.WinDLL("user32", use_last_error=True)
        self.api.GetForegroundWindow.restype = wintypes.HWND
        self.api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.api.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.api.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
        self.api.GetGUIThreadInfo.restype = wintypes.BOOL
        self.api.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        self.api.SendInput.restype = wintypes.UINT
        self.api.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self.api.GetAsyncKeyState.restype = ctypes.c_short

    def escape_pressed(self):
        return bool(self.api.GetAsyncKeyState(0x1B) & 0x8000)

    def modifiers_pressed(self):
        return any(self.api.GetAsyncKeyState(key) & 0x8000 for key in (0x10, 0x11, 0x12, 0x5B, 0x5C))

    def destination(self, allow_own=False):
        window = self.api.GetForegroundWindow()
        if not window:
            raise InjectionError("No foreground window. Click a destination textbox and accept again.")
        pid = wintypes.DWORD()
        thread = self.api.GetWindowThreadProcessId(window, ctypes.byref(pid))
        if not allow_own and pid.value == os.getpid():
            raise InjectionError("Focus is still in SlateInk. Click the destination textbox during the countdown.")
        info = GUITHREADINFO()
        info.cbSize = ctypes.sizeof(info)
        if not self.api.GetGUIThreadInfo(thread, ctypes.byref(info)) or not info.hwndFocus:
            raise InjectionError("No focused destination control. Click an ordinary textbox and try again.")
        return Destination(int(window), int(info.hwndFocus), int(thread), int(pid.value))

    def send(self, text, destination, cancelled=lambda: False, max_characters=2000, allow_own=False):
        validate_text(text, max_characters)
        # One character at a time lets Escape/focus changes stop the remainder.
        for character in text:
            if cancelled() or self.escape_pressed():
                raise InjectionError("Sending stopped. Some text may already be present; no automatic retry.")
            if self.modifiers_pressed():
                raise InjectionError("Sending stopped because a modifier key is held. No automatic retry.")
            if self.destination(allow_own=allow_own) != destination:
                raise InjectionError("Destination focus changed. Sending stopped; no automatic retry.")
            units = character.encode("utf-16-le")
            events = []
            for i in range(0, len(units), 2):
                unit = int.from_bytes(units[i:i+2], "little")
                for flags in (0x0004, 0x0004 | 0x0002):
                    event = INPUT()
                    event.type = 1
                    event.ki = KEYBDINPUT(0, unit, flags, 0, 0)
                    events.append(event)
            batch = (INPUT * len(events))(*events)
            sent = self.api.SendInput(len(events), batch, ctypes.sizeof(INPUT))
            if sent != len(events):
                raise InjectionError("Windows blocked or partially accepted input. Text is retained in preview. No automatic retry.")
            # Let native text controls drain each character. In the real Qt
            # fixture, a burst ending in a surrogate pair reordered the emoji
            # ahead of earlier queued WM_CHAR events. Small pacing preserves
            # order and leaves a useful cancellation window.
            time.sleep(0.008)


def create_injector():
    return WindowsInjector() if sys.platform == "win32" else UnsupportedInjector()
