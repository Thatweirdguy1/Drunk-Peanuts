"""Small local formula editor with MathML and OpenDocument Formula output."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QTextBrowser, QTextEdit, QVBoxLayout, QWidget


MATH = "http://www.w3.org/1998/Math/MathML"
MANIFEST = "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"
MIME = "application/vnd.oasis.opendocument.formula"
GREEK = {"alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "theta": "θ", "lambda": "λ", "mu": "μ", "pi": "π", "sigma": "σ", "phi": "φ", "omega": "ω"}
TOKENS = re.compile(r"sqrt|over|[A-Za-z]+|\d+(?:\.\d+)?|[{}^_()+\-*/=]|\S")


def parse_formula(source: str):
    tokens = TOKENS.findall(source)
    index = 0

    def atom():
        nonlocal index
        if index >= len(tokens):
            raise ValueError("An operand is missing")
        token = tokens[index]
        index += 1
        if token == "{":
            value = expression()
            if index >= len(tokens) or tokens[index] != "}":
                raise ValueError("Missing closing brace")
            index += 1
        elif token == "sqrt":
            value = ("sqrt", atom())
        elif token in {"}", "over", "^", "_"}:
            raise ValueError(f"Unexpected {token}")
        else:
            value = ("token", GREEK.get(token, token))
        while index < len(tokens) and tokens[index] in {"^", "_"}:
            kind = "sup" if tokens[index] == "^" else "sub"
            index += 1
            value = (kind, value, atom())
        return value

    def expression():
        nonlocal index
        values = []
        while index < len(tokens) and tokens[index] not in {"}", "over"}:
            values.append(atom())
        value = ("row", values)
        if index < len(tokens) and tokens[index] == "over":
            index += 1
            value = ("frac", value, expression())
        return value

    tree = expression()
    if index != len(tokens):
        raise ValueError("Unexpected closing brace")
    return tree


def mathml(source: str) -> bytes:
    def add(parent, node):
        kind = node[0]
        tag = {"row": "mrow", "frac": "mfrac", "sqrt": "msqrt", "sup": "msup", "sub": "msub"}.get(kind)
        if kind == "token":
            value = node[1]
            tag = "mn" if value[0].isdigit() else "mi" if value.isalpha() else "mo"
            ET.SubElement(parent, f"{{{MATH}}}{tag}").text = value
        else:
            element = ET.SubElement(parent, f"{{{MATH}}}{tag}")
            children = node[1] if kind == "row" else node[1:]
            for child in children:
                add(element, child)

    ET.register_namespace("", MATH)
    root = ET.Element(f"{{{MATH}}}math")
    add(root, parse_formula(source))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def preview_html(source: str) -> str:
    def render(node):
        kind = node[0]
        if kind == "token":
            return escape(node[1])
        if kind == "row":
            return " ".join(render(value) for value in node[1])
        if kind == "frac":
            return '<table style="display:inline-table;vertical-align:middle;text-align:center;border-collapse:collapse"><tr><td style="border-bottom:1px solid;padding:0 8px">' + render(node[1]) + '</td></tr><tr><td>' + render(node[2]) + '</td></tr></table>'
        if kind == "sqrt":
            return "√(" + render(node[1]) + ")"
        tag = "sup" if kind == "sup" else "sub"
        return render(node[1]) + f"<{tag}>" + render(node[2]) + f"</{tag}>"

    return '<div style="font-size:28px;margin:24px">' + render(parse_formula(source)) + "</div>"


def write_formula(source: str, path: Path) -> None:
    extension = path.suffix.lower()
    if extension == ".formulaic":
        path.write_text(source, encoding="utf-8")
        return
    xml = mathml(source)
    if extension == ".mml":
        path.write_bytes(xml)
        return
    if extension != ".odf":
        raise ValueError("Choose .formulaic, .mml, or .odf")
    # OpenDocument Formula stores MathML directly as content.xml.
    content = xml
    manifest = ET.Element(f"{{{MANIFEST}}}manifest", {f"{{{MANIFEST}}}version": "1.3"})
    for name, media in (("/", MIME), ("content.xml", "text/xml")):
        ET.SubElement(manifest, f"{{{MANIFEST}}}file-entry", {f"{{{MANIFEST}}}full-path": name, f"{{{MANIFEST}}}media-type": media})
    with ZipFile(path, "w") as archive:
        archive.writestr("mimetype", MIME, compress_type=ZIP_STORED)
        archive.writestr("content.xml", content, compress_type=ZIP_DEFLATED)
        archive.writestr("META-INF/manifest.xml", ET.tostring(manifest, encoding="utf-8", xml_declaration=True), compress_type=ZIP_DEFLATED)


def read_formula(path: Path) -> str:
    if path.suffix.lower() == ".formulaic":
        return path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".odf":
        with ZipFile(path) as archive:
            if archive.read("mimetype").decode() != MIME:
                raise ValueError("This is not an OpenDocument Formula file")
            if archive.getinfo("content.xml").file_size > 16 * 1024 * 1024:
                raise ValueError("Formula markup is too large")
            data = archive.read("content.xml")
    elif path.suffix.lower() == ".mml":
        if path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("Formula markup is too large")
        data = path.read_bytes()
    else:
        raise ValueError("Choose .formulaic, .mml, or .odf")

    def source_for(node):
        if node.tag.startswith(f"{{{MATH}}}"):
            tag = node.tag.split("}", 1)[1]
        else:
            raise ValueError("Unsupported formula markup")
        children = list(node)
        if tag in {"math", "mrow"}:
            return " ".join(source_for(child) for child in children)
        if tag == "semantics":
            return source_for(children[0])
        if tag in {"mi", "mn", "mo", "mtext"}:
            return node.text or ""
        if tag == "mfrac" and len(children) == 2:
            return "{" + source_for(children[0]) + "} over {" + source_for(children[1]) + "}"
        if tag == "msqrt":
            return "sqrt {" + " ".join(source_for(child) for child in children) + "}"
        if tag in {"msup", "msub"} and len(children) == 2:
            return "{" + source_for(children[0]) + "}" + ("^" if tag == "msup" else "_") + "{" + source_for(children[1]) + "}"
        raise ValueError(f"Formulaic cannot edit MathML element {tag} without losing it")

    root = ET.fromstring(data)
    return source_for(root)


def export_preview(source: str, path: Path) -> None:
    document = QTextDocument()
    document.setHtml(preview_html(source))
    if path.suffix.lower() == ".pdf":
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(str(path))
        document.print_(printer)
    elif path.suffix.lower() == ".png":
        document.setTextWidth(800)
        picture = QImage(820, max(120, int(document.size().height()) + 20), QImage.Format_ARGB32)
        picture.fill(QColor("white"))
        painter = QPainter(picture)
        painter.translate(10, 10)
        document.drawContents(painter)
        painter.end()
        if not picture.save(str(path), "PNG"):
            raise OSError("Could not save the image")
    else:
        raise ValueError("Choose PDF or PNG")


class Formulaic(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Formulaic · FreeConvert")
        self.resize(850, 550)
        self.path = None
        area = QWidget()
        layout = QVBoxLayout(area)
        toolbar = QHBoxLayout()
        for title, callback in (("New", self.new), ("Open", self.open), ("Save", self.save), ("Save as", self.save_as), ("PDF", lambda: self.export("pdf")), ("PNG", lambda: self.export("png"))):
            control = QPushButton(title)
            control.clicked.connect(callback)
            toolbar.addWidget(control)
        layout.addLayout(toolbar)
        layout.addWidget(QLabel("Formula source · use {a} over {b}, sqrt {x}, x^2, x_1, and Greek names such as alpha"))
        self.source = QTextEdit()
        self.source.setPlaceholderText("{a+b} over {c+d}")
        layout.addWidget(self.source)
        layout.addWidget(QLabel("Preview"))
        self.preview = QTextBrowser()
        layout.addWidget(self.preview)
        self.setCentralWidget(area)
        self.source.textChanged.connect(self.refresh)
        self._theme()
        QApplication.instance().styleHints().colorSchemeChanged.connect(self._theme)
        self.refresh()

    def _theme(self, *_):
        dark = QApplication.instance().styleHints().colorScheme() == Qt.ColorScheme.Dark
        bg, ink, card, border = (("#0b1520", "#edf5f6", "#17232e", "#304551") if dark else
                                 ("#f6f9fb", "#14283d", "#ffffff", "#d8e4e9"))
        self.setStyleSheet(f"QMainWindow,QWidget{{background:{bg};color:{ink};font-size:14px}}"
                           f"QTextEdit,QTextBrowser{{background:{card};color:{ink};border:1px solid {border};border-radius:8px;padding:8px}}"
                           f"QPushButton{{background:{card};color:{ink};border:1px solid {border};border-radius:7px;padding:7px}}")

    def refresh(self):
        try:
            self.preview.setHtml(preview_html(self.source.toPlainText()))
            self.statusBar().clearMessage()
        except ValueError as error:
            self.preview.clear()
            self.statusBar().showMessage(str(error))

    def new(self):
        if not self._can_discard():
            return
        self.path = None
        self.source.clear()
        self.source.document().setModified(False)

    def _can_discard(self):
        return not self.source.document().isModified() or QMessageBox.question(
            self, "Unsaved formula", "Discard unsaved changes?", QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes

    def closeEvent(self, event):
        event.accept() if self._can_discard() else event.ignore()

    def open(self):
        name, _ = QFileDialog.getOpenFileName(self, "Open formula", "", "Formulas (*.formulaic *.mml *.odf)")
        if name and self._can_discard():
            path = Path(name)
            try:
                self.source.setPlainText(read_formula(path))
                self.path = path if path.suffix.lower() == ".formulaic" else None
                self.source.document().setModified(False)
            except (ValueError, OSError, KeyError, BadZipFile, ET.ParseError) as error:
                QMessageBox.warning(self, "Formulaic", str(error))

    def save(self):
        if self.path:
            self._write(self.path)
        else:
            self.save_as()

    def save_as(self):
        name, _ = QFileDialog.getSaveFileName(self, "Save formula", "", "Formulaic (*.formulaic);;MathML (*.mml);;OpenDocument Formula (*.odf)")
        if name:
            self._write(Path(name))

    def _write(self, path):
        try:
            write_formula(self.source.toPlainText(), path)
            if path.suffix.lower() == ".formulaic":
                self.path = path
                self.source.document().setModified(False)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Formulaic", str(error))

    def export(self, fmt):
        name, _ = QFileDialog.getSaveFileName(self, "Export formula", "", f"{fmt.upper()} (*.{fmt})")
        if name:
            try:
                export_preview(self.source.toPlainText(), Path(name))
            except (ValueError, OSError) as error:
                QMessageBox.warning(self, "Formulaic", str(error))
