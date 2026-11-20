import { useState } from "react";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Square,
  Volume2,
  VolumeX,
  Maximize,
  PictureInPicture2,
  ListMusic,
  FolderPlus,
  FolderOpen,
  Save,
  Plus,
  ArrowUp,
  ArrowDown,
  Trash2,
  GripVertical,
  Settings2,
  SlidersHorizontal,
} from "lucide-react";

export function MediaButton({
  icon: Icon,
  label,
  onClick,
  active = false,
  primary = false,
  disabled = false,
}) {
  return (
    <button
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className={`media-button ${active ? "selected" : ""} ${primary ? "bg-yellow text-base hover:bg-yellow/90" : "hover:bg-surface"}`}
    >
      <Icon size={primary ? 22 : 18} />
    </button>
  );
}

export function Playlist({ state, command, onClose }) {
  const [selected, setSelected] = useState(0);
  const [dragged, setDragged] = useState(null);
  return (
    <aside className="playlist-panel">
      <div className="flex items-center justify-between p-4">
        <h2 className="text-sm font-semibold">
          Playlist{" "}
          <span className="ml-2 text-xs font-normal text-muted">
            {state.items.length} files
          </span>
        </h2>
        <button className="workspace-button" onClick={onClose}>
          Hide
        </button>
      </div>
      <div className="flex flex-wrap gap-1 border-y border-line p-2">
        {[
          [Plus, "Add files", "add"],
          [FolderPlus, "Add folder", "folder"],
          [FolderOpen, "Open playlist", "openList"],
          [Save, "Save playlist", "saveList"],
        ].map(([Icon, label, key]) => (
          <MediaButton
            key={key}
            icon={Icon}
            label={label}
            onClick={() => command(key)}
          />
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {state.items.map((name, i) => (
          <div
            key={`${i}-${name}`}
            draggable
            onDragStart={() => setDragged(i)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              if (dragged !== null) command("reorder", [dragged, i]);
              setDragged(null);
              setSelected(i);
            }}
            onClick={() => {
              setSelected(i);
              command("select", i);
            }}
            onDoubleClick={() => command("playItem", i)}
            className={`playlist-row ${i === selected ? "selected" : ""}`}
          >
            <GripVertical size={14} className="shrink-0 text-muted" />
            <button
              className="min-w-0 flex-1 truncate text-left"
              title={`Play ${name}`}
              onClick={(e) => {
                e.stopPropagation();
                setSelected(i);
                command("select", i);
                command("playItem", i);
              }}
            >
              {name}
            </button>
            {state.current === i && (
              <span className="size-1.5 shrink-0 rounded-full bg-purple-light" />
            )}
          </div>
        ))}
        {!state.items.length && (
          <div className="px-4 py-12 text-center">
            <ListMusic className="mx-auto mb-4 text-purple-light" size={32} />
            <p className="text-sm">Make room for a good watch.</p>
            <p className="mt-2 text-xs leading-relaxed text-muted">
              Add local files or a folder. Drag tracks to reorder.
            </p>
          </div>
        )}
      </div>
      <div className="flex items-center gap-1 border-t border-line p-2">
        {[
          [ArrowUp, "Move selected up", "up"],
          [ArrowDown, "Move selected down", "down"],
          [Trash2, "Remove selected", "remove"],
        ].map(([Icon, label, key]) => (
          <MediaButton
            key={key}
            icon={Icon}
            label={label}
            disabled={!state.items.length}
            onClick={() => {
              command("select", selected);
              command(key);
              if (key !== "remove")
                setSelected(
                  Math.max(
                    0,
                    Math.min(
                      state.items.length - 1,
                      selected + (key === "up" ? -1 : 1),
                    ),
                  ),
                );
            }}
          />
        ))}
        <button
          className="ml-auto workspace-button"
          disabled={!state.items.length}
          onClick={() => command("clear")}
        >
          Clear
        </button>
      </div>
    </aside>
  );
}

export default function PlayerControls({
  state,
  command,
  playlist,
  onPlaylist,
}) {
  const [scrub, setScrub] = useState(null);
  const shown = state.bottomControls || ["speed", "audio", "subtitles"];
  const selectors = [
    ["speed", "Speed", state.speeds || [], state.speed],
    ["audio", "Audio", state.audioTracks || [], state.audio],
    ["subtitles", "Subtitles", state.subtitleTracks || [], state.subtitles],
  ];
  return (
    <div className={`player-controls ${state.pip ? "compact" : ""}`}>
      {!state.pip && (
        <>
        <div className="mb-2 flex flex-wrap items-center gap-3 text-xs">
          {selectors.filter(([key]) => shown.includes(key)).map(([key,label,options,value]) => (
            <label key={key} className="flex min-w-0 items-center gap-2">
              {label}
              <select aria-label={`Playback ${label.toLowerCase()}`} value={value ?? ""}
                disabled={state.ready === false || !options.length}
                onChange={(e) => command(key,e.target.value)} className="max-w-40 rounded border border-line bg-base px-2 py-1.5">
                {!options.length && <option value="">No tracks</option>}
                {options.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
              </select>
            </label>
          ))}
          {shown.includes("subtitles") && <button className="workspace-button" onClick={() => command("loadSubtitles")}>Load subtitles</button>}
          <details className="ml-auto">
            <summary className="workspace-button cursor-pointer"><SlidersHorizontal size={14} />Customize bar</summary>
            <div className="flex flex-wrap gap-3 py-2" aria-label="Bottom bar customization">
              {selectors.map(([key,label]) => <label key={key} className="flex items-center gap-2">
                <input type="checkbox" checked={shown.includes(key)} onChange={(e) => command("bottomControls",e.target.checked ? [...shown,key] : shown.filter((v) => v !== key))} />{label}
              </label>)}
            </div>
          </details>
        </div>
        <div className="mb-3 flex items-center gap-3">
          <span className="min-w-24 text-[11px] tabular-nums text-muted">
            {state.time || "00:00 / 00:00"}
          </span>
          <input
            aria-label="Seek playback"
            type="range"
            min="0"
            max="1000"
            value={scrub ?? state.seek ?? 0}
            onChange={(e) => setScrub(Number(e.target.value))}
            onPointerUp={(e) => {
              command("seek", e.currentTarget.value);
              setScrub(null);
            }}
            onKeyUp={(e) => {
              command("seek", e.currentTarget.value);
              setScrub(null);
            }}
            className="min-w-0 flex-1 accent-purple"
          />
        </div>
        </>
      )}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-1">
          <MediaButton
            icon={SkipBack}
            label="Previous track"
            onClick={() => command("previous")}
          />
          <MediaButton
            icon={state.playing ? Pause : Play}
            label={state.playing ? "Pause" : "Play"}
            primary
            disabled={state.ready === false}
            onClick={() => command("toggle")}
          />
          <MediaButton
            icon={SkipForward}
            label="Next track"
            onClick={() => command("next")}
          />
          {!state.pip && (
            <MediaButton
              icon={Square}
              label="Stop"
              onClick={() => command("stop")}
            />
          )}
        </div>
        {!state.pip && (
          <div className="flex items-center gap-2">
            <MediaButton
              icon={state.muted ? VolumeX : Volume2}
              label={state.muted ? "Unmute" : "Mute"}
              active={state.muted}
              onClick={() => command("mute")}
            />
            <input
              aria-label="Volume up to 200 percent"
              type="range"
              min="0"
              max="200"
              value={state.volume ?? 100}
              onChange={(e) => command("volume", e.target.value)}
              className="w-20 accent-purple xl:w-28"
            />
            <span className="w-10 text-xs tabular-nums">
              {state.volume ?? 100}%
            </span>
            <MediaButton
              icon={Settings2}
              label="Playback options"
              onClick={() => command("options")}
            />
            <MediaButton
              icon={ListMusic}
              label="Toggle playlist"
              active={playlist}
              onClick={onPlaylist}
            />
          </div>
        )}
        <div className="flex items-center gap-1">
          <MediaButton
            icon={PictureInPicture2}
            label={state.pip ? "Exit Picture in Picture" : "Picture in Picture"}
            active={state.pip}
            onClick={() => command("pip")}
          />
          {!state.pip && (
            <MediaButton
              icon={Maximize}
              label="Toggle fullscreen"
              onClick={() => command("fullscreen")}
            />
          )}
        </div>
      </div>
    </div>
  );
}
