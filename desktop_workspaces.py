"""React workspace chrome around the existing, lossless native editing engines."""
import json
import math
from pathlib import Path

from PySide6.QtCore import QObject, QRect, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDockWidget, QMainWindow, QMessageBox, QToolBar,
                               QVBoxLayout, QWidget, QWidgetAction)
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from desktop_dashboard import ASSETS, LocalPage, LocalRequests


class WorkspaceBridge(QObject):
    stateChanged = Signal(str)

    def __init__(self, owner, window, tool, host, view):
        super().__init__(window)
        self.owner, self.window, self.tool = owner, window, tool
        self.host, self.view = host, view
        self.actions, self.groups = [], []
        self.last = None
        self.bounds = None
        self.selection = 0
        self.message = ''
        def collect(menu, group):
            for action in menu.actions():
                if action.menu():
                    collect(action.menu(), group + ' / ' + action.text().replace('&', ''))
                elif not action.isSeparator() and not isinstance(action, QWidgetAction) and action not in self.actions:
                    self.actions.append(action)
                    self.groups.append(group)
                    window.addAction(action)
        for action in window.menuBar().actions():
            if action.menu():collect(action.menu(), action.text().replace('&', ''))
        for bar in window.findChildren(QToolBar, options=Qt.FindDirectChildrenOnly):
            collect(bar, 'Tools')
            bar.hide()
        window.menuBar().hide()
        window.statusBar().hide()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.publish)
        self.timer.start(350)

    def state(self):
        w, tool = self.window, self.tool
        editor = getattr(w, 'editor', getattr(w, 'source', None))
        dirty = editor.document().isModified() if editor is not None else getattr(w, 'dirty', False)
        path = getattr(w, 'path', None)
        imported = next((getattr(w, key, None) for key in ('imported_docx','imported_xlsx','imported_pptx','imported_image') if getattr(w,key,None)), None)
        state = dict(tool=tool, native=True, name=Path(path or imported).name if path or imported else 'Untitled',
                     saved=bool(path), imported=bool(imported and not path),
                     dirty=dirty, status=self.message or w.statusBar().currentMessage(),
                     actions=[dict(id=str(i), label=a.text().replace('&', ''), group=self.groups[i],
                                   enabled=a.isEnabled(), checked=a.isCheckable() and a.isChecked(),
                                   shortcut=a.shortcut().toString()) for i,a in enumerate(self.actions)],
                     docks=bool(self.host.findChildren(QDockWidget)), items=[], current=-1)
        if tool == 'pages':
            state.update(font=w.font_family.currentText(), size=w.font_size.value(), words=len(w.editor.toPlainText().split()))
        if tool == 'tables':state.update(address=w.cell_address.text(), formula=w.formula.text())
        if tool == 'dazzle':
            shape=w.selected_shape()
            state.update(previewRevision=w.preview_revision,slideAspect=w.deck.slide_width/w.deck.slide_height,
                         textSelected=bool(shape is not None and shape.has_text_frame),font=w.font_family.currentText(),size=w.font_size.value())
        listing = getattr(w, {'writer':'scenes','organize':'tables','dazzle':'list'}.get(tool,''), None)
        if listing is not None:
            state.update(items=[listing.item(i).text() for i in range(listing.count())], current=listing.currentRow())
        if tool == 'writer':
            state.update(elements=[w.element.itemText(i) for i in range(w.element.count())], element=w.element.currentIndex(), words=len(w.editor.toPlainText().split()))
        if tool == 'sketch':state.update(color=w.canvas.color.name(), size=w.pen_size.value(), eraser=w.canvas.eraser)
        if tool == 'play':
            for widget in (w.heading,w.seek,w.time_label,w.transport,w.volume_controls,w.playlist,w.playlist_tools):widget.hide()
            w.statusBar().hide()
            player = w.player
            state.update(name=w.files[w.index].name if 0 <= w.index < len(w.files) else 'Your local cinema',
                         items=[p.name for p in w.files], current=w.index, volume=w.volume.value(),
                         muted=w.mute.isChecked(), seek=w.seek.value(), time=w.time_label.text(),
                         playing=bool(player and player.is_playing()), pip=w._pip_state is not None,
                         fullscreen=w.isFullScreen(), ready=player is not None)
        return state

    @Slot()
    def ready(self):
        self.last = None
        self.publish()

    @Slot(int,result=str)
    def thumbnail(self,index):
        if self.tool!='dazzle':return ''
        try:return self.window.thumbnail(index)
        except (ValueError,RuntimeError,IndexError,TypeError):return ''

    def publish(self):
        if not self.window.isVisible():return
        payload = json.dumps(self.state())
        if payload != self.last:
            self.last = payload
            self.stateChanged.emit(payload)

    @Slot(str)
    def launch(self, tool):
        if tool == self.tool:return
        if tool == 'home':
            self.owner.dashboard_home()
            self.owner.show();self.owner.raise_();self.owner.activateWindow()
        else:self.owner.dashboard_bridge.launch(tool)

    @Slot(str)
    def trigger(self, identifier):
        if identifier.isdigit() and 0 <= int(identifier) < len(self.actions):
            action = self.actions[int(identifier)]
            if action.isEnabled():action.trigger()
            self.publish()

    @Slot(str)
    def command(self, payload):
        try:
            data = json.loads(payload)
            key, value = data.get('key'), data.get('value')
            w = self.window
            if key == 'inspect':
                docks = self.host.findChildren(QDockWidget)
                show = not any(not dock.isHidden() for dock in docks)
                for dock in docks:dock.setVisible(show)
            elif key == 'select' and self.tool in {'writer','organize','dazzle'}:
                listing = getattr(w, {'writer':'scenes','organize':'tables','dazzle':'list'}[self.tool])
                index = int(value)
                if 0 <= index < listing.count():
                    listing.setCurrentRow(index)
                    if self.tool == 'writer':w._jump(listing.item(index))
            elif self.tool == 'pages':
                if key == 'font' and value in [w.font_family.itemText(i) for i in range(w.font_family.count())]:w.font_family.setCurrentText(value)
                elif key == 'size':w.font_size.setValue(max(6,min(96,int(value))))
            elif self.tool == 'dazzle':
                if key == 'font' and value in [w.font_family.itemText(i) for i in range(w.font_family.count())]:w.format_object(name=value)
                elif key == 'size':w.format_object(size=max(6,min(180,float(value))))
            elif self.tool == 'tables' and key == 'formula' and isinstance(value,str) and len(value) <= 32767:
                w.formula.setText(value);w._apply_formula()
            elif self.tool == 'writer':
                if key == 'element' and 0 <= int(value) < w.element.count():
                    w.element.setCurrentIndex(int(value));w._apply_element(int(value))
                elif key == 'preview':w.preview.setVisible(w.preview.isHidden())
                elif key == 'emphasis' and value in {'**','*','_'}:w._emphasize(value)
                elif key == 'forward':w._forward_menu()
            elif self.tool == 'sketch':
                if key == 'size':w.pen_size.setValue(max(1,min(60,int(value))))
                elif key == 'color' and isinstance(value,str) and QColor(value).isValid():
                    w.canvas.color=QColor(value);w.canvas.eraser=False
                elif key == 'pen':w.canvas.eraser=False
            elif self.tool == 'play':
                callbacks = {'toggle':w.toggle,'previous':w.previous,'next':w.next,'stop':w.stop,
                             'open':w.open_files,'add':w.enqueue_files,'folder':w.add_folder,'openList':w.open_playlist,
                             'saveList':w.save_playlist,'clear':w.clear_playlist,'mute':w.mute.click,
                             'pip':w.picture_in_picture,'fullscreen':w.fullscreen,'options':w.options_toggle.click}
                if key in callbacks:callbacks[key]()
                elif key == 'volume':w.volume.setValue(max(0,min(200,int(value))))
                elif key == 'seek' and w.player is not None:
                    w.seek.setValue(max(0,min(1000,int(value))));w._seek()
                elif key == 'select' and 0 <= int(value) < len(w.files):
                    self.selection=int(value);w.playlist.setCurrentRow(self.selection)
                elif key == 'playItem' and 0 <= int(value) < len(w.files):w._play(int(value))
                elif key in {'up','down','remove'}:
                    if 0 <= self.selection < len(w.files):
                        w.playlist.setCurrentRow(self.selection)
                        if key == 'remove':w.remove_selected()
                        else:
                            delta = -1 if key == 'up' else 1
                            w.move_selected(delta);self.selection=max(0,min(len(w.files)-1,self.selection+delta))
                elif key == 'reorder':
                    start, end = map(int,value)
                    if 0 <= start < len(w.files) and 0 <= end < len(w.files):
                        w.playlist.clearSelection();w.playlist.setCurrentRow(start)
                        for _ in range(abs(end-start)):w.move_selected(1 if end>start else -1)
                        self.selection=end
            self.publish()
        except (ValueError,TypeError,KeyError,OverflowError) as error:
            self.message=f'Could not apply change: {error}. Try again.'
            self.publish()

    @Slot(str)
    def canvas(self, payload):
        try:
            values = json.loads(payload)
            if len(values)!=4 or not all(isinstance(v,(float,int)) and math.isfinite(v) for v in values):return
            x,y,width,height = map(round,values)
            bounds=QRect(x,y,max(0,width),max(0,height)).intersected(self.view.rect())
            self.host.setGeometry(bounds.translated(self.view.pos()))
            self.host.setVisible(bounds.width()>0 and bounds.height()>0)
            self.host.raise_()
        except (ValueError,TypeError):return


