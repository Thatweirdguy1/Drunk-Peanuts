"""Local File Converter desktop interface."""

from __future__ import annotations

import sys
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

import pypdfium2 as pdfium
from PIL import Image
from pypdf import PdfReader
from PySide6.QtCore import QPoint, QSettings, Qt, QThread, Signal, QTimer, QSize, QVariantAnimation, QEvent, QRectF
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPixmap, QAction, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QComboBox, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QDoubleSpinBox, QInputDialog, QMenu, QMessageBox, QProgressBar, QPushButton, QSizePolicy,
    QSplitter, QVBoxLayout, QWidget, QScrollArea, QLayout, QToolBar, QTabBar,
)

from converter import (available_formats, compress, convert, edit_image, extract_zip, kind, ocr_to_text,
                       pdf_merge, pdf_reorder, pdf_rotate, pdf_split, reduce_size, reduced_extension,
                       trim_media, zip_entries, pdfium_guard)
from office_pdf import LEGACY_FORMATS, LIBREOFFICE_FORMATS, available_engines, resolve_engine

VERSION = "0.29.1"


def numbered_target(folder: Path, stem: str, suffix: str, reserved: set[str], pages: int = 1) -> Path:
    """Reserve a fresh output name, including numbered PDF page images."""
    number = 1
    while True:
        name = stem if number == 1 else f"{stem} ({number})"
        target = folder / f"{name}{suffix}"
        outputs = [target] + [folder / f"{name}-{page}{suffix}" for page in range(2, pages + 1)]
        keys = {str(path.resolve()).casefold() for path in outputs}
        if all(not path.exists() for path in outputs) and not keys & reserved:
            reserved.update(keys)
            return target
        number += 1


def preferred_format(path: Path) -> str:
    choices = available_formats(path)
    preferences = {"Image": ("webp", "png"), "PDF": ("png",), "Video": ("mp4", "mkv"),
                   "Audio": ("mp3", "wav"), "Document": ("pdf",), "Spreadsheet": ("xlsx", "csv"),
                   "Text": ("pdf",)}.get(kind(path), ())
    return next((fmt for fmt in preferences if fmt in choices), choices[0] if choices else "")


@pdfium_guard()
def image_preview(path: Path) -> QImage | None:
    try:
        if path.suffix.lower() == ".pdf":
            pdf = pdfium.PdfDocument(str(path))
            try:
                if not len(pdf):
                    return None
                page = pdf[0]
                try:
                    scale = min(540 / page.get_width(), 420 / page.get_height(), 1.4)
                    bitmap = page.render(scale=scale)
                    try:
                        picture = bitmap.to_pil().copy()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
            finally:
                pdf.close()
        elif kind(path) == "Image" and path.suffix.lower() not in {".svg", ".cr2", ".nef", ".arw"}:
            with Image.open(path) as source:
                source.thumbnail((540, 420))
                picture = source.copy()
        else:
            return None
        picture.thumbnail((540, 420))
        picture = picture.convert("RGBA")
        data = picture.tobytes("raw", "RGBA")
        return QImage(data, picture.width, picture.height, QImage.Format_RGBA8888).copy()
    except Exception:
        return None


class PreviewWorker(QThread):
    ready = Signal(object, object)

    def __init__(self, path, parent):
        super().__init__(parent)
        self.path = path

    def run(self):
        self.ready.emit(self.path, image_preview(self.path))


class DropArea(QFrame):
    choose_requested = Signal()
    files_dropped = Signal(list)
    quick_files_dropped = Signal(list, QPoint)

    def __init__(self):
        super().__init__()
        self.setObjectName("dropArea")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName('Choose or drop local files')
        self._drop_level=0.0
        self._dragging=False
        self._drop_animation=QVariantAnimation(self)
        self._drop_animation.setDuration(180)
        self._drop_animation.valueChanged.connect(self._animate_drop)
        layout = QHBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        mark = QLabel("+")
        mark.setObjectName("dropMark")
        mark.setAlignment(Qt.AlignCenter)
        title = QLabel("Drop files here")
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignCenter)
        detail = QLabel("or choose files · Shift-drop for quick conversion")
        detail.setObjectName("muted")
        detail.setAlignment(Qt.AlignCenter)
        layout.addWidget(mark)
        text = QVBoxLayout()
        text.addWidget(title)
        text.addWidget(detail)
        layout.addLayout(text)
        for label in self.findChildren(QLabel):label.setAttribute(Qt.WA_TransparentForMouseEvents)

    def _animate_drop(self,value):
        self._drop_level=float(value);self.update()

    def _drop_feedback(self,active):
        self._drop_animation.stop()
        if not active:
            self._drop_level=0;self.update();return
        self._drop_animation.setStartValue(self._drop_level)
        self._drop_animation.setEndValue(1.0 if active else 0.0)
        self._drop_animation.start()

    def enterEvent(self,event):
        if self.isEnabled():self._drop_feedback(True)
        super().enterEvent(event)

    def leaveEvent(self,event):
        if not self._dragging:self._drop_feedback(False)
        super().leaveEvent(event)

    def hideEvent(self,event):
        self._dragging=False;self._drop_animation.stop();self._drop_level=0;super().hideEvent(event)

    def event(self,event):
        if hasattr(self,'_drop_animation') and (event.type()==QEvent.WindowDeactivate or event.type()==QEvent.EnabledChange and not self.isEnabled()):
            self._dragging=False;self._drop_animation.stop();self._drop_level=0;self.update()
        return super().event(event)

    def paintEvent(self,event):
        super().paintEvent(event)
        if self._drop_level:
            painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing)
            level=self._drop_level;painter.setBrush(QColor(255,221,34,round(18*level)))
            painter.setPen(QPen(QColor(255,221,34,round(235*level)),1+level))
            inset=7-5*level;painter.drawRoundedRect(QRectF(self.rect()).adjusted(inset,inset,-inset,-inset),5,5)

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.choose_requested.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Return,Qt.Key_Space):
            self.choose_requested.emit()
        else:super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()
            self._dragging=True;self._drop_feedback(True)

    def dragLeaveEvent(self,event):
        self._dragging=False;self._drop_feedback(False);event.accept()

    def dropEvent(self, event):
        self._dragging=False;self._drop_feedback(self.underMouse())
        files = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if event.modifiers() & Qt.ShiftModifier:
            self.quick_files_dropped.emit(files, self.mapToGlobal(event.position().toPoint()))
        else:
            self.files_dropped.emit(files)
        event.acceptProposedAction()


