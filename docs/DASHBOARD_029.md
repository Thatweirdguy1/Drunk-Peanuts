# React Home — 0.29.2

The startup Home screen uses React, Tailwind CSS and Lucide icons, taking the Stitch dashboard's navigation / launch cards / tool grid / recent-file structure as inspiration. Black, yellow and purple, the original wordmark, labeled navigation, keyboard focus, reduced motion, local file dialogs, search and category filters are shared across the launcher.

The launcher connects to existing native tools rather than duplicating them. Convert opens the native queue; Pages, Tables, Dazzle, Sketch, Organize and Formulaic open their existing editors; Writer opens the screenplay editor; Play opens its existing local player with playlists, PiP and volume up to 200%. Home in the menu (Ctrl+Shift+H) returns from conversion without clearing the queue.

The UI and icons are built into `assets/dashboard`; Qt WebEngine renders them locally without a server. Qt WebChannel exposes an allowlisted set of workspace actions and native file dialogs. Recent-file opening accepts only previously selected paths. Network requests, unbundled local resources, popups and outside page navigation are blocked. Recent entries can be cleared without deleting source files. Empty installed sessions contain no fabricated files; browser-only previews label sample entries explicitly.

New source dependencies: Node 24 for building the React UI, and Qt WebEngine / WebChannel for rendering and bridging it. These runtimes and assets are bundled in release downloads. Installed users do not need Node or Python. Existing editor windows, conversion settings and Explorer launchers retain their native behavior.

## Checks

- 94 existing Python tests passed.
- The Node check covers tool search, category filtering and filename routing.
- `python app.py --dashboard-self-check` checks actual local React rendering, a DOM click through WebChannel into Pages, a temporary-image conversion queue, return to Home, recent-file clearing, outside-navigation rejection, logo loading and responsive bounds. It isolates recent-file settings in a temporary INI file.
- Release CI builds the React assets and runs the packaged dashboard check on Windows and both macOS targets alongside the existing OCR, native conversion, playlist and playback checks.

Only the Home screen has been converted to React. Editors and the player continue using their existing native Qt interfaces. File format limitations remain as documented in the main README.
