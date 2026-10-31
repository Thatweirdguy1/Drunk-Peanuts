"""Independent presentation editing commands built on the existing PPTX model."""
import copy,math
from pptx.util import Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QTextCursor,QTextListFormat,QTextCharFormat
from PySide6.QtWidgets import (QDialog,QDialogButtonBox,QVBoxLayout,QHBoxLayout,QFormLayout,
    QTextEdit,QGraphicsView,QPushButton,QComboBox,QDoubleSpinBox,QFontComboBox,QInputDialog,QColorDialog,QLabel)
from office_editing import command,presentation_copier


def selected(editor):
    return [item.native_shape for item in sorted(editor.scene.selectedItems(),key=lambda item:item.zValue()) if item.interactive]


def choose_many(editor,shapes):
    identifiers={shape.shape_id for shape in shapes};editor.scene.clearSelection()
    for item in editor.scene.items():
        if item.interactive and item.native_shape.shape_id in identifiers:item.setSelected(True)


def copy_objects(editor,cut=False):
    shapes=selected(editor)
    if not shapes:return
    # Keep a private document snapshot alive; copying never links editable chart/diagram data.
    from pptx import Presentation
    import io
    deck=Presentation(io.BytesIO(editor._bytes()));source=deck.slides[editor.index]
    ids={shape.shape_id for shape in shapes}
    editor._object_clipboard=(deck,source.part,[copy.deepcopy(shape._element) for shape in source.shapes if shape.shape_id in ids])
    if cut:delete_objects(editor)


def paste_objects(editor):
    clipboard=getattr(editor,'_object_clipboard',None)
    if clipboard is None:return
    _,source,elements=clipboard
    def paste():
        slide=editor.deck.slides[editor.index];copier=presentation_copier(source,slide.part);result=[];identifiers={}
        from pptx.shapes.shapetree import SlideShapeFactory
        for element in elements:
            clone=copier(element);identifier=slide.shapes._next_shape_id
            for offset,node in enumerate(clone.findall('.//{http://schemas.openxmlformats.org/presentationml/2006/main}cNvPr')):
                identifiers[node.get('id')]=str(identifier+offset)
                node.set('id',str(identifier+offset));node.set('name',node.get('name','Object')+' copy')
            slide.shapes._spTree.insert_element_before(clone,'p:extLst');shape=SlideShapeFactory(clone,slide.shapes)
            shape.left+=Pt(12);shape.top+=Pt(12);result.append(shape)
        for shape in result:
            for node in shape._element.iter():
                if node.tag.rsplit('}',1)[-1] in {'stCxn','endCxn'}:
                    if node.get('id') in identifiers:node.set('id',identifiers[node.get('id')])
                    else:node.getparent().remove(node)
        return result
    choose_many(editor,editor.change(paste))


def delete_objects(editor):
    shapes=selected(editor)
    if not shapes:return
    from dazzle import effects,set_effect
    def remove():
        slide=editor.deck.slides[editor.index]
        for shape in shapes:
            if shape.shape_id in effects(slide):set_effect(slide,shape.shape_id,None)
            shape._element.getparent().remove(shape._element)
    editor.change(remove)


def group_objects(editor):
    shapes=selected(editor)
    if len(shapes)<2:raise ValueError('Select at least two objects with Shift-click or the selection rectangle.')
    result=editor.change(lambda:editor.deck.slides[editor.index].shapes.add_group_shape(shapes))
    choose_many(editor,[result])


def ungroup_objects(editor):
    shapes=selected(editor)
    if len(shapes)!=1 or shapes[0].shape_type!=MSO_SHAPE_TYPE.GROUP:raise ValueError('Select one group to ungroup.')
    group=shapes[0];xf=group._element.grpSpPr.xfrm
    if group.rotation or xf.get('flipH') in {'1','true'} or xf.get('flipV') in {'1','true'}:
        raise ValueError('Reset the group rotation and flips before ungrouping; the group remains intact.')
    def ungroup():
        tree=group._element.getparent();position=tree.index(group._element);result=[]
        sx=group.width/max(1,xf.chExt.cx);sy=group.height/max(1,xf.chExt.cy)
        for shape in list(group.shapes):
            left=group.left+(shape.left-xf.chOff.x)*sx;top=group.top+(shape.top-xf.chOff.y)*sy
            width=shape.width*sx;height=shape.height*sy
            group.shapes._spTree.remove(shape._element);tree.insert(position,shape._element);position+=1
            shape.left=round(left);shape.top=round(top);shape.width=round(width);shape.height=round(height);result.append(shape)
        tree.remove(group._element);return result
    choose_many(editor,editor.change(ungroup))


