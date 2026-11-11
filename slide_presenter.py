"""Synchronized audience/presenter windows and native custom shows."""
import time
from pptx.oxml.xmlchemy import OxmlElement
from PySide6.QtCore import QTimer,Qt,QRectF
from PySide6.QtGui import QGuiApplication,QPixmap,QImage,QPainter
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QTextEdit,QComboBox,QCheckBox,
    QDoubleSpinBox,QPushButton,QInputDialog,QSizePolicy)
from slide_rendering import P,R


def custom_shows(deck):
    identifiers={node.rId:i for i,node in enumerate(deck.slides._sldIdLst)};result={}
    for show in deck.part._element.findall('p:custShowLst/p:custShow',{'p':P}):
        result[show.get('name','Custom show')]=[identifiers[node.get('{'+R+'}id')] for node in show.findall('p:sldLst/p:sld',{'p':P}) if node.get('{'+R+'}id') in identifiers]
    return result


def set_custom_show(deck,name,order):
    name=name.strip()
    if not name or len(name)>120 or not order or len(order)>10000 or any(not isinstance(i,int) or not 0<=i<len(deck.slides) for i in order):raise ValueError('Use a name and a sequence of existing slide numbers.')
    root=deck.part._element;listing=root.find('p:custShowLst',{'p':P})
    if listing is None:
        listing=OxmlElement('p:custShowLst');following=next((node for node in root if node.tag in ('{'+P+'}photoAlbum','{'+P+'}custDataLst','{'+P+'}kinsoku','{'+P+'}defaultTextStyle','{'+P+'}modifyVerifier','{'+P+'}extLst')),None)
        root.insert(list(root).index(following) if following is not None else len(root),listing)
    existing=next((node for node in listing if node.get('name')==name),None)
    identifier=existing.get('id') if existing is not None else str(max((int(node.get('id','0')) for node in listing),default=0)+1)
    if existing is not None:listing.remove(existing)
    show=OxmlElement('p:custShow');show.set('name',name);show.set('id',identifier);slides=OxmlElement('p:sldLst');show.append(slides)
    for index in order:node=OxmlElement('p:sld');node.set('{'+R+'}id',deck.slides._sldIdLst[index].rId);slides.append(node)
    listing.append(show)


def custom_show_dialog(editor):
    name,ok=QInputDialog.getText(editor,'Create or update custom show','Show name')
    if not ok:return
    current=custom_shows(editor.deck).get(name,list(range(len(editor.deck.slides))))
    text,ok=QInputDialog.getText(editor,'Custom slide sequence','Slide numbers, separated by commas (repeats allowed)',text=', '.join(str(i+1) for i in current))
    if ok:
        try:order=[int(part.strip())-1 for part in text.split(',')]
        except ValueError:raise ValueError('Use slide numbers separated by commas.') from None
        editor.change(lambda:set_custom_show(editor.deck,name,order))