def install(owner, window, tool):
    if getattr(window,'_react_shell',False):return window
    window._react_shell=True
    original=window.takeCentralWidget()
    root=QWidget(window)
    layout=QVBoxLayout(root);layout.setContentsMargins(0,0,0,0)
    view=QWebEngineView(root);layout.addWidget(view)
    host=QMainWindow(root);host.setWindowFlags(Qt.Widget)
    host.setAttribute(Qt.WA_NativeWindow)
    host.setCentralWidget(original)
    host.setStyleSheet('QMainWindow{background:#101014;}')
    for dock in window.findChildren(QDockWidget,options=Qt.FindDirectChildrenOnly):
        area=window.dockWidgetArea(dock);window.removeDockWidget(dock);host.addDockWidget(area,dock);dock.hide()
    window.setCentralWidget(root)
    if tool in {'writer','organize','dazzle'}:getattr(window,{'writer':'scenes','organize':'tables','dazzle':'list'}[tool]).hide()
    if tool == 'tables':
        row=original.layout().itemAt(0).layout()
        if row:
            for i in range(row.count()):
                if row.itemAt(i).widget():row.itemAt(i).widget().hide()
    if tool == 'formulaic' and original.layout().itemAt(0).widget():original.layout().itemAt(0).widget().hide()
    if tool == 'writer':window.status.hide()
    if tool == 'play':
        # Keep the original root/layout for native PiP geometry and stable VLC handles.
        for widget in (window.heading,window.seek,window.time_label,window.transport,window.volume_controls,window.playlist,window.playlist_tools):widget.hide()
        window.surface.setMinimumHeight(0)
    profile=QWebEngineProfile(view);requests=LocalRequests(profile);profile.setUrlRequestInterceptor(requests)
    page=LocalPage(profile,view);page.setBackgroundColor(QColor('#101014'))
    page.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls,False)
    page.settings().setAttribute(QWebEngineSettings.JavascriptCanOpenWindows,False)
    view.setPage(page)
    bridge=WorkspaceBridge(owner,window,tool,host,view)
    channel=QWebChannel(page);channel.registerObject('workspace',bridge);page.setWebChannel(channel)
    view.local_profile,view.local_requests,view.local_page,view.local_channel=profile,requests,page,channel
    url=QUrl.fromLocalFile(str(ASSETS/'index.html'));url.setQuery('workspace='+tool);view.load(url)
    window.frontend=view;window.frontend_bridge=bridge;window.frontend_host=host
    host.hide()
    available=window.screen().availableGeometry()
    window.resize(min(1440,available.width()-40),min(900,available.height()-64))
    window.move(available.center()-window.rect().center())
    return window
