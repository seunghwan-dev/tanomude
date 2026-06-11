import { useEffect, useState } from "react";

import type { AgentStream } from "../src/hooks/useAgentStream";
import { snapshot, subscribe } from "./mockStore";

export type { AgentStream, ExecutionState } from "../src/hooks/useAgentStream";

export function useAgentStream(taskId: number | null, _initialStatus: string | null): AgentStream {
  const [snap, setSnap] = useState(() => snapshot(taskId ?? -1));

  useEffect(() => {
    if (taskId === null) {
      setSnap(snapshot(-1));
      return;
    }
    setSnap(snapshot(taskId));
    return subscribe(taskId, () => setSnap(snapshot(taskId)));
  }, [taskId]);

  return {
    steps: snap.steps,
    taskStatus: snap.status,
    execution: snap.execution,
    connected: snap.connected,
  };
}
