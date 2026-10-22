"""Round trips for the native office workspaces using temporary files."""

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTableWidgetItem
from openpyxl import Workbook, load_workbook
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches
from office_suite import Dazzle, Organize, Pages, Sketch, Tables, quote


class OfficeSuiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_roundtrips(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pages = Pages()
            pages.editor.setPlainText("Hello office")
            pages._write(root / "note.docx")
            pages.editor.clear()
            pages.path = None
            self.assertEqual(__import__("docx").Document(root / "note.docx").paragraphs[0].text, "Hello office")

            tables = Tables()
            tables.grid.setItem(0, 0, QTableWidgetItem("42"))
            tables._write(root / "table.xlsx")
            tables.new()
            tables._read(root / "table.xlsx")
            self.assertEqual(tables.grid.item(0, 0).text(), "42")

            dazzle = Dazzle()
            dazzle.title.setPlainText("Title")
            dazzle.body.setPlainText("Body")
            dazzle._write(root / "slides.pptx")
            self.assertEqual(__import__("pptx").Presentation(root / "slides.pptx").slides[0].shapes.title.text, "Title")

            sketch = Sketch()
            sketch._write(root / "image.png")
            self.assertTrue((root / "image.png").stat().st_size > 0)

            organize = Organize()
            organize.path = root / "data.sqlite"
            with closing(sqlite3.connect(organize.path)) as db:
                with db:
                    db.execute("CREATE TABLE _freeconvert_meta (key TEXT PRIMARY KEY, value TEXT)")
                    db.execute("INSERT INTO _freeconvert_meta VALUES ('owner', 'Organize')")
                    db.execute("CREATE TABLE notes (title TEXT)")
            organize.refresh()
            organize.tables.setCurrentRow(0)
            organize.grid.setRowCount(1)
            organize.grid.setItem(0, 0, QTableWidgetItem("Local"))
            organize.save()
            with closing(sqlite3.connect(organize.path)) as db:
                self.assertEqual(db.execute("SELECT title FROM notes").fetchone()[0], "Local")
            external = root / "external.sqlite"
            with closing(sqlite3.connect(external)) as db:
                with db:
                    db.execute("CREATE TABLE original (value TEXT)")
            organize.path = external
            self.assertFalse(organize._editable())
            self.assertEqual(quote('a"b'), '"a""b"')

    def test_tables_keep_other_worksheets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.xlsx"
            book = Workbook()
            book.active["A1"] = "first"
            book.create_sheet("Other")["B2"] = "keep me"
            book.save(source)
            editor = Tables()
            editor._read(source)
            editor.grid.setItem(0, 0, QTableWidgetItem("changed"))
            target = root / "changed.xlsx"
            editor._write(target)
            saved = load_workbook(target)
            self.assertEqual(saved.active["A1"].value, "changed")
            self.assertEqual(saved["Other"]["B2"].value, "keep me")
            saved.close()
            self.assertEqual(load_workbook(source).active["A1"].value, "first")

    def test_dazzle_keeps_nontext_shapes_on_text_edit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.pptx"
            deck = Presentation()
            slide = deck.slides.add_slide(deck.slide_layouts[5])
            slide.shapes.title.text = "Before"
            shape = slide.shapes.add_shape(1, Inches(1), Inches(2), Inches(2), Inches(1))
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor(255, 0, 0)
            deck.save(source)
            editor = Dazzle()
            editor.imported_pptx = source
            editor.original_slides = [("Before", "")]
            editor.slides = [("Before", "")]
            editor.title.setPlainText("After")
            output = root / "edited.pptx"
            editor._write(output)
            saved = Presentation(output)
            self.assertEqual(saved.slides[0].shapes.title.text, "After")
            self.assertEqual(len(saved.slides[0].shapes), len(slide.shapes))


if __name__ == "__main__":
    unittest.main()
