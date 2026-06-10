import { useEffect, useMemo, useRef, useState } from "react";

import { approveTask, DecisionError, getTask, getTaskPlan, planTask, rejectTask, reviseTask, type PlanRequest, type TaskDetail, type TaskPlan } from "./api";
import type { DecisionKind } from "./components/ActionBar";
import ApprovalCard from "./components/ApprovalCard";
import As400Screen from "./components/As400Screen";
import ExecutionPanel from "./components/ExecutionPanel";
import { useReplay } from "./hooks/useReplay";
import { planDedupKey, sessionNonce } from "./lib/dedup";
import { isVoiceSupported, setVoiceMuted, voiceOutcome, voicePlanReady, voicePlanRefused, voicePlanUnreadable } from "./lib/voice";

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
  const workflow = "shutchou";
  const [instruction, setInstruction] = useState("製品Xの納入調整のため大阪へ出張する。");
  const [dest, setDest] = useState("大阪");
  const [deptDate, setDeptDate] = useState("2026-06-10");
  const [retDate, setRetDate] = useState("2026-06-11");
  const [projHint, setProjHint] = useState("P-001");

  const [result, setResult] = useState<TaskPlan | null>(null);
  const [restored, setRestored] = useState<TaskDetail | null>(null);
  const [activeRequest, setActiveRequest] = useState<PlanRequest | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [pending, setPending] = useState<DecisionKind | null>(null);
  const [decided, setDecided] = useState<"approved" | "rejected" | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<string | null>(null);
  const [reviseNotice, setReviseNotice] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);

  const nonce = useMemo(() => sessionNonce(), []);
  const voiceSupported = useMemo(() => isVoiceSupported(), []);
  const generatedKeys = useRef<Set<string>>(new Set());

  useEffect(() => {
    const param = new URLSearchParams(window.location.search).get("task");
    if (!param) {
      return;
    }
    const taskId = Number(param);
    if (!Number.isInteger(taskId) || taskId <= 0) {
      return;
    }
    let active = true;
    getTask(taskId)
      .then((detail) => {
        if (!active) {
          return;
        }
        if (detail.status !== "awaiting_approval") {
          setRestored(detail);
          return;
        }
        return getTaskPlan(taskId).then((restoredPlan) => {
          if (!active || !restoredPlan.plan) {
            return;
          }
          setResult(restoredPlan);
          setActiveRequest({
            workflow: restoredPlan.task.workflow,
            instruction: restoredPlan.task.instruction,
            fields: restoredPlan.task.fields,
          });
        });
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!result) {
      return;
    }
    const taskId = result.task.id;
    if (result.plan) {
      voicePlanReady(taskId);
    } else if (result.refusal) {
      voicePlanRefused(taskId);
    } else {
      voicePlanUnreadable(taskId);
    }
  }, [result]);

  const showPanel = Boolean(result?.plan) && decided !== "rejected";
  const replaySource = showPanel ? result?.task ?? null : restored;
  const panelTaskId = replaySource ? replaySource.id : null;
  const panelInitialStatus = replaySource?.status ?? "";
  const replay = useReplay(panelTaskId, panelInitialStatus);

  useEffect(() => {
    const exec = replay.execution;
    if (!exec?.finished || exec.taskId !== panelTaskId) {
      return;
    }
    voiceOutcome(exec.taskId, exec.tripId, exec.badData);
  }, [panelTaskId, replay.execution]);

  function toggleMute() {
    const next = !muted;
    setMuted(next);
    setVoiceMuted(next);
  }

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
      setRestored(null);
      window.history.replaceState(null, "", `?task=${data.task.id}`);
      setActiveRequest(request);
      setPending(null);
      setDecided(null);
      setDecisionError(null);
      setLiveStatus(null);
      setReviseNotice(null);
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
    setReviseNotice(null);
    let detail: TaskDetail;
    try {
      detail = await reviseTask(result.task.id, { approver: APPROVER, decision_text: text });
    } catch (err) {
      setDecisionError(err instanceof Error ? err.message : "修正の送信に失敗しました");
      setPending(null);
      return;
    }
    if (detail.revise_notice) {
      setReviseNotice(detail.revise_notice);
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

  return (
    <div className="mx-auto max-w-6xl px-5 py-10">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        <aside className="lg:sticky lg:top-6 lg:w-[38%] lg:flex-none">
          <As400Screen steps={replay.steps} cursor={replay.cursor} tripId={replay.execution?.tripId ?? null} fast={replay.fast} />
        </aside>

        <main className="min-w-0 flex-1">
          <header className="mb-8 flex items-end justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-ink">
                tanomude<span className="text-seal">.</span>
              </h1>
              <p className="text-sm text-ink-faint">基幹系オペレーション 承認コンソール</p>
            </div>
            <div className="flex items-center gap-3">
              {voiceSupported ? (
                <button
                  type="button"
                  onClick={toggleMute}
                  aria-pressed={muted}
                  className="flex items-center gap-1.5 rounded-md border border-line bg-paper px-2.5 py-1 font-mono text-[11px] text-ink-faint transition-colors hover:bg-paper-sunk hover:text-ink"
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${muted ? "bg-ink-faint" : "bg-phosphor"}`} />
                  {muted ? "音声 OFF" : "音声 ON"}
                </button>
              ) : null}
              <div className="flex items-center gap-2 font-mono text-[11px] text-ink-faint">
                <span className="h-2 w-2 rounded-full bg-phosphor" />
                AS-400 / 出張申請
              </div>
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
              {reviseNotice ? (
                <div className="mb-4 rounded-lg border border-seal/40 bg-seal-wash/50 px-4 py-3 text-sm text-seal-deep">
                  {reviseNotice}
                </div>
              ) : null}
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
              {showPanel ? <ExecutionPanel replay={replay} /> : null}
            </>
          ) : restored ? (
            <div>
              <div className="mb-3 flex items-center gap-2 font-mono text-[11px] text-ink-faint">
                <span className="h-2 w-2 rounded-full bg-phosphor" />
                復元したタスク · task #{restored.id}
              </div>
              <ExecutionPanel replay={replay} />
            </div>
          ) : (
            <div className="rounded-card border border-dashed border-line bg-paper-panel/50 px-5 py-16 text-center text-sm text-ink-faint">
              指示を入力し「計画を生成」を押すと、承認カードが表示されます。
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
