"""Editable native theme colors/fonts and master/layout objects."""
import io,json,math,re,copy
from pathlib import Path
from lxml import etree
from pptx import Presentation
from pptx.util import Pt
from pptx.oxml import parse_xml
from pptx.dml.color import RGBColor
from PySide6.QtCore import Qt,QSignalBlocker
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDialog,QFormLayout,QLineEdit,QComboBox,QDialogButtonBox,
    QPushButton,QColorDialog,QFileDialog,QHBoxLayout,QVBoxLayout,QLabel,QTableWidget,
    QTableWidgetItem,QMessageBox,QInputDialog)
from slide_rendering import A,P,R,SlideTheme


def theme_part(master):return next(rel.target_part for rel in master.part.rels.values() if rel.reltype.endswith('/theme'))
def save_xml(part,root):
    if hasattr(part,'_element'):part._element=root
    else:part._blob=etree.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)


def apply_theme(deck,colors,major,minor,all_masters=False,index=0):
    keys={'dk1','lt1','dk2','lt2','accent1','accent2','accent3','accent4','accent5','accent6','hlink','folHlink'}
    if set(colors)!=keys or any(not re.fullmatch('#[0-9a-fA-F]{6}',value) for value in colors.values()):raise ValueError('A theme requires twelve valid RGB colors.')
    if any(not isinstance(font,str) or not font.strip() or len(font)>200 or any(ord(c)<32 for c in font) for font in (major,minor)):raise ValueError('Enter readable font family names, up to 200 characters.')
    masters=list(deck.slide_masters) if all_masters else [deck.slide_masters[index]];seen=set()
    for master in masters:
        part=theme_part(master)
        if part in seen:continue
        seen.add(part);root=etree.fromstring(part.blob);scheme=root.find('.//{'+A+'}clrScheme')
        for key,value in colors.items():
            node=scheme.find('{'+A+'}'+key)
            if node is None:node=etree.SubElement(scheme,'{'+A+'}'+key)
            node[:]=[];etree.SubElement(node,'{'+A+'}srgbClr',val=value[1:])
        for kind,family in [('major',major),('minor',minor)]:root.find('.//{'+A+'}'+kind+'Font/{'+A+'}latin').set('typeface',family)
        save_xml(part,root)


def theme_dialog(editor):
    theme=SlideTheme(editor.deck.slides[editor.index]);window=QDialog(editor);window.setWindowTitle('Theme colors and fonts');form=QFormLayout(window);fields={}
    for key,color in theme.colors.items():
        field=QLineEdit('#'+color);field.setAccessibleName('Theme '+key);button=QPushButton('Choose');row=QHBoxLayout();row.addWidget(field);row.addWidget(button)
        def choose(_,f=field):
            color=QColorDialog.getColor(QColor(f.text()),window)
            if color.isValid():f.setText(color.name())
        button.clicked.connect(choose);form.addRow(key,row);fields[key]=field
    major=QLineEdit(theme.fonts['major']);minor=QLineEdit(theme.fonts['minor']);form.addRow('Headings font',major);form.addRow('Body font',minor)
    scope=QComboBox();scope.addItems(['Current master','All masters']);form.addRow('Apply to',scope)
    row=QHBoxLayout();export=QPushButton('Save theme variant');load=QPushButton('Open theme variant');row.addWidget(export);row.addWidget(load);form.addRow(row)
    def payload():return dict(colors={key:field.text() for key,field in fields.items()},major=major.text(),minor=minor.text())
    def save():
        value=payload();apply_theme(Presentation(),**value)
        name,_=QFileDialog.getSaveFileName(window,'Save local theme variant','','Dazzle theme (*.dp-theme)')
        if name:Path(name).write_text(json.dumps(value,indent=2),encoding='utf-8')
    def open_variant():
        name,_=QFileDialog.getOpenFileName(window,'Open local theme variant','','Dazzle theme (*.dp-theme)')
        if not name:return
        if Path(name).stat().st_size>100000:raise ValueError('Theme variant is too large.')
        value=json.loads(Path(name).read_text(encoding='utf-8'));apply_theme(Presentation(),**value)
        for key,field in fields.items():field.setText(value['colors'][key])
        major.setText(value['major']);minor.setText(value['minor'])
    export.clicked.connect(lambda:editor.report(save));load.clicked.connect(lambda:editor.report(open_variant))
    buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(window.accept);buttons.rejected.connect(window.reject);form.addRow(buttons)
    if window.exec()==QDialog.Accepted:
        index=next(i for i,master in enumerate(editor.deck.slide_masters) if master.part is theme.master.part)
        editor.change(lambda:apply_theme(editor.deck,**payload(),all_masters=bool(scope.currentIndex()),index=index))


