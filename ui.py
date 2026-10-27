"""Shared, original vector icons and desktop editor styling."""

from weakref import ref

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt, QObject, QEvent, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QAction, QIcon, QPainter, QPixmap, QCursor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QAbstractButton, QPushButton, QToolButton, QComboBox, QTabBar, QFrame, QGraphicsOpacityEffect, QStyle


class HoverFeedback(QObject):
    """Fade a mouse-transparent highlight without blurring button text or icons."""
    def __init__(self, parent):
        super().__init__(parent)
        # Qt-created toolbar buttons otherwise lose their Python hover attributes.
        self._buttons = set()

    def _clear(self):
        button = self._hovered() if getattr(self, '_hovered', None) else None
        self._hovered = None
        if button is not None:
            try:
                button._hover_animation.stop()
                button._hover_animation.targetObject().setOpacity(0)
                button._hover_frame.hide()
                button.update()
            except RuntimeError:  # Qt may already have destroyed the previous window.
                pass

    def eventFilter(self, button, event):
        kind = event.type()
        hovered = self._hovered() if getattr(self, '_hovered', None) else None
        if kind in (QEvent.WindowDeactivate, QEvent.ApplicationDeactivate):
            self._clear()
        elif kind == QEvent.Enter and button is not hovered:
            # Child overlays must not keep a previous button highlighted.
            if not isinstance(button, QFrame) or button is not getattr(hovered, '_hover_frame', None):
                self._clear()
        if not isinstance(button, (QPushButton, QToolButton, QComboBox, QTabBar)):
            return False
        tabs = isinstance(button, QTabBar)
        if kind in (QEvent.Polish, QEvent.EnabledChange):
            button.setCursor(Qt.PointingHandCursor if button.isEnabled() else Qt.ArrowCursor)
            if tabs:
                button.setMouseTracking(True)
        frame = getattr(button, '_hover_frame', None)
        if kind == QEvent.Resize and frame is not None:
            frame.setGeometry(button.tabRect(button._hover_index) if tabs else button.rect())
        if kind not in (QEvent.Enter, QEvent.Leave, QEvent.Hide, QEvent.EnabledChange, QEvent.MouseMove):
            return False
        if kind == QEvent.MouseMove and not tabs:
            return False
        index = -1
        active = button.isEnabled() and kind in (QEvent.Enter, QEvent.MouseMove)
        if tabs and active:
            point = event.position().toPoint() if hasattr(event, 'position') else button.mapFromGlobal(QCursor.pos())
            index = button.tabAt(point)
            active = index >= 0 and button.isTabEnabled(index)
            button.setCursor(Qt.PointingHandCursor if active else Qt.ArrowCursor)
            if active and button is hovered and index == button._hover_index:
                return False
            if button is hovered:
                self._clear()
        if not active:
            if button is hovered:
                self._clear()
            return False
        animation = getattr(button, '_hover_animation', None)
        duration = min(160, max(0, button.style().styleHint(QStyle.SH_Widget_Animation_Duration, None, button)))
        animate = duration and button.style().styleHint(QStyle.SH_Widget_Animate, None, button)
        if not animate:
            if animation is not None:
                animation.stop()
                frame.hide()
            return False
        if animation is None:
            self._buttons.add(button)
            button.destroyed.connect(lambda: self._buttons.discard(button))
            frame = QFrame(button)
            frame.setAttribute(Qt.WA_TransparentForMouseEvents)
            frame.setStyleSheet('background: rgba(255, 221, 34, 25); border: 1px solid #a66ce0; border-radius: 3px;')
            effect = QGraphicsOpacityEffect(frame)
            effect.setOpacity(0)
            frame.setGraphicsEffect(effect)
            animation = QPropertyAnimation(effect, b'opacity', effect)
            animation.setEasingCurve(QEasingCurve.OutCubic)
            button._hover_animation = animation
            button._hover_frame = frame
        self._hovered = ref(button)
        button._hover_index = index
        effect = animation.targetObject()
        animation.stop()
        frame.setGeometry(button.tabRect(index) if tabs else button.rect())
        frame.show()
        frame.raise_()
        animation.setDuration(duration)
        animation.setStartValue(effect.opacity())
        animation.setEndValue(1.0)
        animation.start()
        return False


