"""Read-only DrawingML styles and cached SmartArt drawings for the native canvas."""
from __future__ import annotations

import colorsys
import copy
import html
import math
from types import SimpleNamespace

from lxml import etree
from pptx.shapes.shapetree import SlideShapeFactory
from pptx.oxml import parse_xml
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QImage, QLinearGradient, QPainter,
                          QPainterPath, QPen, QPolygonF, QTextDocument)

A='http://schemas.openxmlformats.org/drawingml/2006/main'
P='http://schemas.openxmlformats.org/presentationml/2006/main'
D='http://schemas.microsoft.com/office/drawing/2008/diagram'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
EMU=12700


def child(element,name):
    return element.find('{'+A+'}'+name) if element is not None else None


def number(element,key,default=0):
    try:return float(element.get(key,default)) if element is not None else default
    except (ValueError,TypeError):return default


class SlideTheme:
    def __init__(self,slide):
        self.slide=slide
        self.master=slide.slide_layout.slide_master
        self.colors={'dk1':'000000','lt1':'FFFFFF','dk2':'1F497D','lt2':'EEECE1',
                     'accent1':'4F81BD','accent2':'C0504D','accent3':'9BBB59',
                     'accent4':'8064A2','accent5':'4BACC6','accent6':'F79646',
                     'hlink':'0000FF','folHlink':'800080'}
        self.mapping=dict(bg1='lt1',tx1='dk1',bg2='lt2',tx2='dk2')
        self.root=None
        for rel in self.master.part.rels.values():
            if rel.reltype.endswith('/theme'):
                self.root=etree.fromstring(rel.target_part.blob)
                scheme=self.root.find('.//{'+A+'}clrScheme')
                if scheme is not None:
                    for node in scheme:
                        if len(node):self.colors[etree.QName(node).localname]=node[0].get('lastClr',node[0].get('val','000000'))
                break
        for element in (self.master._element,slide.slide_layout._element,slide._element):
            for node in element.iter():
                if etree.QName(node).localname in {'clrMap','overrideClrMapping'}:self.mapping.update(node.attrib)
        self.fonts={'major':'Calibri','minor':'Calibri'}
        if self.root is not None:
            for kind in self.fonts:
                node=self.root.find('.//{'+A+'}'+kind+'Font/{'+A+'}latin')
                if node is not None and node.get('typeface'):self.fonts[kind]=node.get('typeface')

    def color(self,node,fallback='#202b3d',placeholder=None):
        if node is None:return QColor(fallback)
        if etree.QName(node).localname not in {'srgbClr','schemeClr','sysClr','scrgbClr','prstClr','hslClr'}:
            node=next((n for n in node if etree.QName(n).localname.endswith('Clr')),None)
        if node is None:return QColor(fallback)
        kind=etree.QName(node).localname;value=node.get('val','')
        if kind=='schemeClr':
            value=self.colors.get(self.mapping.get(value,value),fallback.lstrip('#')) if value!='phClr' else (placeholder or fallback).lstrip('#')
            color=QColor('#'+value)
        elif kind in {'sysClr','srgbClr'}:color=QColor('#'+node.get('lastClr',value))
        elif kind=='scrgbClr':color=QColor.fromRgbF(*(max(0,min(1,number(node,k)/100000)) for k in ('r','g','b')))
        elif kind=='hslClr':color=QColor.fromHslF((number(node,'hue')/60000%360)/360,number(node,'sat')/100000,number(node,'lum')/100000)
        else:color=QColor(value)
        if not color.isValid():color=QColor(fallback)
        red,green,blue,alpha=color.getRgbF()
        for transform in node:
            key=etree.QName(transform).localname;v=number(transform,'val')/100000
            if key in {'tint','shade'}:
                red,green,blue=[c*v+(1-v if key=='tint' else 0) for c in (red,green,blue)]
            elif key in {'lumMod','lumOff','satMod','satOff','hueMod','hueOff'}:
                h,l,s=colorsys.rgb_to_hls(red,green,blue)
                if key=='lumMod':l*=v
                elif key=='lumOff':l+=v
                elif key=='satMod':s*=v
                elif key=='satOff':s+=v
                elif key=='hueMod':h*=v
                else:h+=number(transform,'val')/60000/360
                red,green,blue=colorsys.hls_to_rgb(h%1,max(0,min(1,l)),max(0,min(1,s)))
            elif key=='alpha':alpha=v
            elif key=='alphaMod':alpha*=v
            elif key=='alphaOff':alpha+=v
        return QColor.fromRgbF(*(max(0,min(1,c)) for c in (red,green,blue,alpha)))

    def brush(self,properties,rect,style=None):
        if properties is not None and child(properties,'noFill') is not None:return QBrush(Qt.NoBrush)
        fill=next((child(properties,k) for k in ('solidFill','gradFill') if child(properties,k) is not None),None)
        placeholder=None
        if fill is None and style is not None:
            ref=child(style,'fillRef');index=int(number(ref,'idx'))
            if index and self.root is not None:
                placeholder=self.color(ref).name()
                collection=self.root.find('.//{'+A+'}'+('bgFillStyleLst' if index>=1001 else 'fillStyleLst'))
                index=index-1001 if index>=1001 else index-1
                if collection is not None and 0<=index<len(collection):fill=collection[index]
        if fill is None:return QBrush(Qt.NoBrush)
        if etree.QName(fill).localname=='solidFill':return QBrush(self.color(fill,placeholder=placeholder))
        stops=child(fill,'gsLst');angle=math.radians(number(child(fill,'lin'),'ang')/60000)
        dx,dy=math.cos(angle),math.sin(angle);length=abs(rect.width()*dx)+abs(rect.height()*dy)
        center=rect.center();gradient=QLinearGradient(center-QPointF(dx*length/2,dy*length/2),center+QPointF(dx*length/2,dy*length/2))
        for stop in stops if stops is not None else []:gradient.setColorAt(max(0,min(1,number(stop,'pos')/100000)),self.color(stop,placeholder=placeholder))
        return QBrush(gradient)

    def text_style(self,shape=None,element=None,level=0):
        result={'size':18.,'family':self.fonts['minor'],'color':'#202b3d'}
        role='otherStyle'
        chain=[]
        if shape is not None and shape.is_placeholder:
            kind=str(shape.placeholder_format.type)
            role='titleStyle' if 'TITLE' in kind else 'bodyStyle'
            index=shape.placeholder_format.idx
            layout=next((s for s in self.slide.slide_layout.placeholders if s.placeholder_format.idx==index),None)
            if layout is not None:chain.append(layout._element)
        base=self.master._element.find('.//{'+P+'}'+role+'/{'+A+'}lvl'+str(min(9,level+1))+'pPr')
        if base is not None:result.update(self.font_properties(child(base,'defRPr')))
        for node in chain+[element if element is not None else shape._element if shape is not None else None]:
            if node is None:continue
            style=next((n for n in node if etree.QName(n).localname=='style'),None)
            ref=child(style,'fontRef')
            if ref is not None:
                result['family']=self.fonts.get(ref.get('idx'),self.fonts['minor'])
                if len(ref):result['color']=self.color(ref).name()
            body=next((n for n in node if etree.QName(n).localname=='txBody'),None)
            ppr=child(child(body,'lstStyle'),'lvl'+str(min(9,level+1))+'pPr')
            result.update(self.font_properties(child(ppr,'defRPr')))
        return result

    def font_properties(self,node):
        if node is None:return {}
        result={}
        for key,target in (('b','bold'),('i','italic')):
            if node.get(key) is not None:result[target]=node.get(key) in {'1','true'}
        if node.get('u') is not None:result['underline']=node.get('u')!='none'
        if node.get('cap'):result['caps']=node.get('cap')
        highlight=child(node,'highlight')
        if highlight is not None:result['highlight']=self.color(highlight).name()
        if node.get('sz'):result['size']=number(node,'sz')/100
        latin=child(node,'latin')
        if latin is not None:
            family=latin.get('typeface','')
            result['family']=self.fonts['major' if family.startswith('+mj') else 'minor'] if family.startswith('+') else family
        fill=child(node,'solidFill')
        if fill is not None:result['color']=self.color(fill).name()
        return result


