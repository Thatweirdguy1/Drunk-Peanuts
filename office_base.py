"""Shared native Office workspace and file actions."""
from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox, QToolBar
from ui import action as icon_action, editor_theme, refresh_icons

def button(bar, label, callback):
    files = {"New", "Open", "Save", "Save as", "PDF", "New database", "Open database", "Save changes", "Import CSV", "Export CSV"}
    group = "file" if label in files else "edit" if label in {"Undo", "Redo", "Cut", "Copy", "Paste"} else "tools"
    previous = [item for item in bar.actions() if item.property("iconGroup")]
    if previous and previous[-1].property("iconGroup") != group:
        bar.addSeparator()
    item = icon_action(bar, label, lambda: callback())
    item.setProperty("iconGroup", group)
    window = bar.parentWidget()
    if isinstance(window, Workspace):
        window.menus["File" if group == "file" else "Edit"].addAction(item)
    return item


def pick_open(parent, label, filters):
    name, _ = QFileDialog.getOpenFileName(parent, label, "", filters)
    return Path(name) if name else None


def pick_save(parent, label, filters):
    name, _ = QFileDialog.getSaveFileName(parent, label, "", filters)
    return Path(name) if name else None


class Workspace(QMainWindow):
    def __init__(self, name):
        super().__init__()
        self.setWindowTitle(f"{name} · Drunk Peanuts")
        self.resize(1100, 750)
        self.path = None
        self.dirty = False
        self.toolbar = QToolBar(name)
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.toolbar.setIconSize(QSize(18, 18))
        self.addToolBar(self.toolbar)
        self.menus = {name: self.menuBar().addMenu(name) for name in ("File", "Edit")}
        self._theme()
        QApplication.instance().styleHints().colorSchemeChanged.connect(self._theme)

    def _theme(self, *_):
        self.setStyleSheet(editor_theme())
        refresh_icons(self)

    def report(self, operation):
        try:
            operation()
        except Exception as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))

    def showEvent(self,event):
        from office_ribbon import install_ribbon
        install_ribbon(self)
        super().showEvent(event)

    def discard_changes(self):
        return not self.dirty or QMessageBox.question(
            self, "Unsaved changes", "Discard unsaved changes?", QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes

    def closeEvent(self, event):
        event.accept() if self.discard_changes() else event.ignore()


