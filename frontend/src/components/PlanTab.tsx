import type { Step } from "../api";
import { deriveIntent } from "../lib/intent";

const TYPE_LABELS: Record<Step["type"], string> = {
  field: "入力",
  fkey: "ファンクション",
  nav: "遷移",
};

function StepToken({ step }: { step: Step }) {
  if (step.type === "field") {
    return (
      <span className="font-mono text-xs">
        <span className="text-ink-faint">{step.target}</span>
        <span className="text-ink-faint"> ← </span>
        <span className="rounded bg-ink/90 px-1.5 py-0.5 text-phosphor-glow">{step.value || "∅"}</span>
      </span>
    );
  }
  return <span className="font-mono text-xs text-ink-soft">{step.key}</span>;
}

export default function PlanTab({ steps }: { steps: Step[] }) {
  return (
    <ol className="space-y-1.5">
      {steps.map((step) => (
        <li
          key={step.seq}
          className="flex items-center gap-3 rounded-lg border border-line/70 bg-paper-panel px-3 py-2.5"
        >
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-paper-sunk font-mono text-xs font-semibold text-ink-soft">
            {step.seq}
          </span>
          <span className="w-40 shrink-0 text-sm font-medium text-ink">{deriveIntent(step)}</span>
          <span className="hidden w-24 shrink-0 text-[11px] uppercase tracking-wide text-ink-faint sm:block">
            {TYPE_LABELS[step.type]}
          </span>
          <span className="ml-auto text-right">
            <StepToken step={step} />
          </span>
        </li>
      ))}
    </ol>
  );
}