def arrange_objects(editor,edge):
    shapes=selected(editor)
    if not shapes:raise ValueError('Select one or more objects first.')
    left=min(s.left for s in shapes);top=min(s.top for s in shapes)
    right=max(s.left+s.width for s in shapes);bottom=max(s.top+s.height for s in shapes)
    if len(shapes)==1:left=top=0;right=editor.deck.slide_width;bottom=editor.deck.slide_height
    def align():
        for shape in shapes:
            if edge=='Left':shape.left=left
            elif edge=='Center':shape.left=round((left+right-shape.width)/2)
            elif edge=='Right':shape.left=right-shape.width
            elif edge=='Top':shape.top=top
            elif edge=='Middle':shape.top=round((top+bottom-shape.height)/2)
            elif edge=='Bottom':shape.top=bottom-shape.height
    editor.change(align)


def distribute_objects(editor,horizontal=True):
    shapes=selected(editor)
    if len(shapes)<3:raise ValueError('Select at least three objects to distribute.')
    axis,size=('left','width') if horizontal else ('top','height');shapes.sort(key=lambda s:getattr(s,axis))
    start=getattr(shapes[0],axis);end=getattr(shapes[-1],axis)+getattr(shapes[-1],size)
    gap=(end-start-sum(getattr(s,size) for s in shapes))/(len(shapes)-1)
    def distribute():
        position=start
        for shape in shapes:setattr(shape,axis,round(position));position+=getattr(shape,size)+gap
    editor.change(distribute)


def flip_objects(editor,horizontal=True):
    shapes=selected(editor)
    def flip():
        for shape in shapes:
            xf=shape._element.get_or_add_xfrm();key='flipH' if horizontal else 'flipV'
            xf.set(key,'0' if xf.get(key) in {'1','true'} else '1')
    if shapes:editor.change(flip)


def crop_image(editor,values=None):
    shapes=selected(editor)
    if len(shapes)!=1 or shapes[0].shape_type!=MSO_SHAPE_TYPE.PICTURE:raise ValueError('Select one picture to crop.')
    shape=shapes[0];keys=('crop_left','crop_top','crop_right','crop_bottom')
    if values is None:
        dialog=QDialog(editor);dialog.setWindowTitle('Crop picture');layout=QFormLayout(dialog);inputs=[]
        for key in keys:
            spin=QDoubleSpinBox();spin.setRange(0,95);spin.setSuffix(' %');spin.setValue(getattr(shape,key)*100);spin.setAccessibleName(key.replace('_',' '));inputs.append(spin);layout.addRow(key.replace('crop_','').title(),spin)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addRow(buttons)
        if dialog.exec()!=QDialog.Accepted:return
        values=[spin.value()/100 for spin in inputs]
    if len(values)!=4 or not all(math.isfinite(v) and 0<=v<1 for v in values) or values[0]+values[2]>=1 or values[1]+values[3]>=1:raise ValueError('Keep a visible part of the image: opposing crops must total less than 100%.')
    editor.change(lambda:[setattr(shape,key,value) for key,value in zip(keys,values)])


def paragraph_format(editor,alignment=None,bullets=None):
    shapes=[s for s in selected(editor) if s.has_text_frame]
    if not shapes:raise ValueError('Select a text object first.')
    from pptx.oxml.xmlchemy import OxmlElement
    def apply():
        for shape in shapes:
            for paragraph in shape.text_frame.paragraphs:
                if alignment is not None:paragraph.alignment=alignment
                if bullets is not None:
                    props=paragraph._p.get_or_add_pPr()
                    for node in list(props):
                        if node.tag.rsplit('}',1)[-1] in {'buChar','buAutoNum','buNone'}:props.remove(node)
                    node=OxmlElement('a:buChar' if bullets=='bullets' else 'a:buAutoNum' if bullets=='numbers' else 'a:buNone')
                    if bullets=='bullets':node.set('char','•')
                    elif bullets=='numbers':node.set('type','arabicPeriod')
                    props.append(node)
    editor.change(apply)


