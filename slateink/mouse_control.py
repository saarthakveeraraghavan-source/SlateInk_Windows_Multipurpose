"""Deliberately armed hand mouse policy and ordinary Windows input adapter."""
import ctypes
from ctypes import wintypes
from math import hypot,isfinite
import sys
from .gestures import Pinch,pinch_ratio
from .smoothing import OneEuro
from .injection import INPUT,MOUSEINPUT,InjectionError
from .hand_gestures import visible_control,scroll_pose,fingers


def middle_pinch_ratio(hand,aspect=4/3):
    points=hand.landmarks
    palm=hypot((points[5][0]-points[17][0])*aspect,points[5][1]-points[17][1])
    if palm<0.025:return None
    return hypot((points[4][0]-points[12][0])*aspect,points[4][1]-points[12][1])/palm


def resolve_pinches(left,right,config,held=None):
    """Close joined fingers can make both distances small: require a clear winner.

    Equal/near-equal distances stay blocked. A held gesture cannot switch button
    identity without release/rearm, even if the thumb moves toward the other tip.
    """
    if left<config.pinch_down_ratio and right<config.pinch_down_ratio:
        near,far=min(left,right),max(left,right)
        if far-near<.12 or near>far*.6:return None
        winner="left" if left<right else "right"
        if held is not None and winner!=held:return None
        if winner=="left":right=config.pinch_up_ratio+.01
        else:left=config.pinch_up_ratio+.01
    return left,right


class WindowsMouse:
    def __init__(self):
        if sys.platform!="win32":raise InjectionError("Desktop mouse injection is Windows-only.")
        self.api=ctypes.WinDLL("user32",use_last_error=True)
        self.api.SendInput.argtypes=[wintypes.UINT,ctypes.POINTER(INPUT),ctypes.c_int]
        self.api.SendInput.restype=wintypes.UINT
        self.api.GetCursorPos.argtypes=[ctypes.POINTER(wintypes.POINT)]
        self.api.GetCursorPos.restype=wintypes.BOOL
        self.api.GetSystemMetrics.argtypes=[ctypes.c_int]
        self.api.GetSystemMetrics.restype=ctypes.c_int
        self.held=set()

    def _event(self,flags,x=0,y=0):
        event=INPUT(); event.type=0
        event.mi=MOUSEINPUT(x,y,0,flags,0,0)
        sent=self.api.SendInput(1,ctypes.byref(event),ctypes.sizeof(INPUT))
        if sent!=1:raise InjectionError("Windows blocked mouse input. Mouse control disabled; no automatic retry.")

    def move(self,x,y):
        if not all(isfinite(v) for v in (x,y)):raise InjectionError("Invalid pointer coordinates.")
        self._event(0x0001|0x8000|0x4000,round(max(0,min(1,x))*65535),round(max(0,min(1,y))*65535))

    def move_relative(self,dx,dy):
        if not all(isfinite(v) for v in (dx,dy)):raise InjectionError("Invalid touchpad movement.")
        point=wintypes.POINT()
        if not self.api.GetCursorPos(ctypes.byref(point)):raise InjectionError("Cannot read current cursor position.")
        vx,vy=self.api.GetSystemMetrics(76),self.api.GetSystemMetrics(77)
        width,height=self.api.GetSystemMetrics(78),self.api.GetSystemMetrics(79)
        if width<2 or height<2:raise InjectionError("Desktop geometry unavailable.")
        self.move((point.x-vx)/(width-1)+dx,(point.y-vy)/(height-1)+dy)

    def button(self,name,down):
        flags={('left',True):2,('left',False):4,('right',True):8,('right',False):16}
        if down:
            if name in self.held:return
            # Record ownership before SendInput: if native acceptance is unclear,
            # an emergency release still has evidence of our attempted press.
            self.held.add(name)
            self._event(flags[name,True])
        elif name in self.held:
            self._event(flags[name,False]); self.held.discard(name)

    def pixel_scale(self):
        # Primary monitor height defines reach; both axes use this same scalar.
        height=self.api.GetSystemMetrics(1)
        if height<2:raise InjectionError("Desktop geometry unavailable.")
        return height

    def move_pixels(self,dx,dy):
        # Convert exact pixel deltas to absolute desktop coordinates, bypassing
        # Windows relative-mouse acceleration. Retain fractions in the caller.
        width,height=self.api.GetSystemMetrics(78),self.api.GetSystemMetrics(79)
        if width<2 or height<2:raise InjectionError("Desktop geometry unavailable.")
        self.move_relative(dx/(width-1),dy/(height-1))

    def wheel(self,vertical=0,horizontal=0):
        for flags,value in ((0x0800,vertical),(0x1000,horizontal)):
            if not isfinite(value):raise InjectionError("Invalid scroll movement.")
            if value:
                event=INPUT();event.type=0;event.mi=MOUSEINPUT(0,0,round(value)&0xffffffff,flags,0,0)
                if self.api.SendInput(1,ctypes.byref(event),ctypes.sizeof(INPUT))!=1:raise InjectionError("Windows blocked scrolling; control stopped.")

    def release_all(self):
        failures=[]
        for name in tuple(self.held):
            try:self.button(name,False)
            except InjectionError:failures.append(name)
        if failures:raise InjectionError("Windows did not confirm mouse-button release. Use your physical mouse to release; control remains disabled.")