class Worker(QThread):
    update = Signal(int, str, str)
    finished_batch = Signal(int, int)

    def __init__(self, jobs: list[tuple[Path, Path]], archive: Path | None = None, target_mb: float | None = None,
                 operation: Callable[[Path, Path], None] | None = None, rows: list[int] | None = None,
                 engines: dict[Path, str] | None = None):
        super().__init__()
        self.jobs = jobs
        self.archive = archive
        self.target_mb = target_mb
        self.operation = operation
        self.rows = rows or list(range(len(jobs)))
        self.engines = engines or {}

    def run(self):
        done = failed = 0
        if self.archive:
            try:
                compress([source for source, _ in self.jobs], self.archive,
                         lambda index, name: self.update.emit(self.rows[index], "Compressed", name))
                done = len(self.jobs)
            except Exception as error:
                failed = len(self.jobs)
                self.update.emit(self.rows[0], "Failed", str(error))
            self.finished_batch.emit(done, failed)
            return
        def perform(index: int, source: Path, target: Path):
            row = self.rows[index]
            self.update.emit(row, "Processing" if self.operation else "Reducing size" if self.target_mb else "Converting", source.name)
            try:
                if self.operation:
                    self.operation(source, target)
                elif self.target_mb:
                    reduce_size(source, target, self.target_mb)
                else:
                    if source in self.engines:
                        convert(source, target, self.engines[source])
                    else:
                        convert(source, target)
                self.update.emit(row, "Done", target.name)
                return True
            except Exception as error:
                self.update.emit(row, "Failed", str(error))
                return False

        # ponytail: two workers cap CPU and disk contention; raise only if benchmarks justify it.
        with ThreadPoolExecutor(max_workers=min(2, len(self.jobs))) as pool:
            futures = [pool.submit(perform, index, source, target) for index, (source, target) in enumerate(self.jobs)]
            for future in as_completed(futures):
                if future.result():
                    done += 1
                else:
                    failed += 1
        self.finished_batch.emit(done, failed)


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Drunk Peanuts {VERSION}")
        self.resize(1080, 830)
        self.setMinimumSize(760, 540)
        self.preview_worker = None
        self.preview_pending = None
        self.paths: list[Path] = []
        self.formats: dict[Path, str] = {}
        self.engines: dict[Path, str] = {}
        self.worker: Worker | None = None
        self.screenwriter = None
        self.watchit = None
        self.watchit_loader = None
        self.pending_media = []
        self.workspaces = {}
        self.last_error = ""
        self.settings = QSettings("Local File Converter", "Local File Converter")
        self.output_dir = Path(self.settings.value("output_dir", str(Path.home() / "Downloads")))
        self._build()
        self._theme()
        self._refresh_formats()
        QApplication.instance().styleHints().colorSchemeChanged.connect(self._theme)

    def _build(self):
        root = QWidget()
        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(12, 8, 12, 8)
        shell_layout.setSpacing(8)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setWidget(root)
        self.scroll.setMinimumHeight(120)
        shell_layout.addWidget(self.scroll, 1)
        self.setCentralWidget(shell)
        page = QVBoxLayout(root)
        page.setSizeConstraint(QLayout.SetMinimumSize)
        page.setContentsMargins(12, 8, 12, 8)
        page.setSpacing(12)

        header_panel = QWidget()
        header_panel.setObjectName("brandBar")
        header = QHBoxLayout(header_panel)
        header.setContentsMargins(10, 3, 10, 3)
        brand = QVBoxLayout()
        eyebrow = QLabel("LOCAL  /  PRIVATE  /  FREE")
        eyebrow.setObjectName("eyebrow")
        title = QLabel()
        title.setObjectName("title")
        title.setPixmap(QPixmap(str(Path(__file__).resolve().parent / 'assets' / 'logo.png')).scaledToHeight(48, Qt.SmoothTransformation))
        title.setAccessibleName("Drunk Peanuts.")
        brand.addWidget(eyebrow)
        brand.addWidget(title)
        header.addLayout(brand)
        header.addStretch()
        self.add_button = QPushButton("Add files")
        self.add_button.setObjectName("primaryButton")
        self.add_button.clicked.connect(self._choose_files)
        header.addWidget(self.add_button)
        page.addWidget(header_panel)

        subtitle = QLabel("Convert files and create documents, tables, slides, formulas, drawings, databases, and scripts on your computer.")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        self.subtitle = subtitle
        page.addWidget(subtitle)

        spaces = QToolBar("Workspaces", self)
        spaces.setMovable(False)
        spaces.setToolButtonStyle(Qt.ToolButtonTextOnly)
        spaces.setObjectName("workspaces")
        for name in ("Pages", "Tables", "Dazzle", "Sketch", "Organize", "Formulaic"):
            spaces.addAction(name, lambda checked=False, workspace=name: self._open_workspace(workspace))
        spaces.addAction("Writer's Drafts", self._screenwriter)
        spaces.addAction("Play", self._watchit)
        self.menuBar().addAction("Document pages", self._document_pages)
        self.addToolBar(spaces)
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction("Add files…", self._choose_files)
        file_menu.addAction("Output folder…", self._choose_directory)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)
        tools_menu = self.menuBar().addMenu("Tools")
        for index, name in enumerate(("Convert files", "Reduce file size", "Create ZIP", "Extract ZIP")):
            tools_menu.addAction(name, lambda checked=False, i=index: self._show_converter_task(i))
        from office_templates import TEMPLATES
        templates = self.menuBar().addMenu("Templates")
        for workspace, names in TEMPLATES.items():
            menu = templates.addMenu(workspace)
            for name in names:
                menu.addAction(Path(name).stem, lambda checked=False, w=workspace, n=name: self._choose_template(w, n))

        self.drop = DropArea()
        self.drop.setMinimumHeight(72)
        self.drop.setMaximumHeight(90)
        self.drop.files_dropped.connect(self._add_files)
        self.drop.quick_files_dropped.connect(self._quick_drop)
        self.drop.choose_requested.connect(self._choose_files)
        page.addWidget(self.drop)

        section = QHBoxLayout()
        queue_title = QLabel("Your files")
        queue_title.setObjectName("sectionTitle")
        self.count = QLabel("0 files")
        self.count.setObjectName("muted")
        section.addWidget(queue_title)
        section.addWidget(self.count)
        section.addStretch()
        clear_button = QPushButton("Clear queue")
        clear_button.setObjectName("textButton")
        clear_button.clicked.connect(self._clear)
        section.addWidget(clear_button)
        self.clear_button = clear_button
        self.remove_button = QPushButton("Remove selected")
        self.remove_button.setObjectName("textButton")
        self.remove_button.clicked.connect(self._remove_selected)
        section.addWidget(self.remove_button)
        page.addLayout(section)

        splitter = QSplitter(Qt.Horizontal)
        self.list = QListWidget()
        self.list.setObjectName("fileList")
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.currentRowChanged.connect(self._select)
        splitter.addWidget(self.list)

        preview = QFrame()
        preview.setObjectName("previewPanel")
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(23, 22, 23, 22)
        preview_layout.setSpacing(14)
        preview_title = QLabel("PREVIEW")
        preview_title.setObjectName("eyebrow")
        preview_layout.addWidget(preview_title)
        self.preview = QLabel("Select a file to see its preview")
        self.preview.setObjectName("previewImage")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(120)
        self.preview.setMaximumHeight(140)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout.addWidget(self.preview)
        self.details = QLabel("Input and output details appear here")
        self.details.setObjectName("muted")
        self.details.setWordWrap(True)
        preview_layout.addWidget(self.details)
        splitter.addWidget(preview)
        splitter.setSizes([620, 360])
        splitter.setMinimumHeight(190)
        page.addWidget(splitter, 1)

        controls = QFrame()
        controls.setObjectName("controls")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(16, 12, 16, 12)
        controls_layout.setSpacing(8)
        self.task_tabs = QTabBar()
        self.task_tabs.setExpanding(False)
        for name in ("Convert", "Reduce size", "Create ZIP", "Extract ZIP"):
            self.task_tabs.addTab(name)
        controls_layout.addWidget(self.task_tabs)
        controls_top = QHBoxLayout()
        format_label = QLabel("Convert to")
        self.format_label = format_label
        format_label.setObjectName("fieldLabel")
        controls_top.addWidget(format_label)
        self.format = QComboBox()
        self.format.setMinimumWidth(140)
        self.format.currentTextChanged.connect(self._set_format)
        controls_top.addWidget(self.format)
        controls_top.addStretch()
        controls_layout.addLayout(controls_top)
        destination_row = QHBoxLayout()
        destination_label = QLabel("Save in")
        destination_label.setObjectName("fieldLabel")
        destination_row.addWidget(destination_label)
        self.destination = QPushButton(str(self.output_dir))
        self.destination.setObjectName("directoryButton")
        self.destination.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.destination.setToolTip(str(self.output_dir))
        self.destination.clicked.connect(self._choose_directory)
        destination_row.addWidget(self.destination, 1)
        self.convert_button = QPushButton("Convert files")
        self.convert_button.setObjectName("primaryButton")
        self.convert_button.clicked.connect(self._convert)
        quick_convert = QAction("Convert queued files", self)
        quick_convert.setShortcut("Shift+Return")
        quick_convert.triggered.connect(self.convert_button.click)
        self.addAction(quick_convert)
        self.convert_button.setToolTip("Convert queued files (Shift+Enter). Shift-drop files for the quick-format menu.")
        controls_top.addWidget(self.convert_button)
        self.compress_button = QPushButton("Compress to ZIP")
        self.compress_button.setObjectName("secondaryButton")
        self.compress_button.clicked.connect(self._compress)
        controls_top.addWidget(self.compress_button)
        controls_layout.addLayout(destination_row)
        self.pdf_engine_panel = QWidget()
        engine_row = QHBoxLayout(self.pdf_engine_panel)
        engine_row.setContentsMargins(0, 0, 0, 0)
        self.engine_label = QLabel("PDF renderer")
        self.engine_label.setObjectName("fieldLabel")
        engine_row.addWidget(self.engine_label)
        self.pdf_engine = QComboBox()
        self.pdf_engine.currentIndexChanged.connect(self._set_engine)
        engine_row.addWidget(self.pdf_engine)
        self.engine_hint = QLabel("For the selected Office file")
        self.engine_hint.setObjectName("muted")
        engine_row.addWidget(self.engine_hint)
        engine_row.addStretch()
        controls_layout.addWidget(self.pdf_engine_panel)
        self.pdf_engine_panel.hide()
        self.reduce_panel = QWidget()
        reduce_row = QHBoxLayout(self.reduce_panel)
        reduce_row.setContentsMargins(0, 0, 0, 0)
        reduce_label = QLabel("Target size per file")
        reduce_label.setObjectName("fieldLabel")
        reduce_row.addWidget(reduce_label)
        self.target_size = QDoubleSpinBox()
        self.target_size.setMinimum(0.1)
        self.target_size.setMaximum(100000)
        self.target_size.setValue(100)
        self.target_size.setDecimals(1)
        self.target_size.setSuffix(" MB")
        self.target_size.setToolTip("Each output must be at or below this size")
        reduce_row.addWidget(self.target_size)
        reduce_row.addStretch()
        self.reduce_button = QPushButton("Reduce file size")
        self.reduce_button.setObjectName("secondaryButton")
        self.reduce_button.clicked.connect(self._reduce)
        reduce_row.addWidget(self.reduce_button)
        controls_layout.addWidget(self.reduce_panel)
        tools_row = QHBoxLayout()
        self.pdf_button = QPushButton("PDF tools")
        self.pdf_button.setObjectName("textButton")
        self.pdf_button.clicked.connect(self._pdf_tools)
        tools_row.addWidget(self.pdf_button)
        self.image_button = QPushButton("Image tools")
        self.image_button.setObjectName("textButton")
        self.image_button.clicked.connect(self._image_tools)
        tools_row.addWidget(self.image_button)
        self.media_button = QPushButton("Media trim")
        self.media_button.setObjectName("textButton")
        self.media_button.clicked.connect(self._media_tools)
        tools_row.addWidget(self.media_button)
        self.zip_button = QPushButton("Open ZIP")
        self.zip_button.setObjectName("secondaryButton")
        self.zip_button.clicked.connect(self._zip_tools)
        controls_top.addWidget(self.zip_button)
        self.ocr_button = QPushButton("OCR to text")
        self.ocr_button.setObjectName("textButton")
        self.ocr_button.clicked.connect(self._ocr_tools)
        tools_row.addWidget(self.ocr_button)
        controls_layout.addLayout(tools_row)
        self.task_tabs.currentChanged.connect(self._set_task)
        self._set_task(0)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        controls_layout.addWidget(self.progress)
        self.status = QLabel("Ready. Your files stay on this device.")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        controls_layout.addWidget(self.status)
        shell_layout.addWidget(controls)

    def _set_task(self, index):
        for widget in (self.format_label, self.format, self.convert_button):
            widget.setVisible(index == 0)
        self.reduce_panel.setVisible(index == 1)
        self.compress_button.setVisible(index == 2)
        self.zip_button.setVisible(index == 3)

    def _theme(self, *_):
        from ui import palette
        p = palette()
        bg, card, text, muted, border, drop = (p[key] for key in ('bg', 'card', 'ink', 'muted', 'border', 'hover'))
        self.setStyleSheet(f"""
            QWidget {{ background: {bg}; color: {text}; font-family: 'Segoe UI', 'SF Pro Text', sans-serif; font-size: 13px; }}
            QWidget#brandBar {{ background: black; }}
            QWidget#brandBar QLabel {{ background: transparent; }}
            QMenuBar, QMenu {{ background: {card}; color: {text}; }}
            QMenu::item {{ padding: 5px 20px; }}
            QMenu::item:selected {{ background: {drop}; }}
            QTabBar::tab {{ background: transparent; padding: 7px 14px; color: {muted}; border-bottom: 2px solid transparent; }}
            QTabBar::tab:selected {{ color: #ffdd22; border-bottom-color: #ffdd22; }}
            QTabBar::tab:hover:enabled {{ background: {drop}; color: #ffdd22; }}
            QLabel#title {{ font-size: 32px; font-weight: 750; }}
            QLabel#eyebrow {{ color: #ffdd22; font-size: 10px; font-weight: 700; letter-spacing: 2px; }}
            QLabel#sectionTitle {{ font-size: 15px; font-weight: 650; }}
            QLabel#dropTitle {{ font-size: 17px; font-weight: 700; }}
            QLabel#dropMark {{ font-size: 34px; font-weight: 300; color: #ffdd22; }}
            QLabel#muted {{ color: {muted}; }}
            QLabel#fieldLabel {{ font-weight: 700; }}
            QFrame#dropArea {{ background: transparent; border: 1px dashed #78529c; border-radius: 3px; }}
            QFrame#workspaces {{ background: {card}; border: 1px solid {border}; border-radius: 12px; }}
            QToolBar {{ background: {card}; border: none; padding: 3px 6px; spacing: 2px; }}
            QToolButton {{ background: transparent; color: {text}; padding: 6px; border: 1px solid transparent; border-radius: 3px; }}
            QToolButton:hover {{ background: {drop}; color: #ffdd22; border-color: #ffdd22; }}
            QPushButton#workspaceButton {{ background: transparent; border: none; color: {text}; padding: 8px 6px; }}
            QPushButton#workspaceButton:hover {{ background: {drop}; color: #ffdd22; }}
            QFrame#dropArea QLabel {{ background: transparent; }}
            QFrame#previewPanel, QFrame#controls {{ background: {card}; border: none; border-radius: 3px; }}
            QFrame#previewPanel QLabel, QFrame#controls QLabel {{ background: transparent; }}
            QLabel#previewImage {{ background: {drop}; border: none; border-radius: 2px; color: {muted}; }}
            QListWidget#fileList {{ background: {card}; border: none; border-radius: 2px; padding: 3px; outline: none; }}
            QListWidget::item {{ padding: 7px; margin: 1px; border-radius: 2px; }}
            QListWidget::item:selected {{ background: {drop}; color: {text}; }}
            QPushButton {{ min-height: 28px; padding: 2px 11px; border: 1px solid transparent; border-radius: 3px; font-weight: 500; }}
            QPushButton:hover {{ background: {drop}; border-color: #ffdd22; }}
            QPushButton:pressed, QToolButton:pressed {{ background: #d6b917; color: black; }}
            QPushButton#primaryButton {{ background: #ffdd22; color: #0b0b0b; border: 1px solid #ffdd22; }}
            QPushButton#primaryButton:hover {{ background: #fff176; border-color: #fff176; }}
            QPushButton#primaryButton:disabled {{ background: #403b24; color: #aaa99f; border-color: #403b24; }}
            QPushButton#secondaryButton, QPushButton#directoryButton {{ background: {card}; border: 1px solid {border}; }}
            QPushButton#secondaryButton:hover, QPushButton#directoryButton:hover {{ background: {drop}; border-color: #ffdd22; }}
            QPushButton#textButton {{ background: transparent; border: 1px solid transparent; color: #ffdd22; }}
            QPushButton#textButton:hover {{ background: {drop}; border-color: #ffdd22; }}
            QPushButton#textButton:disabled, QToolButton:disabled {{ color: #69695f; border-color: transparent; }}
            QPushButton:focus, QComboBox:focus, QListWidget:focus {{ border: 2px solid #a66ce0; }}
            QComboBox {{ background: {card}; border: 1px solid {border}; border-radius: 3px; min-height: 28px; padding: 2px 8px; }}
            QDoubleSpinBox {{ background: {card}; border: 1px solid {border}; border-radius: 3px; min-height: 28px; padding: 2px 8px; min-width: 90px; }}
            QComboBox QAbstractItemView {{ background: {card}; color: {text}; selection-background-color: {drop}; }}
            QProgressBar {{ height: 7px; background: {drop}; border: none; border-radius: 3px; }}
            QProgressBar::chunk {{ background: #ffdd22; border-radius: 3px; }}
        """)
        from ui import icon
        for button, name in ((self.pdf_button, "export"), (self.image_button, "pen"),
                             (self.media_button, "cut"), (self.ocr_button, "find")):
            button.setIcon(icon(name, p['accent'] if button.isEnabled() else muted))
            button.setIconSize(QSize(18, 18))

    def _choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Choose files")
        self._add_files([Path(file) for file in files])

    def _screenwriter(self):
        from screenwriter import ScreenwriterWindow
        if self.screenwriter is None:
            self.screenwriter = ScreenwriterWindow()
            self._workspace_templates(self.screenwriter, "Writer's Drafts")
        self.screenwriter.show()
        self.screenwriter.raise_()
        self.screenwriter.activateWindow()
        return self.screenwriter

    def _watchit(self):
        if not hasattr(self, 'play_inbox'):
            from play_queue import PlayInbox
            self.play_inbox = PlayInbox(self, self._queue_play)
        if self.watchit is not None:
            self.watchit.show()
            self.watchit.raise_()
            self.watchit.activateWindow()
            return
        from watchit import EngineLoader, WatchIT
        self.watchit = WatchIT(deferred=True)
        self.watchit.show()
        self.watchit.raise_()
        self.watchit.activateWindow()
        if self.watchit_loader is not None:
            return
        self.status.setText("Starting Play playback engine… You can continue using the converter.")
        self.watchit_loader = EngineLoader(self)
        self.watchit_loader.ready.connect(self._watchit_ready)
        self.watchit_loader.failed.connect(lambda message: QMessageBox.warning(self, "Play", message))
        self.watchit_loader.finished.connect(self._watchit_loader_finished)
        self.watchit_loader.start()

    def _watchit_ready(self, engine):
        try:
            self.watchit.set_engine(engine)
            pending, self.pending_media = self.pending_media, []
            for names, enqueue in pending:
                self.watchit.add_media(names, autoplay=not enqueue)
        except Exception as error:
            QMessageBox.warning(self, "Play", str(error))

    def _watchit_loader_finished(self):
        self.watchit_loader.deleteLater()
        self.watchit_loader = None
        self.status.setText("Play ready." if self.watchit is not None and self.watchit.player is not None else "Play could not start. Close its window and try opening it again.")

    def _open_workspace(self, name: str):
        from office_suite import WORKSPACES
        if name not in self.workspaces:
            self.workspaces[name] = WORKSPACES[name]()
            self._workspace_templates(self.workspaces[name], name)
        window = self.workspaces[name]
        window.show()
        window.raise_()
        window.activateWindow()
        return window

    def create_from_template(self, workspace, name, destination):
        from office_templates import ASSETS, create_document
        from office_suite import WORKSPACES
        from screenwriter import ScreenwriterWindow
        target = create_document(workspace, name, destination)
        window = ScreenwriterWindow() if workspace == "Writer's Drafts" else WORKSPACES[workspace]()
        self._workspace_templates(window, workspace)
        self.workspaces[f"template:{target}"] = window
        (window._open if workspace == "Writer's Drafts" else window.open)(target)
        if workspace == 'Pages':
            window.editor.setHtml((ASSETS / 'templates' / Path(name).with_suffix('.html')).read_text(encoding='utf-8'))
            window.imported_docx = None
            window.original_paragraphs = []
            window.editor.document().setModified(False)
        window.path = target
        window.show()
        window.raise_()
        window.activateWindow()
        return window

    def _workspace_templates(self, window, workspace):
        from office_templates import TEMPLATES
        menu = window.menuBar().addMenu('Templates')
        for name in TEMPLATES.get(workspace, ()):
            menu.addAction(Path(name).stem, lambda checked=False, n=name: self._choose_template(workspace, n, window))

    def _choose_template(self, workspace, name, parent=None):
        destination, _ = QFileDialog.getSaveFileName(parent or self, "Create document from template",
            str(self.output_dir / name), f"{workspace} (*{Path(name).suffix})")
        if not destination:
            return
        target = Path(destination)
        if not target.suffix:
            target = target.with_suffix(Path(name).suffix)
        try:
            self.create_from_template(workspace, name, target)
        except PermissionError:
            QMessageBox.warning(parent or self, 'Cannot save here', 'Choose a folder where you have write access, such as Documents. Templates do not need administrator permission.')
        except FileExistsError:
            QMessageBox.warning(parent or self, 'File already exists', 'Choose a new filename. Your existing document has not been replaced.')
        except Exception as error:
            QMessageBox.warning(parent or self, "Could not create document", str(error))

    def open_arguments(self, arguments):
        from windows_integration import WORKSPACE_EXTENSIONS
        workspace = None
        if arguments[:1] == ['--open-workspace']:
            if len(arguments) < 2 or arguments[1] not in WORKSPACE_EXTENSIONS:
                QMessageBox.warning(self, 'Cannot open workspace', 'Unknown Office workspace.')
                return
            workspace = arguments[1]
            arguments = arguments[2:]
            if not arguments:
                if workspace == 'Writer':self._screenwriter()
                elif workspace == 'Play':self._watchit()
                else:self._open_workspace(workspace)
                return
        play = arguments[:1] in (["--play"], ["--enqueue"])
        if play or workspace == 'Play':
            self._queue_play(arguments[1:] if play else arguments, arguments[:1] == ['--enqueue'])
            return
        files = [Path(name).resolve() for name in arguments
                 if not name.startswith("--") and Path(name).is_file()]
        if not files:
            self.show()
            return
        media = [path for path in files if path.suffix.lower() in WORKSPACE_EXTENSIONS['Play']]
        if media:
            self._queue_play(media)
        other = [path for path in files if path not in media]
        if other:
            remaining = []
            for path in other:
                name = workspace or next((w for w, extensions in WORKSPACE_EXTENSIONS.items() if path.suffix.lower() in extensions), None)
                if name is None:
                    remaining.append(path)
                    continue
                if path.suffix.lower() not in WORKSPACE_EXTENSIONS[name]:
                    QMessageBox.warning(self, 'Unsupported file', f'{name} cannot open {path.suffix} files.')
                    continue
                from office_suite import WORKSPACES
                from screenwriter import ScreenwriterWindow
                window = ScreenwriterWindow() if name == 'Writer' else WORKSPACES[name]()
                self._workspace_templates(window, "Writer's Drafts" if name == 'Writer' else name)
                self.workspaces[f'open:{id(window)}'] = window
                (window._open if name == 'Writer' else window.open)(path)
                window.show();window.raise_();window.activateWindow()
            if remaining:
                self.show()
                self._add_files(remaining)

    def _queue_play(self, names, enqueue=False):
        names = [Path(name).resolve() for name in names if not str(name).startswith('--')]
        self._watchit()
        if self.watchit.player is None:
            self.pending_media.append((names, enqueue))
        elif names:
            self.watchit.add_media(names, autoplay=not enqueue)

    def _show_converter_task(self, index):
        if hasattr(self, 'dashboard_converter'):
            self.dashboard_converter()
        self.task_tabs.setCurrentIndex(index)

    def _add_files(self, files: list[Path]):
        if self.worker and self.worker.isRunning():
            return
        if files and hasattr(self, 'dashboard_converter'):
            self.dashboard_converter()
        rejected = 0
        for path in files:
            try:
                supported = path.is_file() and (available_formats(path) or path.suffix.lower() == ".zip")
            except (OSError, ValueError):
                supported = False
            if not supported:
                rejected += 1
                continue
            path = path.resolve()
            if path in self.paths:
                continue
            self.paths.append(path)
            self.formats[path] = preferred_format(path) if path.suffix.lower() != ".zip" else ""
            self.engines[path] = "auto"
            label = f"{path.name}\n{kind(path).upper() if path.suffix.lower() != '.zip' else 'ZIP'} → {self.formats[path].upper() if self.formats[path] else 'EXTRACT'}  ·  {path.stat().st_size / 1024 / 1024:.1f} MB  ·  Waiting"
            self.list.addItem(QListWidgetItem(label))
        self.count.setText(f"{len(self.paths)} file{'s' if len(self.paths) != 1 else ''}")
        self.drop.setVisible(not self.paths)
        self.subtitle.setVisible(not self.paths)
        if self.paths and self.list.currentRow() < 0:
            self.list.setCurrentRow(0)
        if rejected:
            self.status.setText(f"Skipped {rejected} unsupported item{'s' if rejected != 1 else ''}.")
        self._refresh_formats()

    def _clear(self):
        if self.worker and self.worker.isRunning():
            return
        self.paths.clear()
        self.preview_pending = None
        self.formats.clear()
        self.engines.clear()
        self.list.clear()
        self.format.clear()
        self.preview.setPixmap(QPixmap())
        self.preview.setText("Select a file to see its preview")
        self.details.setText("Input and output details appear here")
        self.count.setText("0 files")
        self.progress.setValue(0)
        self.status.setText("Ready. Your files stay on this device.")
        self.drop.show()
        self.subtitle.show()
        self._refresh_formats()

    def _remove_selected(self):
        if self.worker and self.worker.isRunning():
            return
        row = self.list.currentRow()
        if 0 <= row < len(self.paths):
            path = self.paths.pop(row)
            self.formats.pop(path, None)
            self.engines.pop(path, None)
            self.list.takeItem(row)
            if not self.paths:
                self._clear()
            else:
                self.count.setText(f"{len(self.paths)} file{'s' if len(self.paths) != 1 else ''}")
                self._select(self.list.currentRow())

    def _select(self, row: int):
        if row < 0 or row >= len(self.paths):
            return
        path = self.paths[row]
        self.preview.setPixmap(QPixmap())
        self.preview.setText(f"{path.suffix.upper().lstrip('.')}  ·  {kind(path)}")
        self.preview_pending = path
        self._start_preview()
        self._refresh_formats()
        self._refresh_details()

    def _start_preview(self):
        if self.preview_worker is not None or self.preview_pending is None:
            return
        path, self.preview_pending = self.preview_pending, None
        if kind(path) not in {"Image", "PDF"}:
            return
        self.preview_worker = PreviewWorker(path, self)
        self.preview_worker.ready.connect(self._preview_ready)
        self.preview_worker.finished.connect(self._preview_finished)
        self.preview_worker.start()

    def _preview_ready(self, path, picture):
        row = self.list.currentRow()
        if 0 <= row < len(self.paths) and self.paths[row] == path and picture is not None:
            self.preview.setPixmap(QPixmap.fromImage(picture).scaled(
                max(1, self.preview.width() - 16), 112, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _preview_finished(self):
        self.preview_worker.deleteLater()
        self.preview_worker = None
        self._start_preview()

    def _set_format(self, fmt: str):
        row = self.list.currentRow()
        if 0 <= row < len(self.paths) and fmt:
            self.formats[self.paths[row]] = fmt
            item = self.list.item(row)
            item.setText(f"{self.paths[row].name}\n{kind(self.paths[row]).upper()} → {fmt.upper()}  ·  Waiting")
        self._refresh_engine()
        self._refresh_details()

    def _set_engine(self, _index: int):
        row = self.list.currentRow()
        if 0 <= row < len(self.paths) and self.pdf_engine.currentData():
            self.engines[self.paths[row]] = self.pdf_engine.currentData()
        self._refresh_details()

    def _refresh_engine(self):
        row = self.list.currentRow()
        path = self.paths[row] if 0 <= row < len(self.paths) else None
        office_pdf = bool(path and self.formats.get(path) == "pdf" and
                          path.suffix.lower().lstrip(".") in LIBREOFFICE_FORMATS)
        pdf_docx = bool(path and path.suffix.lower() == ".pdf" and self.formats.get(path) == "docx")
        office_cross = bool(path and path.suffix.lower().lstrip(".") in LIBREOFFICE_FORMATS - LEGACY_FORMATS and
                            self.formats.get(path) in {"docx", "odt", "rtf", "xlsx", "ods", "pptx", "odp"} and
                            "libreoffice" in available_engines(path))
        self.pdf_engine_panel.setVisible(office_pdf or pdf_docx or office_cross)
        if not (office_pdf or pdf_docx or office_cross):
            return
        self.engine_label.setText("PDF to DOCX mode" if pdf_docx else "PDF renderer" if office_pdf else "Conversion engine")
        self.engine_hint.setText("Editable text + separate images; complex layouts may reflow" if pdf_docx else "For the selected Office file")
        if pdf_docx:
            choices = [("Editable text and images", "editable"), ("Preserve pages (not editable)", "visual"), ("Text only (drops images/layout)", "text")]
        elif office_cross:
            choices = [("Built-in (basic)", "built-in"), ("LibreOffice (installed)", "libreoffice")]
        else:
            choices = [("Automatic (best installed)", "auto")]
            available = available_engines(path)
            if "built-in" in available:
                choices.append(("Built-in (basic)", "built-in"))
            if "microsoft" in available:
                choices.append(("Microsoft Office (installed)", "microsoft"))
            if "libreoffice" in available:
                choices.append(("LibreOffice (installed)", "libreoffice"))
        self.pdf_engine.blockSignals(True)
        self.pdf_engine.clear()
        for label, value in choices:
            self.pdf_engine.addItem(label, value)
        selected = self.engines.get(path, "auto")
        index = self.pdf_engine.findData(selected)
        self.pdf_engine.setCurrentIndex(index if index >= 0 else 0)
        if index < 0:
            self.engines[path] = "editable" if pdf_docx else "auto" if office_pdf else "built-in"
        self.pdf_engine.blockSignals(False)

    def _refresh_details(self):
        row = self.list.currentRow()
        if 0 <= row < len(self.paths):
            path = self.paths[row]
            target = self.formats.get(path, "—").upper()
            note = ""
            if path.suffix.lower() == ".pdf" and target == "DOCX":
                engine = self.engines.get(path, 'editable')
                note = ('\nComplete page images; text is not editable.' if engine == 'visual' else '\nSelectable text only; images/layout omitted.' if engine == 'text' else '\nEditable paragraphs and separate images. Complex columns, tables and typography may reflow; scanned pages require OCR.')
            if target == "PDF" and path.suffix.lower().lstrip(".") in LIBREOFFICE_FORMATS:
                chosen = resolve_engine(path, self.engines.get(path, "auto"))
                note = f"\nPDF renderer: {chosen}. Installed application required for its native layout."
            elif self.engines.get(path) == "libreoffice":
                note = "\nUsing installed LibreOffice for format conversion."
            self.details.setText(f"{path.name}\n{kind(path)} input  →  {target} output{note}")

    def _refresh_formats(self):
        row = self.list.currentRow()
        path = self.paths[row] if 0 <= row < len(self.paths) else None
        choices = available_formats(path) if path else []
        self.format.blockSignals(True)
        self.format.clear()
        self.format.addItems(choices)
        if path:
            self.format.setCurrentText(self.formats[path])
        self.format.blockSignals(False)
        self._refresh_engine()
        idle = not (self.worker and self.worker.isRunning())
        self.convert_button.setEnabled(bool(self.paths) and all(self.formats.values()) and idle)
        self.compress_button.setEnabled(bool(self.paths) and idle)
        self.reduce_button.setEnabled(bool(self.paths) and all(reduced_extension(path) for path in self.paths) and idle)
        self.pdf_button.setEnabled(any(path.suffix.lower() == ".pdf" for path in self.paths) and idle)
        self.image_button.setEnabled(any(kind(path) == "Image" for path in self.paths) and idle)
        self.media_button.setEnabled(any(kind(path) in {"Video", "Audio"} for path in self.paths) and idle)
        self.zip_button.setEnabled(any(path.suffix.lower() == ".zip" for path in self.paths) and idle)
        self.ocr_button.setEnabled(any(kind(path) in {"Image", "PDF"} for path in self.paths) and idle)
        self.clear_button.setEnabled(bool(self.paths) and idle)
        self.remove_button.setEnabled(path is not None and idle)
        self.format.setEnabled(path is not None and idle)
        self.destination.setEnabled(idle)
        self.pdf_engine.setEnabled(idle)
        self._refresh_details()

    def _choose_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Choose output folder", str(self.output_dir))
        if directory:
            self.output_dir = Path(directory)
            self.settings.setValue("output_dir", directory)
            self.destination.setText(directory)
            self.destination.setToolTip(directory)

    def _quick_drop(self, files: list[Path], position: QPoint):
        if self.worker and self.worker.isRunning():
            return
        paths = self.paths + [path.resolve() for path in files if path.is_file() and available_formats(path) and path.resolve() not in self.paths]
        if not paths:
            return
        common = set(available_formats(paths[0]))
        for path in paths[1:]:
            common.intersection_update(available_formats(path))
        if not common:
            self.status.setText("These files have no shared output format. Convert them in separate batches.")
            return
        menu = QMenu(self)
        choices = {menu.addAction(fmt.upper()): fmt for fmt in sorted(common)}
        chosen = menu.exec(position)
        if chosen:
            self._add_files(files)
            for row, path in enumerate(self.paths):
                self.formats[path] = choices[chosen]
                self.list.item(row).setText(f"{path.name}\n{kind(path).upper()} → {choices[chosen].upper()}  ·  Waiting")
            self._refresh_formats()
            self._convert()

    def _convert(self):
        if not self.paths or not all(self.formats.values()):
            return
        jobs = []
        reserved = {str(path).casefold() for path in self.paths}
        try:
            for source in self.paths:
                fmt = self.formats[source]
                pages = len(PdfReader(str(source)).pages) if source.suffix.lower() == ".pdf" and fmt in {"png", "jpg", "webp"} else 1
                target = numbered_target(self.output_dir, source.stem, f".{fmt}", reserved, pages)
                jobs.append((source, target))
        except Exception as error:
            QMessageBox.warning(self, "Could not plan conversion", str(error))
            return
        engines = {source: self.engines.get(source, "auto") for source, target in jobs
                   if (target.suffix.lower() == ".pdf" and source.suffix.lower().lstrip(".") in LIBREOFFICE_FORMATS)
                   or (source.suffix.lower() == ".pdf" and target.suffix.lower() == ".docx")
                   or (source.suffix.lower().lstrip(".") in LIBREOFFICE_FORMATS and
                       target.suffix.lower().lstrip(".") in {"docx", "odt", "rtf", "xlsx", "ods", "pptx", "odp"})}
        self._start_worker(Worker(jobs, engines=engines))

    def _start_worker(self, worker: Worker):
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            QMessageBox.warning(self, "Save folder unavailable", str(error))
            return
        self.progress.setMaximum(len(worker.jobs))
        self.progress.setValue(0)
        self.last_error = ""
        for button in (self.convert_button, self.compress_button, self.reduce_button,
                       self.pdf_button, self.image_button, self.media_button, self.zip_button,
                       self.ocr_button, self.add_button):
            button.setEnabled(False)
        self.worker = worker
        worker.update.connect(self._job_update)
        worker.finished_batch.connect(self._done)
        worker.finished.connect(self._refresh_formats)
        worker.start()
        self._refresh_formats()

    def _document_pages(self):
        row=self.list.currentRow()
        path=self.paths[row] if 0<=row<len(self.paths) and self.paths[row].suffix.lower()=='.pdf' else None
        if path is None:
            name,_=QFileDialog.getOpenFileName(self,'Organize document pages','','PDF documents (*.pdf)')
            if not name:return
            path=Path(name)
        try:
            from pdf_pages import PdfPages
            dialog=PdfPages(path,self);dialog.exec()
        except Exception as error:QMessageBox.warning(self,'Document pages',str(error))

    def _pdf_tools(self):
        pdfs = [path for path in self.paths if path.suffix.lower() == ".pdf"]
        row = self.list.currentRow()
        selected = self.paths[row] if 0 <= row < len(self.paths) else None
        menu = QMenu(self)
        organize = menu.addAction("Organize pages visually…")
        merge = menu.addAction("Merge queued PDFs")
        split = menu.addAction("Split selected PDF into pages")
        reorder = menu.addAction("Reorder selected PDF pages")
        rotate = menu.addAction("Rotate selected PDF pages")
        chosen = menu.exec(self.pdf_button.mapToGlobal(self.pdf_button.rect().bottomLeft()))
        if not chosen:
            return
        if chosen == organize:
            self._document_pages()
            return
        if chosen == merge:
            if len(pdfs) < 2:
                QMessageBox.warning(self, "PDF tools", "Add at least two PDFs to merge.")
                return
            target = numbered_target(self.output_dir, "Merged", ".pdf", {str(path).casefold() for path in self.paths})
            self._start_worker(Worker([(pdfs[0], target)], operation=lambda _, output: pdf_merge(pdfs, output), rows=[self.paths.index(pdfs[0])]))
            return
        if selected not in pdfs:
            QMessageBox.warning(self, "PDF tools", "Select a PDF in the queue first.")
            return
        if chosen == split:
            target = numbered_target(self.output_dir, f"{selected.stem}-pages", "", {str(path).casefold() for path in self.paths})
            operation = pdf_split
        elif chosen == reorder:
            count = len(PdfReader(str(selected)).pages)
            value, ok = QInputDialog.getText(self, "Reorder PDF", "Page order, comma-separated:", text=",".join(str(i) for i in range(1, count + 1)))
            if not ok:
                return
            try:
                order = [int(part.strip()) for part in value.split(",")]
            except ValueError:
                QMessageBox.warning(self, "Invalid page order", "Enter page numbers separated by commas.")
                return
            if sorted(order) != list(range(1, count + 1)):
                QMessageBox.warning(self, "Invalid page order", f"Enter every page once, from 1 to {count}.")
                return
            target = numbered_target(self.output_dir, f"{selected.stem}-reordered", ".pdf", {str(path).casefold() for path in self.paths})
            operation = lambda source, output: pdf_reorder(source, output, order)
        else:
            value, ok = QInputDialog.getItem(self, "Rotate PDF", "Clockwise:", ["90°", "180°", "270°"], 0, False)
            if not ok:
                return
            degrees = int(value[:-1])
            target = numbered_target(self.output_dir, f"{selected.stem}-rotated", ".pdf", {str(path).casefold() for path in self.paths})
            operation = lambda source, output: pdf_rotate(source, output, degrees)
        self._start_worker(Worker([(selected, target)], operation=operation, rows=[row]))

    def _image_tools(self):
        row = self.list.currentRow()
        selected = self.paths[row] if 0 <= row < len(self.paths) else None
        if not selected or kind(selected) != "Image":
            QMessageBox.warning(self, "Image tools", "Select an image in the queue first.")
            return
        menu = QMenu(self)
        resize = menu.addAction("Resize (fit within width × height)")
        crop = menu.addAction("Crop")
        clockwise = menu.addAction("Rotate 90° clockwise")
        counterclockwise = menu.addAction("Rotate 90° counterclockwise")
        strip = menu.addAction("Remove metadata")
        chosen = menu.exec(self.image_button.mapToGlobal(self.image_button.rect().bottomLeft()))
        if not chosen:
            return
        if chosen in {resize, crop}:
            prompt = "Maximum width × height:" if chosen == resize else "Left, top, width, height:"
            value, ok = QInputDialog.getText(self, "Image tools", prompt)
            if not ok:
                return
            parts = re.split(r"[x×,\s]+", value.strip())
            try:
                values = tuple(int(part) for part in parts)
            except ValueError:
                values = ()
            if len(values) != (2 if chosen == resize else 4):
                QMessageBox.warning(self, "Invalid dimensions", "Enter positive whole-number dimensions.")
                return
            action = "resize" if chosen == resize else "crop"
        elif chosen == strip:
            action, values = "strip_metadata", ()
        else:
            action, values = "rotate", (90 if chosen == clockwise else 270,)
        ext = selected.suffix.lower() if selected.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".gif"} else ".png"
        target = numbered_target(self.output_dir, f"{selected.stem}-{action}", ext, {str(path).casefold() for path in self.paths})
        self._start_worker(Worker([(selected, target)], operation=lambda source, output: edit_image(source, output, action, values), rows=[row]))

    def _media_tools(self):
        row = self.list.currentRow()
        selected = self.paths[row] if 0 <= row < len(self.paths) else None
        if not selected or kind(selected) not in {"Video", "Audio"}:
            QMessageBox.warning(self, "Media trim", "Select an audio or video file first.")
            return
        value, ok = QInputDialog.getText(self, "Trim media", "Start and end in seconds (for example 12.5, 38):")
        if not ok:
            return
        try:
            start, end = (float(part.strip()) for part in value.split(","))
        except ValueError:
            QMessageBox.warning(self, "Invalid times", "Enter start and end seconds separated by a comma.")
            return
        menu = QMenu(self)
        precise = menu.addAction("Precise trim (re-encode)")
        fast = menu.addAction("Fast trim (keyframes)")
        chosen = menu.exec(self.media_button.mapToGlobal(self.media_button.rect().bottomLeft()))
        if chosen not in {precise, fast}:
            return
        target = numbered_target(self.output_dir, f"{selected.stem}-trimmed", selected.suffix,
                                 {str(path).casefold() for path in self.paths})
        self._start_worker(Worker([(selected, target)], operation=lambda source, output: trim_media(source, output, start, end, chosen == precise), rows=[row]))

    def _zip_tools(self):
        row = self.list.currentRow()
        selected = self.paths[row] if 0 <= row < len(self.paths) else None
        if not selected or selected.suffix.lower() != ".zip":
            QMessageBox.warning(self, "Open ZIP", "Select a ZIP archive in the queue first.")
            return
        try:
            entries = zip_entries(selected)
        except Exception as error:
            QMessageBox.warning(self, "Cannot open ZIP", str(error))
            return
        listing = "\n".join(f"{name}  ({size:,} bytes)" for name, size, _ in entries[:30])
        if len(entries) > 30:
            listing += f"\n… and {len(entries) - 30} more"
        answer = QMessageBox.question(self, "ZIP preview", f"{len(entries)} entries, {sum(size for _, size, _ in entries):,} bytes unpacked.\n\n{listing}\n\nExtract to the save folder?")
        if answer != QMessageBox.Yes:
            return
        target = numbered_target(self.output_dir, f"{selected.stem}-extracted", "",
                                 {str(path).casefold() for path in self.paths})
        self._start_worker(Worker([(selected, target)], operation=extract_zip, rows=[row]))

    def _ocr_tools(self):
        row = self.list.currentRow()
        selected = self.paths[row] if 0 <= row < len(self.paths) else None
        if not selected or kind(selected) not in {"Image", "PDF"}:
            QMessageBox.warning(self, "OCR", "Select an image or PDF first.")
            return
        labels = {"Multilingual (Latin, Chinese, Japanese)": "multilingual",
                  "Cyrillic": "cyrillic", "Hindi / Devanagari": "hindi",
                  "Korean": "korean", "Arabic": "arabic"}
        choice, accepted = QInputDialog.getItem(self, "OCR language", "Choose the text's script:",
                                                 list(labels), 0, False)
        if not accepted:
            return
        target = numbered_target(self.output_dir, f"{selected.stem}-ocr", ".txt",
                                 {str(path).casefold() for path in self.paths})
        self._start_worker(Worker([(selected, target)],
                                  operation=lambda source, output: ocr_to_text(source, output, labels[choice]),
                                  rows=[row]))

    def _compress(self):
        if not self.paths:
            return
        suggested = str(self.output_dir / "Converted files.zip")
        filename, _ = QFileDialog.getSaveFileName(self, "Save ZIP archive", suggested, "ZIP archives (*.zip)")
        if not filename:
            return
        target = Path(filename)
        if target.suffix.lower() != ".zip":
            target = target.with_suffix(".zip")
        if target.exists():
            QMessageBox.warning(self, "Output exists", f"The archive already exists:\n{target}")
            return
        self._start_worker(Worker([(path, target) for path in self.paths], archive=target))

    def _reduce(self):
        target_mb = self.target_size.value()
        jobs = []
        reserved = {str(path).casefold() for path in self.paths}
        for source in self.paths:
            extension = reduced_extension(source)
            if not extension:
                QMessageBox.warning(self, "Unsupported file", f"Target-size compression is not available for {source.name}.")
                return
            target = numbered_target(self.output_dir, f"{source.stem}-smaller", f".{extension}", reserved)
            jobs.append((source, target))
        self._start_worker(Worker(jobs, target_mb=target_mb))

    def _job_update(self, index: int, stage: str, detail: str):
        item = self.list.item(index)
        if item:
            output = self.formats[self.paths[index]].upper() or "EXTRACT"
            item.setText(f"{self.paths[index].name}\n{kind(self.paths[index]).upper()} → {output}  ·  {stage}")
            item.setToolTip(detail)
        self.status.setText(f"{stage}: {detail}")
        if stage == "Failed":
            self.last_error = detail
        if stage in {"Done", "Failed", "Compressed"}:
            self.progress.setValue(self.progress.value() + 1)

    def _done(self, done: int, failed: int):
        self.add_button.setEnabled(True)
        self._refresh_formats()
        location = self.worker.archive if self.worker and self.worker.archive else self.output_dir
        summary = f"Finished: {done} processed, {failed} failed."
        if done:
            summary += f" Saved in {location}."
        self.status.setText(f"{summary}. {self.last_error}" if self.last_error else summary)

    def closeEvent(self, event):
        if ((self.worker and self.worker.isRunning()) or self.preview_worker is not None
                or self.watchit_loader is not None):
            self.status.setText("Please wait for the current operation to finish before closing.")
            event.ignore()
            return
        for window in (self.screenwriter, self.watchit, *self.workspaces.values()):
            if window is not None and not window.close():
                event.ignore()
                return
        event.accept()


def main():
    if sys.argv[1:2] == ['--dashboard-self-check']:
        try:
            from verify_dashboard import run
            run(sys.argv[2] if len(sys.argv) > 2 else None)
        except Exception:
            import tempfile
            import traceback
            report = Path(tempfile.gettempdir()) / 'DrunkPeanuts-dashboard-check-error.txt'
            report.write_text(traceback.format_exc(), encoding='utf-8')
            raise SystemExit(1)
        return
    if sys.argv[1:] == ["--register-windows"]:
        from windows_integration import register
        register()
        return
    if sys.argv[1:] == ["--unregister-windows"]:
        from windows_integration import unregister
        unregister()
        return
    if len(sys.argv) == 5 and sys.argv[1] == "--convert-with":
        convert(Path(sys.argv[3]), Path(sys.argv[4]), sys.argv[2])
        return
    if len(sys.argv) == 4 and sys.argv[1] == "--convert":
        convert(Path(sys.argv[2]), Path(sys.argv[3]))
        return
    if len(sys.argv) == 4 and sys.argv[1] == "--ocr":
        ocr_to_text(Path(sys.argv[2]), Path(sys.argv[3]))
        return
    if len(sys.argv) == 5 and sys.argv[1] == "--ocr-with":
        ocr_to_text(Path(sys.argv[3]), Path(sys.argv[4]), sys.argv[2])
        return
    if sys.argv[1:] == ["--office-self-check"]:
        from office_suite import WORKSPACES
        from formulaic import mathml
        if set(WORKSPACES) != {"Pages", "Tables", "Dazzle", "Sketch", "Organize", "Formulaic"}:
            raise RuntimeError("Office workspaces are missing")
        if b"mfrac" not in mathml("{a} over {b}"):
            raise RuntimeError("Formulaic is unavailable")
        return
    if sys.argv[1:] == ["--renderer-self-check"]:
        from office_pdf import available_engines
        if sys.platform == "win32":
            import pythoncom
            import win32com.client
        print(", ".join(available_engines(Path("sample.docx"))))
        return
    if sys.argv[1:] == ['--playlist-self-check']:
        import os
        import tempfile
        import time
        from play_queue import media_paths, save_playlist
        from watchit import WatchIT
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        application = QApplication([])
        player_window = WatchIT()
        player_window.timer.stop()
        player_window.resize(780, 540)
        player_window.volume.setValue(200)
        assert player_window.volume.maximum() == 200 and player_window.volume_label.text() == '200%'
        native_window, surface = int(player_window.winId()), int(player_window.surface.winId())
        flags = player_window.windowHandle().flags()
        player_window.picture_in_picture()
        assert player_window.windowHandle().flags() & Qt.WindowStaysOnTopHint
        assert int(player_window.winId()) == native_window and int(player_window.surface.winId()) == surface
        player_window.escape_view()
        assert player_window.windowHandle().flags() == flags and player_window._pip_state is None
        with tempfile.TemporaryDirectory() as folder:
            files = [(Path(folder)/name).resolve() for name in ('First track.mp4', 'Second track.wav')]
            for file in files:file.touch()
            target = Path(folder)/'Queue.m3u8'
            save_playlist(target, files)
            assert media_paths([target]) == files
            player_window.add_media([folder], autoplay=False)
            deadline = time.monotonic() + 10
            while player_window.scanner is not None and time.monotonic() < deadline:
                application.processEvents()
                time.sleep(.01)
            assert player_window.scanner is None and player_window.files == files
            assert player_window.index == -1
            player_window.playlist.item(0).setSelected(True)
            player_window.move_selected(1)
            assert player_window.files == list(reversed(files))
            player_window.clear_playlist()
            assert not player_window.files
            player_window.close()
        return
    if sys.argv[1:2] == ["--watchit-self-check"] and len(sys.argv) in {2, 3}:
        import json
        import time
        from watchit import create_playback_engine, WatchIT
        shell_seconds = None
        if len(sys.argv) == 3:
            application = QApplication([])
            started = time.perf_counter()
            player_window = WatchIT(deferred=True)
            player_window.show()
            application.processEvents()
            shell_seconds = time.perf_counter() - started
        started = time.perf_counter()
        vlc, engine, player = create_playback_engine()
        engine_seconds = time.perf_counter() - started
        if len(sys.argv) == 3:
            player_window.set_engine((vlc, engine, player))
            report = {"version": VERSION, "shell_seconds": shell_seconds, "engine_seconds": engine_seconds,
                      "engine_version": vlc.libvlc_get_version().decode(), "controls_enabled": player_window.transport.isEnabled()}
            Path(sys.argv[2]).write_text(json.dumps(report, indent=2), encoding="utf-8")
            player_window.close()
        print(vlc.libvlc_get_version().decode())
        player.release()
        engine.release()
        return
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName("Drunk Peanuts")
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("Local File Converter")
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parent / "assets" / "app.ico")))
    if sys.argv[1:2] in (['--play'], ['--enqueue']):
        from play_queue import forward_play
        if forward_play(sys.argv[2:], enqueue=sys.argv[1] == '--enqueue'):
            return
    window = Window()
    if not sys.argv[1:]:
        try:
            from desktop_dashboard import install
            install(window)
        except (ImportError, FileNotFoundError) as error:
            window.status.setText(f"Home unavailable: {error}. Native tools are ready.")
    if not sys.argv[1:]:window.show()
    QTimer.singleShot(0, lambda: window.open_arguments(sys.argv[1:]))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
