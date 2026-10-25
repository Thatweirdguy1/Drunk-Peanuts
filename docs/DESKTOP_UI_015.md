# Desktop inspection and UI revision — 25 October 2026

## Evidence used

REA's MCP tools were absent from this session. The installed REA 6.7.0 CLI worked without changing the user's configuration. Its doctor reported an aligned Codex registration; this did not establish an active MCP connection. Ghidra and Rizin were selected through environment variables limited to the analysis processes.

| Target / tool | Observation | Application to FreeConvert |
| --- | --- | --- |
| Installed Word, Computer Use | A blank document uses grouped file/edit/format commands, compact icons, font controls and a centered white editing surface. | Grouped icon toolbars and a paper canvas in Pages. Menu text and accessible action names remain available. No private documents were opened. |
| Installed Word executable, REA/Rizin | PE import inventory, evidence `ev_6860e0f1e05e7db3b9f1bf4b5962c86836547a5cea360a1aa17f9049502edf5d`. | Establishes the inspected native artifact's identity; imports alone do not explain Word's layout engine or ribbon implementation. |
| Installed LibreOffice, local configuration | Writer's shipped `standardbar.xml` and `textobjectbar.xml` separate file/export, clipboard, undo/redo and formatting groups. Its image packs provide a separate icon layer. | Reuse actions between icon toolbars and text menus; use consistent original vector icons. No LibreOffice icon artwork was copied. |
| Installed LibreOffice `soffice.bin`, REA/Rizin | PE import inventory, evidence `ev_8465711cc2e54e4cd0c974dc3224689c4ccd8d6dbb4a10ec83f3034da530057b`. | Bounded native inspection, not a reconstruction of LibreOffice. |
| Installed VLC, Computer Use | Video dominates the window; timeline and compact playback controls sit underneath. | Compact icon transport, optional playlist, separate advanced settings, preserved fullscreen shortcuts. |
| Installed `libvlc.dll`, REA/Ghidra 12.1.4 | x86-64 PE shared library; 815 analyzed procedures, 886 strings; evidence `ev_45854173f5876412297a56e0a8d56d6d3a627959cae5223b23a2597ce342022e`. | Confirms the native playback boundary and inspected build. This overview is static evidence, not execution or recovery of VLC's entire implementation. |
| Installed `libvlccore.dll`, REA/Rizin | Literal cache-related strings include `stale plugins cache: modified`, `plugins.dat`, and the description that the plugin cache improves startup time. Evidence `ev_750b3a709125eade7dd8afb1b175df5183df2f3ed8acea7697d4078433e4e9f9`. | Test whether the bundled cache matches the copied plugin files. |
| Bundled VLC, runtime experiment | Verbose startup logged many stale-cache errors and a recursive plugin-directory scan. | Regenerate the cache after PyInstaller copies plugins; use the prepared cache without scanning on Windows. |

Complete local REA records and the runtime logs are in `build/qa/word-imports.json`, `libreoffice-imports.json`, `vlc-ghidra.json`, `vlc-core-strings.json`, `vlc-bundled-startup.log`, and `vlc-cache-fixed.log`. `desktop-evidence-summary.json` records evidence IDs and inspected binary hashes. These are local build artifacts, not source dependencies.

JADX, Apktool and ADB were not used: the selected targets are native Windows applications, not Android packages or devices. No authentication, licensing, security controls or original application files were modified.

## Changes

- Pages, Tables, Dazzle, Sketch, Organize, Formulaic and Writer's Drafts now use consistent original vector icons for toolbar commands. Tooltips, accessible action names, text menus and existing shortcuts preserve discoverability. Icons remain independent of the third-party applications.
- Pages has a centered paper canvas, font family/size controls, alignment controls and grouped file, clipboard and formatting actions. New DOCX exports retain the supported font/alignment changes as well as inline formatting and bullets.
- Tables has a cell address and editable formula/value bar, clearer headers and alternating rows. Enter applies the value to the selected cell; the existing calculation command remains available.
- Dazzle displays its title/body editors on a white slide surface. Sketch exposes pen width. Formulaic separates source and preview.
- WatchIT uses icons for open, play/pause, stop, previous/next, fullscreen/restore, settings, playlist, mute and repeat. The playlist starts collapsed. Controls update their icons/tooltips with playback state.
- WatchIT's shell is created before starting the engine thread. Playback controls remain disabled with an explicit startup status until the engine is ready. Audio-device enumeration is available through Refresh devices rather than blocking initial construction.
- `prepare_vlc_runtime.py` regenerates the Windows VLC cache after packaging. The Windows release workflow invokes it before verification. The prepared Windows runtime skips the redundant plugin scan; the macOS startup path is unchanged.

## Measurements and limits

A warm-cache local engine initialization measured 0.3685 seconds before the cache correction and 0.0579 seconds after cache generation with plugin scanning disabled. These measurements used the same VLC build but different staged directories; they are not a controlled cold-disk benchmark and do not guarantee a fixed speedup on every computer.

The deferred WatchIT shell measured 0.0495 seconds to construct, show and process its first events in an offscreen source test. The first packaged check measured **1.0207 seconds for the visible shell** and **0.0901 seconds for engine initialization**, with playback controls enabled and libVLC 3.0.24. These exclude Python/process startup and are measurements on this machine, not universal timing guarantees. The packaged timing check exited successfully; the result is retained in `build/qa/watchit-packaged-timing.json`.

The source regression suite passed **53 tests in 31.800 seconds**, including queue/preview responsiveness, immediate player-window creation while initialization is blocked, icon availability/tooltips, formula-bar editing and previous data-preservation checks. A focused geometry check also verifies the 16:9 slide canvas. Qt test fixtures explicitly dispose native widgets before destroying their QApplication. Packaged native Office conversion passed.

This revision does not turn the Office tools into full Office replacements. Existing imported-document preservation rules, spreadsheet calculation limits and large-file profiling limits still apply. No Windows result establishes macOS behavior.

The final copied Windows executable matched the staged SHA-256 (`968bc59fa2f21e1a8f0e30214290fe23b45c7d68289285159efc54866512c797`). Its WatchIT window opened with enabled icon controls, decoded the synthetic 20-second MP4, advanced the timeline, entered F11 fullscreen and returned with Escape. Packaged OCR checks passed for the default, Cyrillic, Hindi, Korean and Arabic fixtures. The packaged timing self-check exited with code 0. A separate process monitor confirmed normal application shutdown with exit code 0 after opening Pages.
