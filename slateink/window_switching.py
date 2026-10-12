"""Stable window cycling with ordinary Windows foreground APIs."""
import ctypes
from ctypes import wintypes
import os
import sys
import time
from .injection import INPUT, KEYBDINPUT, InjectionError


class WindowCycle:
    """Keep surviving windows in order despite foreground/Z-order changes."""
    def __init__(self, backend):
        self.backend = backend
        self.order = []

    def switch(self, direction):
        if direction not in (-1, 1):
            raise ValueError("Window direction must be next or previous.")
        if self.backend.input_busy():
            return "Release mouse buttons and keyboard modifiers before swiping."
        windows = self.backend.windows()
        live = set(windows)
        self.order = [w for w in self.order if w in live]
        self.order.extend(w for w in windows if w not in self.order)
        current = self.backend.foreground()
        if not self.order or (len(self.order) == 1 and current in live):
            return "No other eligible window to switch to."
        index = self.order.index(current) if current in live else (-1 if direction == 1 else 0)
        target = self.order[(index+direction) % len(self.order)]
        self.backend.activate(target)
        return "Switched to next window — let the hand settle before another air swipe." if direction == 1 else "Switched to previous window — let the hand settle before another air swipe."


class WindowsWindowBackend:
    def __init__(self, excluded_pid=None):
        if sys.platform != "win32":
            raise InjectionError("Window swipe switching is currently available on Windows only.")
        self.excluded_pid = os.getpid() if excluded_pid is None else excluded_pid
        self.api = ctypes.WinDLL("user32", use_last_error=True)
        self.dwm = ctypes.WinDLL("dwmapi")
        self.callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        signatures = {
            "EnumWindows": ([self.callback_type, wintypes.LPARAM], wintypes.BOOL),
            "IsWindowVisible": ([wintypes.HWND], wintypes.BOOL),
            "IsWindowEnabled": ([wintypes.HWND], wintypes.BOOL),
            "IsWindow": ([wintypes.HWND], wintypes.BOOL),
            "IsIconic": ([wintypes.HWND], wintypes.BOOL),
            "GetWindow": ([wintypes.HWND, wintypes.UINT], wintypes.HWND),
            "GetWindowTextW": ([wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
            "GetClassNameW": ([wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
            "GetWindowThreadProcessId": ([wintypes.HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD),
            "GetForegroundWindow": ([], wintypes.HWND),
            "SetForegroundWindow": ([wintypes.HWND], wintypes.BOOL),
            "ShowWindowAsync": ([wintypes.HWND, ctypes.c_int], wintypes.BOOL),
            "GetAsyncKeyState": ([ctypes.c_int], ctypes.c_short),
            "SendInput": ([wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int], wintypes.UINT),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.api, name)
            fn.argtypes, fn.restype = args, result
        self.style = self.api.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else self.api.GetWindowLongW
        self.style.argtypes, self.style.restype = [wintypes.HWND, ctypes.c_int], ctypes.c_ssize_t
        self.dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        self.dwm.DwmGetWindowAttribute.restype = ctypes.c_long
        self.alt_owned = False

    def input_busy(self):
        # Include physical clicks, not just buttons owned by SlateInk.
        return any(self.api.GetAsyncKeyState(k) & 0x8000 for k in (1,2,4,5,6,0x10,0x11,0x12,0x5B,0x5C,0x1B))

    def foreground(self):
        return self.api.GetForegroundWindow()

    def eligible(self, window):
        if not self.api.IsWindow(window) or not self.api.IsWindowVisible(window) or not self.api.IsWindowEnabled(window):
            return False
        pid = wintypes.DWORD()
        self.api.GetWindowThreadProcessId(window, ctypes.byref(pid))
        if not pid.value or pid.value == self.excluded_pid:
            return False
        title = ctypes.create_unicode_buffer(512)
        self.api.GetWindowTextW(window, title, len(title))
        if not title.value.strip() or title.value.lower().startswith("slateink"):
            return False
        cls = ctypes.create_unicode_buffer(256)
        self.api.GetClassNameW(window, cls, len(cls))
        if cls.value in {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}:
            return False
        style = self.style(window, -20)
        if style & (0x80 | 0x08000000): # tool window / no activate
            return False
        if self.api.GetWindow(window, 4) and not style & 0x40000: # owner / explicit app window
            return False
        cloaked = wintypes.DWORD()
        result = self.dwm.DwmGetWindowAttribute(window, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
        return result == 0 and not cloaked.value

    def windows(self):
        result = []
        @self.callback_type
        def collect(window, unused):
            if self.eligible(window):
                result.append(window)
            return True
        if not self.api.EnumWindows(collect, 0):
            raise InjectionError("Windows could not list open windows; hand control stopped.")
        return result

    def _alt(self, down):
        if down:
            self.alt_owned = True
        elif not self.alt_owned:
            return
        event = INPUT()
        event.type = 1
        event.ki = KEYBDINPUT(0x12, 0, 0 if down else 2, 0, 0)
        if self.api.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
            raise InjectionError("Windows blocked window-switch input. Release Alt with your keyboard; hand control stopped.")
        if not down:
            self.alt_owned = False

    def release_all(self):
        self._alt(False)

    def activate(self, window):
        if self.input_busy() or not self.eligible(window):
            raise InjectionError("Window or input changed during swipe; hand control stopped.")
        if self.api.IsIconic(window):
            self.api.ShowWindowAsync(window, 9) # SW_RESTORE
        # A user-requested Alt press enables foreground activation under the
        # documented Windows policy. Never change focus-lock settings or attach
        # thread input queues. Always release the one key we own.
        try:
            self._alt(True)
            # SendInput queues the key; allow Windows to consume Alt before
            # requesting activation. This pause occurs only on a fired swipe.
            time.sleep(.02)
            accepted = self.api.SetForegroundWindow(window)
        finally:
            self.release_all()
        # Cross-process activation can be acknowledged before its input queue
        # updates the foreground handle. Observe once requested, never retry it.
        deadline = time.monotonic()+.15
        while accepted and self.foreground() != window and time.monotonic() < deadline:
            time.sleep(.01)
        if not accepted or self.foreground() != window:
            raise InjectionError("Windows did not confirm the window switch; hand control stopped. No automatic retry.")


class WindowsWindowSwitcher(WindowCycle):
    def __init__(self):
        super().__init__(WindowsWindowBackend())

    def release_all(self):
        self.backend.release_all()
