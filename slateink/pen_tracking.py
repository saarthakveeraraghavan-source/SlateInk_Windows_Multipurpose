"""Experimental colored pen-tip marker tracking. No inferred touch/clicks."""
import cv2
import numpy as np


class PenMarker:
    def __init__(self):
        self.hue=None; self.previous=None; self.last_t=None

    def reset(self):
        self.hue=self.previous=self.last_t=None

    def select(self,rgb,x,y):
        h,w=rgb.shape[:2]
        px=max(0,min(w-1,round(x*(w-1)))); py=max(0,min(h-1,round(y*(h-1))))
        hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
        crop=hsv[max(0,py-4):py+5,max(0,px-4):px+5]
        candidates=crop[(crop[:,:,1]>90)&(crop[:,:,2]>70)]
        if len(candidates)<5:raise ValueError("Select a bright colored marker near the pen tip. Plain black tips are not reliably distinguishable from writing.")
        self.hue=int(np.median(candidates[:,0])); self.previous=(x,y); self.last_t=None

    def detect(self,rgb,t):
        if self.hue is None:return None
        hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
        distance=np.abs(hsv[:,:,0].astype(np.int16)-self.hue)
        distance=np.minimum(distance,180-distance)
        mask=((distance<10)&(hsv[:,:,1]>90)&(hsv[:,:,2]>70)).astype(np.uint8)*255
        mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
        count,_,stats,centers=cv2.connectedComponentsWithStats(mask)
        h,w=rgb.shape[:2]
        choices=[]
        for i in range(1,count):
            area=stats[i,cv2.CC_STAT_AREA]
            if not (8<=area<=h*w*0.008):continue
            point=(float(centers[i,0]/(w-1)),float(centers[i,1]/(h-1)))
            d=np.hypot(point[0]-self.previous[0],point[1]-self.previous[1])
            if d<0.15:choices.append((d,point))
        if not choices:
            self.last_t=t
            return None
        choices.sort()
        if len(choices)>1 and abs(choices[0][0]-choices[1][0])<0.025:return None
        point=choices[0][1]
        self.previous=point; self.last_t=t
        return point
