"""Exercise packaged in-process Office conversion."""

import subprocess
import sys
import tempfile
from pathlib import Path


if __name__ == "__main__":
    executable = sys.argv[1]
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        source = root / "input.txt"
        source.write_text("Native conversion check", encoding="utf-8")
        odt = root / "output.odt"
        output = root / "again.txt"
        for first, second in ((source, odt), (odt, output)):
            subprocess.run([executable, "--convert", str(first), str(second)], check=True, timeout=60)
        if "Native conversion check" not in output.read_text(encoding="utf-8"):
            raise SystemExit("Packaged document round trip failed")
        from reportlab.pdfgen import canvas
        from docx import Document
        from PIL import Image
        from zipfile import ZipFile
        header = root/'header.png'
        Image.new('RGB', (200, 40), '#ffdd22').save(header)
        pdf = root/'letter.pdf'
        page = canvas.Canvas(str(pdf))
        page.drawImage(str(header), 50, 740, width=200, height=40)
        page.drawString(50, 700, 'Editable packaged PDF check')
        page.save()
        result = root/'letter.docx'
        subprocess.run([executable, '--convert', str(pdf), str(result)], check=True, timeout=60)
        assert 'Editable packaged PDF check' in ' '.join(p.text for p in Document(result).paragraphs)
        with ZipFile(result) as archive:
            assert any(n.startswith('word/media/') for n in archive.namelist())
            assert b'wp:anchor' in archive.read('word/document.xml')
    print("Packaged native Office conversion passed")
