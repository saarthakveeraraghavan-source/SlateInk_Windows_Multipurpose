"""A visible, removable global Ctrl+Alt+M shortcut using ordinary Win32 APIs."""
import ctypes
from ctypes import wintypes
from PySide6.QtCore import QObject,Signal,QAbstractNativeEventFilter
from PySide6.QtWidgets import QApplication
from .injection import InjectionError


class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self,owner):super().__init__();self.owner=owner
    def nativeEventFilter(self,event_type,message):
        msg=ctypes.cast(int(message),ctypes.POINTER(wintypes.MSG)).contents
        if msg.message==0x0312 and msg.wParam==self.owner.identifier:
            self.owner.activated.emit();return True,0
        return False,0


class DesktopHotkey(QObject):
    activated=Signal()
    def __init__(self,parent=None):
        super().__init__(parent);self.identifier=0x5349;self.active=False
        self.api=ctypes.WinDLL("user32",use_last_error=True)
        self.api.RegisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int,wintypes.UINT,wintypes.UINT]
        self.api.RegisterHotKey.restype=wintypes.BOOL
        self.api.UnregisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int]
        self.filter=HotkeyFilter(self)
        if not self.api.RegisterHotKey(None,self.identifier,0x4000|0x2|0x1,0x4D):raise InjectionError("Ctrl+Alt+M is already in use. Hand gestures and the app buttons remain available.")
        self.active=True;QApplication.instance().installNativeEventFilter(self.filter)
    def close(self):
        if self.active:
            self.api.UnregisterHotKey(None,self.identifier)
            QApplication.instance().removeNativeEventFilter(self.filter);self.active=False
