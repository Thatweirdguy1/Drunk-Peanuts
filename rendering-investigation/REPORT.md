# Native PDF rendering investigation (Windows, 23 October 2026)

## Scope and evidence labels

This report distinguishes **documented** vendor behavior, **static** REA observations, **experiment** results from generated fixtures, and **inference**. No Frida tracing was needed: the documented COM and LibreOffice command-line interfaces exported the files. No native renderer was copied or reconstructed. These results describe this PC and these fixtures; they are not a guarantee for arbitrary files.

## Phase 1 — installed software and export interfaces

| Application | Installed executable and file version | PDF interface | Other relevant launch options |
| --- | --- | --- | --- |
| Word | `C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE`, `16.0.20430.20182` | COM `Document.SaveAs2(..., wdFormatPDF=17)` succeeded; `Document.ExportAsFixedFormat` is documented | Microsoft documents `/q`, `/safe`, `/t` and other startup switches; no general PDF CLI switch |
| Excel | `C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE`, `16.0.20430.20182` | COM `Workbook.ExportAsFixedFormat(xlTypePDF=0, path)` succeeded | Microsoft documents startup switches; use COM for PDF automation |
| PowerPoint | `C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE`, `16.0.20430.20182` | COM `Presentation.SaveAs(path, ppSaveAsPDF=32)` succeeded; `ExportAsFixedFormat` is documented | Microsoft documents `/B`, `/EMBEDDING`, `/M`, `/N` and other startup switches |
| LibreOffice | `C:\Program Files\LibreOffice\program\soffice.exe`, `26.8.1.1` | `soffice.com --headless --convert-to pdf --outdir ...`; UNO `XStorable.storeToURL` with PDF filter is documented | `--headless`, `--convert-to`, `--outdir`, `-env:UserInstallation` |
| Final Draft | No executable found in the checked Program Files locations or uninstall registrations | Vendor documents File > Save as PDF and Ctrl+Shift+P on Windows | No supported CLI or automation interface established in this investigation |

