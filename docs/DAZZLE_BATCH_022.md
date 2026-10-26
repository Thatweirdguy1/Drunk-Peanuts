# Drunk Peanuts 0.22.0 — neutral surfaces and presenting tools

Large panels, menus, toolbars and progress tracks use neutral black/charcoal. Yellow remains the main command color. Purple appears in the original logo, drop-area outline, keyboard focus, hover outline and selected text/cells rather than tinting the workspace background.

## Dazzle

- **View → Speaker notes:** edit the current slide's native notes body. Apply replaces the notes text/formatting, not the slide or other slides. Cancel leaves it unchanged. Notes save inside PPTX and Dazzle projects; they are intentionally absent from slide/PDF output. Duplicating a slide copies an independent native notes part. Notes edits support Undo/Redo.
- **Design → Slide size:** widescreen, standard, portrait or custom dimensions (1–56 inches). Applies to the whole deck. Shapes retain their position and dimensions; smaller canvases can leave shapes outside the slide. Undo restores the previous canvas.
- **Slide show → Present from beginning (F5)** and **Slideshow (Shift+F5)** from the current slide. During presentation, Home/End go to the first/last slide; B or period toggles a black screen; Escape exits. Existing arrow, click and on-click object animation controls remain available. Black-screen mode ignores navigation until it is dismissed.
- Existing animation actions now appear under **Animations** instead of Home.

## Evidence and scope

80 source tests pass. The new checks cover notes, independent duplication, Undo/Redo, PPTX/Dazzle reload, unchanged shape geometry after canvas resizing, invalid dimensions, ribbon commands and presentation navigation/blackout. Installed Microsoft PowerPoint read both authored notes bodies, recognized the widescreen dimensions (960 × 540 pt), and exported the synthetic two-slide deck to PDF. This uses native document automation; no proprietary Office code was copied.

All jobs in [the v0.22.0 release build](https://github.com/Thatweirdguy1/Drunk-Peanuts/actions/runs/40300028498) passed: Windows x64, Apple Silicon and Intel macOS, followed by release assembly. Downloaded Windows installer/portable files matched both the checksum file and GitHub asset digests. The extracted release passed Office/Play self-checks, native document round-trip conversion and actual video-frame decoding. Native PowerPoint PDF output was also checked to exclude speaker notes.

The downloaded installer upgraded the existing Desktop installation successfully. The installed executable matched the release ZIP byte for byte, launched from the Desktop shortcut, and displayed the neutral theme, new Animations tab and speaker-notes dialog. The README converter screenshot is from this installed release. All five public release downloads returned HTTP 200.

This is a bounded presentation batch. Master editing, advanced typography, multi-object grouping/distribution and a full animation timeline remain in the [Office queue](OFFICE_BATCHES.md). Speaker notes are plain text authoring; this release does not provide a second-monitor presenter view or notes-page PDF printing.
