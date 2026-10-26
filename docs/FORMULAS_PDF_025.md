# Drunk Peanuts 0.25.0 — calculated cells and PDF content preservation

## Tables

Formula cells display calculated results by default: `=B2*C2` stays in the formula bar and cell editor while the grid displays `12.5`. Input edits trigger a short, debounced recalculation. Native XLSX and CSV saves retain the raw formulas, not painted result strings. Existing formatting survives formula-bar edits. Formula-derived numeric values also feed chart previews.

The **Formulas** tab adds **Recalculate (F9)**, **Show formulas** (view only) and **AutoSum (Alt+=)**. AutoSum accepts one selected column and writes below it only if the destination is empty. Number (`0.00`), grouped-decimal (`#,##0.00`) and percentage (`0.00%`) formats now display in the grid as well as saving in XLSX. Other imported/custom/date formats are retained but are not claimed to render fully in the grid.

The local evaluator supports arithmetic, absolute cell references, bounded ranges, SUM/AVERAGE/MIN/MAX/COUNT/COUNTA, IF/IFERROR, ROUND/ABS and AND/OR/NOT with simple comparisons. IF and IFERROR evaluate their branches lazily. Errors display as `#DIV/0!`, `#CYCLE!`, `#REF!`, `#NAME?`, `#VALUE!` or `#NUM!`, with the reason and original formula in a tooltip. Unsupported formulas are never silently replaced by zero or a stale cached Excel value.

This is a bounded local calculation subset, not the Excel engine. Named/cross-sheet/external references, array formulas, advanced functions and percentage operators are not implemented. Limits include 2,000 formula characters, 10,000 cells per range, dependency depth 100 and bounded calculation/numeric work. Excel may differ for less common type-coercion or precision cases. Raw formulas remain in the file for a full native spreadsheet application.

## PDF to DOCX

The previous default extracted selectable text only, which omitted image-based letterheads, graphics and signatures. The default now embeds each complete rendered PDF page into the DOCX, with native page dimensions and aspect ratio retained. This preserves visible headers and page graphics; **the page text is not editable**. The explicit alternative is labelled **Text only (drops images/layout)**. It extracts editable text and deliberately excludes those graphics. PDF-to-TXT behavior is unchanged. Existing PDF digital signatures are not transferred as cryptographic signatures into DOCX.

A user-supplied one-page PDF containing nine embedded images was verified locally: its source bytes remained unchanged, the preserved DOCX contains the complete page image, and LibreOffice rendered it back to one page. A corrected copy was saved separately in Downloads. Personal document content is excluded from repository screenshots and test fixtures.

## Verification

88 source tests pass. New checks cover painted results versus raw formulas, native formula save/reload, automatic dependent recalculation, formula-bar style preservation, chart results, view-only formula toggling, AutoSum overwrite refusal, error states, absolute references, lazy conditionals and rounding. A synthetic graphic-letterhead PDF is compared pixel-for-pixel with the embedded DOCX image; explicit text-only mode and original-source preservation are checked separately.

Nine synthetic arithmetic/aggregate/conditional/rounding/logical results were also compared against installed Excel and matched exactly for those cases. This validates the representative cases rather than asserting full Excel calculation parity.

All jobs in [the v0.25.0 build](https://github.com/Thatweirdguy1/Drunk-Peanuts/actions/runs/40352609081) passed on Windows x64, Apple Silicon and Intel macOS. Downloaded Windows files matched the checksum manifest and GitHub asset digests. The extracted release passed Office/Play self-checks, native document conversion and video-frame decoding. Its actual executable also converted the reported PDF to a complete-page DOCX without changing the source.

The release installer upgraded the Desktop app. Its installed executable matched the downloaded portable release byte for byte and opened through the Desktop shortcut as 0.25.0. Installed Tables reopened the synthetic XLSX and displayed `12.5` in D2 while retaining `=B2*C2` in the formula bar. The README screenshot is from this installed build. Unsaved edits in the separate source preview were preserved.

See the [remaining Office queue](OFFICE_BATCHES.md) for the next batches.
