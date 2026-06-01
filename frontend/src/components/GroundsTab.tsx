import type { Grounding } from "../api";

export default function GroundsTab({ grounding }: { grounding: Grounding[] }) {
  if (grounding.length === 0) {
    return <p className="py-6 text-center text-sm text-ink-faint">根拠となる手順書が見つかりませんでした。</p>;
  }
  return (
    <ul className="space-y-3">
      {grounding.map((chunk) => (
        <li key={chunk.chunk_id} className="rounded-lg border border-line/70 bg-paper-panel p-4">
          <div className="mb-2 flex items-center gap-2">
            <span className="rounded bg-paper-sunk px-2 py-0.5 font-mono text-[11px] uppercase tracking-wide text-ink-soft">
              {chunk.section}
            </span>
            <span className="text-sm font-semibold text-ink">{chunk.heading}</span>
            <span className="ml-auto flex items-center gap-2 text-[11px] text-ink-faint">
              <span className="font-mono">#{chunk.rank}</span>
              <span className="font-mono">score {chunk.score.toFixed(3)}</span>
            </span>
          </div>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-soft">{chunk.text}</p>
        </li>
      ))}
    </ul>
  );
}
