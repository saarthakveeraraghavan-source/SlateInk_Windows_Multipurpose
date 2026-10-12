"""Local face/iris features for an explicitly calibrated gaze experiment."""
from dataclasses import dataclass
import hashlib,json,time
import numpy as np
import mediapipe as mp
from .config import ROOT
EYE_MODEL_SHA256="64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"


@dataclass(frozen=True)
class EyeObservation:
    features: tuple | None
    head: tuple
    iris_centers: tuple
    valid: bool
    reason: str = ""


def eye_features(points):
    p=np.asarray(points,dtype=float)
    if p.ndim!=2 or p.shape[0]<478 or p.shape[1]<2 or not np.isfinite(p[:,:2]).all():return None
    features=[]; centers=[]
    for a,b,top,bottom,iris in ((33,133,159,145,468),(362,263,386,374,473)):
        v=p[b,:2]-p[a,:2]; width=np.linalg.norm(v)
        if width<0.025:return EyeObservation(None,(),(),False,"Move closer: eyes are too small in the camera image.")
        u=v/width; normal=np.array([-u[1],u[0]])
        center=(p[a,:2]+p[b,:2])/2; pupil=p[iris,:2]
        x=float(np.dot(pupil-p[a,:2],u)/width)
        y=float(np.dot(pupil-center,normal)/width)
        openness=np.linalg.norm(p[top,:2]-p[bottom,:2])/width
        centers.append(tuple(pupil))
        if openness<0.12 or not (-0.1<=x<=1.1 and abs(y)<0.45):
            return EyeObservation(None,(),tuple(centers),False,"Eyes closed, occluded, or landmarks unclear.")
        features.extend((x,y))
    left=(p[33,:2]+p[133,:2])/2;right=(p[362,:2]+p[263,:2])/2
    center=(left+right)/2
    separation=np.linalg.norm(right-left);axis=(right-left)/separation
    nose=p[1,:2]-center;normal=np.array([-axis[1],axis[0]])
    head=(float(center[0]),float(center[1]),float(separation),float(np.arctan2(axis[1],axis[0])),
          float(np.dot(nose,axis)/separation),float(np.dot(nose,normal)/separation))
    return EyeObservation(tuple(features),head,tuple(centers),True)


class EyeTracker:
    def __init__(self):
        directory=ROOT/"models/eyes";path=directory/"face_landmarker.task"
        manifest=json.loads((directory/"manifest.json").read_text(encoding="utf-8"))
        if manifest.get("sha256")!=EYE_MODEL_SHA256 or hashlib.sha256(path.read_bytes()).hexdigest()!=EYE_MODEL_SHA256:raise ValueError("Eye model integrity failed.")
        options=mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,num_faces=2,
            min_face_detection_confidence=0.7,min_face_presence_confidence=0.7,
            min_tracking_confidence=0.7)
        self.detector=mp.tasks.vision.FaceLandmarker.create_from_options(options);self.last=-1
    def detect(self,rgb,t):
        timestamp=max(self.last+1,int(t*1000));self.last=timestamp;start=time.perf_counter()
        result=self.detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=np.ascontiguousarray(rgb)),timestamp)
        count=len(result.face_landmarks)
        observation=eye_features([(p.x,p.y,p.z) for p in result.face_landmarks[0]]) if count==1 else None
        return observation,count,(time.perf_counter()-start)*1000
    def close(self):self.detector.close()
