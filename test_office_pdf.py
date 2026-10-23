"""Checks for optional native PDF rendering and output safety."""

import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from reportlab.pdfgen import canvas

from office_pdf import export_pdf, resolve_engine
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from app import Window


class OfficePdfTest(unittest.TestCase):
    def test_renderer_choice_is_per_file(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first, second = root / "first.docx", root / "second.docx"
            first.write_bytes(b"fixture")
            second.write_bytes(b"fixture")
            window = Window()
            window._add_files([first, second])
            window.list.setCurrentRow(0)
            self.assertTrue(window.pdf_engine_panel.isVisibleTo(window))
            self.assertEqual(window.pdf_engine.currentData(), "auto")
            window.pdf_engine.setCurrentIndex(window.pdf_engine.findData("built-in"))
            window.list.setCurrentRow(1)
            self.assertEqual(window.pdf_engine.currentData(), "auto")
            window.list.setCurrentRow(0)
            self.assertEqual(window.pdf_engine.currentData(), "built-in")
            window.close()

    def test_auto_prefers_original_application(self):
        source = Path("sample.docx")
        with patch("office_pdf._office_executable", return_value=Path("word.exe")), \
             patch("office_pdf._libreoffice_executable", return_value=Path("soffice")):
            self.assertEqual(resolve_engine(source, "auto"), "microsoft")
        with patch("office_pdf._office_executable", return_value=None), \
             patch("office_pdf._libreoffice_executable", return_value=Path("soffice")):
            self.assertEqual(resolve_engine(source, "auto"), "libreoffice")

    def test_export_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "sample.docx"
            source.write_bytes(b"sample")
            target = root / "sample.pdf"
            target.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                export_pdf(source, target, "microsoft")
            self.assertEqual(target.read_bytes(), b"existing")

    def test_external_export_validates_pdf_and_cleans_failed_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "sample.docx"
            source.write_bytes(b"sample")
            target = root / "sample.pdf"

            def make_pdf(_source, output):
                pdf = canvas.Canvas(str(output))
                pdf.drawString(72, 720, "Native engine")
                pdf.save()

            with patch("office_pdf.resolve_engine", return_value="microsoft"), \
                 patch("office_pdf._microsoft_pdf", side_effect=make_pdf):
                export_pdf(source, target, "microsoft")
            self.assertTrue(target.is_file())

            bad = root / "invalid.pdf"
            with patch("office_pdf.resolve_engine", return_value="microsoft"), \
                 patch("office_pdf._microsoft_pdf", side_effect=lambda _s, p: p.write_bytes(b"not pdf")):
                with self.assertRaises(Exception):
                    export_pdf(source, bad, "microsoft")
            self.assertFalse(bad.exists())


if __name__ == "__main__":
    unittest.main()
