"""Small end-to-end checks using only temporary files."""

import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from PIL import Image
from pypdf import PdfReader

from converter import available_formats, compress, convert, reduce_size


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


if __name__ == "__main__":
    unittest.main()
