import { useEffect, useRef, useState } from "react";

import type { TaskStep } from "../api";
import { useAgentStream } from "../hooks/useAgentStream";
import { voiceOutcome } from "../lib/voice";
import Inspector from "./Inspector";
import Timeline from "./Timeline";

const STATUS_LABELS: Record<string, string> = {
  awaiting_approval: "承認待ち",
  running: "実行中",
  submitted: "送信済",
  rolled_back: "ロールバック",
  refused: "却下",
  failed: "失敗",
  errored: "エラー",
};

function stepKey(step: TaskStep): string {
  return `${step.execution_id}:${step.ordinal}`;
}

export default function ExecutionPanel({ taskId, initialStatus }: { taskId: number; initialStatus: string }) {
  const { steps, taskStatus, execution, connected } = useAgentStream(taskId, initialStatus);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [pinned, setPinned] = useState(false);
  const lengthRef = useRef(0);
  lengthRef.current = steps.length;

  useEffect(() => {
    if (!execution?.finished) {
      return;
    }
    voiceOutcome(taskId, execution.tripId, execution.badData);
  }, [taskId, execution]);

  useEffect(() => {
    setCursor((current) => Math.min(current, Math.max(steps.length - 1, 0)));
  }, [steps.length]);

  useEffect(() => {
    if (!playing && !pinned && steps.length > 0) {
      setCursor(steps.length - 1);
    }
  }, [steps.length, playing, pinned]);

  useEffect(() => {
    if (!playing) {
      return;
    }
    const id = window.setInterval(() => {
      setCursor((current) => (current >= lengthRef.current - 1 ? current : current + 1));
    }, 700);
    return () => window.clearInterval(id);
  }, [playing]);

  useEffect(() => {
    if (playing && steps.length > 0 && cursor >= steps.length - 1) {
      setPlaying(false);
      setPinned(true);
    }
  }, [playing, cursor, steps.length]);

  const safeCursor = Math.min(cursor, Math.max(steps.length - 1, 0));
  const selected = steps[safeCursor] ?? null;
  const activeKey = selected ? stepKey(selected) : null;

  function onSelect(step: TaskStep) {
    setPlaying(false);
    setPinned(true);
    const index = steps.findIndex((entry) => stepKey(entry) === stepKey(step));
    if (index >= 0) {
      setCursor(index);
    }
  }

  function onPlay() {
    if (steps.length === 0) {
      return;
    }
    setPinned(false);
    if (cursor >= steps.length - 1) {
      setCursor(0);
    }
    setPlaying(true);
  }

  function onLive() {
    setPlaying(false);
    setPinned(false);
    setCursor(Math.max(steps.length - 1, 0));
  }

  return (
    <section className="mt-6 overflow-hidden rounded-card border border-line bg-paper-panel shadow-card">
      <header className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-4">
        <div className="text-sm font-bold tracking-tight text-ink">実行タイムライン</div>
        <span className="flex items-center gap-1.5 font-mono text-[11px] text-ink-faint">
          <span className={`h-2 w-2 rounded-full ${connected ? "bg-phosphor" : "bg-ink-faint"}`} />
          {connected ? "LIVE" : "接続中…"}
        </span>
        <span className="rounded-full bg-paper-sunk px-3 py-1 text-xs font-semibold text-ink-soft">
          {STATUS_LABELS[taskStatus ?? ""] ?? taskStatus ?? "—"}
        </span>
        {execution?.finished ? (
          execution.tripId !== null ? (
            <span className="rounded-full bg-phosphor/10 px-3 py-1 font-mono text-xs font-semibold text-phosphor">
              trip #{execution.tripId}
            </span>
          ) : execution.badData ? (
            <span className="rounded-full bg-seal-wash px-3 py-1 text-xs font-semibold text-seal-deep">
              不正データ・育成候補
            </span>
          ) : (
            <span className="rounded-full border border-line bg-paper px-3 py-1 text-xs font-semibold text-ink-soft">
              要調査
            </span>
          )
        ) : null}

        <div className="ml-auto flex items-center gap-1">
          {playing ? (
            <button
              type="button"
              onClick={() => setPlaying(false)}
              className="rounded-md border border-line bg-paper px-3 py-1.5 text-xs font-semibold text-ink hover:bg-paper-sunk"
            >
              停止
            </button>
          ) : (
            <button
              type="button"
              onClick={onPlay}
              disabled={steps.length === 0}
              className="rounded-md border border-line bg-paper px-3 py-1.5 text-xs font-semibold text-ink hover:bg-paper-sunk disabled:opacity-40"
            >
              再生
            </button>
          )}
          <button
            type="button"
            onClick={onLive}
            disabled={steps.length === 0}
            className="rounded-md px-3 py-1.5 text-xs font-medium text-ink-faint hover:bg-paper-sunk hover:text-ink disabled:opacity-40"
          >
            ライブ
          </button>
          <span className="ml-1 font-mono text-[11px] text-ink-faint">
            {steps.length === 0 ? "0/0" : `${safeCursor + 1}/${steps.length}`}
          </span>
        </div>
      </header>

      {execution?.finished && execution.tripId === null ? (
        <div
          className={
            execution.badData
              ? "border-b border-line bg-seal-wash/40 px-5 py-3"
              : "border-b border-line bg-paper-sunk px-5 py-3"
          }
        >
          {execution.badData ? (
            <p className="text-sm text-seal-deep">
              <span className="font-semibold">育成候補：</span>
              不正データのため差し戻されました。ここでの人手の修正は、次回の同種作業の個人修正（personal_correction）として育成に活かされます。
            </p>
          ) : (
            <p className="text-sm text-ink-soft">
              <span className="font-semibold">要調査：</span>
              再試行を尽くしても画面状態が整合せず差し戻されました。データの誤りではなく、一時的・実行環境側の事象として調査が必要です。
            </p>
          )}
        </div>
      ) : null}

      <div className="grid gap-4 p-5 md:grid-cols-12">
        <div className="max-h-[24rem] overflow-y-auto md:col-span-5">
          <Timeline steps={steps} activeKey={activeKey} onSelect={onSelect} />
        </div>
        <div className="rounded-lg border border-line/70 bg-paper p-4 md:col-span-7">
          <Inspector step={selected} />
        </div>
      </div>
    </section>
  );
}
