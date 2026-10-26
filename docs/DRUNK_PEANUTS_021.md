# Drunk Peanuts 0.21.2 - naming and document layout batch

The application is now **Drunk Peanuts**, in the renamed [Drunk-Peanuts repository](https://github.com/Thatweirdguy1/Drunk-Peanuts). The installer, Desktop/Start menu entries, window titles, media-player label, executable product metadata, release names and original logo use the new name. The shared UI uses black surfaces, purple panels/selection and yellow commands. The Microsoft 365-style tabbed ribbon remains across the six Office workspaces.

## Pages: headers, footers and page numbers

Use **Insert > Header**, **Footer**, or **Page numbers**. The dialog edits header/footer text, number location, alignment, starting number and first-page visibility. Visible bands preview the first page; DOCX/PDF exports contain the actual pagination.

- DOCX uses native header/footer stories and live `PAGE`/`NUMPAGES` fields, not literal page-number text. It applies the authored settings to all sections; later sections continue numbering.
- The first-page option creates a blank first-page story. Normal and even-page stories contain the authored content.
- Editing headers/footers replaces those stories in the saved copy, as explained in the dialog. Imported body XML stays intact if the body was not edited, including existing fields and images. Imported source documents require a new destination.
- Simple native headers/footers and authored page counters reload into the preview and PDF export. Existing stories are preserved during body editing unless header/footer changes are explicitly applied. Complex imported stories remain in DOCX; the basic preview does not interpret them.
- PDF export numbers the actual output pages and respects first-page suppression. Its basic overlay uses a standard PDF Latin font; use installed Word/LibreOffice conversion for complex-script typography and exact imported-document layout.
- TXT/HTML export refuses pending header/footer settings instead of silently dropping them.

## Verification

78 source checks pass. New tests cover native page fields, starting number, first-page stories, unchanged original/body XML, images, numbered three-page PDF output and plain-text export refusal. Installed Word recognized both fields, counted two pages and exported a PDF with the first header/footer hidden and `Page 2 of 2` on the second page.

REA/Ghidra 12.1.4 read the LibreOffice launcher (SHA-256 `3aeb1080d40bc82596f36ea4dd75019ab6aadad676e73d348c355396a464537a`), observing its defined `soffice` strings. REA/Rizin read the updated installed WINWORD.EXE as PE64/x86-64, SHA-256 `9be13b7adc7eda2d1b5256d7f392eb688c996a3cb0adf84bad8cb0ef9e5b871d`, without changing its bytes. These are static identity observations; the native document experiment establishes the header/footer behavior. No proprietary code was copied. Android-only tooling was not applied to Windows Office executables.

## Upgrade and scope

The installer retains the existing application identity so Windows treats this as an upgrade. Existing preference, screenplay-autosave and document/database identifiers are retained. Old installed FreeConvert shortcuts are replaced by Drunk Peanuts shortcuts. The internal `LocalFileConverter.exe` filename and media ProgID remain stable for compatibility; their displayed product/application names are Drunk Peanuts. macOS bundles use DrunkPeanuts.app.

This batch completes header/footer/page-number authoring. Full Office parity is still in progress: true paginated editing, advanced reference/review tools, richer spreadsheets and presentation timelines remain in the [feature queue](OFFICE_BATCHES.md). The app does not expose placeholders for unfinished features.
