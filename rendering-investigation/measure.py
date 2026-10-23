from pathlib import Path
from pypdf import PdfReader
from PIL import ImageChops
import pypdfium2 as pdfium

root = Path(__file__).resolve().parent
for pdf in sorted(root.glob('**/*.pdf')):
    reader = PdfReader(pdf)
    pages = reader.pages
    fonts = set()
    for page in pages:
        resources = page.get('/Resources')
        if resources:
            font_map = resources.get_object().get('/Font')
            if font_map:
                for value in font_map.get_object().values():
                    fonts.add(str(value.get_object().get('/BaseFont', 'unknown')))
    image_count = 0
    for page in pages:
        resources = page.get('/Resources')
        xobjects = resources.get_object().get('/XObject') if resources else None
        if xobjects:
            image_count += sum(1 for obj in xobjects.get_object().values()
                               if obj.get_object().get('/Subtype') == '/Image')
    print(pdf.relative_to(root), 'pages=', len(pages), 'sizes=',
          [(round(float(p.mediabox.width)), round(float(p.mediabox.height))) for p in pages],
          'fonts=', sorted(fonts), 'images=', image_count,
          'text_chars=', sum(len(p.extract_text() or '') for p in pages))

for name, office, libre in [('xlsx', root/'office-pdf/excel.pdf', root/'lo-xlsx/layout.pdf'),
                             ('pptx', root/'office-pdf/powerpoint.pdf', root/'lo-pptx/layout.pdf'),
                             ('docx', root/'office-pdf/word.pdf', root/'lo-docx/layout.pdf')]:
    if not office.exists() or not libre.exists():
        continue
    docs = [PdfReader(path) for path in (office, libre)]
    def positions(page):
        out = []
        page.extract_text(visitor_text=lambda text, cm, tm, font, size:
                          out.append((text.strip()[:24], round(tm[4], 1), round(tm[5], 1))) if text.strip() else None)
        return out[:5]
    print(name, 'first_text_positions=', positions(docs[0].pages[0]), positions(docs[1].pages[0]))
    images = []
    for path in (office, libre):
        pdf = pdfium.PdfDocument(str(path))
        images.append(pdf[0].render(scale=1).to_pil().convert('RGB'))
    if images[0].size == images[1].size:
        diff = ImageChops.difference(*images)
        pixels = sum(1 for rgb in diff.get_flattened_data() if rgb != (0, 0, 0))
        print(name, 'first_page_pixel_difference=',
              f'{pixels / (images[0].width * images[0].height):.1%}', 'bbox=', diff.getbbox())
    else:
        print(name, 'first_page_pixel_difference=not aligned; sizes=', [im.size for im in images])
