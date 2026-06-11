import type { Grounding, Plan, PlanRequest, Slots, Step, TaskPlan, TaskStep, TaskView } from "../src/api";

export const DEFAULT_TRIP_ID = 4087;

const PLAN_CREATED_AT = "2026-06-10T09:11:58Z";

export const KEY_SEQUENCE: Step[] = [
  { seq: 1, type: "nav", target: null, value: null, key: "Enter" },
  { seq: 2, type: "field", target: "DEST", value: "OSAKA", key: null },
  { seq: 3, type: "field", target: "DEPTDATE", value: "20260610", key: null },
  { seq: 4, type: "field", target: "RETDATE", value: "20260611", key: null },
  { seq: 5, type: "field", target: "DAYS", value: "2", key: null },
  { seq: 6, type: "field", target: "PURPOSE", value: "製品X納入調整", key: null },
  { seq: 7, type: "fkey", target: null, value: null, key: "F4" },
  { seq: 8, type: "field", target: "PROJ", value: "P-001", key: null },
  { seq: 9, type: "fkey", target: null, value: null, key: "Enter" },
  { seq: 10, type: "fkey", target: null, value: null, key: "Enter" },
];

const SCREENS = [
  "menu",
  "trip_input",
  "trip_input",
  "trip_input",
  "trip_input",
  "trip_input",
  "proj_prompt",
  "trip_input",
  "confirm",
  "submitted",
];

const INTENTS = [
  "画面遷移",
  "目的地コード入力",
  "出発日入力",
  "帰着日入力",
  "日数入力",
  "目的入力",
  "案件コード選択",
  "案件コード入力",
  "確定",
  "確定",
];

const CREATED_AT = [
  "2026-06-10T09:12:01Z",
  "2026-06-10T09:12:03Z",
  "2026-06-10T09:12:05Z",
  "2026-06-10T09:12:07Z",
  "2026-06-10T09:12:09Z",
  "2026-06-10T09:12:12Z",
  "2026-06-10T09:12:15Z",
  "2026-06-10T09:12:18Z",
  "2026-06-10T09:12:21Z",
  "2026-06-10T09:12:24Z",
];

export function buildSteps(executionId: number): TaskStep[] {
  const fields: Record<string, string> = {};
  const steps: TaskStep[] = [];
  for (let i = 0; i < KEY_SEQUENCE.length; i += 1) {
    const action = KEY_SEQUENCE[i];
    if (action.type === "field" && action.target) {
      fields[action.target] = action.value ?? "";
    }
    steps.push({
      id: executionId * 100 + i + 1,
      execution_id: executionId,
      ordinal: i + 1,
      intent: INTENTS[i],
      action,
      screen: SCREENS[i],
      screen_fields: { ...fields },
      status: "ok",
      errors: null,
      created_at: CREATED_AT[i],
    });
  }
  return steps;
}

const GROUNDING: Grounding[] = [
  {
    chunk_id: 1,
    doc_id: 1,
    section: "2. 入力フィールド",
    heading: "2.1 出張先 (DEST)",
    text: "半角英大文字の都市コードで入力する。最大12文字。必須項目。",
    score: 0.912,
    rank: 1,
  },
  {
    chunk_id: 2,
    doc_id: 1,
    section: "2. 入力フィールド",
    heading: "2.5 案件コード (PROJ)",
    text: "形式は P-### の5文字。直接入力せず F4 プロンプトで一覧から選択する。",
    score: 0.873,
    rank: 2,
  },
  {
    chunk_id: 3,
    doc_id: 1,
    section: "4. 標準手順",
    heading: "4. 標準手順",
    text: "メニューで「出張申請」を選択し、各フィールドを入力後、実行キーで確定・送信する。",
    score: 0.841,
    rank: 3,
  },
];

export function buildPlan(taskId: number, request: PlanRequest): TaskPlan {
  const task: TaskView = {
    id: taskId,
    workflow: request.workflow,
    instruction: request.instruction,
    fields: request.fields,
    status: "awaiting_approval",
  };
  const analysis: Slots = {
    dest_code: "OSAKA",
    purpose: "製品X納入調整",
    overseas: false,
    reuse_prev_proj: false,
  };
  const plan: Plan = {
    id: taskId,
    task_id: taskId,
    version: 1,
    analysis,
    keysequence: KEY_SEQUENCE,
    grounding: GROUNDING,
    status: "ready",
    created_at: PLAN_CREATED_AT,
  };
  return { task, plan, refusal: null };
}
