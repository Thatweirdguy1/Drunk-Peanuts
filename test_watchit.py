"""PC playback controls without requiring a media file."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from watchit import WatchIT
from PySide6.QtCore import Qt


class WatchITTest(unittest.TestCase):
    def test_boost_and_pip_keep_player_surface_queue_and_restore_layout(self):
        app = QApplication.instance() or QApplication([])
        player = MagicMock()
        window = WatchIT(engine=(MagicMock(), MagicMock(), player))
        window.timer.stop()
        window.resize(780, 540)
        window.show()
        window.playlist_toggle.setChecked(True)
        app.processEvents()
        window.volume.setValue(200)
        player.audio_set_volume.assert_called_with(200)
        self.assertEqual(window.volume_label.text(), '200%')
        self.assertEqual((window.volume.minimum(), window.volume.maximum()), (0, 200))
        surface, native_window = int(window.surface.winId()), int(window.winId())
        size = window.size()
        flags = window.windowHandle().flags()
        files = window.files
        try:
            window.picture_in_picture()
            app.processEvents()
            self.assertTrue(window.windowHandle().flags() & Qt.WindowStaysOnTopHint)
            self.assertLessEqual(window.width(), 500)
            self.assertFalse(window.playlist.isVisible())
            self.assertFalse(window.volume.isVisible())
            self.assertTrue(window.pip_button.isVisible())
            self.assertTrue(window.mute.isVisible())
            self.assertEqual(int(window.surface.winId()), surface)
            self.assertEqual(int(window.winId()), native_window)
            window.escape_view()
            app.processEvents()
            self.assertEqual(window.windowHandle().flags(), flags)
            self.assertEqual(window.size(), size)
            self.assertTrue(window.playlist.isVisible())
            self.assertTrue(window.volume.isVisible())
            self.assertEqual(window.volume.value(), 200)
            self.assertIs(window.files, files)
            player.stop.assert_not_called()
            player.play.assert_not_called()
            player.set_media.assert_not_called()
            window.playlist_toggle.setChecked(False)
            window.picture_in_picture()
            window._append_media([Path('queued while in PiP.mp4').resolve()], False)
            self.assertTrue(window.playlist.isHidden())
            self.assertTrue(window.playlist_tools.isHidden())
            window.exit_pip()
            self.assertFalse(window.playlist_toggle.isChecked())
            self.assertTrue(window.playlist.isHidden())
            window.fullscreen()
            window.picture_in_picture()
            self.assertFalse(window.isFullScreen())
            self.assertIsNotNone(window._pip_state)
            window.fullscreen()
            self.assertIsNone(window._pip_state)
            self.assertTrue(window.isFullScreen())
            window.escape_view()
            window.showMaximized()
            app.processEvents()
            window.picture_in_picture()
            window.escape_view()
            self.assertTrue(window.isMaximized())
        finally:
            window.close()

    @unittest.skipUnless((sys.platform == "win32" and (Path(os.environ.get("ProgramFiles", "")) / "VideoLAN/VLC/libvlc.dll").is_file()) or
                         (sys.platform == "darwin" and Path("/Applications/VLC.app/Contents/MacOS/lib/libvlc.dylib").is_file()),
                         "Source playback test needs installed VLC")
    def test_sync_and_device_controls(self):
        app = QApplication.instance() or QApplication([])
        window = WatchIT()
        self.assertGreaterEqual(window.devices.count(), 1)
        with patch.object(window.player, "audio_set_delay") as audio, patch.object(window.player, "video_set_spu_delay") as subtitles:
            window.audio_sync.setValue(250)
            window.subtitle_sync.setValue(-500)
            audio.assert_called_with(250000)
            subtitles.assert_called_with(-500000)
        window.close()


if __name__ == "__main__":
    unittest.main()
