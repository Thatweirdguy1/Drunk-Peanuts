"""Native DrawingML freeform geometry and Qt path operations."""
import copy,math
from PySide6.QtCore import QObject,QEvent,QPointF,Qt
from PySide6.QtGui import QPainterPath,QPen,QColor
from PySide6.QtWidgets import QDialog,QVBoxLayout,QTableWidget,QTableWidgetItem,QDialogButtonBox,QGraphicsPathItem
from pptx.oxml.xmlchemy import OxmlElement
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Pt
from pptx.dml.color import RGBColor
from slide_rendering import A,geometry_path


def checked_bounds(path):
    if path.isEmpty() or path.elementCount()>10000:raise ValueError('Use a nonempty path with at most 10,000 points.')
    bounds=path.boundingRect()
    if any(not math.isfinite(v) or abs(v)>100000 for v in (bounds.x(),bounds.y(),bounds.width(),bounds.height())):raise ValueError('Geometry coordinates are out of range.')
    return bounds


def set_path(shape,path):
    bounds=checked_bounds(path)
    shape.left=Pt(bounds.x());shape.top=Pt(bounds.y());shape.width=Pt(max(1,bounds.width()));shape.height=Pt(max(1,bounds.height()));shape.rotation=0
    properties=shape._element.spPr
    for attribute in ('flipH','flipV'):properties.xfrm.attrib.pop(attribute,None)
    for tag in ('prstGeom','custGeom'):
        for node in list(properties.findall('{'+A+'}'+tag)):properties.remove(node)
    geometry=OxmlElement('a:custGeom')
    for tag in ('avLst','gdLst','ahLst','cxnLst'):geometry.append(OxmlElement('a:'+tag))
    rect=OxmlElement('a:rect')
    for key,value in [('l','0'),('t','0'),('r','w'),('b','h')]:rect.set(key,value)
    geometry.append(rect);listing=OxmlElement('a:pathLst');geometry.append(listing);node=OxmlElement('a:path');node.set('w',str(shape.width));node.set('h',str(shape.height));listing.append(node)
    def point(element):
        pt=OxmlElement('a:pt');pt.set('x',str(round((element.x-bounds.x())*12700)));pt.set('y',str(round((element.y-bounds.y())*12700)));return pt
    i=0
    while i<path.elementCount():
        element=path.elementAt(i)
        if element.isMoveTo():command=OxmlElement('a:moveTo');command.append(point(element))
        elif element.isLineTo():command=OxmlElement('a:lnTo');command.append(point(element))
        elif element.isCurveTo():
            if i+2>=path.elementCount():raise ValueError('Incomplete curve.')
            command=OxmlElement('a:cubicBezTo')
            for offset in range(3):command.append(point(path.elementAt(i+offset)))
            i+=2
        else:i+=1;continue
        node.append(command);i+=1
    # DrawingML geometry precedes fill, line and effect properties.
    position=1 if properties.find('{'+A+'}xfrm') is not None else 0;properties.insert(position,geometry)


def insert_path(editor,path,style=None):
    bounds=checked_bounds(path)
    shape=editor.deck.slides[editor.index].shapes.add_shape(MSO_SHAPE.RECTANGLE,Pt(bounds.x()),Pt(bounds.y()),Pt(max(1,bounds.width())),Pt(max(1,bounds.height())))
    if style is not None:
        for child in list(shape._element.spPr):
            if child.tag!='{'+A+'}xfrm':shape._element.spPr.remove(child)
        for child in style:
            if child.tag not in ('{'+A+'}xfrm','{'+A+'}prstGeom','{'+A+'}custGeom'):shape._element.spPr.append(copy.deepcopy(child))
    else:shape.fill.solid();shape.fill.fore_color.rgb=RGBColor.from_string('9457FF')
    set_path(shape,path);shape.name='Freeform';return shape


def combine(editor,operation):
    items=sorted(editor.scene.selectedItems(),key=lambda item:item.zValue())
    if len(items)<2:raise ValueError('Select at least two shapes.')
    if any(not hasattr(item,'native_shape') or item.parentItem() is not None or item.native_shape.has_chart or item.native_shape.has_table or item.native_shape.shape_type in (6,9,13,16,17) for item in items):raise ValueError('Select ungrouped drawing shapes. Pictures, text boxes, lines, charts and tables cannot be combined.')
    paths=[item.sceneTransform().map(geometry_path(item.native_shape._element.spPr,item.boundingRect())) for item in items]
    result=paths[0]
    for path in paths[1:]:
        if operation=='Union':result=result.united(path)
        elif operation=='Intersect':result=result.intersected(path)
        elif operation=='Subtract':result=result.subtracted(path)
        elif operation=='Exclude':result=result.united(path).subtracted(result.intersected(path))
        else:raise ValueError('Choose a shape operation.')
    if result.isEmpty():raise ValueError('The operation produces an empty shape. Try overlapping shapes.')
    def apply():
        shape=insert_path(editor,result,items[0].native_shape._element.spPr)
        from slide_rendering import P
        from presentation_tools import remove_native_shapes
        original=items[0].native_shape;first=original._element.find('.//{'+P+'}cNvPr');created=shape._element.find('.//{'+P+'}cNvPr');created.getparent().replace(created,copy.deepcopy(first))
        bodies=[item.native_shape._element.find('{'+P+'}txBody') for item in items if item.native_shape.has_text_frame and item.native_shape.text.strip()]
        if bodies:
            body=copy.deepcopy(bodies[0])
            for other in bodies[1:]:
                for paragraph in other.findall('{'+A+'}p'):body.append(copy.deepcopy(paragraph))
            existing=shape._element.find('{'+P+'}txBody')
            if existing is not None:shape._element.replace(existing,body)
            else:shape._element.append(body)
        remove_native_shapes(editor.deck.slides[editor.index],[item.native_shape for item in items],retained_ids=(original.shape_id,))
        return shape
    shape=editor.change(apply);editor.choose(shape);return shape


