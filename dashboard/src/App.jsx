import { useEffect, useRef, useState } from "react";
import {
  Search,
  FolderOpen,
  ArrowUpRight,
  HardDrive,
  X,
  Keyboard,
} from "lucide-react";
import Sidebar from "./components/Sidebar";
import LaunchCards from "./components/LaunchCards";
import ToolGrid from "./components/ToolGrid";
import RecentFiles from "./components/RecentFiles";
import { tools, sampleFiles, toolForFile } from "./data";

export default function App() {
  const [collapsed, setCollapsed] = useState(false);
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState("All");
  const [files, setFiles] = useState([]);
  const [dialog, setDialog] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [bridge, setBridge] = useState(null);
  const [status, setStatus] = useState("Ready when you are.");
  const input = useRef(null);
  const search = useRef(null);
  const fileMode = useRef("convert");

  useEffect(() => {
    if (!window.qt?.webChannelTransport) {
      setFiles(sampleFiles);
      return;
    }
    const script = document.createElement("script");
    script.src = "qrc:///qtwebchannel/qwebchannel.js";
    script.onload = () =>
      new window.QWebChannel(window.qt.webChannelTransport, (channel) => {
        const native = channel.objects.desktop;
        native.stateChanged.connect((payload) => {
          const state = JSON.parse(payload);
          setFiles(state.files);
          setStatus(state.status);
        });
        setBridge(native);
        native.ready();
      });
    script.onerror = () =>
      setStatus(
        "Could not connect to the desktop tools. Reopen Home from the File menu.",
      );
    document.head.appendChild(script);
    return () => script.remove();
  }, []);

  useEffect(() => {
    const shortcut = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        search.current?.focus();
      }
      if (event.key === "Escape") {
        setQuery("");
        setDragging(false);
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);

  function launch(id) {
    if (bridge) {
      bridge.launch(id);
      return;
    }
    setDialog({
      title: tools.find((t) => t.id === id)?.name,
      message:
        "This browser preview shows the dashboard. In the installed desktop app, this opens the existing native workspace.",
    });
  }
  function choose(mode = "convert") {
    if (bridge) {
      bridge.chooseFiles(mode);
      return;
    }
    fileMode.current = mode;
    input.current.accept = mode === "play" ? "audio/*,video/*" : "";
    input.current.click();
  }
  function addBrowserFiles(selected) {
    const items = Array.from(selected).map((file, index) => ({
      id: `${Date.now()}-${index}`,
      name: file.name,
      size: `${(file.size / 1024 / 1024).toFixed(1)} MB`,
      tool: fileMode.current === "play" ? "play" : toolForFile(file.name),
      modified: "Just now",
    }));
    setFiles((current) =>
      [...items, ...current.filter((f) => !f.sample)].slice(0, 12),
    );
    setStatus(
      `${items.length} local file${items.length === 1 ? "" : "s"} selected. Preview only — no files changed.`,
    );
  }
  function openFile(file) {
    if (bridge) bridge.openRecent(file.id);
    else
      setDialog({
        title: file.name,
        message:
          "File opening is connected to the native editors in the desktop app. This preview does not modify or convert your files.",
      });
  }
  return (
    <div className="flex h-dvh min-h-0 flex-col bg-base text-ink">
      <a href="#workspace" className="skip-link">
        Skip to workspace
      </a>
      <div className="flex min-h-0 flex-1">
        <Sidebar
          collapsed={collapsed}
          onCollapse={() => setCollapsed((v) => !v)}
          onLaunch={launch}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-line px-5 lg:px-8">
            <div className="flex items-center gap-2 text-xs">
              <span className="text-muted">Workspace</span>
              <span className="text-muted/50">/</span>
              <span>Home</span>
            </div>
            <div className="flex items-center gap-4">
              <span className="hidden items-center gap-2 text-[11px] text-muted sm:flex">
                <span className="size-1.5 rounded-full bg-purple-light" />
                Free. Offline. Yours.
              </span>
              <span className="h-4 w-px bg-line" />
              <button
                onClick={() => choose("open")}
                className="flex items-center gap-2 rounded-md py-2 text-xs hover:text-purple-light"
              >
                <FolderOpen size={15} />
                Open file
                <ArrowUpRight size={13} />
              </button>
            </div>
          </header>
          <main
            id="workspace"
            tabIndex={-1}
            className="min-h-0 flex-1 overflow-y-auto px-5 py-7 lg:px-8 xl:px-10"
          >
            <div className="mx-auto max-w-[1520px] space-y-5">
              <section className="flex flex-wrap items-end justify-between gap-5">
                <div>
                  <p className="eyebrow mb-2 text-muted">
                    A LITTLE ROOM FOR BIG IDEAS
                  </p>
                  <h1 className="display text-3xl font-semibold tracking-[-.045em] lg:text-[38px]">
                    What are we making<span className="text-yellow">?</span>
                  </h1>
                  <p className="mt-2 text-xs text-muted">
                    A fresh start, a final draft, or something in between.
                  </p>
                </div>
                <label className="flex h-10 w-full max-w-72 items-center gap-2.5 rounded-lg border border-line bg-panel px-3 focus-within:border-purple">
                  <Search size={16} className="text-muted" />
                  <span className="sr-only">Search tools</span>
                  <input
                    ref={search}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Find your tool…"
                    className="min-w-0 flex-1 bg-transparent text-xs outline-none"
                  />
                  <kbd className="rounded border border-line px-1.5 py-0.5 text-[10px] text-muted">
                    ⌘ / Ctrl K
                  </kbd>
                </label>
              </section>
              <LaunchCards
                onChoose={choose}
                onLaunch={launch}
                dragging={dragging}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={(e) => {
                  if (!e.currentTarget.contains(e.relatedTarget))
                    setDragging(false);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  fileMode.current = "convert";
                  if (!bridge) addBrowserFiles(e.dataTransfer.files);
                }}
              />
              <ToolGrid
                query={query}
                group={group}
                onGroup={setGroup}
                onLaunch={launch}
              />
              <RecentFiles
                files={files}
                onOpen={openFile}
                onChoose={choose}
                onClear={() => (bridge ? bridge.clearRecent() : setFiles([]))}
              />
              <div className="flex flex-wrap items-center justify-between gap-3 pb-1 text-[11px] text-muted">
                <p>Made for the work. And the person making it.</p>
                <span className="flex items-center gap-1.5">
                  <Keyboard size={14} />
                  Tab to explore · Enter to open
                </span>
              </div>
            </div>
          </main>
        </div>
      </div>
      <footer className="flex min-h-8 shrink-0 items-center justify-between gap-3 border-t border-line bg-panel px-4 text-[10px] text-muted">
        <span className="flex min-w-0 items-center gap-2" role="status">
          <span className="size-1.5 shrink-0 rounded-full bg-green-400" />
          <span className="truncate">{status}</span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          <HardDrive size={12} />
          {bridge ? "Local workspace" : "Dashboard preview"}
        </span>
      </footer>
      <input
        ref={input}
        type="file"
        multiple
        hidden
        onChange={(e) => {
          addBrowserFiles(e.target.files);
          e.target.value = "";
        }}
      />
      {dialog && (
        <PreviewDialog dialog={dialog} onClose={() => setDialog(null)} />
      )}
    </div>
  );
}

function PreviewDialog({ dialog, onClose }) {
  const ref = useRef(null);
  useEffect(() => {
    const element = ref.current;
    element.showModal();
    return () => element.close();
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="m-auto w-[min(440px,90vw)] rounded-2xl border border-line bg-panel p-6 text-ink shadow-2xl backdrop:bg-black/65"
    >
      <div className="flex items-center justify-between gap-4">
        <h2 className="display text-xl font-semibold">{dialog.title}</h2>
        <button
          autoFocus
          onClick={onClose}
          aria-label="Close dialog"
          className="grid size-9 shrink-0 place-items-center rounded-lg hover:bg-surface"
        >
          <X size={18} />
        </button>
      </div>
      <p className="mt-4 text-sm leading-relaxed text-muted">
        {dialog.message}
      </p>
      <button onClick={onClose} className="button-primary mt-6">
        Back to workspace
      </button>
    </dialog>
  );
}