Sources: [Microsoft Office startup switches](https://support.microsoft.com/en-us/office/lifecycle/command-line-switches-for-microsoft-office-products), [Word SaveAs2](https://learn.microsoft.com/en-us/office/vba/api/word.saveas2), [Excel ExportAsFixedFormat](https://learn.microsoft.com/en-us/office/vba/api/excel.workbook.exportasfixedformat), [PowerPoint PDF format constant](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.ppsaveasfiletype), [PowerPoint ExportAsFixedFormat](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.presentation.exportasfixedformat), [LibreOffice startup parameters](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html), [UNO XStorable](https://api.libreoffice.org/docs/idl/ref/interfacecom_1_1sun_1_1star_1_1frame_1_1XStorable.html), [Final Draft PDF instructions](https://kb.finaldraft.com/hc/en-us/articles/27524968753428-How-do-I-save-my-Final-Draft-file-as-a-PDF).

## Phases 2–3 — fixtures and original-engine baselines

`make_fixtures.py` creates a DOCX with a DATE field, explicit page break, Cambria heading, table, image, header, and footer; an XLSX with formula, chart, print area, manual row break, header, and footer; a PPTX with Arial text, image, and two slides; and a long-dialogue FDX intended to provoke screenplay continuation. The FDX is **unvalidated** because Final Draft is absent. `export_office.ps1` exports with the installed Office apps. LibreOffice exports are in `lo-docx`, `lo-xlsx`, and `lo-pptx`. `measure.py` reads the PDFs and compares their first pages.

An initial Word `ExportAsFixedFormat` COM call stalled, so the successful Word baseline used documented `SaveAs2` PDF output. An initial PowerPoint `ExportAsFixedFormat` call failed through PowerShell COM argument binding; documented `SaveAs` with PDF format succeeded. The reproducible export script completed under PowerShell 7.6.5; an invocation under Windows PowerShell 5.1 stalled at Word COM on this PC. These are automation-call observations, not claims about either rendering engine.

## Phases 4–6 — static inspection and PDF comparison

**Static (REA/Ghidra):** `soffice.exe` is a PE64 executable (SHA-256 `3aeb1080d40bc82596f36ea4dd75019ab6aadad676e73d348c355396a464537a`). Its analyzed strings did not contain `pdf`; inspection of this launcher alone does not identify the PDF writer call path.

**Static (REA/Rizin):** LibreOffice's installed `mergedlo.dll` contains `vcl::pdf::PDFWriter` type names, including PDF form-widget types. This establishes that PDF writer code is present in that library; it does **not** prove which exact functions ran during our exports. The `soffice.exe` Rizin inspection also found no `pdf` import/string match. We did not trace Office's private internal DLL call graph or Final Draft binaries. No Frida runtime instrumentation was justified for the documented export route; function calls, registry/file reads, and subprocess stages therefore remain unobserved.

Run `python measure.py` for current metrics. The first completed comparison produced:

| Fixture | Native Office PDF | LibreOffice PDF | Observed difference |
| --- | --- | --- | --- |
| DOCX | 2 US Letter pages, Cambria, 280 extracted characters, 1 embedded PDF image | 2 US Letter pages, Cambria, 264 extracted characters, 2 embedded PDF images | DATE field formatted `10/23/2026` in Word and `10/23/26` in LibreOffice; 1.5% of first-page raster pixels differed |
| XLSX | 4 US Letter pages, Calibri, 136 extracted characters | 4 A4 pages, Calibri, 272 extracted characters | Page dimensions, text positions, and extracted content differed; the LibreOffice first-page header started around y=797.6 pt versus Excel y=745.4 pt |
| PPTX | 2 pages of 720×540 pt, ArialMT/Calibri, 1 embedded PDF image | 2 pages of 720×540 pt, ArialMT/Calibri, 2 embedded PDF images | Text position differed by about 0.4 pt; 0.7% of first-page raster pixels differed despite equal page count and dimensions |

PDF font names include subset prefixes, so a differing prefix alone is **not** font substitution. Both native and LibreOffice PDFs embedded Cambria, Calibri, and, for the slide, ArialMT as appropriate. Embedded image counts reflect PDF internals, not necessarily differing visible images. Different page dimensions make a raw pixel comparison of the XLSX invalid until page normalization is specified.

## Phase 7–9 — evidence table and decision

| Source document | Engine that supplies its native PDF baseline | Other engine | Evidence and limit |
| --- | --- | --- | --- |
| DOCX | Installed Word | LibreOffice Writer is approximate | Experiment: same count and paper size, different DATE field and pixels. Native means Word's output on this version, with installed fonts and export settings; cross-version byte identity is not promised. |
| XLSX | Installed Excel | LibreOffice Calc is approximate | Experiment: four pages each but Letter versus A4, altered positions and text extraction. Print settings must be aligned before any stronger fidelity claim. |
| PPTX | Installed PowerPoint | LibreOffice Impress is approximate | Experiment: same slide size/count, different pixel rendering. A matched image does not prove every animation, chart, or font is preserved. |
| ODF documents | Installed LibreOffice | Microsoft Office compatibility untested here | Inference: LibreOffice is the appropriate native baseline for its own formats; no ODF fixture was exported in this run. |
| FDX | Final Draft, if installed/licensed | App or other programs are approximate | Documented: Final Draft offers native Save as PDF. Experiment unavailable: no local installation and no Final Draft-exported baseline. Exact continuation and pagination cannot be claimed. |

**Implementation implication:** when the original desktop application is installed and the user chooses it, invoke its supported PDF export interface. Disclose that the external application and its license are required. If only LibreOffice is available, label conversion as compatibility output, not exact Microsoft/Final Draft rendering. Do not require purchase of Final Draft just to run the other tests; a user-supplied Final Draft PDF of the same FDX would enable the missing comparison.

## FreeConvert integration (v0.13.0)

The converter now exposes a per-file PDF renderer choice for supported Office inputs. Automatic prefers Word/Excel/PowerPoint for their OOXML files on Windows, then installed LibreOffice, then the built-in basic renderer. Explicit choices never silently fall back. Microsoft export uses COM on Windows; LibreOffice uses a temporary profile and `--headless --convert-to pdf`. Both write to a temporary PDF, validate that it has pages, then create the requested destination without replacing existing files. Neither external application is bundled. Final Draft has no automatic export integration because it is absent and a supported automation interface was not established; use its own Save as PDF command for the native screenplay baseline.

On this PC, calling FreeConvert's conversion function with the Microsoft renderer produced 2-page DOCX, 4-page XLSX, and 2-page PPTX PDFs from the fixtures. The LibreOffice renderer produced a 2-page DOCX PDF. The full source test suite passed with 36 tests. This checks routing and outputs, not arbitrary-document fidelity.

The Windows one-folder package was also built locally. Its renderer self-check, Microsoft Word PDF export, and LibreOffice Writer PDF export completed after applying PyInstaller's documented external-process DLL-search fix. The packaged conversions each produced a 2-page PDF from the DOCX fixture. See [PyInstaller's external-program guidance](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html) for the DLL search-path issue. macOS package behavior remains a GitHub Actions release check, not a local experiment.
