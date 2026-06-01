import type { TaskStep } from "../api";

function Line({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-line/60 py-2 last:border-b-0">
      <span className="text-xs text-ink-faint">{label}</span>
      <span className="text-right font-mono text-xs text-ink">{children}</span>
    </div>
  );
}

export default function Inspector({ step }: { step: TaskStep | null }) {
  if (!step) {
    return (
      <div className="grid h-full place-items-center px-4 py-10 text-center text-sm text-ink-faint">
        ステップを選択すると、意図・キーシーケンス・画面状態が表示されます。
      </div>
    );
  }
  const fields = Object.entries(step.screen_fields);
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-ink-faint">#{step.ordinal}</span>
        <span className="text-sm font-semibold text-ink">{step.intent}</span>
        <span
          className={`ml-auto rounded-full px-2.5 py-1 text-xs font-semibold ${
            step.status === "error" ? "bg-seal-wash text-seal-deep" : "bg-phosphor/10 text-phosphor"
          }`}
        >
          {step.status === "error" ? "検証エラー" : "正常"}
        </span>
      </div>

      <div>
        <div className="mb-1 text-xs font-semibold text-ink-soft">キーシーケンス</div>
        <div className="rounded-lg border border-line bg-paper-panel px-3 py-2">
          <Line label="type">{step.action.type}</Line>
          {step.action.target ? <Line label="target">{step.action.target}</Line> : null}
          {step.action.value ? (
            <Line label="value">
              <span className="rounded bg-ink/90 px-1.5 py-0.5 text-phosphor-glow">{step.action.value}</span>
            </Line>
          ) : null}
          {step.action.key ? <Line label="key">{step.action.key}</Line> : null}
        </div>
      </div>

      <div>
        <div className="mb-1 flex items-center justify-between">
          <span className="text-xs font-semibold text-ink-soft">画面状態</span>
          <span className="font-mono text-xs text-ink-faint">{step.screen ?? "—"}</span>
        </div>
        <div className="rounded-lg border border-line bg-paper-panel px-3 py-2">
          {fields.length === 0 ? (
            <div className="py-1 text-xs text-ink-faint">フィールドなし</div>
          ) : (
            fields.map(([name, value]) => (
              <Line key={name} label={name}>
                <span className="text-phosphor">{value || "∅"}</span>
              </Line>
            ))
          )}
        </div>
      </div>

      {step.errors && step.errors.length > 0 ? (
        <div>
          <div className="mb-1 text-xs font-semibold text-seal-deep">エラー</div>
          <div className="flex flex-wrap gap-2">
            {step.errors.map((error, index) => (
              <span
                key={`${index}:${error}`}
                className="rounded bg-seal-wash px-2 py-1 font-mono text-xs text-seal-deep"
              >
                {error}
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