def text_html(shape,theme,element=None):
    element=element if element is not None else shape._element
    body=next((n for n in element if etree.QName(n).localname=='txBody'),None)
    if body is None:return ''
    blocks=[];counters={}
    autofit=child(child(body,'bodyPr'),'normAutofit');font_scale=number(autofit,'fontScale',100000)/100000
    for paragraph in body.findall('{'+A+'}p'):
        ppr=child(paragraph,'pPr');level=int(number(ppr,'lvl'))
        base=theme.text_style(shape,element,level);base.update(theme.font_properties(child(ppr,'defRPr')))
        pieces=[]
        if ppr is not None and child(ppr,'buChar') is not None:pieces.append(html.escape(child(ppr,'buChar').get('char','•'))+' ')
        elif ppr is not None and child(ppr,'buAutoNum') is not None:
            counters[level]=counters.get(level,int(number(child(ppr,'buAutoNum'),'startAt',1))-1)+1;pieces.append(str(counters[level])+'. ')
        for run in paragraph:
            tag=etree.QName(run).localname
            if tag=='br':pieces.append('<br>');continue
            if tag not in {'r','fld'}:continue
            style=dict(base);style.update(theme.font_properties(child(run,'rPr')))
            css=f'font-family:&quot;{html.escape(style["family"],quote=True)}&quot;;font-size:{style["size"]*font_scale}px;color:{style["color"]};'
            if style.get('bold'):css+='font-weight:bold;'
            if style.get('italic'):css+='font-style:italic;'
            if style.get('underline'):css+='text-decoration:underline;'
            if style.get('highlight'):css+='background-color:'+style['highlight']+';'
            if style.get('caps')=='all':css+='text-transform:uppercase;'
            pieces.append('<span style="'+css+'">'+html.escape((''.join(n.text or '' for n in run.findall('{'+A+'}t'))).upper() if style.get('caps')=='all' else ''.join(n.text or '' for n in run.findall('{'+A+'}t'))).replace('\v','<br>')+'</span>')
        align={'ctr':'center','r':'right','just':'justify'}.get(ppr.get('algn') if ppr is not None else '', 'left')
        margin=max(0,number(ppr,'marL')/EMU)
        before=number(child(child(ppr,'spcBef'),'spcPts'),'val')/100;after=number(child(child(ppr,'spcAft'),'spcPts'),'val')/100
        spacing=child(ppr,'lnSpc');percent=child(spacing,'spcPct');points=child(spacing,'spcPts')
        line=f'line-height:{number(percent,"val")/1000}%;' if percent is not None else f'line-height:{number(points,"val")/100}px;' if points is not None else ''
        blocks.append(f'<p style="margin:{before}px 0 {after}px {margin}px;text-align:{align};{line}">'+(''.join(pieces) or '<br>')+'</p>')
    return ''.join(blocks)


