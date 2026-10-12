"""Volatile personal gaze calibration, optional accuracy gate and pinch control.

Iris landmarks are not gaze coordinates. Screen mapping is fitted from deliberate
look-target samples. Desktop input requires validation or an explicit override.
"""
from collections import deque
from collections import Counter
import numpy as np
from .gestures import Pinch
from .mouse_control import middle_pinch_ratio,resolve_pinches
from .smoothing import OneEuro


def gaze_filter():
    return OneEuro(min_cutoff=1.1,beta=.3)


class GazeCalibration:
    def __init__(self):
        self.groups=[];self.weights=None;self.validated=False;self.report=None
        self.mean=self.std=self.head_mean=self.lower=self.upper=None
    def add(self,observations,target):
        self.validated=False
        valid=[o for o in observations if o is not None and o.valid]
        if len(valid)<12:raise ValueError("Keep looking at the dot with eyes open for at least one second, then press Space.")
        features=np.asarray([o.features for o in valid],float)
        if features.shape!=(len(valid),4) or not np.isfinite(features).all():raise ValueError("Invalid eye sample; calibration stays off.")
        if np.max(np.std(features,axis=0))>0.05:raise ValueError("Eye sample is unstable. Keep your head still and look steadily at the dot.")
        self.groups.append((np.median(features,axis=0),tuple(target),np.median([o.head for o in valid],axis=0)))
    def fit(self):
        self.validated=False;self.weights=None
        if len(self.groups)<9:raise ValueError("Complete all calibration targets first.")
        x=np.asarray([g[0] for g in self.groups]);y=np.asarray([g[1] for g in self.groups])
        self.mean=x.mean(axis=0);self.std=x.std(axis=0)
        if max(self.std[[0,2]])<0.008 or max(self.std[[1,3]])<0.003:
            raise ValueError("Not enough eye movement was measured. Webcam gaze control remains off.")
        self.std=np.maximum(self.std,0.005)
        design=np.column_stack([np.ones(len(x)),(x-self.mean)/self.std])
        penalty=np.eye(design.shape[1])*0.08;penalty[0,0]=0
        self.weights=np.linalg.solve(design.T@design+penalty,design.T@y)
        self.lower=x.min(axis=0)-0.05;self.upper=x.max(axis=0)+0.05
        self.head_mean=np.mean([g[2] for g in self.groups],axis=0)
        if len(self.head_mean)>3:
            rolls=np.asarray([g[2][3] for g in self.groups])
            self.head_mean[3]=np.arctan2(np.sin(rolls).mean(),np.cos(rolls).mean())
        self.validated=False
    def predict(self,observation):
        return self.predict_with_reason(observation)[0]

    def predict_with_reason(self,observation,allow_extrapolation=False):
        if self.weights is None:return None,"Screen mapping is not ready."
        if observation is None or not observation.valid:return None,"Both eyes were not clearly visible."
        features=np.asarray(observation.features,float);head=np.asarray(observation.head,float)
        if features.shape!=(4,) or head.shape!=self.head_mean.shape or not np.isfinite(head).all() or self.head_mean[2]<=0:return None,"Eye measurements were unusable."
        if not np.isfinite(features).all():return None,"Eye measurements were unusable."
        if not allow_extrapolation and (np.any(features<self.lower) or np.any(features>self.upper)):return None,"Eyes moved outside the measured range; recalibration may be needed."
        if not allow_extrapolation and np.linalg.norm(head[:2]-self.head_mean[:2])>0.045:return None,"Head position changed; return to the calibration position."
        if not allow_extrapolation and abs(head[2]/self.head_mean[2]-1)>0.18:return None,"Distance from the camera changed; return to the calibration position."
        if len(head)>3 and not allow_extrapolation:
            roll=abs((head[3]-self.head_mean[3]+np.pi)%(2*np.pi)-np.pi)
            if roll>.17 or abs(head[4]-self.head_mean[4])>.12 or abs(head[5]-self.head_mean[5])>.15:return None,"Head angle changed; face the camera as during calibration."
        prediction=np.r_[1,(features-self.mean)/self.std]@self.weights
        if not np.isfinite(prediction).all() or (not allow_extrapolation and (np.any(prediction<-.05) or np.any(prediction>1.05))):return None,"Screen mapping went outside the display; recalibration may be needed."
        return tuple(np.clip(prediction,0,1)),None
    def validate(self,groups,width_px,height_px):
        self.validated=False;self.report=None
        errors=[];details=[]
        if len(groups)<5:raise ValueError("Complete the separate accuracy-check targets.")
        for index,(observations,target) in enumerate(groups):
            timed=bool(observations) and isinstance(observations[0],(tuple,list)) and len(observations[0])==2
            predictions=[];reasons=[];smoother=gaze_filter();first=None;last=None;usable=0
            for item in observations:
                t,o=item if timed else (None,item)
                if timed and (not np.isfinite(t) or (last is not None and t<=last)):
                    reasons.append("Camera samples repeated or arrived out of order.");continue
                prediction,reason=self.predict_with_reason(o)
                if prediction is None:
                    reasons.append(reason);continue
                usable+=1
                if timed:
                    if last is not None and t-last>.2:smoother.reset();first=None
                    if first is None:first=t
                    last=t;prediction=smoother.update(prediction,t)
                    if t-first<.25:continue
                predictions.append(prediction)
            detail={"index":index,"usable_samples":usable,"total_samples":len(observations),"error_px":None,"jitter_px":None,"passed":False}
            if usable<12 or len(predictions)<6 or usable/max(1,len(observations))<.75:
                detail["reason"]=(Counter(reasons).most_common(1)[0][0] if reasons else "Not enough fresh eye samples; look at this dot a little longer.")
            else:
                jitter=float(np.max(np.std(predictions,axis=0)*[width_px,height_px]))
                error=float(np.linalg.norm((np.median(predictions,axis=0)-target)*[width_px,height_px]))
                detail.update(error_px=error,jitter_px=jitter,passed=jitter<=30 and error<=60)
                detail["reason"]="Pointer was too jittery; keep your head still and retry this dot." if jitter>30 else ("Pointer missed this dot; retry while looking at its center." if error>60 else "Check completed.")
                errors.append(error)
            details.append(detail)
        median=float(np.median(errors)) if errors else None;p90=float(np.percentile(errors,90)) if errors else None
        self.validated=len(errors)==len(groups) and all(d["passed"] for d in details) and median<=35 and p90<=60
        retry=[d["index"] for d in details if not d["passed"]]
        if not self.validated and not retry:retry=[d["index"] for d in details if d["error_px"]>35]
        self.report={"validation_targets":len(groups),"median_error_px":median,"p90_error_px":p90,"passed":self.validated,
                     "checks":details,"retry_indices":retry,"reason":"Accuracy check passed." if self.validated else "Some accuracy checks need another try. Desktop control remains off."}
        return self.report
    def clear(self):self.__init__()


