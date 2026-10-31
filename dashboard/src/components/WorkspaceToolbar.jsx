import { useState } from "react";
import {
  Search,
  SlidersHorizontal,
  Undo2,
  Redo2,
  Bold,
  Italic,
  Underline,
  AlignLeft,
  AlignCenter,
  AlignRight,
  Image,
  Plus,
  Play,
  Eraser,
  PenLine,
} from "lucide-react";

export function CommandButton({
  action,
  onAction,
  icon: Icon,
  primary = false,
}) {
  if (!action) return null;
  return (
    <button
      disabled={!action.enabled}
      title={`${action.label}${action.shortcut ? ` (${action.shortcut})` : ""}`}
      onClick={() => onAction(action.id)}
      className={`${primary ? "button-primary" : "workspace-button"} ${action.checked ? "selected" : ""}`}
    >
      {Icon && <Icon size={16} />}
      <span>{action.label}</span>
    </button>
  );
}

export default function WorkspaceToolbar({
  tool,
  state,
  onAction,
  command,
  onMenu,
}) {
  const [menu, setMenu] = useState(false);
  const [query, setQuery] = useState("");
  const [slideTab, setSlideTab] = useState("Home");
  function showMenu(open) {
    setMenu(open);
    onMenu(open);
  }
  const actions = state.actions || [];
  const find = (label) =>
    actions.find((a) => a.label.toLowerCase() === label.toLowerCase());
  const controls =
    {
      pages: [
        ["Undo", Undo2],
        ["Redo", Redo2],
        ["Bold", Bold],
        ["Italic", Italic],
        ["Underline", Underline],
        ["Align left", AlignLeft],
        ["Align center", AlignCenter],
        ["Align right", AlignRight],
        ["Image", Image],
      ],
      tables: [
        ["Undo", Undo2],
        ["Redo", Redo2],
        ["Add row", Plus],
        ["Add column", Plus],
        ["Calculate selected", null],
      ],
      dazzle: ({
        File: [["New", Plus], ["Open", null], ["Save as", null], ["PDF", null], ["Export slide images", Image]],
        Home: [["Undo", Undo2], ["Redo", Redo2], ["Add slide", Plus], ["Duplicate slide", Plus], ["Delete slide", null], ["Copy objects", null], ["Paste objects", null], ["Edit object", PenLine]],
        Text: [["Format text", PenLine], ["Bold", Bold], ["Italic", Italic], ["Underline", Underline], ["Align text left", AlignLeft], ["Align text center", AlignCenter], ["Align text right", AlignRight], ["Bullets", null], ["Numbering", null]],
        Insert: [["Text box", Plus], ["Image", Image], ["Video", Play], ["Shape", Plus], ["Chart / graph", null], ["Table", null], ["Connector", null], ["Hyperlink", null]],
        Design: [["Slide layout", null], ["Crop picture", null], ["Background color", null], ["Background image", Image], ["Slide size", null], ["Slide transition", null]],
        Arrange: [["Duplicate object", Plus], ["Delete object", null], ["Bring to front", null], ["Send to back", null], ["Align left", AlignLeft], ["Align center", AlignCenter], ["Align right", AlignRight], ["Group", null], ["Ungroup", null], ["Distribute horizontally", null], ["Distribute vertically", null], ["Flip horizontal", null], ["Flip vertical", null]],
        Present: [["Slideshow", Play], ["Presenter view", null], ["Hide / show slide", null], ["Present from beginning", Play], ["Speaker notes", null], ["Fade on click", null], ["Remove animation", null], ["Fit slide", null]],
      }[slideTab]),
      organize: [
        ["New table", Plus],
        ["Add record", Plus],
        ["Delete record", null],
        ["Import CSV", null],
        ["Export CSV", null],
      ],
      formulaic: [
        ["Undo", Undo2],
        ["Redo", Redo2],
        ["Fraction", null],
        ["Square root", null],
        ["Power", null],
        ["Subscript", null],
        ["Greek alpha", null],
      ],
      writer: [
        ["Find", Search],
        ["Title page", null],
        ["Beat map", null],
      ],
      sketch: [
        ["Eraser", Eraser],
        ["Pen color", null],
        ["Clear", null],
      ],
    }[tool] || [];
  return (
    <div>
      {tool === "dazzle" && <div className="flex gap-1 border-b border-white/10 bg-[#1B1B23] px-5 pt-1" role="tablist" aria-label="Presentation tools">
        {["File", "Home", "Text", "Insert", "Design", "Arrange", "Present"].map(tab => <button key={tab} role="tab" aria-selected={slideTab === tab} className={`workspace-button ${slideTab === tab ? "selected" : ""}`} onClick={() => setSlideTab(tab)}>{tab}</button>)}
      </div>}
    <div className="workspace-toolbar">
      <div className="flex min-w-0 flex-1 items-center gap-1.5 overflow-x-auto py-1">
        {(tool === "pages" || (tool === "dazzle" && slideTab === "Text" && state.textSelected)) && (
          <>
            <select
              aria-label="Font family"
              className="workspace-input w-32"
              value={state.font || "Calibri"}
              onChange={(e) => command("font", e.target.value)}
            >
              {[
                ...new Set([
                  state.font || "Calibri",
                  "Arial",
                  "Georgia",
                  "Times New Roman",
                  "Segoe UI",
                ]),
              ].map((f) => (
                <option key={f}>{f}</option>
              ))}
            </select>
            <input
              aria-label="Font size"
              type="number"
              min="6"
              max={tool === "dazzle" ? 180 : 96}
              className="workspace-input w-16"
              value={state.size || 12}
              onChange={(e) => command("size", e.target.value)}
            />
          </>
        )}
        {tool === "writer" && (
          <>
            <select
              aria-label="Screenplay element"
              className="workspace-input w-40"
              value={state.element || 0}
              onChange={(e) => command("element", Number(e.target.value))}
            >
              {(
                state.elements || [
                  "Scene Heading",
                  "Action",
                  "Character",
                  "Dialogue",
                  "Parenthetical",
                  "Transition",
                  "Shot",
                  "General Text",
                ]
              ).map((e, i) => (
                <option value={i} key={e}>
                  {e}
                </option>
              ))}
            </select>
            {[
              [Bold, "Bold", "**"],
              [Italic, "Italic", "*"],
              [Underline, "Underline", "_"],
            ].map(([Icon, label, marker]) => (
              <button
                className="workspace-button"
                key={label}
                title={label}
                aria-label={label}
                onClick={() => command("emphasis", marker)}
              >
                <Icon size={16} />
              </button>
            ))}
            <button
              className="workspace-button"
              onClick={() => command("preview")}
            >
              Script preview
            </button>
            <button
              className="workspace-button"
              onClick={() => command("forward")}
            >
              Forward writing
            </button>
          </>
        )}
        {tool === "sketch" && (
          <>
            <button
              className={`workspace-button ${!state.eraser ? "selected" : ""}`}
              onClick={() => command("pen")}
            >
              <PenLine size={16} />
              Pen
            </button>
            <input
              aria-label="Stroke color"
              type="color"
              value={state.color || "#101014"}
              onChange={(e) => command("color", e.target.value)}
              className="h-8 w-9 rounded"
            />
            <label className="flex items-center gap-2 px-2 text-xs text-muted">
              Stroke
              <input
                aria-label="Stroke width"
                type="range"
                min="1"
                max="60"
                value={state.size || 3}
                onChange={(e) => command("size", e.target.value)}
                className="w-24 accent-purple"
              />
              {state.size || 3} px
            </label>
          </>
        )}
        {controls.map(([label, Icon]) => (
          <CommandButton
            key={label}
            action={find(label)}
            icon={Icon}
            onAction={onAction}
          />
        ))}
      </div>
      {state.docks && (
        <button
          className="workspace-button shrink-0"
          onClick={() => command("inspect")}
          title="Show or hide contextual inspector"
        >
          <SlidersHorizontal size={16} />
          <span className="hidden xl:inline">Inspector</span>
        </button>
      )}
      <div className="relative shrink-0">
        <button
          className={`workspace-button ${menu ? "selected" : ""}`}
          aria-expanded={menu}
          onClick={() => showMenu(!menu)}
        >
          <Search size={16} />
          Commands
        </button>
        {menu && (
          <div
            className="command-panel"
            onKeyDown={(e) => {
              if (e.key === "Escape") showMenu(false);
            }}
          >
            <label className="flex items-center gap-2 border-b border-line p-3">
              <Search size={16} />
              <input
                autoFocus
                aria-label="Find a command"
                placeholder="Find a command…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="min-w-0 bg-transparent outline-none"
              />
            </label>
            <div className="max-h-80 overflow-y-auto p-2">
              {actions
                .filter((a) =>
                  `${a.label} ${a.group}`
                    .toLowerCase()
                    .includes(query.toLowerCase()),
                )
                .map((a) => (
                  <button
                    key={a.id}
                    disabled={!a.enabled}
                    className="flex w-full items-center justify-between gap-4 rounded-md px-3 py-2 text-left hover:bg-surface"
                    onClick={() => {
                      onAction(a.id);
                      showMenu(false);
                    }}
                  >
                    <span>
                      {a.label}
                      <small className="block text-[10px] text-muted">
                        {a.group}
                      </small>
                    </span>
                    <kbd className="text-[10px] text-muted">{a.shortcut}</kbd>
                  </button>
                ))}
              {!actions.length && (
                <p className="p-3 text-muted">
                  Commands connect to the editing engine in the desktop app.
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
    </div>
  );
}
