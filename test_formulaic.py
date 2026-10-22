"""Native formula syntax and file smoke checks."""

import tempfile
import unittest
import xml.etree.ElementTree as ET
import os
from pathlib import Path
from zipfile import ZipFile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from pypdf import PdfReader
from formulaic import MATH, MIME, export_preview, mathml, read_formula, write_formula


class FormulaicTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_mathml_and_odf(self):
        source = "{alpha+x^2} over {sqrt {beta}}"
        markup = mathml(source)
        root = ET.fromstring(markup)
        self.assertEqual(root.tag, f"{{{MATH}}}math")
        self.assertIsNotNone(root.find(f".//{{{MATH}}}mfrac"))
        self.assertIn("α", markup.decode())
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "equation.odf"
            write_formula(source, output)
            with ZipFile(output) as archive:
                self.assertEqual(archive.namelist()[0], "mimetype")
                self.assertEqual(archive.read("mimetype").decode(), MIME)
                self.assertIn(b"mfrac", archive.read("content.xml"))
                self.assertEqual(ET.fromstring(archive.read("content.xml")).tag, f"{{{MATH}}}math")
            self.assertIn("over", read_formula(output))

    def test_invalid_formula_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing closing brace"):
            mathml("sqrt {x")

    def test_pdf_and_png_export(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pdf, png = root / "equation.pdf", root / "equation.png"
            export_preview("{a} over {b}", pdf)
            export_preview("{a} over {b}", png)
            self.assertEqual(len(PdfReader(pdf).pages), 1)
            self.assertGreater(png.stat().st_size, 100)


if __name__ == "__main__":
    unittest.main()
