"""Native PresentationML animation authoring and deterministic Qt playback."""
from __future__ import annotations
import copy,math,re
from dataclasses import dataclass,asdict
from lxml import etree
from PySide6.QtCore import (QObject,QPointF,QVariantAnimation,QSequentialAnimationGroup,
                           QParallelAnimationGroup,QPauseAnimation,Qt)
from PySide6.QtGui import QPainterPath
from pptx.oxml.xmlchemy import OxmlElement
from animation_math import PRESETS,EMPHASIS,ease,sample

P='http://schemas.openxmlformats.org/presentationml/2006/main'
FC='urn:drunkpeanuts:timeline:1'
NS={'p':P}
EFFECTS=tuple(PRESETS)
STARTS=('On click','With previous','After previous')
PHASES=('Entrance','Emphasis','Exit')


def slide_shapes(slide):
    def visit(shapes):
        for shape in shapes:
            yield shape
            if shape.shape_type==6:yield from visit(shape.shapes)
    return {shape.shape_id:shape for shape in visit(slide.shapes)}


@dataclass
class Effect:
    shape:int
    effect:str='Fade'
    phase:str='Entrance'
    start:str='On click'
    duration:float=.6
    delay:float=0
    repeat:int=1
    direction:str='Left'
    trigger:int=0
    path:str='M 0 0 L 0.25 0 E'
    source:str=''
    accel:float=0.
    decel:float=0.
    bounce:float=0.
    amount:float=0.
    autoreverse:bool=False
    rewind:bool=False
    paragraph:int=-1
    native_preset:str=''

    def validate(self):
        if self.shape<1 or self.effect not in EFFECTS or self.phase not in PHASES or self.start not in STARTS:raise ValueError('Choose a supported animation and target object.')
        if not all(math.isfinite(v) for v in (self.duration,self.delay)) or not .05<=self.duration<=120 or not 0<=self.delay<=120:raise ValueError('Duration must be 0.05–120 seconds; delay 0–120 seconds.')
        if not isinstance(self.repeat,int) or not -1<=self.repeat<=100 or self.repeat==0 or self.trigger<0:raise ValueError('Repeat must be 1–100 or indefinite; choose an existing trigger.')
        if not isinstance(self.paragraph,int) or not -1<=self.paragraph<=10000:raise ValueError('Choose a paragraph or the whole object.')
        if self.direction not in ('Left','Right','Up','Down'):raise ValueError('Choose a direction.')
        if not all(math.isfinite(v) and 0<=v<=1 for v in (self.accel,self.decel,self.bounce)):raise ValueError('Smoothing and bounce must be 0–100%.')
        if not math.isfinite(self.amount) or abs(self.amount)>36000:raise ValueError('Animation amount is out of range.')
        motion_path(self.path)
        return self


def motion_path(value):
    if not isinstance(value,str) or len(value)>10000:raise ValueError('Motion path is too long.')
    pattern=r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?|[MLCZEmlcze]'
    if re.sub(pattern,'',value).strip(' \t\r\n,'):raise ValueError('Unsupported motion path command.')
    tokens=re.findall(pattern,value);path=QPainterPath();i=0
    try:
        while i<len(tokens):
            token=tokens[i];op=token.upper();i+=1
            if op in ('E','Z'):
                if op=='Z':path.closeSubpath()
                continue
            count=6 if op=='C' else 2 if op in ('M','L') else 0
            if not count:raise ValueError()
            values=[float(n) for n in tokens[i:i+count]];i+=count
            if len(values)!=count or not all(math.isfinite(n) and abs(n)<=100 for n in values):raise ValueError()
            if token.islower():
                point=path.currentPosition();values=[n+(point.x() if offset%2==0 else point.y()) for offset,n in enumerate(values)]
            if op=='M':path.moveTo(*values)
            elif op=='L':path.lineTo(*values)
            else:path.cubicTo(*values)
    except (ValueError,TypeError):raise ValueError('Use normalized M x y, L x y or C x1 y1 x2 y2 x y path commands.') from None
    if path.elementCount()<2:raise ValueError('A motion path needs at least two points.')
    return path


def own_effects(slide):
    result=[]
    for node in slide._element.findall('.//{'+FC+'}effect'):
        try:
            values=dict(node.attrib)
            for key in ('shape','repeat','trigger','paragraph'):
                if key in values:values[key]=int(values[key])
            for key in ('duration','delay','accel','decel','bounce','amount'):
                if key in values:values[key]=float(values[key])
            for key in ('autoreverse','rewind'):
                if key in values:values[key]=values[key]=='True'
            result.append(Effect(**values).validate())
        except (ValueError,TypeError,KeyError):continue
    return result


