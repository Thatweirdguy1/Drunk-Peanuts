# Local File Converter

A free, local desktop file converter, compressor, and screenwriting workspace for Windows and macOS. Drop files into the queue, choose an output for each file, or use the PDF, image, media, ZIP, OCR, and writing tools.

![Local File Converter desktop app](docs/screenshot.png)

## Download

Download the zip for your system from the [latest release](https://github.com/Thatweirdguy1/FreeConvert/releases/latest). Extract it, then open `LocalFileConverter.exe` on Windows or `LocalFileConverter.app` on macOS. The macOS builds are unsigned; your system may require **Open Anyway** in Privacy & Security after the first launch. The app is free and needs no account.

The desktop downloads include [LibreOffice](https://www.libreoffice.org/) for local document, presentation, and spreadsheet conversions. **No separate LibreOffice installation is needed.** Select **Office suite** to open its full desktop editor for Writer, Calc, Impress, Draw, Base, and Math. The downloads are larger because they include the suite. When running from source, install LibreOffice separately or put `soffice` on `PATH` to enable Office conversions.

OCR runs locally using bundled [RapidOCR](https://github.com/RapidAI/RapidOCR) and English recognition models. No separate OCR installation, account, or network connection is needed.

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

The bundled LibreOffice runtime enables conversions within document (DOC, DOCX, ODT, RTF, TXT), presentation (PPT, PPTX, ODP), and spreadsheet (XLS, XLSX, ODS, CSV) families, plus PDF output. Output options vary by input. The **Office suite** button opens LibreOffice itself for richer editing than the converter window provides.

## Use

### Screenwriter

Select **Screenwriter** in the main window to write a screenplay locally. The editor uses [Fountain](https://fountain.io/syntax/) as its editable source format, with a live formatted preview, title page fields, scene navigation, a beat map (`#` sections and `=` synopses), character picker, emphasis buttons, dual dialogue, find, and local autosave with crash recovery. **New**, **Open**, and **Save** work with `.fountain`; **Open** also imports Final Draft `.fdx`, plain text, and Markdown. Scripts stay on your device.

Use **Export** to save a separate **PDF, Fountain, Final Draft (.fdx), plain text, HTML, or Markdown** file. Existing export files are not overwritten. PDF uses US Letter screenplay pages; HTML is printable in a browser. When you open an FDX and export it again *without editing*, the app copies its original bytes, preserving all metadata exactly. Once edited, FDX is regenerated from the Fountain source and only supported screenplay content is retained. The app's PDF layout is independent of Final Draft's renderer, so matching Final Draft page breaks is not guaranteed. For exact Final Draft pagination, export a PDF from Final Draft and use that PDF as the final copy.

Select an element in the toolbar or press **Ctrl+1–8**. **Tab** and **Shift+Tab** move through element types. Use **Ctrl+B/I/U** for emphasis, **Ctrl+D** to mark a second character cue as dual dialogue, **Ctrl+K** to insert a known character, and **Ctrl+S** to save. **Forward writing** provides optional timed sessions that lock completed lines while the timer runs. The writing tools work offline and need no account or LibreOffice.

### File conversion

1. Drag files into the window or select **Add files**.
2. Select each file for a visual image/PDF preview and choose its output format. Mixed formats can share one batch.
3. Choose a save folder and select **Convert files**.

For a shortcut, hold **Shift** while dropping files into the app's drop area. A menu at the pointer shows formats shared by those files and anything already queued. Choose one to apply that format to the queue and start conversion immediately into the selected save folder; dismiss the menu to cancel. The shortcut works inside the app window on Windows and macOS.

**PDF tools** merge queued PDFs in queue order, or split, reorder, and rotate the selected PDF. **Image tools** resize to fit within a width and height, crop by coordinates, rotate, or remove metadata from the selected image. Each tool saves a new file in the chosen folder. Animated images must be converted to a still image before editing.

**Media trim** takes start and end times in seconds. Precise trim re-encodes for accurate cuts; fast trim copies streams and may start at a nearby keyframe. It saves a new file alongside other outputs. FFmpeg is bundled with the app.

**Open ZIP** previews the selected archive's entries and unpacked size, then extracts it to a new numbered folder. Extraction rejects unsafe paths, duplicate names, symlinks, encrypted entries, and archives over 10,000 entries or 2 GB unpacked. Very high compression ratios are also rejected. **OCR to text** reads the selected image or each page of a scanned PDF and saves a UTF-8 text file. Recognition quality depends on the scan.

For command-line OCR, run `LocalFileConverter.exe --ocr input.png output.txt` on Windows or `LocalFileConverter.app/Contents/MacOS/LocalFileConverter --ocr input.png output.txt` on macOS. Existing output files are not replaced.

Select **Compress to ZIP** to save the queued files in one lossless archive. Files with duplicate names cannot share an archive.

For upload limits, enter a per-file size in MB and select **Reduce file size**. This creates WebP images, MP4 videos, MP3 audio, or a smaller PDF. The app checks the completed output and reports a failure if it cannot meet the limit. This mode may reduce image quality or dimensions; PDFs are rasterized, so their text will no longer be selectable. Animated images and Office documents are excluded from this mode.

Inputs are never overwritten. Existing output names and collisions within a batch get numbered copies, such as `photo (2).webp`. Multi-page PDF image outputs reserve all page names before the batch starts. Conversion and tools run in the background so the interface stays responsive; each item reports its stage and result.

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

- Regular PDF to text extracts embedded/selectable text. Use **OCR to text** for scanned PDFs.
- PDF to DOCX uses extracted text and does not preserve the PDF layout, images, or tables.
- Animated GIF input becomes a multi-page PDF or an animated GIF. Other raster outputs use the first frame.
- CSV to XLSX stores values as text; XLSX to CSV exports the active worksheet's displayed values.
- The bundled LibreOffice runtime handles Office files; it does not parse Final Draft metadata or reproduce Final Draft's pagination.
- LibreOffice's own format filters can change layout when moving between Office formats. Check important documents after conversion.
- Bundled OCR currently recognizes English text. RapidOCR and its converted PaddleOCR models are distributed under Apache 2.0; see [third-party notices](THIRD_PARTY_NOTICES.md).
- macOS builds are unnotarized and Windows builds are unsigned.

MIT licensed. See [LICENSE](LICENSE).
