## Drunk Peanuts 0.29.1

A new Home screen brings Convert, Create and Play into one local creative workspace. The React UI uses Tailwind CSS and Lucide icons with the original wordmark, black/yellow/purple identity, a collapsible navigation rail, tool search, category filters and recent local files.

Buttons open the existing native tools: conversion, Pages, Tables, Dazzle, Sketch, Organize, Formulaic, Writer and Play. Native file dialogs and drag/drop add files without uploads. Home in the menu or Ctrl+Shift+H returns from the converter without clearing its queue. The installed app contains the built UI and Qt WebEngine runtime; no Node, server or network connection is required.

The Home bridge blocks outside navigation and network resources, and only reopens previously selected local paths. Recent-list clearing forgets paths without deleting files. Native editors, file-format limits, save protections, playlists, PiP and the 200% volume control retain their existing behavior.

### Checks

94 Python regression tests, the dashboard's Node check and the actual React/native bridge self-check pass locally. Release builds run packaged dashboard, OCR, native conversion, playlist and playback checks on Windows x64, macOS Intel and Apple Silicon. See docs/DASHBOARD_029.md for scope and verification.

### Downloads

- DrunkPeanuts-0.29.1-Setup.exe — Windows installer.
- DrunkPeanuts-Windows-x64.zip — complete portable folder.
- DrunkPeanuts-macOS-Apple-Silicon.zip and DrunkPeanuts-macOS-Intel.zip.
- SHA256SUMS.txt — checksums.

The Home screen uses React; the editors and player remain native Qt workspaces. Windows binaries remain unsigned and macOS builds unnotarized.