class HandMouseController:
    def __init__(self,config,sink):
        self.config=config; self.sink=sink
        self.left=Pinch(config.pinch_down_ratio,config.pinch_up_ratio,config.pinch_debounce_ms,
                        press_debounce_ms=25,latch_press=True)
        self.right=Pinch(config.pinch_down_ratio,config.pinch_up_ratio,config.pinch_debounce_ms,press_debounce_ms=100)
        self.filter=OneEuro(min_cutoff=1.4,beta=0.25)
        self.enabled=False; self.surface=None
        self.last=None; self.label=None; self.button_held=None
        self.right_enabled=True
        self.reference=None; self.clutched=False; self.clutch_since=None; self.pressed_at=None
        self.press_anchor=None;self.dragging=False;self.release_until=0
        self.scroll_filter=OneEuro(min_cutoff=2,beta=.3);self.scroll_reference=None;self.scroll_axis=None;self.scroll_remainder=0
        self.click_kind=None;self.click_origin=None

    def interrupt(self):
        try:self.sink.release_all()
        finally:
            self.button_held=None; self.left.reset(); self.right.reset()
            self.filter.reset(); self.last=None; self.label=None
            self.reference=None; self.clutched=False; self.clutch_since=None; self.pressed_at=None
            self.press_anchor=None;self.dragging=False;self.release_until=0;self.reset_scroll()
            self.click_kind=None;self.click_origin=None

    def reset_scroll(self):
        self.scroll_filter.reset();self.scroll_reference=None;self.scroll_axis=None;self.scroll_remainder=0

    def _scroll(self,anchor,t):
        point=self.scroll_filter.update(anchor,t)
        if self.scroll_reference is None:self.scroll_reference=point;return
        dx,dy=point[0]-self.scroll_reference[0],point[1]-self.scroll_reference[1]
        if self.scroll_axis is None:
            if hypot(dx,dy)<.006:return
            self.scroll_axis="horizontal" if abs(dx)>abs(dy)*1.4 else "vertical"
        delta=dx if self.scroll_axis=="horizontal" else -dy
        if self.config.touchpad_natural_scroll:delta=-delta
        self.scroll_reference=point;self.scroll_remainder+=delta*self.config.touchpad_scroll_speed*120
        steps=max(-3,min(3,int(self.scroll_remainder/120)))
        if steps:
            value=steps*120;self.scroll_remainder-=value
            self.sink.wheel(vertical=value if self.scroll_axis=="vertical" else 0,horizontal=value if self.scroll_axis=="horizontal" else 0)

    def set_enabled(self,enabled):
        self.enabled=False
        self.interrupt()
        self.enabled=bool(enabled)

    def _anchor(self,hand):
        # Knuckles move less than fingertips during a pinch; no screen XY map.
        return ((hand.landmarks[5][0]+hand.landmarks[9][0])/2,
                (hand.landmarks[5][1]+hand.landmarks[9][1])/2)

    def observe_open(self,hand,t,aspect=4/3):
        """Remember a visible open pinch while another gesture owns movement.

        An idle open palm reserves the swipe channel, but is also valid evidence
        that the thumb/index have separated. Never inject input from this path.
        """
        if not visible_control(hand) or hand.ratio is None:
            self.interrupt();return
        right=middle_pinch_ratio(hand,aspect)
        if hand.ratio<self.config.pinch_up_ratio or right is None or right<self.config.pinch_up_ratio:
            self.interrupt();return
        point=self._anchor(hand)
        if (self.button_held is not None or (self.label is not None and self.label!=hand.label)
                or (self.last is not None and (not 0<t-self.last[1]<=.2
                    or hypot(point[0]-self.last[0][0],point[1]-self.last[0][1])>.25))):self.interrupt()
        self.label=hand.label;self.last=(point,t)
        self.left.update(hand.ratio,t);self.right.update(right,t)
        self.reference=None;self.filter.reset();self.reset_scroll()
        self.clutched=False;self.clutch_since=None;self.click_kind=None;self.click_origin=None

    def _stick(self,hand,aspect):
        p=hand.landmarks
        def distance(a,b):return hypot((p[a][0]-p[b][0])*aspect,p[a][1]-p[b][1])
        palm=distance(5,17)
        if palm<0.025:return False
        close=distance(8,12)/palm< (0.55 if self.clutched else 0.42)
        # Both pointing fingers should extend away from the wrist.
        extended=distance(8,0)>distance(6,0)*1.10 and distance(12,0)>distance(10,0)*1.10
        return close and extended

    def _motion(self,anchor,t,move_enabled,precision=False):
        if not move_enabled:
            self.reference=None;self.filter.reset();return
        filtered=self.filter.update(anchor,t)
        if self.reference is None:self.reference=filtered;return
        dx,dy=filtered[0]-self.reference[0],filtered[1]-self.reference[1]
        distance=hypot(dx,dy); deadzone=self.config.touchpad_deadzone*(.6 if precision else 1)
        if distance<=deadzone:return
        # Remove the dead-zone slack instead of jumping by the full displacement.
        scale=(distance-deadzone)/distance
        step=(dx*scale,dy*scale)
        # Small movements have a lower gain; larger sweeps retain normal reach.
        gain=.45 if precision else max(.65,min(1.4,.65+distance*18))
        self.sink.move_relative(step[0]*self.config.touchpad_sensitivity*gain,
                                step[1]*self.config.touchpad_sensitivity*gain)
        self.reference=(self.reference[0]+step[0],self.reference[1]+step[1])

    def process(self,hand,t,age=0,aspect=4/3,precision=False):
        if not self.enabled:return "Mouse control off."
        if hand is None or age>0.2:
            self.interrupt(); return "Tracking lost — buttons released. Open both pinches to re-arm."
        points=hand.landmarks
        if not visible_control(hand):
            self.interrupt();return "Control fingertips/knuckles left the camera view — buttons released. Move them back into view."
        point=self._anchor(hand)
        if self.label is not None and hand.label!=self.label:
            self.interrupt(); return "Hand changed — buttons released."
        if self.last is not None and (t-self.last[1]>0.2 or hypot(point[0]-self.last[0][0],point[1]-self.last[0][1])>0.25):
            self.interrupt(); return "Pointer jump — buttons released. Open pinches to resume."
        self.label=hand.label; self.last=(point,t)
        left_ratio=hand.ratio; right_ratio=middle_pinch_ratio(hand,aspect) if self.right_enabled else 1.0
        if left_ratio is None or right_ratio is None or not isfinite(left_ratio) or not isfinite(right_ratio):
            self.interrupt(); return "Pinch landmarks unavailable — buttons released."
        extended=fingers(hand,aspect)
        if (left_ratio<self.config.pinch_down_ratio and right_ratio<self.config.pinch_down_ratio
                and self.button_held in (None,"left")):
            def radial(tip,pip):
                d=lambda i:hypot((points[i][0]-points[0][0])*aspect,points[i][1]-points[0][1])
                return d(tip)/max(d(pip),.025)
            # When joined fingertips both approach the thumb, an explicitly
            # folded index with a straight middle still means LEFT click.
            # Equal/unclear finger shapes retain the ambiguous-pinch guard.
            if radial(8,6)<1.05 and radial(12,10)>1.18:
                right_ratio=self.config.pinch_up_ratio+.01
        # Thumb touching both fingers is ambiguous. Never switch a left drag
        # into a right click; release and require deliberate open gestures.
        resolved=resolve_pinches(left_ratio,right_ratio,self.config,self.button_held)
        if resolved is None:
            self.interrupt(); return "Both pinches detected — open index and middle fingers to re-arm."
        left_ratio,right_ratio=resolved
        if (self.button_held is None and right_ratio<self.config.pinch_down_ratio
                and (left_ratio-right_ratio<.15 or right_ratio>left_ratio*.7)):
            # A thumb merely passing near middle while aiming for index must
            # not become a context-menu click on the threshold boundary.
            right_ratio=self.config.pinch_up_ratio+.01
        # Test the supporting fingers only AFTER choosing the pinch target.
        # A valid left pinch can also lie near middle; the irrelevant middle
        # distance must not reject it for having the index (correctly) curled.
        # An OK-shaped index pinch can have the other fingers comfortably
        # curled. Its contact remains beyond the knuckles; a resting fist's
        # fingertips fold back into the palm instead.
        axis=((points[9][0]-points[0][0])*aspect,points[9][1]-points[0][1])
        axis_length=hypot(*axis)
        palm=hypot((points[5][0]-points[17][0])*aspect,points[5][1]-points[17][1])
        ahead=sum(a*b for a,b in zip(((points[8][0]-points[5][0])*aspect,points[8][1]-points[5][1]),axis))/max(axis_length,.025)
        index_contact=ahead>palm*.12
        if (left_ratio<self.config.pinch_down_ratio and not (any(extended[1:]) or index_contact)) or (right_ratio<self.config.pinch_down_ratio and not (extended[0] or any(extended[2:]))):
            self.interrupt();return "Closed/resting hand — no click. Keep another finger extended when pinching."
        if self.button_held is None:
            kind="left" if left_ratio<self.config.pinch_down_ratio else ("right" if right_ratio<self.config.pinch_down_ratio else None)
            if kind!=self.click_kind:
                self.click_kind=kind;self.click_origin=point if kind else None
            elif kind is not None:
                palm=hypot((points[5][0]-points[17][0])*aspect,points[5][1]-points[17][1])
                drift=hypot((point[0]-self.click_origin[0])*aspect,point[1]-self.click_origin[1])
                if drift>palm*(.65 if kind=="left" else .25):
                    self.interrupt();return "Pinch moved too quickly — open the pinch and click with the hand briefly still."
        left_down=self.left.update(left_ratio,t)
        right_down=self.right.update(right_ratio,t)
        if right_down and not self.left.released:
            self.right.reset();right_down=False
        if not self.left.released and not self.right.released:return "Open index/thumb and middle/thumb pinches to arm mouse."
        if left_down and right_down:
            self.interrupt(); return "Ambiguous gesture — buttons released."
        wanted="left" if left_down else ("right" if right_down else None)
        if self.button_held is not None and wanted is not None and wanted!=self.button_held:
            self.interrupt();return "Pinch changed — open both pinches before selecting another button."
        if self.button_held is not None and wanted!=self.button_held:
            if self.button_held=="left":self.release_until=t+.12
            self.sink.button(self.button_held,False); self.button_held=None;self.dragging=False;self.press_anchor=None
        if wanted is not None and self.button_held is None:
            self.sink.button(wanted,True); self.button_held=wanted;self.pressed_at=t
            self.press_anchor=point;self.dragging=False
            self.reference=None;self.filter.reset()
        scrolling=scroll_pose(hand,aspect) and self.button_held is None and left_ratio>=self.config.pinch_up_ratio and right_ratio>=self.config.pinch_up_ratio
        if scrolling:
            self._motion(point,t,False);self.clutched=False;self.clutch_since=None
            self._scroll(point,t);return f"Scrolling {self.scroll_axis or '— move vertically or sideways'} · lower ring finger to point."
        self.reset_scroll()
        stick=self._stick(hand,aspect)
        if stick:
            if self.clutch_since is None:self.clutch_since=t
            self.clutched=t-self.clutch_since>=0.08
        else:self.clutched=False;self.clutch_since=None
        pinching=left_ratio<self.config.pinch_up_ratio or right_ratio<self.config.pinch_up_ratio
        if self.button_held=="left":
            # Short settling interval ignores closure posture. Then palm motion
            # drives a held drag even while the two fingertips are apart.
            if not self.dragging and self.pressed_at is not None and t-self.pressed_at>=.22 and hypot(point[0]-self.press_anchor[0],point[1]-self.press_anchor[1])>=self.config.touchpad_drag_threshold:
                self.dragging=True
            move_enabled=self.dragging
        else:move_enabled=self.clutched and not pinching and self.button_held is None and t>=self.release_until
        self._motion(point,t,move_enabled,precision=precision or self.dragging)
        if wanted:return "Selecting/dragging — release index pinch to drop." if self.dragging else f"{wanted.upper()} held — release to click; deliberate movement selects/drags."
        return "Touchpad moving — separate index/middle to reposition." if self.clutched else "Paused — join and extend index + middle to move."
