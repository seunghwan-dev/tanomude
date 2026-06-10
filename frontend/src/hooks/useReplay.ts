import { useEffect, useRef, useState } from "react";

import type { TaskStep } from "../api";
import { type ExecutionState, useAgentStream } from "./useAgentStream";

const REPLAY_STEP_MS = 700;
const LIVE_STEP_MS = 350;
const FINAL_STATUSES = ["submitted", "rolled_back", "errored", "refused", "verify_failed", "parse_failed"];

function stepKey(step: TaskStep): string {
  return `${step.execution_id}:${step.ordinal}`;
}

export interface Replay {
  steps: TaskStep[];
  taskStatus: string | null;
  execution: ExecutionState | null;
  connected: boolean;
  cursor: number;
  selected: TaskStep | null;
  activeKey: string | null;
  playing: boolean;
  fast: boolean;
  play: () => void;
  stop: () => void;
  live: () => void;
  select: (step: TaskStep) => void;
}

export function useReplay(taskId: number | null, initialStatus: string): Replay {
  const { steps, taskStatus, execution, connected } = useAgentStream(taskId, initialStatus);
  const startedFinal = FINAL_STATUSES.includes(initialStatus);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [pinned, setPinned] = useState(false);
  const lengthRef = useRef(0);
  lengthRef.current = steps.length;

  useEffect(() => {
    setCursor(0);
    setPlaying(false);
    setPinned(false);
  }, [taskId]);

  useEffect(() => {
    setCursor((current) => Math.min(current, Math.max(steps.length - 1, 0)));
  }, [steps.length]);

  useEffect(() => {
    if (startedFinal && !playing && !pinned && steps.length > 0) {
      setCursor(steps.length - 1);
    }
  }, [startedFinal, playing, pinned, steps.length]);

  useEffect(() => {
    if (!playing) {
      return;
    }
    const id = window.setInterval(() => {
      setCursor((current) => (current >= lengthRef.current - 1 ? current : current + 1));
    }, REPLAY_STEP_MS);
    return () => window.clearInterval(id);
  }, [playing]);

  useEffect(() => {
    if (playing && steps.length > 0 && cursor >= steps.length - 1) {
      setPlaying(false);
      setPinned(true);
    }
  }, [playing, cursor, steps.length]);

  useEffect(() => {
    if (playing || pinned || startedFinal) {
      return;
    }
    const id = window.setInterval(() => {
      setCursor((current) => (current >= lengthRef.current - 1 ? current : current + 1));
    }, LIVE_STEP_MS);
    return () => window.clearInterval(id);
  }, [playing, pinned, startedFinal]);

  const safeCursor = Math.min(cursor, Math.max(steps.length - 1, 0));
  const selected = steps[safeCursor] ?? null;
  const activeKey = selected ? stepKey(selected) : null;

  function select(step: TaskStep) {
    setPlaying(false);
    setPinned(true);
    const index = steps.findIndex((entry) => stepKey(entry) === stepKey(step));
    if (index >= 0) {
      setCursor(index);
    }
  }

  function play() {
    if (steps.length === 0) {
      return;
    }
    setPinned(false);
    if (cursor >= steps.length - 1) {
      setCursor(0);
    }
    setPlaying(true);
  }

  function stop() {
    setPlaying(false);
    setPinned(true);
  }

  function live() {
    setPlaying(false);
    setPinned(false);
    setCursor(Math.max(steps.length - 1, 0));
  }

  return {
    steps,
    taskStatus,
    execution,
    connected,
    cursor: safeCursor,
    selected,
    activeKey,
    playing,
    fast: !playing && !pinned && !startedFinal,
    play,
    stop,
    live,
    select,
  };
}
