"""Playlist round trips, folder commands and playback-preserving queue edits."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication
from play_queue import media_paths, save_playlist, PlayInbox
from watchit import WatchIT
from windows_integration import registration_values


class PlayQueueTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait(self, condition):
        deadline = time.monotonic() + 8
        while not condition() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.005)
        self.assertTrue(condition())

    def test_folder_playlist_roundtrip_and_untrusted_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root/'nested';nested.mkdir()
            one, two = root/'01 space #é.mp4', nested/'02.wav'
            one.touch();two.touch();(root/'ignore.txt').touch()
            expected = [one.resolve(), two.resolve()]
            self.assertEqual(media_paths([root]), expected)
            playlist = root/'List.m3u8'
            save_playlist(playlist, expected)
            self.assertEqual(media_paths([playlist]), expected)
            playlist.write_text('#EXTVLCOPT:run something\nList.m3u8\nhttps://example.com/media.mp4\nmissing.mp4\n01 space #é.mp4\n', encoding='utf-8')
            self.assertEqual(media_paths([playlist]), [one.resolve()])
            self.assertEqual(media_paths([root], cancelled=lambda: True), [])

    def test_enqueue_reorder_remove_and_clear_preserve_playing_item(self):
        player = MagicMock()
        with tempfile.TemporaryDirectory() as directory:
            files = [Path(directory)/f'{i}.mp4' for i in range(3)]
            for file in files:file.touch()
            window = WatchIT(engine=(MagicMock(), MagicMock(), player))
            window.timer.stop()
            try:
                window.add_media(files[:2])
                self.wait(lambda: window.scanner is None)
                self.assertEqual(window.index, 0)
                player.play.assert_called_once()
                window.add_media(files[2:], autoplay=False)
                self.wait(lambda: window.scanner is None)
                self.assertEqual(window.index, 0)
                self.assertEqual(player.play.call_count, 1)
                window.playlist.clearSelection()
                window.playlist.item(0).setSelected(True)
                window.move_selected(1)
                self.assertEqual(window.index, 1)
                self.assertEqual(window.files[1], files[0].resolve())
                window.playlist.clearSelection()
                window.playlist.item(0).setSelected(True)
                window.remove_selected()
                self.assertEqual(window.index, 0)
                self.assertEqual(window.files[0], files[0].resolve())
                self.assertEqual(player.play.call_count, 1)
                window.clear_playlist()
                self.assertEqual((window.index, window.files, window.playlist.count()), (-1, [], 0))
            finally:
                window.close()

    def test_folder_verbs_quote_paths_and_leave_vlc_defaults_alone(self):
        executable = Path('build/App with spaces/LocalFileConverter.exe').resolve()
        values = registration_values(executable)
        for verb, argument in (('Play', '--play'), ('Enqueue', '--enqueue')):
            self.assertIn(('Software\\Classes\\Directory\\shell\\DrunkPeanuts.'+verb+'\\command', '', f'"{executable}" {argument} "%1"'), values)
        self.assertFalse(any('VLC' in key or 'UserChoice' in key for key, _, _ in values))

    def test_other_process_can_enqueue_into_existing_play(self):
        import sys
        received = []
        with patch('play_queue.SERVER_NAME', 'DrunkPeanuts.Test.'+str(os.getpid())):
            inbox = PlayInbox(self.app, lambda names, enqueue: received.append((names, enqueue)))
            process = QProcess()
            process.start(sys.executable, ['-c', "import play_queue;play_queue.SERVER_NAME='DrunkPeanuts.Test."+str(os.getpid())+"';from PySide6.QtCore import QCoreApplication;a=QCoreApplication([]);assert play_queue.forward_play(['a file.mp4'],True)"])
            try:
                self.wait(lambda: process.state() == QProcess.NotRunning)
                self.assertEqual(process.exitCode(), 0, bytes(process.readAllStandardError()).decode())
                self.assertEqual(received, [([str(Path('a file.mp4').resolve())], True)])
            finally:
                inbox.server.close()
                inbox.deleteLater()


if __name__ == '__main__':
    unittest.main()
