import {
  ArrowUpRight,
  Plus,
  Play,
  ArrowDownToLine,
  MoveUpRight,
} from "lucide-react";
export default function LaunchCards({
  onChoose,
  onLaunch,
  dragging,
  onDragOver,
  onDragLeave,
  onDrop,
}) {
  return (
    <section
      aria-label="Start something"
      className="grid grid-cols-1 gap-4 md:grid-cols-[1.16fr_1fr_0.9fr]"
    >
      <article
        className={`launch-card convert-card ${dragging ? "dragging" : ""}`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        <div className="flex items-start justify-between">
          <span className="eyebrow text-muted">01 / REWORK</span>
          <div className="conversion-art" aria-hidden="true">
            <span>RAW</span>
            <MoveUpRight size={27} />
            <span>NEW</span>
          </div>
        </div>
        <div className="mt-7">
          <h2 className="display text-2xl font-semibold">
            Different format.
            <br />
            Same great work.
          </h2>
          <p className="mt-2 max-w-64 text-xs leading-relaxed text-muted">
            Convert, compress, extract. Get your local files ready for
            whatever’s next.
          </p>
        </div>
        <div className="mt-6 flex items-center gap-3">
          <button
            className="button-primary"
            onClick={() => onChoose("convert")}
          >
            <Plus size={17} />
            Choose files
            <ArrowUpRight size={16} />
          </button>
          <span className="text-[11px] text-muted">or drop them here</span>
        </div>
        {dragging && (
          <div className="pointer-events-none absolute inset-0 grid place-items-center rounded-2xl bg-base/95 text-lg font-semibold text-white">
            <ArrowDownToLine />
            Drop to add local files
          </div>
        )}
      </article>
      <article className="launch-card create-card">
        <div className="flex items-start justify-between">
          <span className="eyebrow text-purple-light">02 / CREATE</span>
          <div className="creative-art" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
        </div>
        <div className="mt-7">
          <h2 className="display text-2xl font-semibold">
            A blank page.
            <br />A big possibility.
          </h2>
          <p className="mt-2 max-w-64 text-xs leading-relaxed text-muted">
            Write it, draw it, build it. A whole creative toolkit, in one place.
          </p>
        </div>
        <button
          className="button-secondary mt-6"
          onClick={() => onLaunch("pages")}
        >
          Open Pages
          <ArrowUpRight size={16} />
        </button>
      </article>
      <article className="launch-card play-card">
        <div className="flex items-start justify-between">
          <span className="eyebrow text-muted">03 / UNWIND</span>
          <div className="sound-art" aria-hidden="true">
            {[15, 28, 40, 23, 32, 18, 36, 25].map((h, i) => (
              <i key={i} style={{ height: h }} />
            ))}
          </div>
        </div>
        <div className="mt-7">
          <h2 className="display text-2xl font-semibold">
            Less noise.
            <br />
            More play.
          </h2>
          <p className="mt-2 text-xs leading-relaxed text-muted">
            Your films. Your music. Your queue.
            <br />
            Make a little room for a break.
          </p>
        </div>
        <button
          className="button-secondary mt-6"
          onClick={() => onChoose("play")}
        >
          <Play size={15} />
          Open media
          <ArrowUpRight size={16} />
        </button>
      </article>
    </section>
  );
}
