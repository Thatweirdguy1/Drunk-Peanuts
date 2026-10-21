"""Local File Converter desktop interface."""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image
from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QComboBox, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QDoubleSpinBox, QMessageBox, QProgressBar, QPushButton, QSizePolicy,
    QSplitter, QVBoxLayout, QWidget,
)

from converter import available_formats, compress, convert, kind, reduce_size, reduced_extension

VERSION = "0.2.0"


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
        detail = QLabel("or choose files from your computer")
        detail.setObjectName("muted")
        detail.setAlignment(Qt.AlignCenter)
        layout.addWidget(mark)
        layout.addWidget(title)
        layout.addWidget(detail)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.files_dropped.emit([Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()])
        event.acceptProposedAction()


class Worker(QThread):
    update = Signal(int, str, str)
    finished_batch = Signal(int, int)

    def __init__(self, jobs: list[tuple[Path, Path]], archive: Path | None = None, target_mb: float | None = None):
        super().__init__()
        self.jobs = jobs
        self.archive = archive
        self.target_mb = target_mb

    def run(self):
        done = failed = 0
        if self.archive:
            try:
                compress([source for source, _ in self.jobs], self.archive,
                         lambda index, name: self.update.emit(index, "Compressed", name))
                done = len(self.jobs)
            except Exception as error:
                failed = len(self.jobs)
                self.update.emit(0, "Failed", str(error))
            self.finished_batch.emit(done, failed)
            return
        def perform(index: int, source: Path, target: Path):
            self.update.emit(index, "Reducing size" if self.target_mb else "Converting", source.name)
            try:
                if self.target_mb:
                    reduce_size(source, target, self.target_mb)
                else:
                    convert(source, target)
                self.update.emit(index, "Done", target.name)
                return True
            except Exception as error:
                self.update.emit(index, "Failed", str(error))
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
        self.setWindowTitle(f"Local File Converter {VERSION}")
        self.resize(1080, 830)
        self.setMinimumSize(780, 700)
        self.paths: list[Path] = []
        self.worker: Worker | None = None
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
        title = QLabel("File Converter")
        title.setObjectName("title")
        brand.addWidget(eyebrow)
        brand.addWidget(title)
        header.addLayout(brand)
        header.addStretch()
        self.add_button = QPushButton("Add files")
        self.add_button.setObjectName("secondaryButton")
        self.add_button.clicked.connect(self._choose_files)
        header.addWidget(self.add_button)
        page.addLayout(header)

        subtitle = QLabel("Convert images, PDFs, media, and documents on your computer.")
        subtitle.setObjectName("muted")
        page.addWidget(subtitle)

        self.drop = DropArea()
        self.drop.setFixedHeight(115)
        self.drop.files_dropped.connect(self._add_files)
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
        self.format.currentTextChanged.connect(self._refresh_details)
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
            ("#101923", "#182633", "#f2f7f8", "#a8bbc6", "#304250", "#14252d") if dark else
            ("#f4faf9", "#ffffff", "#173b3e", "#526c72", "#cce0dd", "#e9f8f5")
        )
        self.setStyleSheet(f"""
            QWidget {{ background: {bg}; color: {text}; font-family: 'Segoe UI', 'SF Pro Text', sans-serif; font-size: 14px; }}
            QLabel#title {{ font-size: 34px; font-weight: 750; }}
            QLabel#eyebrow {{ color: #087e75; font-size: 10px; font-weight: 700; letter-spacing: 2px; }}
            QLabel#sectionTitle {{ font-size: 19px; font-weight: 700; }}
            QLabel#dropTitle {{ font-size: 17px; font-weight: 700; }}
            QLabel#dropMark {{ font-size: 34px; font-weight: 300; color: #087e75; }}
            QLabel#muted {{ color: {muted}; }}
            QLabel#fieldLabel {{ font-weight: 700; }}
            QFrame#dropArea {{ background: {drop}; border: 2px dashed #69aaa3; border-radius: 14px; }}
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

    def _add_files(self, files: list[Path]):
        if self.worker and self.worker.isRunning():
            return
        rejected = 0
        for path in files:
            if not path.is_file() or not available_formats(path):
                rejected += 1
                continue
            if path.resolve() in self.paths:
                continue
            self.paths.append(path.resolve())
            label = f"{path.name}\n{kind(path).upper()}  ·  {path.stat().st_size / 1024 / 1024:.1f} MB  ·  Waiting"
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
        self._refresh_details()

    def _refresh_details(self):
        row = self.list.currentRow()
        if 0 <= row < len(self.paths):
            path = self.paths[row]
            target = self.format.currentText().upper() or "—"
            note = "\nSelectable text only; PDF layout and images are not preserved." if path.suffix.lower() == ".pdf" and target == "DOCX" else ""
            self.details.setText(f"{path.name}\n{kind(path)} input  →  {target} output{note}")

    def _refresh_formats(self):
        previous = self.format.currentText()
        common = set(available_formats(self.paths[0])) if self.paths else set()
        for path in self.paths[1:]:
            common.intersection_update(available_formats(path))
        self.format.blockSignals(True)
        self.format.clear()
        self.format.addItems(sorted(common))
        if previous in common:
            self.format.setCurrentText(previous)
        elif common:
            preferred = {"Image": "webp", "PDF": "png", "Video": "mp4", "Audio": "mp3", "Document": "pdf", "Spreadsheet": "xlsx"}.get(kind(self.paths[0]), "pdf")
            if preferred in common:
                self.format.setCurrentText(preferred)
        self.format.blockSignals(False)
        self.convert_button.setEnabled(bool(common) and not (self.worker and self.worker.isRunning()))
        self.compress_button.setEnabled(bool(self.paths) and not (self.worker and self.worker.isRunning()))
        self.reduce_button.setEnabled(bool(self.paths) and all(reduced_extension(path) for path in self.paths) and not (self.worker and self.worker.isRunning()))
        if self.paths and not common:
            self.status.setText("These files have no shared output format. Convert them in separate batches.")
        self._refresh_details()

    def _choose_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Choose output folder", str(self.output_dir))
        if directory:
            self.output_dir = Path(directory)
            self.settings.setValue("output_dir", directory)
            self.destination.setText(directory)

    def _convert(self):
        fmt = self.format.currentText()
        if not fmt:
            return
        jobs = []
        for source in self.paths:
            target = self.output_dir / f"{source.stem}.{fmt}"
            if target.resolve() == source or target.exists():
                QMessageBox.warning(self, "Output exists", f"Choose another folder or move the existing output:\n{target}")
                return
            jobs.append((source, target))
        if len({target.name.casefold() for _, target in jobs}) != len(jobs):
            QMessageBox.warning(self, "Duplicate output names", "Two files would produce the same output name. Convert them in separate batches.")
            return
        self.progress.setMaximum(len(jobs))
        self.last_error = ""
        self.progress.setValue(0)
        self.convert_button.setEnabled(False)
        self.compress_button.setEnabled(False)
        self.reduce_button.setEnabled(False)
        self.add_button.setEnabled(False)
        self.worker = Worker(jobs)
        self.worker.update.connect(self._job_update)
        self.worker.finished_batch.connect(self._done)
        self.worker.start()

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
        self.progress.setMaximum(len(self.paths))
        self.last_error = ""
        self.progress.setValue(0)
        self.convert_button.setEnabled(False)
        self.compress_button.setEnabled(False)
        self.reduce_button.setEnabled(False)
        self.add_button.setEnabled(False)
        self.worker = Worker([(path, target) for path in self.paths], archive=target)
        self.worker.update.connect(self._job_update)
        self.worker.finished_batch.connect(self._done)
        self.worker.start()

    def _reduce(self):
        target_mb = self.target_size.value()
        jobs = []
        for source in self.paths:
            extension = reduced_extension(source)
            if not extension:
                QMessageBox.warning(self, "Unsupported file", f"Target-size compression is not available for {source.name}.")
                return
            target = self.output_dir / f"{source.stem}-smaller.{extension}"
            if target.exists() or target.resolve() == source:
                QMessageBox.warning(self, "Output exists", f"Choose another folder or move the existing output:\n{target}")
                return
            jobs.append((source, target))
        if len({target.name.casefold() for _, target in jobs}) != len(jobs):
            QMessageBox.warning(self, "Duplicate output names", "Two files would produce the same output name. Reduce them in separate batches.")
            return
        self.progress.setMaximum(len(jobs))
        self.last_error = ""
        self.progress.setValue(0)
        self.convert_button.setEnabled(False)
        self.compress_button.setEnabled(False)
        self.reduce_button.setEnabled(False)
        self.add_button.setEnabled(False)
        self.worker = Worker(jobs, target_mb=target_mb)
        self.worker.update.connect(self._job_update)
        self.worker.finished_batch.connect(self._done)
        self.worker.start()

    def _job_update(self, index: int, stage: str, detail: str):
        item = self.list.item(index)
        if item:
            item.setText(f"{self.paths[index].name}\n{kind(self.paths[index]).upper()}  ·  {stage}")
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
    app = QApplication(sys.argv)
    app.setApplicationName("Local File Converter")
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("Local File Converter")
    window = Window()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