def paint_text(painter,shape,theme,rect,element=None):
    element=element if element is not None else shape._element
    body=next((n for n in element if etree.QName(n).localname=='txBody'),None)
    if body is None:return
    properties=copy.deepcopy(child(body,'bodyPr'))
    if shape.is_placeholder:
        index=shape.placeholder_format.idx
        layout=next((s for s in theme.slide.slide_layout.placeholders if s.placeholder_format.idx==index),None)
        inherited=child(layout._element.find('{'+P+'}txBody'),'bodyPr') if layout is not None else None
        if properties is not None and inherited is not None:
            for key,value in inherited.attrib.items():
                if properties.get(key) is None:properties.set(key,value)
    left=number(properties,'lIns',91440)/EMU;right=number(properties,'rIns',91440)/EMU
    top=number(properties,'tIns',45720)/EMU;bottom=number(properties,'bIns',45720)/EMU
    content=rect.adjusted(left,top,-right,-bottom)
    from PySide6.QtCore import QSizeF
    from PySide6.QtGui import QTextCursor,QTextOption
    import re
    columns=max(1,min(8,int(number(properties,'numCol',1))));gap=max(0,number(properties,'spcCol')/EMU);column_width=max(1,(content.width()-gap*(columns-1))/columns)
    doc=QTextDocument();doc.setDocumentMargin(0);markup=text_html(shape,theme,element);doc.setHtml(markup);doc.setTextWidth(column_width)
    option=doc.defaultTextOption()
    if properties is not None and properties.get('wrap')=='none':option.setWrapMode(QTextOption.NoWrap)
    doc.setDefaultTextOption(option)
    fit=child(properties,'normAutofit')
    if fit is not None and fit.get('fontScale') is None and content.height()>0 and doc.size().height()>content.height()*columns:
        low,high=.05,1.
        for _ in range(8):
            scale=(low+high)/2;doc.setHtml(re.sub(r'font-size:([\d.]+)px',lambda match:'font-size:'+str(float(match.group(1))*scale)+'px',markup));doc.setTextWidth(column_width)
            if doc.size().height()>content.height()*columns:high=scale
            else:low=scale
        doc.setHtml(re.sub(r'font-size:([\d.]+)px',lambda match:'font-size:'+str(float(match.group(1))*low)+'px',markup));doc.setTextWidth(column_width)
    block=doc.begin()
    for paragraph in body.findall('{'+A+'}p'):
        if not block.isValid():break
        ppr=child(paragraph,'pPr');tabs=child(ppr,'tabLst')
        if tabs is not None:
            fmt=block.blockFormat();positions=[]
            for node in tabs:
                tab=QTextOption.Tab();tab.position=number(node,'pos')/EMU;tab.type=QTextOption.LeftTab;positions.append(tab)
            fmt.setTabPositions(positions);cursor=QTextCursor(block);cursor.setBlockFormat(fmt)
        block=block.next()
    if columns>1:
        if content.height()<=0:return
        doc.setPageSize(QSizeF(column_width,content.height()))
        for column in range(columns):
            target=QRectF(content.x()+column*(column_width+gap),content.y(),column_width,content.height())
            painter.save();painter.setClipRect(target);painter.translate(target.x(),target.y()-column*content.height());doc.drawContents(painter);painter.restore()
        return
    free=content.height()-doc.size().height();anchor=properties.get('anchor','t') if properties is not None else 't'
    offset=free/2 if anchor=='ctr' else free if anchor=='b' else 0
    painter.save();painter.translate(content.left(),content.top()+offset);doc.drawContents(painter);painter.restore()