def add_placeholder(owner,kind='obj'):
    if kind not in ('title','body','obj','pic','dt','ftr','hdr','sldNum'):raise ValueError('Choose a supported placeholder role.')
    index=max((s.placeholder_format.idx for s in owner.shapes if s.is_placeholder),default=0)+1;identifier=owner.shapes._next_shape_id
    element=parse_xml(f'<p:sp xmlns:p="{P}" xmlns:a="{A}"><p:nvSpPr><p:cNvPr id="{identifier}" name="New placeholder {index}"/><p:cNvSpPr/><p:nvPr><p:ph type="{kind}" idx="{index}"/></p:nvPr></p:nvSpPr><p:spPr><a:xfrm><a:off x="914400" y="914400"/><a:ext cx="5486400" cy="1828800"/></a:xfrm></p:spPr><p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>New placeholder</a:t></a:r></a:p></p:txBody></p:sp>')
    owner.shapes._spTree.insert_element_before(element,'p:extLst')
    return owner.shapes[-1]


def clone_layout(deck,layout,name):
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT
    from office_editing import presentation_copier
    if not name.strip() or len(name)>200:raise ValueError('Enter a layout name up to 200 characters.')
    part=layout.part;package=deck.part.package;target=type(part).load(package.next_partname('/ppt/slideLayouts/slideLayout%d.xml'),part.content_type,package,part.blob)
    target.relate_to(layout.slide_master.part,RT.SLIDE_MASTER);target._element=presentation_copier(part,target)(layout._element);target._element.cSld.set('name',name)
    master=layout.slide_master;rid=master.part.relate_to(target,RT.SLIDE_LAYOUT);listing=master._element.sldLayoutIdLst;identifier=max((int(n.get('id')) for n in listing),default=2147483648)+1
    node=etree.SubElement(listing,'{'+P+'}sldLayoutId',id=str(identifier));node.set('{'+R+'}id',rid)
    return target.slide_layout


