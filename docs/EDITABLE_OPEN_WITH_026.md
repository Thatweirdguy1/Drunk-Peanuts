# Editable PDF and Windows Open with — 0.26.2

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

- 89 source tests passed locally; Windows, Intel macOS and Apple Silicon CI all passed on commit `7d96bc0` (run `40374306166`).
- Windows installer and portable ZIP match both the release checksum manifest and GitHub asset digests. The installed main executable and all eight launchers match the verified CI package.
- Installed Office imports, media-engine initialization, native document round trip and editable PDF conversion passed. The private sample retains all selectable non-whitespace text in order, nine embedded image files and eleven positioned pictures; the original PDF hash is unchanged. The editable copy is local only.
- All 35 recorded default-app choices remained unchanged after installation. Windows' native `SHAssocEnumHandlers` recognizes Play as recommended, with a valid executable, display name and icon.
- **Unresolved:** this Windows 11 Explorer still omits Play and Pages from its short Open with menu, including after an Explorer restart. Extra registry/cache experiments did not resolve it and were removed. The system app chooser is not exposed as a targetable window by the computer helper; a one-time manual selection is pending before further UI verification. Do not interpret registration tests as proof that the visible menu issue is fixed.
- Version 0.26.2 remains a draft release pending that check. No personal document content is included in the public repository.