def timeline(slide):
    """Read native imported animation nodes; retain unknown nodes in the document."""
    result=[];owned_ids={e.source for e in own_effects(slide)}
    for node in slide._element.findall('.//p:cTn',NS):
        phase={'entr':'Entrance','exit':'Exit','emph':'Emphasis','path':'Emphasis'}.get(node.get('presetClass'))
        if not phase or node.get('id') in owned_ids:continue
        targets=node.findall('.//p:spTgt',NS)
        if not targets:continue
        effect=node.find('.//p:animEffect',NS);motion=node.find('.//p:animMotion',NS)
        preset=node.get('presetID','1');known={str(value):key for key,value in PRESETS.items() if (key in EMPHASIS)==(phase=='Emphasis')};name=known.get(preset,'Fade')
        if phase in ('Entrance','Exit'):known['47']='Float';name=known.get(preset,name)
        if effect is not None and preset not in known:
            filt=effect.get('filter','').lower();name=next((v for k,v in [('fade','Fade'),('wipe','Wipe'),('slide','Fly'),('zoom','Zoom')] if k in filt),name)
        if motion is not None:name='Motion path'
        elif preset not in known and node.find('.//p:animRot',NS) is not None:name='Spin'
        elif node.find('.//p:animScale',NS) is not None and phase=='Emphasis' and preset not in known:name='Pulse'
        duration=max((float(n.get('dur'))/1000*(2 if n.get('autoRev') in ('1','true') else 1)*(float(n.get('repeatCount','1000'))/1000 if n.get('repeatCount','1000').isdigit() else 1) for n in node.findall('.//p:cTn',NS) if n.get('dur','').isdigit() and int(n.get('dur'))>1),default=.6)
        start={'withEffect':'With previous','afterEffect':'After previous'}.get(node.get('nodeType'),'On click')
        delay=next((float(n.get('delay'))/1000 for n in node.findall('./p:stCondLst/p:cond',NS) if n.get('delay','').isdigit()),0)
        trigger=next((int(t.get('spid')) for t in node.findall('.//p:cond[@evt="onClick"]/p:tgtEl/p:spTgt',NS) if t.get('spid','').isdigit()),0)
        if not trigger:
            for parent in node.iterancestors('{'+P+'}cTn'):
                if parent.get('nodeType')!='interactiveSeq':continue
                target=parent.find('p:stCondLst/p:cond/p:tgtEl/p:spTgt',NS)
                if target is not None and target.get('spid','').isdigit():trigger=int(target.get('spid'));break
        try:
            repeat=-1 if node.get('repeatCount')=='indefinite' else min(100,max(1,int(float(node.get('repeatCount','1000'))/1000)))
            entry=Effect(int(targets[0].get('spid')),name,phase,start,min(120,max(.05,duration)),min(120,delay),repeat,'Left',trigger,motion.get('path') if motion is not None else 'M 0 0 L 0.25 0 E',node.get('id',''))
            if preset not in known and motion is None:entry.native_preset=preset
            entry.direction={'1':'Up','2':'Right','4':'Down','8':'Left'}.get(node.get('presetSubtype'),'Down' if preset=='47' else 'Left')
            if effect is not None:
                direction=re.search(r'(?:wipe|slide)\((?:from)?(left|right|up|down)\)',effect.get('filter',''),re.I)
                if direction:
                    entry.direction=direction.group(1).title()
                    if effect.get('filter','').lower().startswith('wipe'):entry.direction={'Left':'Right','Right':'Left','Up':'Down','Down':'Up'}[entry.direction]
            paragraph=targets[0].find('p:txEl/p:pRg',NS)
            if paragraph is not None:entry.paragraph=int(paragraph.get('st','0'))
            entry.accel=float(node.get('accel','0'))/100000;entry.decel=float(node.get('decel','0'))/100000;entry.bounce=float(node.get('bounceEnd','0'))/100000;entry.autoreverse=node.get('autoRev') in ('1','true');entry.rewind=node.get('fill')=='remove'
            rotation=node.find('.//p:animRot',NS)
            if rotation is not None:entry.amount=float(rotation.get('by','21600000'))/60000
            result.append(entry.validate())
        except (ValueError,TypeError):continue
    return result+own_effects(slide)


