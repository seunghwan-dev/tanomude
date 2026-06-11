import type * as RealApi from "../src/api";
import { approve, createTask, getDetail, getPlan, reject, revise } from "./mockStore";

export type {
  Slots,
  Step,
  Grounding,
  Plan,
  Refusal,
  TaskView,
  TaskPlan,
  TaskStep,
  CorrectionCandidate,
  Execution,
  TaskDetail,
  EventType,
  Envelope,
  PlanRequest,
  DecisionRequest,
} from "../src/api";
export { DecisionError } from "../src/api";

export const planTask: typeof RealApi.planTask = (request) => createTask(request);

export const getTask: typeof RealApi.getTask = (taskId) => getDetail(taskId);

export const getTaskPlan: typeof RealApi.getTaskPlan = (taskId) => getPlan(taskId);

export const approveTask: typeof RealApi.approveTask = (taskId) => approve(taskId);

export const rejectTask: typeof RealApi.rejectTask = (taskId) => reject(taskId);

export const reviseTask: typeof RealApi.reviseTask = (taskId, body) => revise(taskId, body.decision_text ?? "");