PATHS = {
    "strike": '<path d="M17 5c-8-5-15 4-5 7s4 12-5 6M2 12h20"/>',
    "superscript": '<path d="M3 11l9 10M12 11L3 21M15 4c0-4 7-4 7 0 0 2-7 5-7 7h7"/>',
    "subscript": '<path d="M3 4l9 10M12 4L3 14M15 14c0-4 7-4 7 0 0 2-7 5-7 7h7"/>',
    "highlight": '<path d="M6 14L16 3l5 5-11 10zM6 14l4 4-5 3H2zM2 23h20"/>',
    "chart": '<path d="M3 2v20h20M7 18v-5h3v5M13 18V8h3v10M19 18V4h3v14"/>',
    "new": '<path d="M14 3H5v18h14V8zM14 3v5h5M8 14h8M12 10v8"/>',
    "open": '<path d="M3 19V5h6l2 3h10l-3 11zM3 11h16"/>',
    "save": '<path d="M4 3h13l3 3v15H4zM8 3v6h8V3M8 21v-8h9v8"/>',
    "save-as": '<path d="M4 20V3h13l3 3v5M8 3v6h8V3M9 21l2-5 7-7 3 3-7 7z"/>',
    "export": '<path d="M14 3H5v18h14v-7M14 3v5h5M12 12h9M18 9l3 3-3 3"/>',
    "undo": '<path d="M4 10h10a6 6 0 0 1 0 12M4 10l5-5M4 10l5 5" transform="translate(0 -2)"/>',
    "redo": '<path d="M20 8H10a6 6 0 0 0 0 12M20 8l-5-5M20 8l-5 5"/>',
    "cut": '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M8 8l13 13M8 16L21 3"/>',
    "copy": '<rect x="8" y="8" width="12" height="13" rx="1"/><path d="M15 8V3H3v13h5"/>',
    "paste": '<path d="M8 5H4v16h16V5h-4M8 3h8v5H8zM8 12h8M8 16h6"/>',
    "bold": '<path d="M7 3h6a5 5 0 0 1 0 10H7zM7 13h7a4 4 0 0 1 0 8H7z" stroke-width="2.6"/>',
    "italic": '<path d="M10 3h9M5 21h9M15 3L9 21"/>',
    "underline": '<path d="M6 3v8a6 6 0 0 0 12 0V3M4 21h16"/>',
    "bullets": '<circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/><path d="M9 6h12M9 12h12M9 18h12"/>',
    "left": '<path d="M3 4h18M3 9h12M3 14h18M3 19h12"/>',
    "center": '<path d="M3 4h18M6 9h12M3 14h18M6 19h12"/>',
    "right": '<path d="M3 4h18M9 9h12M3 14h18M9 19h12"/>',
    "row": '<rect x="3" y="3" width="18" height="18" rx="1"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18M16 18h6M19 15v6"/>',
    "column": '<rect x="3" y="3" width="18" height="18" rx="1"/><path d="M9 3v18M15 3v18M3 9h18M3 15h18M18 16v6M15 19h6"/>',
    "calculate": '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M8 6h8M8 11h1M14 11h1M8 15h1M14 15h1M8 19h1M14 19h1"/>',
    "slide": '<rect x="2" y="4" width="20" height="14" rx="1"/><path d="M12 18v4M7 22h10M7 9h10M7 13h7"/>',
    "add": '<path d="M12 4v16M4 12h16"/>',
    "delete": '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7"/>',
    "pen": '<path d="M3 21l2-7L16 3l5 5L10 19zM13 6l5 5M3 21l7-2"/>',
    "color": '<path d="M12 2S4 10 4 15a8 8 0 0 0 16 0c0-5-8-13-8-13zM7 16a5 5 0 0 0 5 4"/>',
    "eraser": '<path d="M3 14L14 3l7 7-11 11H7zM8 9l7 7M10 21h11"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 4 18 4 18 0V5M3 12c0 4 18 4 18 0"/>',
    "table": '<rect x="2" y="3" width="20" height="18" rx="2"/><path d="M2 9h20M2 15h20M9 9v12M16 9v12"/>',
    "import": '<path d="M14 3H5v7M5 16v5h14V8l-5-5v5h5M2 13h11M9 9l4 4-4 4"/>',
    "find": '<circle cx="10" cy="10" r="7"/><path d="M15 15l7 7"/>',
    "title": '<path d="M3 5h18M12 5v16M8 21h8M3 5v4M21 5v4"/>',
    "map": '<path d="M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3zM9 3v15M15 6v15"/>',
    "timer": '<circle cx="12" cy="13" r="8"/><path d="M12 13V8M9 2h6M12 2v3M18 5l2-2"/>',
    "play": '<path d="M7 3l15 9L7 21z" fill="currentColor" stroke="none"/>',
    "pause": '<path d="M7 4v16M17 4v16" stroke-width="5"/>',
    "stop": '<rect x="5" y="5" width="14" height="14" rx="1" fill="currentColor" stroke="none"/>',
    "previous": '<path d="M5 4v16M20 4L7 12l13 8z"/>',
    "next": '<path d="M19 4v16M4 4l13 8-13 8z"/>',
    "fullscreen": '<path d="M3 9V3h6M15 3h6v6M21 15v6h-6M9 21H3v-6"/>',
    "restore": '<path d="M9 3v6H3M15 3v6h6M21 15h-6v6M3 15h6v6"/>',
    "volume": '<path d="M3 9h4l5-5v16l-5-5H3zM16 8a6 6 0 0 1 0 8M19 4a11 11 0 0 1 0 16"/>',
    "mute": '<path d="M3 9h4l5-5v16l-5-5H3zM16 8l6 8M22 8l-6 8"/>',
    "loop": '<path d="M4 8h13l-3-3M20 16H7l3 3M20 8v5M4 16v-5"/>',
    "playlist": '<path d="M3 5h12M3 11h12M3 17h8M18 12l5 5-5 5z"/>',
    "up": '<path d="M12 21V3M5 10l7-7 7 7"/>',
    "down": '<path d="M12 3v18M5 14l7 7 7-7"/>',
    "clear": '<path d="M5 5h14M5 12h9M5 19h9M17 16l5 5M22 16l-5 5"/>',
    "settings": '<path d="M4 4v16M12 4v16M20 4v16M1 8h6M9 16h6M17 9h6"/>',
}

