"""Single-letter CNN inference using a pinned local ONNX model, no remote code."""
import hashlib
import json
import time
import cv2
import numpy as np
from .config import ROOT
from .recognition import Recognition

LABELS="ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def prepare_character(image):
    array=np.array(image.convert("L"))
    ys,xs=np.where(array<180)
    # A narrow vertical or horizontal stroke may be I/l; do not require width
    # and height to both exceed a text-line threshold.
    if len(xs)<15 or max(np.ptp(xs),np.ptp(ys))<6:
        raise ValueError("Not enough ink for a letter.")
    crop=array[ys.min():ys.max()+1,xs.min():xs.max()+1]
    side=max(crop.shape)
    margin=max(4,round(side*0.18))
    square=np.full((side+2*margin,side+2*margin),255,np.uint8)
    y=(square.shape[0]-crop.shape[0])//2
    x=(square.shape[1]-crop.shape[1])//2
    square[y:y+crop.shape[0],x:x+crop.shape[1]]=crop
    small=cv2.resize(square,(96,96),interpolation=cv2.INTER_AREA)
    # Training source uses EMNIST's white ink on black; the model card's
    # inference polarity is inconsistent with its dataset implementation.
    # Our local synthetic glyph probe measures both before choosing this.
    return np.ascontiguousarray((((255-small.astype(np.float32))/255-0.5)/0.5)[None,None])


class CharacterRecognizer:
    def __init__(self):
        directory=ROOT/"models"/"alphabet"
        model=directory/"alphabet_model.onnx"
        manifest=json.loads((directory/"manifest.json").read_text(encoding="utf-8"))
        if manifest.get("revision")!="cf2bb20a6606fa405afb8f0b3df986c22169760f":
            raise ValueError("Unexpected alphabet model revision.")
        if hashlib.sha256(model.read_bytes()).hexdigest()!=manifest["sha256"]:
            raise ValueError("Alphabet model integrity check failed.")
        self.net=cv2.dnn.readNetFromONNX(str(model))
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

    def recognize(self,image):
        start=time.perf_counter()
        self.net.setInput(prepare_character(image))
        logits=self.net.forward().reshape(-1)
        if len(logits)!=27 or not np.isfinite(logits).all():
            raise ValueError("Invalid alphabet model output.")
        probabilities=np.exp(logits-logits.max())
        probabilities/=probabilities.sum()
        best=int(probabilities.argmax())
        if best==26:
            raise ValueError("The model detected a blank instead of a letter.")
        alternatives=tuple((LABELS[int(i)],float(probabilities[int(i)]))
                           for i in np.argsort(probabilities[:26])[::-1][:3])
        return Recognition(LABELS[best],float(probabilities[best]),time.perf_counter()-start,
                           alternatives=alternatives)
