import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  FilePlus2,
  FolderOpen,
  Save,
  PanelLeft,
  Check,
  Circle,
  HardDrive,
  Film,
  Database,
  ListTree,
} from "lucide-react";
import Sidebar from "./components/Sidebar";
import SlideThumbnail from "./components/SlideThumbnail";
import WorkspaceToolbar, { CommandButton } from "./components/WorkspaceToolbar";
import PlayerControls, { Playlist } from "./components/PlayerControls";
import { tools } from "./data";

const tool = new URLSearchParams(location.search).get("workspace");
const names = {
  pages: "Pages",
  tables: "Tables",
  dazzle: "Dazzle",
  organize: "Organize",
  sketch: "Sketch",
  formulaic: "Formulaic",
  writer: "Writer",
  play: "Play",
};
const subtitles = {
  pages: "A little space to put it into words.",
  tables: "Everything adds up here.",
  dazzle: "Give your ideas the big screen.",
  organize: "A place for every detail.",
  sketch: "Follow the line.",
  formulaic: "Make the complex clear.",
  writer: "Every scene starts somewhere.",
  play: "Press play. Stay a while.",
};
const previewNames = {
  pages: "Harbor field notes.docx",
  tables: "Shoot budget.xlsx",
  dazzle: "Before the city wakes.pptx",
  organize: "Production.sqlite",
  sketch: "Harbor study.png",
  formulaic: "Field equations.formulaic",
  writer: "Before the city wakes.fountain",
  play: "Harbor-at-dawn.mp4",
};
function initial() {
  return {
    name: previewNames[tool],
    native: false,
    dirty: false,
    actions: [],
    items:
      tool === "play"
        ? ["Harbor-at-dawn.mp4", "Studio-session.wav", "Night-train.mp4"]
        : tool === "dazzle"
          ? [
              "Before the city wakes",
              "A city in transition",
              "Finding the story",
              "The people",
              "Next steps",
            ]
          : tool === "organize"
            ? ["Contacts", "Locations", "Equipment"]
            : tool === "writer"
              ? ["EXT. HARBOR — DAWN", "INT. TRAIN — MORNING"]
              : [],
    current: 0,
  };
}

