"""Bounded, local playground simulation. Never emits desktop input or saves frames."""
from collections import deque
from dataclasses import dataclass
import math
import random
import numpy as np
from .hand_gestures import visible_control
from .gestures import Pinch
from .smoothing import OneEuro

SCENES=("portal","web","nebula")


def clamp(value,low,high):return max(low,min(high,value))


@dataclass
class Particle:
    x:float;y:float;vx:float;vy:float;life:float;ttl:float;size:float;kind:int=0


@dataclass
class Portal:
    x:float;y:float;radius:float;born:float


def fit_portal(samples):
    """Require a large, closed, consistently circular observed stroke."""
    if len(samples)<12 or not .65<=samples[-1][2]-samples[0][2]<=4.5:return None
    points=np.asarray([(p[0],p[1]) for p in samples],dtype=float)
    if not np.isfinite(points).all():return None
    span=np.ptp(points,axis=0)
    if min(span)<.18 or max(span)>1.8 or not .65<span[0]/max(span[1],1e-8)<1.5:return None
    matrix=np.column_stack((2*points[:,0],2*points[:,1],np.ones(len(points))))
    fit,_,rank,_=np.linalg.lstsq(matrix,(points*points).sum(axis=1),rcond=None)
    if rank<3:return None
    center=fit[:2];r2=fit[2]+float(center@center)
    if r2<=0:return None
    radius=math.sqrt(r2)
    if not .09<=radius<=.65:return None
    distances=np.linalg.norm(points-center,axis=1)
    if float(np.sqrt(np.mean((distances-radius)**2)))/radius>.14:return None
    if np.linalg.norm(points[-1]-points[0])>radius*.4:return None
    angles=np.unwrap(np.arctan2(points[:,1]-center[1],points[:,0]-center[0]))
    coverage=abs(float(angles[-1]-angles[0]))
    travel=float(np.linalg.norm(np.diff(points,axis=0),axis=1).sum())
    if not 5.4<=coverage<=8.0 or not 5*radius<=travel<=8.8*radius:return None
    return float(center[0]),float(center[1]),radius


