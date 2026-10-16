"""Two-hand roles, precision, pause and deliberate Wispr gesture coordination."""
from .hand_gestures import open_palm,voice_symbol,DwellPose,ConfirmedPose
from .touchpad_submodes import GamingController,DrawingController
from .air_swipe import WindowSwipe


class TouchpadSession:
    def __init__(self,controller,shortcuts,movement_keys=None,window_switcher=None):
        self.controller=controller;self.shortcuts=shortcuts
        self.config=controller.config;self.paused=False;self.chosen_label=None
        self.swipe=WindowSwipe();self.window_switcher=window_switcher
        self.last_submode=self.config.touchpad_submode
        self.chosen_since=None;self.hand_role_locked=False
        self.swipe_quiet_until=0
        self.pause_pose=DwellPose(hold=.9);self.voice_pose=ConfirmedPose();self.voice_stop=ConfirmedPose(hold=.06)
        self.voice_started=None;self.voice_hand=None;self.voice_candidate=None;self.primary=None;self.helper=None
        self.gaming=GamingController(self.config,movement_keys)
        self.drawing=DrawingController(self.config,controller.sink,movement_keys.target if movement_keys else None)

    @property
    def button_held(self):return "left" if self.config.touchpad_submode=="drawing" and (self.drawing.held or self.drawing.click_held) else self.controller.button_held

    def release_inputs(self):
        self.swipe.reset()
        try:
            if self.window_switcher:self.window_switcher.release_all()
        finally:
            try:self.gaming.interrupt()
            finally:
                try:self.drawing.interrupt()
                finally:self.controller.interrupt()

    @property
    def dictating(self):return self.voice_started is not None

    def interrupt(self):
        try:
            if self.shortcuts:self.shortcuts.cancel()
        finally:
            try:self.release_inputs()
            finally:
                self.voice_started=None;self.voice_hand=None;self.voice_candidate=None
                self.voice_pose.reset();self.voice_stop.reset();self.pause_pose.reset();self.primary=None;self.helper=None

    def tracking_stale(self):
        self.release_inputs();self.voice_pose.reset();self.voice_stop.reset();self.voice_candidate=None
        if self.dictating:return self.process_dictation((),None)
        self.primary=self.helper=None
        return "Tracking stale — input released. Open the pinch to resume."

    def process_dictation(self,hands,t,aspect=4/3):
        self.release_inputs()
        if not self.shortcuts.target_unchanged():
            self.interrupt();return "Dictation cancelled because the focused textbox/window changed."
        # Hand disappearance, other poses, duplicate labels and the other hand
        # never end a latched recording. Stop needs the initiating hand again.
        trusted=[h for h in hands if h.label==self.voice_hand and h.handedness_confidence>=.65]
        unambiguous=len(hands)<=2 and len({h.label for h in hands})==len(hands)
        self.primary,self.helper=self.choose_hands(hands,t) if unambiguous else (None,None)
        stop=unambiguous and len(trusted)==1 and voice_symbol(trusted[0],aspect)=="stop"
        if t is None:self.voice_stop.reset()
        elif self.voice_stop.update(stop,t):
            self.shortcuts.finish();self.voice_started=None;self.voice_hand=None
            self.voice_pose.reset();self.voice_stop.reset();self.voice_candidate=None;self.pause_pose.reset()
            return "Wispr stop shortcut sent — wait for Flow to insert text; open the pinch to resume pointing."
        physical_right="Left" if self.config.camera_mirrored else "Right"
        owner="RIGHT" if self.voice_hand==physical_right else "LEFT"
        return f"Wispr listening — relax or lower your hand. {owner} index + pinky + thumb (swag sign) stops and inserts text."

    def set_enabled(self,value):
        self.controller.enabled=False;self.interrupt();self.controller.set_enabled(value)
        self.paused=False;self.chosen_label=None
        self.chosen_since=None;self.hand_role_locked=False
        self.swipe_quiet_until=0

    def toggle_pause(self):
        self.interrupt();self.paused=not self.paused
        if self.config.touchpad_submode=="gaming":return "Gaming paused — Ctrl+Alt+M resumes." if self.paused else "Gaming resumed — hold your left palm still to center."
        return "Hand touchpad paused — show both open palms or press Ctrl+Alt+M to resume." if self.paused else "Hand touchpad resumed — open pinches, then join index + middle."

    def choose_hands(self,hands,t=None):
        if len(hands)>2 or len({h.label for h in hands})!=len(hands):return None,None
        if self.config.touchpad_submode=="gaming" or (self.config.touchpad_submode=="drawing" and self.config.drawing_two_hand):
            # This installed Tasks model labels the unmirrored public left-hand
            # fixture Left and its mirror Right. Do not apply the legacy Hands
            # selfie convention: the live frames have already been mirrored.
            right="Left" if self.config.camera_mirrored else "Right"
            return next((h for h in hands if h.label==right),None),next((h for h in hands if h.label!=right),None)
        wanted=self.config.touchpad_hand
        if wanted=="auto":
            if self.chosen_label is None and hands:
                self.chosen_label=hands[0].label;self.chosen_since=t
            if len(hands)==2:self.hand_role_locked=True
            # Establish first-shown identity over a short acquisition interval.
            # The new previous video begins with a one-frame wrong label;
            # permanently locking that first estimate loses the actual hand.
            if not self.hand_role_locked and len(hands)==1 and t is not None:
                if hands[0].label!=self.chosen_label:
                    self.chosen_label=hands[0].label;self.chosen_since=t
                elif self.chosen_since is not None and t-self.chosen_since>=.15:
                    self.hand_role_locked=True
            wanted=self.chosen_label
        primary=next((h for h in hands if h.label==wanted),None)
        helper=next((h for h in hands if h.label!=wanted),None)
        return primary,helper

    def process(self,hands,t,age=0,aspect=4/3):
        if not self.controller.enabled:return "Touchpad off."
        if self.last_submode!=self.config.touchpad_submode:
            self.interrupt();self.last_submode=self.config.touchpad_submode
        if self.dictating:
            return self.process_dictation(hands if age<=.2 else (),t,aspect)
        if age>.2:
            return self.tracking_stale()
        if self.config.touchpad_submode=="desktop" and self.config.touchpad_swipe_enabled:
            # The new next recording contains a low-confidence duplicate hand
            # during motion blur. It is not an established second hand role.
            hands=tuple(h for h in hands if h.handedness_confidence>=.6)
        if len(hands)>2 or len({h.label for h in hands})!=len(hands):
            self.interrupt();return "Hand roles unclear — input released. Separate your hands."
        self.primary,self.helper=self.choose_hands(hands,t)
        # Left joystick already uses a palm. A relaxed right mouse hand can
        # also have all four fingers extended; that must not pause gameplay.
        both_open=self.config.touchpad_submode!="gaming" and open_palm(self.primary,aspect) and open_palm(self.helper,aspect)
        if self.pause_pose.update(both_open,t):return self.toggle_pause()
        if both_open:
            self.voice_pose.reset();self.voice_candidate=None
            self.release_inputs();return "Hold both open palms steadily to pause/resume."
        if self.paused:return "PAUSED — press Ctrl+Alt+M to resume." if self.config.touchpad_submode=="gaming" else "PAUSED — hold both open palms for one second, or press Ctrl+Alt+M."
        if self.config.touchpad_submode=="gaming":
            self.gaming.config=self.config
            if self.primary is None:
                self.interrupt();return "Right mouse hand missing — all inputs released. Show both hands to play."
            target=self.gaming.sink.target() if self.gaming.sink else None
            if target is None or (self.gaming.target is not None and target!=self.gaming.target):
                self.interrupt();return "Focus changed — mouse and WASD released. Focus the game, then hold your left palm still to center."
            keys=self.gaming.process(self.helper,t,age,aspect)
            mouse=self.controller.process(self.primary,t,age,aspect)
            return keys+"  Right mouse: "+mouse
        if self.config.touchpad_submode=="drawing":
            self.drawing.config=self.config;self.drawing.sink=self.controller.sink
            return self.drawing.process(self.primary,t,age,aspect,click_hand=self.helper,split_click=self.config.drawing_two_hand)
        voice_hand=next((h for h in (self.helper,self.primary) if h is not None
                         and h.handedness_confidence>=.65 and voice_symbol(h,aspect)=="start"),None) if self.config.wispr_enabled else None
        pose=voice_hand is not None
        if pose and self.voice_candidate!=voice_hand.label:
            self.voice_pose.reset();self.voice_candidate=voice_hand.label
        if not pose:self.voice_candidate=None
        # Only the physical right hand supplies window swipes. Mirroring
        # changes the tracker's handedness label, not the physical hand role.
        right="Left" if self.config.camera_mirrored else "Right"
        swipe_control=next((h for h in hands if h.label==right),None)
        # A deliberate rock sign takes priority over a pending window swipe.
        if pose:
            self.swipe.reset()
        else:
            if self.config.touchpad_swipe_enabled and self.window_switcher:
                freeze,direction=self.swipe.update(swipe_control,t,self.config,aspect,
                    blocked=self.controller.button_held is not None or self.controller.dragging or t<self.controller.release_until,age=age)
                if freeze:
                    if self.swipe.moving or direction is not None:self.swipe_quiet_until=t+.2
                    self.voice_pose.reset();self.voice_candidate=None
                    if self.swipe.moving or direction is not None or t<self.swipe_quiet_until:self.controller.interrupt()
                    else:self.controller.observe_open(self.primary,t,aspect)
                    if direction is not None:return self.window_switcher.switch(direction)
                    return self.swipe.hint
            else:self.swipe.reset()
        requested=self.voice_pose.update(pose,t)
        if requested and not self.dictating and self.shortcuts:
            self.controller.interrupt()
            self.shortcuts.begin(self.config.wispr_shortcut_mode)
            self.voice_started=t;self.voice_hand=voice_hand.label;self.voice_stop.reset()
        if self.dictating:
            return self.process_dictation(hands,t,aspect)
        if pose:
            self.swipe.reset()
            self.controller.interrupt();return "Rock sign detected — starting Wispr. Relax, then add your thumb to the same-hand rock sign to finish."
        if self.config.touchpad_swipe_enabled and t<self.swipe_quiet_until:
            self.controller.interrupt()
            return "Swipe settling — relax your hand, then point or pinch normally."
        return self.controller.process(self.primary,t,age,aspect,precision=open_palm(self.helper,aspect))
