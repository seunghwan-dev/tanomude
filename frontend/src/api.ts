export interface Slots {
  dest_code: string;
  purpose: string;
  overseas: boolean;
  reuse_prev_proj: boolean;
}

export interface Step {
  seq: number;
  type: "field" | "fkey" | "nav";
  target: string | null;
  value: string | null;
  key: string | null;
}

export interface Grounding {
  chunk_id: number;
  doc_id: number;
  section: string;
  heading: string;
  text: string;
  score: number;
  rank: number;
}

export interface Plan {
  id: number;
  task_id: number;
  version: number;
  analysis: Slots;
  keysequence: Step[];
  grounding: Grounding[];
  status: string;
  created_at: string;
}

export interface Refusal {
  reason: string;
  missing_fields: string[];
}

export interface TaskView {
  id: number;
  workflow: string;
  instruction: string;
  status: string;
}

export interface TaskPlan {
  task: TaskView;
  plan: Plan | null;
  refusal: Refusal | null;
}

export interface PlanRequest {
  workflow: string;
  instruction: string;
  fields: Record<string, string>;
}

export async function planTask(request: PlanRequest): Promise<TaskPlan> {
  const response = await fetch("/api/tasks/plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(`計画リクエストに失敗しました (HTTP ${response.status})`);
  }
  return (await response.json()) as TaskPlan;
}