def rich_text(editor):
    shapes=selected(editor)
    if len(shapes)!=1 or not shapes[0].has_text_frame:raise ValueError('Select one text object first. Use Edit object for charts, tables, and diagrams.')
    shape=shapes[0]
    from slide_rendering import text_html,SlideTheme,background
    dialog=QDialog(editor);dialog.setWindowTitle('Format text');dialog.resize(760,500);layout=QVBoxLayout(dialog);bar=QHBoxLayout();layout.addLayout(bar)
    theme=SlideTheme(editor.deck.slides[editor.index])
    text=QTextEdit();text.setAcceptRichText(False);text.setAccessibleName('Slide text editor');text.setStyleSheet('background:'+background(theme.slide,theme).name()+';');text.setHtml(text_html(shape,theme));layout.addWidget(text)
    family=QFontComboBox();family.setAccessibleName('Text font');bar.addWidget(family);family.currentFontChanged.connect(lambda font:text.setFontFamily(font.family()))
    size=QDoubleSpinBox();size.setRange(6,180);size.setValue(24);size.setAccessibleName('Text size');bar.addWidget(size);size.valueChanged.connect(text.setFontPointSize)
    for label,key in [('B','bold'),('I','italic'),('U','underline')]:
        button=QPushButton(label);button.setCheckable(True);button.setAccessibleName(key.title());bar.addWidget(button)
        def apply(checked,k=key):
            fmt=QTextCharFormat()
            if k=='bold':fmt.setFontWeight(700 if checked else 400)
            elif k=='italic':fmt.setFontItalic(checked)
            else:fmt.setFontUnderline(checked)
            text.mergeCurrentCharFormat(fmt);text.setFocus()
        button.clicked.connect(apply)
    color=QPushButton('Color');bar.addWidget(color)
    def choose_color():
        result=QColorDialog.getColor(text.textColor(),dialog)
        if result.isValid():text.setTextColor(result)
    color.clicked.connect(choose_color)
    buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
    if dialog.exec()!=QDialog.Accepted:return
    def apply_text():
        frame=shape.text_frame;frame.clear();block=text.document().begin();index=0
        while block.isValid():
            paragraph=frame.paragraphs[0] if index==0 else frame.add_paragraph();index+=1
            paragraph.alignment={Qt.AlignHCenter:PP_ALIGN.CENTER,Qt.AlignRight:PP_ALIGN.RIGHT,Qt.AlignJustify:PP_ALIGN.JUSTIFY}.get(block.blockFormat().alignment(),PP_ALIGN.LEFT)
            it=block.begin()
            while not it.atEnd():
                fragment=it.fragment()
                if fragment.isValid():
                    fmt=fragment.charFormat();run=paragraph.add_run();run.text=fragment.text();font=fmt.font();run.font.name=font.family() or 'Calibri';run.font.size=Pt(font.pointSizeF() if font.pointSizeF()>0 else max(6,font.pixelSize()))
                    run.font.bold=font.bold();run.font.italic=font.italic();run.font.underline=font.underline()
                    if fmt.foreground().color().isValid():run.font.color.rgb=RGBColor.from_string(fmt.foreground().color().name()[1:])
                it+=1
            block=block.next()
    editor.change(apply_text)


def slide_layout(editor,layout_index=None):
    layouts=editor.deck.slide_layouts
    if layout_index is None:
        label,ok=QInputDialog.getItem(editor,'Slide layout','Existing content keeps its position',[f'{i+1}. {layout.name}' for i,layout in enumerate(layouts)],0,False)
        if not ok:return
        layout_index=int(label.split('.',1)[0])-1
    if not 0<=layout_index<len(layouts):raise ValueError('Choose an available slide layout.')
    def apply():
        from pptx.opc.constants import RELATIONSHIP_TYPE as RT
        slide=editor.deck.slides[editor.index];part=slide.part
        positions=[(shape,shape.left,shape.top,shape.width,shape.height) for shape in slide.shapes]
        for rel in list(part.rels.values()):
            if rel.reltype==RT.SLIDE_LAYOUT:part.drop_rel(rel.rId)
        part.relate_to(layouts[layout_index].part,RT.SLIDE_LAYOUT)
        # python-pptx caches the resolved layout on the slide part.
        part.__dict__.pop('slide_layout',None)
        for shape,left,top,width,height in positions:
            if all(value is not None for value in (left,top,width,height)):
                shape.left=left;shape.top=top;shape.width=width;shape.height=height
    editor.change(apply)