function PreviewCanvas() {
  if (tool === "tables" || tool === "organize")
    return (
      <div className="h-full overflow-auto bg-[#17171e] p-3">
        <table className="preview-grid">
          <thead>
            <tr>
              {(tool === "tables"
                ? [
                    "",
                    "A · Item",
                    "B · Quantity",
                    "C · Rate",
                    "D · Notes",
                    "E · Cost",
                  ]
                : ["ID", "Name", "Role", "Location", "Email"]
              ).map((t) => (
                <th key={t}>{t}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(tool === "tables"
              ? [
                  ["1", "Camera rental", 1, 300, "Daily rate", "300.00"],
                  ["2", "Sound kit", 1, 90, "Daily rate", "90.00"],
                  ["3", "Transport", 2, 60, "Return trips", "120.00"],
                  ["4", "Meals", 6, 15, "Crew", "90.00"],
                  ["5", "Location permit", 1, 200, "North pier", "200.00"],
                  ["6", "Props", 1, 50, "Market supplies", "50.00"],
                  ["7", "TOTAL", "", "", "=SUM(E1:E6)", "850.00"],
                ]
              : [
                  [
                    1,
                    "Maya Sen",
                    "Director",
                    "North pier",
                    "maya@example.test",
                  ],
                  [2, "Arun Rao", "Sound", "Old station", "arun@example.test"],
                  [3, "Nia Das", "Producer", "Studio B", "nia@example.test"],
                ]
            ).map((row, i) => (
              <tr key={i}>
                {row.map((v, j) => (
                  <td key={j} className={i === 6 && j === 5 ? "selected" : ""}>
                    {v}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  if (tool === "play")
    return (
      <div className="flex h-full items-center justify-center bg-black">
        <div className="text-center">
          <Film
            size={64}
            strokeWidth={1}
            className="mx-auto mb-5 text-purple-light"
          />
          <p className="text-xl">Your local cinema</p>
          <p className="mt-3 text-xs text-muted">
            Desktop preview · Local video appears here
          </p>
        </div>
      </div>
    );
  if (tool === "formulaic")
    return (
      <div className="grid h-full grid-cols-2 gap-px bg-line">
        <div className="bg-base p-8 font-mono text-sm text-purple-light">
          # Motion at first light
          <br />
          <br />v = u + a t<br />s = u t + 1/2 a t^2
          <br />
          <br />
          sqrt(a^2 + b^2)
        </div>
        <div className="flex items-center justify-center bg-panel text-3xl">
          v = u + at
        </div>
      </div>
    );
  if (tool === "dazzle")
    return (
      <div className="flex h-full items-center justify-center p-10">
        <div className="aspect-video w-full max-w-4xl bg-[#ece9df] p-12 text-[#172e3f]">
          <p className="text-xs tracking-[.2em]">A DOCUMENTARY IN THE MAKING</p>
          <h2 className="display mt-10 max-w-md text-5xl font-bold">
            Before the
            <br />
            city wakes
          </h2>
          <p className="mt-6 text-sm">
            Small stories. First light. A different perspective.
          </p>
          <div className="mt-10 h-2 w-20 bg-[#6a9ca5]" />
        </div>
      </div>
    );
  if (tool === "sketch")
    return (
      <div className="flex h-full items-center justify-center p-10">
        <div className="flex aspect-[3/2] max-h-full w-full items-center justify-center bg-[#f7f4ed]">
          <svg viewBox="0 0 600 400" className="h-full max-h-full">
            <path
              d="M70 290 Q180 250 270 280 T540 270 M70 310 Q180 270 270 300 T540 290 M120 270 L170 170 L310 170 L360 270 Z M240 170 L240 90 L310 170 M380 270 L410 205 L510 205 L540 270 Z"
              fill="none"
              stroke="#424754"
              strokeWidth="3"
              strokeLinecap="round"
            />
            <circle cx="450" cy="100" r="38" fill="#dbc7ee" />
          </svg>
        </div>
      </div>
    );
  return (
    <div className="h-full overflow-y-auto p-8">
      <article
        className={`preview-paper ${tool === "writer" ? "font-mono" : ""}`}
      >
        {tool === "writer" ? (
          <>
            <p>EXT. HARBOR — DAWN</p>
            <p>
              The city is still asleep. MAYA stands by the railing, a battered
              recorder in her hand.
            </p>
            <p className="mt-8 text-center">ARUN</p>
            <p className="mx-auto max-w-xs">
              You always get here before the light.
            </p>
            <p className="mt-8 text-center">MAYA</p>
            <p className="mx-auto max-w-xs">Someone has to hear it wake up.</p>
            <p className="mt-8">A distant train sounds. She presses RECORD.</p>
          </>
        ) : (
          <>
            <p className="text-xs tracking-[.18em] text-[#6b6575]">
              FIELD NOTES / 06
            </p>
            <h1 className="display my-6 text-4xl font-bold">
              A quieter kind
              <br />
              of morning
            </h1>
            <p>North pier · 05:40 AM</p>
            <div className="my-7 flex h-36 items-end bg-[#bbc6c7] p-5 text-[#344953]">
              NORTH PIER — FIRST LIGHT
            </div>
            <h2 className="my-5 text-xl font-semibold">Location notes</h2>
            <p>
              The pier is quiet at first light. Fishing boats move across the
              water while the city finds its rhythm.
            </p>
            <h2 className="my-5 text-xl font-semibold">Light & atmosphere</h2>
            <p>Keep the camera low. Let the morning arrive in its own time.</p>
          </>
        )}
      </article>
    </div>
  );
}

export default function Workspace() {
  const [state, setState] = useState(initial);
  const [bridge, setBridge] = useState(null);
  const [collapsed, setCollapsed] = useState(true);
  const [rail, setRail] = useState(true);
  const [playlist, setPlaylist] = useState(true);
  const [notice, setNotice] = useState("");
  const [commandsOpen, setCommandsOpen] = useState(false);
  const canvas = useRef(null);
  const playerOverlay = useRef(null);
  const keyboardNavigation = useRef(false);
  useEffect(() => {
    if (!window.qt?.webChannelTransport) return;
    const script = document.createElement("script");
    script.src = "qrc:///qtwebchannel/qwebchannel.js";
    script.onload = () =>
      new window.QWebChannel(window.qt.webChannelTransport, (channel) => {
        const native = channel.objects.workspace;
        native.stateChanged.connect((payload) => setState(JSON.parse(payload)));
        setBridge(native);
        native.ready();
      });
    script.onerror = () =>
      setNotice(
        "Could not connect to the editor. Close this window and open the workspace again.",
      );
    document.head.appendChild(script);
    return () => script.remove();
  }, []);
  useLayoutEffect(() => {
    if (!bridge || !canvas.current) return;
    const update = () => {
      const r = canvas.current.getBoundingClientRect();
      bridge.canvas(JSON.stringify([r.x, r.y, r.width, r.height, playerOverlay.current?.getBoundingClientRect().height || 0]));
    };
    const observer = new ResizeObserver(update);
    observer.observe(canvas.current);
    if (playerOverlay.current) observer.observe(playerOverlay.current);
    window.addEventListener("resize", update);
    update();
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", update);
    };
  }, [bridge, state.pip, state.fullscreen, collapsed, rail, playlist]);
  useEffect(() => {
    if (!bridge || tool !== "play") return;
    const activity = (event) => {if (event.key === "Tab") keyboardNavigation.current = true;bridge.command(JSON.stringify({key:"activity"}));};
    document.addEventListener("keydown", activity);
    return () => document.removeEventListener("keydown", activity);
  }, [bridge]);
  const command = (key, value = null) => {
    if (bridge) bridge.command(JSON.stringify({ key, value }));
    else
      setNotice(
        "Design preview — editing and playback connect to local tools in the desktop app.",
      );
  };
  const launch = (id) => {
    if (bridge) bridge.launch(id);
    else location.href = id === "home" ? "./index.html" : `?workspace=${id}`;
  };
  const trigger = (id) => bridge?.trigger(id);
  const find = (...labels) =>
    state.actions.find((a) =>
      labels.some((l) => l.toLowerCase() === a.label.toLowerCase()),
    );
  const immersive = state.pip || state.fullscreen;
  const navigation = ["dazzle", "organize", "writer"].includes(tool);
  const RailIcon =
    tool === "dazzle" ? Film : tool === "organize" ? Database : ListTree;
  if (!names[tool])
    return (
      <p className="p-8">
        Workspace not found. <a href="./index.html">Open Home</a>
      </p>
    );
  return (
    <div className="suite-shell flex h-dvh bg-base text-ink">
      {!immersive && (
        <Sidebar
          active={tool}
          collapsed={collapsed}
          onCollapse={() => setCollapsed(!collapsed)}
          onLaunch={launch}
        />
      )}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {!immersive && (
          <>
            <header className="workspace-header">
              <div className="flex min-w-0 items-center gap-4">
                <div className="shrink-0">
                  <h1 className="display text-lg font-bold tracking-tight">
                    {names[tool]}
                    <span className="text-purple-light">.</span>
                  </h1>
                  <p className="mt-0.5 hidden text-[10px] text-muted xl:block">
                    {subtitles[tool]}
                  </p>
                </div>
                <span className="h-7 w-px bg-line" />
                <div className="min-w-0">
                  <p className="truncate text-xs" title={state.name}>
                    {state.name}
                  </p>
                  <p className="mt-1 flex items-center gap-1.5 text-[10px] text-muted">
                    {state.dirty ? (
                      <Circle size={10} className="text-purple-light" />
                    ) : (
                      <Check size={11} />
                    )}{" "}
                    {state.native
                      ? tool === "play"
                        ? "Local media · on this device"
                        : state.dirty
                          ? "Unsaved changes"
                          : state.saved
                            ? "Saved locally"
                            : state.imported
                              ? "Imported copy · save to a new file"
                              : "New document · not saved yet"
                      : "Design preview · sample content"}
                  </p>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {tool === "play" ? (
                  <button
                    className="button-primary"
                    onClick={() => command("open")}
                  >
                    <FolderOpen size={16} />
                    Open media
                  </button>
                ) : (
                  <>
                    <CommandButton
                      action={find("New", "New database")}
                      icon={FilePlus2}
                      onAction={trigger}
                    />
                    <CommandButton
                      action={find("Open", "Open database")}
                      icon={FolderOpen}
                      onAction={trigger}
                    />
                    <CommandButton
                      action={find("Save", "Save changes")}
                      icon={Save}
                      onAction={trigger}
                      primary
                    />
                  </>
                )}
              </div>
            </header>
            {tool !== "play" && (
              <WorkspaceToolbar
                tool={tool}
                state={state}
                onAction={trigger}
                command={command}
                onMenu={setCommandsOpen}
              />
            )}
            {tool === "tables" && (
              <div className="flex items-center gap-3 border-b border-line bg-panel px-4 py-2 text-xs">
                <span className="w-14 font-mono text-purple-light">
                  {state.address || "E8"}
                </span>
                <span className="text-muted italic">fx</span>
                <input
                  key={`${state.address}-${state.formula}`}
                  aria-label="Cell formula"
                  defaultValue={state.formula ?? "=SUM(E2:E7)"}
                  onKeyDown={(e) => {
                    if (e.key === "Enter")
                      command("formula", e.currentTarget.value);
                  }}
                  className="min-w-0 flex-1 bg-transparent px-2 py-1 font-mono outline-none"
                />
                <span className="text-[10px] text-muted">Enter to apply</span>
              </div>
            )}
          </>
        )}
        <div className="flex min-h-0 flex-1">
          {navigation && !immersive && (
            <aside className={`workspace-rail ${rail ? "" : "rail-closed"}`}>
              <button
                className="flex w-full items-center gap-2 border-b border-line p-3 text-xs font-semibold"
                onClick={() => setRail(!rail)}
                title="Toggle workspace navigator"
              >
                <RailIcon size={16} />
                {rail && (
                  <>
                    {tool === "dazzle"
                      ? "Slides"
                      : tool === "writer"
                        ? "Scenes"
                        : "Tables"}
                    <PanelLeft size={14} className="ml-auto text-muted" />
                  </>
                )}
              </button>
              {rail && (
                <div className="min-h-0 flex-1 overflow-y-auto p-2">
                  {state.items.map((item, i) => (
                    <button
                      key={i}
                      onClick={() => command("select", i)}
                      title={item}
                      className={`workspace-nav-row ${i === state.current ? "selected" : ""}`}
                    >
                      {tool === "dazzle" ? (
                        <SlideThumbnail
                          bridge={bridge}
                          index={i}
                          revision={state.previewRevision}
                          aspect={state.slideAspect}
                          title={item}
                        />
                      ) : (
                        <>
                          <span className="mr-2 font-mono text-[10px] text-muted">
                            {String(i + 1).padStart(2, "0")}
                          </span>
                          {item}
                        </>
                      )}
                    </button>
                  ))}
                  {!state.items.length && (
                    <p className="px-2 py-5 text-xs leading-relaxed text-muted">
                      {tool === "organize"
                        ? "Open or create a database to see its tables."
                        : "Your document structure appears here."}
                    </p>
                  )}
                </div>
              )}
            </aside>
          )}
          <div
            ref={canvas}
            data-native-canvas
            style={commandsOpen ? { marginRight: 350 } : undefined}
            className="relative min-h-0 min-w-0 flex-1 overflow-hidden bg-[#15151c]"
          >
            {!state.native && <PreviewCanvas />}
            {tool === "play" && (
              <div ref={playerOverlay} data-player-overlay
                hidden={state.controlsVisible === false && !state.pip}
                className="absolute inset-x-0 bottom-0"
                onPointerDownCapture={() => {keyboardNavigation.current = false;command("controlsFocus", false);}}
                onFocusCapture={() => command("controlsFocus", keyboardNavigation.current)}
                onBlurCapture={(e) => {if (!e.currentTarget.contains(e.relatedTarget)) command("controlsFocus", false);}}>
                <PlayerControls state={state} command={command} playlist={playlist} onPlaylist={() => setPlaylist(!playlist)} />
              </div>
            )}
          </div>
          {tool === "play" && playlist && !immersive && (
            <Playlist
              state={state}
              command={command}
              onClose={() => setPlaylist(false)}
            />
          )}
        </div>
        {!immersive && (
          <footer
            className="flex h-7 shrink-0 items-center justify-between gap-4 border-t border-line bg-panel px-4 text-[10px] text-muted"
            role="status"
          >
            <span className="truncate">
              {notice ||
                state.status ||
                (state.native
                  ? "Ready. Your files stay on this device."
                  : "Browser preview — sample content. Use the desktop app to edit local files.")}
            </span>
            <span className="flex shrink-0 items-center gap-2">
              {state.words !== undefined &&
                `${state.words.toLocaleString()} words · `}
              <HardDrive size={11} />
              Offline workspace
            </span>
          </footer>
        )}
      </div>
    </div>
  );
}
