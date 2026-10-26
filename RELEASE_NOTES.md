## Drunk Peanuts 0.24.0

Tables adds native XLSX worksheet print settings: Letter/Legal/A3/A4, portrait/landscape, margins, print areas, repeating header rows, percentage or fit-to-pages scaling, printed gridlines/headings and horizontal centering. Use Layout → Worksheet print layout and save as XLSX. Other worksheets, chart parts and formulas are preserved; existing repeat columns are retained. Invalid ranges and impossible margins are rejected. Pending changes cannot silently export to CSV.

84 source tests pass. Installed Excel recognized the settings and exported a four-page PDF with the header repeated on each page. Sparse worksheets also load correctly when empty placeholder cells lack style attributes.

The grid is not a print preview. Excel/LibreOffice rendering honors the native settings; built-in conversion is not claimed to reproduce Excel pagination. See the [batch report](https://github.com/Thatweirdguy1/Drunk-Peanuts/blob/main/docs/TABLES_PRINT_024.md). Full Office parity remains in progress.

### Downloads
- DrunkPeanuts-0.24.0-Setup.exe — Windows Desktop/Start menu installer.
- DrunkPeanuts-Windows-x64.zip — extract the whole portable folder.
- DrunkPeanuts-macOS-Apple-Silicon.zip and DrunkPeanuts-macOS-Intel.zip.
- SHA256SUMS.txt — download checksums.

Windows builds remain unsigned; macOS builds are not notarized.