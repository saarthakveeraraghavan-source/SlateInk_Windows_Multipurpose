"""Only the configured Wispr shortcut; no arbitrary commands or clipboard access."""
import ctypes
from ctypes import wintypes
import time
import psutil
from .injection import WindowsInjector,INPUT,KEYBDINPUT,InjectionError


class WindowsWisprShortcut:
    def __init__(self):
        self.injector=WindowsInjector();self.api=self.injector.api
        self.owned=[];self.active=False;self.target=None;self.mode=None
        self.checked_at=0;self.available=False

    def flow_running(self):
        if time.monotonic()-self.checked_at>1:
            self.checked_at=time.monotonic()
            self.available=any("wispr" in (p.info.get("name") or "").lower() for p in psutil.process_iter(["name"]))
        return self.available

    def key(self,vk,down):
        if down:
            if vk in self.owned:return
            self.owned.append(vk)
        elif vk not in self.owned:return
        event=INPUT();event.type=1;event.ki=KEYBDINPUT(vk,0,0 if down else 2,0,0)
        if self.api.SendInput(1,ctypes.byref(event),ctypes.sizeof(INPUT))!=1:raise InjectionError("Windows blocked the Wispr shortcut. No automatic retry.")
        if not down:self.owned.remove(vk)

    def release_owned(self):
        failures=[]
        for key in reversed(tuple(self.owned)):
            try:self.key(key,False)
            except InjectionError:failures.append(key)
        if failures:raise InjectionError("Shortcut keys could not be released. Use your keyboard to release Ctrl/Win; hand control is stopped.")

    def combo(self,space=False,hold=False):
        try:
            self.key(0xA2,True);self.key(0x5B,True)
            if space:self.key(0x20,True);self.key(0x20,False)
            if not hold:self.release_owned()
        except Exception:
            self.release_owned();raise

    def begin(self,mode):
        if self.active:return
        if not self.flow_running():raise InjectionError("Open Wispr Flow before using its hand gesture.")
        if self.injector.modifiers_pressed():raise InjectionError("Release keyboard modifiers before starting the Wispr gesture.")
        target=self.injector.destination()
        self.mode=mode
        self.combo(space=mode=="toggle_ctrl_win_space",hold=mode=="hold_ctrl_win")
        self.active=True;self.target=target

    def target_unchanged(self):
        try:return self.active and self.injector.destination()==self.target
        except InjectionError:return False

    def finish(self):
        if not self.active:return
        if not self.target_unchanged():self.cancel();return
        try:
            if self.mode=="hold_ctrl_win":self.release_owned()
            else:self.combo(space=self.mode=="toggle_ctrl_win_space")
        finally:self.active=False;self.target=None

    def cancel(self):
        try:
            if self.active:self.key(0x1B,True);self.key(0x1B,False)
        finally:
            self.release_owned();self.active=False;self.target=None
