"""Visual, nondestructive PDF page organization."""
from pathlib import Path
from pypdf import PdfReader,PdfWriter
from PySide6.QtCore import Qt,QSize,QTimer
from PySide6.QtGui import QIcon,QPixmap,QImage,QTransform
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QListWidget,QListWidgetItem,QAbstractItemView,QPushButton,QFileDialog,QInputDialog,QLabel,QMessageBox,QProgressDialog
from ui import editor_theme


def page_range(text,count):
    result=[]
    for token in text.split(','):
        token=token.strip()
        if not token:raise ValueError('Enter page numbers or ranges, for example 1-3,5.')
        pieces=token.split('-')
        if len(pieces)>2 or not all(p.isdigit() for p in pieces):raise ValueError('Use positive page numbers and comma-separated ranges.')
        start=int(pieces[0]);end=int(pieces[-1])
        if not 1<=start<=count or not 1<=end<=count:raise ValueError(f'Page numbers must be between 1 and {count}.')
        result.extend(range(start,end+(1 if end>=start else -1),1 if end>=start else -1))
    if len(result)!=len(set(result)):raise ValueError('A page may only appear once.')
    return result

def write_pages(source,target,records):
    source,target=Path(source),Path(target)
    if target.exists() or source.resolve()==target.resolve():raise FileExistsError('Choose a new output filename; source files are never replaced.')
    reader=PdfReader(str(source));count=len(reader.pages)
    if not records or len({p for p,r in records})!=len(records) or any(not 1<=p<=count or r not in (0,90,180,270) for p,r in records):raise ValueError('Choose valid, unique pages and quarter-turn rotations.')
    writer=PdfWriter();created=False
    try:
        for page,rotation in records:
            writer.add_page(reader.pages[page-1])
            if rotation:writer.pages[-1].rotate(rotation)
        with target.open('xb') as out:created=True;writer.write(out)
    except Exception:
        if created:target.unlink(missing_ok=True)
        raise
    finally:writer.close()

def split_groups(source,folder,groups):
    folder=Path(folder)
    if folder.exists():raise FileExistsError('Choose a new output folder.')
    if not groups or any(not group for group in groups):raise ValueError('Each output needs at least one page.')
    folder.mkdir(parents=True)
    created=[]
    try:
        for index,group in enumerate(groups,1):
            path=folder/f'part-{index:03d}.pdf';write_pages(source,path,group);created.append(path)
    except Exception:
        for path in created:path.unlink(missing_ok=True)
        folder.rmdir();raise