NAMES = {
    "New": "new", "Open": "open", "Save": "save", "Save as": "save-as", "PDF": "export", "PNG": "export", "Export": "export",
    "Undo": "undo", "Redo": "redo", "Cut": "cut", "Copy": "copy", "Paste": "paste", "Bold": "bold", "Italic": "italic", "Underline": "underline", "B": "bold", "I": "italic", "U": "underline", "Bullets": "bullets",
    "Align left": "left", "Align center": "center", "Align right": "right", "Add row": "row", "Add column": "column", "Calculate selected": "calculate", "Add slide": "slide", "Delete slide": "delete", "Pen color": "color", "Eraser": "eraser", "Clear": "delete",
    "New database": "database", "Open database": "open", "New table": "table", "Add record": "add", "Delete record": "delete", "Save changes": "save", "Import CSV": "import", "Export CSV": "export", "Title page": "title", "Find": "find", "Beat map": "map", "Forward writing": "timer",
}
SHORTCUTS = {"New": "Ctrl+N", "Open": "Ctrl+O", "Save": "Ctrl+S", "Save as": "Ctrl+Shift+S", "Undo": "Ctrl+Z", "Redo": "Ctrl+Y", "Cut": "Ctrl+X", "Copy": "Ctrl+C", "Paste": "Ctrl+V", "Bold": "Ctrl+B", "Italic": "Ctrl+I", "Underline": "Ctrl+U"}


def palette():
    app = QApplication.instance()
    if not hasattr(app, '_hover_feedback'):
        app._hover_feedback = HoverFeedback(app)
        app.installEventFilter(app._hover_feedback)
    return dict(bg="#0b0b0b", card="#181818", ink="#f2f2ed", muted="#aaa99f", border="#3c3c3c", accent="#ffdd22", hover="#292929")


def icon(name, color):
    body = PATHS[name].replace("currentColor", color)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    result = QIcon()
    for size in (24, 48):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        result.addPixmap(pixmap)
    return result


def action(bar, label, callback):
    item = QAction(icon(NAMES[label], palette()["accent"]), label, bar)
    item.setProperty("iconName", NAMES[label])
    if label in SHORTCUTS:
        item.setShortcut(SHORTCUTS[label])
    item.setToolTip(label + (f" ({SHORTCUTS[label]})" if label in SHORTCUTS else ""))
    item.triggered.connect(callback)
    bar.addAction(item)
    return item


def icon_button(button, label, name):
    button.setProperty("iconName", name)
    button.setText("")
    button.setIcon(icon(name, "#0b0b0b" if button.objectName() == "playButton" else palette()["accent"]))
    button.setIconSize(QSize(18, 18))
    button.setToolTip(label)
    button.setAccessibleName(label)
    button.setFixedSize(32, 32)


