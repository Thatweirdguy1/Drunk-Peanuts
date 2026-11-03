"""Local slide transitions and native PPTX transition settings."""
import math
from lxml import etree
from PySide6.QtCore import QObject,QVariantAnimation,QRectF,QPointF
from PySide6.QtGui import QImage,QPainter,QTransform
from slide_rendering import P

P14='http://schemas.microsoft.com/office/powerpoint/2010/main'
P159='http://schemas.microsoft.com/office/powerpoint/2015/09/main'
MC='http://schemas.openxmlformats.org/markup-compatibility/2006'
KINDS=('None','Fade','Push','Wipe','Morph objects')


def settings(slide):
    node=slide._element.find('.//{'+P+'}transition')
    if node is None:return dict(kind='None',duration=.45,direction='Left',advance=0.)
    children=[child for child in node if etree.QName(child).localname!='extLst']
    kind=next(({'fade':'Fade','push':'Push','wipe':'Wipe','morph':'Morph objects'}.get(etree.QName(child).localname) for child in children if etree.QName(child).localname in {'fade','push','wipe','morph'}),'Fade' if children else 'None')
    duration=node.get('{'+P14+'}dur',{'slow':'1000','med':'600','fast':'350'}.get(node.get('spd'),'450'))
    direction=next(({'l':'Left','r':'Right','u':'Up','d':'Down'}.get(child.get('dir'),'Left') for child in node),'Left')
    try:return dict(kind=kind,duration=min(10,max(.05,float(duration)/1000)),direction=direction,advance=min(3600,max(0,float(node.get('advTm','0'))/1000)))
    except ValueError:return dict(kind='Fade',duration=.45,direction='Left',advance=0.)


def write(slide,kind,duration=.6,direction='Left',advance=0):
    if kind not in KINDS or direction not in ('Left','Right','Up','Down'):raise ValueError('Choose a transition and direction.')
    if not all(math.isfinite(v) for v in (duration,advance)) or not .05<=duration<=10 or not 0<=advance<=3600:raise ValueError('Transition duration: 0.05–10 seconds; advance: 0–3600 seconds.')
    for node in list(slide._element):
        if etree.QName(node).localname=='transition' or (etree.QName(node).localname=='AlternateContent' and node.find('.//{'+P+'}transition') is not None):slide._element.remove(node)
    if kind=='None' and not advance:return
    node=etree.Element('{'+P+'}transition',nsmap={'p14':P14,'p159':P159});node.set('spd','med');node.set('advClick','1');node.set('{'+P14+'}dur',str(round(duration*1000)))
    if advance:node.set('advTm',str(round(advance*1000)))
    if kind!='None':
        effect=etree.SubElement(node,'{'+(P159 if kind=='Morph objects' else P)+'}'+{'Fade':'fade','Push':'push','Wipe':'wipe','Morph objects':'morph'}[kind])
        if kind in ('Push','Wipe'):effect.set('dir',{'Left':'l','Right':'r','Up':'u','Down':'d'}[direction])
        elif kind=='Morph objects':effect.set('option','byObject')
    if kind=='Morph objects':
        root=etree.Element('{'+MC+'}AlternateContent',nsmap={'mc':MC,'p159':P159});choice=etree.SubElement(root,'{'+MC+'}Choice',Requires='p159');choice.append(node);fallback=etree.SubElement(root,'{'+MC+'}Fallback');transition=etree.SubElement(fallback,'{'+P+'}transition',spd='med');etree.SubElement(transition,'{'+P+'}fade');node=root
    index=next((i for i,child in enumerate(slide._element) if etree.QName(child).localname in {'timing','extLst'}),len(slide._element));slide._element.insert(index,node)


def snapshot(scene):
    rect=scene.sceneRect();width=1440;height=max(1,round(width*rect.height()/rect.width()));image=QImage(width,height,QImage.Format_ARGB32);image.fill(0);painter=QPainter(image)
    try:scene.render(painter,QRectF(image.rect()),rect)
    finally:painter.end()
    return image


