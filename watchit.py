"""WatchIT: local media playback powered by the bundled libVLC runtime."""

from __future__ import annotations

import os
import sys
import ctypes
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout,
    QLabel, QListWidget, QMainWindow, QMessageBox, QPushButton, QSlider,
    QVBoxLayout, QWidget)

_dll_directory = None


def vlc_runtime():
    """Select the shipped VLC modules first; source runs may use installed VLC."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "vlc_runtime"
    library = root / ("libvlc.dll" if sys.platform == "win32" else "lib/libvlc.dylib")
    plugins = root / "plugins"
    if library.is_file() and plugins.is_dir():
        if sys.platform == "win32":
            global _dll_directory
            _dll_directory = os.add_dll_directory(str(root))
        elif sys.platform == "darwin":
            ctypes.CDLL(str(root / "lib/libvlccore.dylib"), mode=ctypes.RTLD_GLOBAL)
        os.environ["PYTHON_VLC_LIB_PATH"] = str(library)
        os.environ["PYTHON_VLC_MODULE_PATH"] = str(plugins)
        os.environ["VLC_PLUGIN_PATH"] = str(plugins)
    elif getattr(sys, "frozen", False):
        raise RuntimeError("The bundled VLC playback engine is missing.")
    elif sys.platform == "win32" and not (Path(os.environ.get("ProgramFiles", "")) / "VideoLAN/VLC/libvlc.dll").is_file():
        raise RuntimeError("Install VLC to run WatchIT from source; downloads include the playback engine.")
    elif sys.platform == "darwin" and not Path("/Applications/VLC.app/Contents/MacOS/lib/libvlc.dylib").is_file():
        raise RuntimeError("Install VLC to run WatchIT from source; downloads include the playback engine.")
    import vlc
    return vlc


def clock(milliseconds):
    seconds = max(0, milliseconds // 1000)
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"


class VideoSurface(QWidget):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_NativeWindow)
        self.setStyleSheet("background: #050b11;")
        self.setMinimumHeight(260)


class WatchIT(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WatchIT · FreeConvert")
        self.resize(1060, 740)
        self.vlc = vlc_runtime()
        self.instance = self.vlc.Instance("--no-video-title-show", "--quiet")
        if self.instance is None:
            raise RuntimeError("VLC could not start its playback engine.")
        self.player = self.instance.media_player_new()
        self.files: list[Path] = []
        self.index = -1
        self.seeking = False
        self._build()
        self._theme()
        QApplication.instance().styleHints().colorSchemeChanged.connect(self._theme)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(300)

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        page = QVBoxLayout(root)
        page.setContentsMargins(24, 20, 24, 20)
        page.setSpacing(12)
        heading = QLabel("WatchIT")
        heading.setObjectName("title")
        page.addWidget(heading)
        self.surface = VideoSurface()
        page.addWidget(self.surface, 1)
        self.seek = QSlider(Qt.Horizontal)
        self.seek.setRange(0, 1000)
        self.seek.sliderPressed.connect(lambda: setattr(self, "seeking", True))
        self.seek.sliderReleased.connect(self._seek)
        page.addWidget(self.seek)
        row = QHBoxLayout()
        self.time_label = QLabel("00:00:00 / 00:00:00")
        row.addWidget(self.time_label)
        row.addStretch()
        for label, callback in (("Open", self.open_files), ("Previous", self.previous),
                                ("Play/Pause", self.toggle), ("Stop", self.stop),
                                ("Next", self.next), ("Fullscreen", self.fullscreen)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        page.addLayout(row)
        options = QHBoxLayout()
        options.addWidget(QLabel("Speed"))
        self.speed = QComboBox()
        for rate in (0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 3, 4):
            self.speed.addItem(f"{rate:g}×", rate)
        self.speed.setCurrentIndex(3)
        self.speed.currentIndexChanged.connect(lambda: self.player.set_rate(self.speed.currentData()))
        options.addWidget(self.speed)
        options.addWidget(QLabel("Aspect"))
        self.aspect = QComboBox()
        for label, ratio in (("Auto", None), ("16:9", "16:9"), ("4:3", "4:3"),
                             ("21:9", "21:9"), ("1:1", "1:1"), ("9:16", "9:16")):
            self.aspect.addItem(label, ratio)
        self.aspect.currentIndexChanged.connect(lambda: self.player.video_set_aspect_ratio(self.aspect.currentData()))
        options.addWidget(self.aspect)
        options.addWidget(QLabel("Subtitles"))
        self.subtitles = QComboBox()
        self.subtitles.currentIndexChanged.connect(self._subtitle)
        options.addWidget(self.subtitles)
        external = QPushButton("Load subtitles")
        external.clicked.connect(self.load_subtitles)
        options.addWidget(external)
        options.addWidget(QLabel("Audio"))
        self.audio = QComboBox()
        self.audio.currentIndexChanged.connect(self._audio)
        options.addWidget(self.audio)
        page.addLayout(options)
        volume_row = QHBoxLayout()
        volume_row.addWidget(QLabel("Volume"))
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 150)
        self.volume.setValue(100)
        self.volume.setMaximumWidth(180)
        self.volume.valueChanged.connect(self.player.audio_set_volume)
        volume_row.addWidget(self.volume)
        self.mute = QPushButton("Mute")
        self.mute.clicked.connect(lambda: self.player.audio_toggle_mute())
        volume_row.addWidget(self.mute)
        self.loop = QPushButton("Loop: Off")
        self.loop.setCheckable(True)
        self.loop.toggled.connect(lambda on: self.loop.setText("Loop: On" if on else "Loop: Off"))
        volume_row.addWidget(self.loop)
        volume_row.addStretch()
        page.addLayout(volume_row)
        self.playlist = QListWidget()
        self.playlist.setMaximumHeight(110)
        self.playlist.itemDoubleClicked.connect(lambda item: self._play(self.playlist.row(item)))
        page.addWidget(self.playlist)
        self.statusBar().showMessage("Open media files to play locally")
        for keys, callback in (("Space", self.toggle), ("Ctrl+O", self.open_files),
                               ("F", self.fullscreen), ("Right", lambda: self._skip(10000)),
                               ("Left", lambda: self._skip(-10000))):
            action = QAction(self)
            action.setShortcut(QKeySequence(keys))
            action.triggered.connect(callback)
            self.addAction(action)

    def _theme(self, *_):
        dark = QApplication.instance().styleHints().colorScheme() == Qt.ColorScheme.Dark
        bg, card, ink, muted, border = (("#0b1520", "#17232e", "#edf5f6", "#a6bac3", "#304551") if dark else
                                        ("#f6f9fb", "#ffffff", "#14283d", "#58717e", "#d8e4e9"))
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background: {bg}; color: {ink}; font-family: 'Segoe UI', 'SF Pro Text'; font-size: 14px; }}
            QLabel#title {{ font-size: 28px; font-weight: 750; }}
            QPushButton, QComboBox {{ background: {card}; color: {ink}; border: 1px solid {border}; border-radius: 8px; padding: 7px 10px; min-height: 25px; }}
            QPushButton:hover, QComboBox:hover {{ border-color: #087e75; }}
            QPushButton:focus, QComboBox:focus, QListWidget:focus {{ border: 2px solid #087e75; }}
            QComboBox QAbstractItemView, QListWidget {{ background: {card}; color: {ink}; border: 1px solid {border}; border-radius: 8px; }}
            QListWidget::item:selected {{ background: {'#20524f' if dark else '#d9f2ec'}; }}
            QSlider::groove:horizontal {{ height: 6px; background: {border}; border-radius: 3px; }}
            QSlider::handle:horizontal {{ width: 16px; margin: -5px 0; border-radius: 8px; background: #087e75; }}
            QStatusBar {{ color: {muted}; }}
        """)

    def open_files(self):
        names, _ = QFileDialog.getOpenFileNames(self, "Open media", "", "Media files (*);;All files (*)")
        if names:
            start = len(self.files)
            self.files.extend(Path(name) for name in names)
            self.playlist.addItems([Path(name).name for name in names])
            self._play(start)

    def _play(self, index):
        if not 0 <= index < len(self.files):
            return
        self.index = index
        path = self.files[index]
        self.player.stop()
        self.player.set_media(self.instance.media_new_path(str(path)))
        handle = int(self.surface.winId())
        if sys.platform == "win32":
            self.player.set_hwnd(handle)
        elif sys.platform == "darwin":
            self.player.set_nsobject(handle)
        self.player.play()
        self.player.set_rate(self.speed.currentData())
        self.player.audio_set_volume(self.volume.value())
        self.playlist.setCurrentRow(index)
        self.statusBar().showMessage(path.name)
        QTimer.singleShot(700, self._tracks)

    def toggle(self):
        if self.player.is_playing():
            self.player.pause()
        elif self.index >= 0:
            self.player.play()

    def stop(self):
        self.player.stop()

    def previous(self):
        if self.files:
            self._play((self.index - 1) % len(self.files))

    def next(self):
        if self.files:
            self._play((self.index + 1) % len(self.files))

    def fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def _skip(self, delta):
        if self.index >= 0 and self.player.is_seekable():
            self.player.set_time(max(0, self.player.get_time() + delta))

    def _seek(self):
        if self.player.is_seekable():
            self.player.set_position(self.seek.value() / 1000)
        self.seeking = False

    def _tracks(self):
        self.subtitles.blockSignals(True)
        self.subtitles.clear()
        self.subtitles.addItem("Off", -1)
        tracks = self.player.video_get_spu_description() or []
        for track_id, name in tracks:
            if track_id != -1:
                self.subtitles.addItem(name.decode(errors="replace") if isinstance(name, bytes) else str(name), track_id)
        self.subtitles.setCurrentIndex(max(0, self.subtitles.findData(self.player.video_get_spu())))
        self.subtitles.blockSignals(False)
        self.audio.blockSignals(True)
        self.audio.clear()
        for track_id, name in self.player.audio_get_track_description() or []:
            self.audio.addItem(name.decode(errors="replace") if isinstance(name, bytes) else str(name), track_id)
        self.audio.setCurrentIndex(max(0, self.audio.findData(self.player.audio_get_track())))
        self.audio.blockSignals(False)

    def _subtitle(self):
        if self.subtitles.currentData() is not None:
            self.player.video_set_spu(self.subtitles.currentData())

    def _audio(self):
        if self.audio.currentData() is not None:
            self.player.audio_set_track(self.audio.currentData())

    def load_subtitles(self):
        name, _ = QFileDialog.getOpenFileName(self, "Load subtitles", "", "Subtitle files (*.srt *.ass *.ssa *.sub *.vtt *.txt);;All files (*)")
        if name and self.index >= 0:
            if not self.player.video_set_subtitle_file(name):
                QMessageBox.warning(self, "WatchIT", "VLC could not load this subtitle file.")
            QTimer.singleShot(300, self._tracks)

    def _refresh(self):
        if self.index < 0:
            return
        duration = self.player.get_length()
        elapsed = self.player.get_time()
        self.time_label.setText(f"{clock(elapsed)} / {clock(duration)}")
        if duration > 0 and not self.seeking:
            self.seek.setValue(max(0, min(1000, int(elapsed * 1000 / duration))))
        if self.player.get_state() == self.vlc.State.Ended:
            if self.loop.isChecked():
                self._play(self.index)
            elif self.index + 1 < len(self.files):
                self._play(self.index + 1)

    def closeEvent(self, event):
        self.player.stop()
        super().closeEvent(event)
