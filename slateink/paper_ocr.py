"""Offline recognition of actual visible paper/slate text, memory-only."""
import hashlib
import json
import math
import os
import sys
from pathlib import Path
import time
import cv2
import numpy as np
import yaml
from PySide6.QtCore import QThread,Signal
from .config import ROOT
from .recognition import Recognition

REVISIONS={"english":"3fafbc3b5dcf93dd72add9f48368be8a3a2cd33b",
           "medium":"50c7eacafc52fa7bcf4194e8cd08e46f8558504b"}
_DLL_HANDLES=[]


def prepare_cuda_libraries(ort):
    if sys.platform=="win32" and not _DLL_HANDLES:
        # cuDNN itself dynamically loads engine DLLs. Preloading only cudnn64
        # does not make those siblings discoverable on Windows. Scope both
        # search mechanisms to this process and this project's installed wheels.
        bins=sorted((Path(ort.__file__).parent.parent/"nvidia").glob("*/bin"))
        for directory in bins:_DLL_HANDLES.append(os.add_dll_directory(str(directory)))
        os.environ["PATH"]=os.pathsep.join(str(p) for p in bins)+os.pathsep+os.environ.get("PATH","")
    ort.preload_dlls(directory="")


def warp_paper(rgb,surface,mirrored=False):
    h,w=rgb.shape[:2]
    corners=surface.corners*np.array([w-1,h-1],np.float32)
    width=(np.linalg.norm(corners[1]-corners[0])+np.linalg.norm(corners[2]-corners[3]))/2
    height=(np.linalg.norm(corners[3]-corners[0])+np.linalg.norm(corners[2]-corners[1]))/2
    if width<40 or height<20:raise ValueError("Writing region is too small. Move the webcam closer or select a larger region.")
    scale=min(2.0,1600/max(width,height))
    tw,th=max(40,round(width*scale)),max(20,round(height*scale))
    destination=np.array([[0,0],[tw-1,0],[tw-1,th-1],[0,th-1]],np.float32)
    matrix=cv2.getPerspectiveTransform(corners.astype(np.float32),destination)
    result=cv2.warpPerspective(rgb,matrix,(tw,th),borderValue=(255,255,255))
    # Real ink must not become backwards just because the preview is mirrored.
    return cv2.flip(result,1) if mirrored else result


def line_regions(rgb,light_ink=False):
    image=255-rgb if light_ink else rgb
    gray=cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
    h,w=gray.shape
    binary=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,31,15)
    # Ignore long ruled-paper guide lines; preserve shorter letter crossbars.
    rules=cv2.morphologyEx(binary,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(max(30,round(w*0.8)),1)))
    binary=cv2.subtract(binary,rules)
    n,labels,stats,_=cv2.connectedComponentsWithStats(binary)
    clean=np.zeros_like(binary)
    for i in range(1,n):
        if stats[i,cv2.CC_STAT_AREA]>=5:clean[labels==i]=255
    occupied=(clean>0).sum(axis=1)>=max(3,int(w*0.002))
    indices=np.flatnonzero(occupied)
    if not len(indices):raise ValueError("No visible writing. Use larger dark writing on light paper, or select light ink for a dark slate.")
    groups=[]; start=previous=int(indices[0]); gap=max(3,round(h*0.008))
    for row in indices[1:]:
        row=int(row)
        if row-previous>gap:
            groups.append([start,previous+1]); start=row
        previous=row
    groups.append([start,previous+1])
    # Join small dots/accents to a nearby baseline rather than sending them as
    # separate text lines. Full automatic layout inference remains unvalidated.
    merged=[]
    for group in groups:
        if merged and (group[0]-merged[-1][1]<max(12,round(h*0.03))) and (group[1]-group[0]<10 or merged[-1][1]-merged[-1][0]<10):
            merged[-1][1]=group[1]
        else:merged.append(group)
    crops=[]
    for y0,y1 in merged:
        ys,xs=np.where(clean[y0:y1]>0)
        if len(xs)<15 or y1-y0<4:continue
        margin=max(6,round((y1-y0)*0.15))
        crop=image[max(0,y0-margin):min(h,y1+margin),max(0,int(xs.min())-margin):min(w,int(xs.max())+1+margin)]
        crops.append(crop)
    if not crops:raise ValueError("Writing is too small or unclear to recognize.")
    if len(crops)>30:raise ValueError("Too many text/noise regions. Capture fewer lines or improve lighting.")
    return crops


def decode_ctc(output,characters):
    probabilities=np.asarray(output)
    if probabilities.ndim==3:probabilities=probabilities[0]
    if probabilities.ndim!=2 or probabilities.shape[1]!=len(characters) or not np.isfinite(probabilities).all():
        raise ValueError("Unexpected OCR output shape or dictionary.")
    # Official export produces probabilities; tolerate logits explicitly.
    if probabilities.min()<0 or probabilities.max()>1.001 or not np.allclose(probabilities.sum(axis=1),1,atol=0.05):
        probabilities=np.exp(probabilities-probabilities.max(axis=1,keepdims=True))
        probabilities/=probabilities.sum(axis=1,keepdims=True)
    best=probabilities.argmax(axis=1)
    text=[]; scores=[]; previous=-1
    for i,index in enumerate(best):
        index=int(index)
        if index!=0 and index!=previous:
            text.append(characters[index]); scores.append(float(probabilities[i,index]))
        previous=index
    return "".join(text),float(np.mean(scores)) if scores else None


