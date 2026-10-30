"""Offline React Home screen, connected to the existing native workspaces."""

import json
from pathlib import Path

from PySide6.QtCore import QObject, QEvent, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import QFileDialog, QMessageBox, QStackedWidget, QToolBar
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (QWebEnginePage, QWebEngineProfile,
                                    QWebEngineSettings, QWebEngineUrlRequestInterceptor)
from PySide6.QtWebEngineWidgets import QWebEngineView

ASSETS = Path(__file__).resolve().parent / 'assets' / 'dashboard'
WORKSPACES = {'pages': 'Pages', 'tables': 'Tables', 'dazzle': 'Dazzle',
              'sketch': 'Sketch', 'organize': 'Organize', 'formulaic': 'Formulaic'}


class LocalRequests(QWebEngineUrlRequestInterceptor):
    def interceptRequest(self, info):
        url = info.requestUrl()
        allowed = url.scheme() in {'qrc', 'data'}
        if url.isLocalFile():
            allowed = Path(url.toLocalFile()).resolve().is_relative_to(ASSETS)
        info.block(not allowed)


class LocalPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        return url.isLocalFile() and Path(url.toLocalFile()).resolve() == ASSETS / 'index.html'

    def createWindow(self, window_type):
        return None


class DashboardBridge(QObject):
    stateChanged = Signal(str)

    def __init__(self, owner, show_converter):
        super().__init__(owner)
        self.owner = owner
        self.show_converter = show_converter
        self.message = 'Ready when you are.'
        saved = owner.settings.value('dashboard/recent', [])
        self.recent = [str(path) for path in saved] if isinstance(saved, list) else []

    def _publish(self):
        from windows_integration import WORKSPACE_EXTENSIONS
        files = []
        for name in self.recent:
            path = Path(name)
            try:
                size = path.stat().st_size
                if not path.is_file():
                    continue
            except OSError:
                continue
            tool = next((workspace.lower() for workspace, extensions in WORKSPACE_EXTENSIONS.items()
                         if path.suffix.lower() in extensions), 'convert')
            files.append({'id': name, 'name': path.name, 'size': f'{size / 1048576:.1f} MB',
                          'tool': tool, 'modified': 'Recently opened'})
        self.stateChanged.emit(json.dumps({'files': files, 'status': self.message}))

    def remember(self, paths):
        names = [str(path.resolve()) for path in paths if path.is_file()]
        self.recent = list(dict.fromkeys(names + self.recent))[:12]
        self.owner.settings.setValue('dashboard/recent', self.recent)
        self._publish()

    @Slot()
    def ready(self):
        self._publish()

    @Slot()
    def clearRecent(self):
        self.recent = []
        self.owner.settings.setValue('dashboard/recent', [])
        self._publish()

    @Slot(str)
    def launch(self, tool):
        try:
            if tool == 'convert':
                self.show_converter()
            elif tool in WORKSPACES:
                self.owner._open_workspace(WORKSPACES[tool])
            elif tool == 'writer':
                self.owner._screenwriter()
            elif tool == 'play':
                self.owner._watchit()
            else:
                raise ValueError('Choose a tool from the workspace navigation.')
        except Exception as error:
            self._error(error)

    def _error(self, error):
        self.message = f'Could not open workspace: {error}. Try again or choose another file.'
        self._publish()
        QMessageBox.warning(self.owner, 'Could not open workspace', self.message)

    @Slot(str)
    def chooseFiles(self, mode):
        if mode not in {'convert', 'play', 'open'}:
            return
        from windows_integration import WORKSPACE_EXTENSIONS
        file_filter = 'All files (*)'
        if mode == 'play':
            patterns = ' '.join('*' + ext for ext in sorted(WORKSPACE_EXTENSIONS['Play']))
            file_filter = f'Media ({patterns})'
        names, _ = QFileDialog.getOpenFileNames(self.owner, 'Choose local files',
                                               str(self.owner.output_dir), file_filter)
        if names:
            self.open_paths([Path(name) for name in names], mode)

    def open_paths(self, paths, mode='convert'):
        try:
            paths = [path.resolve() for path in paths if path.is_file()]
            if not paths:
                raise ValueError('No readable files selected')
            if mode == 'convert':
                if self.owner.worker and self.owner.worker.isRunning():
                    raise ValueError('Wait for the current conversion to finish before adding files')
                self.show_converter()
                self.owner._add_files(paths)
                paths = [path for path in paths if path in self.owner.paths]
            elif mode == 'play':
                self.owner._queue_play(paths)
            else:
                self.owner.open_arguments([str(path) for path in paths])
                if any(path in self.owner.paths for path in paths):
                    self.show_converter()
            self.remember(paths)
        except Exception as error:
            self._error(error)

    @Slot(str)
    def openRecent(self, name):
        # Only paths already selected through a native dialog/drop can be reopened.
        if name not in self.recent:
            return
        path = Path(name)
        if not path.is_file():
            self.message = 'File moved or missing. Use Open file to locate it again.'
            self._publish()
            return
        self.open_paths([path], 'open')


class DashboardView(QWebEngineView):
    def eventFilter(self, watched, event):
        if event.type() in {QEvent.DragEnter, QEvent.DragMove, QEvent.Drop} and event.mimeData().hasUrls():
            paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
            if paths:
                event.acceptProposedAction()
                if event.type() == QEvent.Drop:
                    self.bridge.open_paths(paths)
                return True
        return super().eventFilter(watched, event)


def install(owner):
    """Install Home without replacing or duplicating any native editor logic."""
    if not (ASSETS / 'index.html').is_file():
        raise FileNotFoundError('Build the dashboard first: cd dashboard; npm ci; npm run build')
    original = owner.takeCentralWidget()
    stack = QStackedWidget(owner)
    view = DashboardView(stack)
    profile = QWebEngineProfile(view)  # Off-the-record; no browser history/cookie store.
    interceptor = LocalRequests(profile)
    profile.setUrlRequestInterceptor(interceptor)
    page = LocalPage(profile, view)
    page.setBackgroundColor(QColor('#101014'))
    page.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
    page.settings().setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, False)
    view.setPage(page)
    stack.addWidget(view)
    stack.addWidget(original)
    owner.setCentralWidget(stack)
    toolbars = owner.findChildren(QToolBar)

    def show_converter():
        stack.setCurrentWidget(original)
        for toolbar in toolbars:
            toolbar.show()

    def show_home():
        stack.setCurrentWidget(view)
        for toolbar in toolbars:
            toolbar.hide()
        view.setFocus()

    bridge = DashboardBridge(owner, show_converter)
    view.bridge = bridge
    channel = QWebChannel(page)
    channel.registerObject('desktop', bridge)
    page.setWebChannel(channel)
    # Qt setters keep C++ pointers; retain Python overrides for the view's lifetime.
    view.local_profile = profile
    view.local_requests = interceptor
    view.local_page = page
    view.local_channel = channel
    view.loadFinished.connect(lambda ok: view.focusProxy().installEventFilter(view) if ok and view.focusProxy() else None)
    view.load(QUrl.fromLocalFile(str(ASSETS / 'index.html')))
    home_action = QAction('Home', owner)
    home_action.setShortcut('Ctrl+Shift+H')
    home_action.triggered.connect(show_home)
    owner.menuBar().insertAction(owner.menuBar().actions()[0], home_action)
    owner.dashboard = view
    owner.dashboard_bridge = bridge
    owner.dashboard_home = show_home
    owner.dashboard_converter = show_converter
    owner.resize(1440, 900)
    show_home()
    return view
