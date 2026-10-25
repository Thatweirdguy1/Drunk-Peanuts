# FreeConvert usability audit — 24 October 2026

The starting app was the running Windows download, version 0.14.1. Its maximized main window visibly overlapped conversion, size-reduction and tool controls. Its accessibility tree exposed only the window/title bar to Computer Use; the source-run app exposed its controls normally. Input to the original packaged window did not produce a verified response, so no cause is assigned to that difference.

## Problems found and repaired in 0.14.2

| Feature | Problem | Repair |
| --- | --- | --- |
| Main window | Minimum heights exceeded the available screen height and squeezed rows into one another. | Keep conversion controls in their own bottom panel; scroll the upper content when needed. Verify button bounds and intersections at 760×540, 1080×830 and 1536×864. |
| Navigation | Eight workspace buttons occupied an inflexible row. | Use Qt's toolbar overflow, with consistent spacing. |
| Queue | The large empty drop area continued consuming space with files loaded. | Hide empty-state content once files are queued; restore it on clearing the queue. |
| Queue | There was no way to remove just one unwanted file. | Add Remove selected. This removes a queue entry and never deletes the source file. |
| Output folder | A long path could force the other controls off-screen. | Give the folder its own shrinking row and expose its full path in a tooltip. |
| Idle controls | Conversion/tool buttons appeared enabled on startup with no files. | Initialize and update enabled states from queue contents. |
| Batch completion | Completion was signalled before the thread stopped; controls could remain disabled afterward. | Refresh again on the thread's finished signal. |
| Active conversion | Changing options/closing during a worker could cause inconsistent state or destroy a running thread. | Lock relevant settings and queue controls while working; reject closing until work finishes. |
| Previews | Image decoding/PDF rendering ran on the UI thread. | Use one background preview worker, coalescing subsequent selections and ignoring results for other files. Create QPixmap only on the UI thread. |
| PDF previews | Rendering at a fixed scale could allocate an unnecessarily large bitmap. | Bound rendering to the thumbnail dimensions; close bitmap/page/document resources. |
| PDF concurrency | Background previews and conversions could enter PDFium concurrently. | Serialize PDFium access. PDF rendering throughput is deliberately limited within one process. |
| Startup | OCR and RAW libraries loaded before those features were requested. | Load those libraries when the relevant operation starts. No numerical startup-speed claim is made. |
| Format defaults | MP4 defaulted to AAC when MP4 was excluded as the same format; spreadsheets were classified as documents. | Prefer another video format for video inputs and identify spreadsheet formats correctly. |
| Bad input | Damaged image files could raise during queue admission. | Reject unreadable inputs rather than letting the exception escape the add-files flow. |
| WatchIT fullscreen | Fullscreen expanded the whole crowded window; there was no Escape handler or video double-click handler. | F/F11 or video double-click enters/exits; Escape exits; hide playlist/settings, then hide transport controls after inactivity. Mouse movement restores controls. Preserve the previous maximized/windowed state. |
| WatchIT layout | All track/device/sync settings competed with the video and transport. | Put advanced playback options in a separate resizable window with a scrollable form. A packaged visual check caught and replaced an intermediate settings panel that was too cramped. |
| WatchIT input | VLC could intercept keyboard/mouse input inside its video output. | Disable VLC's own key/mouse handling so the Qt player handles shortcuts. |
| WatchIT feedback | Play/Pause and Mute labels did not reflect state; Stop left the timeline at its previous position. | Reflect play/mute state and reset the timeline on Stop. |
| WatchIT playback | Missing files and decoder errors had no useful feedback; track discovery depended only on a fixed delay. | Report missing files/playback errors and refresh tracks when playback enters Playing. |
| WatchIT lifecycle | A hidden player kept its refresh timer running. | Stop its timer on close and restart it on reopening. |
| WatchIT startup | First playback-engine initialization briefly made the copied packaged app stop responding. | Initialize VLC in a background loader and report startup progress while the converter remains usable. A blocked-engine regression check verifies that the event loop still runs. |
| Tables | Added columns had no spreadsheet labels beyond Z; structural edits did not mark the document dirty. | Generate AA, AB, etc.; mark row/column additions as edits. |
| Tables loading | Each populated cell emitted edit notifications and could repaint. | Block change signals and painting during grid population. |
| Office workspaces | Common file/edit keyboard shortcuts were absent. | Add Ctrl+N/O/S, Ctrl+Shift+S and applicable bold/italic/underline shortcuts. |
| Pages | New DOCX exports flattened bold, italic, underline and bullets to plain paragraphs. | Preserve those supported rich-text features when creating a DOCX. |
| Sketch | Large images were clipped instead of fitted to the window; a click alone did not draw a dot. | Fit the complete image, map input back to image coordinates and draw click dots. |
| Sketch internals | The pen-width integer shadowed QWidget.width(). | Rename it to pen_width. |
| Organize — data loss | Saving deleted the whole table and reinserted only the first 1,000 displayed records. | Save individual updates/inserts/deletions by row identity. Records beyond the displayed limit remain intact. Preserve unchanged NULL/numeric values. |
| Organize — data loss | Switching tables discarded unsaved edits. | Ask before switching; restore the original selection when declined. |
| Organize conflicts | External changes could be silently overwritten. | Compare loaded records inside a write transaction and refuse a stale save. |
| Organize table selection | Creating a table selected the last alphabetical entry, which might be a different table. | Select the table that was actually created. |
| Writer's Drafts | Toolbar rows could be squeezed; preview updates reset reading position. | Use native toolbar overflow and restore the preview scroll position. |
| Writer's Drafts performance | Each preview rendered the entire draft, including very large imports. | Bound live preview/scene navigation to the first 150,000 characters, with an explicit notice. Saving/exporting retains the complete draft. |
| Writer's Drafts feedback | Status said autosaved before the autosave succeeded; closed windows kept timers active. | Show pending until a successful write; stop timers on close and resume them when reopened. |
| Formulaic | Every keystroke immediately rebuilt the preview. | Debounce preview refresh by 200 ms. |

