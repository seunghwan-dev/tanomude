import type { Slots } from "../api";

function Row({
  label,
  code,
  growth,
  children,
}: {
  label: string;
  code?: string;
  growth?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line/70 py-3 last:border-b-0">
      <div className="shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-ink">{label}</span>
          {growth ? (
            <span className="inline-flex items-center rounded-full bg-phosphor/10 px-2 py-0.5 text-[10px] font-semibold text-phosphor">
              育成候補
            </span>
          ) : null}
        </div>
        {code ? <div className="font-mono text-[11px] uppercase tracking-wide text-ink-faint">{code}</div> : null}
        {growth ? <div className="mt-0.5 text-[11px] text-ink-faint">個人修正で調整される推論値</div> : null}
      </div>
      <div className="text-right">{children}</div>
    </div>
  );
}

function Flag({ on, onText, offText }: { on: boolean; onText: string; offText: string }) {
  return (
    <span
      className={
        on
          ? "inline-flex items-center rounded-full bg-seal-wash px-2.5 py-1 text-xs font-semibold text-seal-deep"
          : "inline-flex items-center rounded-full bg-paper-sunk px-2.5 py-1 text-xs font-medium text-ink-faint"
      }
    >
      {on ? onText : offText}
    </span>
  );
}

export default function AnalysisTab({ slots }: { slots: Slots }) {
  return (
    <div>
      <Row label="目的地コード" code="dest_code">
        <span className="font-mono text-base font-semibold text-ink">{slots.dest_code || "—"}</span>
      </Row>
      <Row label="目的" code="purpose">
        <span className="max-w-[22rem] text-sm text-ink-soft">{slots.purpose || "—"}</span>
      </Row>
      <Row label="海外出張" code="overseas" growth>
        <Flag on={slots.overseas} onText="海外" offText="国内" />
      </Row>
      <Row label="前回案件の再利用" code="reuse_prev_proj" growth>
        <Flag on={slots.reuse_prev_proj} onText="再利用する" offText="新規" />
      </Row>
    </div>
  );
}
