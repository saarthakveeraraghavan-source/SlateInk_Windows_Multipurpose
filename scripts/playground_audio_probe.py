"""Render original sound examples; optional silent native-output check. No mic."""
from pathlib import Path
import argparse,json,sys,wave,time
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from slateink.config import ROOT
from slateink.fun_audio import PlaygroundSynth,PlaygroundAudio
from slateink.fun_physics import PlaygroundModel


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check-device',action='store_true',help='Open output at zero volume to verify the Qt PCM path')
    args=parser.parse_args();out=ROOT/'artifacts/playground-audio';out.mkdir(parents=True,exist_ok=True)
    report={'microphone_opened':False,'examples':[],'native_output_checked':False}
    for scene,event in (("portal","seal"),("web","ripple"),("nebula","burst")):
        synth=PlaygroundSynth(scene);blocks=[];fired=False
        for i in range(282):
            t=i*1024/48000
            if t>=2 and not fired:synth.trigger(event);fired=True
            blocks.append(synth.render(1024,motion=.5+.4*np.sin(t*2),spread=.9+.5*np.sin(t),pan=.2*np.sin(t*.8),active=t>.25))
        audio=np.concatenate(blocks);path=out/(scene+'.wav')
        with wave.open(str(path),'wb') as wav:
            wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(48000);wav.writeframes((audio*32767).astype('<i2').tobytes())
        report['examples'].append({'scene':scene,'peak':round(float(np.max(np.abs(audio))),4),
                                   'rms':round(float(np.sqrt(np.mean(audio*audio))),4),'path':str(path)})
    if args.check_device:
        from PySide6.QtCore import QCoreApplication,QTimer
        app=QCoreApplication([]);audio=PlaygroundAudio();audio.volume=0
        state={'scene':0,'since':time.monotonic(),'processed_us':[]}
        scenes=('portal','web','nebula');model=PlaygroundModel(scenes[0]);audio.configure(scenes[0],True)
        def step():
            audio.update(model)
            if time.monotonic()-state['since']<.5:return
            state['processed_us'].append(audio.sink.processedUSecs() if audio.sink else 0)
            audio.stop();state['scene']+=1;state['since']=time.monotonic()
            if state['scene']==3:
                report['native_output_checked']=True;report['processed_us']=state['processed_us']
                report['native_success']=all(n>0 for n in state['processed_us']);app.quit();return
            model.set_scene(scenes[state['scene']]);audio.configure(scenes[state['scene']],True)
        timer=QTimer();timer.timeout.connect(step);timer.start(16)
        try:app.exec()
        finally:audio.stop()
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
    return 0 if not args.check_device or report.get('native_success') else 1


if __name__=='__main__':raise SystemExit(main())
