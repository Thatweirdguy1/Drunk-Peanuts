# Drunk Peanuts 0.23.0 — Pages productivity

## Shipped controls

- **View → Document outline** (Ctrl+Alt+O): a docked heading list, using the document's Heading 1–3 styles. Filter headings by text; click or press Enter to jump to a section. The outline refreshes after body edits. Navigation does not modify the document. Imported supported DOCX headings appear too. This is a navigation pane, not a table-of-contents field.
- **Review → Document statistics**: counts words, characters, characters without whitespace and nonempty paragraphs in the body and current selection. Embedded image markers and header/footer text are excluded. Local word boundaries may differ from Word; physical page counts remain an export concern.
- **File → Document properties**: edit title, subject, author, keywords, description and category, up to 255 characters each. Values persist as native DOCX core properties and reload when opened. Cancel changes nothing. Pending property edits require DOCX when saving; unsupported text formats are refused rather than silently losing the edits. PDF export remains a body rendering and does not apply these DOCX-only properties.

Property-only edits preserve the original body XML, including unsupported fields/objects, and retain unedited properties. Imported originals still require a new destination. The existing rich-body safety guard still applies when changing an imported document containing unsupported content. These controls do not remove all metadata, revision history or personal information from a file.

## Verification

82 source tests pass. New tests cover property validation, native DOCX reload, preserving original body/fields/unedited properties, original-file protection, pending plain-text export refusal, heading filtering/jumping, non-mutating navigation, heading refresh and text statistics. Installed Word recognized the authored native properties and exported the synthetic document to PDF.

The neutral black/charcoal theme and small purple accents remain. Tracked changes, comments, proofing dictionaries, mail merge, full paginated editing and the other advanced features in the [Office queue](OFFICE_BATCHES.md) remain future batches.
