"""Original procedural playground soundscapes and bounded Qt audio output.

No recordings, downloads, microphone, global volume changes or external assets.
The output device is opened only for an explicitly enabled, active scene.
"""
import math
import time
import numpy as np


class PlaygroundSynth:
    def __init__(self,scene,rate=48000,seed=31):
        if scene not in ("portal","web","nebula"):raise ValueError("Unknown sound scene")
        self.scene=scene;self.rate=rate;self.rng=np.random.default_rng(seed)
        self.position=0;self.phase=0.;self.level=0.;self.voices=[]
        self.loop=self.make_loop()

    def make_loop(self):
        n=self.rate*4;t=np.arange(n)/self.rate
        freq=np.fft.rfftfreq(n,1/self.rate)
        weight=np.maximum(freq,30)**(-.6)
        weight*=1-np.exp(-(freq/70)**2);weight*=np.exp(-(freq/6500)**2);weight[0]=0
        channels=[]
        for _ in range(2):
            noise=np.fft.irfft(np.fft.rfft(self.rng.normal(size=n))*weight,n=n)
            noise/=max(float(np.std(noise)),1e-6)
            channels.append(noise)
        stereo=np.column_stack(channels)
        if self.scene=="portal":
            stereo*=.12*(.75+.25*np.sin(t*math.tau*.5))[:,None]
            # Short, differently pitched grains make a stochastic ember bed.
            for _ in range(120):
                start=int(self.rng.integers(0,n-3000));length=int(self.rng.integers(160,2200))
                q=np.arange(length)/self.rate
                grain=self.rng.normal(size=length)*np.exp(-q*self.rng.uniform(70,210))
                grain*=np.minimum(1,q/.0008)*self.rng.uniform(.1,.33)
                pan=self.rng.uniform(.15,.85)
                stereo[start:start+length,0]+=grain*pan
                stereo[start:start+length,1]+=grain*(1-pan)
        elif self.scene=="web":
            stereo*=.012
            for i,f in enumerate((110,165,220.5,330.25)):
                stereo[:,0]+=np.sin(t*math.tau*f+i*.7)*.025/(i+1)
                stereo[:,1]+=np.sin(t*math.tau*(f+.25)+i*.7)*.025/(i+1)
        else:
            stereo*=.045
            for i,f in enumerate((55,82.5,110.25,165.5,247.5)):
                swell=.65+.35*np.sin(t*math.tau*.25+i)
                stereo[:,0]+=np.sin(t*math.tau*f)*swell*.035/(1+i*.3)
                stereo[:,1]+=np.sin(t*math.tau*(f+.25)+.4)*swell*.035/(1+i*.3)
        return stereo.astype(np.float32)

    def trigger(self,kind,strength=1):
        if kind not in ("seal","ripple","stretch","burst"):return
        self.voices.append({"kind":kind,"age":0.,"strength":max(0,min(1.5,strength)),"pan":float(self.rng.uniform(-.35,.35))})
        self.voices=self.voices[-8:]

    def voice(self,voice,frames):
        t=voice["age"]+np.arange(frames)/self.rate;kind=voice["kind"]
        if kind=="seal":
            duration=1.65;env=(1-np.exp(-t*35))*np.exp(-t*2.6)
            signal=.42*np.sin(math.tau*(105*t+85*t*t))*env
            signal+=.22*np.sin(math.tau*52*t)*np.exp(-t*8)*(1-np.exp(-t*80))
            signal+=self.rng.normal(size=frames)*.16*env*(.6+.4*np.sin(t*13))
            for f in (660,990,1320):signal+=.055*np.sin(math.tau*f*t)*np.exp(-t*3.7)*(1-np.exp(-t*80))
        elif kind in ("ripple","stretch"):
            duration=1.2 if kind=="ripple" else .65
            fundamental=280 if kind=="ripple" else 190+100*voice["strength"]
            env=(1-np.exp(-t*200))*np.exp(-t*(4 if kind=="ripple" else 7))
            signal=sum(np.sin(math.tau*fundamental*ratio*t)*amplitude*np.exp(-t*i)
                       for i,(ratio,amplitude) in enumerate(((1,.30),(2.01,.12),(3.98,.055))))*env
        else:
            duration=1.9;env=(1-np.exp(-t*55))*np.exp(-t*3)
            signal=self.rng.normal(size=frames)*.12*env
            for i,f in enumerate((880,660,440,330)):
                q=np.maximum(0,t-i*.07);gate=t>=i*.07
                signal+=gate*.15*np.sin(math.tau*(f*q-35*q*q))*(1-np.exp(-q*180))*np.exp(-q*3.8)
            signal+=.13*np.sin(math.tau*65*t)*env
        tail=np.clip((duration-t)/.08,0,1)
        signal*=tail*(t<duration)*voice["strength"]
        voice["age"]+=frames/self.rate
        return signal,duration

    def render(self,frames,motion=0,spread=.85,pan=0,active=False):
        frames=int(frames)
        if not 1<=frames<=8192:raise ValueError("Audio quantum outside bounds")
        motion=float(np.clip(np.nan_to_num(motion),0,2));spread=float(np.clip(np.nan_to_num(spread),.5,1.8))
        pan=float(np.clip(np.nan_to_num(pan),-.65,.65))
        index=(self.position+np.arange(frames))%len(self.loop);self.position=(self.position+frames)%len(self.loop)
        target=.28+motion*.20 if active else .08
        final=target+(self.level-target)*math.exp(-frames/self.rate/.09)
        ramp=np.linspace(self.level,final,frames);self.level=final
        result=self.loop[index]*ramp[:,None]
        # Continuous tension/power tone follows the model, with a phase that
        # remains continuous across output quanta and gesture updates.
        frequency={"portal":48+motion*9,"web":85+spread*85,"nebula":70+motion*14}[self.scene]
        phase=self.phase+np.arange(frames)*math.tau*frequency/self.rate
        self.phase=float((phase[-1]+math.tau*frequency/self.rate)%math.tau)
        tone=np.sin(phase)+.18*np.sin(phase*2)
        amount={"portal":.09,"web":.12,"nebula":.08}[self.scene]
        result+=tone[:,None]*ramp[:,None]*amount
        surviving=[]
        for voice in self.voices:
            signal,duration=self.voice(voice,frames)
            result[:,0]+=signal*math.sqrt((1-voice["pan"])*.5)
            result[:,1]+=signal*math.sqrt((1+voice["pan"])*.5)
            if voice["age"]<duration:surviving.append(voice)
        self.voices=surviving
        result[:,0]*=math.sqrt(1-pan*.6);result[:,1]*=math.sqrt(1+pan*.6)
        # Conservative level and a soft ceiling; the app never changes the
        # system mixer. Short startup ramps and event envelopes avoid clicks.
        return (np.tanh(result*.9)*.38).astype(np.float32)


