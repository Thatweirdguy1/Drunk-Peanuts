"""Animation math adapted from DeckCraft, MIT licensed.

Copyright (c) 2026 ArtCraft Team and the DeckCraft contributors.
Source: 0d45a64db23baa0a4c8f9f7ac14c59c91b40fec9,
crates/anim/src/easing.rs and effects.rs. See assets/deckcraft-LICENSE-MIT.txt.
The Qt adapter and Python implementation are modified for Drunk Peanuts.
"""
import math

PRESETS={'Appear':1,'Fade':10,'Fly':2,'Float':42,'Split':16,'Wipe':22,'Circle':6,'Box':4,'Diamond':8,'Grow and turn':31,'Zoom':53,'Swivel':45,'Bounce':26,'Peek':12,'Strips':18,'Expand':55,'Rise':37,'Spinner':49,'Pulse':26,'Teeter':32,'Spin':8,'Grow/shrink':6,'Wave':34,'Transparency':9,'Motion path':0}
EMPHASIS={'Pulse','Teeter','Spin','Grow/shrink','Wave','Transparency'}


def clamp(value,low=0.,high=1.):
    return min(high,max(low,value)) if math.isfinite(value) else low


def ease(progress,accel=0.,decel=0.,bounce=0.):
    p=clamp(progress);a=clamp(accel);d=clamp(decel)
    if a+d>1:a,d=a/(a+d),d/(a+d)
    velocity=2/(2-a-d)
    if a>0 and p<a:y=velocity*p*p/(2*a)
    elif d>0 and p>1-d:y=1-velocity*(1-p)**2/(2*d)
    else:y=velocity*a/2+velocity*(p-a)
    b=clamp(bounce)
    if b:
        hit=1-b
        if p<hit:y=(p/hit)**2 if hit else 1.
        else:
            s=(p-hit)/b;k=min(2,math.floor(s*3));y=1-(.5**k)*math.sin((s*3-k)*math.pi)*.25
    return clamp(y,-1.,2.)


def bounce_out(progress):
    p=clamp(progress);n=7.5625;d=2.75
    if p<1/d:return n*p*p
    if p<2/d:return n*(p-1.5/d)**2+.75
    if p<2.5/d:return n*(p-2.25/d)**2+.9375
    return min(1,n*(p-2.625/d)**2+.984375)


def sample(effect,phase,progress,direction,slide_width,slide_height,amount=1.5,box=(0,0,0,0)):
    p=clamp(progress);p=1-p if phase=='Exit' else p;q=1-p;state=dict(opacity=1.,x=0.,y=0.,sx=1.,sy=1.,rotation=0.,clip=None)
    if effect=='Appear':state['opacity']=1. if p>0 else 0.
    elif effect=='Fade':state['opacity']=p
    elif effect=='Fly':
        x,y,w,h=box;state['x']=(-(x+w) if direction=='Left' else slide_width-x if direction=='Right' else 0)*q;state['y']=(-(y+h) if direction=='Up' else slide_height-y if direction=='Down' else 0)*q
    elif effect=='Wipe':state['clip']={'Left':(0.,0.,p,1.),'Right':(q,0.,1.,1.),'Up':(0.,0.,1.,p),'Down':(0.,q,1.,1.)}[direction]
    elif effect=='Zoom':state.update(opacity=p,sx=p,sy=p)
    elif effect=='Pulse':state.update(sx=1+.18*math.sin(p*math.pi),sy=1+.18*math.sin(p*math.pi))
    elif effect=='Spin':state['rotation']=amount*p
    elif effect in ('Float','Rise'):state.update(opacity=p,y=(1 if direction!='Down' else -1)*.1*slide_height*q)
    elif effect=='Split':state['clip']=(0.,q/2,1.,1-q/2) if direction in ('Left','Right') else (q/2,0.,1-q/2,1.)
    elif effect in ('Circle','Box','Diamond'):state['clip']=(q/2,q/2,1-q/2,1-q/2)
    elif effect=='Grow and turn':state.update(sx=p,sy=p,rotation=-90*q,opacity=p)
    elif effect=='Swivel':state.update(sx=p*math.cos(q*2.5*math.pi),opacity=p)
    elif effect=='Bounce':state.update(x=-.1*slide_width*q,y=-.25*slide_height*(1-bounce_out(p)),opacity=min(1,p*4))
    elif effect=='Peek':
        state['clip']={'Left':(q,0.,1.,1.),'Right':(0.,0.,p,1.),'Up':(0.,q,1.,1.),'Down':(0.,0.,1.,p)}[direction]
        state['x']=(-1 if direction=='Left' else 1 if direction=='Right' else 0)*.2*slide_width*q
        state['y']=(-1 if direction=='Up' else 1 if direction=='Down' else 0)*.2*slide_height*q
    elif effect=='Strips':state['clip']=(q,q,1.,1.)
    elif effect=='Expand':state.update(sx=.3+.7*p,opacity=p)
    elif effect=='Spinner':state.update(rotation=360*q,sx=.5+.5*p,sy=.5+.5*p,opacity=p)
    elif effect=='Teeter':state['rotation']=8*math.sin(p*4*math.pi)*(1-p*.5)
    elif effect=='Grow/shrink':state.update(sx=1+(amount-1)*p,sy=1+(amount-1)*p)
    elif effect=='Wave':state.update(y=-.02*slide_height*math.sin(p*math.pi),sy=1+.05*math.sin(p*math.pi))
    elif effect=='Transparency':state['opacity']=1-clamp(amount)*p
    return state
