"""Small end-to-end checks using only temporary files."""

import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
import wave

from PIL import Image
from pypdf import PdfReader
from docx import Document
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from converter import available_formats, compress, convert, reduce_size
from app import Window, Worker, numbered_target
from converter import edit_image, extract_zip, ocr_to_text, pdf_merge, pdf_reorder, pdf_rotate, pdf_split, trim_media, zip_entries


class ConversionTest(unittest.TestCase):
    def test_image_pdf_and_back(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "sample.png"
            Image.new("RGB", (32, 24), "#0d9488").save(source)
            pdf = root / "sample.pdf"
            convert(source, pdf)
            self.assertEqual(len(PdfReader(str(pdf)).pages), 1)
            output = root / "rendered.png"
            convert(pdf, output)
            with Image.open(output) as image:
                self.assertEqual(image.size, (64, 48))
            with self.assertRaises(FileExistsError):
                convert(source, pdf)

    def test_csv_xlsx_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "data.csv"
            source.write_text("name,value\nalpha,3\n", encoding="utf-8")
            spreadsheet = root / "data.xlsx"
            convert(source, spreadsheet)
            output = root / "again.csv"
            convert(spreadsheet, output)
            self.assertIn("alpha,3", output.read_text(encoding="utf-8-sig"))
            self.assertNotIn("xlsx", available_formats(spreadsheet))

    def test_local_document_conversion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "notes.txt"
            source.write_text("First line\nSecond line", encoding="utf-8")
            word = root / "notes.docx"
            convert(source, word)
            self.assertEqual([p.text for p in Document(word).paragraphs], ["First line", "Second line"])
            pdf = root / "notes.pdf"
            convert(source, pdf)
            extracted = root / "extracted.docx"
            convert(pdf, extracted)
            self.assertIn("First line", "\n".join(p.text for p in Document(extracted).paragraphs))
            self.assertIn("docx", available_formats(pdf))

        with patch("converter.office_binary", return_value="soffice"):
            self.assertIn("pdf", available_formats(Path("slides.pptx")))
            self.assertNotIn("xlsx", available_formats(Path("slides.pptx")))
            self.assertIn("rtf", available_formats(Path("letter.docx")))

    def test_zip_compression(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first, second = root / "one.txt", root / "two.txt"
            first.write_text("hello" * 100, encoding="utf-8")
            second.write_text("world" * 100, encoding="utf-8")
            archive = root / "files.zip"
            compress([first, second], archive)
            with ZipFile(archive) as opened:
                self.assertEqual(opened.namelist(), ["one.txt", "two.txt"])
                self.assertEqual(opened.read("one.txt"), first.read_bytes())
            with self.assertRaises(FileExistsError):
                compress([first], archive)

    def test_target_size_image(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "large.png"
            Image.effect_noise((256, 256), 100).convert("RGB").save(source)
            target = root / "large-smaller.webp"
            reduce_size(source, target, 0.02)
            self.assertLessEqual(target.stat().st_size, int(0.02 * 1024 * 1024))
            with Image.open(target) as image:
                self.assertEqual(image.format, "WEBP")

    def test_batch_runs_two_files_concurrently(self):
        barrier = threading.Barrier(2, timeout=3)
        worker = Worker([(Path("a"), Path("a.out")), (Path("b"), Path("b.out"))])
        result = []
        worker.finished_batch.connect(lambda done, failed: result.append((done, failed)))
        with patch("app.convert", side_effect=lambda *_: barrier.wait()):
            worker.run()
        self.assertEqual(result, [(2, 0)])

    def test_shift_drop_chooses_format_and_converts(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "note.txt"
            source.write_text("hello", encoding="utf-8")
            window = Window()

            class Menu:
                def __init__(self, *_):
                    self.actions = []

                def addAction(self, label):
                    self.actions.append(label)
                    return label

                def exec(self, _):
                    return "DOCX"

            with patch("app.QMenu", Menu), patch.object(window, "_convert") as start:
                data = QMimeData()
                data.setUrls([QUrl.fromLocalFile(str(source))])
                drop = QDropEvent(QPointF(5, 5), Qt.CopyAction, data, Qt.LeftButton, Qt.ShiftModifier)
                window.drop.dropEvent(drop)
                self.assertEqual(window.format.currentText(), "docx")
                start.assert_called_once()
            window.close()

    def test_mixed_formats_and_numbered_outputs(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "same.png"
            Image.new("RGB", (20, 20), "red").save(image)
            text = root / "same.txt"
            text.write_text("hello", encoding="utf-8")
            image, text = image.resolve(), text.resolve()
            (root / "same.pdf").write_bytes(b"existing")
            (root / "same.docx").write_bytes(b"existing word file")
            window = Window()
            window.output_dir = root
            window._add_files([image, text])
            self.assertEqual(window.formats[image], "webp")
            window.list.setCurrentRow(1)
            window.format.setCurrentText("docx")
            self.assertEqual(window.formats[text], "docx")
            self.assertEqual(window.formats[image], "webp")
            reserved = {str(image).casefold(), str(text).casefold()}
            first = numbered_target(root, "same", ".pdf", reserved)
            second = numbered_target(root, "same", ".pdf", reserved)
            self.assertEqual((first.name, second.name), ("same (2).pdf", "same (3).pdf"))
            window._convert()
            self.assertTrue(window.worker.wait(10000))
            app.processEvents()
            self.assertTrue((root / "same.webp").exists())
            self.assertEqual(Document(root / "same (2).docx").paragraphs[0].text, "hello")
            self.assertEqual((root / "same.docx").read_bytes(), b"existing word file")
            window.close()

    def test_pdf_tools_keep_pages_and_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = root / "first.pdf"
            second = root / "second.pdf"
            (root / "first.txt").write_text("FIRST", encoding="utf-8")
            (root / "second.txt").write_text("SECOND", encoding="utf-8")
            convert(root / "first.txt", first)
            convert(root / "second.txt", second)
            merged = root / "merged.pdf"
            pdf_merge([first, second], merged)
            self.assertEqual(len(PdfReader(str(merged)).pages), 2)
            (root / "merged-2.png").write_bytes(b"existing page image")
            self.assertEqual(numbered_target(root, "merged", ".png", set(), pages=2).name, "merged (2).png")
            reordered = root / "reordered.pdf"
            pdf_reorder(merged, reordered, [2, 1])
            self.assertIn("SECOND", PdfReader(str(reordered)).pages[0].extract_text())
            rotated = root / "rotated.pdf"
            pdf_rotate(first, rotated, 90)
            self.assertEqual(PdfReader(str(rotated)).pages[0].rotation, 90)
            pages = root / "pages"
            pdf_split(merged, pages)
            self.assertEqual(sorted(path.name for path in pages.iterdir()), ["page-1.pdf", "page-2.pdf"])
            with self.assertRaises(ValueError):
                pdf_reorder(merged, root / "bad.pdf", [1, 1])
            self.assertIn("FIRST", PdfReader(str(first)).pages[0].extract_text())

    def test_image_tools_resize_crop_and_strip_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "photo.png"
            Image.new("RGB", (60, 40), "blue").save(source, pnginfo=self._comment())
            resized = root / "resized.png"
            edit_image(source, resized, "resize", (30, 30))
            with Image.open(resized) as image:
                self.assertEqual(image.size, (30, 20))
            cropped = root / "cropped.png"
            edit_image(source, cropped, "crop", (10, 5, 20, 15))
            with Image.open(cropped) as image:
                self.assertEqual(image.size, (20, 15))
            stripped = root / "stripped.png"
            edit_image(source, stripped, "strip_metadata")
            with Image.open(stripped) as image:
                self.assertNotIn("Comment", image.info)
            with self.assertRaises(ValueError):
                edit_image(source, root / "bad.png", "crop", (50, 0, 20, 20))

    def test_media_trim_keeps_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "tone.wav"
            with wave.open(str(source), "wb") as output:
                output.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                output.writeframes(b"\x00\x00" * 16000)
            trimmed = root / "tone-trimmed.wav"
            trim_media(source, trimmed, 0.5, 1.5)
            with wave.open(str(trimmed), "rb") as result:
                self.assertAlmostEqual(result.getnframes() / result.getframerate(), 1, delta=0.1)
            with self.assertRaises(FileExistsError):
                trim_media(source, trimmed, 0.5, 1.5)
            self.assertTrue(source.exists())

    def test_zip_preview_and_safe_extraction(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "files.zip"
            with ZipFile(archive, "w") as output:
                output.writestr("inside/note.txt", "hello")
            self.assertEqual(zip_entries(archive)[0][0], "inside/note.txt")
            target = root / "extracted"
            extract_zip(archive, target)
            self.assertEqual((target / "inside" / "note.txt").read_text(), "hello")
            with self.assertRaises(FileExistsError):
                extract_zip(archive, target)
            bad = root / "bad.zip"
            with ZipFile(bad, "w") as output:
                output.writestr("../escape.txt", "no")
            with self.assertRaises(ValueError):
                extract_zip(bad, root / "unsafe")
            self.assertFalse((root / "escape.txt").exists())

    def test_ocr_image_and_pdf_pages(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "scan.png"
            Image.new("RGB", (20, 20), "white").save(image)
            with patch("converter.tesseract_binary", return_value="tesseract"), patch("converter.subprocess.run") as run:
                run.return_value.returncode = 0
                run.return_value.stdout = "recognized text\n"
                ocr_to_text(image, root / "image.txt")
                self.assertEqual((root / "image.txt").read_text(), "recognized text\n")
                run.assert_called_once()
                self.assertEqual(run.call_args.args[0][-3:], ["stdout", "-l", "eng"])
                pdf = root / "pages.pdf"
                convert(image, pdf)
                ocr_to_text(pdf, root / "pages.txt")
                self.assertIn("recognized text", (root / "pages.txt").read_text())

    @staticmethod
    def _comment():
        from PIL.PngImagePlugin import PngInfo
        metadata = PngInfo()
        metadata.add_text("Comment", "private")
        return metadata


if __name__ == "__main__":
    unittest.main()
