import { ArrowUpRight, FolderOpen } from "lucide-react";
import { tools } from "../data";
import ToolIcon from "./Icons";
export default function RecentFiles({ files, onOpen, onChoose, onClear }) {
  return (
    <section aria-labelledby="recent-heading">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 id="recent-heading" className="text-sm font-semibold">
            Pick up where you left off
          </h2>
          <span className="text-[10px] text-muted">
            {files.some((f) => f.sample)
              ? "Sample recent files"
              : "This session"}
          </span>
        </div>
        <button
          className="rounded px-2 py-1.5 text-[11px] text-muted hover:text-white"
          onClick={onClear}
          disabled={!files.length}
        >
          Clear list
        </button>
      </div>
      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full text-left text-xs">
          <thead className="bg-panel text-[10px] tracking-wider text-muted uppercase">
            <tr>
              <th className="px-4 py-2.5 font-medium">File name</th>
              <th className="px-4 py-2.5 font-medium">Workspace</th>
              <th className="px-4 py-2.5 font-medium">Size</th>
              <th className="px-4 py-2.5 font-medium">Last opened</th>
              <th className="px-4 py-2.5">
                <span className="sr-only">Open</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {files.map((file) => (
              <tr
                key={file.id}
                className="border-t border-line/70 hover:bg-panel/60"
              >
                <td className="px-4 py-3">
                  <button
                    className="flex items-center gap-3 rounded text-left"
                    onClick={() => onOpen(file)}
                  >
                    <span className="text-purple-light">
                      <ToolIcon name={file.tool} size={16} />
                    </span>
                    <span className="whitespace-nowrap font-medium">
                      {file.name}
                    </span>
                  </button>
                </td>
                <td className="px-4 py-3 text-muted">
                  {tools.find((t) => t.id === file.tool)?.name}
                </td>
                <td className="whitespace-nowrap px-4 py-3 tabular-nums text-muted">
                  {file.size}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-muted">
                  {file.modified}
                </td>
                <td className="px-4 py-3">
                  <button
                    title={`Open ${file.name}`}
                    aria-label={`Open ${file.name}`}
                    onClick={() => onOpen(file)}
                    className="grid size-8 place-items-center rounded-lg text-muted hover:bg-surface hover:text-white"
                  >
                    <ArrowUpRight size={15} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!files.length && (
          <button
            onClick={() => onChoose()}
            className="flex w-full items-center justify-center gap-2 p-7 text-sm text-muted"
          >
            <FolderOpen size={17} />
            Choose local files to get started
          </button>
        )}
      </div>
    </section>
  );
}
