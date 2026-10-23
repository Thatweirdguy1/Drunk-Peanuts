"""PC playback controls without requiring a media file."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from watchit import WatchIT


class WatchITTest(unittest.TestCase):
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