class PlaygroundModel:
    max_particles=900
    def __init__(self,scene="portal",seed=None):
        self.rng=random.Random(seed);self.scene=scene;self.aspect=4/3
        self.filter=OneEuro(min_cutoff=4,beta=1.5)
        self.pinch=Pinch(press_debounce_ms=25,latch_press=True)
        self.stars=[]
        for _ in range(580):
            radius=self.rng.random()**.6*.75;angle=self.rng.random()*math.tau
            x,y=math.cos(angle)*radius*1.5,math.sin(angle)*radius*.75
            self.stars.append(Particle(x,y,-y*.13,x*.13,1,1,self.rng.uniform(.6,1.7),1))
        self.initial_stars=[(p.x,p.y,p.vx,p.vy) for p in self.stars]
        self.clear()

    def clear(self):
        for p,initial in zip(self.stars,self.initial_stars):p.x,p.y,p.vx,p.vy=initial
        self.particles=[];self.trail=deque(maxlen=420);self.stroke=deque(maxlen=180)
        self.portals=deque(maxlen=3);self.last_point=None;self.stroke_id=0
        self.brush=None;self.other=None;self.last_input=None;self.last_hand_time=None
        self.last_step=None;self.time=0;self.input_state="Show your right hand"
        self.dome_scale=self.dome_target=.85;self.yaw=self.yaw_target=-.3
        self.pitch=self.pitch_target=.35;self.dome_center=(0.,0.)
        self.pulse=0;self.portal_cooldown=0
        self.filter.reset();self.pinch.reset()

    def set_scene(self,scene):
        if scene not in SCENES:raise ValueError("Unknown playground scene")
        self.scene=scene;self.clear()

    def interrupt(self,message="Tracking paused — bring your right hand into view"):
        self.brush=self.other=None;self.last_point=None;self.stroke.clear()
        self.last_hand_time=None;self.stroke_id+=1
        self.filter.reset();self.pinch.reset();self.input_state=message

    def emit(self,x,y,count=12,energy=1,kind=0):
        for _ in range(min(count,80)):
            angle=self.rng.random()*math.tau;speed=self.rng.uniform(.04,.3)*energy
            ttl=self.rng.uniform(.28,1.1)
            self.particles.append(Particle(x,y,math.cos(angle)*speed,math.sin(angle)*speed-.05,
                                           ttl,ttl,self.rng.uniform(.8,2.3),kind))
        if len(self.particles)>self.max_particles:del self.particles[:-self.max_particles]

    def observe(self,hands,t,mirrored=True,age=0,aspect=4/3):
        if not math.isfinite(t) or not math.isfinite(age) or age<0 or age>.2:
            self.interrupt("Tracking delayed — trail paused");return
        if not math.isfinite(aspect) or not .5<=aspect<=3:
            self.interrupt();return
        if abs(aspect-self.aspect)>.02:
            self.clear();self.aspect=aspect
        self.last_input=t
        trusted=[h for h in hands if math.isfinite(h.handedness_confidence) and h.handedness_confidence>=.65]
        if len(trusted)>2 or len({h.label for h in trusted})!=len(trusted):
            self.interrupt("Separate your hands — tracking is unclear");return
        right_label="Left" if mirrored else "Right"
        right=next((h for h in trusted if h.label==right_label and visible_control(h)),None)
        left=next((h for h in trusted if h.label!=right_label and visible_control(h)),None)
        if right is None:
            self.interrupt("Show your right hand · keep fingers and knuckles in frame");return
        p=right.landmarks
        point=((p[8][0]-.5)*aspect,p[8][1]-.5)
        if self.last_hand_time is not None and (not 0<t-self.last_hand_time<=.2
                or (self.last_point is not None and math.dist(point,self.last_point)>.35)):
            self.interrupt("Hand reacquired — starting a new trail")
        self.last_hand_time=t;point=self.filter.update(point,t)
        self.brush=point
        def palm(hand):
            return (sum(hand.landmarks[i][0]-.5 for i in (0,5,9,13,17))/5*aspect,
                    sum(hand.landmarks[i][1]-.5 for i in (0,5,9,13,17))/5)
        center=palm(right)
        self.other=palm(left) if left is not None else None
        self.input_state="Right hand tracked"
        if self.scene=="portal":
            if self.last_point is not None:
                distance=math.dist(point,self.last_point)
                if distance>.003:
                    count=max(1,min(24,int(distance/.009)))
                    for i in range(1,count+1):
                        u=i/count
                        self.trail.append((self.last_point[0]+(point[0]-self.last_point[0])*u,
                                           self.last_point[1]+(point[1]-self.last_point[1])*u,t,self.stroke_id))
                    self.emit(*point,min(18,2+int(distance*100)),energy=1.2)
            if not self.stroke or math.dist(point,self.stroke[-1][:2])>.005:self.stroke.append((*point,t))
            while self.stroke and t-self.stroke[0][2]>4.5:self.stroke.popleft()
            portal=fit_portal(self.stroke) if t>=self.portal_cooldown else None
            if portal:
                self.portals.append(Portal(*portal,t));self.portal_cooldown=t+1.2
                self.stroke.clear();self.emit(*point,70,energy=2);self.pulse=1
                self.input_state="Portal formed · draw another circle"
        elif self.scene=="web":
            if self.other is not None:
                spread=math.dist(center,self.other)
                self.dome_target=clamp(.45+spread*1.7,.5,1.8)
                self.dome_center=(clamp((center[0]+self.other[0])*.15,-.15,.15),
                                  clamp((center[1]+self.other[1])*.12,-.08,.08))
                self.input_state="Two hands linked · spread apart to expand"
            self.yaw_target=center[0]*2.2;self.pitch_target=clamp(.35+center[1]*1.3,-.15,.85)
        elif self.other is not None:self.input_state="Two gravity wells · pinch your right hand for a burst"
        if self.scene!="portal":
            was_down=self.pinch.down
            down=self.pinch.update(right.ratio,t)
            if down and not was_down:
                self.pulse=1;self.emit(*point,70,energy=2.6,kind=1)
                if self.scene=="nebula":
                    for star in self.stars:
                        dx,dy=star.x-point[0],star.y-point[1];d=max(.03,math.hypot(dx,dy))
                        star.vx+=dx/d*.6;star.vy+=dy/d*.6
        self.last_point=point

    def advance(self,t):
        if not math.isfinite(t):return
        dt=0 if self.last_step is None else clamp(t-self.last_step,0,.04)
        self.last_step=t;self.time=t
        if self.last_input is not None and t-self.last_input>.22 and self.brush is not None:self.interrupt()
        while self.trail and t-self.trail[0][2]>1.6:self.trail.popleft()
        while self.portals and t-self.portals[0].born>9:self.portals.popleft()
        self.pulse=max(0,self.pulse-dt*1.4)
        self.dome_scale+=(self.dome_target-self.dome_scale)*min(1,dt*7)
        self.yaw+=(self.yaw_target-self.yaw)*min(1,dt*6)
        self.pitch+=(self.pitch_target-self.pitch)*min(1,dt*6)
        if self.scene=="portal" and dt:
            if self.brush:self.emit(*self.brush,2,energy=.65)
            for portal in self.portals:
                for _ in range(3):
                    a=self.rng.random()*math.tau
                    self.emit(portal.x+math.cos(a)*portal.radius,portal.y+math.sin(a)*portal.radius,1)
        survivors=[]
        for p in self.particles:
            p.life-=dt
            if p.life<=0:continue
            p.x+=p.vx*dt;p.y+=p.vy*dt;p.vy+=(-.12 if p.kind==0 else .02)*dt
            survivors.append(p)
        self.particles=survivors
        if self.scene=="nebula" and dt:
            for p in self.stars:
                # Softened, capped attraction plus tangential force creates a
                # controllable vortex rather than a singularity at the hand.
                targets=[(self.brush,1)] if self.brush else [((0.,0.),.12)]
                if self.other:targets.append((self.other,-.5))
                for point,strength in targets:
                    dx,dy=point[0]-p.x,point[1]-p.y;d2=dx*dx+dy*dy+.035
                    force=clamp(strength*.06/d2,-1.5,1.5)
                    p.vx+=(dx-dy*.8)*force*dt;p.vy+=(dy+dx*.8)*force*dt
                p.vx*=math.exp(-dt*.5);p.vy*=math.exp(-dt*.5)
                speed=math.hypot(p.vx,p.vy)
                if speed>1.8:p.vx*=1.8/speed;p.vy*=1.8/speed
                p.x+=p.vx*dt;p.y+=p.vy*dt
                if abs(p.x)>1.4 or abs(p.y)>.9:
                    p.x=self.rng.uniform(-1.2,1.2);p.y=self.rng.choice((-.65,.65));p.vx=p.vy=0