def properties(element):
    return next((n for n in element if etree.QName(n).localname in {'spPr','grpSpPr'}),None)


def geometry_path(props,rect):
    from preset_geometry import paths
    resolved=paths(props,rect)
    if resolved:
        result=QPainterPath()
        for path,_,_ in resolved:result.addPath(path)
        return result
    custom=child(props,'custGeom');result=QPainterPath()
    if custom is None:
        preset=child(props,'prstGeom');kind=preset.get('prst','rect') if preset is not None else 'rect'
        if kind=='ellipse':result.addEllipse(rect)
        elif kind in {'roundRect','round2SameRect','round1Rect'}:result.addRoundedRect(rect,min(rect.width(),rect.height())*.12,min(rect.width(),rect.height())*.12)
        elif kind=='line':result.moveTo(rect.topLeft());result.lineTo(rect.bottomRight())
        elif kind=='rightArrow':
            w,h=rect.width(),rect.height();points=[(0,h*.25),(w*.65,h*.25),(w*.65,0),(w,h*.5),(w*.65,h),(w*.65,h*.75),(0,h*.75)]
            result.moveTo(*points[0])
            for point in points[1:]:result.lineTo(*point)
            result.closeSubpath()
        elif kind=='star5':
            w,h=rect.width(),rect.height()
            for i in range(10):
                angle=-math.pi/2+i*math.pi/5;r=1 if i%2==0 else .45;point=QPointF(w/2+math.cos(angle)*w/2*r,h/2+math.sin(angle)*h/2*r)
                if i:result.lineTo(point)
                else:result.moveTo(point)
            result.closeSubpath()
        elif kind in {'triangle','rtTriangle'}:result.moveTo(rect.center().x(),rect.top());result.lineTo(rect.bottomRight());result.lineTo(rect.bottomLeft());result.closeSubpath()
        else:result.addRect(rect)
        return result
    paths=child(custom,'pathLst')
    for path in paths if paths is not None else []:
        sx=rect.width()/number(path,'w',rect.width()*EMU);sy=rect.height()/number(path,'h',rect.height()*EMU)
        def point(n):return QPointF(number(n,'x')*sx,number(n,'y')*sy)
        for command in path:
            kind=etree.QName(command).localname
            if kind=='moveTo':result.moveTo(point(command[0]))
            elif kind=='lnTo':result.lineTo(point(command[0]))
            elif kind=='cubicBezTo':result.cubicTo(*(point(n) for n in command))
            elif kind=='quadBezTo':result.quadTo(*(point(n) for n in command))
            elif kind=='close':result.closeSubpath()
    return result