class PdfPages(QDialog):
    def __init__(self,path,parent=None):
        super().__init__(parent);self.source=Path(path);self.setWindowTitle('Document pages · FreeConvert');self.resize(1050,760);self.setStyleSheet(editor_theme());self.pdf=None;self.thumb_index=0;self.pixmaps={};self.items={}
        count=len(PdfReader(str(path)).pages);self.total=count
        if not count:raise ValueError('The document has no pages.')
        layout=QVBoxLayout(self);layout.addWidget(QLabel(f'{self.source.name} · {count} pages\nDrag cards to reorder. Ctrl/Shift selects several pages. Every operation creates new files.'))
        self.pages=QListWidget();self.pages.setViewMode(QListWidget.IconMode);self.pages.setIconSize(QSize(125,160));self.pages.setGridSize(QSize(160,200));self.pages.setResizeMode(QListWidget.Adjust);self.pages.setDragDropMode(QAbstractItemView.InternalMove);self.pages.setMovement(QListWidget.Snap);self.pages.setSelectionMode(QAbstractItemView.ExtendedSelection);layout.addWidget(self.pages,1)
        for number in range(1,count+1):
            item=QListWidgetItem(f'Page {number}');item.setData(Qt.UserRole,(number,0));self.pages.addItem(item);self.items[number]=item
        row=QHBoxLayout();layout.addLayout(row)
        for label,callback in [('Move up',lambda:self.move(-1)),('Move down',lambda:self.move(1)),('Rotate left',lambda:self.rotate(270)),('Rotate right',lambda:self.rotate(90)),('Remove from output',self.remove),('Select range',self.select_range)]:
            button=QPushButton(label);button.clicked.connect(lambda checked=False,cb=callback:self.report(cb));row.addWidget(button)
        row=QHBoxLayout();layout.addLayout(row)
        for label,callback in [('Save arranged PDF',self.save_all),('Extract selection',self.extract),('Split into pages',self.split),('Split by ranges',self.ranges),('Combine PDFs',self.combine)]:
            button=QPushButton(label);button.clicked.connect(lambda checked=False,cb=callback:self.report(cb));row.addWidget(button)
        self.message=QLabel('Loading page previews…');layout.addWidget(self.message)
        self.timer=QTimer(self);self.timer.timeout.connect(self.thumbnail);self.timer.start(10)
    def report(self,callback):
        try:callback()
        except Exception as error:QMessageBox.warning(self,'Document pages',str(error))
    def thumbnail(self):
        if self.thumb_index>=self.total:self.timer.stop();self.message.setText('Ready · source document unchanged');return
        try:
            if self.pdf is None:
                import pypdfium2
                self.pdf=pypdfium2.PdfDocument(str(self.source))
            index=self.thumb_index;self.thumb_index+=1;item=self.items.get(index+1)
            if item is None:return
            number,rotation=item.data(Qt.UserRole)
            page=self.pdf[number-1];bitmap=page.render(scale=125/max(1,page.get_width()))
            try:
                image=bitmap.to_pil().convert('RGBA');qimage=QImage(image.tobytes(),image.width,image.height,QImage.Format_RGBA8888).copy();pixmap=QPixmap.fromImage(qimage);self.pixmaps[number]=pixmap;item.setIcon(QIcon(pixmap.transformed(QTransform().rotate(rotation))))
            finally:bitmap.close();page.close()
        except Exception:self.timer.stop();self.message.setText('Preview unavailable. Page organization and export remain available.')
    def records(self,selected=False):return [self.pages.item(i).data(Qt.UserRole) for i in range(self.pages.count()) if not selected or self.pages.item(i).isSelected()]
    def move(self,direction):
        indices=[i for i in range(self.pages.count()) if self.pages.item(i).isSelected()]
        for index in indices if direction<0 else reversed(indices):
            target=index+direction
            if 0<=target<self.pages.count() and target not in indices:
                item=self.pages.takeItem(index);self.pages.insertItem(target,item);item.setSelected(True)
    def rotate(self,angle):
        for item in self.pages.selectedItems():
            page,rotation=item.data(Qt.UserRole);rotation=(rotation+angle)%360;item.setData(Qt.UserRole,(page,rotation));item.setText(f'Page {page} · {rotation}°')
            if page in self.pixmaps:item.setIcon(QIcon(self.pixmaps[page].transformed(QTransform().rotate(rotation))))
    def remove(self):
        selected=self.pages.selectedItems()
        if len(selected)==self.pages.count():raise ValueError('Keep at least one page in the output.')
        for item in selected:self.items.pop(item.data(Qt.UserRole)[0],None);self.pages.takeItem(self.pages.row(item))
    def select_range(self):
        text,ok=QInputDialog.getText(self,'Select pages','Original page numbers, for example 1-3,5:')
        if ok:
            chosen=set(page_range(text,len(PdfReader(str(self.source)).pages)))
            for i in range(self.pages.count()):self.pages.item(i).setSelected(self.pages.item(i).data(Qt.UserRole)[0] in chosen)
    def output(self,label):
        name,_=QFileDialog.getSaveFileName(self,label,str(self.source.with_name(self.source.stem+'-organized.pdf')),'PDF (*.pdf)');return Path(name) if name else None
    def save_all(self):
        path=self.output('Save arranged PDF')
        if path:write_pages(self.source,path,self.records());self.message.setText('Saved '+str(path))
    def extract(self):
        records=self.records(True)
        if not records:raise ValueError('Select the pages to extract.')
        path=self.output('Extract selected pages')
        if path:write_pages(self.source,path,records);self.message.setText('Extracted '+str(path))
    def split(self):
        folder=QFileDialog.getExistingDirectory(self,'Choose parent folder for split pages')
        if not folder:return
        target=Path(folder)/(self.source.stem+'-split');index=2
        while target.exists():target=Path(folder)/(self.source.stem+f'-split-{index}');index+=1
        split_groups(self.source,target,[[record] for record in self.records()]);self.message.setText('Created '+str(target))
    def ranges(self):
        text,ok=QInputDialog.getText(self,'Split by ranges','Groups in current output order; separate files with semicolons (1-3;4-6):')
        if not ok:return
        records=self.records();groups=[[records[n-1] for n in page_range(group,len(records))] for group in text.split(';')]
        folder=QFileDialog.getExistingDirectory(self,'Choose parent folder')
        if folder:
            target=Path(folder)/(self.source.stem+'-parts');index=2
            while target.exists():target=Path(folder)/(self.source.stem+f'-parts-{index}');index+=1
            split_groups(self.source,target,groups);self.message.setText('Created '+str(target))
    def combine(self):
        names,_=QFileDialog.getOpenFileNames(self,'Select PDFs to combine in this order','','PDF (*.pdf)')
        if not names:return
        path=self.output('Save combined PDF')
        if path:
            from converter import pdf_merge
            pdf_merge([Path(n) for n in names],path);self.message.setText('Combined '+str(path))
    def closeEvent(self,event):
        self.timer.stop()
        if self.pdf is not None:self.pdf.close();self.pdf=None
        super().closeEvent(event)
