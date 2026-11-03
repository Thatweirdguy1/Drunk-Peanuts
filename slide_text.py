"""On-canvas rich text and native paragraph/frame properties."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QTextCursor,QTextCharFormat
from PySide6.QtWidgets import QGraphicsTextItem,QDialog,QFormLayout,QDoubleSpinBox,QSpinBox,QComboBox,QCheckBox,QLineEdit,QDialogButtonBox
from pptx.util import Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN,MSO_AUTO_SIZE,MSO_ANCHOR
from pptx.oxml.xmlchemy import OxmlElement
from slide_rendering import A,text_html,SlideTheme


def document_to_frame(shape,document):
    frame=shape.text_frame;frame.clear();block=document.begin();index=0
    while block.isValid():
        paragraph=frame.paragraphs[0] if index==0 else frame.add_paragraph();index+=1;bf=block.blockFormat()
        paragraph.alignment={Qt.AlignHCenter:PP_ALIGN.CENTER,Qt.AlignRight:PP_ALIGN.RIGHT,Qt.AlignJustify:PP_ALIGN.JUSTIFY}.get(bf.alignment(),PP_ALIGN.LEFT)
        paragraph.space_before=Pt(max(0,bf.topMargin()));paragraph.space_after=Pt(max(0,bf.bottomMargin()))
        listing=block.textList()
        if listing is not None:
            node=OxmlElement('a:buChar');node.set('char','•');paragraph._p.get_or_add_pPr().append(node)
        it=block.begin()
        while not it.atEnd():
            fragment=it.fragment()
            if fragment.isValid():
                fmt=fragment.charFormat();run=paragraph.add_run();run.text=fragment.text();font=fmt.font();run.font.name=font.family() or 'Calibri';run.font.size=Pt(font.pointSizeF() if font.pointSizeF()>0 else max(6,font.pixelSize()))
                run.font.bold=font.bold();run.font.italic=font.italic();run.font.underline=font.underline()
                if fmt.foreground().color().isValid():run.font.color.rgb=RGBColor.from_string(fmt.foreground().color().name()[1:])
            it+=1
        block=block.next()


class InlineText(QGraphicsTextItem):
    def __init__(self,item):
        super().__init__(item);self.item=item;self.owner=item.owner;self.committing=False;self.cancelled=False
        self.setHtml(text_html(item.native_shape,item.theme));self.document().setDocumentMargin(0);self.setTextWidth(max(1,item.boundingRect().width()-14));self.setPos(7,3.5)
        self.setTextInteractionFlags(Qt.TextEditorInteraction);self.setZValue(1000);item.inline_editor=self;self.document().setModified(False);self.setFocus(Qt.MouseFocusReason)
        cursor=self.textCursor();cursor.movePosition(QTextCursor.End);self.setTextCursor(cursor)
    def finish(self,cancel=False):
        if self.committing or self.cancelled:return
        self.committing=True;self.cancelled=cancel;self.item.inline_editor=None
        if not cancel and self.document().isModified():
            def apply():
                shape=self.item.native_shape;document_to_frame(shape,self.document())
                if shape.text_frame.auto_size==MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT:shape.height=Pt(self.document().size().height()+shape.text_frame.margin_top.pt+shape.text_frame.margin_bottom.pt)
            self.owner.change(apply)
        else:self.item.update()
        if self.scene() is not None:self.scene().removeItem(self)
        self.deleteLater()
    def focusOutEvent(self,event):
        super().focusOutEvent(event);self.finish()
    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Escape:self.finish(True);return
        if event.key() in (Qt.Key_Return,Qt.Key_Enter) and event.modifiers() & Qt.ControlModifier:self.finish();return
        if event.modifiers() & Qt.ControlModifier and event.key() in (Qt.Key_B,Qt.Key_I,Qt.Key_U):
            cursor=self.textCursor();fmt=cursor.charFormat();update=QTextCharFormat()
            if event.key()==Qt.Key_B:update.setFontWeight(400 if fmt.fontWeight()>=700 else 700)
            elif event.key()==Qt.Key_I:update.setFontItalic(not fmt.fontItalic())
            else:update.setFontUnderline(not fmt.fontUnderline())
            cursor.mergeCharFormat(update);self.setTextCursor(cursor);return
        super().keyPressEvent(event)


def paragraph_dialog(editor):
    shape=editor.selected_shape()
    if shape is None or not shape.has_text_frame:raise ValueError('Select a text object first.')
    frame=shape.text_frame;paragraph=frame.paragraphs[0];window=QDialog(editor);window.setWindowTitle('Paragraph and text frame');form=QFormLayout(window);spins={}
    values={'Space before':paragraph.space_before.pt if paragraph.space_before else 0,'Space after':paragraph.space_after.pt if paragraph.space_after else 0,'Left margin':frame.margin_left.pt,'Right margin':frame.margin_right.pt,'Top margin':frame.margin_top.pt,'Bottom margin':frame.margin_bottom.pt,'Column gap':12}
    for name,value in values.items():
        widget=QDoubleSpinBox();widget.setRange(0,1000);widget.setValue(value);widget.setSuffix(' pt');widget.setAccessibleName(name);form.addRow(name,widget);spins[name]=widget
    spacing=QDoubleSpinBox();spacing.setRange(.5,5);spacing.setSingleStep(.1);spacing.setValue(paragraph.line_spacing if isinstance(paragraph.line_spacing,float) else 1);form.addRow('Line spacing (multiple)',spacing)
    columns=QSpinBox();columns.setRange(1,8);columns.setValue(int(frame._txBody.bodyPr.get('numCol','1')));form.addRow('Columns',columns)
    anchor=QComboBox();anchor.addItems(['Top','Middle','Bottom']);anchor.setCurrentIndex({MSO_ANCHOR.TOP:0,MSO_ANCHOR.MIDDLE:1,MSO_ANCHOR.BOTTOM:2}.get(frame.vertical_anchor,0));form.addRow('Vertical alignment',anchor)
    fit=QComboBox();fit.addItems(['Keep size / allow overflow','Shrink text to fit','Grow shape to fit text']);fit.setCurrentIndex({MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE:1,MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT:2}.get(frame.auto_size,0));form.addRow('Autofit',fit)
    wrap=QCheckBox('Wrap text');wrap.setChecked(frame.word_wrap is not False);form.addRow(wrap);tabs=QLineEdit();tabs.setPlaceholderText('36, 72, 108');tabs.setAccessibleName('Tab positions in points');form.addRow('Left tab stops (pt)',tabs)
    buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(window.accept);buttons.rejected.connect(window.reject);form.addRow(buttons)
    if window.exec()!=QDialog.Accepted:return
    stops=sorted({float(value.strip()) for value in tabs.text().split(',') if value.strip()})
    if any(not 0<=value<=10000 for value in stops):raise ValueError('Tab positions must be 0–10,000 points.')
    def apply():
        for p in frame.paragraphs:
            p.space_before=Pt(spins['Space before'].value());p.space_after=Pt(spins['Space after'].value());p.line_spacing=float(spacing.value())
            if stops:
                props=p._p.get_or_add_pPr();old=props.find('{'+A+'}tabLst')
                if old is not None:props.remove(old)
                listing=OxmlElement('a:tabLst');props.append(listing)
                for position in stops:node=OxmlElement('a:tab');node.set('pos',str(int(Pt(position))));node.set('algn','l');listing.append(node)
        for label,key in [('Left margin','margin_left'),('Right margin','margin_right'),('Top margin','margin_top'),('Bottom margin','margin_bottom')]:setattr(frame,key,Pt(spins[label].value()))
        frame.vertical_anchor=[MSO_ANCHOR.TOP,MSO_ANCHOR.MIDDLE,MSO_ANCHOR.BOTTOM][anchor.currentIndex()];frame.auto_size=[MSO_AUTO_SIZE.NONE,MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE,MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT][fit.currentIndex()];frame.word_wrap=wrap.isChecked();frame._txBody.bodyPr.set('numCol',str(columns.value()));frame._txBody.bodyPr.set('spcCol',str(int(Pt(spins['Column gap'].value()))))
    editor.change(apply)
