# Local File Converter

A free, local desktop file converter and compressor for Windows and macOS. Drop files into the queue, convert them to a shared output format, or package them in a lossless ZIP archive.

![Local File Converter desktop app](docs/screenshot.png)

## Download

Download the zip for your system from [Releases](https://github.com/Thatweirdguy1/local-file-converter/releases). Extract it, then open `LocalFileConverter.exe` on Windows or `LocalFileConverter.app` on macOS. The macOS builds are unsigned; your system may require **Open Anyway** in Privacy & Security after the first launch. The app is free and needs no account.

**For Office document, presentation, and spreadsheet conversions, install [LibreOffice](https://www.libreoffice.org/download/download-libreoffice/) separately.** It is not bundled with the app. The app detects standard Windows installations automatically; on macOS, make `soffice` available on `PATH`. Without LibreOffice, only the basic conversions listed below are available.

## What it converts

| Input | Output |
| --- | --- |
| JPG, PNG, HEIC, HEIF, TIFF, GIF, BMP, WebP, SVG, RAW (CR2/NEF/ARW), ICO | JPG, PNG, TIFF, GIF, BMP, WebP, ICO, PDF (where different from input) |
| PDF | PNG, JPG, WebP (one image per page), TXT or DOCX (selectable text only) |
| MP4, MOV, AVI, MPEG/MPG, MKV, WebM | MP4, MOV, AVI, MPEG, MKV, WebM, GIF, MP3, WAV, M4A, AAC, FLAC, OGG |
| MP3, WAV, AIFF, M4A, AAC, FLAC, OGG | MP3, WAV, AIFF, M4A, AAC, FLAC, OGG |
| CSV | XLSX, TXT |
| XLSX | CSV (first worksheet) |
| DOCX | TXT (paragraph text) |
| TXT | PDF, DOCX |

With LibreOffice detected, the app also exposes conversions within document (DOC, DOCX, ODT, RTF, TXT), presentation (PPT, PPTX, ODP), and spreadsheet (XLS, XLSX, ODS, CSV) families, plus PDF output. Output options vary by input and installed tools. The picker only shows formats common to all queued files.

## Use

1. Drag files into the window or select **Add files**.
2. Select a file for a visual image/PDF preview, then choose an output format.
3. Choose a save folder and select **Convert files**.

Select **Compress to ZIP** to save the queued files in one lossless archive. Files with duplicate names cannot share an archive.

For upload limits, enter a per-file size in MB and select **Reduce file size**. This creates WebP images, MP4 videos, MP3 audio, or a smaller PDF. The app checks the completed output and reports a failure if it cannot meet the limit. This mode may reduce image quality or dimensions; PDFs are rasterized, so their text will no longer be selectable. Animated images and Office documents are excluded from this mode.

Inputs are never overwritten. Existing outputs stop the batch before it starts. Conversion runs in the background so the interface stays responsive; each item reports its stage and result.

## Run from source

Python 3.11+ is required.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Run the conversion checks with `python -m unittest -q`. Tagged commits build Windows x64, macOS Intel, and macOS Apple Silicon downloads through GitHub Actions.

## Privacy and security

Files stay on your computer. The app has no upload service, analytics, or account. External tools are launched without a shell, inputs are not replaced, and SVG links to external resources are rejected. It is **not an operating-system sandbox**: codecs and LibreOffice process the supplied files with your user permissions. Only convert files from sources you trust. The bundled macOS app is not notarized.

## Limitations

- PDF to text extracts embedded/selectable text; it does not perform OCR.
- PDF to DOCX uses extracted text and does not preserve the PDF layout, images, or tables.
- Animated GIF input becomes a multi-page PDF or an animated GIF. Other raster outputs use the first frame.
- CSV to XLSX stores values as text; XLSX to CSV exports the active worksheet's displayed values.
- LibreOffice is a separate free installation and is required for full Office conversions.
- macOS builds are unnotarized and Windows builds are unsigned.

MIT licensed. See [LICENSE](LICENSE).
