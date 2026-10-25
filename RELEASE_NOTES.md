## FreeConvert 0.20.1

A Microsoft 365-style tabbed ribbon now organizes the six Office workspaces, with compact icons, quick access, live command search and scrolling groups for narrow windows. The converter drop area has a distinct expanding hover/drag highlight that clears when the pointer leaves.

This tested editing batch adds Pages headings, numbering, spacing, run formatting, find/replace and page setup; native XLSX cell formatting and clipboard tools in Tables; independent slide duplication/alignment in Dazzle; and formula insertion controls. It also fixes stale slide selection and retains native chart workbooks when duplicating slides.

The README has fresh screenshots. See [batch coverage and remaining work](https://github.com/Thatweirdguy1/FreeConvert/blob/main/docs/OFFICE_BATCHES.md). Full Office feature parity remains in progress; unfinished features are not represented by placeholder controls.

### Downloads

- `FreeConvert-0.20.1-Setup.exe`: Windows installer with Desktop/Start menu shortcuts.
- `LocalFileConverter-Windows-x64.zip`: portable Windows app; extract the entire folder.
- `LocalFileConverter-macOS-Apple-Silicon.zip`: Apple Silicon app.
- `LocalFileConverter-macOS-Intel.zip`: Intel macOS app.
- `SHA256SUMS.txt`: download checksums.

76 source tests passed, including native-format round trips for the new commands. Generated Office fixtures were opened/exported by installed Word, Excel and PowerPoint. Release builds check packaged OCR, native workspaces, playback and conversion on all three platforms.

Windows builds remain unsigned and macOS apps unnotarized. Tables previews show raw values; numeric display formats persist in XLSX. Filters and auto-fit are view controls. Existing advanced-object and video-link limits are documented in the feature report.