def presenter_view(editor):
    existing=getattr(editor,'presenter_window',None)
    if existing is not None and existing.isVisible():existing.raise_();existing.activateWindow();return existing
    dialog=QDialog(editor);dialog.setWindowTitle('Dazzle · Presenter view');dialog.resize(1080,760);layout=QVBoxLayout(dialog);settings=QHBoxLayout();layout.addLayout(settings)
    screens=QGuiApplication.screens();monitor=QComboBox();monitor.setAccessibleName('Audience monitor')
    if screens:
        available=screens[0].availableGeometry();dialog.resize(min(1080,available.width()-60),min(760,available.height()-60))
    for i,screen in enumerate(screens):monitor.addItem(f'{i+1}: {screen.name()} · {screen.size().width()}×{screen.size().height()}')
    monitor.setCurrentIndex(1 if len(screens)>1 else 0);settings.addWidget(monitor)
    fullscreen=QCheckBox('Full screen audience');fullscreen.setChecked(len(screens)>1);settings.addWidget(fullscreen)
    shows=QComboBox();shows.setAccessibleName('Slide sequence');shows.addItem('All visible slides',None)
    for name,order in custom_shows(editor.deck).items():shows.addItem(name,order)
    settings.addWidget(shows);kiosk=QCheckBox('Kiosk / timed');settings.addWidget(kiosk);loop=QCheckBox('Loop');settings.addWidget(loop);hold=QDoubleSpinBox();hold.setRange(1,3600);hold.setValue(5);hold.setSuffix(' s / slide');hold.setAccessibleName('Default timed slide duration');settings.addWidget(hold)
    status=QLabel();layout.addWidget(status);previews=QHBoxLayout();layout.addLayout(previews);current=QLabel();upcoming=QLabel()
    for label in (current,upcoming):label.setMinimumSize(300,180);label.setAlignment(Qt.AlignCenter);label.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Expanding);previews.addWidget(label)
    notes=QTextEdit();notes.setReadOnly(True);notes.setAccessibleName('Current slide speaker notes');layout.addWidget(notes)
    layout.addWidget(QLabel('Audience and notes stay synchronized. P toggles temporary ink; E clears it; Escape ends the show. Editing the document does not change an active show.'))
    row=QHBoxLayout();layout.addLayout(row);state={'show':None,'started':None,'next':None,'image':None,'current':None,'current_image':None}
    def preview(index,deck):
        image=QImage(960,max(1,round(960*deck.slide_height/deck.slide_width)),QImage.Format_ARGB32);image.fill(Qt.transparent);painter=QPainter(image);scene=editor.make_scene(index,False,deck)
        try:scene.render(painter,QRectF(image.rect()),scene.sceneRect())
        finally:painter.end();scene.clear();scene.deleteLater()
        return QPixmap.fromImage(image)
    def refresh():
        show=state['show'];active=show is not None and show.isVisible();index=show.index if active else editor.index;deck=show.deck if active else editor.deck
        elapsed=int(time.monotonic()-state['started']) if active and state['started'] else 0;status.setText(f'Slide {index+1} of {len(deck.slides)} · {elapsed//60:02}:{elapsed%60:02} · '+('Presenting' if active else 'Ready'))
        if active:current.setPixmap(show.viewport().grab().scaled(current.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
        else:
            key=(id(deck),index,editor.preview_revision)
            if key!=state['current']:state['current']=key;state['current_image']=preview(index,deck)
            current.setPixmap(state['current_image'].scaled(current.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
        sequence=show.order if active else list(range(len(deck.slides)));position=show.position if active else sequence.index(index);next_index=sequence[position+1] if position+1<len(sequence) else sequence[0] if active and show.loop else None
        key=(id(deck),next_index)
        if key!=state['next']:
            state['next']=key;state['image']=None
            if next_index is not None:
                state['image']=preview(next_index,deck)
        if state['image'] is not None:upcoming.setPixmap(state['image'].scaled(upcoming.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
        else:upcoming.clear();upcoming.setText('End of presentation')
        slide=deck.slides[index];frame=slide.notes_slide.notes_text_frame if slide.has_notes_slide else None;value=frame.text if frame else 'No speaker notes.'
        if notes.toPlainText()!=value:notes.setPlainText(value)
    def stop():
        show=state['show']
        if show is not None and show.isVisible():show.close()
        state['show']=None
    def start():
        from dazzle import SlideShow
        if not screens or monitor.currentIndex()<0 or screens[monitor.currentIndex()] not in QGuiApplication.screens():raise ValueError('The selected monitor is no longer connected.')
        stop();editor._store();order=shows.currentData()
        if order is None:order=[i for i,slide in enumerate(editor.deck.slides) if slide._element.get('show')!='0']
        show=SlideShow(editor,editor.index,order=order,loop=loop.isChecked(),kiosk=kiosk.isChecked(),hold=hold.value(),screen=screens[monitor.currentIndex()],fullscreen=fullscreen.isChecked());state['show']=show;state['started']=time.monotonic();state['next']=None;show.slide_changed.connect(lambda _:refresh());refresh()
    def control(action):
        show=state['show']
        if show is not None and show.isVisible():action(show);refresh()
    def ink(show):show.ink_active=not show.ink_active
    def clear(show):show.ink=[];show.viewport().update()
    for text,callback in [('Start audience',lambda:editor.report(start)),('Previous',lambda:control(lambda s:s.previous())),('Next / build',lambda:control(lambda s:s.advance())),('Blackout',lambda:control(lambda s:s.toggle_blackout())),('Ink on/off',lambda:control(ink)),('Clear ink',lambda:control(clear)),('Zoom in',lambda:control(lambda s:s.scale(1.25,1.25))),('Fit',lambda:control(lambda s:s.fitInView(s.sceneRect(),Qt.KeepAspectRatio))),('End show',stop),('Close',dialog.close)]:button=QPushButton(text);button.clicked.connect(callback);row.addWidget(button)
    timer=QTimer(dialog);timer.timeout.connect(refresh);timer.start(250);dialog.finished.connect(stop);editor.presenter_window=dialog;dialog.show();refresh();return dialog
