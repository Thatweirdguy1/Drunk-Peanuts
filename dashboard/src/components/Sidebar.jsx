import {
  Home,
  PanelLeftClose,
  PanelLeftOpen,
  HardDrive,
  ArrowUpRight,
} from "lucide-react";
import { tools } from "../data";
import ToolIcon from "./Icons";
export default function Sidebar({ collapsed, onCollapse, onLaunch }) {
  return (
    <aside
      className={`sidebar ${collapsed ? "is-collapsed" : ""} flex shrink-0 flex-col border-r border-line bg-panel/60`}
    >
      <div className="flex h-24 items-center justify-center border-b border-line px-4">
        <img
          src="./logo.png"
          alt="Drunk Peanuts."
          className={`object-contain ${collapsed ? "w-14" : "w-48"}`}
        />
      </div>
      <nav
        aria-label="Main navigation"
        className="flex-1 overflow-y-auto px-3 py-5"
      >
        <button className="nav-item active" aria-current="page" title="Home">
          <Home size={19} aria-hidden="true" />
          <span className="nav-label">Home</span>
          <span className="nav-label ml-auto text-xs text-muted">01</span>
        </button>
        {["Convert", "Create", "Play"].map((group) => (
          <div key={group} className="mt-5">
            <p className="nav-label mb-2 px-3 text-[10px] font-semibold tracking-[.18em] text-muted uppercase">
              {group}
            </p>
            {tools
              .filter((tool) => tool.group === group)
              .map((tool) => (
                <button
                  key={tool.id}
                  onClick={() => onLaunch(tool.id)}
                  title={`${tool.name} — ${tool.detail}`}
                  className="nav-item"
                >
                  <ToolIcon name={tool.icon} />
                  <span className="nav-label">{tool.name}</span>
                </button>
              ))}
          </div>
        ))}
      </nav>
      <div className="border-t border-line p-3">
        <div className="nav-label mb-3 rounded-xl border border-line bg-base p-3">
          <div className="mb-1 flex items-center gap-2 text-xs">
            <HardDrive size={14} /> Yours. Locally.
          </div>
          <p className="text-[11px] leading-relaxed text-muted">
            Your files stay in your workspace.
          </p>
        </div>
        <button
          className="nav-item"
          onClick={onCollapse}
          aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          aria-expanded={!collapsed}
          title={collapsed ? "Expand navigation" : "Collapse navigation"}
        >
          {collapsed ? (
            <PanelLeftOpen size={19} />
          ) : (
            <PanelLeftClose size={19} />
          )}
          <span className="nav-label">Collapse sidebar</span>
          <ArrowUpRight size={14} className="nav-label ml-auto text-muted" />
        </button>
      </div>
    </aside>
  );
}
