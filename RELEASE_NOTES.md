## FreeConvert 0.19.0

Dazzle now edits actual slide objects instead of only a title/body pair. Insert text boxes, images, embedded videos, shapes, editable tables and column/bar/line/pie/scatter charts. Select, move, resize, rotate, format and layer objects; change backgrounds; add on-click fades and fade slide transitions; reorder slides; undo/redo; present fullscreen with F5. PPTX and Dazzle projects retain the native package and media.

Pages adds rich image/table insertion, rendered charts and shapes, page breaks, paragraph colors and local video links. Tables adds real XLSX charts, anchored images, previews and local video hyperlinks while retaining unrelated workbook package parts.

The new **Document pages** entry provides a visual PDF organizer: drag reorder, move, rotate, remove from a new output, extract selected pages, split into individual pages or range groups, and combine PDFs. Source documents remain untouched.

The existing black/yellow theme, compact icons, temporary hover feedback, Play media player and 15 Office templates remain available. See the updated [README](https://github.com/Thatweirdguy1/FreeConvert#readme) and [feature/verification report](https://github.com/Thatweirdguy1/FreeConvert/blob/main/docs/OFFICE_FEATURES_019.md).

### Downloads

- `FreeConvert-0.19.0-Setup.exe`: Windows installer with Desktop/Start menu shortcuts.
- `LocalFileConverter-Windows-x64.zip`: portable Windows app; extract the whole folder.
- `LocalFileConverter-macOS-Apple-Silicon.zip`: Apple Silicon app.
- `LocalFileConverter-macOS-Intel.zip`: Intel macOS app.
- `SHA256SUMS.txt`: download checksums.

### Scope and verification

The feature fixtures were opened/exported by installed PowerPoint, Word, Excel and LibreOffice. Regression tests cover native object persistence, selection/resizing/undo, charts, media, preservation and nondestructive page operations. GitHub Actions checks source and packaged OCR, Office, playback and conversion on all three build targets.

This is a substantial local editor update, not full Microsoft Office parity. Fade effects are the supported authored animations. SmartArt/groups/advanced imported effects are preserved but not fully editable/rendered. Pages charts/shapes are images; Pages/Tables videos are local links, while Dazzle embeds media. The organizer works on PDF pages. Windows downloads remain unsigned and macOS apps unnotarized.