class Transition(QObject):
    def __init__(self,view,previous,previous_slide,config,finished):
        super().__init__(view);self.view=view;self.config=config;self.progress=0.;self.active=True;self.previous=previous;self.current=None;self.morph=[]
        if config['kind']=='Morph objects' and previous_slide is not None:
            old={shape.name:shape for shape in previous_slide.shapes}
            for item in view.scene().items():
                if not hasattr(item,'native_shape') or item.parentItem() is not None:continue
                shape=item.native_shape;target=QPointF(item.pos());transform=QTransform(item.transform());rotation=item.rotation();match=old.get(shape.name)
                if match is not None and match.width and match.height:
                    self.morph.append((item,QPointF(match.left/12700,match.top/12700),target,match.width/max(1,shape.width),match.height/max(1,shape.height),transform,match.rotation,rotation))
                else:self.morph.append((item,target,target,1,1,transform,rotation,rotation))
        else:self.current=snapshot(view.scene())
        self.animation=QVariantAnimation(self);self.animation.setStartValue(0.);self.animation.setEndValue(1.);self.animation.setDuration(round(config['duration']*1000));self.animation.valueChanged.connect(self.update);self.animation.finished.connect(lambda:self.complete(finished));self.animation.start()
    def update(self,value):
        self.progress=float(value)
        for item,origin,target,sx,sy,transform,old_rotation,rotation in self.morph:
            t=self.progress;item.setPos(origin+(target-origin)*t);item.setTransform(transform*QTransform.fromScale(sx+(1-sx)*t,sy+(1-sy)*t));item.setRotation(old_rotation+(rotation-old_rotation)*t)
        self.view.viewport().update()
    def complete(self,finished):
        self.update(1.);self.active=False;self.view.viewport().update();finished()
    def paint(self,painter,rect):
        if not self.active or self.current is None:return
        t=self.progress;painter.save();painter.setClipRect(rect)
        if self.previous is not None:painter.drawImage(rect,self.previous)
        kind=self.config['kind'];direction=self.config['direction']
        if kind=='Push':
            dx,dy={'Left':(-rect.width()*t,0),'Right':(rect.width()*t,0),'Up':(0,-rect.height()*t),'Down':(0,rect.height()*t)}[direction]
            if self.previous is not None:painter.drawImage(rect.translated(dx,dy),self.previous)
            nx,ny={'Left':(rect.width()*(1-t),0),'Right':(-rect.width()*(1-t),0),'Up':(0,rect.height()*(1-t)),'Down':(0,-rect.height()*(1-t))}[direction];painter.drawImage(rect.translated(nx,ny),self.current)
        elif kind=='Wipe':
            clip=QRectF(rect)
            if direction=='Left':clip.setWidth(rect.width()*t)
            elif direction=='Right':clip.setLeft(rect.right()-rect.width()*t)
            elif direction=='Up':clip.setHeight(rect.height()*t)
            else:clip.setTop(rect.bottom()-rect.height()*t)
            painter.setClipRect(clip);painter.drawImage(rect,self.current)
        else:painter.setOpacity(t);painter.drawImage(rect,self.current)
        painter.restore()


def dialog(editor):
    from PySide6.QtWidgets import QDialog,QFormLayout,QComboBox,QDoubleSpinBox,QDialogButtonBox,QLabel
    slide=editor.deck.slides[editor.index];values=settings(slide);window=QDialog(editor);window.setWindowTitle('Slide transition and timing');form=QFormLayout(window)
    kind=QComboBox();kind.addItems(KINDS);kind.setCurrentText(values['kind']);direction=QComboBox();direction.addItems(['Left','Right','Up','Down']);direction.setCurrentText(values['direction'])
    duration=QDoubleSpinBox();duration.setRange(.05,10);duration.setValue(values['duration']);duration.setSuffix(' s');advance=QDoubleSpinBox();advance.setRange(0,3600);advance.setValue(values['advance']);advance.setSuffix(' s')
    for title,widget in [('Transition',kind),('Direction',direction),('Duration',duration),('Advance after (0 = manual)',advance)]:widget.setAccessibleName(title);form.addRow(title,widget)
    form.addRow(QLabel('Morph matches objects by name; use unique names across slides.'))
    buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(window.accept);buttons.rejected.connect(window.reject);form.addRow(buttons)
    if window.exec()==QDialog.Accepted:editor.change(lambda:write(slide,kind.currentText(),duration.value(),direction.currentText(),advance.value()))
