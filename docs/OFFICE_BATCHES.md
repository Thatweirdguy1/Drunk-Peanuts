# Office expansion: batches and verification

## 0.22.0 — presentation productivity

Native speaker notes with independent duplication and Undo/Redo, deck dimensions, presenting from beginning/current slide, first/last navigation and black-screen controls have shipped in this batch. Large UI surfaces now use neutral charcoal with small purple accents. See [native round trips, controls and limits](DAZZLE_BATCH_022.md).

## 0.21.2 — document headers and numbering

Pages header/footer text, native PAGE/NUMPAGES fields, first-page suppression and PDF counters shipped in [the document layout batch](DRUNK_PEANUTS_021.md). Other document-layout work below remains open.

## 0.20.1 — ribbon and core editing batch

The six Office workspaces (Pages, Tables, Dazzle, Sketch, Organize and Formulaic) now use a native tabbed ribbon. Existing commands remain connected to their original actions, including shortcuts, check states, file pickers and template menus. A quick-access row provides Save/Undo/Redo where available. Command search executes actual commands. Narrow windows scroll the groups horizontally; controls are not stacked over one another. The black/yellow identity remains.

The converter drop area has a separate expanding outline and soft background animation for pointer hover or a valid local-file drag. It resets on leave, drag cancellation, drop, hiding, disabling or window deactivation. Clicking it, Enter and Space open the existing file picker.

| Workspace | Added in this batch | Native output / checks |
| --- | --- | --- |
| Pages | Normal/Heading 1–3, numbering, line spacing, strike/super/subscript, highlight, clear formatting, find/replace, page setup (A4/Letter, orientation, margins), view zoom | DOCX paragraph styles, numbering, spacing, run formatting and section geometry; selected page setup also applies to PDF export. Replacement is a single undo operation and preserves images/tables. |
| Tables | Font selection, bold/italic/underline, text/fill colors, alignment and number formats; rectangular TSV copy/paste; column filter/show all and auto-fit | XLSX style edits append native font/fill/format records and update cells without rebuilding unrelated workbook parts. Blank formatted cells persist. CSV export refuses pending formatting loss. The grid shows raw values; numeric formats are used by Excel/LibreOffice. Filters and auto-fit are view controls. |
| Dazzle | Independent slide duplication, six slide-relative alignment commands, ribbon animation add/remove and fit-to-slide | Duplicated chart parts and embedded workbooks are independent. Image/video relationships, backgrounds and timing are retained. A selection bug that could edit the previously selected object was fixed. |
| Formulaic | Ribbon editing commands and fraction/root/power/subscript/Greek insertion | Existing formula source/MathML/export model remains in use. |
| Sketch / Organize | Ribbon organization and command search | Existing native canvas/database operations remain connected. |

## Evidence

- **Reference UI:** the user-supplied Microsoft 365 Word screenshot shows quick access, tabs, and Clipboard/Font/Paragraph/Styles/Editing groups. FreeConvert uses that organization with its own icons and branding.
- **REA/Rizin static observation:** read-only inspection of installed WINWORD.EXE identified PE64/x86-64, SHA-256 `0f96d6172dd6cc9eda5ddb786fee5d8f9c8b4bee96f56db2dab6f5888f3be882`; pre/post bytes were unchanged. This does not reveal or prove ribbon behavior.
- **REA/Ghidra historical observation:** the previous [0.19 investigation](OFFICE_FEATURES_019.md) recorded the LibreOffice launcher inspection. Repeating launcher decompilation would not establish editing behavior.
- **Installed LibreOffice resources:** Writer's `soffice.cfg/modules/swriter/ui/notebookbar.ui` contains Home font/paragraph commands and Insert/Review command groups. Its existing tabbed interface is a relevant native UI reference.
- **Native experiment:** generated DOCX/PPTX/XLSX files were reopened and exported through installed Word, PowerPoint and Excel. Word recognized the Heading 1 style; Excel recognized the bold header alongside the native chart and image. Tests additionally reopen native packages and verify layout/style data and independent chart values.
- **Packaged Windows checks:** Office/VLC self-checks, native conversion and OCR passed. Installed executable SHA-256 matches the staged build; the Desktop shortcut launched 0.20.1. Pointer hover and leave were observed in the installed app. The final 0.20.1 installer was downloaded from the successful release build; its installed executable matches the downloaded portable package. All three platform jobs passed, every published asset returned HTTP 200, and the downloaded Windows package passed native Office/conversion/playback checks with decoded video. A native DOCX was opened using Ctrl+O in the installed ribbon and captured for the README.
- **Source checks:** 76 tests passed. The five batch checks exercise drop hover reset and activation, ribbon commands/shortcuts/font-widget ownership, DOCX style/layout/find undo, XLSX styles/blank cells/unrelated-sheet preservation, and duplicated PPTX charts/alignment/animation removal.
- JADX, Apktool and ADB inspect Android artifacts/devices. No Android artifact is involved in this Windows UI work; they were not applied to Office executables.

References: [Microsoft ribbon customization](https://support.microsoft.com/en-us/office/foundations-experiences/customize-the-ribbon-in-office), [Word ribbon shortcuts and tab responsibilities](https://support.microsoft.com/en-us/accessibility/word/keyboard-shortcuts-in-word), [LibreOffice notebook bar](https://help.libreoffice.org/latest/en-US/text/shared/01/notebook_bar.html?DbPAR=SHARED).

## Remaining batches — not implemented by 0.20

Full Microsoft 365/LibreOffice feature parity is not complete. Only working commands are shown in this release. This is the implementation queue, not a list of shipped features:

| Batch | Features to implement | Required verification before shipping |
| --- | --- | --- |
| Document layout and references | True paginated editing, sections/columns, footnotes/endnotes, contents and citations, editable vector/text boxes, image positioning/wrapping | Save/reopen in Word and LibreOffice; page/section/reference structure retained; representative native PDF comparison. |
| Spreadsheet authoring | Multiple-sheet editing, broader formulas, range-aware structural edits/sort, tables, merged cells, validations, conditional formatting, workbook print layout, pivot analysis | Formula/range references update correctly; charts and unknown package parts survive; native Excel/Calc round trips. |
| Presentation authoring | Multi-object grouping/distribution, richer text layout, master/layout authoring, crops, editable chart styling, additional transitions and animation timelines, second-monitor presenter view | Independent native objects/media, correct timing/playback, undo and native PowerPoint/Impress round trips. |
| Review and productivity | Comments, tracked changes, proofing dictionaries, navigation, comparison, mail merge, accessibility review and document metadata tools | No silent loss of review data; offline fixtures and recovery checks; clear unsupported-format handling. |

Existing limits from the 0.19 report still apply: unsupported advanced slide objects are preserved rather than fully rendered; Pages charts/shapes are images and Pages/Tables video insertions are local links. Document page splitting/reordering currently targets PDFs. Signed macros, cloud collaboration and account services are separate systems, not implied by an Office-style layout.
