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
from PySide6.QtCore import QPoint, QSettings, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QComboBox, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QDoubleSpinBox, QInputDialog, QMenu, QMessageBox, QProgressBar, QPushButton, QSizePolicy,
    QSplitter, QVBoxLayout, QWidget,
)

from converter import (available_formats, compress, convert, edit_image, extract_zip, kind, ocr_to_text,
                       pdf_merge, pdf_reorder, pdf_rotate, pdf_split, reduce_size, reduced_extension,
                       trim_media, zip_entries)

VERSION = "0.11.0"


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
    preferred = {"Image": "webp", "PDF": "png", "Video": "mp4", "Audio": "mp3",
                 "Document": "pdf", "Spreadsheet": "xlsx", "Text": "pdf"}.get(kind(path))
    return preferred if preferred in choices else choices[0]


def image_preview(path: Path) -> QPixmap | None:
    try:
        if path.suffix.lower() == ".pdf":
            pdf = pdfium.PdfDocument(str(path))
            try:
                if not len(pdf):
                    return None
                page = pdf[0]
                picture = page.render(scale=1.4).to_pil()
                page.close()
            finally:
                pdf.close()
        elif kind(path) == "Image" and path.suffix.lower() not in {".svg", ".cr2", ".nef", ".arw"}:
            with Image.open(path) as source:
                picture = source.copy()
        else:
            return None
        picture.thumbnail((540, 420))
        picture = picture.convert("RGBA")
        data = picture.tobytes("raw", "RGBA")
        return QPixmap.fromImage(QImage(data, picture.width, picture.height, QImage.Format_RGBA8888).copy())
    except Exception:
        return None


