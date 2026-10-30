import { ArrowUpRight, SearchX } from "lucide-react";
import { filterTools } from "../data";
import ToolIcon from "./Icons";
export default function ToolGrid({ query, group, onGroup, onLaunch }) {
  const matches = filterTools(query, group);
  return (
    <section aria-labelledby="tools-heading">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 id="tools-heading" className="text-sm font-semibold">
            Your toolkit
          </h2>
          <span className="text-xs text-muted">
            Small tools. Big possibilities.
          </span>
        </div>
        <div
          className="flex gap-1 rounded-lg bg-panel p-1"
          aria-label="Filter tools"
        >
          {["All", "Convert", "Create", "Play"].map((item) => (
            <button
              key={item}
              aria-pressed={group === item}
              onClick={() => onGroup(item)}
              className={`rounded-md px-3 py-1.5 text-[11px] transition-colors ${group === item ? "bg-surface text-white" : "text-muted hover:text-white"}`}
            >
              {item}
            </button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
        {matches.map((tool) => (
          <button
            key={tool.id}
            onClick={() => onLaunch(tool.id)}
            className="tool-card group flex min-w-0 items-center gap-3 rounded-xl border border-line bg-panel/65 p-3 text-left hover:border-purple/60 hover:bg-panel"
          >
            <span
              className={`grid size-10 shrink-0 place-items-center rounded-lg ${tool.group === "Create" ? "bg-purple/10 text-purple-light" : "bg-white/5 text-white"}`}
            >
              <ToolIcon name={tool.icon} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[13px] font-semibold">
                {tool.name}
                <span className="ml-2 text-[10px] font-normal text-muted">
                  {tool.detail.split(",")[0]}
                </span>
              </span>
              <span className="mt-1 block truncate text-[11px] text-muted">
                {tool.description}
              </span>
            </span>
            <ArrowUpRight
              size={14}
              className="shrink-0 text-muted group-hover:text-purple-light"
            />
          </button>
        ))}
      </div>
      {!matches.length && (
        <div className="flex items-center gap-3 rounded-xl border border-dashed border-line p-8 text-sm text-muted">
          <SearchX size={22} />
          No tools match “{query}”. Try a different search or category.
        </div>
      )}
    </section>
  );
}