def hide_slide(editor):
    slide=editor.deck.slides[editor.index]
    editor.change(lambda:slide._element.set('show','1' if slide._element.get('show')=='0' else '0'))


def set_hyperlink(editor,address=None):
    shapes=selected(editor)
    if len(shapes)!=1:raise ValueError('Select one object first.')
    shape=shapes[0]
    if address is None:
        address,ok=QInputDialog.getText(editor,'Object hyperlink','HTTPS, HTTP, or mailto address (empty removes link)')
        if not ok:return
    from urllib.parse import urlparse
    if not isinstance(address,str) or len(address)>4096 or (address and urlparse(address).scheme.lower() not in {'https','http','mailto'}):raise ValueError('Use an HTTP, HTTPS, or mailto link.')
    editor.change(lambda:setattr(shape.click_action.hyperlink,'address',address or None))


def insert_connector(editor):
    shapes=selected(editor)
    if len(shapes)!=2:raise ValueError('Select two objects to connect, using Shift-click.')
    from pptx.enum.shapes import MSO_CONNECTOR
    from pptx.oxml.xmlchemy import OxmlElement
    def add():
        first,last=shapes;line=editor.deck.slides[editor.index].shapes.add_connector(MSO_CONNECTOR.STRAIGHT,first.left+first.width,first.top+first.height//2,last.left,last.top+last.height//2)
        line.begin_connect(first,3);line.end_connect(last,1);line.line.color.rgb=RGBColor.from_string('9457FF');line.line.width=Pt(1.5)
        tail=OxmlElement('a:tailEnd');tail.set('type','triangle');line._element.spPr.get_or_add_ln().append(tail)
        line._element.set('{urn:freeconvert:slide-animation:1}connector','1');return line
    choose_many(editor,[editor.change(add)])


def export_images(editor):
    from PySide6.QtWidgets import QFileDialog
    from PySide6.QtGui import QImage,QPainter
    from PySide6.QtCore import QRectF
    from pathlib import Path
    import tempfile
    folder=QFileDialog.getExistingDirectory(editor,'Export slides as PNG images')
    if not folder:return
    # Export into a new directory; never overwrite an existing image batch.
    target=Path(tempfile.mkdtemp(prefix='Dazzle-slides-',dir=folder));editor._store()
    for index in range(len(editor.deck.slides)):
        scene=editor.make_scene(index,False);height=round(1920*editor.deck.slide_height/editor.deck.slide_width)
        image=QImage(1920,height,QImage.Format_ARGB32);image.fill(Qt.transparent);painter=QPainter(image)
        try:scene.render(painter,QRectF(0,0,1920,height))
        finally:painter.end();scene.deleteLater()
        if not image.save(str(target/f'slide-{index+1:03}.png')):raise OSError('Could not write slide image. Check free space and folder permissions.')
    editor.statusBar().showMessage('Slide images saved to '+str(target))


def presenter_view(editor):
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QPixmap,QImage,QPainter
    from PySide6.QtCore import QRectF
    from PySide6.QtWidgets import QSizePolicy
    import time
    dialog=QDialog(editor);dialog.setWindowTitle('Dazzle · Presenter view');dialog.resize(1000,650);layout=QVBoxLayout(dialog);status=QLabel();layout.addWidget(status)
    previews=QHBoxLayout();layout.addLayout(previews);current=QLabel();upcoming=QLabel()
    for label in (current,upcoming):
        label.setAlignment(Qt.AlignCenter);label.setMinimumSize(300,180);label.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Expanding);previews.addWidget(label)
    notes=QTextEdit();notes.setReadOnly(True);notes.setAccessibleName('Current slide speaker notes');layout.addWidget(notes)
    row=QHBoxLayout();layout.addLayout(row);started=time.monotonic();index=[editor.index];pixmaps={}
    def refresh():
        slide=editor.deck.slides[index[0]];status.setText(f'Slide {index[0]+1} of {len(editor.deck.slides)} · elapsed {int(time.monotonic()-started)//60:02}:{int(time.monotonic()-started)%60:02}')
        for cached in list(pixmaps):
            if cached not in (index[0],index[0]+1):del pixmaps[cached]
        for label,i in ((current,index[0]),(upcoming,index[0]+1)):
            if i<len(editor.deck.slides):
                if i not in pixmaps:
                    scene=editor.make_scene(i,False);image=QImage(960,round(960*editor.deck.slide_height/editor.deck.slide_width),QImage.Format_ARGB32);image.fill(Qt.transparent);painter=QPainter(image)
                    try:scene.render(painter,QRectF(image.rect()))
                    finally:painter.end();scene.deleteLater()
                    pixmaps[i]=QPixmap.fromImage(image)
                label.setPixmap(pixmaps[i].scaled(label.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
            else:label.setText('End of presentation')
        frame=slide.notes_slide.notes_text_frame if slide.has_notes_slide else None;notes.setPlainText(frame.text if frame is not None else 'No speaker notes for this slide.')
    def navigate(delta):index[0]=max(0,min(len(editor.deck.slides)-1,index[0]+delta));refresh()
    for label,callback in [('Previous',lambda:navigate(-1)),('Next',lambda:navigate(1)),('Present current slide',lambda:editor.present(index[0])),('Close',dialog.close)]:
        button=QPushButton(label);button.clicked.connect(callback);row.addWidget(button)
    timer=QTimer(dialog);timer.timeout.connect(refresh);timer.start(1000);QTimer.singleShot(0,refresh);dialog.exec()


def sync_connectors(editor):
    slide=editor.deck.slides[editor.index];shapes={shape.shape_id:shape for shape in slide.shapes}
    for line in slide.shapes:
        if line._element.get('{urn:freeconvert:slide-animation:1}connector')!='1':continue
        ns='{http://schemas.openxmlformats.org/drawingml/2006/main}'
        start=line._element.find('.//'+ns+'stCxn');end=line._element.find('.//'+ns+'endCxn')
        if start is None or end is None:continue
        first=shapes.get(int(start.get('id')));last=shapes.get(int(end.get('id')))
        if first is None or last is None:continue
        x1,y1=first.left+first.width,first.top+first.height//2;x2,y2=last.left,last.top+last.height//2
        xf=line._element.spPr.xfrm;xf.off.x=min(x1,x2);xf.off.y=min(y1,y2);xf.ext.cx=abs(x2-x1);xf.ext.cy=abs(y2-y1)
        xf.set('flipH','1' if x1>x2 else '0');xf.set('flipV','1' if y1>y2 else '0')


def setup(editor):
    editor.slide_page.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
    commands=[
        ('File','Export slide images',lambda:export_images(editor),None),
        ('Insert','Connector',lambda:insert_connector(editor),None),('Insert','Hyperlink',lambda:set_hyperlink(editor),'Ctrl+K'),
        ('Slide','Presenter view',lambda:presenter_view(editor),None),
        ('Edit','Select all objects',lambda:choose_many(editor,list(editor.deck.slides[editor.index].shapes)),'Ctrl+A'),
        ('Edit','Copy objects',lambda:copy_objects(editor),'Ctrl+C'),('Edit','Cut objects',lambda:copy_objects(editor,True),'Ctrl+X'),
        ('Edit','Paste objects',lambda:paste_objects(editor),'Ctrl+V'),('Design','Format text',lambda:rich_text(editor),'Ctrl+E'),
        ('Design','Align text left',lambda:paragraph_format(editor,PP_ALIGN.LEFT),None),('Design','Align text center',lambda:paragraph_format(editor,PP_ALIGN.CENTER),None),
        ('Design','Align text right',lambda:paragraph_format(editor,PP_ALIGN.RIGHT),None),('Design','Bullets',lambda:paragraph_format(editor,bullets='bullets'),None),
        ('Design','Numbering',lambda:paragraph_format(editor,bullets='numbers'),None),('Design','Remove bullets',lambda:paragraph_format(editor,bullets='none'),None),
        ('Design','Slide layout',lambda:slide_layout(editor),None),('Design','Crop picture',lambda:crop_image(editor),None),
        ('Arrange','Group',lambda:group_objects(editor),'Ctrl+G'),('Arrange','Ungroup',lambda:ungroup_objects(editor),'Ctrl+Shift+G'),
        ('Arrange','Distribute horizontally',lambda:distribute_objects(editor,True),None),('Arrange','Distribute vertically',lambda:distribute_objects(editor,False),None),
        ('Arrange','Flip horizontal',lambda:flip_objects(editor,True),None),('Arrange','Flip vertical',lambda:flip_objects(editor,False),None),
        ('Slide','Hide / show slide',lambda:hide_slide(editor),None),
    ]
    for menu,label,callback,shortcut in commands:command(editor,menu,label,callback,'settings',shortcut)
