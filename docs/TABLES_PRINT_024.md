# Drunk Peanuts 0.24.0 — Tables print layout

Use **Tables → Layout → Worksheet print layout** to set native XLSX print settings for the active worksheet:

- Letter, Legal, A3 or A4 paper, portrait or landscape.
- Percentage scaling (10–400%) or fit-to-pages width/height (0 means automatic).
- One or more print areas, such as `A1:F40, H1:J20`; blank uses the used cells.
- Repeating header rows, such as `1:2`; blank removes repeating rows. Existing repeating columns are preserved.
- Left/right/top/bottom margins in inches, printed gridlines, printed row/column headings and horizontal centering.

The dialog loads existing supported settings. Apply marks the workbook changed; Cancel leaves it unchanged. Save as XLSX to persist them. CSV export refuses pending print-layout changes. Only the active worksheet and its scoped print definitions are changed; other worksheets, formulas, charts, drawings and unrelated ZIP parts remain intact. Imported originals still require a new destination. Signed/duplicate-part workbooks are refused. Invalid/reversed/out-of-bounds ranges and margins leaving no printable area are rejected.

The grid is not a print preview. Excel/LibreOffice rendering uses the native saved settings; the built-in converter is not claimed to reproduce Excel pagination. This batch does not add a printer dialog or require Office for XLSX authoring. Microsoft Office and LibreOffice remain optional renderers. Loading sparse worksheets also now skips empty placeholder cells correctly instead of raising a formatting error.

## Verification

84 source tests pass. New checks cover native settings/reload, multiple print areas, preserving existing repeat columns, clearing repeat rows, percentage/fit modes, range/margin validation, CSV refusal, new workbooks and ribbon wiring. A workbook with formulas, a chart and a second sheet changed only its active-sheet XML and workbook print definitions; all other package parts stayed byte-identical.

Installed Excel recognized landscape Letter paper, `A1:D131`, repeating row 1, one-page-wide scaling and printed gridlines. It exported four PDF pages with the header repeated on every page. The native application was opened only for the synthetic fixture and closed without changing its source.

LibreOffice also exported the same saved XLSX to four PDF pages with the header repeated on every page, using the existing isolated-profile conversion helper.

All jobs in [the v0.24.0 build](https://github.com/Thatweirdguy1/Drunk-Peanuts/actions/runs/40308471479) passed on Windows x64, Apple Silicon and Intel macOS. Downloaded Windows installer and portable files matched the checksum manifest and GitHub asset digests. The extracted release passed Office/Play self-checks, native document conversion and actual video-frame decoding.

The release installer upgraded the Desktop app successfully. Its installed executable matched the downloaded portable release byte for byte; the Desktop shortcut opened 0.24.0. Installed Tables reopened the native workbook and displayed the saved paper, orientation, area, repeat rows, margins, scaling and gridline settings. The README print-layout screenshot is from this installed build.

Multiple-sheet authoring, structural/formula-aware edits, conditional formatting, validations, merged-cell authoring and pivot tools remain in the [Office queue](OFFICE_BATCHES.md).
