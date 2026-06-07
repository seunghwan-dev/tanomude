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
  fields: Record<string, string | boolean>;
  status: string;
}

export interface TaskPlan {
  task: TaskView;
  plan: Plan | null;
  refusal: Refusal | null;
}

export interface TaskStep {
  id: number;
  execution_id: number;
  ordinal: number;
  intent: string;
  action: Step;
  screen: string | null;
  screen_fields: Record<string, string>;
  status: "ok" | "error";
  errors: string[] | null;
  created_at: string;
}

export interface CorrectionCandidate {
  screen: string | null;
  expected: string;
  diffs: string[];
  replan_count: number;
  bad_data: boolean;
}

export interface Execution {
  id: number;
  attempt_no: number;
  status: string;
  final_screen: string | null;
  trip_id: number | null;
  trip_created: boolean | null;
  executed_steps: number;
  errors: string[] | null;
  correction_candidate: CorrectionCandidate | null;
  steps: TaskStep[];
}

export interface TaskDetail {
  id: number;
  workflow: string;
  instruction: string;
  fields: Record<string, string | boolean>;
  status: string;
  executions: Execution[];
}

export type EventType =
  | "task_created"
  | "execution_started"
  | "execution_finished"
  | "status_changed"
  | "step_executed"
  | "plan_ready"
  | "approved"
  | "rejected"
  | "revised";

export interface Envelope {
  type: EventType;
  task_id: number;
  seq: number;
  ts: string;
  payload: Record<string, unknown>;
}

export interface PlanRequest {
  workflow: string;
  instruction: string;
  fields: Record<string, string | boolean>;
  dedup_key?: string;
}

export interface DecisionRequest {
  approver: string;
  decision_text?: string;
}

export async function getTask(taskId: number): Promise<TaskDetail> {
  const response = await fetch(`/api/tasks/${taskId}`);
  if (!response.ok) {
    throw new Error(`タスク取得に失敗しました (HTTP ${response.status})`);
  }
  return (await response.json()) as TaskDetail;
}

export async function getTaskPlan(taskId: number): Promise<TaskPlan> {
  const response = await fetch(`/api/tasks/${taskId}/plan`);
  if (!response.ok) {
    throw new Error(`計画の取得に失敗しました (HTTP ${response.status})`);
  }
  return (await response.json()) as TaskPlan;
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

const DECISION_LABELS: Record<string, string> = {
  approve: "承認",
  reject: "却下",
  revise: "修正",
};

export class DecisionError extends Error {
  readonly responded: boolean;

  constructor(message: string, responded: boolean) {
    super(message);
    this.responded = responded;
  }
}

async function postDecision(taskId: number, action: string, body: DecisionRequest): Promise<TaskDetail> {
  const label = DECISION_LABELS[action] ?? action;
  let response: Response;
  try {
    response = await fetch(`/api/tasks/${taskId}/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new DecisionError(`${label}に失敗しました（通信エラー）`, false);
  }
  if (!response.ok) {
    throw new DecisionError(`${label}に失敗しました (HTTP ${response.status})`, true);
  }
  return (await response.json()) as TaskDetail;
}

export function approveTask(taskId: number, body: DecisionRequest): Promise<TaskDetail> {
  return postDecision(taskId, "approve", body);
}

export function rejectTask(taskId: number, body: DecisionRequest): Promise<TaskDetail> {
  return postDecision(taskId, "reject", body);
}

export function reviseTask(taskId: number, body: DecisionRequest): Promise<TaskDetail> {
  return postDecision(taskId, "revise", body);
}
