import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import type { TaskPlan } from "../api";
import ActionBar from "./ActionBar";
import AnalysisTab from "./AnalysisTab";
import GroundsTab from "./GroundsTab";
import PlanTab from "./PlanTab";

type TabKey = "analysis" | "plan" | "grounds";

const TABS: { key: TabKey; label: string; code: string }[] = [
  { key: "analysis", label: "分析", code: "slots" },
  { key: "plan", label: "計画", code: "keysequence" },
  { key: "grounds", label: "根拠", code: "grounding" },
];

const STATUS_LABELS: Record<string, string> = {
  awaiting_approval: "承認待ち",
  refused: "却下",
  failed: "失敗",
  running: "実行中",
  submitted: "送信済",
};

function StatusBadge({ status }: { status: string }) {
  const danger = status === "refused" || status === "failed";
  return (
    <span
      className={
        danger
          ? "rounded-full bg-seal-wash px-3 py-1 text-xs font-semibold text-seal-deep"
          : "rounded-full bg-phosphor/10 px-3 py-1 text-xs font-semibold text-phosphor"
      }
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

export default function ApprovalCard({ result }: { result: TaskPlan }) {
  const [tab, setTab] = useState<TabKey>("analysis");
  const { task, plan, refusal } = result;

  return (
    <section className="overflow-hidden rounded-card border border-line bg-paper-panel shadow-card">
      <header className="flex items-center gap-3 border-b border-line px-5 py-4">
        <div className="grid h-9 w-9 place-items-center rounded-md bg-ink font-mono text-xs font-bold text-paper-panel">
          稟
        </div>
        <div>
          <div className="text-sm font-bold tracking-tight text-ink">出張申請 承認カード</div>
          <div className="font-mono text-[11px] text-ink-faint">
            task #{task.id} · workflow {task.workflow}
          </div>
        </div>
        <div className="ml-auto">
          <StatusBadge status={task.status} />
        </div>
      </header>

      <div className="px-5 pt-3">
        <p className="mb-3 rounded-lg bg-paper-sunk px-3 py-2 text-sm text-ink-soft">{task.instruction}</p>
      </div>

      {plan ? (
        <>
          <div className="px-5">
            <div className="inline-flex rounded-lg border border-line bg-paper p-1">
              {TABS.map((entry) => (
                <button
                  key={entry.key}
                  type="button"
                  onClick={() => setTab(entry.key)}
                  className={
                    tab === entry.key
                      ? "relative rounded-md px-4 py-1.5 text-sm font-semibold text-ink"
                      : "relative rounded-md px-4 py-1.5 text-sm font-medium text-ink-faint transition-colors hover:text-ink-soft"
                  }
                >
                  {tab === entry.key ? (
                    <motion.span
                      layoutId="tab-pill"
                      className="absolute inset-0 rounded-md bg-paper-panel shadow-sm"
                      transition={{ type: "spring", stiffness: 420, damping: 34 }}
                    />
                  ) : null}
                  <span className="relative">{entry.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="min-h-[16rem] px-5 py-4">
            <AnimatePresence mode="wait">
              <motion.div
                key={tab}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.16, ease: "easeOut" }}
              >
                {tab === "analysis" ? <AnalysisTab slots={plan.analysis} /> : null}
                {tab === "plan" ? <PlanTab steps={plan.keysequence} /> : null}
                {tab === "grounds" ? <GroundsTab grounding={plan.grounding} /> : null}
              </motion.div>
            </AnimatePresence>
          </div>

          <ActionBar />
        </>
      ) : refusal ? (
        <div className="px-5 pb-6">
          <div className="rounded-lg border border-seal/40 bg-seal-wash/50 p-4">
            <div className="mb-2 text-sm font-bold text-seal-deep">この申請は実行できません</div>
            <p className="mb-3 text-sm text-ink-soft">{refusal.reason}</p>
            <div className="flex flex-wrap gap-2">
              {refusal.missing_fields.map((field) => (
                <span
                  key={field}
                  className="rounded bg-paper-panel px-2 py-1 font-mono text-xs font-semibold text-seal-deep"
                >
                  {field}
                </span>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="px-5 pb-6">
          <div className="rounded-lg border border-line bg-paper-sunk p-4 text-sm text-ink-soft">
            計画を生成できませんでした（指示の解析に失敗しました）。
          </div>
        </div>
      )}
    </section>
  );
}