def write_timeline(slide,entries):
    """Write a separate native sequence, preserving imported timing/media nodes."""
    shapes=slide_shapes(slide)
    for entry in entries:
        entry.validate()
        if entry.shape not in shapes or entry.trigger and entry.trigger not in shapes:raise ValueError('Choose an existing object and trigger on this slide.')
        if entry.paragraph>=0 and (not shapes[entry.shape].has_text_frame or entry.paragraph>=len(shapes[entry.shape].text_frame.paragraphs)):raise ValueError('Choose an existing paragraph or Whole object.')
    for previous,entry in zip(entries,entries[1:]):
        if previous.repeat==-1 and entry.start=='After previous' and previous.trigger==entry.trigger:
            raise ValueError('An effect after an indefinite repeat needs an On click start.')
    old=slide._element.find('.//{'+FC+'}timeline')
    if old is not None:
        sequence_id=old.get('sequence')
        for seq in slide._element.findall('.//p:seq',NS):
            node=seq.find('p:cTn',NS)
            if node is not None and node.get('id')==sequence_id:seq.getparent().remove(seq)
        old.getparent().getparent().remove(old.getparent())
    if not entries:
        timing=slide._element.find('p:timing',NS)
        root=timing.find('.//p:cTn[@nodeType="tmRoot"]/p:childTnLst',NS) if timing is not None else None
        if root is not None and not len(root):slide._element.remove(timing)
        return
    from pathlib import Path
    template=etree.fromstring((Path(__file__).resolve().parent/'assets/animation-fade.xml').read_bytes())
    timing=slide._element.find('p:timing',NS)
    if timing is None:
        timing=copy.deepcopy(template);timing.find('.//p:cTn[@nodeType="tmRoot"]/p:childTnLst',NS).clear();timing.remove(timing.find('p:bldLst',NS))
        before=slide._element.find('p:extLst',NS);slide._element.insert(list(slide._element).index(before) if before is not None else len(slide._element),timing)
    root=timing.find('.//p:cTn[@nodeType="tmRoot"]/p:childTnLst',NS)
    if root is None:raise ValueError('This timing tree cannot be extended safely.')
    next_id=max((int(n.get('id')) for n in timing.findall('.//p:cTn',NS) if n.get('id','').isdigit()),default=1)+1
    def identify(element):
        nonlocal next_id
        for n in element.findall('.//p:cTn',NS):n.set('id',str(next_id));next_id+=1
    sequence=copy.deepcopy(template.find('.//p:seq',NS));sequence.find('p:cTn/p:childTnLst',NS).clear();identify(sequence);root.append(sequence)
    main=sequence.find('p:cTn/p:childTnLst',NS)
    extlst=slide._element.find('p:extLst',NS)
    if extlst is None:extlst=OxmlElement('p:extLst');slide._element.append(extlst)
    ext=OxmlElement('p:ext');ext.set('uri',FC);extlst.append(ext);metadata=etree.SubElement(ext,'{'+FC+'}timeline',sequence=sequence.find('p:cTn',NS).get('id'))
    prototype=template.find('.//p:cTn[@nodeType="mainSeq"]/p:childTnLst',NS)[0]
    previous_group=None;previous_start=previous_end=0
    for entry in entries:
        group=copy.deepcopy(prototype);identify(group)
        offset=(previous_start if entry.start=='With previous' else previous_end if entry.start=='After previous' else 0)+round(entry.delay*1000)
        if previous_group is not None and entry.start!='On click' and not entry.trigger:
            inner=group.find('p:cTn/p:childTnLst',NS)[0];previous_group.find('p:cTn/p:childTnLst',NS).append(inner)
            inner.find('p:cTn/p:stCondLst/p:cond',NS).set('delay',str(offset))
            group=inner
        else:
            main.append(group);previous_group=group
            if entry.start!='On click' and not entry.trigger:group.find('p:cTn/p:stCondLst/p:cond',NS).set('delay',str(round(entry.delay*1000)))
        previous_start=offset;previous_end=offset+round(entry.duration*1000)*entry.repeat*(2 if entry.autoreverse else 1)
        effect_node=group.find('.//p:cTn[@presetClass]',NS);effect_node.set('nodeType',{'On click':'clickEffect','With previous':'withEffect','After previous':'afterEffect'}[entry.start]);effect_node.set('presetClass',{'Entrance':'entr','Emphasis':'emph','Exit':'exit'}[entry.phase]);effect_node.set('presetID',str(PRESETS[entry.effect]))
        if entry.effect=='Motion path':effect_node.set('presetClass','path')
        for key,value in [('accel',entry.accel),('decel',entry.decel),('bounceEnd',entry.bounce)]:
            if value:effect_node.set(key,str(round(value*100000)))
        if entry.autoreverse:effect_node.set('autoRev','1')
        effect_node.set('fill','remove' if entry.rewind else 'hold')
        effect_node.find('p:stCondLst/p:cond',NS).set('delay','0')
        if entry.start=='On click':group.find('p:cTn/p:childTnLst/p:par/p:cTn/p:stCondLst/p:cond',NS).set('delay',str(round(entry.delay*1000)))
        if entry.trigger:
            condition=group.find('p:cTn/p:stCondLst/p:cond',NS);condition.set('evt','onClick');condition.set('delay','0');target=OxmlElement('p:tgtEl');sp=OxmlElement('p:spTgt');sp.set('spid',str(entry.trigger));target.append(sp);condition.append(target)
        for target in group.findall('.//p:spTgt',NS):
            if not any(etree.QName(parent).localname=='cond' for parent in target.iterancestors()):target.set('spid',str(entry.shape))
        behavior=group.find('.//p:animEffect',NS);behavior.set('transition','out' if entry.phase=='Exit' else 'in');behavior.set('filter',{'Wipe':{'Left':'wipe(right)','Right':'wipe(left)','Up':'wipe(down)','Down':'wipe(up)'}[entry.direction],'Split':'barn(outHorizontal)','Circle':'circle(out)','Box':'box(out)','Diamond':'diamond(out)','Strips':'strips(upLeft)','Peek':{'Left':'slide(fromLeft)','Right':'slide(fromRight)','Up':'slide(fromTop)','Down':'slide(fromBottom)'}[entry.direction]}.get(entry.effect,'fade'))
        clock=behavior.find('p:cBhvr/p:cTn',NS);clock.set('dur',str(round(entry.duration*1000)));effect_node.set('repeatCount','indefinite' if entry.repeat==-1 else str(entry.repeat*1000))
        if entry.effect=='Motion path':
            behavior.tag='{'+P+'}animMotion';behavior.attrib.clear();behavior.set('origin','layout');behavior.set('path',entry.path);behavior.set('pathEditMode','relative')
        elif entry.effect=='Spin':
            behavior.tag='{'+P+'}animRot';behavior.attrib.clear();behavior.set('by',str(round((entry.amount or 360)*60000)))
        elif entry.effect=='Pulse':
            behavior.tag='{'+P+'}animScale';behavior.attrib.clear();clock.set('autoRev','1');clock.set('dur',str(round(entry.duration*500)));value=OxmlElement('p:to');value.set('x','118000');value.set('y','118000');behavior.append(value)
        elif entry.effect=='Grow/shrink':
            behavior.tag='{'+P+'}animScale';behavior.attrib.clear();value=OxmlElement('p:to');value.set('x',str(round((entry.amount or 1.5)*100000)));value.set('y',value.get('x'));behavior.append(value)
        elif entry.effect=='Teeter':
            behavior.tag='{'+P+'}animRot';behavior.attrib.clear();behavior.set('by','480000');clock.set('autoRev','1');clock.set('repeatCount','2000');clock.set('dur',str(round(entry.duration*250)))
        if entry.effect in ('Fly','Float','Rise','Zoom','Grow and turn','Expand','Spinner','Wave','Transparency'):
            container=behavior.getparent();template_behavior=copy.deepcopy(behavior.find('p:cBhvr',NS));container.remove(behavior)
            def prop(name,first,last):
                nonlocal next_id
                node=OxmlElement('p:anim');node.set('calcmode','lin');node.set('valueType','num');container.append(node);bhvr=copy.deepcopy(template_behavior);bhvr.find('p:cTn',NS).set('id',str(next_id));next_id+=1;node.append(bhvr)
                names=OxmlElement('p:attrNameLst');label=OxmlElement('p:attrName');label.text=name;names.append(label);bhvr.append(names);listing=OxmlElement('p:tavLst');node.append(listing)
                for tm,value in [('0',first),('100000',last)]:
                    tav=OxmlElement('p:tav');tav.set('tm',tm);listing.append(tav);val=OxmlElement('p:val');tav.append(val);text=OxmlElement('p:strVal');text.set('val',value);val.append(text)
                return bhvr.find('p:cTn',NS)
            out=entry.phase=='Exit'
            def values(first,last):return (last,first) if out else (first,last)
            if entry.effect=='Fly':
                x={'Left':'0-#ppt_w/2','Right':'1+#ppt_w/2'}.get(entry.direction,'#ppt_x');y={'Up':'0-#ppt_h/2','Down':'1+#ppt_h/2'}.get(entry.direction,'#ppt_y');prop('ppt_x',*values(x,'#ppt_x'));prop('ppt_y',*values(y,'#ppt_y'))
            elif entry.effect in ('Float','Rise','Wave'):
                clock=prop('ppt_y',*values('#ppt_y+.1' if entry.effect!='Wave' else '#ppt_y','#ppt_y' if entry.effect!='Wave' else '#ppt_y-.02'))
                if entry.effect=='Wave':clock.set('autoRev','1');clock.set('dur',str(round(entry.duration*500)))
            elif entry.effect=='Transparency':prop('style.opacity','1',str(1-min(1,max(0,entry.amount or .5))))
            else:prop('ppt_w',*values('0','#ppt_w'));prop('ppt_h',*values('0','#ppt_h'))
        if entry.paragraph>=0:
            for target in effect_node.findall('.//p:cBhvr/p:tgtEl/p:spTgt',NS):
                text=OxmlElement('p:txEl');paragraph=OxmlElement('p:pRg');paragraph.set('st',str(entry.paragraph));paragraph.set('end',str(entry.paragraph));text.append(paragraph);target.append(text)
        entry=copy.copy(entry);entry.source=effect_node.get('id');etree.SubElement(metadata,'{'+FC+'}effect',**{k:str(v) for k,v in asdict(entry).items()})


