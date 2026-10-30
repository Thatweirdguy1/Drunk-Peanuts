# Drunk Peanuts. dashboard

React Home screen inspired by [the Stitch dashboard](https://stitch.withgoogle.com/projects/8925735609446928643). Tailwind CSS handles layout and tokens; Lucide provides inline SVG icons. The original wordmark is in `public/logo.png`. Everything is bundled locally; there are no remote fonts, CDNs, accounts, or upload endpoints.

```sh
npm ci
npm test
npm run build
```

The build writes to `../assets/dashboard`, which the desktop package includes. Run `python app.py` from the repository root to open the integrated launcher. Node is needed only to develop/build the UI, not by users of the installed app.

`npm run dev` starts a browser preview. That preview clearly labels sample recent files and explains that native tools are available in the desktop app; it does not pretend to convert or edit files.

Components: `Sidebar`, `LaunchCards`, `ToolGrid`, `RecentFiles`, and the shared `ToolIcon`. `App.jsx` owns search/filter state and the Qt bridge connection. `data.js` contains the tool catalog. The native bridge in `../desktop_dashboard.py` reuses the existing conversion queue, Office workspaces, screenplay editor and Play. Its off-the-record WebEngine view only loads bundled resources and blocks outside navigation.

Use Home in the native menu, or Ctrl+Shift+H, to return from the converter. Workspaces open in their existing separate windows and keep their existing save and close protections. Recent files record only files explicitly chosen/dropped through Home, up to 12 paths; Clear list forgets those paths without deleting files.

Verification: `python app.py --dashboard-self-check` renders the actual built React UI, checks the bridge by opening Pages, queues a temporary image, checks Home return/recent files, rejects outside navigation, and checks layouts at 1280×720 and 1440×900.