class GazeController:
    def __init__(self,config,sink,calibration):
        self.sink=sink;self.calibration=calibration;self.config=config;self.enabled=False;self.unverified=False
        self.left=Pinch(config.pinch_down_ratio,config.pinch_up_ratio,config.pinch_debounce_ms)
        self.right=Pinch(config.pinch_down_ratio,config.pinch_up_ratio,config.pinch_debounce_ms)
        self.filter=gaze_filter();self.history=deque(maxlen=12)
        self.held=None;self.right_enabled=True;self.gaze=None;self.last_label=None
        self.screen_rect=(0,0,1,1) # normalized subset of the Windows virtual desktop
    def interrupt(self):
        try:self.sink.release_all()
        finally:
            self.held=None;self.left.reset();self.right.reset();self.filter.reset()
            self.history.clear();self.gaze=None;self.last_label=None
    def set_enabled(self,value,allow_unverified=False):
        self.enabled=False;self.unverified=False;self.interrupt()
        fitted=self.calibration.weights is not None
        self.enabled=bool(value and fitted and (self.calibration.validated or allow_unverified))
        self.unverified=bool(self.enabled and not self.calibration.validated)
    def process(self,observation,hand,t,age=0,aspect=4/3):
        if self.calibration.weights is None:
            self.interrupt()
            return "Both eyes visible — click Calibrate eyes & check accuracy." if observation is not None and observation.valid and age<=.2 else "Show both eyes clearly to the webcam, then calibrate. Desktop control is off."
        gaze=self.calibration.predict_with_reason(observation,allow_extrapolation=self.unverified)[0]
        if gaze is None or age>.2:
            self.interrupt();return "Gaze unclear/head moved — clicks blocked and buttons released."
        self.gaze=self.filter.update(gaze,t);self.history.append((t,self.gaze))
        if not self.enabled:return "Gaze preview only — desktop control off."
        if hand is None:
            if self.held is not None:self.interrupt()
            else:self.left.reset();self.right.reset();self.last_label=None
            # Valid eyes can move the pointer; clicks always require one fresh hand.
            if self.gaze is not None:self._move(self.gaze)
            return "Gaze pointer active; show one hand and open pinches before clicking."
        if self.last_label is not None and hand.label!=self.last_label:
            self.interrupt();return "Hand changed — open both pinches again."
        self.last_label=hand.label
        left=hand.ratio;right=middle_pinch_ratio(hand,aspect) if self.right_enabled else 1.0
        if left is None or right is None or not np.isfinite([left,right]).all():
            self.interrupt();return "Pinch unavailable — clicks blocked."
        resolved=resolve_pinches(left,right,self.config,self.held)
        if resolved is None:
            self.interrupt();return "Ambiguous pinch — clicks blocked."
        left,right=resolved
        l=self.left.update(left,t);r=self.right.update(right,t)
        if not (self.left.released and self.right.released):return "Open both pinches to arm gaze clicking."
        wanted="left" if l else ("right" if r else None)
        if self.held is not None and wanted is not None and wanted!=self.held:
            self.interrupt();return "Pinch changed — open both pinches before another click."
        if self.held is not None and wanted!=self.held:
            self.sink.button(self.held,False);self.held=None
        if wanted is not None and self.held is None:
            recent=[p for timestamp,p in self.history if t-timestamp<=.35]
            fresh=len(recent)>=6 and self.history[-1][0]-self.history[0][0]>=.2
            stable=fresh and (self.unverified or np.max(np.std(recent,axis=0))<.008)
            if not stable:
                self.left.reset();self.right.reset();return "Look steadily at the target, then open and pinch again."
            self._move(tuple(np.median(recent,axis=0)))
            self.sink.button(wanted,True);self.held=wanted
        # Freeze the cursor while pinched. Gaze jitter cannot drag a window.
        if self.held is None and left>=self.config.pinch_up_ratio and right>=self.config.pinch_up_ratio:self._move(self.gaze)
        return "Gaze click held — release pinch to finish." if self.held else "Look to point; index pinch left-clicks, middle pinch right-clicks."
    def _move(self,point):
        x,y,w,h=self.screen_rect;self.sink.move(x+point[0]*w,y+point[1]*h)