def save_sequence(slide,entries,original):
    """Edit imported timing in place; replace only intentionally changed effect graphs."""
    for entry in entries:entry.validate()
    # Work on a detached slide: a validation error must never leave partial edits.
    clone=copy.deepcopy(slide._element);working=type(slide)(clone,slide.part)
    owned={entry.source for entry in own_effects(slide)};native={entry.source:entry for entry in original if entry.source and entry.source not in owned}
    desired={entry.source:entry for entry in entries if entry.source in native}
    local=[copy.copy(entry) for entry in entries if entry.source not in native]
    structural=('shape','effect','phase','start','trigger','direction','path','paragraph')
    surviving={entry.source for entry in entries if entry.source}
    old_order=[entry.source for entry in original if entry.source in surviving]
    new_order=[entry.source for entry in entries if entry.source in native or entry.source in owned]
    rebuild=old_order!=new_order or any(any(getattr(native[key],field)!=getattr(value,field) for field in structural) or value.amount!=native[key].amount and value.effect!='Spin' for key,value in desired.items())
    last_native=max((i for i,entry in enumerate(entries) if entry.source in native),default=-1)
    if any(not entry.source and i<last_native for i,entry in enumerate(entries)):rebuild=True
    if rebuild:
        if any(entry.native_preset and entry.source in native and entry.effect==native[entry.source].effect for entry in entries):raise ValueError('Unsupported native effects must keep their order and type. You can edit their timing or explicitly replace them with a supported effect.')
        local=[copy.copy(entry) for entry in entries]
        for entry in local:entry.source='';entry.native_preset=''
    for identifier,before in native.items():
        node=next((n for n in working._element.findall('.//p:cTn',NS) if n.get('id')==identifier),None)
        if node is None:raise ValueError('The imported timeline changed. Reopen the animation pane.')
        after=desired.get(identifier)
        if after==before and not rebuild:continue
        replace=rebuild or after is None or any(getattr(before,key)!=getattr(after,key) for key in structural)
        if after is not None and after.amount!=before.amount and after.effect!='Spin':replace=True
        if replace:
            if after is not None and before.native_preset and after.effect==before.effect:
                raise ValueError('This native effect is unsupported. Edit its timing or explicitly choose another effect to replace it.')
            parent=node.getparent();container=parent.getparent();container.remove(parent)
            while not len(container) and container.tag=='{'+P+'}childTnLst':
                clock=container.getparent();wrapper=clock.getparent()
                if clock.get('nodeType')=='tmRoot':break
                outer=wrapper.getparent()
                if outer is None or outer.tag!='{'+P+'}childTnLst':break
                outer.remove(wrapper);container=outer
            if after is not None and not rebuild:
                entry=copy.copy(after);entry.source='';entry.native_preset='';local.append(entry)
            continue
        node.set('repeatCount','indefinite' if after.repeat==-1 else str(after.repeat*1000))
        node.set('autoRev','1' if after.autoreverse else '0');node.set('fill','remove' if after.rewind else 'hold')
        for key,value in [('accel',after.accel),('decel',after.decel),('bounceEnd',after.bounce)]:node.set(key,str(round(value*100000)))
        for clock in node.findall('.//p:cBhvr/p:cTn',NS):
            raw=clock.get('dur','')
            if raw.isdigit() and int(raw)>1:clock.set('dur',str(max(1,round(int(raw)*after.duration/before.duration))))
        if after.delay!=before.delay:
            condition=node.find('p:stCondLst/p:cond',NS)
            if condition is None:
                listing=OxmlElement('p:stCondLst');node.insert(0,listing);condition=OxmlElement('p:cond');listing.append(condition)
            condition.set('delay',str(round(after.delay*1000)))
        if after.amount!=before.amount:
            for rotation in node.findall('.//p:animRot',NS):rotation.set('by',str(round((after.amount or 360)*60000)))
    write_timeline(working,local)
    # Replace timing and extensions only; cached shapes must retain their XML objects.
    for name in ('timing','extLst'):
        old=slide._element.find('p:'+name,NS);new=working._element.find('p:'+name,NS)
        if old is not None:slide._element.remove(old)
        if new is not None:
            following=slide._element.find('p:extLst',NS) if name=='timing' else None
            slide._element.insert(list(slide._element).index(following) if following is not None else len(slide._element),new)


