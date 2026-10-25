## FreeConvert 0.18.0

The conversion panel now gives animated yellow hover feedback on **Convert, Reduce size, Create ZIP and Extract ZIP**, as well as enabled format dropdowns and buttons. Moving the pointer away clears the feedback immediately; hovering does not select another task. Disabled tools remain inactive until the selected file supports them. Animations follow the platform's animation preference, and keyboard focus remains visible.

### Included in this update

- **Play:** renamed from WatchIT across the interface and Windows Open with labels. The bundled VLC engine, playlist, fullscreen and keyboard controls remain available locally.
- **Black and yellow:** consistent application styling, compact original 18px icons and the FreeConvert cursive wordmark. Document paper keeps its actual print colors.
- **15 original Office starters:** Pages reports/letters/meeting notes, Tables budget/task tracker, six Dazzle decks, and starters for Sketch, Organize, Formulaic and Writer's Drafts.
- **Dazzle templates:** Presentation, Project update, Pitch deck, Research presentation, Lesson plan and Portfolio. Each editor has a Templates menu. PPTX, Dazzle project and PDF outputs retain the supported slide background and text colors.
- **Hover repairs:** toolbar buttons retain their animation state until Qt destroys them, preventing accumulated highlights. Feedback clears on pointer leave, disable, hide and window deactivation.
- **Fresh documentation:** new screenshots of the converter, Pages, Dazzle and Play, plus updated installation, template and workflow guidance.

### Downloads

| Asset | Purpose |
| --- | --- |
| `FreeConvert-0.18.0-Setup.exe` | Windows x64 installer with Desktop/Start menu shortcuts and media-file registration |
| `LocalFileConverter-Windows-x64.zip` | Portable Windows app; extract the entire folder |
| `LocalFileConverter-macOS-Apple-Silicon.zip` | macOS Apple Silicon app |
| `LocalFileConverter-macOS-Intel.zip` | macOS Intel app |
| `SHA256SUMS.txt` | SHA-256 checksums for the downloads |

FFmpeg, VLC playback plugins, OCR models and Office starters are bundled. Microsoft Office and LibreOffice are optional installed applications for their rendering engines. The original templates are MIT licensed; saving only requires write access to the destination folder.

### Verification and limits

The source suite has **62 tests**, including pointer movement between task tabs, unchanged task selection during hover, disabled tabs, clickable dropdowns, toolbar wrapper lifetime and animation cleanup. Platform-dependent checks may be skipped if their external dependency is unavailable. GitHub Actions checks source tests and packaged OCR, Office, playback and conversion on all three build targets before creating the release draft. Windows UI checks cover real pointer movement and launching from the Desktop shortcut; macOS UI was not manually exercised.

Windows binaries are **unsigned** and macOS builds are **not notarized**. These focused Office editors do not reproduce every feature or layout of Microsoft Office. OCR, media decoding and document fidelity depend on the input and available engines. See the [README](https://github.com/Thatweirdguy1/FreeConvert#readme), [verification report](https://github.com/Thatweirdguy1/FreeConvert/blob/main/docs/DESKTOP_018.md), and [installation/signing guide](https://github.com/Thatweirdguy1/FreeConvert/blob/main/docs/WINDOWS_INSTALL_AND_SIGNING.md).
