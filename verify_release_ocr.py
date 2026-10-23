"""Check that a packaged app can OCR without installed tools or model downloads."""

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


with tempfile.TemporaryDirectory() as folder:
    source = Path(folder) / "scan.png"
    target = Path(folder) / "scan.txt"
    image = Image.new("RGB", (600, 160), "white")
    ImageDraw.Draw(image).text((25, 35), "HELLO OCR 123", fill="black", font=ImageFont.load_default(size=48))
    image.save(source)
    subprocess.run([sys.argv[1], "--ocr", str(source), str(target)], check=True, timeout=120)
    assert "HELLO" in target.read_text(encoding="utf-8"), "Packaged OCR failed to recognize test image"
    fixtures = Path(__file__).parent / "test_data"
    for language, name, expected in (("cyrillic", "cyrillic", "Привет"),
                                     ("hindi", "hindi", "भारत"),
                                     ("korean", "korean", "세계"),
                                     ("arabic", "arabic", "مرحبا")):
        output = Path(folder) / f"{name}.txt"
        subprocess.run([sys.argv[1], "--ocr-with", language,
                        str(fixtures / f"ocr_{name}.png"), str(output)], check=True, timeout=120)
        assert expected in output.read_text(encoding="utf-8"), f"Packaged {language} OCR failed"
