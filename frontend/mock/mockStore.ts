import type { Execution, PlanRequest, TaskDetail, TaskPlan, TaskStep } from "../src/api";
import type { ExecutionState } from "../src/hooks/useAgentStream";
import { buildPlan, buildSteps, DEFAULT_TRIP_ID } from "./mockData";

export interface StreamSnapshot {
  steps: TaskStep[];
  status: string;
  execution: ExecutionState | null;
  connected: boolean;
}

const PLAN_LATENCY = 900;
const APPROVE_LATENCY = 600;
const DECISION_LATENCY = 450;
const STEP_MS = 350;

const plans = new Map<number, TaskPlan>();
const finals = new Map<number, TaskDetail>();
const streams = new Map<number, StreamSnapshot>();
const listeners = new Map<number, Set<() => void>>();

let nextId = 0;

const EMPTY: StreamSnapshot = { steps: [], status: "", execution: null, connected: false };

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function ensure(taskId: number): StreamSnapshot {
  let stream = streams.get(taskId);
  if (!stream) {
    stream = { steps: [], status: "awaiting_approval", execution: null, connected: true };
    streams.set(taskId, stream);
  }
  return stream;
}

function emit(taskId: number): void {
  const set = listeners.get(taskId);
  if (set) {
    for (const fn of set) {
      fn();
    }
  }
}

export function subscribe(taskId: number, fn: () => void): () => void {
  let set = listeners.get(taskId);
  if (!set) {
    set = new Set();
    listeners.set(taskId, set);
  }
  set.add(fn);
  return () => {
    set?.delete(fn);
  };
}

export function snapshot(taskId: number): StreamSnapshot {
  const stream = streams.get(taskId);
  if (!stream) {
    return EMPTY;
  }
  return {
    steps: stream.steps,
    status: stream.status,
    execution: stream.execution,
    connected: stream.connected,
  };
}

function awaitingDetail(plan: TaskPlan): TaskDetail {
  return {
    id: plan.task.id,
    workflow: plan.task.workflow,
    instruction: plan.task.instruction,
    fields: plan.task.fields,
    status: "awaiting_approval",
    executions: [],
    revise_notice: null,
  };
}

function baseDetail(taskId: number): TaskDetail {
  const plan = plans.get(taskId);
  if (plan) {
    return awaitingDetail(plan);
  }
  return {
    id: taskId,
    workflow: "shutchou",
    instruction: "",
    fields: {},
    status: "",
    executions: [],
    revise_notice: null,
  };
}

function submittedDetail(taskId: number, executionId: number, steps: TaskStep[], tripId: number): TaskDetail {
  const execution: Execution = {
    id: executionId,
    attempt_no: 1,
    status: "submitted",
    final_screen: "submitted",
    trip_id: tripId,
    trip_created: true,
    executed_steps: steps.length,
    errors: null,
    correction_candidate: null,
    steps,
  };
  return { ...baseDetail(taskId), status: "submitted", executions: [execution], revise_notice: null };
}

function startStream(taskId: number): void {
  const executionId = taskId;
  const all = buildSteps(executionId);
  const stream = ensure(taskId);
  stream.steps = [];
  stream.status = "running";
  stream.execution = null;
  stream.connected = true;
  emit(taskId);
  let index = 0;
  const advance = (): void => {
    if (index >= all.length) {
      stream.status = "submitted";
      stream.execution = { taskId, status: "submitted", tripId: DEFAULT_TRIP_ID, badData: false, finished: true };
      finals.set(taskId, submittedDetail(taskId, executionId, all, DEFAULT_TRIP_ID));
      emit(taskId);
      return;
    }
    stream.steps = all.slice(0, index + 1);
    index += 1;
    emit(taskId);
    window.setTimeout(advance, STEP_MS);
  };
  window.setTimeout(advance, STEP_MS);
}

export async function createTask(request: PlanRequest): Promise<TaskPlan> {
  await delay(PLAN_LATENCY);
  nextId += 1;
  const id = nextId;
  const plan = buildPlan(id, request);
  plans.set(id, plan);
  const stream = ensure(id);
  stream.steps = [];
  stream.status = "awaiting_approval";
  stream.execution = null;
  stream.connected = true;
  emit(id);
  return plan;
}

export async function getDetail(taskId: number): Promise<TaskDetail> {
  await delay(DECISION_LATENCY);
  const final = finals.get(taskId);
  if (final) {
    return final;
  }
  const plan = plans.get(taskId);
  if (plan) {
    return awaitingDetail(plan);
  }
  throw new Error("タスクが見つかりません");
}

export async function getPlan(taskId: number): Promise<TaskPlan> {
  await delay(DECISION_LATENCY);
  const plan = plans.get(taskId);
  if (!plan) {
    throw new Error("計画が見つかりません");
  }
  return plan;
}

export async function approve(taskId: number): Promise<TaskDetail> {
  await delay(APPROVE_LATENCY);
  startStream(taskId);
  return { ...baseDetail(taskId), status: "running", executions: [], revise_notice: null };
}

export async function reject(taskId: number): Promise<TaskDetail> {
  await delay(DECISION_LATENCY);
  const detail: TaskDetail = { ...baseDetail(taskId), status: "refused", executions: [], revise_notice: null };
  finals.set(taskId, detail);
  const stream = ensure(taskId);
  stream.status = "refused";
  emit(taskId);
  return detail;
}

export async function revise(taskId: number, _text: string): Promise<TaskDetail> {
  await delay(DECISION_LATENCY);
  return { ...baseDetail(taskId), revise_notice: null };
}
