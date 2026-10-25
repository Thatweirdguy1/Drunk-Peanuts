## FreeConvert 0.16.0

This release brings the desktop usability repairs since 0.14.1 into a single update, with a Windows installer and a more compact local workspace.

### New and improved

- **Windows installation:** a per-user Setup executable, branded Desktop and Start menu shortcuts, an Installed apps entry and uninstaller. No Python installation or terminal is needed.
- **Open with:** WatchIT registers as an available audio/video handler. Opening a file queues playback until its engine is ready. Installation preserves your existing default player.
- **Compact interface:** 18px original vector icons across the Office Suite and WatchIT, slimmer controls, and a black/yellow cursive FreeConvert wordmark.
- **Clear conversion tools:** separate Convert, Reduce size, Create ZIP and Extract ZIP tabs; Shift+Enter converts the queue, while Shift-drop retains the quick-format menu.
- **11 Office starters:** reports, letters, meeting notes, budgets, task tracking, presentations, project updates, a drawing canvas, contacts, equations and a screenplay. Templates open as new files in separate workspaces; existing unsaved documents are preserved.
- **WatchIT:** the window appears while the playback engine loads; device enumeration is deferred, and Windows packaging regenerates VLC's plugin cache. Fullscreen supports F/F11, Escape and video double-click.
- **Editing and responsiveness:** clearer document/slide canvases, a spreadsheet formula bar, background previews, queue controls that follow worker state, safer SQLite record updates, corrected drawing coordinates and debounced live previews.

### Downloads

| Asset | Purpose |
| --- | --- |
| `FreeConvert-0.16.0-Setup.exe` | Recommended Windows x64 installer with Desktop/Start menu and file integration |
| `LocalFileConverter-Windows-x64.zip` | Portable Windows app; extract the whole folder |
| `LocalFileConverter-macOS-Apple-Silicon.zip` | macOS Apple Silicon app |
| `LocalFileConverter-macOS-Intel.zip` | macOS Intel app |
| `SHA256SUMS.txt` | SHA-256 checksums for the downloads |

FFmpeg, VLC playback plugins, OCR models and Office starters are bundled. Microsoft Office and LibreOffice remain optional installed applications for their document-rendering engines.

### Verification and limits

The Windows build was installed and launched from its Desktop shortcut. Tests covered conversion, OCR, Office modules, playback/fullscreen, template formatting and save, and preservation of existing data. The source suite contains 57 checks; platform-dependent checks may be skipped when their external dependency is unavailable. GitHub Actions also verifies the packaged builds before creating the release draft.

Windows binaries are **unsigned**; macOS apps are **not notarized**. The Office workspaces are focused editors rather than full Office replacements. OCR accuracy, media decoding and document layout depend on the input and available engines. See the [README](https://github.com/Thatweirdguy1/FreeConvert#readme), [desktop report](https://github.com/Thatweirdguy1/FreeConvert/blob/main/docs/DESKTOP_016.md), and [installation/signing guide](https://github.com/Thatweirdguy1/FreeConvert/blob/main/docs/WINDOWS_INSTALL_AND_SIGNING.md).
