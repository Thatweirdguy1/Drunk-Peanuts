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

from screenplay import export_script, from_fdx, merge_fdx, parse_fountain, to_fdx, to_pdf
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
    def test_import_script_over_20_mb(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "large.fountain"
            source.write_text(("A" * 4095 + "\n") * 5121, encoding="utf-8")
            self.assertGreater(source.stat().st_size, 20 * 1024 * 1024)
            app = QApplication.instance() or QApplication([])
            with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
                window = ScreenwriterWindow()
            window.autosave = Path(folder) / "autosave.fountain"
            with patch("screenwriter.QFileDialog.getOpenFileName", return_value=(str(source), "")):
                window._open()
            self.assertEqual(window.editor.toPlainText(), source.read_text(encoding="utf-8"))
            window.close()

    def test_edited_fdx_keeps_unrelated_metadata(self):
        original = b'''<?xml version="1.0" encoding="UTF-8"?>
<FinalDraft Version="13"><CustomMetadata id="keep"><Revision key="A"/></CustomMetadata>
<Content><Paragraph Type="Scene Heading" Number="7"><SceneProperties Page="3" Title="Story beat"/><Text>INT. ROOM - DAY</Text></Paragraph>
<Paragraph Type="Action" id="action-1"><Text>The door opens.</Text></Paragraph></Content></FinalDraft>'''
        before = from_fdx(original.decode())
        after = before.replace("The door opens.", "The door closes.")
        merged = ET.fromstring(merge_fdx(original, before, after))
        self.assertEqual(merged.find("./CustomMetadata/Revision").get("key"), "A")
        self.assertEqual(merged.find("./Content/Paragraph/SceneProperties").get("Title"), "Story beat")
        self.assertEqual(merged.findall("./Content/Paragraph")[1].get("id"), "action-1")
        self.assertEqual(merged.findall("./Content/Paragraph")[1].findtext("Text"), "The door closes.")
        with self.assertRaises(ValueError):
            merge_fdx(original, before, after + "\nAnother action.\n")

    def test_pdf_uses_fdx_page_size_and_keeps_cue_with_dialogue(self):
        source = "INT. ROOM - DAY\n\n" + "\n\n".join(f"Action number {n}." for n in range(28)) + "\n\n@MAYA\nStay here.\n"
        settings = b'''<FinalDraft><PageLayout TopMargin="90" BottomMargin="62"><PageSize Width="8.5" Height="5.5"/></PageLayout>
<ElementSettings Type="Action"><FontSpec Size="12"/><ParagraphSpec LeftIndent="1.25" RightIndent="7.25" SpaceBefore="12" Spacing="1"/></ElementSettings></FinalDraft>'''
        with tempfile.TemporaryDirectory() as folder:
            normal = Path(folder) / "normal.pdf"
            compact = Path(folder) / "compact.pdf"
            to_pdf(source, normal)
            to_pdf(source, compact, settings)
            default_pages = PdfReader(str(normal)).pages
            compact_pages = PdfReader(str(compact)).pages
            self.assertGreater(len(compact_pages), len(default_pages))
            self.assertEqual(float(compact_pages[0].mediabox.height), 396)
            pages = [page.extract_text() for page in compact_pages]
            self.assertEqual(sum(page.count("Action number") for page in pages), 28)
            self.assertTrue(any("MAYA" in page and "Stay here." in page for page in pages))

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

    def test_unchanged_fdx_export_keeps_original_bytes(self):
        QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "original.fdx"
            target = Path(folder) / "copy.fdx"
            original = b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?><FinalDraft Version="13"><CustomMetadata id="keep"/><Content><Paragraph Type="Scene Heading"><Text>INT. ROOM - DAY</Text></Paragraph></Content></FinalDraft>'
            source.write_bytes(original)
            with patch("screenwriter.QMessageBox.question", return_value=QMessageBox.No):
                window = ScreenwriterWindow()
            window.autosave = Path(folder) / "draft.fountain"
            with patch("screenwriter.QFileDialog.getOpenFileName", return_value=(str(source), "")):
                window._open()
            with patch("screenwriter.QFileDialog.getSaveFileName", return_value=(str(target), "Final Draft (*.fdx)")):
                window._export()
            self.assertEqual(target.read_bytes(), original)
            edited = Path(folder) / "edited.fdx"
            window.editor.setPlainText(window.editor.toPlainText().replace("ROOM", "HALL"))
            with patch("screenwriter.QFileDialog.getSaveFileName", return_value=(str(edited), "Final Draft (*.fdx)")):
                window._export()
            self.assertEqual(ET.fromstring(edited.read_bytes()).find("CustomMetadata").get("id"), "keep")
            self.assertIn("INT. HALL", edited.read_text())
            window.editor.document().setModified(False)
            window.close()


if __name__ == "__main__":
    unittest.main()
