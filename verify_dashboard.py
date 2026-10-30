"""Run the real bundled React screen and native bridge with temporary local files."""
import json
import os
import sys
from pathlib import Path
import tempfile
import time
from unittest.mock import patch


def run(screenshot_dir=None):
    if not screenshot_dir:
        if sys.platform != 'darwin':
            os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu')
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt, QUrl
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    from PySide6.QtWidgets import QApplication, QFileDialog
    from app import Window, VERSION
    from desktop_dashboard import install, ASSETS
    from PIL import Image
    from docx import Document

    application = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as folder:
        owner = Window()
        owner.settings = QSettings(str(Path(folder) / 'settings.ini'), QSettings.IniFormat)
        view = install(owner)
        owner.show()

        def wait(condition, seconds=30):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                application.processEvents()
                if condition():
                    return
                time.sleep(.01)
            raise AssertionError('Dashboard check timed out')

        def javascript(source):
            result = []
            view.page().runJavaScript(source, lambda value: result.append(value))
            wait(lambda: bool(result))
            return result[0]

        def settle():
            deadline = time.monotonic() + .7
            while time.monotonic() < deadline:
                application.processEvents()
                time.sleep(.01)

        loaded = []
        owner.dashboard_bridge.stateChanged.connect(loaded.append)
        wait(lambda: bool(loaded))
        text = javascript('document.body.innerText')
        assert 'What are we making?' in text and 'Local workspace' in text
        assert 'Sample recent files' not in text and 'Dashboard preview' not in text
        assert javascript('document.querySelectorAll(".tool-card").length') == 9
        assert javascript('document.querySelector("img").naturalWidth > 0')
        # Send an actual DOM click through QWebChannel into the existing editor.
        javascript('[...document.querySelectorAll("nav button")].find(b => b.innerText === "Pages").click()')
        wait(lambda: 'Pages' in owner.workspaces)
        assert owner.workspaces['Pages'].isVisible()
        owner.workspaces['Pages'].close()

        picture = Path(folder) / 'Harbor poster.png'
        Image.new('RGB', (40, 30), '#9457ff').save(picture)
        with patch.object(QFileDialog, 'getOpenFileNames', return_value=([str(picture)], '')):
            owner.dashboard_bridge.chooseFiles('convert')
        assert picture.resolve() in owner.paths
        assert owner.centralWidget().currentWidget() is not view
        wait(lambda: owner.preview_worker is None)
        owner.dashboard_home()
        assert owner.centralWidget().currentWidget() is view
        owner.dashboard_bridge.openRecent(str(picture))
        assert owner.centralWidget().currentWidget() is not view
        owner.dashboard_home()
        owner.dashboard_bridge.clearRecent()
        assert not owner.dashboard_bridge.recent

        # Navigation outside the bundled page must not acquire the native bridge.
        assert not view.page().acceptNavigationRequest(QUrl('https://example.com'), 0, True)
        assert not view.page().acceptNavigationRequest(QUrl.fromLocalFile(str(picture)), 0, True)
        assert view.page().acceptNavigationRequest(QUrl.fromLocalFile(str(ASSETS / 'index.html')), 0, True)
        assert javascript('document.documentElement.scrollWidth <= innerWidth')
        owner.resize(1280, 720)
        settle()
        assert javascript('document.documentElement.scrollWidth <= innerWidth')
        assert javascript('document.querySelector("main").getBoundingClientRect().right <= innerWidth + 1')

        if screenshot_dir:
            output = Path(screenshot_dir)
            output.mkdir(parents=True, exist_ok=True)
            owner.activateWindow()
            settle()
            owner.grab().save(str(output / 'dashboard-compact-029.png'))
            owner.resize(1440, 900)
            settle()
            owner.grab().save(str(output / 'dashboard-native-029.png'))
            owner.dashboard_bridge.launch('tables')
            application.processEvents()
            owner.workspaces['Tables'].grab().save(str(output / 'dashboard-tables-029.png'))
            owner.workspaces['Tables'].close()

        wait(lambda: owner.preview_worker is None)
        owner.close()
        application.processEvents()
        # Destroy the page before its off-the-record profile.
        view.page().deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    print(json.dumps({'version': VERSION, 'dashboard': 'passed', 'native_bridge': 'passed',
                      'file_queue': 'passed', 'local_navigation': 'passed', 'responsive': 'passed'}))


if __name__ == '__main__':
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else None)
