"""Capture the actual Qt window for the README screenshot."""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import Window  # noqa: E402


with TemporaryDirectory() as folder:
    root = Path(folder)
    image = root / "mountain-photo.png"
    picture = Image.new("RGB", (960, 600), "#d8eee9")
    draw = ImageDraw.Draw(picture)
    draw.rectangle((0, 340, 960, 600), fill="#8ab8ad")
    draw.polygon([(0, 410), (300, 110), (560, 410)], fill="#376d75")
    draw.polygon([(290, 410), (680, 140), (960, 410)], fill="#245761")
    draw.ellipse((735, 65, 840, 170), fill="#f5be70")
    picture.save(image)
    document = root / "sample-report.pdf"
    pdf = canvas.Canvas(str(document))
    pdf.drawString(80, 700, "Sample report")
    pdf.save()
    app = QApplication([])
    window = Window()
    window._add_files([image, document])
    window.format.setCurrentText("jpg")
    window.show()

    def capture():
        window.grab().save(str(Path(__file__).with_name("screenshot.png")))
        app.quit()

    QTimer.singleShot(800, capture)
    app.exec()
