"""DrawingML guide/path evaluation; preset data is Apache POI licensed material."""
import math
from functools import lru_cache
from pathlib import Path
from lxml import etree
from PySide6.QtCore import QRectF,QPointF
from PySide6.QtGui import QPainterPath

A='http://schemas.openxmlformats.org/drawingml/2006/main'
def child(node,name):return node.find('{'+A+'}'+name) if node is not None else None


@lru_cache(maxsize=1)
def presets():
    return {node.tag:node for node in etree.parse(str(Path(__file__).resolve().parent/'assets/presetShapeDefinitions.xml')).getroot()}


def paths(properties,rect):
    preset=child(properties,'prstGeom');geometry=child(properties,'custGeom')
    if geometry is None:
        geometry=presets().get(preset.get('prst','rect') if preset is not None else 'rect')
    if geometry is None:return []
    width=max(1,rect.width()*12700);height=max(1,rect.height()*12700)
    values=dict(w=width,h=height,l=0.,t=0.,r=width,b=height,hc=width/2,vc=height/2,ss=min(width,height),ls=max(width,height),cd2=10800000.,cd4=5400000.,cd8=2700000.)
    for n in range(2,33):
        values['wd'+str(n)]=width/n;values['hd'+str(n)]=height/n;values['ssd'+str(n)]=min(width,height)/n
    for multiplier in range(1,8):values[str(multiplier)+'cd4']=21600000*multiplier/4;values[str(multiplier)+'cd8']=21600000*multiplier/8
    def value(token):
        if token in values:return values[token]
        try:return float(token)
        except (TypeError,ValueError):return 0.
    def formula(expression):
        parts=expression.split();op=parts[0];args=[value(v) for v in parts[1:]];a,b,c=(args+[0.,0.,0.])[:3]
        if op=='val':result=a
        elif op=='*/':result=a*b/c if c else 0
        elif op=='+-':result=a+b-c
        elif op=='+/':result=(a+b)/c if c else 0
        elif op=='?:':result=b if a>0 else c
        elif op=='abs':result=abs(a)
        elif op=='sqrt':result=math.sqrt(max(0,a))
        elif op=='max':result=max(a,b)
        elif op=='min':result=min(a,b)
        elif op=='pin':result=max(a,min(b,c))
        elif op=='mod':result=math.sqrt(a*a+b*b+c*c)
        elif op=='at2':result=math.degrees(math.atan2(b,a))*60000
        elif op=='cat2':result=a*math.cos(math.atan2(c,b))
        elif op=='sat2':result=a*math.sin(math.atan2(c,b))
        elif op in ('cos','sin','tan'):result=a*getattr(math,op)(math.radians(b/60000))
        else:result=0
        return max(-1e12,min(1e12,result)) if math.isfinite(result) else 0.
    def guides(parent):
        if parent is not None:
            for node in parent:values[node.get('name')]=formula(node.get('fmla','val 0'))
    guides(child(geometry,'avLst'))
    if preset is not None:guides(child(preset,'avLst'))
    guides(child(geometry,'gdLst'));result=[];path_list=child(geometry,'pathLst')
    for node in path_list if path_list is not None else []:
        sx=rect.width()/max(1,value(node.get('w',str(width))));sy=rect.height()/max(1,value(node.get('h',str(height))))
        def point(n):return QPointF(rect.x()+value(n.get('x','0'))*sx,rect.y()+value(n.get('y','0'))*sy)
        path=QPainterPath()
        for command in node:
            tag=etree.QName(command).localname
            if tag=='moveTo':path.moveTo(point(command[0]))
            elif tag=='lnTo':path.lineTo(point(command[0]))
            elif tag=='cubicBezTo':path.cubicTo(*(point(n) for n in command))
            elif tag=='quadBezTo':path.quadTo(*(point(n) for n in command))
            elif tag=='close':path.closeSubpath()
            elif tag=='arcTo':
                rx=abs(value(command.get('wR','0'))*sx);ry=abs(value(command.get('hR','0'))*sy);start=value(command.get('stAng','0'))/60000;sweep=value(command.get('swAng','0'))/60000
                current=path.currentPosition();cx=current.x()-rx*math.cos(math.radians(start));cy=current.y()-ry*math.sin(math.radians(start))
                path.arcTo(QRectF(cx-rx,cy-ry,2*rx,2*ry),-start,-sweep)
        result.append((path,node.get('fill','norm'),node.get('stroke','1') not in ('0','false')))
    return result
