import { useMemo, useRef, useState } from "react";

import { approveTask, DecisionError, planTask, rejectTask, reviseTask, type PlanRequest, type TaskPlan } from "./api";
import type { DecisionKind } from "./components/ActionBar";
import ApprovalCard from "./components/ApprovalCard";
import ExecutionPanel from "./components/ExecutionPanel";
import { planDedupKey, sessionNonce } from "./lib/dedup";

const APPROVER = "operator";

function TextField(props: { label: string; value: string; onChange: (value: string) => void; mono?: boolean }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-semibold text-ink-soft">{props.label}</span>
      <input
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
        className={`w-full rounded-lg border border-line bg-paper-panel px-3 py-2 text-sm text-ink focus:border-ink-soft focus:outline-none ${
          props.mono ? "font-mono" : ""
        }`}
      />
    </label>
  );
}

export default function App() {
  const workflow = "shukko";
  const [instruction, setInstruction] = useState("製品Xの納入調整のため大阪へ出張する。");
  const [dest, setDest] = useState("大阪");
  const [deptDate, setDeptDate] = useState("2026-06-10");
  const [retDate, setRetDate] = useState("2026-06-11");
  const [projHint, setProjHint] = useState("P-001");

  const [result, setResult] = useState<TaskPlan | null>(null);
  const [activeRequest, setActiveRequest] = useState<PlanRequest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [pending, setPending] = useState<DecisionKind | null>(null);
  const [decided, setDecided] = useState<"approved" | "rejected" | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<string | null>(null);

  const nonce = useMemo(() => sessionNonce(), []);
  const generatedKeys = useRef<Set<string>>(new Set());

  async function generate(request: PlanRequest): Promise<TaskPlan | null> {
    const dedupKey = planDedupKey(nonce, request);
    if (generatedKeys.current.has(dedupKey) && result) {
      setError("同じ内容の計画は生成済みです。修正または入力を変更してから再生成してください。");
      return null;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await planTask({ ...request, dedup_key: dedupKey });
      generatedKeys.current.add(dedupKey);
      setResult(data);
      setActiveRequest(request);
      setPending(null);
      setDecided(null);
      setDecisionError(null);
      setLiveStatus(null);
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : "不明なエラーが発生しました");
      return null;
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (loading || pending) {
      return;
    }
    void generate({
      workflow,
      instruction,
      fields: { dest, dept_date: deptDate, ret_date: retDate, proj_hint: projHint },
    });
  }

  async function onApprove() {
    if (!result || pending) {
      return;
    }
    setPending("approve");
    setDecisionError(null);
    setLiveStatus("running");
    try {
      const detail = await approveTask(result.task.id, { approver: APPROVER });
      setLiveStatus(detail.status);
      setDecided("approved");
    } catch (err) {
      if (err instanceof DecisionError && err.responded) {
        setLiveStatus("failed");
        setDecided("approved");
      } else {
        setLiveStatus(null);
        setDecisionError(err instanceof Error ? err.message : "承認に失敗しました");
      }
    } finally {
      setPending(null);
    }
  }

  async function onReject(reason: string) {
    if (!result || pending) {
      return;
    }
    setPending("reject");
    setDecisionError(null);
    try {
      const detail = await rejectTask(result.task.id, {
        approver: APPROVER,
        decision_text: reason || undefined,
      });
      setLiveStatus(detail.status);
      setDecided("rejected");
    } catch (err) {
      setDecisionError(err instanceof Error ? err.message : "却下に失敗しました");
    } finally {
      setPending(null);
    }
  }

  async function onRevise(text: string) {
    if (!result || !activeRequest || pending) {
      return;
    }
    setPending("revise");
    setDecisionError(null);
    try {
      await reviseTask(result.task.id, { approver: APPROVER, decision_text: text });
    } catch (err) {
      setDecisionError(err instanceof Error ? err.message : "修正の送信に失敗しました");
      setPending(null);
      return;
    }
    const revised: PlanRequest = {
      ...activeRequest,
      instruction: `${activeRequest.instruction}\n\n【修正指示】${text}`,
    };
    const next = await generate(revised);
    if (!next) {
      setPending(null);
    }
  }

  const cardStatus = liveStatus ?? result?.task.status ?? "";
  const showPanel = Boolean(result?.plan) && decided !== "rejected";

  return (
    <div className="mx-auto max-w-3xl px-5 py-10">
      <header className="mb-8 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">
            tanomude<span className="text-seal">.</span>
          </h1>
          <p className="text-sm text-ink-faint">基幹系オペレーション 承認コンソール</p>
        </div>
        <div className="flex items-center gap-2 font-mono text-[11px] text-ink-faint">
          <span className="h-2 w-2 rounded-full bg-phosphor" />
          AS-400 / 出張申請
        </div>
      </header>

      <form onSubmit={onSubmit} className="mb-8 rounded-card border border-line bg-paper-panel p-5 shadow-card">
        <label className="mb-4 block">
          <span className="mb-1 block text-xs font-semibold text-ink-soft">指示</span>
          <textarea
            value={instruction}
            onChange={(event) => setInstruction(event.target.value)}
            rows={2}
            className="w-full resize-none rounded-lg border border-line bg-paper-panel px-3 py-2 text-sm text-ink focus:border-ink-soft focus:outline-none"
          />
        </label>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <TextField label="出張先" value={dest} onChange={setDest} />
          <TextField label="出発日" value={deptDate} onChange={setDeptDate} mono />
          <TextField label="帰着日" value={retDate} onChange={setRetDate} mono />
          <TextField label="案件コード" value={projHint} onChange={setProjHint} mono />
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button
            type="submit"
            disabled={loading || pending !== null}
            className="rounded-lg bg-ink px-5 py-2.5 text-sm font-semibold text-paper-panel transition-colors hover:bg-ink-soft disabled:opacity-50"
          >
            {loading ? "生成中…" : "計画を生成"}
          </button>
          {error ? <span className="text-sm text-seal-deep">{error}</span> : null}
        </div>
      </form>

      {result ? (
        <>
          <ApprovalCard
            key={`card-${result.task.id}`}
            result={result}
            status={cardStatus}
            pending={pending}
            decided={decided}
            error={decisionError}
            onApprove={onApprove}
            onRevise={onRevise}
            onReject={onReject}
          />
          {showPanel ? (
            <ExecutionPanel key={`panel-${result.task.id}`} taskId={result.task.id} initialStatus={result.task.status} />
          ) : null}
        </>
      ) : (
        <div className="rounded-card border border-dashed border-line bg-paper-panel/50 px-5 py-16 text-center text-sm text-ink-faint">
          指示を入力し「計画を生成」を押すと、承認カードが表示されます。
        </div>
      )}
    </div>
  );
}
