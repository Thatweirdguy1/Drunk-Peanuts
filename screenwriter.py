"""Local Fountain writing workspace with live screenplay preview."""

from __future__ import annotations

import os
import re
import time
from collections import Counter
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QSplitter, QTextBrowser, QVBoxLayout, QWidget,
)

from screenplay import SCENE, TITLE_KEYS, export_script, from_fdx, merge_fdx, parse_fountain, to_html


class FountainHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text: str):
        stripped = text.strip()
        color = None
        if SCENE.match(stripped) or stripped.startswith(".") and not stripped.startswith(".."):
            color = "#087e75"
        elif stripped.startswith("#"):
            color = "#6850a1"
        elif stripped.startswith("=") or stripped.startswith("[["):
            color = "#79848b"
        elif stripped.startswith("@") or stripped.isupper() and len(stripped) < 40:
            color = "#344b8e"
        elif stripped.startswith(">") or stripped.endswith("TO:"):
            color = "#996626"
        if color:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            fmt.setFontWeight(QFont.Bold)
            self.setFormat(0, len(text), fmt)


class ScriptEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.locked_prefix = ""
        self.forward_only = False

    def keyPressEvent(self, event):
        if self.forward_only:
            cursor = self.textCursor()
            if (cursor.selectionStart() < len(self.locked_prefix) or
                    cursor.position() < len(self.locked_prefix) or
                    event.matches(QKeySequence.Undo) or event.matches(QKeySequence.Redo)):
                cursor.movePosition(QTextCursor.End)
                self.setTextCursor(cursor)
                if event.key() in {Qt.Key_Backspace, Qt.Key_Delete} or event.matches(QKeySequence.Undo) or event.matches(QKeySequence.Redo):
                    return
        super().keyPressEvent(event)


class ScreenwriterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Writer's Drafts · FreeConvert")
        self.resize(1320, 830)
        self.path: Path | None = None
        self.original_fdx: bytes | None = None
        self.imported_fountain: str | None = None
        self.settings = QSettings("Local File Converter", "Screenwriter")
        self.autosave = Path.home() / ".local-file-converter" / "screenwriter-autosave.fountain"
        self.autosave.parent.mkdir(parents=True, exist_ok=True)
        self.deadline = 0.0
        self._building = False
        self._build()
        self._theme()
        QApplication.instance().styleHints().colorSchemeChanged.connect(self._theme)
        self.refresh = QTimer(self)
        self.refresh.setSingleShot(True)
        self.refresh.setInterval(450)
        self.refresh.timeout.connect(self._refresh)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(1200)
        self.autosave_timer.timeout.connect(self._autosave)
        self.clock = QTimer(self)
        self.clock.timeout.connect(self._tick)
        self.clock.start(1000)
        self._new_text()
        self.autosave_timer.stop()
        if self.autosave.exists() and self.autosave.stat().st_size:
            if QMessageBox.question(self, "Recover script", "Recover the last locally autosaved draft?") == QMessageBox.Yes:
                self.editor.setPlainText(self.autosave.read_text(encoding="utf-8"))
                self.editor.document().setModified(True)
        deadline = float(self.settings.value("forward_deadline", 0))
        if deadline > time.time():
            self.deadline = deadline
            self.editor.forward_only = True
            self.editor.locked_prefix = self.editor.toPlainText().rpartition("\n")[0]
            self._tick()
        self._refresh()

    def _theme(self, *_):
        dark = QApplication.instance().styleHints().colorScheme() == Qt.ColorScheme.Dark
        bg, card, ink, muted, border = (("#0b1520", "#17232e", "#edf5f6", "#a6bac3", "#304551") if dark else
                                        ("#f6f9fb", "#ffffff", "#14283d", "#58717e", "#d8e4e9"))
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background: {bg}; color: {ink}; font-family: 'Segoe UI', 'SF Pro Text'; font-size: 14px; }}
            QPlainTextEdit, QTextBrowser, QListWidget {{ background: {card}; color: {ink}; border: 1px solid {border}; border-radius: 9px; padding: 8px; }}
            QPushButton, QComboBox {{ background: {card}; color: {ink}; border: 1px solid {border}; border-radius: 8px; padding: 7px; }}
            QPushButton:hover, QComboBox:hover {{ border-color: #087e75; }}
            QPushButton:focus, QComboBox:focus, QPlainTextEdit:focus {{ border: 2px solid #087e75; }}
            QComboBox QAbstractItemView {{ background: {card}; color: {ink}; selection-background-color: #087e75; }}
            QLabel {{ color: {muted}; }}
        """)

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        toolbar = QHBoxLayout()
        for label, callback in (("New", self._new), ("Open", self._open), ("Save", self._save),
                                ("Export", self._export), ("Title page", self._title_page),
                                ("Find", self._find), ("Beat map", self._beat_map)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        toolbar.addStretch()
        self.forward = QPushButton("Forward writing")
        self.forward.clicked.connect(self._forward_menu)
        toolbar.addWidget(self.forward)
        layout.addLayout(toolbar)

        second = QHBoxLayout()
        second.addWidget(QLabel("Element"))
        self.element = QComboBox()
        self.element.addItems(["Scene Heading", "Action", "Character", "Dialogue", "Parenthetical", "Transition", "Shot", "General Text"])
        self.element.activated.connect(self._apply_element)
        second.addWidget(self.element)
        for label, marker in (("B", "**"), ("I", "*"), ("U", "_")):
            button = QPushButton(label)
            button.setFixedWidth(40)
            button.clicked.connect(lambda _=False, value=marker: self._emphasize(value))
            second.addWidget(button)
        second.addStretch()
        second.addWidget(QLabel("Tab: cycle elements · Ctrl+1–8: choose · Ctrl+D: dual speech"))
        layout.addLayout(second)

        splitter = QSplitter(Qt.Horizontal)
        self.scenes = QListWidget()
        self.scenes.setMinimumWidth(190)
        self.scenes.itemClicked.connect(self._jump)
        splitter.addWidget(self.scenes)
        self.editor = ScriptEditor()
        self.editor.setFont(QFont("Courier New", 12))
        self.editor.setTabStopDistance(32)
        self.editor.textChanged.connect(self._changed)
        self.editor.cursorPositionChanged.connect(self._cursor_changed)
        self.editor.setPlaceholderText("INT. LOCATION - DAY\n\nWrite your scene here…")
        FountainHighlighter(self.editor.document())
        splitter.addWidget(self.editor)
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(False)
        splitter.addWidget(self.preview)
        splitter.setSizes([210, 540, 570])
        layout.addWidget(splitter, 1)
        self.status = QLabel("Local draft")
        layout.addWidget(self.status)

        for key, callback in (("Ctrl+N", self._new), ("Ctrl+O", self._open), ("Ctrl+S", self._save),
                              ("Ctrl+Shift+S", self._export), ("Ctrl+F", self._find),
                              ("Ctrl+D", self._dual), ("Ctrl+K", self._character_picker),
                              ("Ctrl+B", lambda: self._emphasize("**")),
                              ("Ctrl+I", lambda: self._emphasize("*")),
                              ("Ctrl+U", lambda: self._emphasize("_"))):
            action = QAction(self)
            action.setShortcut(key)
            action.triggered.connect(callback)
            self.addAction(action)
        for index in range(8):
            action = QAction(self)
            action.setShortcut(f"Ctrl+{index + 1}")
            action.triggered.connect(lambda _=False, value=index: self._apply_element(value))
            self.addAction(action)
        tab = QAction(self)
        tab.setShortcut("Tab")
        tab.triggered.connect(lambda: self._apply_element((self.element.currentIndex() + 1) % 8))
        self.addAction(tab)
        backtab = QAction(self)
        backtab.setShortcut("Shift+Tab")
        backtab.triggered.connect(lambda: self._apply_element((self.element.currentIndex() - 1) % 8))
        self.addAction(backtab)

    def _new_text(self):
        self.editor.setPlainText("Title: Untitled\nCredit: Written by\nAuthor: \n\nINT. LOCATION - DAY\n\n")
        self.editor.document().setModified(False)

    def _new(self):
        if self.editor.document().isModified() and not self._ask_save():
            return
        self.path = None
        self.original_fdx = None
        self.imported_fountain = None
        self._new_text()
        self.autosave_timer.stop()
        self.autosave.unlink(missing_ok=True)

    def _ask_save(self) -> bool:
        answer = QMessageBox.question(self, "Unsaved changes", "Save this draft before continuing?",
                                      QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if answer == QMessageBox.Cancel:
            return False
        if answer == QMessageBox.Save:
            return self._save()
        return True

    def _open(self):
        if self.editor.document().isModified() and not self._ask_save():
            return
        filename, _ = QFileDialog.getOpenFileName(self, "Open script", "", "Scripts (*.fountain *.fdx *.txt *.md);;All files (*)")
        if not filename:
            return
        try:
            path = Path(filename)
            if path.stat().st_size > 20 * 1024 * 1024:
                raise ValueError("Script is too large to open safely.")
            is_fdx = path.suffix.lower() == ".fdx"
            original = path.read_bytes() if is_fdx else None
            content = original.decode("utf-8-sig") if original is not None else path.read_text(encoding="utf-8-sig")
            fountain = from_fdx(content) if is_fdx else content
            self.editor.setPlainText(fountain)
            self.original_fdx = original
            self.imported_fountain = fountain if is_fdx else None
            self.path = path if path.suffix.lower() == ".fountain" else None
            self.editor.document().setModified(False)
            self.autosave_timer.stop()
            self.autosave.unlink(missing_ok=True)
        except Exception as error:
            QMessageBox.warning(self, "Cannot open script", str(error))

    def _save(self) -> bool:
        path = self.path
        if path is None:
            filename, _ = QFileDialog.getSaveFileName(self, "Save Fountain script", "Untitled.fountain", "Fountain (*.fountain)")
            if not filename:
                return False
            path = Path(filename).with_suffix(".fountain")
            if path.exists() and QMessageBox.question(self, "Replace file?", f"Replace {path.name}?") != QMessageBox.Yes:
                return False
        try:
            self._atomic_write(path, self.editor.toPlainText())
            self.path = path
            self.editor.document().setModified(False)
            self.status.setText(f"Saved locally: {path}")
            return True
        except Exception as error:
            QMessageBox.warning(self, "Cannot save", str(error))
            return False

    @staticmethod
    def _atomic_write(path: Path, text: str):
        pending = path.with_name(path.name + ".writing")
        pending.write_text(text, encoding="utf-8")
        os.replace(pending, path)

    def _export(self):
        filename, selected = QFileDialog.getSaveFileName(
            self, "Export screenplay", str((self.path or Path("Untitled.fountain")).with_suffix(".pdf")),
            "PDF (*.pdf);;Fountain (*.fountain);;Final Draft (*.fdx);;Plain text (*.txt);;HTML (*.html);;Markdown (*.md)")
        if not filename:
            return
        suffix = {"PDF": ".pdf", "Fountain": ".fountain", "Final Draft": ".fdx",
                  "Plain text": ".txt", "HTML": ".html", "Markdown": ".md"}
        target = Path(filename).with_suffix(next(value for key, value in suffix.items() if selected.startswith(key)))
        try:
            if target.suffix.lower() == ".fdx" and self.original_fdx is not None:
                if target.exists():
                    raise FileExistsError(f"Output already exists: {target.name}")
                current = self.editor.toPlainText()
                if current == self.imported_fountain:
                    data = self.original_fdx
                else:
                    try:
                        data = merge_fdx(self.original_fdx, self.imported_fountain, current)
                    except ValueError as error:
                        choice = QMessageBox.question(
                            self, "FDX metadata", f"{error}\n\nExport a new FDX without the original metadata?",
                            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                        if choice != QMessageBox.Yes:
                            return
                        data = None
                if data is None:
                    export_script(current, target)
                else:
                    target.write_bytes(data)
            else:
                export_script(self.editor.toPlainText(), target,
                              self.original_fdx if target.suffix.lower() == ".pdf" else None)
            self.status.setText(f"Exported locally: {target}")
        except Exception as error:
            QMessageBox.warning(self, "Cannot export", str(error))

    def _title_page(self):
        title, _ = parse_fountain(self.editor.toPlainText())
        dialog = QDialog(self)
        dialog.setWindowTitle("Title page")
        layout = QFormLayout(dialog)
        fields = {}
        for key in ("title", "credit", "author", "source", "contact", "draft date"):
            field = QLineEdit(title.get(key, ""))
            layout.addRow(key.title(), field)
            fields[key] = field
        done = QPushButton("Apply")
        done.clicked.connect(dialog.accept)
        layout.addRow(done)
        if dialog.exec() != QDialog.Accepted:
            return
        lines = self.editor.toPlainText().splitlines()
        while lines and (match := re.match(r"^([A-Za-z ]+):", lines[0])) and match.group(1).lower() in TITLE_KEYS:
            lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
        header = [f"{key.title()}: {field.text()}" for key, field in fields.items() if field.text().strip()]
        self.editor.setPlainText("\n".join(header + [""] + lines).rstrip() + "\n")

    def _beat_map(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Beat map")
        dialog.resize(440, 520)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Use # for sections and = for scene beats. Both stay out of the PDF."))
        beats = QListWidget()
        _, elements = parse_fountain(self.editor.toPlainText())
        for element in elements:
            if element.kind in {"section", "synopsis", "scene"}:
                item = QListWidgetItem(f"{element.kind.title()}: {element.text}")
                item.setData(Qt.UserRole, element.line)
                beats.addItem(item)
        beats.itemDoubleClicked.connect(lambda item: (self._jump(item), dialog.accept()))
        layout.addWidget(beats)
        for label, prefix in (("Add section", "# "), ("Add beat", "= ")):
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, value=prefix: (dialog.accept(), self.editor.insertPlainText("\n" + value)))
            layout.addWidget(button)
        dialog.exec()

    def _find(self):
        term, ok = QInputDialog.getText(self, "Find text", "Find:")
        if ok and term and not self.editor.find(term):
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.Start)
            self.editor.setTextCursor(cursor)
            if not self.editor.find(term):
                QMessageBox.information(self, "Find text", "No match.")

    def _line(self) -> tuple[QTextCursor, str]:
        cursor = self.editor.textCursor()
        cursor.select(QTextCursor.LineUnderCursor)
        return cursor, cursor.selectedText()

    def _apply_element(self, index: int):
        if self.editor.forward_only:
            return
        self.element.setCurrentIndex(index)
        cursor, line = self._line()
        text = line.strip().lstrip("@.!>")
        if index == 0:
            text = text.upper() if text else "INT. LOCATION - DAY"
            if not SCENE.match(text):
                text = "." + text
        elif index == 1:
            text = "!" + text
        elif index == 2:
            text = "@" + (text.upper() or "CHARACTER")
        elif index == 4:
            text = text if text.startswith("(") else f"({text})"
        elif index == 5:
            text = ">" + (text.upper() or "CUT TO:")
        elif index == 6:
            text = "." + (text.upper() or "ANGLE ON")
        cursor.insertText(text)
        self.editor.setTextCursor(cursor)

    def _emphasize(self, marker: str):
        if self.editor.forward_only:
            return
        cursor = self.editor.textCursor()
        text = cursor.selectedText()
        cursor.insertText(marker + text + marker)
        if not text:
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, len(marker))
            self.editor.setTextCursor(cursor)

    def _dual(self):
        cursor, line = self._line()
        if line.strip().startswith("@") and not line.rstrip().endswith("^"):
            cursor.insertText(line.rstrip() + " ^")

    def _character_picker(self):
        _, elements = parse_fountain(self.editor.toPlainText())
        names = [name for name, _ in Counter(element.text for element in elements if element.kind == "character").most_common()]
        if not names:
            return
        choice, ok = QInputDialog.getItem(self, "Characters", "Insert character:", names, 0, False)
        if ok:
            self.editor.insertPlainText("\n@" + choice + "\n")

    def _forward_menu(self):
        if self.deadline:
            QMessageBox.information(self, "Forward writing", "The current session unlocks when its timer ends.")
            return
        choice, ok = QInputDialog.getItem(self, "Forward writing", "Append-only session:",
                                          ["5 minutes", "15 minutes", "30 minutes", "60 minutes"], 0, False)
        if ok:
            self.deadline = time.time() + int(choice.split()[0]) * 60
            self.settings.setValue("forward_deadline", self.deadline)
            self.editor.forward_only = True
            self.editor.locked_prefix = self.editor.toPlainText().rpartition("\n")[0]
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.editor.setTextCursor(cursor)
            self.editor.setUndoRedoEnabled(False)
            self._tick()

    def _tick(self):
        if not self.deadline:
            return
        remaining = int(self.deadline - time.time())
        if remaining <= 0:
            self.deadline = 0
            self.editor.locked_prefix = ""
            self.editor.forward_only = False
            self.editor.setUndoRedoEnabled(True)
            self.settings.remove("forward_deadline")
            self.forward.setText("Forward writing")
        else:
            self.forward.setText(f"Forward: {remaining // 60:02}:{remaining % 60:02}")

    def _changed(self):
        if self.editor.forward_only and not self.editor.toPlainText().startswith(self.editor.locked_prefix):
            self.editor.blockSignals(True)
            self.editor.setPlainText(self.editor.locked_prefix)
            self.editor.blockSignals(False)
        if self.deadline:
            text = self.editor.toPlainText()
            self.editor.locked_prefix = text.rpartition("\n")[0]
        self.refresh.start()
        self.autosave_timer.start()

    def _autosave(self):
        try:
            self._atomic_write(self.autosave, self.editor.toPlainText())
        except OSError:
            self.status.setText("Autosave failed; use Save to keep this draft.")

    def _cursor_changed(self):
        if self.editor.forward_only and self.editor.textCursor().position() < len(self.editor.locked_prefix):
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.editor.setTextCursor(cursor)

    def _refresh(self):
        text = self.editor.toPlainText()
        _, elements = parse_fountain(text)
        self.scenes.clear()
        for element in elements:
            if element.kind == "scene":
                item = QListWidgetItem(element.text)
                item.setData(Qt.UserRole, element.line)
                self.scenes.addItem(item)
        self.preview.setHtml(to_html(text))
        words = len(re.findall(r"\b\w+\b", text))
        pages = max(1, (sum(max(1, len(element.text) // 65 + 1) for element in elements) + 54) // 55)
        self.status.setText(f"{self.path or 'Unsaved local draft'} · {self.scenes.count()} scenes · ~{pages} pages · {words} words · autosaved locally")

    def _jump(self, item: QListWidgetItem):
        line = item.data(Qt.UserRole)
        block = self.editor.document().findBlockByNumber(line)
        if block.isValid():
            cursor = QTextCursor(block)
            self.editor.setTextCursor(cursor)
            self.editor.setFocus()

    def closeEvent(self, event):
        if self.editor.document().isModified() and not self._ask_save():
            event.ignore()
        else:
            self.autosave_timer.stop()
            self.autosave.unlink(missing_ok=True)
            event.accept()