def master_dialog(editor):
    working=Presentation(io.BytesIO(editor._bytes()));window=QDialog(editor);window.setWindowTitle('Slide masters and layouts');window.resize(1120,700);layout=QVBoxLayout(window)
    layout.addWidget(QLabel('Changes affect every slide using this master or layout. Cancel leaves the presentation unchanged. Blank font fields retain inheritance.'))
    choice=QComboBox();layout.addWidget(choice);table=QTableWidget();layout.addWidget(table)
    columns=['Name','Role','Placeholder ID','X (pt)','Y (pt)','Width (pt)','Height (pt)','Text','Font','Size (pt)','Color','Alt text'];table.setColumnCount(len(columns));table.setHorizontalHeaderLabels(columns);table.setAccessibleName('Master and layout objects');state={'owner':None,'rows':[]}
    def owners():
        result=[]
        for i,master in enumerate(working.slide_masters):
            result.append((f'Master {i+1}',master))
            result.extend((f'  {i+1} / {part.name}',part) for part in master.slide_layouts)
        return result
    def reload_choices(selected=None):
        with QSignalBlocker(choice):
            choice.clear()
            for label,owner in owners():choice.addItem(label,owner)
            if selected is not None:
                for i in range(choice.count()):
                    if choice.itemData(i).part is selected.part:choice.setCurrentIndex(i);break
    def commit_rows():
        rows=state['rows'];parsed=[]
        for row,shape in enumerate(rows):
            values=[table.item(row,col).text() for col in range(len(columns))]
            numbers=[float(value) if value.strip() else None for value in values[3:7]]
            if any(value is not None and (not math.isfinite(value) or abs(value)>10000) for value in numbers):raise ValueError('Object geometry must be finite and within 10,000 points.')
            if any(value is not None and value<=0 for value in numbers[2:]):raise ValueError('Object width and height must be positive.')
            if values[10] and not re.fullmatch('#[0-9a-fA-F]{6}',values[10]):raise ValueError('Use #RRGGBB for text colors.')
            if values[9] and not 1<=float(values[9])<=400:raise ValueError('Font size must be 1–400 points.')
            if values[1] and values[1] not in ('title','body','ctrTitle','subTitle','obj','pic','dt','ftr','hdr','sldNum','chart','tbl','media','clipArt','dgm','sldImg'):raise ValueError('Choose a valid placeholder role.')
            if values[2] and not 0<=int(values[2])<=10000:raise ValueError('Placeholder IDs must be 0–10,000.')
            parsed.append((shape,values,numbers))
        ids=[v[1][2] for v in parsed if v[1][2]]
        if len(ids)!=len(set(ids)):raise ValueError('Placeholder IDs must be unique within this master/layout.')
        for shape,values,numbers in parsed:
            shape.name=values[0]
            for key,value in zip(('left','top','width','height'),numbers):
                if value is not None:setattr(shape,key,Pt(value))
            nv=shape._element.find('.//{'+P+'}cNvPr')
            if nv is not None:nv.set('descr',values[11])
            ph=shape._element.find('.//{'+P+'}ph')
            if ph is not None:ph.set('type',values[1] or 'obj');ph.set('idx',values[2] or '0')
            if shape.has_text_frame:
                if shape.text!=values[7]:
                    from office_surgery import replace_text_frame
                    replace_text_frame(shape,values[7])
                if any(values[8:11]):
                    for paragraph in shape.text_frame.paragraphs:
                        for font in [paragraph.font]+[run.font for run in paragraph.runs]:
                            if values[8]:font.name=values[8]
                            if values[9]:font.size=Pt(float(values[9]))
                            if values[10]:font.color.rgb=RGBColor.from_string(values[10][1:])
    def show_owner(index):
        old=state['owner']
        try:commit_rows()
        except (ValueError,TypeError) as error:
            QMessageBox.warning(window,'Master properties',str(error))
            with QSignalBlocker(choice):
                for i in range(choice.count()):
                    if choice.itemData(i) is old:choice.setCurrentIndex(i);break
            return
        owner=choice.itemData(index);state['owner']=owner;state['rows']=list(owner.shapes);table.setRowCount(len(state['rows']))
        for row,shape in enumerate(state['rows']):
            ph=shape._element.find('.//{'+P+'}ph');rpr=shape._element.find('.//{'+A+'}rPr');latin=rpr.find('{'+A+'}latin') if rpr is not None else None;color=rpr.find('{'+A+'}solidFill/{'+A+'}srgbClr') if rpr is not None else None;nv=shape._element.find('.//{'+P+'}cNvPr')
            values=[shape.name,ph.get('type','obj') if ph is not None else '',ph.get('idx','0') if ph is not None else '',*[f'{value/12700:g}' if value is not None else '' for value in (shape.left,shape.top,shape.width,shape.height)],shape.text if shape.has_text_frame else '',latin.get('typeface','') if latin is not None else '',str(float(rpr.get('sz'))/100) if rpr is not None and rpr.get('sz') else '',('#'+color.get('val')) if color is not None else '',nv.get('descr','') if nv is not None else '']
            for col,value in enumerate(values):table.setItem(row,col,QTableWidgetItem(value))
        table.resizeColumnsToContents()
    def add():
        commit_rows();kind,ok=QInputDialog.getItem(window,'New placeholder','Role',['title','body','obj','pic','dt','ftr','sldNum'],0,False)
        if ok:add_placeholder(state['owner'],kind);state['rows']=[];show_owner(choice.currentIndex())
    def remove():
        row=table.currentRow()
        if row<0:return
        shape=state['rows'][row];shape._element.getparent().remove(shape._element);state['rows'].pop(row);table.removeRow(row)
    def duplicate():
        commit_rows();owner=state['owner']
        if not hasattr(owner,'slide_master'):raise ValueError('Select a layout to duplicate.')
        name,ok=QInputDialog.getText(window,'Duplicate layout','Name')
        if ok:result=clone_layout(working,owner,name);state['rows']=[];reload_choices(result);show_owner(choice.currentIndex())
    def background():
        color=QColorDialog.getColor(QColor('#f5f3eb'),window)
        if color.isValid():fill=state['owner'].background.fill;fill.solid();fill.fore_color.rgb=RGBColor.from_string(color.name()[1:])
    row=QHBoxLayout();layout.addLayout(row)
    for label,callback in [('Add placeholder',add),('Delete object',remove),('Duplicate layout',duplicate),('Background',background)]:
        button=QPushButton(label);button.clicked.connect(lambda _,cb=callback:editor.report(cb));row.addWidget(button)
    choice.currentIndexChanged.connect(show_owner);reload_choices();show_owner(0)
    buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);layout.addWidget(buttons)
    def accept():
        try:commit_rows();window.accept()
        except (ValueError,TypeError) as error:QMessageBox.warning(window,'Master properties',str(error))
    buttons.accepted.connect(accept);buttons.rejected.connect(window.reject)
    if window.exec()==QDialog.Accepted:editor.change(lambda:setattr(editor,'deck',working))


def inherit_background(editor):
    slide=editor.deck.slides[editor.index]
    def apply():
        node=slide._element.cSld.find('{'+P+'}bg')
        if node is not None:node.getparent().remove(node)
    editor.change(apply)
