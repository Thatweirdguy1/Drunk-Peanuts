# Editable PDF and Windows Open with — 0.26.1

PDF → DOCX now defaults to **Editable text and images**. Selectable PDF text becomes normal Word paragraphs; embedded raster pictures become independently positioned Word images. This uses the bundled PDFium engine and works offline without installing Word. The reported private letter was checked locally: editable body text, separate letterhead/signature images, and a one-page LibreOffice rendering. The original was left untouched; private content is excluded from this repository.

This is a single-column reconstruction, not full PDF layout recovery. Font substitutions, line breaks, complex tables/columns and vector artwork can differ. Rotated pages must be prepared first. Image-only/scanned pages report that OCR is required rather than silently returning an image-only DOCX. **Preserve pages (not editable)** retains complete rendered pages; **Text only** omits images.

## Windows file integration

Setup includes eight small Windows launchers: Pages, Tables, Dazzle, Sketch, Organize, Formulaic, Writer and Play. Windows can identify each app separately rather than treating every workspace as the same generic executable. Launchers forward quoted file paths to the installed main executable. Office files open directly in their workspace; multiple documents open in separate windows, preserving existing work.

| App | Registered formats |
| --- | --- |
| Pages | DOCX, TXT, HTML, HTM |
| Tables | XLSX, CSV |
| Dazzle | PPTX, DAZZLE |
| Sketch | PNG, JPG, JPEG, BMP |
| Organize | SQLITE, DB |
| Formulaic | FORMULAIC, MML |
| Writer | FOUNTAIN, FDX |
| Play | MP4, MKV, MOV, AVI, WEBM, MPEG, MPG, WMV, M4V, MP3, WAV, FLAC, OGG, M4A, AAC, AIFF, WMA |

Registration uses per-user ProgIDs, Applications/SupportedTypes and RegisteredApplications capabilities. It never changes UserChoice, extension defaults or another application's registration. Setup registers automatically; a portable Windows download needs its complete extracted folder and a one-time `LocalFileConverter.exe --register-windows`. Uninstall removes matching owned values only. An older installation cannot unregister a newer installation.

Explorer chooses its short Open with list; **Choose another app** exposes additional candidates. Close and reopen an already open menu after installation. The desktop shortcut opens the main suite as before.

Microsoft references: [Open with registration](https://learn.microsoft.com/en-us/windows/win32/shell/how-to-include-an-application-on-the-open-with-dialog-box) and [application registration](https://learn.microsoft.com/en-us/windows/win32/shell/default-programs).

## Validation

Source checks cover PDF text/image preservation, explicit visual/text modes, quoted handler paths, no default changes, and independent Office document windows. Packaged native checks also exercise editable PDF conversion. Release and installed-app results are recorded after artifact verification.
