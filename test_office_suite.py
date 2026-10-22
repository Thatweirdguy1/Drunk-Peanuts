"""Round trips for the native office workspaces using temporary files."""

import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTableWidgetItem
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


if __name__ == "__main__":
    unittest.main()