class TimelinePlayer(QObject):
    def __init__(self,view,slide,autoplay=True):
        super().__init__(view);self.view=view;self.groups=[];self.pending=[];self.triggered={};self.trigger_cursor={};self.trigger_group={};self.running=[]
        self.items={item.native_shape.shape_id:item for item in view.scene().items() if hasattr(item,'native_shape') and item.native_shape.part is slide.part}
        from PySide6.QtGui import QTransform
        self.base={sid:(QPointF(item.pos()),item.scale(),item.rotation()) for sid,item in self.items.items()};self.transforms={sid:QTransform(item.transform()) for sid,item in self.items.items()};self.automatic=[];self.states={}
        entries=timeline(slide);first=set()
        for entry in entries:
            if entry.shape not in self.items:continue
            if entry.shape not in first:
                first.add(entry.shape)
                if entry.phase=='Entrance':self.items[entry.shape].setOpacity(0)
        batches=[];current=[]
        for entry in entries:
            if entry.trigger:
                batches_for_shape=self.triggered.setdefault(entry.trigger,[])
                if entry.start=='On click' or not batches_for_shape:batches_for_shape.append([])
                batches_for_shape[-1].append(entry);continue
            if entry.start=='On click' and current:batches.append(current);current=[]
            current.append(entry)
        if current:batches.append(current)
        for batch in batches:
            group=self.compile(batch);self.groups.append(group)
            if batch[0].start=='On click':self.pending.append(group)
            else:self.automatic.append(group)
        if autoplay:self.start_auto()

    def start_auto(self):
        for group in self.automatic:self.start(group)
        self.automatic=[]

    def play_all(self):
        sequence=QSequentialAnimationGroup(self);sequence.entries=[]
        while self.pending:
            group=self.pending.pop(0);sequence.addAnimation(QPauseAnimation(300));sequence.addAnimation(group);sequence.entries.extend(group.entries)
        if sequence.animationCount():self.start(sequence)

    def compile(self,entries):
        parallel=QParallelAnimationGroup(self);parallel.entries=[];previous_start=previous_end=0
        for entry in entries:
            if entry.shape not in self.items:continue
            if entry.start=='After previous' and previous_end is None:continue
            offset=previous_start if entry.start=='With previous' else previous_end if entry.start=='After previous' else 0
            offset+=round(entry.delay*1000);sequence=QSequentialAnimationGroup(parallel)
            if offset:sequence.addAnimation(QPauseAnimation(offset))
            animation=QVariantAnimation(sequence);animation.setStartValue(0.0);animation.setEndValue(1.0);animation.setDuration(round(entry.duration*1000)*(2 if entry.autoreverse else 1));animation.setLoopCount(entry.repeat)
            animation.valueChanged.connect(lambda value,e=entry:self.apply(e,(2*float(value) if float(value)<.5 else 2*(1-float(value))) if e.autoreverse else float(value)));animation.finished.connect(lambda e=entry:self.apply(e,0.0 if e.autoreverse or e.rewind else 1.0));sequence.addAnimation(animation);parallel.addAnimation(sequence)
            parallel.entries.append(entry);previous_start=offset;previous_end=None if entry.repeat==-1 else offset+animation.duration()*entry.repeat
        return parallel

    def apply(self,entry,t):
        from PySide6.QtGui import QTransform
        t=ease(t,entry.accel,entry.decel,entry.bounce);item=self.items[entry.shape];position,scale,rotation=self.base[entry.shape];bounds=self.view.sceneRect();rect=item.boundingRect()
        amount=entry.amount or (360 if entry.effect=='Spin' else .5 if entry.effect=='Transparency' else 1.5)
        state=sample(entry.effect,entry.phase,t,entry.direction,bounds.width(),bounds.height(),amount,(position.x(),position.y(),rect.width(),rect.height()))
        if entry.effect in ('Circle','Diamond'):state['clip']=None
        if entry.effect=='Motion path':
            path=motion_path(entry.path);point=path.pointAtPercent(t)-path.pointAtPercent(0);state['x']=point.x()*bounds.width();state['y']=point.y()*bounds.height()
        if entry.phase=='Exit' and t>=1:state['opacity']=0.
        if entry.phase=='Entrance' and t<=0:
            for key,(old,_) in list(self.states.items()):
                if old.shape==entry.shape and old.phase=='Exit':self.states.pop(key)
        self.states[id(entry)]=(entry,state)
        total=dict(opacity=1.,x=0.,y=0.,sx=1.,sy=1.,rotation=0.,clip=None)
        for old,current in self.states.values():
            if old.shape!=entry.shape:continue
            for key in ('opacity','sx','sy'):total[key]*=current[key]
            for key in ('x','y','rotation'):total[key]+=current[key]
            if current['clip'] is not None:
                before=total['clip'] or (0.,0.,1.,1.);after=current['clip'];total['clip']=(max(before[0],after[0]),max(before[1],after[1]),min(before[2],after[2]),min(before[3],after[3]))
        state['mask_progress']=1-t if entry.phase=='Exit' else t
        item.animation_masks=[(old.effect,current.get('mask_progress',1)) for old,current in self.states.values() if old.shape==entry.shape and old.effect in ('Circle','Diamond')]
        item.setOpacity(max(0,min(1,total['opacity'])));item.setPos(position+QPointF(total['x'],total['y']));item.setRotation(rotation+total['rotation']);item.setScale(scale)
        matrix=QTransform();center=rect.center();matrix.translate(center.x(),center.y());matrix.scale(total['sx'],total['sy']);matrix.translate(-center.x(),-center.y());item.setTransform(self.transforms[entry.shape]*matrix);item.animation_clip=total['clip'];item.reveal=(1.,'Left');item.setFlag(item.GraphicsItemFlag.ItemClipsToShape,True);item.setFlag(item.GraphicsItemFlag.ItemClipsChildrenToShape,True);item.update()

    def start(self,group):self.running.append(group);group.start()
    def advance(self):
        if any(group.state()==group.State.Running for group in self.running):
            for group in self.running:
                if group.state()==group.State.Running:
                    if group.totalDuration()<0:
                        group.stop()
                        for entry in group.entries:self.apply(entry,0 if entry.rewind or entry.autoreverse else 1)
                    else:group.setCurrentTime(group.totalDuration())
            return True
        if not self.pending:return False
        self.start(self.pending.pop(0));return True
    def trigger(self,shape):
        batches=self.triggered.get(shape,[])
        if not batches:return False
        active=self.trigger_group.get(shape)
        if active is not None and active.state()==active.State.Running:
            if active.totalDuration()<0:
                active.stop()
                for entry in active.entries:self.apply(entry,1)
            else:active.setCurrentTime(active.totalDuration())
            return True
        cursor=self.trigger_cursor.get(shape,0);group=self.compile(batches[cursor%len(batches)])
        self.trigger_cursor[shape]=cursor+1;self.trigger_group[shape]=group;self.start(group);return True
    def stop(self):
        for group in self.groups+self.running:group.stop()


