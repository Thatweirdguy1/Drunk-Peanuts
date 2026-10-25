# FreeConvert 0.19.0 — Office features and document pages

## Audit and resulting coverage

| Area | Previous gap | Implemented behavior |
| --- | --- | --- |
| Dazzle model | Two text editors; no editable scene objects | Native PPTX-backed object canvas with selection, dragging and resize handle |
| Text | No object font or style controls | Font family/size, bold/italic/underline, text color, position, size and rotation |
| Insert | No images, shapes, tables, charts or videos | Embedded images/video, six shape choices, editable tables and column/bar/line/pie/scatter charts |
| Design | Fixed styling | Background color/image, object fill, layering and fade slide transition |
| Presenting | No usable slide show | F5 fullscreen; next/previous slide, on-click object fades and embedded video playback in Play |
| Slide management | Limited slide order | Add/delete, move up/down, undo/redo; PPTX and self-contained Dazzle project persistence |
| Pages | Text-only insertion/output | Rich Word text/images/tables; chart/shape images; page breaks, paragraph background, local video links with poster |
| Tables | No native drawing insertion | Native XLSX charts and anchored images, object preview sidebar, local video hyperlinks; unrelated package parts retained |
| Document splitter | Hidden text-based PDF commands | Visible Document pages entry, thumbnails/cards, drag reorder, move, rotate, extract, remove-from-output, split-all, split-ranges and combine |

## Inspection and evidence

**Static observation — REA/Ghidra 12.1.4:** inspected the installed LibreOffice `soffice.exe` PE64 launcher, SHA-256 `3aeb1080d40bc82596f36ea4dd75019ab6aadad676e73d348c355396a464537a`. Its defined string inventory identifies `soffice`; this launcher observation does not establish the implementation of charts or animations.

**Static observation — REA/Rizin:** inspected installed `POWERPNT.EXE`, SHA-256 `8b6684a9a02f13292ea283e9525a16e8c4e5a1bacd8cf31eaa494daf2f374bcc`, as PE64/x86-64. The tool reported unchanged artifact bytes. No Office executable or proprietary program code was copied into FreeConvert.

**Installed UI resources:** LibreOffice's Writer, Calc and Impress menu XML exposes `.uno:InsertGraphic`, `.uno:InsertObjectChart`, `.uno:InsertAVMedia`, `.uno:InsertTable`, `.uno:CustomAnimation` and `.uno:SlideChangeWindow`. These commands informed the separation of Insert, Design, Slide and Arrange controls.

**Controlled experiment — PowerPoint COM:** generated an owned one-textbox presentation with Arial 28-point bold text and a 0.6-second fade through `TimeLine.MainSequence.AddEffect`. Examined that fixture's saved OOXML timing tree to implement native on-click fades. The shipped XML template comes from this synthetic document, not from an Office binary.

**Native application experiment:** PowerPoint opened the generated two-slide feature deck (five objects on slide 1, four on slide 2) and reported one native animation effect. Word recognized one native table and one inline chart image. Excel recognized one native chart and two drawing objects. All three exported PDF through their documented Office interfaces. LibreOffice also exported all three generated formats: two slide pages, one document page and two spreadsheet pages. These are representative interoperability checks, not a guarantee for arbitrary Office files.

JADX, Apktool and ADB were not used against these Windows applications: no Android package/device was involved. Existing Android tooling/configuration was left intact.

## Verification and limits

All 71 source tests passed. Packaged OCR, native conversion and Office/playback import checks passed. The Windows installer was built and the Desktop shortcut launched version 0.19.0; an installed-app PDF export was verified as Research, Overview (90 degrees), Results, Next steps. A toolbar signal regression discovered during desktop checking is covered by a direct action-trigger test.

Source regression checks cover object hit testing, native charts, font/color save, image/media embedding, animation timing retention, Dazzle project round trips, undo, slide order, rich DOCX images/tables, XLSX package preservation and PDF range/reorder/rotation/splitting without changing source bytes.

- On-click fade and fade slide transitions are supported; advanced timelines and motion paths are outside this version's authoring tools.
- Unsupported grouped/SmartArt/advanced imported objects remain in native PPTX output but may appear as preserved-object placeholders on the canvas/PDF.
- Pages charts/decorative shapes are rendered images. Pages and Tables video insertion uses local file links; Dazzle embeds the actual movie.
- Rich editing refuses unsupported Word fields/objects rather than dropping them. Installed fonts affect rendering. XLSX charts use worksheet data; formula compatibility remains limited to existing supported operations in the local preview.
- Embedded videos are limited to 128 MB, images to 64 MB / 50 million pixels. Undo keeps up to 15 deck snapshots and trims history for large presentations.
- PDF organization acts on PDF pages, creates new outputs and never replaces the source. It does not split DOCX/XLSX files into editable Office pages.

References: [python-pptx shapes, media and charts](https://python-pptx.readthedocs.io/en/latest/api/shapes.html), [PowerPoint animation sequence](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.sequence), [LibreOffice Impress objects and animation](https://books.libreoffice.org/en/GS71/GS7106-GettingStartedWithImpress.html), and the [earlier original-engine rendering investigation](../rendering-investigation/REPORT.md).