class DropArea(QFrame):
    files_dropped = Signal(list)
    quick_files_dropped = Signal(list, QPoint)

    def __init__(self):
        super().__init__()
        self.setObjectName("dropArea")
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(7)
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
        layout.addWidget(title)
        layout.addWidget(detail)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
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
                 operation: Callable[[Path, Path], None] | None = None, rows: list[int] | None = None):
        super().__init__()
        self.jobs = jobs
        self.archive = archive
        self.target_mb = target_mb
        self.operation = operation
        self.rows = rows or list(range(len(jobs)))

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
        self.setWindowTitle(f"FreeConvert {VERSION}")
        self.resize(1080, 830)
        self.setMinimumSize(780, 700)
        self.paths: list[Path] = []
        self.formats: dict[Path, str] = {}
        self.worker: Worker | None = None
        self.screenwriter = None
        self.workspaces = {}
        self.last_error = ""
        self.settings = QSettings("Local File Converter", "Local File Converter")
        self.output_dir = Path(self.settings.value("output_dir", str(Path.home() / "Downloads")))
        self._build()
        self._theme()
        QApplication.instance().styleHints().colorSchemeChanged.connect(self._theme)

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        page = QVBoxLayout(root)
        page.setContentsMargins(34, 22, 34, 22)
        page.setSpacing(14)

        header = QHBoxLayout()
        brand = QVBoxLayout()
        eyebrow = QLabel("LOCAL  /  PRIVATE  /  FREE")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("FreeConvert")
        title.setObjectName("title")
        brand.addWidget(eyebrow)
        brand.addWidget(title)
        header.addLayout(brand)
        header.addStretch()
        self.add_button = QPushButton("Add files")
        self.add_button.setObjectName("primaryButton")
        self.add_button.clicked.connect(self._choose_files)
        header.addWidget(self.add_button)
        page.addLayout(header)

        subtitle = QLabel("Convert files and create documents, tables, slides, formulas, drawings, databases, and scripts on your computer.")
        subtitle.setObjectName("muted")
        page.addWidget(subtitle)

        spaces = QFrame()
        spaces.setObjectName("workspaces")
        spaces_layout = QHBoxLayout(spaces)
        spaces_layout.setContentsMargins(8, 8, 8, 8)
        spaces_layout.setSpacing(5)
        for name in ("Pages", "Tables", "Dazzle", "Sketch", "Organize", "Formulaic"):
            control = QPushButton(name)
            control.setObjectName("workspaceButton")
            control.clicked.connect(lambda checked=False, workspace=name: self._open_workspace(workspace))
            spaces_layout.addWidget(control)
        drafts = QPushButton("Writer's Drafts")
        drafts.setObjectName("workspaceButton")
        drafts.clicked.connect(self._screenwriter)
        spaces_layout.addWidget(drafts)
        page.addWidget(spaces)

        self.drop = DropArea()
        self.drop.setFixedHeight(115)
        self.drop.files_dropped.connect(self._add_files)
        self.drop.quick_files_dropped.connect(self._quick_drop)
        self.drop.mousePressEvent = lambda event: self._choose_files()
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
        splitter.setMinimumHeight(260)
        page.addWidget(splitter, 1)

        controls = QFrame()
        controls.setObjectName("controls")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(20, 18, 20, 18)
        controls_layout.setSpacing(12)
        controls_top = QHBoxLayout()
        format_label = QLabel("Convert to")
        format_label.setObjectName("fieldLabel")
        controls_top.addWidget(format_label)
        self.format = QComboBox()
        self.format.setMinimumWidth(140)
        self.format.currentTextChanged.connect(self._set_format)
        controls_top.addWidget(self.format)
        controls_top.addSpacing(15)
        destination_label = QLabel("Save in")
        destination_label.setObjectName("fieldLabel")
        controls_top.addWidget(destination_label)
        self.destination = QPushButton(str(self.output_dir))
        self.destination.setObjectName("directoryButton")
        self.destination.clicked.connect(self._choose_directory)
        controls_top.addWidget(self.destination, 1)
        self.convert_button = QPushButton("Convert files")
        self.convert_button.setObjectName("primaryButton")
        self.convert_button.clicked.connect(self._convert)
        controls_top.addWidget(self.convert_button)
        self.compress_button = QPushButton("Compress to ZIP")
        self.compress_button.setObjectName("secondaryButton")
        self.compress_button.clicked.connect(self._compress)
        controls_top.addWidget(self.compress_button)
        controls_layout.addLayout(controls_top)
        reduce_row = QHBoxLayout()
        reduce_label = QLabel("Upload limit per file")
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
        controls_layout.addLayout(reduce_row)
        tools_row = QHBoxLayout()
        self.pdf_button = QPushButton("PDF tools")
        self.pdf_button.setObjectName("secondaryButton")
        self.pdf_button.clicked.connect(self._pdf_tools)
        tools_row.addWidget(self.pdf_button)
        self.image_button = QPushButton("Image tools")
        self.image_button.setObjectName("secondaryButton")
        self.image_button.clicked.connect(self._image_tools)
        tools_row.addWidget(self.image_button)
        self.media_button = QPushButton("Media trim")
        self.media_button.setObjectName("secondaryButton")
        self.media_button.clicked.connect(self._media_tools)
        tools_row.addWidget(self.media_button)
        self.zip_button = QPushButton("Open ZIP")
        self.zip_button.setObjectName("secondaryButton")
        self.zip_button.clicked.connect(self._zip_tools)
        tools_row.addWidget(self.zip_button)
        self.ocr_button = QPushButton("OCR to text")
        self.ocr_button.setObjectName("secondaryButton")
        self.ocr_button.clicked.connect(self._ocr_tools)
        tools_row.addWidget(self.ocr_button)
        tools_row.addStretch()
        controls_layout.addLayout(tools_row)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        controls_layout.addWidget(self.progress)
        self.status = QLabel("Ready. Your files stay on this device.")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        controls_layout.addWidget(self.status)
        page.addWidget(controls)

    def _theme(self, *_):
        dark = QApplication.instance().styleHints().colorScheme() == Qt.ColorScheme.Dark
        bg, card, text, muted, border, drop = (
            ("#0b1520", "#17232e", "#edf5f6", "#a6bac3", "#304551", "#11222b") if dark else
            ("#f6f9fb", "#ffffff", "#14283d", "#58717e", "#d8e4e9", "#eaf8f7")
        )
        self.setStyleSheet(f"""
            QWidget {{ background: {bg}; color: {text}; font-family: 'Segoe UI', 'SF Pro Text', sans-serif; font-size: 14px; }}
            QLabel#title {{ font-size: 32px; font-weight: 750; }}
            QLabel#eyebrow {{ color: #087e75; font-size: 10px; font-weight: 700; letter-spacing: 2px; }}
            QLabel#sectionTitle {{ font-size: 19px; font-weight: 700; }}
            QLabel#dropTitle {{ font-size: 17px; font-weight: 700; }}
            QLabel#dropMark {{ font-size: 34px; font-weight: 300; color: #087e75; }}
            QLabel#muted {{ color: {muted}; }}
            QLabel#fieldLabel {{ font-weight: 700; }}
            QFrame#dropArea {{ background: {drop}; border: 2px dashed #69aaa3; border-radius: 14px; }}
            QFrame#workspaces {{ background: {card}; border: 1px solid {border}; border-radius: 12px; }}
            QPushButton#workspaceButton {{ background: transparent; border: none; color: {text}; padding: 8px 6px; }}
            QPushButton#workspaceButton:hover {{ background: {'#20524f' if dark else '#d9f2ec'}; }}
            QFrame#dropArea QLabel {{ background: transparent; }}
            QFrame#previewPanel, QFrame#controls {{ background: {card}; border: 1px solid {border}; border-radius: 12px; }}
            QFrame#previewPanel QLabel, QFrame#controls QLabel {{ background: transparent; }}
            QLabel#previewImage {{ background: {drop}; border: 1px solid {border}; border-radius: 8px; color: {muted}; }}
            QListWidget#fileList {{ background: {card}; border: 1px solid {border}; border-radius: 12px; padding: 8px; outline: none; }}
            QListWidget::item {{ padding: 12px; margin: 3px; border-radius: 7px; }}
            QListWidget::item:selected {{ background: {'#20524f' if dark else '#d9f2ec'}; color: {text}; }}
            QPushButton {{ min-height: 36px; padding: 3px 15px; border-radius: 8px; font-weight: 650; }}
            QPushButton#primaryButton {{ background: #087e75; color: white; border: 1px solid #087e75; }}
            QPushButton#primaryButton:hover {{ background: #096b63; }}
            QPushButton#primaryButton:disabled {{ background: #719994; border-color: #719994; }}
            QPushButton#secondaryButton, QPushButton#directoryButton {{ background: {card}; border: 1px solid {border}; }}
            QPushButton#secondaryButton:hover, QPushButton#directoryButton:hover {{ border-color: #087e75; }}
            QPushButton#textButton {{ background: transparent; border: none; color: #087e75; }}
            QPushButton:focus, QComboBox:focus, QListWidget:focus {{ border: 2px solid #087e75; }}
            QComboBox {{ background: {card}; border: 1px solid {border}; border-radius: 8px; min-height: 36px; padding: 2px 12px; }}
            QDoubleSpinBox {{ background: {card}; border: 1px solid {border}; border-radius: 8px; min-height: 36px; padding: 2px 12px; min-width: 100px; }}
            QComboBox QAbstractItemView {{ background: {card}; color: {text}; selection-background-color: #087e75; }}
            QProgressBar {{ height: 7px; background: {drop}; border: none; border-radius: 3px; }}
            QProgressBar::chunk {{ background: #0d9488; border-radius: 3px; }}
        """)

    def _choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Choose files")
        self._add_files([Path(file) for file in files])

    def _screenwriter(self):
        from screenwriter import ScreenwriterWindow
        if self.screenwriter is None:
            self.screenwriter = ScreenwriterWindow()
        self.screenwriter.show()
        self.screenwriter.raise_()
        self.screenwriter.activateWindow()

    def _open_workspace(self, name: str):
        from office_suite import WORKSPACES
        if name not in self.workspaces:
            self.workspaces[name] = WORKSPACES[name]()
        window = self.workspaces[name]
        window.show()
        window.raise_()
        window.activateWindow()

    def _add_files(self, files: list[Path]):
        if self.worker and self.worker.isRunning():
            return
        rejected = 0
        for path in files:
            if not path.is_file() or not (available_formats(path) or path.suffix.lower() == ".zip"):
                rejected += 1
                continue
            path = path.resolve()
            if path in self.paths:
                continue
            self.paths.append(path)
            self.formats[path] = preferred_format(path) if path.suffix.lower() != ".zip" else ""
            label = f"{path.name}\n{kind(path).upper() if path.suffix.lower() != '.zip' else 'ZIP'} → {self.formats[path].upper() if self.formats[path] else 'EXTRACT'}  ·  {path.stat().st_size / 1024 / 1024:.1f} MB  ·  Waiting"
            self.list.addItem(QListWidgetItem(label))
        self.count.setText(f"{len(self.paths)} file{'s' if len(self.paths) != 1 else ''}")
        if self.paths and self.list.currentRow() < 0:
            self.list.setCurrentRow(0)
        if rejected:
            self.status.setText(f"Skipped {rejected} unsupported item{'s' if rejected != 1 else ''}.")
        self._refresh_formats()

    def _clear(self):
        if self.worker and self.worker.isRunning():
            return
        self.paths.clear()
        self.formats.clear()
        self.list.clear()
        self.format.clear()
        self.preview.setPixmap(QPixmap())
        self.preview.setText("Select a file to see its preview")
        self.details.setText("Input and output details appear here")
        self.count.setText("0 files")
        self.progress.setValue(0)
        self.status.setText("Ready. Your files stay on this device.")

    def _select(self, row: int):
        if row < 0 or row >= len(self.paths):
            return
        path = self.paths[row]
        picture = image_preview(path)
        if picture:
            self.preview.setPixmap(picture.scaled(500, 112, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.preview.setPixmap(QPixmap())
            self.preview.setText(f"{path.suffix.upper().lstrip('.')}  ·  {kind(path)}")
        self._refresh_formats()
        self._refresh_details()

    def _set_format(self, fmt: str):
        row = self.list.currentRow()
        if 0 <= row < len(self.paths) and fmt:
            self.formats[self.paths[row]] = fmt
            item = self.list.item(row)
            item.setText(f"{self.paths[row].name}\n{kind(self.paths[row]).upper()} → {fmt.upper()}  ·  Waiting")
        self._refresh_details()

    def _refresh_details(self):
        row = self.list.currentRow()
        if 0 <= row < len(self.paths):
            path = self.paths[row]
            target = self.formats.get(path, "—").upper()
            note = "\nSelectable text only; PDF layout and images are not preserved." if path.suffix.lower() == ".pdf" and target == "DOCX" else ""
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
        idle = not (self.worker and self.worker.isRunning())
        self.convert_button.setEnabled(bool(self.paths) and all(self.formats.values()) and idle)
        self.compress_button.setEnabled(bool(self.paths) and idle)
        self.reduce_button.setEnabled(bool(self.paths) and all(reduced_extension(path) for path in self.paths) and idle)
        self.pdf_button.setEnabled(any(path.suffix.lower() == ".pdf" for path in self.paths) and idle)
        self.image_button.setEnabled(any(kind(path) == "Image" for path in self.paths) and idle)
        self.media_button.setEnabled(any(kind(path) in {"Video", "Audio"} for path in self.paths) and idle)
        self.zip_button.setEnabled(any(path.suffix.lower() == ".zip" for path in self.paths) and idle)
        self.ocr_button.setEnabled(any(kind(path) in {"Image", "PDF"} for path in self.paths) and idle)
        self._refresh_details()

    def _choose_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Choose output folder", str(self.output_dir))
        if directory:
            self.output_dir = Path(directory)
            self.settings.setValue("output_dir", directory)
            self.destination.setText(directory)

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
        self._start_worker(Worker(jobs))

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
        worker.start()

    def _pdf_tools(self):
        pdfs = [path for path in self.paths if path.suffix.lower() == ".pdf"]
        row = self.list.currentRow()
        selected = self.paths[row] if 0 <= row < len(self.paths) else None
        menu = QMenu(self)
        merge = menu.addAction("Merge queued PDFs")
        split = menu.addAction("Split selected PDF into pages")
        reorder = menu.addAction("Reorder selected PDF pages")
        rotate = menu.addAction("Rotate selected PDF pages")
        chosen = menu.exec(self.pdf_button.mapToGlobal(self.pdf_button.rect().bottomLeft()))
        if not chosen:
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
        ext = selected.suffix.lower() if selected.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"} else ".png"
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
        target = numbered_target(self.output_dir, f"{selected.stem}-ocr", ".txt",
                                 {str(path).casefold() for path in self.paths})
        self._start_worker(Worker([(selected, target)], operation=ocr_to_text, rows=[row]))

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


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--convert":
        convert(Path(sys.argv[2]), Path(sys.argv[3]))
        return
    if len(sys.argv) == 4 and sys.argv[1] == "--ocr":
        ocr_to_text(Path(sys.argv[2]), Path(sys.argv[3]))
        return
    if sys.argv[1:] == ["--office-self-check"]:
        from office_suite import WORKSPACES
        from formulaic import mathml
        if set(WORKSPACES) != {"Pages", "Tables", "Dazzle", "Sketch", "Organize", "Formulaic"}:
            raise RuntimeError("Office workspaces are missing")
        if b"mfrac" not in mathml("{a} over {b}"):
            raise RuntimeError("Formulaic is unavailable")
        return
    app = QApplication(sys.argv)
    app.setApplicationName("FreeConvert")
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("Local File Converter")
    window = Window()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
