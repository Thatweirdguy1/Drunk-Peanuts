# 0.33.0 — Dazzle authoring and presenter update

Imported timing edits/reordering, shaped masks and indefinite repeats; native freeform/boolean shapes and snapping; merged-table structure edits; eleven chart types and chart options; local comments, alt text and basic accessibility/reading-order checks; notes/handout printing; POTX/PPSX and optional LibreOffice ODP/PPT imports; synchronized presenter/audience windows, custom sequences, timed/kiosk looping, blackout, zoom and temporary ink.

PowerPoint and LibreOffice interoperability checks use synthetic files. Full PowerPoint parity remains incomplete; see docs/DAZZLE_033.md for exact limits. Physical dual-monitor operation has not been verified on this single-monitor laptop.

# 0.32.0 — Dazzle animation and authoring update

Animation pane, 25 effect types, native PPTX timing export, simultaneous playback, easing, triggers and motion paths; Fade/Push/Wipe/object Morph transitions; inline text, paragraph/frame controls, preset geometry, table grid editing and master/theme properties. DeckCraft and Apache POI notices are bundled.

This is an incremental independent-editor release, not full PowerPoint parity. See docs/DAZZLE_032.md for exact support and remaining work.

## Drunk Peanuts 0.31.2

Dazzle expands as an independent local presentation editor. Office is not required. File, Home, Text, Insert, Design, Arrange and Present tabs connect to the native PPTX model.

- Multi-selection, cut/copy/paste, independent duplication, grouping/ungrouping, align/distribute, keyboard nudge, picture crop and flips.
- Rich text, paragraph alignment, lists, connectors, safe hyperlinks, slide layouts and hidden slides.
- Notes/rehearsal presenter view with current/next previews and elapsed clock; PNG slide batches alongside PPTX/Dazzle/PDF.
- General rendering of cached SmartArt/icons, themes, master/layout artwork, gradients, groups, crops/flips and improved text inheritance/overflow.
- Independent chart/diagram copies; read-only previews; imported originals initially require Save as.

This is not full PowerPoint parity. Morph, arbitrary imported animation timelines, SmartArt layout generation, OLE/ActiveX, macros, 3D, recording, full master editing and some advanced styles/effects remain unsupported. See docs/DAZZLE_031.md. Private compatibility-check documents/images are not distributed.

### Validation

98 Python regression tests, frontend Node checks and real React/native suite checks. Release builds verify Windows x64 and macOS Intel/Apple Silicon, including native grouping and text formatting commands.

### Downloads

- DrunkPeanuts-0.31.2-Setup.exe — Windows installer.
- DrunkPeanuts-Windows-x64.zip — portable folder.
- DrunkPeanuts-macOS-Apple-Silicon.zip and DrunkPeanuts-macOS-Intel.zip.
- SHA256SUMS.txt — checksums.

Windows binaries remain unsigned and macOS builds unnotarized.
