import unittest
import tempfile
from pathlib import Path
from windows_integration import registration_values, MEDIA_EXTENSIONS


class WindowsIntegrationTest(unittest.TestCase):
    def test_quoted_media_handler_does_not_set_defaults(self):
        executable = Path('build/App with spaces/LocalFileConverter.exe').resolve()
        values = registration_values(executable)
        commands = [v for path, name, v in values if path.endswith('open\\command')]
        self.assertEqual(commands, [f'"{executable}" --play "%1"'] * 2)
        for extension in MEDIA_EXTENSIONS:
            self.assertIn(('Software\\Classes\\' + extension + '\\OpenWithProgids', 'FreeConvert.Media', ''), values)
        self.assertFalse(any('UserChoice' in path or name == 'ProgId' for path, name, _ in values))

    def test_templates_are_editable_copies_and_never_overwrite(self):
        from office_templates import ASSETS, TEMPLATES, create_document
        from docx import Document
        from openpyxl import load_workbook
        from pptx import Presentation
        with tempfile.TemporaryDirectory() as folder:
            for workspace, names in TEMPLATES.items():
                for name in names:
                    target = create_document(workspace, name, Path(folder)/name)
                    self.assertEqual(target.read_bytes(), (ASSETS/'templates'/name).read_bytes())
                    with self.assertRaises(FileExistsError):
                        create_document(workspace, name, target)
            self.assertIn('Report title', [p.text for p in Document(Path(folder)/'Report.docx').paragraphs])
            book = load_workbook(Path(folder)/'Budget.xlsx')
            self.assertEqual(book.active['D2'].value, '=B2-C2')
            book.close()
            self.assertEqual(len(Presentation(Path(folder)/'Presentation.pptx').slides), 4)
            import sqlite3
            from contextlib import closing
            with closing(sqlite3.connect(Path(folder)/'Contacts.sqlite')) as db:
                self.assertEqual(db.execute("SELECT value FROM _freeconvert_meta WHERE key='owner'").fetchone(), ('Organize',))


if __name__ == '__main__':
    unittest.main()
