import type { Step, TaskStep } from "../api";

function actionToken(action: Step) {
  if (action.type === "field") {
    return (
      <span className="flex items-baseline gap-1 font-mono text-[11px]">
        <span className="shrink-0 text-ink-faint">{action.target}</span>
        <span className="shrink-0 text-ink-faint">←</span>
        <span className="max-w-[6.5rem] truncate rounded bg-ink/90 px-1.5 py-0.5 text-phosphor-glow">
          {action.value || "∅"}
        </span>
      </span>
    );
  }
  return <span className="font-mono text-[11px] text-ink-soft">{action.key}</span>;
}

export default function Timeline({
  steps,
  activeKey,
  onSelect,
}: {
  steps: TaskStep[];
  activeKey: string | null;
  onSelect: (step: TaskStep) => void;
}) {
  if (steps.length === 0) {
    return (
      <div className="grid h-full place-items-center px-4 py-10 text-center text-sm text-ink-faint">
        承認後、実行ステップがここに順次表示されます。
      </div>
    );
  }
  return (
    <ol className="space-y-1">
      {steps.map((step) => {
        const key = `${step.execution_id}:${step.ordinal}`;
        const active = key === activeKey;
        const error = step.status === "error";
        return (
          <li key={key}>
            <button
              type="button"
              onClick={() => onSelect(step)}
              className={`flex w-full items-center gap-2 rounded-md border px-2.5 py-2 text-left transition-colors ${
                active
                  ? "border-ink bg-paper"
                  : error
                    ? "border-seal/40 bg-seal-wash/40 hover:bg-seal-wash/60"
                    : "border-line/70 bg-paper-panel hover:bg-paper-sunk"
              }`}
            >
              <span className="shrink-0 font-mono text-[11px] text-ink-faint">
                {step.ordinal.toString().padStart(2, "0")}
              </span>
              <span className={`h-2 w-2 shrink-0 rounded-full ${error ? "bg-seal" : "bg-phosphor"}`} />
              <span className="min-w-0 flex-1 truncate text-xs font-medium text-ink">{step.intent}</span>
              <span className="shrink-0">{actionToken(step.action)}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