class FreeformTool(QObject):
    def __init__(self,editor):
        super().__init__(editor);self.editor=editor;self.points=[];self.preview=None;self.viewport=editor.slide_page.viewport();self.viewport.installEventFilter(self);editor.slide_page.installEventFilter(self);editor.slide_page.setFocus();self.viewport.setCursor(Qt.CrossCursor)
        editor.statusBar().showMessage('Freeform: click vertices · Enter or double-click closes the shape · Escape cancels')
    def stop(self,commit=False):
        self.viewport.removeEventFilter(self);self.editor.slide_page.removeEventFilter(self);self.viewport.unsetCursor();self.editor.freeform_tool=None
        if self.preview is not None and self.preview.scene():self.preview.scene().removeItem(self.preview)
        if commit and len(self.points)>=3:
            path=QPainterPath(self.points[0])
            for point in self.points[1:]:path.lineTo(point)
            path.closeSubpath();shape=self.editor.change(lambda:insert_path(self.editor,path));self.editor.choose(shape)
        self.editor.statusBar().showMessage('Freeform shape added.' if commit and len(self.points)>=3 else 'Drawing canceled.')
        self.editor.freeform_tool=None;self.deleteLater()
    def eventFilter(self,watched,event):
        if event.type()==QEvent.KeyPress:
            if event.key() in (Qt.Key_Escape,Qt.Key_Return,Qt.Key_Enter):self.stop(event.key()!=Qt.Key_Escape);return True
        if event.type() in (QEvent.MouseButtonPress,QEvent.MouseButtonDblClick) and event.button()==Qt.LeftButton:
            point=self.editor.slide_page.mapToScene(event.pos())
            if not self.editor.scene.sceneRect().contains(point):return True
            self.points.append(point)
            if event.type()==QEvent.MouseButtonDblClick:self.stop(True)
            else:
                path=QPainterPath(self.points[0])
                for point in self.points[1:]:path.lineTo(point)
                if self.preview is None:self.preview=QGraphicsPathItem();self.preview.setPen(QPen(QColor('#9457ff'),2));self.editor.scene.addItem(self.preview)
                self.preview.setPath(path)
            return True
        return False


def start_freeform(editor):
    active=getattr(editor,'freeform_tool',None)
    if active is not None:active.stop()
    editor.freeform_tool=FreeformTool(editor)


def snap_positions(editor,tolerance=6):
    items=[item for item in editor.scene.selectedItems() if getattr(item,'interactive',False)]
    if not items:return []
    bounds=items[0].sceneBoundingRect()
    for item in items[1:]:bounds=bounds.united(item.sceneBoundingRect())
    page=editor.scene.sceneRect();xs=[page.left(),page.center().x(),page.right()];ys=[page.top(),page.center().y(),page.bottom()]
    for item in editor.scene.items():
        if item in items or not getattr(item,'interactive',False):continue
        rect=item.sceneBoundingRect();xs.extend((rect.left(),rect.center().x(),rect.right()));ys.extend((rect.top(),rect.center().y(),rect.bottom()))
    def nearest(anchors,targets):
        value=min((target-anchor for anchor in anchors for target in targets),key=abs)
        return value if abs(value)<=tolerance else 0
    dx=nearest((bounds.left(),bounds.center().x(),bounds.right()),xs);dy=nearest((bounds.top(),bounds.center().y(),bounds.bottom()),ys)
    return [(item.native_shape,item.pos()+QPointF(dx,dy)) for item in items]


def edit_points(editor):
    items=editor.scene.selectedItems()
    if len(items)!=1 or not hasattr(items[0],'native_shape'):raise ValueError('Select one drawing shape.')
    item=items[0];shape=item.native_shape
    if shape.shape_type not in (1,5):raise ValueError('Select a drawing shape.')
    path=item.sceneTransform().map(geometry_path(shape._element.spPr,item.boundingRect()))
    dialog=QDialog(editor);dialog.setWindowTitle('Edit geometry points');dialog.resize(560,550);layout=QVBoxLayout(dialog);grid=QTableWidget(path.elementCount(),3);grid.setHorizontalHeaderLabels(['Point type','X (points)','Y (points)']);layout.addWidget(grid)
    for i in range(path.elementCount()):
        point=path.elementAt(i);label=QTableWidgetItem('Move' if point.isMoveTo() else 'Line' if point.isLineTo() else 'Curve/control');label.setFlags(label.flags() & ~Qt.ItemIsEditable);grid.setItem(i,0,label);grid.setItem(i,1,QTableWidgetItem(f'{point.x:.3f}'));grid.setItem(i,2,QTableWidgetItem(f'{point.y:.3f}'))
    buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);layout.addWidget(buttons);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
    if dialog.exec()==QDialog.Accepted:
        for i in range(path.elementCount()):
            x,y=float(grid.item(i,1).text()),float(grid.item(i,2).text())
            if not all(math.isfinite(v) and abs(v)<=100000 for v in (x,y)):raise ValueError('Point coordinates must be finite and within 100,000 points.')
            path.setElementPositionAt(i,x,y)
        editor.change(lambda:set_path(shape,path))