def animation_pane(editor):
    from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QListWidget,
        QComboBox,QDoubleSpinBox,QSpinBox,QLineEdit,QPushButton,QLabel,QDialogButtonBox,QMessageBox,QWidget,QScrollArea,QCheckBox,QGraphicsView,QGraphicsScene)
    slide=editor.deck.slides[editor.index];original=copy.deepcopy(timeline(slide));entries=copy.deepcopy(original)
    dialog=QDialog(editor);dialog.setWindowTitle('Animation pane');dialog.resize(840,600);layout=QVBoxLayout(dialog)
    notice=QLabel('Timing edits keep imported effect graphs. Changing types or order rebuilds supported effects. Unsupported effects can keep their timing or be explicitly replaced.');notice.setWordWrap(True);layout.addWidget(notice)
    listing=QListWidget();listing.setMaximumHeight(110);listing.setAccessibleName('Animation order');layout.addWidget(listing)
    graph=QGraphicsView();graph.setAccessibleName('Animation timing bars');graph.setMinimumHeight(90);graph.setMaximumHeight(130);layout.addWidget(graph);graph_scene=QGraphicsScene(graph);graph.setScene(graph_scene)
    form_widget=QWidget();form=QFormLayout(form_widget);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(form_widget);layout.addWidget(scroll,1)
    shapes=slide_shapes(slide);target=QComboBox();trigger=QComboBox();trigger.addItem('Slide / keyboard click',0)
    for sid,shape in shapes.items():target.addItem(shape.name,sid);trigger.addItem(shape.name,sid)
    selected=editor.selected_shape()
    if selected is not None:target.setCurrentIndex(max(0,target.findData(selected.shape_id)))
    effect=QComboBox();effect.addItems(EFFECTS);phase=QComboBox();phase.addItems(PHASES);start=QComboBox();start.addItems(STARTS);direction=QComboBox();direction.addItems(['Left','Right','Up','Down'])
    duration=QDoubleSpinBox();duration.setRange(.05,120);duration.setValue(.6);duration.setSuffix(' s');delay=QDoubleSpinBox();delay.setRange(0,120);delay.setSuffix(' s');repeat=QSpinBox();repeat.setRange(0,100);repeat.setSpecialValueText('Indefinite');repeat.setValue(1);path=QLineEdit('M 0 0 L 0.25 0 E')
    accel=QDoubleSpinBox();decel=QDoubleSpinBox();bounce=QDoubleSpinBox()
    for field in (accel,decel,bounce):field.setRange(0,100);field.setSuffix(' %')
    paragraph=QSpinBox();paragraph.setRange(-1,10000);paragraph.setSpecialValueText('Whole object');paragraph.setValue(-1);paragraph.setToolTip('Zero-based native paragraph target; preserved in PPTX. Paragraph-only playback is not yet supported.')
    amount=QDoubleSpinBox();amount.setRange(-36000,36000);amount.setDecimals(2);amount.setToolTip('0 uses the default: spin 360 degrees, grow 1.5×, transparency 50%.')
    reverse=QCheckBox('Auto-reverse');rewind=QCheckBox('Restore previous state when finished')
    for label,widget in [('Object',target),('Effect',effect),('Phase',phase),('Start',start),('Duration',duration),('Delay',delay),('Repeat',repeat),('Direction',direction),('Trigger',trigger),('Motion path',path)]:widget.setAccessibleName(label);form.addRow(label,widget)
    for label,widget in [('Smooth start',accel),('Smooth end',decel),('Bounce end',bounce),('Amount (0 = default)',amount),('Reverse',reverse),('Rewind',rewind),('Paragraph target',paragraph)]:widget.setAccessibleName(label);form.addRow(label,widget)
    effect.currentTextChanged.connect(lambda name:phase.setCurrentText('Emphasis' if name in EMPHASIS or name=='Motion path' else 'Entrance'))
    def refresh(row=None):
        listing.clear();listing.addItems([f'{i+1}. {shapes[e.shape].name if e.shape in shapes else "Missing object"} · {"Native preset "+e.native_preset if e.native_preset else e.effect} · {e.phase} · {e.start} · {e.duration:g}s'+(' · repeat indefinitely' if e.repeat==-1 else '') for i,e in enumerate(entries)])
        from PySide6.QtGui import QColor,QPen
        graph_scene.clear();previous_start=previous_end=0.;click=0
        for i,e in enumerate(entries):
            if e.start=='On click':click+=1;offset=0.
            else:offset=previous_start if e.start=='With previous' else previous_end
            offset+=e.delay;span=e.duration*(e.repeat if e.repeat>0 else 3)*(2 if e.autoreverse else 1);color={'Entrance':'#42b89a','Emphasis':'#ffdd22','Exit':'#e47b86'}[e.phase]
            graph_scene.addText(f'{i+1} · click {click}').setPos(0,i*27);graph_scene.addRect(120+offset*70,i*27+4,max(2,span*70),18,QPen(QColor(color)),QColor(color));previous_start=offset;previous_end=offset+span
        graph_scene.setSceneRect(graph_scene.itemsBoundingRect().adjusted(0,0,20,10))
        if row is not None:listing.setCurrentRow(row)
    def choose(row):
        if not 0<=row<len(entries):return
        e=entries[row];target.setCurrentIndex(target.findData(e.shape));effect.setCurrentText(e.effect);phase.setCurrentText(e.phase);start.setCurrentText(e.start);duration.setValue(e.duration);delay.setValue(e.delay);repeat.setValue(max(0,e.repeat));direction.setCurrentText(e.direction);trigger.setCurrentIndex(max(0,trigger.findData(e.trigger)));path.setText(e.path)
        accel.setValue(e.accel*100);decel.setValue(e.decel*100);bounce.setValue(e.bounce*100);amount.setValue(e.amount);reverse.setChecked(e.autoreverse);rewind.setChecked(e.rewind);paragraph.setValue(e.paragraph)
    listing.currentRowChanged.connect(choose)
    def store(replace=False):
        try:
            entry=Effect(int(target.currentData()),effect.currentText(),phase.currentText(),start.currentText(),duration.value(),delay.value(),repeat.value() or -1,direction.currentText(),int(trigger.currentData()),path.text()).validate()
            entry.accel=accel.value()/100;entry.decel=decel.value()/100;entry.bounce=bounce.value()/100;entry.amount=amount.value();entry.autoreverse=reverse.isChecked();entry.rewind=rewind.isChecked();entry.paragraph=paragraph.value();entry.validate()
            row=listing.currentRow()
            if replace and row>=0:entry.source=entries[row].source;entry.native_preset=entries[row].native_preset;entries[row]=entry
            else:entries.append(entry);row=len(entries)-1
            refresh(row)
        except (ValueError,TypeError) as error:QMessageBox.warning(dialog,'Animation',str(error))
    def remove():
        row=listing.currentRow()
        if row>=0:entries.pop(row);refresh(min(row,len(entries)-1))
    def move(delta):
        row=listing.currentRow();other=row+delta
        if 0<=row<len(entries) and 0<=other<len(entries):entries[row],entries[other]=entries[other],entries[row];refresh(other)
    row=QHBoxLayout();layout.addLayout(row)
    for label,callback in [('Add effect',lambda:store()),('Update effect',lambda:store(True)),('Remove',remove),('Move up',lambda:move(-1)),('Move down',lambda:move(1))]:
        button=QPushButton(label);button.clicked.connect(callback);row.addWidget(button)
    def save():
        try:editor.change(lambda:save_sequence(slide,entries,original))
        except (ValueError,TypeError) as error:QMessageBox.warning(dialog,'Animation',str(error));return
        dialog.accept()
    buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(save);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons);refresh();dialog.exec()
