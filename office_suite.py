"""FreeConvert's local document, table, slide, drawing, and database workspaces."""

from __future__ import annotations

import csv
import shutil
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from docx import Document
from openpyxl import Workbook, load_workbook
from pptx import Presentation
from native_office import advanced_content
from office_surgery import edit_xlsx_cells, replace_runs, replace_text_frame
from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QImage, QPainter, QPen, QTextListFormat
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QColorDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel,
    QListWidget, QMainWindow, QMessageBox, QPushButton, QSplitter, QTableWidget,
    QTableWidgetItem, QTextEdit, QToolBar, QVBoxLayout, QWidget)


def button(bar, label, callback):
    action = QAction(label, bar)
    action.triggered.connect(callback)
    bar.addAction(action)
    return action


def pick_open(parent, label, filters):
    name, _ = QFileDialog.getOpenFileName(parent, label, "", filters)
    return Path(name) if name else None


def pick_save(parent, label, filters):
    name, _ = QFileDialog.getSaveFileName(parent, label, "", filters)
    return Path(name) if name else None


class Workspace(QMainWindow):
    def __init__(self, name):
        super().__init__()
        self.setWindowTitle(f"{name} · FreeConvert")
        self.resize(1100, 750)
        self.path = None
        self.dirty = False
        self.toolbar = QToolBar(name)
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)
        self._theme()
        QApplication.instance().styleHints().colorSchemeChanged.connect(self._theme)

    def _theme(self, *_):
        dark = QApplication.instance().styleHints().colorScheme() == Qt.ColorScheme.Dark
        bg, card, ink, border, accent = (("#0b1520", "#17232e", "#edf5f6", "#304551", "#61d8d0") if dark else
                                         ("#f6f9fb", "#ffffff", "#14283d", "#d8e4e9", "#087e75"))
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background: {bg}; color: {ink}; font-family: 'Segoe UI'; font-size: 14px; }}
            QTextEdit, QTableWidget, QListWidget {{ background: {card}; color: {ink}; border: 1px solid {border}; border-radius: 9px; padding: 8px; }}
            QToolBar {{ background: {card}; border-bottom: 1px solid {border}; spacing: 5px; padding: 8px; }}
            QToolButton {{ color: {ink}; background: {card}; border: 1px solid {border}; border-radius: 7px; padding: 6px; }}
            QToolButton:hover {{ border-color: {accent}; }}
            QHeaderView::section {{ background: {card}; color: {ink}; border: 1px solid {border}; padding: 4px; }}
        """)

    def report(self, operation):
        try:
            operation()
        except Exception as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))

    def discard_changes(self):
        return not self.dirty or QMessageBox.question(
            self, "Unsaved changes", "Discard unsaved changes?", QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes

    def closeEvent(self, event):
        event.accept() if self.discard_changes() else event.ignore()


class Pages(Workspace):
    """Rich text editing with native HTML, TXT, DOCX and PDF output."""

    def __init__(self):
        super().__init__("Pages")
        self.imported_docx = None
        self.original_paragraphs = []
        self.editor = QTextEdit()
        self.editor.setAcceptRichText(True)
        self.editor.setPlaceholderText("Start writing…")
        self.setCentralWidget(self.editor)
        for label, method in [("New", self.new), ("Open", self.open), ("Save", self.save),
                              ("Save as", self.save_as), ("PDF", self.export_pdf),
                              ("Bold", lambda: self.editor.setFontWeight(QFont.Bold if self.editor.fontWeight() < QFont.Bold else QFont.Normal)),
                              ("Italic", lambda: self.editor.setFontItalic(not self.editor.fontItalic())),
                              ("Underline", lambda: self.editor.setFontUnderline(not self.editor.fontUnderline())),
                              ("Bullets", self.bullets)]:
            button(self.toolbar, label, method)
        self.editor.textChanged.connect(self._count)
        self._count()

    def _count(self):
        self.statusBar().showMessage(f"{len(self.editor.toPlainText().split())} words")

    def bullets(self):
        self.editor.textCursor().createList(QTextListFormat.ListDisc)

    def new(self):
        if not self._can_close():
            return
        self.path = None
        self.imported_docx = None
        self.original_paragraphs = []
        self.editor.clear()
        self.editor.document().setModified(False)

    def _can_close(self):
        if not self.editor.document().isModified():
            return True
        answer = QMessageBox.question(self, "Unsaved changes", "Discard changes?", QMessageBox.Yes | QMessageBox.No)
        return answer == QMessageBox.Yes

    def closeEvent(self, event):
        event.accept() if self._can_close() else event.ignore()

    def open(self):
        path = pick_open(self, "Open document", "Documents (*.docx *.html *.htm *.txt)")
        if not path or not self._can_close():
            return
        def read():
            if path.suffix.lower() == ".docx":
                doc = Document(path)
                self.original_paragraphs = [p.text for p in doc.paragraphs]
                self.editor.setPlainText("\n".join(self.original_paragraphs))
                self.imported_docx = path
            elif path.suffix.lower() in {".html", ".htm"}:
                self.editor.setHtml(path.read_text(encoding="utf-8"))
                self.imported_docx = None
            else:
                self.editor.setPlainText(path.read_text(encoding="utf-8"))
                self.imported_docx = None
            # Imported DOCX may contain structures this editor cannot retain.
            self.path = None if path.suffix.lower() == ".docx" else path
            self.editor.document().setModified(False)
        self.report(read)

    def save(self):
        if self.path:
            self.report(lambda: self._write(self.path))
        else:
            self.save_as()

    def save_as(self):
        path = pick_save(self, "Save document", "Word document (*.docx);;HTML (*.html);;Plain text (*.txt)")
        if path:
            self.report(lambda: self._write(path))

    def _write(self, path):
        if path.suffix.lower() == ".docx":
            lines = self.editor.toPlainText().split("\n")
            if self.imported_docx and path.resolve() == self.imported_docx.resolve() and self.path is None:
                raise ValueError("Save an imported Word document to a new file")
            if self.imported_docx and lines == self.original_paragraphs:
                if path.resolve() != self.imported_docx.resolve():
                    shutil.copyfile(self.imported_docx, path)
            elif self.imported_docx and len(lines) == len(self.original_paragraphs):
                doc = Document(self.imported_docx)
                for paragraph, old, new in zip(doc.paragraphs, self.original_paragraphs, lines):
                    if new != old:
                        replace_runs(paragraph, new)
                doc.save(path)
            else:
                if self.imported_docx:
                    doc = Document(self.imported_docx)
                    if doc.tables or advanced_content(self.imported_docx):
                        raise ValueError("Paragraph count changed in a complex Word file; save as HTML or TXT to avoid dropping content")
                doc = Document()
                for line in lines:
                    doc.add_paragraph(line)
                doc.save(path)
            self.imported_docx = path
            self.original_paragraphs = lines
        elif path.suffix.lower() in {".html", ".htm"}:
            path.write_text(self.editor.toHtml(), encoding="utf-8")
        elif path.suffix.lower() == ".txt":
            path.write_text(self.editor.toPlainText(), encoding="utf-8")
        else:
            raise ValueError("Choose DOCX, HTML, or TXT")
        self.path = path
        self.editor.document().setModified(False)

    def export_pdf(self):
        path = pick_save(self, "Export PDF", "PDF (*.pdf)")
        if path:
            def write():
                printer = QPrinter(QPrinter.HighResolution)
                printer.setOutputFormat(QPrinter.PdfFormat)
                printer.setOutputFileName(str(path))
                self.editor.document().print_(printer)
            self.report(write)


class Tables(Workspace):
    """Editable spreadsheet cells with CSV and XLSX persistence."""

    def __init__(self):
        super().__init__("Tables")
        self.imported_xlsx = None
        self.original_rows = []
        self.grid = QTableWidget(100, 26)
        self.grid.setHorizontalHeaderLabels([chr(65 + i) for i in range(26)])
        self.setCentralWidget(self.grid)
        self.grid.itemChanged.connect(lambda _: setattr(self, "dirty", True))
        for label, method in [("New", self.new), ("Open", self.open), ("Save", self.save), ("Save as", self.save_as),
                              ("Add row", lambda: self.grid.insertRow(self.grid.rowCount())),
                              ("Add column", lambda: self.grid.insertColumn(self.grid.columnCount()))]:
            button(self.toolbar, label, method)
        self.statusBar().showMessage("CSV and XLSX · enter values or formulas")

    def new(self):
        if not self.discard_changes():
            return
        self.grid.clearContents()
        self.path = None
        self.imported_xlsx = None
        self.original_rows = []
        self.dirty = False

    def open(self):
        path = pick_open(self, "Open table", "Spreadsheets (*.xlsx *.csv)")
        if path and self.discard_changes():
            self.report(lambda: self._read(path))

    def _read(self, path):
        if path.suffix.lower() == ".xlsx":
            book = load_workbook(path, read_only=True, data_only=False)
            try:
                rows = list(book.active.values)
            finally:
                book.close()
        elif path.suffix.lower() == ".csv":
            with path.open(newline="", encoding="utf-8-sig") as stream:
                rows = list(csv.reader(stream))
        else:
            raise ValueError("Choose XLSX or CSV")
        self.grid.clearContents()
        self.grid.setRowCount(max(100, len(rows)))
        self.grid.setColumnCount(max(26, max((len(row) for row in rows), default=0)))
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                if value is not None:
                    self.grid.setItem(i, j, QTableWidgetItem(str(value)))
        self.imported_xlsx = path if path.suffix.lower() == ".xlsx" else None
        self.original_rows = [["" if value is None else str(value) for value in row] for row in rows]
        # Imported XLSX requires a new path, preserving the original file.
        self.path = None if path.suffix.lower() == ".xlsx" else path
        self.dirty = False

    def save(self):
        if self.path:
            self.report(lambda: self._write(self.path))
        else:
            self.save_as()

    def save_as(self):
        path = pick_save(self, "Save table", "Excel workbook (*.xlsx);;CSV (*.csv)")
        if path:
            self.report(lambda: self._write(path))

    def _rows(self):
        rows = [[self.grid.item(i, j).text() if self.grid.item(i, j) else ""
                 for j in range(self.grid.columnCount())] for i in range(self.grid.rowCount())]
        while rows and not any(rows[-1]):
            rows.pop()
        width = max((next((j + 1 for j in range(len(row) - 1, -1, -1) if row[j]), 0) for row in rows), default=0)
        return [row[:width] for row in rows]

    def _write(self, path):
        rows = self._rows()
        if path.suffix.lower() == ".xlsx":
            if self.imported_xlsx and path.resolve() == self.imported_xlsx.resolve() and self.path is None:
                raise ValueError("Save an imported workbook to a new file")
            if self.imported_xlsx and rows == self.original_rows:
                if path.resolve() != self.imported_xlsx.resolve():
                    shutil.copyfile(self.imported_xlsx, path)
                self.imported_xlsx = path
                self.path = path
                self.dirty = False
                return
            if self.imported_xlsx:
                edit_xlsx_cells(self.imported_xlsx, path, self.original_rows, rows)
            else:
                book = Workbook()
                try:
                    sheet = book.active
                    for i, row in enumerate(rows):
                        for j, value in enumerate(row):
                            sheet.cell(i + 1, j + 1).value = (float(value) if value and value.replace(".", "", 1).replace("-", "", 1).isdigit() else value)
                    book.save(path)
                finally:
                    book.close()
            self.imported_xlsx = path
            self.original_rows = rows
        elif path.suffix.lower() == ".csv":
            with path.open("w", newline="", encoding="utf-8-sig") as stream:
                csv.writer(stream).writerows(rows)
        else:
            raise ValueError("Choose XLSX or CSV")
        self.path = path
        self.dirty = False


class Dazzle(Workspace):
    """Local slide authoring with editable text and HTML presentation output."""

    def __init__(self):
        super().__init__("Dazzle")
        self.imported_pptx = None
        self.original_slides = []
        self.slides = []
        self.index = -1
        self.list = QListWidget()
        self.title = QTextEdit()
        self.title.setPlaceholderText("Slide title")
        self.title.setMaximumHeight(90)
        self.body = QTextEdit()
        self.body.setPlaceholderText("Slide body")
        area = QWidget()
        layout = QVBoxLayout(area)
        layout.addWidget(self.title)
        layout.addWidget(self.body)
        split = QSplitter()
        split.addWidget(self.list)
        split.addWidget(area)
        split.setSizes([230, 800])
        self.setCentralWidget(split)
        self.list.currentRowChanged.connect(self.select)
        self.title.textChanged.connect(lambda: setattr(self, "dirty", True))
        self.body.textChanged.connect(lambda: setattr(self, "dirty", True))
        for label, method in [("New", self.new), ("Add slide", self.add), ("Delete slide", self.delete),
                              ("Open", self.open), ("Save", self.save), ("Save as", self.save_as), ("PDF", self.export_pdf)]:
            button(self.toolbar, label, method)
        self.new()

    def _store(self):
        if self.index >= 0:
            self.slides[self.index] = (self.title.toPlainText(), self.body.toPlainText())
            self.list.item(self.index).setText(self.title.toPlainText() or f"Slide {self.index + 1}")

    def select(self, index):
        if index == self.index:
            return
        self._store()
        self.index = index
        if index >= 0:
            title, body = self.slides[index]
            with QSignalBlocker(self.title), QSignalBlocker(self.body):
                self.title.setPlainText(title)
                self.body.setPlainText(body)

    def new(self):
        if not self.discard_changes():
            return
        self.slides = []
        self.list.clear()
        self.index = -1
        self.path = None
        self.imported_pptx = None
        self.original_slides = []
        self.add()
        self.dirty = False

    def add(self):
        self._store()
        self.slides.append(("", ""))
        self.list.addItem(f"Slide {len(self.slides)}")
        self.list.setCurrentRow(len(self.slides) - 1)
        self.dirty = True

    def delete(self):
        if len(self.slides) <= 1:
            return
        index = self.list.currentRow()
        self.index = -1
        del self.slides[index]
        self.list.takeItem(index)
        self.list.setCurrentRow(min(index, len(self.slides) - 1))
        self.dirty = True

    def open(self):
        path = pick_open(self, "Open slides", "Presentations (*.pptx *.dazzle)")
        if path and self.discard_changes():
            def read():
                import json
                if path.suffix.lower() == ".pptx":
                    prs = Presentation(path)
                    slides = []
                    for slide in prs.slides:
                        parts = [shape.text for shape in slide.shapes if shape.has_text_frame and shape.text.strip()]
                        slides.append([parts[0] if parts else "", "\n".join(parts[1:])])
                else:
                    slides = json.loads(path.read_text(encoding="utf-8"))["slides"]
                if not isinstance(slides, list) or not slides or not all(isinstance(s, list) and len(s) == 2 and all(isinstance(v, str) for v in s) for s in slides):
                    raise ValueError("Invalid Dazzle document")
                self.index = -1
                self.slides = [tuple(s) for s in slides]
                self.list.clear()
                for i, slide in enumerate(self.slides):
                    self.list.addItem(slide[0] or f"Slide {i + 1}")
                self.list.setCurrentRow(0)
                self.imported_pptx = path if path.suffix.lower() == ".pptx" else None
                self.original_slides = [tuple(s) for s in slides]
                # PPTX import keeps text only, so never overwrite the imported deck via Save.
                self.path = None if path.suffix.lower() == ".pptx" else path
                self.dirty = False
            self.report(read)

    def save(self):
        if self.path:
            self.report(lambda: self._write(self.path))
        else:
            self.save_as()

    def save_as(self):
        path = pick_save(self, "Save slides", "PowerPoint (*.pptx);;Dazzle slides (*.dazzle)")
        if path:
            self.report(lambda: self._write(path))

    def _write(self, path):
        import json
        self._store()
        if path.suffix.lower() == ".pptx":
            if self.imported_pptx and path.resolve() == self.imported_pptx.resolve() and self.path is None:
                raise ValueError("Save an imported presentation to a new file")
            if self.imported_pptx and self.slides == self.original_slides:
                if path.resolve() != self.imported_pptx.resolve():
                    shutil.copyfile(self.imported_pptx, path)
                self.imported_pptx = path
                self.path = path
                self.dirty = False
                return
            if self.imported_pptx and len(self.slides) == len(self.original_slides):
                prs = Presentation(self.imported_pptx)
                for slide, (title, body), original in zip(prs.slides, self.slides, self.original_slides):
                    if (title, body) == original:
                        continue
                    shapes = [shape for shape in slide.shapes if shape.has_text_frame and shape.text.strip()]
                    if title != original[0]:
                        if shapes:
                            replace_text_frame(shapes[0], title)
                        else:
                            slide.shapes.add_textbox(914400, 914400, prs.slide_width - 1828800, 685800).text = title
                    if body != original[1]:
                        if len(shapes) > 1:
                            old_shapes = shapes[1:]
                            lines = body.split("\n")
                            counts = [len(shape.text_frame.paragraphs) for shape in old_shapes]
                            if sum(counts) != len(lines):
                                raise ValueError("Text box structure changed; save a Dazzle copy to keep the text")
                            offset = 0
                            for shape, count in zip(old_shapes, counts):
                                replace_text_frame(shape, "\n".join(lines[offset:offset + count]))
                                offset += count
                        else:
                            slide.shapes.add_textbox(914400, 1828800, prs.slide_width - 1828800, 3657600).text = body
            else:
                if self.imported_pptx and advanced_content(self.imported_pptx):
                    raise ValueError("Slide structure changed in a complex presentation; save a Dazzle copy to keep the text")
                prs = Presentation()
                for title, body in self.slides:
                    slide = prs.slides.add_slide(prs.slide_layouts[1])
                    slide.shapes.title.text = title
                    slide.placeholders[1].text = body
            prs.save(path)
            self.imported_pptx = path
            self.original_slides = list(self.slides)
        elif path.suffix.lower() == ".dazzle":
            path.write_text(json.dumps({"slides": self.slides}, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            raise ValueError("Choose PPTX or Dazzle format")
        self.path = path
        self.dirty = False

    def export_pdf(self):
        path = pick_save(self, "Export slides", "PDF (*.pdf)")
        if path:
            def write():
                from reportlab.pdfgen import canvas
                self._store()
                pdf = canvas.Canvas(str(path), pagesize=(960, 540))
                for title, body in self.slides:
                    pdf.setFont("Helvetica-Bold", 36)
                    pdf.drawString(60, 465, title[:48])
                    pdf.setFont("Helvetica", 22)
                    for i, line in enumerate(body.splitlines()[:15]):
                        pdf.drawString(70, 390 - i * 27, line[:75])
                    pdf.showPage()
                pdf.save()
            self.report(write)


class Canvas(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.image = QImage(1200, 800, QImage.Format_ARGB32)
        self.image.fill(Qt.white)
        self.color = QColor("#102f39")
        self.width = 4
        self.last = None
        self.eraser = False
        self.setMinimumSize(700, 480)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#d9e5e7"))
        painter.drawImage(0, 0, self.image)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.last = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self.last and event.buttons() & Qt.LeftButton:
            point = event.position().toPoint()
            painter = QPainter(self.image)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(Qt.white if self.eraser else self.color, self.width, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(self.last, point)
            painter.end()
            self.last = point
            self.update()
            self.changed.emit()

    def mouseReleaseEvent(self, event):
        self.last = None


class Sketch(Workspace):
    def __init__(self):
        super().__init__("Sketch")
        self.canvas = Canvas()
        self.setCentralWidget(self.canvas)
        self.canvas.changed.connect(lambda: setattr(self, "dirty", True))
        for label, method in [("New", self.new), ("Open", self.open), ("Save", self.save),
                              ("Save as", self.save_as), ("Pen color", self.color),
                              ("Eraser", self.eraser), ("Clear", self.clear)]:
            button(self.toolbar, label, method)

    def new(self):
        if not self.discard_changes():
            return
        self.canvas.image.fill(Qt.white)
        self.canvas.update()
        self.path = None
        self.dirty = False

    def clear(self):
        self.canvas.image.fill(Qt.white)
        self.canvas.update()
        self.dirty = True

    def color(self):
        color = QColorDialog.getColor(self.canvas.color, self)
        if color.isValid():
            self.canvas.color = color
            self.canvas.eraser = False

    def eraser(self):
        self.canvas.eraser = not self.canvas.eraser

    def open(self):
        path = pick_open(self, "Open image", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path and self.discard_changes():
            image = QImage(str(path))
            if image.isNull():
                QMessageBox.warning(self, "Sketch", "Could not open image")
                return
            self.canvas.image = image.convertToFormat(QImage.Format_ARGB32)
            self.canvas.update()
            # Imported images may contain metadata the canvas cannot retain.
            self.path = None
            self.dirty = False

    def save(self):
        if self.path:
            self.report(lambda: self._write(self.path))
        else:
            self.save_as()

    def save_as(self):
        path = pick_save(self, "Save image", "PNG (*.png);;JPEG (*.jpg);;BMP (*.bmp)")
        if path:
            self.report(lambda: self._write(path))

    def _write(self, path):
        if not self.canvas.image.save(str(path)):
            raise OSError("Could not save image")
        self.path = path
        self.dirty = False


class Organize(Workspace):
    """SQLite database table browser and record editor."""

    def __init__(self):
        super().__init__("Organize")
        self.tables = QListWidget()
        self.grid = QTableWidget()
        self.grid.itemChanged.connect(lambda _: setattr(self, "dirty", True))
        split = QSplitter()
        split.addWidget(self.tables)
        split.addWidget(self.grid)
        split.setSizes([200, 900])
        self.setCentralWidget(split)
        self.tables.currentTextChanged.connect(self.show_table)
        for label, method in [("New database", self.new), ("Open database", self.open),
                              ("New table", self.new_table), ("Add record", self.add_record),
                              ("Delete record", self.delete_record), ("Save changes", self.save),
                              ("Import CSV", self.import_csv), ("Export CSV", self.export_csv)]:
            button(self.toolbar, label, method)

    @contextmanager
    def connect(self):
        if not self.path:
            raise ValueError("Create or open a database first")
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def new(self):
        path = pick_save(self, "Create database", "SQLite database (*.sqlite *.db)")
        if path and self.discard_changes():
            if path.exists():
                QMessageBox.warning(self, "Organize", "Choose a new filename; an existing database cannot be replaced here.")
                return
            with closing(sqlite3.connect(path)) as db:
                with db:
                    db.execute("CREATE TABLE IF NOT EXISTS _freeconvert_meta (key TEXT PRIMARY KEY, value TEXT)")
                    db.execute("INSERT OR REPLACE INTO _freeconvert_meta VALUES ('owner', 'Organize')")
            self.path = path
            self.refresh()
            self.dirty = False

    def open(self):
        path = pick_open(self, "Open database", "SQLite database (*.sqlite *.db)")
        if path and self.discard_changes():
            self.path = path
            self.report(self.refresh)
            self.dirty = False

    def refresh(self):
        with self.connect() as db:
            names = [x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != '_freeconvert_meta' ORDER BY name")]
        self.tables.clear()
        self.tables.addItems(names)

    def show_table(self, name):
        if not name:
            self.grid.clear()
            return
        def read():
            with self.connect() as db:
                cols = [x[1] for x in db.execute(f"PRAGMA table_info({quote(name)})")]
                rows = db.execute(f"SELECT * FROM {quote(name)} LIMIT 1000").fetchall()
            self.grid.clear()
            self.grid.setRowCount(len(rows))
            self.grid.setColumnCount(len(cols))
            self.grid.setHorizontalHeaderLabels(cols)
            for i, row in enumerate(rows):
                for j, value in enumerate(row):
                    self.grid.setItem(i, j, QTableWidgetItem("" if value is None else str(value)))
            self.grid.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed if self._editable() else QAbstractItemView.NoEditTriggers)
            self.dirty = False
        self.report(read)

    def new_table(self):
        if not self.path:
            return
        if not self._editable():
            QMessageBox.warning(self, "Organize", "External databases are read-only. Create an Organize database to edit records.")
            return
        name, ok = QInputDialog.getText(self, "New table", "Table name")
        if not ok or not name.strip():
            return
        columns, ok = QInputDialog.getText(self, "Columns", "Comma-separated column names")
        if not ok:
            return
        names = [x.strip() for x in columns.split(",") if x.strip()]
        if not names or len(set(names)) != len(names):
            QMessageBox.warning(self, "Organize", "Enter unique column names")
            return
        def create():
            with self.connect() as db:
                db.execute(f"CREATE TABLE {quote(name.strip())} ({', '.join(quote(x) + ' TEXT' for x in names)})")
            self.refresh()
            self.tables.setCurrentRow(self.tables.count() - 1)
        self.report(create)

    def add_record(self):
        if self.tables.currentItem() and self._editable():
            self.grid.insertRow(self.grid.rowCount())
            self.dirty = True

    def delete_record(self):
        row = self.grid.currentRow()
        if row >= 0 and self._editable():
            self.grid.removeRow(row)
            self.dirty = True

    def save(self):
        name = self.tables.currentItem().text() if self.tables.currentItem() else None
        if not name:
            return
        if not self._editable():
            QMessageBox.warning(self, "Organize", "External databases are read-only")
            return
        def write():
            with self.connect() as db:
                columns = [self.grid.horizontalHeaderItem(j).text() for j in range(self.grid.columnCount())]
                db.execute(f"DELETE FROM {quote(name)}")
                placeholders = ",".join("?" for _ in columns)
                for i in range(self.grid.rowCount()):
                    values = [self.grid.item(i, j).text() if self.grid.item(i, j) else None for j in range(len(columns))]
                    db.execute(f"INSERT INTO {quote(name)} VALUES ({placeholders})", values)
            self.statusBar().showMessage("Changes saved")
            self.dirty = False
        self.report(write)

    def import_csv(self):
        if not self.path or not self._editable():
            return
        path = pick_open(self, "Import CSV", "CSV (*.csv)")
        if not path:
            return
        def write():
            with path.open(newline="", encoding="utf-8-sig") as stream:
                rows = list(csv.reader(stream))
            if not rows or not rows[0] or len(set(rows[0])) != len(rows[0]):
                raise ValueError("CSV needs unique column headings")
            name = path.stem
            with self.connect() as db:
                db.execute(f"CREATE TABLE {quote(name)} ({', '.join(quote(x) + ' TEXT' for x in rows[0])})")
                for row in rows[1:]:
                    db.execute(f"INSERT INTO {quote(name)} VALUES ({','.join('?' for _ in rows[0])})", (row + [None] * len(rows[0]))[:len(rows[0])])
            self.refresh()
        self.report(write)

    def export_csv(self):
        if not self.tables.currentItem():
            return
        path = pick_save(self, "Export CSV", "CSV (*.csv)")
        if path:
            def write():
                with path.open("w", newline="", encoding="utf-8-sig") as stream:
                    out = csv.writer(stream)
                    out.writerow([self.grid.horizontalHeaderItem(j).text() for j in range(self.grid.columnCount())])
                    for i in range(self.grid.rowCount()):
                        out.writerow([self.grid.item(i, j).text() if self.grid.item(i, j) else "" for j in range(self.grid.columnCount())])
            self.report(write)

    def _editable(self):
        if not self.path:
            return False
        with self.connect() as db:
            try:
                return db.execute("SELECT value FROM _freeconvert_meta WHERE key='owner'").fetchone() == ("Organize",)
            except sqlite3.OperationalError:
                return False


def quote(identifier):
    if not identifier or "\x00" in identifier:
        raise ValueError("Invalid table or column name")
    return '"' + identifier.replace('"', '""') + '"'


from formulaic import Formulaic

WORKSPACES = {"Pages": Pages, "Tables": Tables, "Dazzle": Dazzle, "Sketch": Sketch, "Organize": Organize, "Formulaic": Formulaic}
