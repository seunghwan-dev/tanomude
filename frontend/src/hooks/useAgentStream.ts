import { useEffect, useState } from "react";

import { getTask, type Envelope, type TaskStep } from "../api";

export interface ExecutionState {
  status: string;
  tripId: number | null;
  badData: boolean;
  finished: boolean;
}

export interface AgentStream {
  steps: TaskStep[];
  taskStatus: string | null;
  execution: ExecutionState | null;
  connected: boolean;
}

const FINAL_STATUSES = ["submitted", "rolled_back", "errored", "refused", "verify_failed", "parse_failed"];

function stepKey(step: TaskStep): string {
  return `${step.execution_id}:${step.ordinal}`;
}

export function useAgentStream(taskId: number | null, initialStatus: string | null): AgentStream {
  const [steps, setSteps] = useState<Map<string, TaskStep>>(new Map());
  const [taskStatus, setTaskStatus] = useState<string | null>(initialStatus);
  const [execution, setExecution] = useState<ExecutionState | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (taskId === null) {
      return;
    }
    const activeId = taskId;
    let stopped = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | undefined;
    let attempt = 0;

    setSteps(new Map());
    setTaskStatus(initialStatus);
    setExecution(null);

    async function snapshot() {
      try {
        const detail = await getTask(activeId);
        if (stopped) {
          return;
        }
        setTaskStatus(detail.status);
        setSteps((prev) => {
          const next = new Map(prev);
          for (const exec of detail.executions) {
            for (const step of exec.steps) {
              next.set(stepKey(step), step);
            }
          }
          return next;
        });
        const last = detail.executions[detail.executions.length - 1];
        if (last && FINAL_STATUSES.includes(last.status)) {
          setExecution({
            status: last.status,
            tripId: last.trip_id,
            badData: last.correction_candidate?.bad_data ?? false,
            finished: true,
          });
        }
      } catch {
        if (!stopped) {
          setConnected(false);
        }
      }
    }

    function handle(envelope: Envelope) {
      if (envelope.task_id !== activeId) {
        return;
      }
      if (envelope.type === "step_executed") {
        const step = envelope.payload as unknown as TaskStep;
        if (typeof step.execution_id === "number" && typeof step.ordinal === "number") {
          setSteps((prev) => new Map(prev).set(stepKey(step), step));
        }
        return;
      }
      if (envelope.type === "status_changed") {
        const status = envelope.payload.status as string | undefined;
        if (status) {
          setTaskStatus(status);
        }
        return;
      }
      if (envelope.type === "execution_finished") {
        void snapshot();
      }
    }

    function connect() {
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${window.location.host}/ws/agent`);
      socket = ws;
      ws.onopen = () => {
        if (stopped || ws !== socket) {
          return;
        }
        attempt = 0;
        setConnected(true);
        void snapshot();
      };
      ws.onmessage = (event) => {
        if (ws !== socket) {
          return;
        }
        let envelope: Envelope;
        try {
          envelope = JSON.parse(event.data) as Envelope;
        } catch {
          return;
        }
        handle(envelope);
      };
      ws.onclose = () => {
        if (stopped || ws !== socket) {
          return;
        }
        setConnected(false);
        attempt += 1;
        const delay = Math.min(1500 * 2 ** (attempt - 1), 15000);
        if (reconnectTimer) {
          window.clearTimeout(reconnectTimer);
        }
        reconnectTimer = window.setTimeout(connect, delay);
      };
      ws.onerror = () => ws.close();
    }

    connect();

    return () => {
      stopped = true;
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
      }
      socket?.close();
    };
  }, [taskId]);

  const ordered = Array.from(steps.values()).sort((a, b) =>
    a.execution_id === b.execution_id ? a.ordinal - b.ordinal : a.execution_id - b.execution_id,
  );

  return { steps: ordered, taskStatus, execution, connected };
}
