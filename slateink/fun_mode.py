"""Playground lifecycle; desktop input remains disabled for the entire session."""
from dataclasses import replace
from .fun_physics import SCENES


class FunModeMixin:
    def change_fun_scene(self,index):
        self.config=replace(self.config,fun_scene=SCENES[index])
        self.sync_fun_sound_choice()
        if self.fun_window:self.fun_window.choose_scene(self.config.fun_scene)
        self.save_touchpad_preferences()

    def remember_fun_scene(self,scene):
        self.config=replace(self.config,fun_scene=scene)
        self.fun_scene_choice.blockSignals(True)
        self.fun_scene_choice.setCurrentIndex(SCENES.index(scene));self.fun_scene_choice.blockSignals(False)
        self.sync_fun_sound_choice()
        self.save_touchpad_preferences()

    def sync_fun_sound_choice(self):
        self.fun_sound.blockSignals(True)
        self.fun_sound.setChecked(getattr(self.config,"fun_"+self.config.fun_scene+"_sound"))
        self.fun_sound.blockSignals(False)

    def change_fun_sound(self,enabled):self.remember_fun_sound(self.config.fun_scene,enabled)

    def remember_fun_sound(self,scene,enabled):
        self.config=replace(self.config,**{"fun_"+scene+"_sound":bool(enabled)})
        if scene==self.config.fun_scene:self.sync_fun_sound_choice()
        if self.fun_window:self.fun_window.set_scene_sound(scene,enabled)
        self.save_touchpad_preferences()

    def launch_fun(self):
        if self.mode!="hand_mouse" or self.config.touchpad_submode!="fun" or self.closing:return
        if self.fun_window:
            self.fun_window.showFullScreen();self.fun_window.raise_();self.fun_window.activateWindow();return
        self.arm_touchpad_when_ready=False;self.stop_pointer()
        if self.worker is None:self.start_camera()
        if self.worker is None or self.worker.stop_event.is_set():return
        from .fun_playground import FunWindow
        window=self.fun_window=FunWindow(self.config.fun_scene,
            {scene:getattr(self.config,"fun_"+scene+"_sound") for scene in SCENES})
        window.scene_changed.connect(self.remember_fun_scene)
        window.sound_changed.connect(self.remember_fun_sound)
        window.finished.connect(lambda:self.fun_finished(window))
        window.showFullScreen();window.raise_();window.activateWindow();window.setFocus()
        self.hint.setText("Fun playground open — right hand paints. Escape returns and stops the camera.")
        self.refresh_controls()

    def fun_finished(self,window):
        if self.fun_window is not window:return
        self.fun_window=None
        self.stop_camera()
        if not self.closing:self.showNormal();self.raise_();self.activateWindow()

    def stop_fun(self):
        window=self.fun_window;self.fun_window=None
        if window:window.close()

    def process_fun_packet(self,packet,now):
        if self.fun_window:
            hands=packet.hands or ((packet.hand,) if packet.hand is not None else ())
            self.fun_window.observe(hands,packet.t,self.config.camera_mirrored,
                                    now-packet.t,packet.rgb.shape[1]/packet.rgb.shape[0],self.camera_view.image)
            self.hint.setText(self.fun_window.model.input_state)
