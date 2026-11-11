"""Native slide, notes and handout printing with atomic PDF output."""
import math,tempfile
from pathlib import Path
from PySide6.QtCore import QRectF,QSizeF
from PySide6.QtGui import QPainter,QTextDocument,QFont,QPageSize
from PySide6.QtPrintSupport import QPrinter,QPrintPreviewDialog
from PySide6.QtWidgets import QDialog,QFormLayout,QComboBox,QCheckBox,QPushButton,QFileDialog


def render(editor,printer,mode='Slides',per_page=6,include_hidden=False):
    if mode not in ('Slides','Notes','Handouts') or per_page not in (2,3,4,6,9):raise ValueError('Choose a print layout.')
    selected=[i for i,slide in enumerate(editor.deck.slides) if include_hidden or slide._element.get('show')!='0']
    if not selected:raise ValueError('There are no visible slides to print.')
    painter=QPainter()
    if not painter.begin(printer):raise OSError('Could not open the printer or PDF output.')
    resolution=printer.resolution();page=QRectF(0,0,printer.width()*72/resolution,printer.height()*72/resolution);pages=0
    def new_page():
        nonlocal pages
        if pages and not printer.newPage():raise OSError('The printer could not create another page.')
        pages+=1;painter.resetTransform();painter.scale(resolution/72,resolution/72);painter.setFont(QFont('Arial',10))
    def slide(index,rect):
        scene=editor.make_scene(index,False)
        try:scene.render(painter,rect,scene.sceneRect())
        finally:scene.clear();scene.deleteLater()
    try:
        if mode=='Handouts':
            columns=2 if per_page>=4 else 1;rows=math.ceil(per_page/columns)
            for first in range(0,len(selected),per_page):
                new_page()
                for position,index in enumerate(selected[first:first+per_page]):
                    width=page.width()/columns;height=page.height()/rows;x=(position%columns)*width;y=(position//columns)*height
                    painter.drawText(QRectF(x+6,y+2,width-12,18),f'Slide {index+1}')
                    slide(index,QRectF(x+6,y+24,width-12,height-36))
        else:
            for index in selected:
                if mode=='Slides':new_page();slide(index,page);continue
                source=editor.deck.slides[index];notes=source.notes_slide.notes_text_frame.text if source.has_notes_slide and source.notes_slide.notes_text_frame is not None else ''
                image_height=page.width()*editor.deck.slide_height/editor.deck.slide_width;top=min(page.height()*.48,image_height)+28;available=max(80,page.height()-top-16)
                document=QTextDocument();document.setDefaultFont(QFont('Arial',11));document.setPlainText(notes or 'No speaker notes.');document.setPageSize(QSizeF(page.width()-12,available))
                for continuation in range(max(1,document.pageCount())):
                    new_page();painter.drawText(QRectF(0,0,page.width(),20),f'Slide {index+1} · Speaker notes'+(' (continued)' if continuation else ''))
                    slide(index,QRectF(0,24,page.width(),top-28));painter.save();painter.translate(6,top);painter.setClipRect(QRectF(0,0,page.width()-12,available));painter.translate(0,-continuation*available);document.drawContents(painter);painter.restore()
    finally:painter.end()
    return pages


def export_pdf(editor,path,mode='Slides',per_page=6,include_hidden=False):
    path=Path(path)
    if path.suffix.lower()!='.pdf':raise ValueError('Choose a PDF filename.')
    with tempfile.NamedTemporaryFile(dir=path.parent,suffix='.pdf',delete=False) as stream:temporary=Path(stream.name)
    try:
        printer=QPrinter(QPrinter.HighResolution);printer.setResolution(120);printer.setOutputFormat(QPrinter.PdfFormat);printer.setPageSize(QPageSize(QPageSize.A4));printer.setOutputFileName(str(temporary))
        pages=render(editor,printer,mode,per_page,include_hidden);temporary.replace(path);return pages
    finally:temporary.unlink(missing_ok=True)


def dialog(editor):
    window=QDialog(editor);window.setWindowTitle('Print slides, notes and handouts');form=QFormLayout(window)
    mode=QComboBox();mode.addItems(['Slides','Notes','Handouts']);count=QComboBox();count.addItems(['2','3','4','6','9']);count.setCurrentText('6');hidden=QCheckBox('Include hidden slides');form.addRow('Layout',mode);form.addRow('Slides per handout page',count);form.addRow(hidden)
    def preview():
        printer=QPrinter(QPrinter.HighResolution);printer.setPageSize(QPageSize(QPageSize.A4));view=QPrintPreviewDialog(printer,window);view.paintRequested.connect(lambda output:editor.report(lambda:render(editor,output,mode.currentText(),int(count.currentText()),hidden.isChecked())));view.exec()
    def save():
        path,_=QFileDialog.getSaveFileName(window,'Save print layout as PDF','','PDF (*.pdf)')
        if path:editor.report(lambda:export_pdf(editor,path,mode.currentText(),int(count.currentText()),hidden.isChecked()))
    for label,callback in [('Preview / Print',preview),('Save PDF',save),('Close',window.accept)]:button=QPushButton(label);button.clicked.connect(callback);form.addRow(button)
    window.exec()