## Verification

The original 43-test suite passed before edits. The final expanded suite passed **52 tests in 32.687 seconds**. It uses temporary files and databases, synthetic images/media, real conversion round trips, and mocked VLC state for portable UI regression checks. Checks deliberately block preview and playback-engine startup workers and verify that an event-loop heartbeat still runs; stale preview results are ignored.

The Windows 0.14.2 executable was rebuilt with PyInstaller. Packaged Office/VLC self-checks, native conversion and OCR checks passed, including dedicated Cyrillic, Hindi, Korean and Arabic OCR fixtures. The packaged main window exposed its controls through accessibility and displayed the bottom action panel without the original overlaps. A generated 20-second H.264 clip played in packaged WatchIT, advanced its timeline and displayed video in F11 fullscreen. These checks do not establish compatibility with arbitrary user files or other operating systems.

Run from the project directory:

```powershell
.\.venv\Scripts\python.exe -m unittest -q
```

## Remaining limits and scope

- This is a bounded audit of the current Windows app, source flows and regression suite; it does not prove every codec, document, device, display scale or operating system works.
- The Office tools remain focused editors. They do not provide full spreadsheet calculation, advanced page layout or a complete slide-design/presentation application. Imported Office content retains the existing preservation/refusal rules. New DOCX export now retains supported inline formatting and bullets; this is not a complete rich-text-to-Word layout converter.
- Large spreadsheet/Office imports and exports still do synchronous work in their workspace. Background conversion and previews are covered; those editor operations need separate realistic large-file profiling before claiming all lag is eliminated.
- Organize displays at most 1,000 records. Saving no longer removes records beyond that limit; paging/filtering is not implemented.
- Writer's Drafts live preview and its scene list stop at 150,000 characters. Export includes the full draft.
- WatchIT uses VLC's available codecs/devices. Seek, track, aspect and sync behavior can vary with the input and playback backend. A synthetic clip does not establish compatibility with every real media file.
- The existing conversion timeouts/cancellation model remains: work is allowed to finish, and closing is blocked while it runs. There is no new cancel-job control.
- The original downloaded app and unrelated untracked project folders are preserved. The repaired executable is delivered separately.
