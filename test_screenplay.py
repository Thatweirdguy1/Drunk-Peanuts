"""Screenplay round-trip and export checks."""

import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader
from PySide6.QtWidgets import QApplication, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from screenplay import export_script, from_fdx, parse_fountain, to_fdx
from screenwriter import ScreenwriterWindow


SAMPLE = """Title: NIGHT RUN
Credit: Written by
Author: A. Writer

# ACT I
= The chase begins.

INT. GARAGE - NIGHT

The door opens.

MAYA
(whispering)
Go now.

LUKE ^
I'm coming.

CUT TO:
"""


class ScreenplayTest(unittest.TestCase):
    def test_parse_and_all_exports(self):
        title, elements = parse_fountain(SAMPLE)
        self.assertEqual(title["title"], "NIGHT RUN")
        self.assertEqual([element.kind for element in elements],
                         ["section", "synopsis", "scene", "action", "character", "parenthetical",
                          "dialogue", "character", "dialogue", "transition"])
        self.assertTrue(elements[7].dual)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for suffix in (".pdf", ".fountain", ".fdx", ".txt", ".html", ".md"):
                export_script(SAMPLE, root / f"script{suffix}")
                self.assertGreater((root / f"script{suffix}").stat().st_size, 20)
            self.assertIn("NIGHT RUN", PdfReader(str(root / "script.pdf")).pages[0].extract_text())
            self.assertEqual(ET.fromstring((root / "script.fdx").read_text()).tag, "FinalDraft")
            self.assertIn("INT. GARAGE", from_fdx(to_fdx(SAMPLE)))
            self.assertIn("<p class=\"scene\">INT. GARAGE", (root / "script.html").read_text())
            self.assertIn("### INT. GARAGE", (root / "script.md").read_text())
            with self.assertRaises(FileExistsError):
                export_script(SAMPLE, root / "script.pdf")

    def test_editor_scene_navigation_and_autosave(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            with patch("screenwriter.QMessageBox.question", return_value=QMessageBox.No):
                window = ScreenwriterWindow()
            window.autosave = Path(folder) / "draft.fountain"
            window.editor.setPlainText(SAMPLE)
            window._refresh()
            self.assertEqual(window.scenes.count(), 1)
            window._autosave()
            self.assertEqual(window.autosave.read_text(), SAMPLE)
            window.editor.document().setModified(False)
            window.close()


if __name__ == "__main__":
    unittest.main()
