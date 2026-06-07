import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from backend.corrections import decision_text_rejection_reason


class TaskCreate(BaseModel):
    workflow: str
    instruction: str
    fields: dict
    dedup_key: str | None = None


class DecisionInput(BaseModel):
    approver: str
    decision_text: str | None = None

    @field_validator("decision_text")
    @classmethod
    def _bounded_decision_text(cls, value: str | None) -> str | None:
        reason = decision_text_rejection_reason(value)
        if reason is not None:
            raise ValueError(reason)
        return value


EventType = Literal[
    "task_created",
    "execution_started",
    "execution_finished",
    "status_changed",
    "step_executed",
    "plan_ready",
    "approved",
    "rejected",
    "revised",
]


class Envelope(BaseModel):
    type: EventType
    task_id: int
    seq: int
    ts: dt.datetime
    payload: dict


class TaskStepView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    execution_id: int
    ordinal: int
    intent: str
    action: dict
    screen: str | None
    screen_fields: dict
    status: str
    errors: list | None
    created_at: dt.datetime


class ExecutionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    attempt_no: int
    status: str
    final_screen: str | None
    trip_id: int | None
    trip_created: bool | None
    executed_steps: int
    errors: list | None
    correction_candidate: dict | None
    started_at: dt.datetime
    finished_at: dt.datetime | None
    steps: list[TaskStepView] = []


class TaskView(BaseModel):
    id: int
    dedup_key: str | None
    workflow: str
    instruction: str
    fields: dict
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime
    executions: list[ExecutionView]


class PlanView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    version: int
    analysis: dict
    keysequence: list
    grounding: list
    status: str
    created_at: dt.datetime


class RefusalView(BaseModel):
    reason: str
    missing_fields: list[str]


class TaskPlanView(BaseModel):
    task: TaskView
    plan: PlanView | None = None
    refusal: RefusalView | None = None