def paint_geometry(painter,element,theme,rect,draw_default=True):
    props=properties(element);style=next((n for n in element if etree.QName(n).localname=='style'),None)
    brush=theme.brush(props,rect,style);line=child(props,'ln')
    if line is None and style is not None and theme.root is not None:
        ref=child(style,'lnRef');index=int(number(ref,'idx'))-1
        lines=theme.root.find('.//{'+A+'}lnStyleLst')
        if lines is not None and 0<=index<len(lines):line=lines[index]
    pen=QPen(Qt.NoPen)
    if line is not None and child(line,'noFill') is None:
        pen=QPen(theme.color(child(line,'solidFill'),'#202b3d'),max(.25,number(line,'w',12700)/EMU))
        dash=child(line,'prstDash')
        if dash is not None and dash.get('val')!='solid':pen.setStyle(Qt.DashLine)
    painter.save();painter.setBrush(brush);painter.setPen(pen)
    if draw_default or brush.style()!=Qt.NoBrush or line is not None:
        from preset_geometry import paths
        resolved=paths(props,rect)
        if not resolved:resolved=[(geometry_path(props,rect),'norm',True)]
        path=QPainterPath()
        for segment,fill_mode,stroke in resolved:
            painter.setPen(pen if stroke else QPen(Qt.NoPen));current=brush
            if fill_mode=='none':current=QBrush(Qt.NoBrush)
            elif brush.style()==Qt.SolidPattern and fill_mode.startswith(('darken','lighten')):
                color=brush.color();current=QBrush(color.darker(125) if fill_mode.startswith('darken') else color.lighter(125))
            painter.setBrush(current);painter.drawPath(segment);path.addPath(segment)
        if line is not None and path.elementCount()>=2:
            for key,end in (('headEnd',False),('tailEnd',True)):
                arrow=child(line,key)
                if arrow is None or arrow.get('type') in {None,'none'}:continue
                tip=path.pointAtPercent(1 if end else 0);near=path.pointAtPercent(.96 if end else .04)
                angle=math.atan2(tip.y()-near.y(),tip.x()-near.x());size=max(4,pen.widthF()*4)
                points=[tip,QPointF(tip.x()-size*math.cos(angle-.45),tip.y()-size*math.sin(angle-.45)),QPointF(tip.x()-size*math.cos(angle+.45),tip.y()-size*math.sin(angle+.45))]
                painter.setBrush(pen.color());painter.drawPolygon(QPolygonF(points))
    painter.restore()


def diagram_part(shape):
    refs=shape._element.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/diagram}relIds')
    if not refs:return None
    data=shape.part.related_part(refs[0].get('{'+R+'}dm'))
    root=etree.fromstring(data.blob)
    for node in root.iter():
        if etree.QName(node).localname=='dataModelExt':
            rid=node.get('relId')
            for part in (shape.part,data):
                if rid in part.rels and part.rels[rid].reltype.endswith('/diagramDrawing'):return part.rels[rid].target_part
    return next((r.target_part for r in shape.part.rels.values() if r.reltype.endswith('/diagramDrawing')),None)


def diagram_image(shape,theme):
    part=diagram_part(shape)
    if part is None:return None
    tree=etree.fromstring(part.blob).find('{'+D+'}spTree')
    if tree is None:return None
    width=max(1,shape.width/EMU);height=max(1,shape.height/EMU)
    scale=min(2,2000/width,2000/height)
    image=QImage(max(1,round(width*scale)),max(1,round(height*scale)),QImage.Format_ARGB32);image.fill(Qt.transparent)
    painter=QPainter(image);painter.setRenderHints(QPainter.Antialiasing|QPainter.SmoothPixmapTransform);painter.scale(scale,scale)
    # Cached drawings keep their original coordinate system when the frame is resized.
    cached_width=cached_height=1
    for element in tree:
        xf=child(properties(element),'xfrm');off=child(xf,'off');ext=child(xf,'ext')
        cached_width=max(cached_width,(number(off,'x')+number(ext,'cx'))/EMU)
        cached_height=max(cached_height,(number(off,'y')+number(ext,'cy'))/EMU)
    painter.scale(width/cached_width,height/cached_height)
    try:
        for element in tree:
            if etree.QName(element).localname!='sp':continue
            props=properties(element);xfrm=child(props,'xfrm');off=child(xfrm,'off');ext=child(xfrm,'ext')
            rect=QRectF(0,0,number(ext,'cx')/EMU,number(ext,'cy')/EMU)
            painter.save();painter.translate(number(off,'x')/EMU,number(off,'y')/EMU)
            rotation=number(xfrm,'rot')/60000
            if rotation:painter.translate(rect.center());painter.rotate(rotation);painter.translate(-rect.center())
            blip=child(child(props,'blipFill'),'blip')
            if blip is not None:
                rid=blip.get('{'+R+'}embed')
                if rid in part.rels and not part.rels[rid].is_external:
                    picture=QImage.fromData(part.related_part(rid).blob)
                    painter.drawImage(rect,picture)
            else:paint_geometry(painter,element,theme,rect)
            # Convert only the copied shape's namespace; relationships stay local.
            clone=copy.deepcopy(element)
            for node in clone.iter():
                if etree.QName(node).namespace==D:node.tag='{'+P+'}'+etree.QName(node).localname
            proxy=SlideShapeFactory(parse_xml(etree.tostring(clone)),SimpleNamespace(part=part))
            paint_text(painter,proxy,theme,rect,element)
            painter.restore()
    finally:painter.end()
    return image