class PaperRecognizer:
    def __init__(self,variant="medium",device="auto",profile=False):
        import onnxruntime as ort
        ort.disable_telemetry_events()
        if device not in {"auto","cpu","cuda"}:raise ValueError("Unknown OCR device.")
        self.requested_device=device
        directory=ROOT/"models/paper"/variant
        manifest=json.loads((directory/"manifest.json").read_text(encoding="utf-8"))
        if manifest.get("revision")!=REVISIONS[variant]:raise ValueError("Unexpected paper OCR revision.")
        for filename in ("inference.onnx","inference.yml"):
            if hashlib.sha256((directory/filename).read_bytes()).hexdigest()!=manifest["sha256"][filename]:
                raise ValueError("Paper OCR asset integrity failed.")
        config=yaml.safe_load((directory/"inference.yml").read_text(encoding="utf-8"))
        if config["PostProcess"]["name"]!="CTCLabelDecode":raise ValueError("Unsupported paper OCR decoder.")
        self.characters=[""]+config["PostProcess"]["character_dict"]
        if config["PostProcess"].get("use_space_char",True):self.characters.append(" ")
        options=ort.SessionOptions(); options.intra_op_num_threads=4; options.inter_op_num_threads=1
        options.log_severity_level=3
        options.enable_profiling=profile
        options.profile_file_prefix=str(ROOT/"artifacts/ocr-benchmark-profile")
        providers=["CPUExecutionProvider"]
        if device!="cpu" and "CUDAExecutionProvider" in ort.get_available_providers():
            try:
                # Project-local NVIDIA wheels, never a system CUDA installation.
                prepare_cuda_libraries(ort)
                providers=[("CUDAExecutionProvider",{"use_tf32":0,"cudnn_conv_algo_search":"HEURISTIC"}),"CPUExecutionProvider"]
            except (OSError,RuntimeError):
                if device=="cuda":raise RuntimeError("GPU libraries could not be loaded.")
        self.session=ort.InferenceSession(str(directory/"inference.onnx"),sess_options=options,providers=providers)
        self.session.disable_fallback()
        self.input=self.session.get_inputs()[0].name
        self.variant=variant
        # Verify the selected execution path before reporting it as ready.
        try:self.session.run(None,{self.input:np.zeros((1,3,48,320),np.float32)})
        except Exception:
            if device!="auto":raise RuntimeError("Requested OCR device failed its execution check.") from None
            self.session=ort.InferenceSession(str(directory/"inference.onnx"),sess_options=options,providers=["CPUExecutionProvider"])
            self.session.disable_fallback()
            self.session.run(None,{self.input:np.zeros((1,3,48,320),np.float32)})
        gpu="CUDAExecutionProvider" in self.session.get_providers()
        if device=="cuda" and not gpu:raise RuntimeError("GPU OCR was required but CUDA is unavailable. Select CPU or GPU when available.")
        self.device="GPU (CUDA)" if gpu else ("CPU" if device=="cpu" else "CPU (GPU unavailable)")

    def recognize_line(self,rgb):
        h,w=rgb.shape[:2]
        width=max(16,min(2048,math.ceil(48*w/h)))
        # Export accepts a dynamic width, padded to at least its training width.
        padded_width=max(320,width)
        resized=cv2.resize(cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR),(width,48))
        normalized=resized.astype(np.float32)/127.5-1
        tensor=np.zeros((1,3,48,padded_width),np.float32)
        tensor[0,:,:,:width]=normalized.transpose(2,0,1)
        output=self.session.run(None,{self.input:tensor})[0]
        return decode_ctc(output,self.characters)

    def recognize(self,rgb,light_ink=False):
        start=time.perf_counter()
        lines=line_regions(rgb,light_ink)
        texts=[]; scores=[]
        for line in lines:
            text,score=self.recognize_line(line)
            if text.strip():texts.append(text.strip())
            if score is not None:scores.append(score)
        if not texts:raise ValueError("No readable text was found.")
        # No automatic Enter/command submission. Flatten line breaks into spaces
        # before the explicit text preview and native-input validation.
        text=" ".join(texts)
        return Recognition(text,float(np.mean(scores)) if scores else None,time.perf_counter()-start,device=self.device)


class PaperWorker(QThread):
    ready=Signal(object); failed=Signal(str)
    def __init__(self,rgb,light_ink=False,variant="medium",existing=None,device="auto"):
        super().__init__()
        self.image=rgb; self.light_ink=light_ink; self.variant=variant; self.recognizer=existing;self.device=device
    def run(self):
        try:
            if self.recognizer is None:self.recognizer=PaperRecognizer(self.variant,self.device)
            result=self.recognizer.recognize(self.image,self.light_ink)
            if not self.isInterruptionRequested():self.ready.emit(result)
        except Exception:
            if not self.isInterruptionRequested():self.failed.emit("Paper OCR could not read the selected writing. Remove your hand, improve lighting/write larger, and retry. No text was sent.")
        finally:self.image=None
