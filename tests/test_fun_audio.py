import os
os.environ["QT_QPA_PLATFORM"]="offscreen"
from types import SimpleNamespace
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from slateink.config import Config
from slateink.fun_audio import PlaygroundSynth,PlaygroundAudio
from slateink.fun_physics import PlaygroundModel,Portal
from slateink.fun_playground import FunWindow
from test_modes import window


@pytest.mark.parametrize("scene,event",[("portal","seal"),("web","ripple"),("nebula","burst")])
def test_sounds_have_stereo_energy_and_bounded_click_free_output(scene,event):
    synth=PlaygroundSynth(scene,rate=12000)
    blocks=[]
    for i in range(60):
        if i==10:synth.trigger(event)
        blocks.append(synth.render(1024,motion=.8,spread=1.3,pan=.3,active=True))
    data=np.concatenate(blocks)
    assert data.dtype==np.float32 and data.shape==(61440,2)
    assert np.isfinite(data).all() and np.max(np.abs(data))<.38
    assert .001<float(np.sqrt(np.mean(data*data)))<.15
    assert abs(float(data.mean()))<.015 and not np.array_equal(data[:,0],data[:,1])
    assert np.max(np.abs(data[:12]))<.01 and not synth.voices


def test_synthesis_events_are_distinct_and_simultaneous_voices_are_capped():
    fingerprints=[]
    for event in ("seal","ripple","stretch","burst"):
        synth=PlaygroundSynth("web",rate=12000);synth.trigger(event)
        fingerprints.append(synth.render(4096).tobytes())
        for _ in range(30):synth.trigger(event)
        assert len(synth.voices)==8
    assert len(set(fingerprints))==4


def test_muted_or_inactive_audio_never_opens_output():
    audio=PlaygroundAudio();model=PlaygroundModel()
    def forbidden():raise AssertionError("Muted scene tried to open audio")
    audio.open_output=forbidden
    audio.update(model);audio.configure("web",True);audio.update(model,active=False)
    assert audio.sink is None


class Output:
    def __init__(self):self.data=bytearray();self.cleared=False
    def error(self):return SimpleNamespace(name="NoError")
    def bytesFree(self):return 8192
    def write(self,data):
        # Exercise the partial-byte write path, including odd remainders.
        count=max(1,len(data)//2) if data else 0;self.data.extend(data[:count]);return count
    def reset(self):self.cleared=True
    def deleteLater(self):pass


def test_audio_streaming_preserves_partial_writes_and_mutes_immediately():
    audio=PlaygroundAudio();audio.configure("portal",True);output=Output();model=PlaygroundModel()
    def open_output():
        audio.sink=output;audio.device=output;audio.synth=PlaygroundSynth("portal",rate=12000)
        audio.format=SimpleNamespace(bytesPerFrame=lambda:8,channelCount=lambda:2,sampleFormat=lambda:SimpleNamespace(name="Float"))
        return True
    audio.open_output=open_output
    audio.update(model);model.portals.append(Portal(0,0,.2,2));audio.update(model)
    assert output.data and any(v["kind"]=="seal" for v in audio.synth.voices)
    audio.configure("portal",False)
    assert output.cleared and audio.sink is None and audio.pending==b""
    count=len(output.data);audio.update(model);assert len(output.data)==count


def test_unavailable_audio_is_throttled_and_does_not_change_the_visual_model():
    audio=PlaygroundAudio();audio.configure("nebula",True);model=PlaygroundModel("nebula");calls=[]
    audio.open_output=lambda:calls.append(True) or False
    for _ in range(20):audio.update(model)
    assert calls==[True] and model.scene=="nebula" and len(model.stars)==580


def test_sound_choices_are_independent_saved_and_available_before_entry(window,tmp_path,monkeypatch):
    import slateink.config as config
    monkeypatch.setattr(config,"ROOT",tmp_path);window.persist_preferences=True
    window.mode_choice.setCurrentIndex(1);window.submode_choice.setCurrentIndex(3)
    assert not window.fun_sound.isChecked() and window.fun_window is None
    window.fun_sound.setChecked(True)
    window.fun_scene_choice.setCurrentIndex(1);assert not window.fun_sound.isChecked()
    window.fun_sound.setChecked(True)
    window.fun_scene_choice.setCurrentIndex(2);assert not window.fun_sound.isChecked()
    window.fun_scene_choice.setCurrentIndex(0);assert window.fun_sound.isChecked()
    saved=config.load_config()
    assert saved.fun_portal_sound and saved.fun_web_sound and not saved.fun_nebula_sound


def test_inside_scene_mute_tracks_each_scene_without_starting_audio_before_entry():
    app=QApplication.instance() or QApplication([])
    window=FunWindow("portal",{"portal":True,"web":False,"nebula":True});window.timer.stop()
    changes=[];window.sound_changed.connect(lambda scene,value:changes.append((scene,value)))
    assert window.audio.sink is None and window.sound_button.isChecked()
    window.choose_scene("web");assert not window.sound_button.isChecked() and not window.audio.enabled
    window.choose_scene("nebula");assert window.sound_button.isChecked() and window.audio.enabled
    window.sound_button.click();assert changes==[("nebula",False)] and not window.audio.enabled
    window.close();app.processEvents()


def test_sound_config_accepts_only_boolean_choices():
    assert not Config().fun_portal_sound
    with pytest.raises(ValueError):Config(fun_web_sound=1)
