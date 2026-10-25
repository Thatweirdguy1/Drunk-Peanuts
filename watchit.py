"""Play: local media playback powered by the bundled libVLC runtime."""

from __future__ import annotations

import os
import sys
import ctypes
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QAction, QKeySequence, QCursor
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout,
    QLabel, QListWidget, QMainWindow, QMessageBox, QPushButton, QSlider, QSpinBox,
    QVBoxLayout, QWidget, QFormLayout, QScrollArea, QFrame, QDialog)
from ui import icon_button, icon, palette

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
        raise RuntimeError("Install VLC to run Play from source; downloads include the playback engine.")
    elif sys.platform == "darwin" and not Path("/Applications/VLC.app/Contents/MacOS/lib/libvlc.dylib").is_file():
        raise RuntimeError("Install VLC to run Play from source; downloads include the playback engine.")
    import vlc
    return vlc


def clock(milliseconds):
    seconds = max(0, milliseconds // 1000)
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"


def create_playback_engine():
    vlc = vlc_runtime()
    options = ["--no-video-title-show", "--quiet"]
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "vlc_runtime"
    if sys.platform == "win32" and getattr(sys, "frozen", False) and (root / "plugins/plugins.dat").is_file():
        options.append("--no-plugins-scan")
    instance = vlc.Instance(*options)
    if instance is None:
        raise RuntimeError("VLC could not start its playback engine.")
    return vlc, instance, instance.media_player_new()


class EngineLoader(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            self.ready.emit(create_playback_engine())
        except Exception as error:
            self.failed.emit(str(error))


class VideoSurface(QWidget):
    double_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_NativeWindow)
        self.setObjectName("videoSurface")
        self.setStyleSheet("background: #000000;")
        self.setMinimumHeight(260)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()


class WatchIT(QMainWindow):
    def __init__(self, engine=None, deferred=False):
        super().__init__()
        self.setWindowTitle("Play · FreeConvert")
        self.resize(1060, 740)
        self.setMinimumSize(760, 520)
        self.vlc = self.instance = self.player = None
        prepared = engine or (None if deferred else create_playback_engine())
        self.files: list[Path] = []
        self.index = -1
        self.seeking = False
        self._fullscreen_state = None
        self._last_state = None
        self._build()
        self._theme()
        QApplication.instance().styleHints().colorSchemeChanged.connect(self._theme)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(300)
        if prepared is not None:
            self.set_engine(prepared)
        else:
            self._enable_playback(False)
            self.statusBar().showMessage("Starting local playback engine…")

    def _enable_playback(self, enabled):
        for widget in (self.transport, self.options_toggle, self.volume_controls, self.seek, self.playlist):
            widget.setEnabled(enabled)

    def set_engine(self, engine):
        self.vlc, self.instance, self.player = engine
        self.player.video_set_mouse_input(False)
        self.player.video_set_key_input(False)
        self._enable_playback(True)
        self.statusBar().showMessage("Open media · Space: play/pause · F11: fullscreen")

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        page = QVBoxLayout(root)
        page.setContentsMargins(16, 10, 16, 10)
        page.setSpacing(8)
        heading = QLabel("Play")
        self.heading = heading
        heading.setObjectName("title")
        page.addWidget(heading)
        self.surface = VideoSurface()
        self.surface.double_clicked.connect(self.fullscreen)
        page.addWidget(self.surface, 1)
        self.seek = QSlider(Qt.Horizontal)
        self.seek.setRange(0, 1000)
        self.seek.sliderPressed.connect(lambda: setattr(self, "seeking", True))
        self.seek.sliderReleased.connect(self._seek)
        page.addWidget(self.seek)
        self.time_label = QLabel("00:00:00 / 00:00:00")
        page.addWidget(self.time_label)
        self.transport = QWidget()
        row = QHBoxLayout(self.transport)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addStretch()
        for label, callback in (("Open", self.open_files), ("Previous", self.previous),
                                ("Play/Pause", self.toggle), ("Stop", self.stop),
                                ("Next", self.next), ("Fullscreen", self.fullscreen)):
            button = QPushButton(label)
            name = {"Open": "open", "Previous": "previous", "Play/Pause": "play", "Stop": "stop", "Next": "next", "Fullscreen": "fullscreen"}[label]
            icon_button(button, label, name)
            button.clicked.connect(callback)
            row.addWidget(button)
            if label == "Fullscreen":
                self.fullscreen_button = button
            elif label == "Play/Pause":
                self.play_button = button
                button.setObjectName("playButton")
        row.addStretch()
        page.addWidget(self.transport)
        self.advanced = QWidget()
        advanced_layout = QVBoxLayout(self.advanced)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        self.options_toggle = QPushButton("Playback options")
        icon_button(self.options_toggle, "Playback options", "settings")
        self.options_toggle.setCheckable(True)
        row.insertWidget(row.count() - 1, self.options_toggle)
        self.options_scroll = QDialog(self)
        self.options_scroll.setWindowTitle("Playback options · Play")
        self.options_scroll.resize(560, 520)
        settings_layout = QVBoxLayout(self.options_scroll)
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setFrameShape(QFrame.NoFrame)
        settings_scroll.setWidget(self.advanced)
        settings_layout.addWidget(settings_scroll)
        self.options_toggle.toggled.connect(self.options_scroll.setVisible)
        self.options_scroll.finished.connect(lambda: self.options_toggle.setChecked(False))
        self.options_scroll.hide()
        self.advanced.show()
        options = QFormLayout()
        self.speed = QComboBox()
        for rate in (0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 3, 4):
            self.speed.addItem(f"{rate:g}×", rate)
        self.speed.setCurrentIndex(3)
        self.speed.currentIndexChanged.connect(lambda: self.player.set_rate(self.speed.currentData()))
        options.addRow("Speed", self.speed)
        self.aspect = QComboBox()
        for label, ratio in (("Auto", None), ("16:9", "16:9"), ("4:3", "4:3"),
                             ("21:9", "21:9"), ("1:1", "1:1"), ("9:16", "9:16")):
            self.aspect.addItem(label, ratio)
        self.aspect.currentIndexChanged.connect(lambda: self.player.video_set_aspect_ratio(self.aspect.currentData()))
        options.addRow("Aspect", self.aspect)
        self.subtitles = QComboBox()
        self.subtitles.currentIndexChanged.connect(self._subtitle)
        subtitle_row = QHBoxLayout()
        subtitle_row.addWidget(self.subtitles, 1)
        external = QPushButton("Load subtitles")
        external.clicked.connect(self.load_subtitles)
        subtitle_row.addWidget(external)
        options.addRow("Subtitles", subtitle_row)
        self.audio = QComboBox()
        self.audio.currentIndexChanged.connect(self._audio)
        options.addRow("Audio", self.audio)
        advanced_layout.addLayout(options)
        sync = QFormLayout()
        for label, method in (("Audio sync (ms)", "audio_set_delay"),
                              ("Subtitle sync (ms)", "video_set_spu_delay")):
            control = QSpinBox()
            control.setRange(-5000, 5000)
            control.setSingleStep(100)
            control.valueChanged.connect(lambda value, setter=method: getattr(self.player, setter)(value * 1000))
            sync.addRow(label, control)
            if label.startswith("Audio"):
                self.audio_sync = control
            else:
                self.subtitle_sync = control
        self.devices = QComboBox()
        self.devices.addItem("System default", None)
        self.devices.currentIndexChanged.connect(self._device)
        device_row = QHBoxLayout()
        device_row.addWidget(self.devices, 1)
        refresh_devices = QPushButton("Refresh devices")
        refresh_devices.clicked.connect(self._devices)
        device_row.addWidget(refresh_devices)
        sync.addRow("Output device", device_row)
        advanced_layout.addLayout(sync)
        self.volume_controls = QWidget()
        volume_row = QHBoxLayout(self.volume_controls)
        volume_row.setContentsMargins(0, 0, 0, 0)
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 150)
        self.volume.setValue(100)
        self.volume.setMaximumWidth(180)
        self.volume.valueChanged.connect(lambda value: self.player.audio_set_volume(value) if self.player is not None else None)
        volume_row.addWidget(self.volume)
        self.mute = QPushButton("Mute")
        icon_button(self.mute, "Mute (M)", "volume")
        self.mute.setCheckable(True)
        self.mute.toggled.connect(self._mute)
        volume_row.addWidget(self.mute)
        self.loop = QPushButton("Loop: Off")
        icon_button(self.loop, "Loop: off", "loop")
        self.loop.setCheckable(True)
        self.loop.toggled.connect(lambda on: self.loop.setToolTip("Loop: on" if on else "Loop: off"))
        volume_row.addWidget(self.loop)
        volume_row.addStretch()
        row.insertWidget(row.count() - 1, self.volume_controls)
        self.playlist = QListWidget()
        self.playlist.setMaximumHeight(110)
        self.playlist.itemDoubleClicked.connect(lambda item: self._play(self.playlist.row(item)))
        page.addWidget(self.playlist)
        self.playlist_toggle = QPushButton()
        icon_button(self.playlist_toggle, "Show / hide playlist", "playlist")
        self.playlist_toggle.setCheckable(True)
        self.playlist_toggle.toggled.connect(self.playlist.setVisible)
        row.insertWidget(row.count() - 1, self.playlist_toggle)
        self.playlist.hide()
        self.statusBar().showMessage("Open media files to play locally")
        for keys, callback in (("Space", self.toggle), ("Ctrl+O", self.open_files),
                               ("F", self.fullscreen), ("F11", self.fullscreen),
                               ("Escape", self.exit_fullscreen), ("M", self.mute.click),
                               ("Right", lambda: self._skip(10000)),
                               ("Left", lambda: self._skip(-10000))):
            action = QAction(self)
            action.setShortcut(QKeySequence(keys))
            action.triggered.connect(callback)
            self.addAction(action)

    def _mute(self, muted):
        if self.player is not None:
            self.player.audio_set_mute(muted)
        icon_button(self.mute, "Unmute (M)" if muted else "Mute (M)", "mute" if muted else "volume")

    def _theme(self, *_):
        p = palette()
        bg, card, ink, muted, border = (p[key] for key in ('bg', 'card', 'ink', 'muted', 'border'))
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background: {bg}; color: {ink}; font-family: 'Segoe UI', 'SF Pro Text'; font-size: 13px; }}
            QLabel#title {{ font-size: 17px; font-weight: 650; }}
            QPushButton, QComboBox {{ background: {card}; color: {ink}; border: 1px solid {border}; border-radius: 3px; padding: 4px 6px; min-height: 22px; }}
            QPushButton:hover, QComboBox:hover {{ background: {p['hover']}; border-color: #ffdd22; }}
            QPushButton:focus, QComboBox:focus, QListWidget:focus {{ border: 2px solid #ffdd22; }}
            QPushButton:disabled {{ color: #69695f; border-color: transparent; }}
            QComboBox QAbstractItemView, QListWidget {{ background: {card}; color: {ink}; border: 1px solid {border}; border-radius: 3px; }}
            QListWidget::item {{ color: {ink}; }}
            QListWidget::item:selected {{ background: {p['hover']}; color: {ink}; }}
            QSpinBox {{ background: {card}; color: {ink}; border: 1px solid {border}; border-radius: 3px; padding: 3px; }}
            QSlider::groove:horizontal {{ height: 6px; background: {border}; border-radius: 3px; }}
            QSlider::handle:horizontal {{ width: 16px; margin: -5px 0; border-radius: 8px; background: #ffdd22; }}
            QStatusBar {{ color: {muted}; }}
            QWidget#videoSurface {{ background: #000000; }}
            QPushButton[iconName] {{ min-height: 0; padding: 4px; background: transparent; border-color: transparent; border-radius: 3px; }}
            QPushButton[iconName]:hover, QPushButton[iconName]:checked {{ background: {p['hover']}; border-color: #ffdd22; }}
            QPushButton[iconName]:pressed {{ background: #75671d; }}
            QPushButton#playButton {{ background: #ffdd22; border-radius: 16px; }}
            QPushButton#playButton:hover {{ background: #fff176; }}
        """)
        for button in self.findChildren(QPushButton):
            name = button.property("iconName")
            if name:
                button.setIcon(icon(name, "#0b0b0b" if button.objectName() == "playButton" else p['accent']))

    def open_files(self):
        if self.player is None:
            return
        names, _ = QFileDialog.getOpenFileNames(self, "Open media", "", "Media files (*.mp4 *.mkv *.mov *.avi *.webm *.mp3 *.wav *.flac *.ogg *.m4a *.aac *.mpeg *.mpg *.aiff *.wma *.wmv *.m4v);;All files (*)")
        if names:
            self.add_media(names)

    def add_media(self, names):
        if self.player is None:
            return
        files = [Path(name) for name in names if Path(name).is_file()]
        if not files:
            return
        start = len(self.files)
        self.files.extend(files)
        self.playlist.addItems([path.name for path in files])
        self.playlist_toggle.setChecked(True)
        self._play(start)

    def _play(self, index):
        if self.player is None or not 0 <= index < len(self.files):
            return
        self.index = index
        path = self.files[index]
        if not path.is_file():
            self.statusBar().showMessage(f"File is no longer available: {path.name}")
            return
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
        self.player.audio_set_mute(self.mute.isChecked())
        self.player.video_set_aspect_ratio(self.aspect.currentData())
        self.player.audio_set_delay(self.audio_sync.value() * 1000)
        self.player.video_set_spu_delay(self.subtitle_sync.value() * 1000)
        self._last_state = None
        self.playlist.setCurrentRow(index)
        self.statusBar().showMessage(path.name)
        QTimer.singleShot(700, self._tracks)

    def toggle(self):
        if self.player is None:
            return
        if self.player.is_playing():
            self.player.pause()
        elif self.index >= 0:
            self.player.play()

    def stop(self):
        if self.player is None:
            return
        self.player.stop()
        self.seek.setValue(0)
        self.time_label.setText("00:00:00 / 00:00:00")
        icon_button(self.play_button, "Play (Space)", "play")

    def previous(self):
        if self.files:
            self._play((self.index - 1) % len(self.files))

    def next(self):
        if self.files:
            self._play((self.index + 1) % len(self.files))

    def fullscreen(self):
        if self.isFullScreen():
            self.exit_fullscreen()
            return
        self._fullscreen_state = self.windowState()
        self._mouse_position = QCursor.pos()
        self._controls_until = time.monotonic() + 2.5
        self._options_visible = self.options_scroll.isVisible()
        self._playlist_visible = self.playlist.isVisible()
        for widget in (self.heading, self.playlist, self.options_scroll, self.options_toggle):
            widget.hide()
        self.centralWidget().layout().setContentsMargins(0, 0, 0, 0)
        self.statusBar().hide()
        icon_button(self.fullscreen_button, "Exit fullscreen (Escape)", "restore")
        self.showFullScreen()

    def exit_fullscreen(self):
        if not self.isFullScreen():
            return
        self.setWindowState(self._fullscreen_state or Qt.WindowNoState)
        for widget in (self.heading, self.options_toggle):
            widget.show()
        self.playlist.setVisible(self._playlist_visible)
        self.options_scroll.setVisible(self._options_visible)
        self.centralWidget().layout().setContentsMargins(24, 20, 24, 20)
        self.statusBar().show()
        icon_button(self.fullscreen_button, "Fullscreen (F11)", "fullscreen")
        self._show_controls(True)

    def _show_controls(self, visible):
        for widget in (self.seek, self.time_label, self.transport, self.volume_controls):
            widget.setVisible(visible)

    def _fullscreen_controls(self):
        if not self.isFullScreen():
            return
        position = QCursor.pos()
        if position != self._mouse_position:
            self._mouse_position = position
            self._controls_until = time.monotonic() + 2.5
            self._show_controls(True)
        if time.monotonic() > self._controls_until and not self.transport.underMouse() and not self.volume_controls.underMouse():
            self._show_controls(False)

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

    def _devices(self):
        self.devices.blockSignals(True)
        self.devices.clear()
        self.devices.addItem("System default", None)
        head = self.player.audio_output_device_enum()
        device = head
        try:
            while device:
                entry = device.contents
                device_id = entry.device.decode(errors="replace") if entry.device else ""
                name = entry.description.decode(errors="replace") if entry.description else device_id
                if device_id:
                    self.devices.addItem(name, device_id)
                device = entry.next
        finally:
            if head:
                self.vlc.libvlc_audio_output_device_list_release(head)
        current = self.player.audio_output_device_get()
        if current:
            current = current.decode(errors="replace") if isinstance(current, bytes) else current
            self.devices.setCurrentIndex(max(0, self.devices.findData(current)))
        self.devices.blockSignals(False)

    def _device(self):
        device = self.devices.currentData()
        self.player.audio_output_device_set(None, device)

    def load_subtitles(self):
        name, _ = QFileDialog.getOpenFileName(self, "Load subtitles", "", "Subtitle files (*.srt *.ass *.ssa *.sub *.vtt *.txt);;All files (*)")
        if name and self.index >= 0:
            if not self.player.video_set_subtitle_file(name):
                QMessageBox.warning(self, "Play", "VLC could not load this subtitle file.")
            QTimer.singleShot(300, self._tracks)

    def _refresh(self):
        self._fullscreen_controls()
        if self.player is None or self.index < 0:
            return
        state = self.player.get_state()
        changed = state != self._last_state
        self._last_state = state
        if changed:
            icon_button(self.play_button, "Pause (Space)" if state == self.vlc.State.Playing else "Play (Space)",
                        "pause" if state == self.vlc.State.Playing else "play")
        if changed and state == self.vlc.State.Playing:
            self._tracks()
        if changed and state == self.vlc.State.Error:
            self.statusBar().showMessage("Could not play this file. It may be damaged or use an unsupported codec.")
        duration = self.player.get_length()
        elapsed = self.player.get_time()
        self.time_label.setText(f"{clock(elapsed)} / {clock(duration)}")
        if duration > 0 and not self.seeking:
            self.seek.setValue(max(0, min(1000, int(elapsed * 1000 / duration))))
        if changed and state == self.vlc.State.Ended:
            if self.loop.isChecked():
                self._play(self.index)
            elif self.index + 1 < len(self.files):
                self._play(self.index + 1)

    def closeEvent(self, event):
        self.exit_fullscreen()
        self.options_scroll.hide()
        self.options_toggle.setChecked(False)
        self.timer.stop()
        if self.player is not None:
            self.player.stop()
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "timer"):
            self.timer.start(300)