def inherited_shapes(slide):
    if slide._element.get('showMasterSp')=='0':return []
    result=[]
    if slide.slide_layout._element.get('showMasterSp')!='0':result.extend(s for s in slide.slide_layout.slide_master.shapes if not s.is_placeholder)
    result.extend(s for s in slide.slide_layout.shapes if not s.is_placeholder)
    return result


def background(slide,theme):
    for root in (slide._element,slide.slide_layout._element,slide.slide_layout.slide_master._element):
        csld=root.find('{'+P+'}cSld');bg=csld.find('{'+P+'}bg') if csld is not None else None
        if bg is None:continue
        props=bg.find('{'+P+'}bgPr');solid=child(props,'solidFill')
        if solid is not None:return theme.color(solid,'#ffffff')
        ref=bg.find('{'+P+'}bgRef')
        if ref is not None:return theme.color(ref,'#ffffff')
    return QColor('#ffffff')


def background_brush(slide,theme,rect):
    for root in (slide._element,slide.slide_layout._element,slide.slide_layout.slide_master._element):
        csld=root.find('{'+P+'}cSld');bg=csld.find('{'+P+'}bg') if csld is not None else None
        if bg is None:continue
        props=bg.find('{'+P+'}bgPr')
        if props is not None:
            brush=theme.brush(props,rect)
            if brush.style()!=Qt.NoBrush:return brush
        return QBrush(background(slide,theme))
    return QBrush(QColor('#ffffff'))


def diagram_nodes(shape):
    """Editable data nodes mapped to their cached presentation shapes by model id."""
    part=diagram_part(shape)
    if part is None:return None
    refs=shape._element.find('.//{http://schemas.openxmlformats.org/drawingml/2006/diagram}relIds')
    data=shape.part.related_part(refs.get('{'+R+'}dm'))
    root=etree.fromstring(data.blob);drawing=etree.fromstring(part.blob)
    ns={'dgm':'http://schemas.openxmlformats.org/drawingml/2006/diagram'}
    nodes=[]
    for node in root.findall('.//dgm:pt',ns):
        body=node.find('dgm:t',ns)
        if body is None or not body.findall('.//{'+A+'}t'):continue
        associated={p.get('modelId') for p in root.findall('.//dgm:pt',ns) if any(n.get('presAssocID')==node.get('modelId') for n in p)}
        cached=[n for n in drawing.findall('.//{'+D+'}sp') if n.get('modelId') in associated and n.find('{'+D+'}txBody') is not None]
        if cached:nodes.append((body,cached))
    return data,root,part,drawing,nodes


def replace_diagram_node(shape,index,text):
    if not isinstance(text,str) or len(text)>10000:raise ValueError('Diagram text must be at most 10,000 characters.')
    info=diagram_nodes(shape)
    if info is None or not 0<=index<len(info[4]):raise ValueError('Choose an editable diagram node.')
    data,root,part,drawing,nodes=info;body,cached=nodes[index]
    # Keep paragraph/run formatting and diagram topology. No automatic re-layout.
    for container in [body]+cached:
        texts=container.findall('.//{'+A+'}t')
        texts[0].text=text
        for old in texts[1:]:old.text=''
    data._blob=etree.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
    part._blob=etree.tostring(drawing,xml_declaration=True,encoding='UTF-8',standalone=True)