class PlaygroundAudio:
    def __init__(self):
        self.scene="portal";self.enabled=False;self.sink=None;self.device=None;self.synth=None
        self.format=None;self.pending=b"";self.status="Sound off";self.retry_at=0
        self.volume=.55;self.last_time=None;self.last_brush=None;self.motion=0
        self.last_portal=None;self.last_pulse=0;self.last_spread=.85;self.last_chime=0

    def configure(self,scene,enabled):
        if self.scene==scene and self.enabled==bool(enabled):return
        self.stop();self.scene=scene;self.enabled=bool(enabled);self.retry_at=0
        self.status="Sound ready" if self.enabled else "Sound off"

    def stop(self):
        sink=self.sink;self.sink=None;self.device=None;self.synth=None;self.pending=b""
        self.last_time=None;self.last_brush=None;self.motion=0;self.last_portal=None;self.last_pulse=0
        if sink:
            try:sink.reset();sink.deleteLater()
            except RuntimeError:pass

    def open_output(self):
        # Qt's QIODevice output path works with the pinned PySide6 6.10 build.
        # https://doc.qt.io/qt-6/qaudiosink.html
        from PySide6.QtMultimedia import QAudioSink,QAudioFormat,QMediaDevices
        output=QMediaDevices.defaultAudioOutput()
        if output.isNull():self.status="No audio output device — visuals continue";return False
        fmt=QAudioFormat();fmt.setSampleRate(48000);fmt.setChannelCount(2);fmt.setSampleFormat(QAudioFormat.SampleFormat.Float)
        if not output.isFormatSupported(fmt):fmt=output.preferredFormat()
        if not 8000<=fmt.sampleRate()<=192000 or not 1<=fmt.channelCount()<=8 or fmt.sampleFormat().name=="Unknown":
            self.status="Unsupported audio output format — visuals continue";return False
        self.format=fmt;self.sink=QAudioSink(output,fmt)
        self.sink.setBufferSize(int(fmt.sampleRate()*.09)*fmt.bytesPerFrame());self.sink.setVolume(self.volume)
        self.device=self.sink.start()
        if self.device is None or self.sink.error().name not in ("NoError","UnderrunError"):
            self.status="Audio output unavailable — visuals continue";self.stop();return False
        self.synth=PlaygroundSynth(self.scene,fmt.sampleRate());self.status="Sound on · system default output"
        return True

    def encode(self,audio):
        channels=self.format.channelCount();kind=self.format.sampleFormat().name
        if channels==1:audio=audio.mean(axis=1,keepdims=True)
        elif channels>2:audio=np.pad(audio,((0,0),(0,channels-2)))
        if kind=="Float":return audio.astype('<f4').tobytes()
        if kind=="Int16":return (audio*32767).astype('<i2').tobytes()
        if kind=="Int32":return (audio*2147483647).astype('<i4').tobytes()
        if kind=="UInt8":return (audio*127+128).astype('u1').tobytes()
        raise ValueError("Unsupported output encoding")

    def update(self,model,active=True):
        if not self.enabled or not active:
            if self.sink:self.stop()
            return
        now=time.monotonic()
        if self.sink is None:
            if now<self.retry_at:return
            try:opened=self.open_output()
            except (ImportError,RuntimeError,ValueError):
                self.status="Audio backend unavailable — visuals continue";self.stop();opened=False
            if not opened:self.retry_at=now+3;return
            self.last_portal=max((p.born for p in model.portals),default=0)
            self.last_spread=model.dome_scale;self.last_pulse=model.pulse
        if self.sink.error().name not in ("NoError","UnderrunError"):
            self.status="Audio device changed — waiting to reconnect";self.stop();self.retry_at=now+2;return
        dt=.016 if self.last_time is None else max(.001,min(.2,now-self.last_time))
        self.last_time=now
        if model.brush is not None and self.last_brush is not None and model.brush!=self.last_brush:
            speed=min(2,math.dist(model.brush,self.last_brush)/dt)
            self.motion+=.2*(speed-self.motion)
        else:self.motion*=math.exp(-dt*3)
        self.last_brush=model.brush
        latest=max((p.born for p in model.portals),default=0)
        if latest>(self.last_portal or 0):self.synth.trigger("seal");self.last_portal=latest
        if model.pulse>.8 and self.last_pulse<=.8 and self.scene!="portal":
            self.synth.trigger("ripple" if self.scene=="web" else "burst")
        self.last_pulse=model.pulse
        if self.scene=="web" and abs(model.dome_scale-self.last_spread)>.14 and now-self.last_chime>.18:
            self.synth.trigger("stretch",model.dome_scale/1.8);self.last_chime=now;self.last_spread=model.dome_scale
        try:
            for _ in range(5):
                free=self.sink.bytesFree();frame_bytes=self.format.bytesPerFrame()
                if free<frame_bytes*64:break
                if not self.pending:
                    frames=min(1024,free//frame_bytes)
                    data=self.synth.render(frames,self.motion,model.dome_scale,
                                           (model.brush[0] if model.brush else 0),model.brush is not None)
                    self.pending=self.encode(data)
                size=min(len(self.pending),free)
                written=self.device.write(self.pending[:size])
                if written<0:raise RuntimeError("Audio write failed")
                self.pending=self.pending[written:]
                if written==0:break
        except (RuntimeError,ValueError):
            self.status="Audio paused — visuals continue";self.stop();self.retry_at=now+2