def refresh_icons(window):
    for item in window.findChildren(QAction) + window.findChildren(QAbstractButton):
        name = item.property("iconName")
        if name:
            item.setIcon(icon(name, "#0b0b0b" if isinstance(item, QAbstractButton) and item.objectName() == 'playButton' else palette()["accent"]))


def editor_theme():
    p = palette()
    return f"""
        QMainWindow, QWidget {{ background: {p['bg']}; color: {p['ink']}; font: 13px 'Segoe UI'; }}
        QMenuBar, QMenu, QToolBar {{ background: {p['card']}; color: {p['ink']}; }}
        QMenuBar {{ padding: 2px 8px; }}
        QWidget#officeRibbon {{ background:{p['card']}; }}
        QWidget#ribbonGroup {{ border-right:1px solid {p['border']}; }}
        QLabel#ribbonCaption {{ color:{p['muted']};font-size:10px;padding:1px; }}
        QTabWidget#ribbonTabs::pane {{ border:0;border-top:1px solid {p['border']}; }}
        QTabBar::tab {{ color:{p['ink']};background:transparent;padding:6px 13px;border-bottom:2px solid transparent; }}
        QTabBar::tab:selected {{ color:{p['accent']};border-bottom-color:{p['accent']}; }}
        QMenu::item {{ padding: 7px 28px; }}
        QMenu::item:selected, QMenuBar::item:selected {{ background: {p['hover']}; }}
        QToolBar {{ padding: 3px 8px; spacing: 2px; border: none; border-bottom: 1px solid {p['border']}; }}
        QToolBar::separator {{ width: 1px; background: {p['border']}; margin: 5px 6px; }}
        QToolButton {{ background: transparent; color: {p['ink']}; border: 1px solid transparent; border-radius: 3px; padding: 5px; }}
        QPushButton, QToolButton {{ border: 1px solid transparent; border-radius: 3px; padding: 5px; }}
        QPushButton:hover, QToolButton:hover, QToolButton:checked {{ background: {p['hover']}; border-color: {p['accent']}; color: {p['accent']}; }}
        QPushButton:pressed, QToolButton:pressed {{ background: {p['accent']}; color: {p['bg']}; }}
        QPushButton:disabled, QToolButton:disabled {{ color: #66665e; border-color: transparent; }}
        QPushButton:focus, QToolButton:focus {{ border-color: #a66ce0; }}
        QLineEdit, QComboBox, QSpinBox {{ background: {p['card']}; color: {p['ink']}; border: 1px solid {p['border']}; border-radius: 3px; padding: 4px; }}
        QTextEdit, QPlainTextEdit, QTextBrowser, QTableWidget, QListWidget {{ background: {p['card']}; color: {p['ink']}; border: 1px solid {p['border']}; border-radius: 2px; selection-background-color: #61358c; selection-color: white; }}
        QTableWidget {{ gridline-color: {p['border']}; alternate-background-color: {p['bg']}; }}
        QTableWidget::item:selected {{ background: #61358c; color: white; border: 1px solid {p['accent']}; }}
        QHeaderView::section {{ background: {p['card']}; color: {p['muted']}; border: none; border-right: 1px solid {p['border']}; border-bottom: 1px solid {p['border']}; padding: 7px; }}
        QListWidget::item {{ padding: 6px; border-radius: 2px; }}
        QListWidget::item:selected {{ background: {p['hover']}; color: {p['ink']}; }}
        QStatusBar {{ background: {p['card']}; color: {p['muted']}; border-top: 1px solid {p['border']}; padding: 4px 12px; }}
        QTextEdit#paper, QTextEdit#slideTitle, QTextEdit#slideBody, QTextBrowser#mathPreview {{ background: white; color: #202b3d; border: none; border-radius: 3px; }}
        QTextEdit#paper {{ font: 16px 'Calibri'; }}
        QTextEdit#slideTitle {{ font: 600 28px 'Calibri'; }}
        QTextEdit#slideBody {{ font: 18px 'Calibri'; }}
        QPlainTextEdit, QTextEdit#formulaSource {{ font: 15px 'Consolas'; }}
        QWidget#slidePage {{ background: white; border: 1px solid #d2d9e3; border-radius: 4px; }}
        QLabel#sectionLabel {{ color: {p['muted']}; font-size: 12px; font-weight: 600; padding: 6px; }}
        QLabel#formulaMark {{ color: {p['accent']}; font: italic 20px 'Georgia'; }}
    """
